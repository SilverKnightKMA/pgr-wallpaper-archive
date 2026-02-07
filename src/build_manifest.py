#!/usr/bin/env python3
"""Build detailed wallpaper manifest with per-file status and URL info."""
import json
import sys
import os
import urllib.parse


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


def main():
    if len(sys.argv) < 5:
        print("Usage: build_manifest.py <wp_dir> <repo_dir> <timestamp> <server_id> [<server_id>...]", file=sys.stderr)
        sys.exit(1)

    wp_dir = sys.argv[1]
    repo_dir = sys.argv[2]
    timestamp = sys.argv[3]
    server_ids = sys.argv[4:]

    # Load existing manifest if passed via stdin
    if sys.stdin.isatty():
        manifest = {}
    else:
        data = sys.stdin.read()
        data = data.strip()
        manifest = json.loads(data) if data else {}

    for sid in server_ids:
        img_dir = os.path.join(repo_dir, 'branches', sid, 'images')
        # Wallpapers branch: files at root (flat structure)
        wp_branch_root = wp_dir
        txt_file = os.path.join(repo_dir, 'Wallpapers', 'images_url', f'{sid}.txt')
        failed_file = os.path.join(repo_dir, 'Wallpapers', 'failed', f'{sid}.txt')

        # Directories to search for file sizes (new downloads + wallpapers branch root)
        size_dirs = [d for d in [img_dir, wp_branch_root] if os.path.isdir(d)]

        # Count new images
        image_count = 0
        if os.path.isdir(img_dir):
            image_count = len([f for f in os.listdir(img_dir)
                             if os.path.isfile(os.path.join(img_dir, f))
                             and f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])

        # Count existing images on wallpapers branch (flat root)
        # We need the list of files that belong to this server from prior manifest
        existing_count = 0
        prior_filenames = set()
        if sid in manifest and 'wallpapers' in manifest[sid]:
            for pw in manifest[sid]['wallpapers']:
                if pw.get('status') == 'success':
                    prior_filenames.add(pw['filename'])
            existing_count = len(prior_filenames)

        success = existing_count + image_count

        # Count failed
        failed_count = 0
        failed_urls = []
        if os.path.isfile(failed_file):
            with open(failed_file) as f:
                failed_urls = [line.strip() for line in f if line.strip()]
            failed_count = len(failed_urls)

        total = success + failed_count

        # Build detailed wallpaper list
        wallpapers = []
        existing_names = set()

        # Seed maps from prior manifest to retain source URLs/times/sizes for older wallpapers
        prior_url_map = {}
        prior_release_time_map = {}
        prior_size_map = {}
        if sid in manifest and 'wallpapers' in manifest[sid]:
            for pw in manifest[sid]['wallpapers']:
                if pw.get('url'):
                    prior_url_map[pw['filename']] = pw['url']
                if pw.get('releaseTime'):
                    prior_release_time_map[pw['filename']] = pw['releaseTime']
                if pw.get('size'):
                    prior_size_map[pw['filename']] = pw['size']

        # Collect existing wallpapers from the prior manifest (flat root structure)
        for fn in sorted(prior_filenames):
            size = get_file_size(size_dirs, fn)
            size_str = prior_size_map.get(fn, '')
            if size > 0:
                size_str = format_size(size)
            wallpapers.append({
                'filename': fn,
                'status': 'success',
                'url': prior_url_map.get(fn, ''),
                'releaseTime': prior_release_time_map.get(fn, timestamp),
                'size': size_str
            })
            existing_names.add(fn)

        # Add newly downloaded wallpapers with their URLs
        if os.path.isfile(txt_file):
            with open(txt_file) as f:
                for line in f:
                    url = line.strip()
                    if not url:
                        continue
                    raw_fn = os.path.basename(url)
                    decoded_fn = urllib.parse.unquote(raw_fn)
                    fn = decoded_fn if decoded_fn != raw_fn else raw_fn
                    if fn not in existing_names:
                        size = get_file_size(size_dirs, fn)
                        size_str = format_size(size) if size > 0 else ''
                        wallpapers.append({
                            'filename': fn, 'url': url, 'status': 'success',
                            'releaseTime': timestamp, 'size': size_str
                        })
                        existing_names.add(fn)
                    else:
                        # Update URL for existing entry if missing
                        for w in wallpapers:
                            if w['filename'] == fn and not w.get('url'):
                                w['url'] = url
                                break

        # Add failed URLs
        for url in failed_urls:
            raw_fn = os.path.basename(url)
            decoded_fn = urllib.parse.unquote(raw_fn)
            fn = decoded_fn if decoded_fn != raw_fn else raw_fn
            wallpapers.append({
                'filename': fn, 'url': url, 'status': 'failed',
                'releaseTime': timestamp, 'size': ''
            })

        manifest[sid] = {
            'total': total,
            'success': success,
            'failed': failed_count,
            'lastUpdated': timestamp,
            'wallpapers': wallpapers
        }

    # Store a single releaseTime for the entire action run
    manifest['releaseTime'] = timestamp

    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
