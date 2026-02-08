#!/usr/bin/env python3
"""Build detailed wallpaper manifest with full metadata from scraped JSON.

Merges scraped picture data from the CDN JSON with the existing manifest,
preserving custom fields added by the user while incorporating all original
JSON fields (pictureId, pictureType, terminalType, nameIn, packageUrl, etc.).

Usage:
    python3 build_manifest.py <wp_dir> <repo_dir> <timestamp> <server_id> [...]
    # Reads existing manifest from stdin
"""
import json
import sys
import os
import urllib.parse
from datetime import datetime

CATEGORIES = ['desktop', 'mobile']

# terminalType → folder category (same mapping as scraper)
TERMINAL_CATEGORY = {
    6: 'mobile',
    7: 'desktop',
    20: 'desktop',
}


def format_size(size_bytes):
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_file_size(directories, filename):
    """Look up file size across multiple directories, return bytes or 0."""
    for d in directories:
        fp = os.path.join(d, filename)
        if os.path.isfile(fp):
            return os.path.getsize(fp)
    return 0


def filename_from_url(url):
    """Extract a clean filename from a URL."""
    raw = os.path.basename(urllib.parse.urlparse(url).path.rstrip('/'))
    try:
        decoded = urllib.parse.unquote(raw)
    except Exception:
        decoded = raw
    return decoded or raw


def epoch_ms_to_iso(ms):
    """Convert epoch milliseconds to ISO datetime string."""
    if not ms or not isinstance(ms, (int, float)):
        return ''
    try:
        return datetime.utcfromtimestamp(ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
    except (OSError, ValueError):
        return ''


def build_picture_index(scraped_metadata, server_id):
    """Build an index from scraped metadata keyed by pictureId.

    Returns dict mapping pictureId -> picture data.
    """
    index = {}
    server_meta = scraped_metadata.get(server_id, {})
    pictures = server_meta.get('pictures', [])
    for pic in pictures:
        pid = pic.get('pictureId')
        if pid is not None:
            index[pid] = pic
    return index


def build_url_to_picture_map(pictures):
    """Build a map from URL basename -> picture data for URL-based matching."""
    url_map = {}
    for pic in pictures:
        for key in ('packageUrl', 'imgUrl', 'condenseImg', 'deputyImgUrl'):
            url = pic.get(key, '')
            if url and url.startswith('http'):
                fn = filename_from_url(url)
                if fn:
                    url_map[fn] = pic
    return url_map


# Standard fields from the CDN JSON to preserve in manifest
PICTURE_FIELDS = [
    'gameId', 'pictureId', 'pictureType', 'terminalType',
    'packageUrl', 'imgUrl', 'condenseImg', 'deputyImgUrl',
    'nameIn', 'nameOut', 'versionOut',
    'sortingMark', 'startTime', 'endTime', 'ossUpdate',
    'roleAudioUrl', 'audioUrl', 'audioTime',
    'roleLeve', 'voiceCn', 'voiceJp', 'voiceGd',
    'videoLink', 'videoType', 'clickUrl',
]


def main():
    if len(sys.argv) < 5:
        print("Usage: build_manifest.py <wp_dir> <repo_dir> <timestamp> <server_id> [...]",
              file=sys.stderr)
        sys.exit(1)

    wp_dir = sys.argv[1]
    repo_dir = sys.argv[2]
    run_timestamp = sys.argv[3]
    server_ids = sys.argv[4:]

    # Load config
    config_path = os.path.join(repo_dir, 'config.json')
    server_name_map = {}
    if os.path.isfile(config_path):
        try:
            with open(config_path, encoding='utf-8') as cf:
                config = json.load(cf)
        except json.JSONDecodeError as e:
            print(f"Error: Failed to parse config: {e}", file=sys.stderr)
            config = {}
        for s in config.get('servers', []):
            server_name_map[s['id']] = s.get('name', s['id'])

    # Load scraped metadata (produced by scraper.py)
    scraped_path = os.path.join(repo_dir, 'data', 'scraped_metadata.json')
    scraped_metadata = {}
    if os.path.isfile(scraped_path):
        try:
            with open(scraped_path, encoding='utf-8') as f:
                scraped_metadata = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not load scraped metadata: {e}", file=sys.stderr)

    # Load existing manifest from stdin
    if sys.stdin.isatty():
        manifest = {}
    else:
        data = sys.stdin.read().strip()
        manifest = json.loads(data) if data else {}

    for sid in server_ids:
        wp_branch_root = wp_dir

        # Collect size lookup dirs across both categories
        size_dirs = {}
        for cat in CATEGORIES:
            img_dir = os.path.join(repo_dir, 'branches', sid, 'images', cat)
            wp_cat_dir = os.path.join(wp_dir, cat)
            size_dirs[cat] = [d for d in [img_dir, wp_cat_dir] if os.path.isdir(d)]

        # Build picture index from scraped data for metadata enrichment
        pic_index = build_picture_index(scraped_metadata, sid)
        server_pics = scraped_metadata.get(sid, {}).get('pictures', [])
        url_pic_map = build_url_to_picture_map(server_pics)

        # ---- Preserve prior manifest data (custom fields, etc.) ----
        prior_wallpaper_map = {}  # filename -> full wallpaper dict
        success_filenames = set()

        if sid in manifest and 'wallpapers' in manifest[sid]:
            for pw in manifest[sid]['wallpapers']:
                fn = pw.get('filename')
                if not fn:
                    continue
                prior_wallpaper_map[fn] = pw
                if pw.get('status') == 'success':
                    success_filenames.add(fn)

        # ---- Load failed URLs first to exclude from success ----
        failed_urls = []
        failed_filenames = set()
        for cat in CATEGORIES:
            failed_file = os.path.join(repo_dir, 'Wallpapers', 'failed', f'{sid}_{cat}.txt')
            if os.path.isfile(failed_file):
                with open(failed_file, encoding='utf-8') as f:
                    for line in f:
                        url = line.strip()
                        if url:
                            failed_urls.append(url)
                            failed_filenames.add(filename_from_url(url))
        failed_count = len(failed_urls)

        # ---- Add NEW filenames from images_url txt (new discoveries) ----
        new_url_map = {}  # filename -> (url, category)
        for cat in CATEGORIES:
            txt_file = os.path.join(repo_dir, 'Wallpapers', 'images_url', f'{sid}_{cat}.txt')
            if os.path.isfile(txt_file):
                with open(txt_file, encoding='utf-8') as f:
                    for line in f:
                        url = line.strip()
                        if not url:
                            continue
                        fn = filename_from_url(url)
                        new_url_map[fn] = (url, cat)
                        # Only mark as success if not in failed list AND file exists on disk
                        if fn not in failed_filenames and get_file_size(size_dirs.get(cat, []), fn) > 0:
                            success_filenames.add(fn)

        success = len(success_filenames)
        total = success + failed_count

        # ---- Build wallpaper entries with full metadata ----
        wallpapers = []

        for fn in sorted(success_filenames):
            # Start with prior data to preserve custom fields
            entry = dict(prior_wallpaper_map.get(fn, {}))

            # Core fields
            entry['filename'] = fn
            entry['server'] = server_name_map.get(sid, sid)
            entry['status'] = 'success'

            # URL and category
            if fn in new_url_map:
                entry['url'] = new_url_map[fn][0]
                entry['category'] = new_url_map[fn][1]
            elif 'url' not in entry:
                entry['url'] = ''

            # Determine category from picture metadata if not set
            if 'category' not in entry:
                pic = url_pic_map.get(fn)
                if pic:
                    tt = pic.get('terminalType', 20)
                    entry['category'] = TERMINAL_CATEGORY.get(tt, 'desktop')
                else:
                    entry['category'] = 'desktop'

            # Release time
            if 'releaseTime' not in entry:
                entry['releaseTime'] = run_timestamp

            # File size
            size = get_file_size(size_dirs, fn)
            if size > 0:
                entry['size'] = format_size(size)
            elif 'size' not in entry:
                entry['size'] = ''

            # ---- Enrich with scraped picture metadata ----
            # Try to match by filename -> URL -> picture data
            pic_data = url_pic_map.get(fn)
            if pic_data:
                for field in PICTURE_FIELDS:
                    if field in pic_data and pic_data[field] not in (None, ''):
                        val = pic_data[field]
                        # Convert epoch ms timestamps to readable format
                        if field in ('startTime', 'endTime', 'ossUpdate') and isinstance(val, (int, float)):
                            entry[field] = val  # keep raw epoch ms
                            entry[f'{field}_formatted'] = epoch_ms_to_iso(val)
                        else:
                            entry[field] = val

            wallpapers.append(entry)

        # Add failed URLs
        for url in failed_urls:
            fn = filename_from_url(url)
            entry = dict(prior_wallpaper_map.get(fn, {}))
            entry['filename'] = fn
            entry['server'] = server_name_map.get(sid, sid)
            entry['url'] = url
            entry['status'] = 'failed'
            entry['releaseTime'] = run_timestamp
            entry['size'] = ''
            wallpapers.append(entry)

        # ---- Build server-level metadata ----
        server_entry = {
            'name': server_name_map.get(sid, sid),
            'total': total,
            'success': success,
            'failed': failed_count,
            'lastUpdated': run_timestamp,
            'wallpapers': wallpapers,
        }

        # Store full picture catalog from JSON separately for reference
        if server_pics:
            server_entry['pictureCount'] = len(server_pics)
            server_entry['pictureTypes'] = sorted(set(
                p.get('pictureType') for p in server_pics if p.get('pictureType') is not None
            ))

        # Preserve any custom top-level fields from prior manifest
        if sid in manifest:
            for k, v in manifest[sid].items():
                if k not in server_entry and k != 'wallpapers':
                    server_entry[k] = v

        manifest[sid] = server_entry

    # Store a single releaseTime for the entire action run
    manifest['releaseTime'] = run_timestamp

    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
