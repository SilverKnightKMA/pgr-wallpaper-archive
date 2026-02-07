#!/usr/bin/env python3
"""Compare old and new manifests to find truly new wallpapers per server.

Writes per-server txt files containing only URLs for wallpapers that are
new (not present in the old manifest with success status).

Usage: diff_manifest.py <old_manifest> <new_manifest> <output_dir>
"""
import json
import os
import sys


def main():
    if len(sys.argv) < 4:
        print("Usage: diff_manifest.py <old_manifest> <new_manifest> <output_dir>", file=sys.stderr)
        sys.exit(1)

    old_path = sys.argv[1]
    new_path = sys.argv[2]
    output_dir = sys.argv[3]

    # Load old manifest
    old_manifest = {}
    if os.path.isfile(old_path):
        try:
            with open(old_path, encoding='utf-8') as f:
                old_manifest = json.load(f)
        except (json.JSONDecodeError, OSError):
            old_manifest = {}

    # Load new manifest
    if not os.path.isfile(new_path):
        print(f"Error: New manifest not found: {new_path}", file=sys.stderr)
        sys.exit(1)

    with open(new_path, encoding='utf-8') as f:
        new_manifest = json.load(f)

    os.makedirs(output_dir, exist_ok=True)

    for sid, server_data in new_manifest.items():
        if not isinstance(server_data, dict) or 'wallpapers' not in server_data:
            continue

        # Build set of filenames from old manifest (success only)
        old_filenames = set()
        if sid in old_manifest and isinstance(old_manifest[sid], dict):
            for w in old_manifest[sid].get('wallpapers', []):
                fn = w.get('filename')
                if fn and w.get('status') == 'success':
                    old_filenames.add(fn)

        # Find new wallpapers (in new but not in old)
        new_urls = []
        for w in server_data['wallpapers']:
            fn = w.get('filename')
            if fn and w.get('status') == 'success' and fn not in old_filenames:
                url = w.get('url', '')
                if url:
                    new_urls.append(url)

        # Write per-server file
        out_file = os.path.join(output_dir, f'{sid}.txt')
        with open(out_file, 'w') as f:
            for url in new_urls:
                f.write(url + '\n')

        count = len(new_urls)
        if count > 0:
            print(f"[{sid}] {count} new wallpapers")


if __name__ == '__main__':
    main()
