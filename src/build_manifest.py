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

        # Build prior filename mapping and get existing success filenames from old manifest
        # NOTE: images_url txt files contain only NEW links per run (scraper truncates when none found)
        # So we must merge with prior manifest to preserve existing wallpapers
        prior_url_map = {}
        prior_release_time_map = {}
        prior_size_map = {}
        success_filenames = set()
        
        if sid in manifest and 'wallpapers' in manifest[sid]:
            for pw in manifest[sid]['wallpapers']:
                filename = pw.get('filename')
                if not filename:
                    continue
                # Preserve existing successful wallpapers
                if pw.get('status') == 'success':
                    success_filenames.add(filename)
                # Preserve metadata for all wallpapers
                if pw.get('url'):
                    prior_url_map[filename] = pw['url']
                if pw.get('releaseTime'):
                    prior_release_time_map[filename] = pw['releaseTime']
                if pw.get('size'):
                    prior_size_map[filename] = pw['size']

        # Add NEW filenames from images_url txt file (new discoveries this run)
        if os.path.isfile(txt_file):
            with open(txt_file) as f:
                for line in f:
                    url = line.strip()
                    if not url:
                        continue
                    raw_fn = os.path.basename(url)
                    decoded_fn = urllib.parse.unquote(raw_fn)
                    fn = decoded_fn if decoded_fn != raw_fn else raw_fn
                    success_filenames.add(fn)
                    # Update URL for new or previously missing URLs
                    if fn not in prior_url_map or not prior_url_map[fn]:
                        prior_url_map[fn] = url

        success = len(success_filenames)

        # Count failed
        failed_count = 0
        failed_urls = []
        if os.path.isfile(failed_file):
            with open(failed_file) as f:
                failed_urls = [line.strip() for line in f if line.strip()]
            failed_count = len(failed_urls)

        total = success + failed_count

        # Build detailed wallpaper list from success_filenames (deduplicated set)
        wallpapers = []
        
        # Add all successful wallpapers from the deduplicated set
        for fn in sorted(success_filenames):
            # Get file size
            size = get_file_size(size_dirs, fn)
            size_str = prior_size_map.get(fn, '')
            if size > 0:
                size_str = format_size(size)
            
            wallpapers.append({
                'filename': fn,
                'url': prior_url_map.get(fn, ''),
                'status': 'success',
                'releaseTime': prior_release_time_map.get(fn, timestamp),
                'size': size_str
            })

        # Add failed URLs
        for url in failed_urls:
            raw_fn = os.path.basename(url)
            decoded_fn = urllib.parse.unquote(raw_fn)
            fn = decoded_fn if decoded_fn != raw_fn else raw_fn
            wallpapers.append({
                'filename': fn,
                'url': url,
                'status': 'failed',
                'releaseTime': timestamp,
                'size': ''
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
