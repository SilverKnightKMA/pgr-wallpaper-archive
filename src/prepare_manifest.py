import json
import sys
import os

# Usage: python3 src/prepare_manifest.py <server_id>
if len(sys.argv) < 2:
    sys.exit(1)

server_id = sys.argv[1]
manifest_path = 'data/manifest.json'

if not os.path.exists(manifest_path):
    sys.exit(0)

try:
    with open(manifest_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if server_id in data and 'wallpapers' in data[server_id]:
        for w in data[server_id]['wallpapers']:
            fn = w.get('filename')
            status = w.get('status')
            if fn and status == 'success':
                # Output just the filename (used for dedup check by scraper)
                print(fn)
except Exception as e:
    sys.stderr.write(f"Error reading manifest: {e}\n")
