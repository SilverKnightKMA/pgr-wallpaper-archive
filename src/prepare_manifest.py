import json
import re
import sys
import os

# Usage: python3 src/prepare_manifest.py <server_id>
#
# Outputs dedup keys (one per line) for images already archived successfully
# for this server, in the form "<sourceFilename>|<ts-bucket>" where ts-bucket
# is the /images/<ts>/ segment of the stored imgUrl (empty if not extractable).
# Consumed by src/scraper.py so that a re-upload of the same basename under a
# NEW timestamp is detected as a new image instead of being silently skipped.

if len(sys.argv) < 2:
    sys.exit(1)

server_id = sys.argv[1]
manifest_path = 'data/manifest.json'

TS_RE = re.compile(r'/images/(\d+)/')


def ts_bucket_from_url(url):
    """Extract the /images/<ts>/ segment from a Kuro CDN URL ('' if absent)."""
    if not isinstance(url, str):
        return ''
    m = TS_RE.search(url)
    return m.group(1) if m else ''


if not os.path.exists(manifest_path):
    sys.exit(0)

try:
    with open(manifest_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if server_id in data and 'wallpapers' in data[server_id]:
        for w in data[server_id]['wallpapers']:
            fn = w.get('sourceFilename') or w.get('filename')
            status = w.get('status')
            if fn and status == 'success':
                ts = ts_bucket_from_url(w.get('imgUrl', ''))
                print(f'{fn}|{ts}')
except Exception as e:
    sys.stderr.write(f"Error reading manifest: {e}\n")
