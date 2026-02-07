#!/usr/bin/env python3
"""Build detailed wallpaper manifest with per-file status and URL info."""
import json
import sys
import os
import urllib.parse


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
        wp_branch_img_dir = os.path.join(wp_dir, sid, 'images')
        txt_file = os.path.join(repo_dir, 'Wallpapers', 'images_url', f'{sid}.txt')
        failed_file = os.path.join(repo_dir, 'Wallpapers', 'failed', f'{sid}.txt')

        # Count new images
        image_count = 0
        if os.path.isdir(img_dir):
            image_count = len([f for f in os.listdir(img_dir)
                             if os.path.isfile(os.path.join(img_dir, f))
                             and f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])

        # Count existing images on wallpapers branch
        existing_count = 0
        if os.path.isdir(wp_branch_img_dir):
            existing_count = len([f for f in os.listdir(wp_branch_img_dir)
                                if os.path.isfile(os.path.join(wp_branch_img_dir, f))
                                and f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])

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

        # Seed URL map from prior manifest to retain source URLs for older wallpapers
        prior_url_map = {}
        if sid in manifest and 'wallpapers' in manifest[sid]:
            for pw in manifest[sid]['wallpapers']:
                if pw.get('url'):
                    prior_url_map[pw['filename']] = pw['url']

        # Collect existing wallpapers from the wallpapers branch
        if os.path.isdir(wp_branch_img_dir):
            for fn in sorted(os.listdir(wp_branch_img_dir)):
                fp = os.path.join(wp_branch_img_dir, fn)
                if os.path.isfile(fp) and fn.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    wallpapers.append({'filename': fn, 'status': 'success', 'url': prior_url_map.get(fn, '')})
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
                        wallpapers.append({'filename': fn, 'url': url, 'status': 'success'})
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
            wallpapers.append({'filename': fn, 'url': url, 'status': 'failed'})

        manifest[sid] = {
            'total': total,
            'success': success,
            'failed': failed_count,
            'lastUpdated': timestamp,
            'wallpapers': wallpapers
        }

    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
