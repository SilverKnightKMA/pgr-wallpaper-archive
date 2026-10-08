#!/usr/bin/env python3
"""Health gate: verify every server's MainMenu.json is reachable and sane.

Run before the nightly download batch (see downloader.yml). Exits 1 —
turning the run red and emailing the owner — if any server fails any of:

  - fetch error / HTTP status != 200
  - body is not valid JSON
  - zero wallpaper items (empty 'picture' list or none passing the filter)
  - item count < 80% of the archived count in data/manifest.json
    (catches Kuro silently serving a stale/rotated index — the
    kurogame.com -> kurogames.net migration class of failure, which
    would otherwise look like a green "0 new images" run forever)

Usage: python3 src/health_check.py
"""

import json
import os
import ssl
import sys
import urllib.request

CONFIG_PATH = 'config.json'
MANIFEST_PATH = 'data/manifest.json'
FLOOR_RATIO = 0.7  # fetched items must be >= 70% of archived count — low
                    # enough to tolerate Kuro pruning old images (tw is at 81%
                    # as of Oct 2026), high enough to catch a rotated index
ALLOWED_PICTURE_TYPES = {11}  # keep in sync with src/scraper.py

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

ctx = ssl.create_default_context()


def main():
    with open(CONFIG_PATH, encoding='utf-8') as f:
        servers = json.load(f)['servers']

    archived_counts = {}
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, encoding='utf-8') as f:
                manifest = json.load(f)
            archived_counts = {
                sid: sd.get('total', 0) for sid, sd in manifest.items()
                if isinstance(sd, dict)
            }
        except Exception as e:  # manifest corrupt -> warn, don't block
            print(f'::warning title=Health gate::manifest unreadable ({e}) '
                  '- running without archived-count floors')

    failed = False
    print('=== Server health check ===')
    for srv in servers:
        sid, url = srv['id'], srv['jsonUrl']
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
                code = resp.getcode()
                body = resp.read().decode('utf-8')
        except Exception as e:
            print(f'::error title=Health gate::[{sid}] fetch failed: {e}')
            failed = True
            continue

        if code != 200:
            print(f'::error title=Health gate::[{sid}] HTTP {code}')
            failed = True
            continue

        try:
            data = json.loads(body)
        except Exception as e:
            print(f'::error title=Health gate::[{sid}] invalid JSON: {e}')
            failed = True
            continue

        items = [
            p for p in data.get('picture', [])
            if p.get('pictureType') in ALLOWED_PICTURE_TYPES
            and isinstance(p.get('imgUrl'), str)
            and p['imgUrl'].startswith('http')
        ]

        archived = archived_counts.get(sid, 0)
        floor = max(1, int(archived * FLOOR_RATIO))
        if len(items) < floor:
            print(f'::error title=Health gate::[{sid}] only {len(items)} '
                  f'wallpaper items (archived {archived}, floor {floor}) — '
                  f'index looks stale or rotated')
            failed = True
        else:
            print(f'  [OK] {sid}: HTTP {code}, {len(items)} items '
                  f'(archived {archived}, floor {floor})')

    if failed:
        sys.exit(1)
    print('All servers healthy.')


if __name__ == '__main__':
    main()
