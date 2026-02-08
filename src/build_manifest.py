#!/usr/bin/env python3
"""Build detailed wallpaper manifest with full metadata from scraped JSON.

Merges scraped picture data from the CDN JSON with the existing manifest,
preserving custom fields added by the user while incorporating all original
JSON fields.

Key changes from previous version:
  - Uses resolution-based category detection (landscape=desktop, portrait=mobile)
  - Stores resolution field in manifest entries
  - Uses imgUrl instead of redundant url field
  - Properly separates startTime (image publish time) and releaseTime (GitHub archive time)

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
    """Build an index from scraped metadata keyed by pictureId."""
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
        for key in ('imgUrl', 'condenseImg', 'deputyImgUrl'):
            url = pic.get(key, '')
            if url and url.startswith('http'):
                fn = filename_from_url(url)
                if fn:
                    url_map[fn] = pic
    return url_map


def get_resolution_from_file(filepath):
    """Get image resolution using Pillow. Returns (width, height) or (0, 0)."""
    try:
        from PIL import Image
        with Image.open(filepath) as img:
            return img.size
    except Exception:
        return (0, 0)


def determine_category(width, height):
    """Determine category from resolution: landscape=desktop, portrait=mobile."""
    if width <= 0 or height <= 0:
        return 'desktop'
    return 'desktop' if width >= height else 'mobile'


# Standard fields from the CDN JSON to preserve in manifest
PICTURE_FIELDS = [
    'gameId', 'pictureId', 'pictureType', 'terminalType',
    'imgUrl', 'condenseImg',
    'nameIn', 'nameOut', 'versionOut',
    'sortingMark', 'startTime', 'endTime', 'ossUpdate',
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

    # Load image metadata (produced by process_images.py)
    img_meta_path = os.path.join(repo_dir, 'data', 'image_metadata.json')
    image_metadata = {}
    if os.path.isfile(img_meta_path):
        try:
            with open(img_meta_path, encoding='utf-8') as f:
                image_metadata = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not load image metadata: {e}", file=sys.stderr)

    # Load existing manifest from stdin
    if sys.stdin.isatty():
        manifest = {}
    else:
        data = sys.stdin.read().strip()
        manifest = json.loads(data) if data else {}

    for sid in server_ids:
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

        # ---- Preserve prior manifest data ----
        prior_wallpaper_map = {}
        success_filenames = set()

        if sid in manifest and 'wallpapers' in manifest[sid]:
            for pw in manifest[sid]['wallpapers']:
                fn = pw.get('filename')
                if not fn:
                    continue
                prior_wallpaper_map[fn] = pw
                if pw.get('status') == 'success':
                    success_filenames.add(fn)

        # ---- Load failed URLs ----
        failed_urls = []
        failed_filenames = set()
        failed_file = os.path.join(repo_dir, 'Wallpapers', 'failed', f'{sid}.txt')
        if os.path.isfile(failed_file):
            with open(failed_file, encoding='utf-8') as f:
                for line in f:
                    url = line.strip()
                    if url:
                        failed_urls.append(url)
                        failed_filenames.add(filename_from_url(url))
        failed_count = len(failed_urls)

        # ---- Add NEW filenames from images_url txt ----
        new_url_map = {}  # filename -> url
        txt_file = os.path.join(repo_dir, 'Wallpapers', 'images_url', f'{sid}.txt')
        if os.path.isfile(txt_file):
            with open(txt_file, encoding='utf-8') as f:
                for line in f:
                    url = line.strip()
                    if not url:
                        continue
                    fn = filename_from_url(url)
                    new_url_map[fn] = url
                    if fn not in failed_filenames:
                        # Check if file exists in any category dir
                        for cat in CATEGORIES:
                            if get_file_size(size_dirs.get(cat, []), fn) > 0:
                                success_filenames.add(fn)
                                break

        success = len(success_filenames)
        total = success + failed_count

        # ---- Build wallpaper entries with full metadata ----
        wallpapers = []

        for fn in sorted(success_filenames):
            entry = dict(prior_wallpaper_map.get(fn, {}))

            # Core fields
            entry['filename'] = fn
            entry['server'] = server_name_map.get(sid, sid)
            entry['status'] = 'success'

            # ---- Resolution + Category (resolution-based) ----
            img_meta = image_metadata.get(fn)
            if img_meta:
                entry['resolution'] = img_meta.get('resolution', '')
                entry['category'] = img_meta.get('category', 'desktop')
                if img_meta.get('preview'):
                    entry['preview'] = img_meta['preview']
            else:
                # Try to get resolution from file in WP_DIR
                resolution_found = False
                for cat in CATEGORIES:
                    filepath = os.path.join(wp_dir, cat, fn)
                    if os.path.isfile(filepath):
                        w, h = get_resolution_from_file(filepath)
                        if w > 0 and h > 0:
                            entry['resolution'] = f'{w}x{h}'
                            entry['category'] = determine_category(w, h)
                            resolution_found = True
                        break
                if not resolution_found:
                    # Preserve prior values or use defaults
                    if 'resolution' not in entry:
                        entry['resolution'] = ''
                    if 'category' not in entry:
                        entry['category'] = 'desktop'

            # imgUrl (primary URL field, replaces old 'url')
            pic_data = url_pic_map.get(fn)
            if pic_data and pic_data.get('imgUrl'):
                entry['imgUrl'] = pic_data['imgUrl']
            elif fn in new_url_map:
                entry['imgUrl'] = new_url_map[fn]
            elif 'imgUrl' not in entry:
                # Migrate from old 'url' field
                entry['imgUrl'] = entry.pop('url', '')

            # Remove old redundant 'url' field if present
            entry.pop('url', None)

            # releaseTime = when archived to GitHub (batch crawl timestamp)
            if 'releaseTime' not in entry:
                entry['releaseTime'] = run_timestamp

            # File size
            cat = entry.get('category', 'desktop')
            size = get_file_size(size_dirs.get(cat, []), fn)
            if size > 0:
                entry['size'] = format_size(size)
            elif 'size' not in entry:
                entry['size'] = ''

            # ---- Enrich with scraped picture metadata ----
            if pic_data:
                for field in PICTURE_FIELDS:
                    if field in pic_data and pic_data[field] not in (None, ''):
                        val = pic_data[field]
                        if field in ('startTime', 'endTime', 'ossUpdate') and isinstance(val, (int, float)):
                            entry[field] = val  # keep raw epoch ms
                            entry[f'{field}_formatted'] = epoch_ms_to_iso(val)
                        elif field == 'imgUrl':
                            entry['imgUrl'] = val  # already handled above
                        else:
                            entry[field] = val

            wallpapers.append(entry)

        # Add failed URLs
        for url in failed_urls:
            fn = filename_from_url(url)
            entry = dict(prior_wallpaper_map.get(fn, {}))
            entry['filename'] = fn
            entry['server'] = server_name_map.get(sid, sid)
            entry['imgUrl'] = url
            entry.pop('url', None)
            entry['status'] = 'failed'
            entry['releaseTime'] = run_timestamp
            entry['size'] = ''
            entry['resolution'] = ''
            entry['category'] = 'desktop'
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

        if server_pics:
            server_entry['pictureCount'] = len(server_pics)

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
