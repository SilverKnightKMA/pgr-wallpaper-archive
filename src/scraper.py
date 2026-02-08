#!/usr/bin/env python3
"""Scraper: Download MainMenu.json from each server, extract wallpaper data.

Fetches picture entries from each server's MainMenu.json and filters to
wallpaper types only (pictureType 11 = wallpapers/CG, 12 = version key visual).
Images are categorized into 'desktop' and 'mobile' based on terminalType:
  - terminalType 7  → desktop (PC)
  - terminalType 6  → mobile
  - terminalType 20 → desktop (universal)

Output:
  - Per-server URL lists: images_url/{server}_{desktop|mobile}.txt
  - Combined metadata: data/scraped_metadata.json

Usage:
    python3 src/scraper.py

Environment variables:
    MAX_IMAGES  – cap on images per server per category (default: unlimited)
"""

import json
import os
import sys
import urllib.parse
import urllib.request
import ssl
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(SCRIPT_DIR, '..')
CONFIG_PATH = os.path.join(REPO_DIR, 'config.json')

# Only download wallpaper/CG (11) and version key visual (12)
ALLOWED_PICTURE_TYPES = {11, 12}

# terminalType → folder category
# Based on PGR website: pcTopPicture uses tt=7, mobileTopPicture uses tt=6
TERMINAL_CATEGORY = {
    6: 'mobile',
    7: 'desktop',
    20: 'desktop',  # universal resolution, stored with desktop
}

CATEGORIES = ['desktop', 'mobile']

timestamp = lambda: datetime.now().strftime('%H:%M:%S')


def load_config():
    if not os.path.isfile(CONFIG_PATH):
        print(f'Error: Config file not found at {CONFIG_PATH}', file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, encoding='utf-8') as f:
        return json.load(f)


def download_json(url):
    """Download and parse a JSON file from a URL."""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
        return json.loads(resp.read().decode('utf-8'))


def list_existing_images(server_id):
    """Load existing image filenames from .existing_images file and local dirs."""
    existing = set()
    branch_dir = os.path.join(REPO_DIR, 'branches', server_id)

    # From .existing_images file (populated by manifest step)
    existing_file = os.path.join(branch_dir, '.existing_images')
    if os.path.isfile(existing_file):
        with open(existing_file, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    existing.add(line)

    # Check local desktop/mobile directories
    for category in CATEGORIES:
        for subdir in [os.path.join(branch_dir, category),
                       os.path.join(branch_dir, 'images', category)]:
            if os.path.isdir(subdir):
                for fn in os.listdir(subdir):
                    if fn.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        existing.add(fn)

    return existing


def extract_download_info(picture_item):
    """Extract downloadable URL and category from a picture item.

    Returns a list of (url, category) tuples.
    Only items with pictureType 11/12 and a valid imgUrl are included.
    """
    results = []
    pt = picture_item.get('pictureType')
    if pt not in ALLOWED_PICTURE_TYPES:
        return results

    img = picture_item.get('imgUrl', '')
    if img and img.startswith('http'):
        tt = picture_item.get('terminalType', 20)
        category = TERMINAL_CATEGORY.get(tt, 'desktop')
        results.append((img, category))

    return results


def filename_from_url(url):
    """Extract a clean filename from a URL."""
    raw = os.path.basename(urllib.parse.urlparse(url).path.rstrip('/'))
    try:
        decoded = urllib.parse.unquote(raw)
    except Exception:
        decoded = raw
    return decoded or raw


def process_server(server, max_images):
    """Process a single server: download JSON, filter wallpapers, find new ones."""
    server_id = server['id']
    server_name = server['name']
    json_url = server.get('jsonUrl', '')

    print(f'\n[{timestamp()}] 🚀 STARTING: {server_name}')

    if not json_url:
        print(f'[{timestamp()}] [{server_name}] ⚠️ No jsonUrl configured, skipping.')
        return [], {'desktop': [], 'mobile': []}

    # Download the MainMenu.json
    print(f'[{timestamp()}] [{server_name}] Downloading: {json_url}')
    try:
        data = download_json(json_url)
    except Exception as e:
        print(f'[{timestamp()}] [{server_name}] ❌ Failed to download JSON: {e}',
              file=sys.stderr)
        return [], {'desktop': [], 'mobile': []}

    # Extract picture array and filter to allowed types
    pictures = data.get('picture', [])
    filtered = [p for p in pictures if p.get('pictureType') in ALLOWED_PICTURE_TYPES]
    print(f'[{timestamp()}] [{server_name}] Found {len(pictures)} picture entries, '
          f'{len(filtered)} are wallpapers (type 11/12)')

    # Load existing images
    existing = list_existing_images(server_id)
    print(f'[{timestamp()}] [{server_name}] 📂 Existing images: {len(existing)}')

    # Collect filtered picture metadata and new URLs by category
    all_pictures = []
    new_urls = {'desktop': [], 'mobile': []}

    for pic in filtered:
        all_pictures.append(pic)

        infos = extract_download_info(pic)
        for url, category in infos:
            fn = filename_from_url(url)
            if fn and fn not in existing:
                new_urls[category].append(url)
                existing.add(fn)  # prevent duplicates within this run

    # Apply max_images cap per category
    if max_images:
        for cat in CATEGORIES:
            if len(new_urls[cat]) > max_images:
                new_urls[cat] = new_urls[cat][:max_images]

    # Write new URLs to per-category txt files
    url_dir = os.path.join(REPO_DIR, 'Wallpapers', 'images_url')
    os.makedirs(url_dir, exist_ok=True)

    total_new = 0
    for cat in CATEGORIES:
        txt_path = os.path.join(url_dir, f'{server_id}_{cat}.txt')
        with open(txt_path, 'w', encoding='utf-8') as f:
            for url in new_urls[cat]:
                f.write(url + '\n')
        count = len(new_urls[cat])
        total_new += count
        if count:
            print(f'[{timestamp()}] [{server_name}] ✅ {count} new {cat} URLs → {txt_path}')

    if total_new == 0:
        print(f'[{timestamp()}] [{server_name}] ⚠️ No new images found')

    return all_pictures, new_urls


def main():
    config = load_config()
    max_images = int(os.environ.get('MAX_IMAGES', '0')) or None

    print('=== SCRAPER STARTED (JSON MODE) ===')
    print(f'[{timestamp()}] Max images per server: {max_images or "unlimited"}')
    print(f'[{timestamp()}] Filter: pictureType in {ALLOWED_PICTURE_TYPES}')
    print(f'[{timestamp()}] Categories: desktop (tt=7,20), mobile (tt=6)')

    # Process all servers and collect metadata
    all_metadata = {}
    for server in config['servers']:
        pictures, new_urls = process_server(server, max_images)
        all_metadata[server['id']] = {
            'name': server['name'],
            'jsonUrl': server.get('jsonUrl', ''),
            'pictures': pictures,
            'newUrls': new_urls,
        }

    # Save combined scraped metadata for use by build_manifest
    metadata_dir = os.path.join(REPO_DIR, 'data')
    os.makedirs(metadata_dir, exist_ok=True)
    metadata_path = os.path.join(metadata_dir, 'scraped_metadata.json')
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, ensure_ascii=False, indent=2)
    print(f'\n[{timestamp()}] 📄 Scraped metadata saved to {metadata_path}')

    print('\n=== ALL TASKS COMPLETED ===\n')


if __name__ == '__main__':
    main()
