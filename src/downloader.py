#!/usr/bin/env python3
"""Download wallpaper images from URL lists.

Reads per-server, per-category URL lists from
Wallpapers/images_url/<server_id>_{desktop|mobile}.txt
and downloads them with concurrent workers into
branches/<server_id>/{desktop|mobile}/.

Usage:
    python3 src/downloader.py
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(SCRIPT_DIR, '..')
CONFIG_PATH = os.path.join(REPO_DIR, 'config.json')
MAX_WORKERS = 16
CATEGORIES = ['desktop', 'mobile']


def load_config():
    with open(CONFIG_PATH, encoding='utf-8') as f:
        return json.load(f)


def encode_url(url):
    """Properly encode a URL that may contain non-ASCII characters or spaces.

    Note: '+' is intentionally NOT in the safe set so it gets encoded as %2B.
    Some CDNs/servers misinterpret literal '+' in URL paths.
    """
    parsed = urllib.parse.urlsplit(url)
    # Re-encode the path: unquote first (to avoid double-encoding), then quote
    path = urllib.parse.unquote(parsed.path)
    path = urllib.parse.quote(path, safe='/:@!$&\'()*,;=-._~')
    # Reconstruct the URL
    return urllib.parse.urlunsplit((
        parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment
    ))


MAX_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]  # seconds between retries


def download_file(url, dest):
    """Download a single file with retry logic.

    Returns (success, filename, error_msg, encoded_url).
    Retries on transient errors (timeouts, 5xx). Does NOT retry on 4xx (e.g. 404).
    """
    ctx = ssl.create_default_context()
    encoded_url = encode_url(url)
    basename = os.path.basename(dest)
    last_err = None

    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(encoded_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
                with open(dest, 'wb') as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
            return True, basename, None, encoded_url
        except urllib.error.HTTPError as e:
            last_err = str(e)
            # Don't retry client errors (4xx) — they won't succeed
            if 400 <= e.code < 500:
                break
            # Server errors (5xx) are retryable
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF[attempt - 1])
        except Exception as e:
            last_err = str(e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF[attempt - 1])
        finally:
            # Clean up partial download on failure
            if not os.path.exists(dest) or os.path.getsize(dest) == 0:
                pass
            elif last_err:
                try:
                    os.remove(dest)
                except OSError:
                    pass

    return False, basename, f'{last_err} (after {attempt} attempt(s))', encoded_url


def process_server(server):
    """Download all new images for a server (both desktop and mobile)."""
    server_id = server['id']
    server_name = server['name']

    print(f'\n--- Processing: {server_name} ---')

    for category in CATEGORIES:
        txt_path = os.path.join(REPO_DIR, 'Wallpapers', 'images_url',
                                f'{server_id}_{category}.txt')
        server_dir = os.path.join(REPO_DIR, 'branches', server_id, category)

        print(f'  [{category}] Reading links from: {txt_path}')

        if not os.path.isfile(txt_path):
            print(f'  [{category}] Skip: File not found.')
            continue

        os.makedirs(server_dir, exist_ok=True)

        # Read URLs
        with open(txt_path, encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        if not urls:
            print(f'  [{category}] No URLs to download.')
            continue

        total = len(urls)
        downloaded = 0
        failed = 0
        failed_urls = []

        # Build download tasks
        tasks = []
        for url in urls:
            raw_fn = os.path.basename(urllib.parse.urlparse(url).path.rstrip('/'))
            try:
                decoded_fn = urllib.parse.unquote(raw_fn)
            except Exception:
                decoded_fn = raw_fn
            filename = decoded_fn if decoded_fn else raw_fn
            dest = os.path.join(server_dir, filename)

            if os.path.isfile(dest):
                print(f'  [{server_name}/{category}] SKIPPED: {filename} (Exists)')
                continue

            tasks.append((url, dest, filename))

        # Download concurrently
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {}
            for idx, (url, dest, filename) in enumerate(tasks, 1):
                future = executor.submit(download_file, url, dest)
                futures[future] = (idx, url, filename)

            for future in as_completed(futures):
                idx, url, filename = futures[future]
                success, fn, err, enc_url = future.result()
                if success:
                    downloaded += 1
                    if downloaded % 10 == 0 or downloaded == len(tasks):
                        print(f'  [{server_name}/{category}] Progress: {downloaded}/{len(tasks)} downloaded')
                else:
                    failed += 1
                    failed_urls.append(url)
                    print(f'  [{server_name}/{category}] ❌ FAILED: {fn}')
                    print(f'    Original URL: {url}')
                    print(f'    Encoded URL:  {enc_url}')
                    print(f'    Error:        {err}')

        print(f'  >> {server_name}/{category}: {downloaded} success, {failed} failed.')

        # Write failed URLs
        failed_dir = os.path.join(REPO_DIR, 'Wallpapers', 'failed')
        os.makedirs(failed_dir, exist_ok=True)
        failed_file = os.path.join(failed_dir, f'{server_id}_{category}.txt')
        if failed_urls:
            with open(failed_file, 'w', encoding='utf-8') as f:
                for url in failed_urls:
                    f.write(url + '\n')
            print(f'  [!] Failed URLs saved to: {failed_file}')
        else:
            # Clear previous failures
            if os.path.isfile(failed_file):
                os.remove(failed_file)


def main():
    config = load_config()
    print('=== PGR DOWNLOADER START ===')

    for server in config['servers']:
        process_server(server)

    print('\n=== ALL DOWNLOADS FINISHED ===')


if __name__ == '__main__':
    main()
