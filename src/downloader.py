#!/usr/bin/env python3
"""Download wallpaper images from URL lists.

Reads per-server URL lists from Wallpapers/images_url/<server_id>.txt
and downloads them into branches/<server_id>/downloads/ (flat directory).

Supports a size limit (MAX_BATCH_BYTES env var, default 1.8GB).
When the limit is reached, downloading stops and remaining URLs are kept
in the txt files for the next iteration.

Exit codes:
    0 - All downloads completed (no remaining)
    2 - Batch limit reached, more downloads remain

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

# 1.8 GB default, overridable via env
MAX_BATCH_BYTES = int(float(os.environ.get('MAX_BATCH_BYTES',
                                            1.8 * 1024 * 1024 * 1024)))


def load_config():
    with open(CONFIG_PATH, encoding='utf-8') as f:
        return json.load(f)


def encode_url(url):
    parsed = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(parsed.path)
    path = urllib.parse.quote(path, safe="/:@!$&'()*,;=-._~")
    return urllib.parse.urlunsplit((
        parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment
    ))


MAX_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]


def download_file(url, dest):
    """Download a single file. Returns (success, filename, error, encoded_url, size)."""
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
            fsize = os.path.getsize(dest)
            return True, basename, None, encoded_url, fsize
        except urllib.error.HTTPError as e:
            last_err = str(e)
            if 400 <= e.code < 500:
                break
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF[attempt - 1])
        except Exception as e:
            last_err = str(e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF[attempt - 1])
        finally:
            if not os.path.exists(dest) or os.path.getsize(dest) == 0:
                pass
            elif last_err:
                try:
                    os.remove(dest)
                except OSError:
                    pass

    return False, basename, f'{last_err} (after {attempt} attempt(s))', encoded_url, 0


def process_server(server, cumulative_bytes):
    """Download new images for a server.

    Returns (new_cumulative_bytes, hit_limit).
    When limit is reached, remaining URLs are written back to the txt file.
    """
    server_id = server['id']
    server_name = server['name']
    hit_limit = False

    print(f'\n--- Processing: {server_name} ---')
    sys.stdout.flush()

    txt_path = os.path.join(REPO_DIR, 'Wallpapers', 'images_url',
                            f'{server_id}.txt')
    download_dir = os.path.join(REPO_DIR, 'branches', server_id, 'downloads')

    if not os.path.isfile(txt_path):
        print(f'  Skip: URL file not found.')
        return cumulative_bytes, False

    with open(txt_path, encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls:
        print(f'  No URLs to download.')
        return cumulative_bytes, False

    os.makedirs(download_dir, exist_ok=True)

    # Separate into tasks (need download) vs already-downloaded
    tasks = []
    for url in urls:
        raw_fn = os.path.basename(urllib.parse.urlparse(url).path.rstrip('/'))
        try:
            decoded_fn = urllib.parse.unquote(raw_fn)
        except Exception:
            decoded_fn = raw_fn
        filename = decoded_fn if decoded_fn else raw_fn
        dest = os.path.join(download_dir, filename)

        if os.path.isfile(dest):
            continue
        tasks.append((url, dest, filename))

    if not tasks:
        print(f'  All files already exist.')
        return cumulative_bytes, False

    downloaded = 0
    failed = 0
    failed_urls = []
    remaining_urls = []

    # Submit in small batches so we can stop when size limit is hit
    SUBMIT_BATCH = MAX_WORKERS * 2  # submit this many at a time
    task_idx = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        while task_idx < len(tasks) and not hit_limit:
            # Submit a batch of tasks
            futures = {}
            batch_end = min(task_idx + SUBMIT_BATCH, len(tasks))
            for i in range(task_idx, batch_end):
                url, dest, filename = tasks[i]
                future = executor.submit(download_file, url, dest)
                futures[future] = (url, dest, filename)
            task_idx = batch_end

            # Collect results
            for future in as_completed(futures):
                url, dest, filename = futures[future]
                success, fn, err, enc_url, fsize = future.result()
                if success:
                    downloaded += 1
                    cumulative_bytes += fsize
                    if downloaded % 10 == 0:
                        size_mb = cumulative_bytes / (1024 * 1024)
                        print(f'  [{server_name}] {downloaded} downloaded ({size_mb:.0f} MB cumulative)')
                        sys.stdout.flush()
                    if cumulative_bytes >= MAX_BATCH_BYTES:
                        hit_limit = True
                else:
                    failed += 1
                    failed_urls.append(url)
                    print(f'  [{server_name}] FAILED: {fn} -- {err}')
                    sys.stdout.flush()

        # Any tasks not yet submitted go to remaining
        if hit_limit and task_idx < len(tasks):
            for i in range(task_idx, len(tasks)):
                remaining_urls.append(tasks[i][0])  # url

    if hit_limit:
        print(f'  [!] Batch size limit reached ({MAX_BATCH_BYTES / (1024**3):.1f} GB)')

    print(f'  >> {server_name}: {downloaded} OK, {failed} failed, {len(remaining_urls)} deferred')
    sys.stdout.flush()

    # Write failed URLs
    failed_dir = os.path.join(REPO_DIR, 'Wallpapers', 'failed')
    os.makedirs(failed_dir, exist_ok=True)
    failed_file = os.path.join(failed_dir, f'{server_id}.txt')
    if failed_urls:
        with open(failed_file, 'w', encoding='utf-8') as f:
            for url in failed_urls:
                f.write(url + '\n')
    elif os.path.isfile(failed_file):
        os.remove(failed_file)

    # Write remaining URLs back for next iteration
    if remaining_urls:
        with open(txt_path, 'w', encoding='utf-8') as f:
            for url in remaining_urls:
                f.write(url + '\n')
        print(f'  [{server_name}] {len(remaining_urls)} URLs saved for next batch')
    else:
        # All done for this server -- clear the URL file
        with open(txt_path, 'w', encoding='utf-8') as f:
            pass

    return cumulative_bytes, hit_limit


def main():
    config = load_config()
    print('=== PGR DOWNLOADER START ===')
    sys.stdout.flush()

    cumulative = 0
    hit_limit = False

    for server in config['servers']:
        cumulative, hit_limit = process_server(server, cumulative)
        if hit_limit:
            print(f'\n[!] Batch limit reached. Remaining servers deferred to next iteration.')
            break

    size_mb = cumulative / (1024 * 1024)
    print(f'\n=== DOWNLOAD BATCH COMPLETE ({size_mb:.0f} MB) ===')
    sys.stdout.flush()

    # Exit code 2 = more work remains (used by workflow loop)
    if hit_limit:
        sys.exit(2)


if __name__ == '__main__':
    main()
