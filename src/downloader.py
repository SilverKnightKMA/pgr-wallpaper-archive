#!/usr/bin/env python3
"""Download wallpaper images from URL lists.

Reads per-server URL lists from Wallpapers/images_url/<server_id>.txt
and downloads them into branches/<server_id>/downloads/ (flat directory).

Supports a size limit (MAX_BATCH_BYTES env var, default 1.8GB).
When the limit is reached, downloading stops and remaining URLs are kept
in the txt files for the next iteration.

Stored filenames: each downloaded file keeps its URL basename unless that
name (or its stem — previews share the stem namespace) is already taken by
an archived image (any server) or by a file downloaded earlier in this run;
in that case "__<server_id>" (and a counter if needed) is appended, e.g.
"01.png" -> "01__cn.png". The mapping is written to
Wallpapers/downloaded/<server_id>.map ("<stored>\t<url>") for
build_manifest.py, which records it as sourceFilename vs filename.

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
import threading
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


def load_existing_stored_names():
    """Load all stored filenames (+ stems) from data/manifest.json.

    The manifest mirrors the wallpapers/preview branches 1:1, so these names
    form the global namespace a new file must not collide with (across all
    servers). Returns (names, stems).
    """
    names, stems = set(), set()
    manifest_path = os.path.join(REPO_DIR, 'data', 'manifest.json')
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return names, stems
        for _sid, sdata in data.items():
            if not isinstance(sdata, dict):
                continue
            for w in sdata.get('wallpapers', []):
                fn = w.get('filename')
                if fn:
                    names.add(fn)
                    stems.add(os.path.splitext(fn)[0])
    return names, stems


def pick_stored_name(base, server_id, taken_names, taken_stems):
    """Return a collision-free stored filename for a downloaded image.

    Keeps `base` when free; otherwise appends __<server_id> (+ counter) so a
    same-basename image never overwrites another file or another preview
    (previews are stem + '.jpg', so stems share one namespace). Callers must
    add the returned name/stem to the taken sets.
    """
    stem, ext = os.path.splitext(base)
    if base not in taken_names and stem not in taken_stems:
        return base
    cand = f'{stem}__{server_id}{ext}'
    n = 2
    while cand in taken_names or os.path.splitext(cand)[0] in taken_stems:
        cand = f'{stem}__{server_id}__{n}{ext}'
        n += 1
    return cand


MAX_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]


def download_file(url, dest, stop_event=None):
    """Download a single file. Returns (success, filename, error, encoded_url, size).

    If stop_event is set before or during download, aborts early and returns failure.
    """
    ctx = ssl.create_default_context()
    encoded_url = encode_url(url)
    basename = os.path.basename(dest)
    last_err = None

    # Check before starting
    if stop_event and stop_event.is_set():
        return False, basename, 'cancelled', encoded_url, 0

    for attempt in range(1, MAX_RETRIES + 1):
        # Check again before each retry
        if stop_event and stop_event.is_set():
            return False, basename, 'cancelled', encoded_url, 0

        last_err = None
        req = urllib.request.Request(encoded_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
                with open(dest, 'wb') as f:
                    while True:
                        if stop_event and stop_event.is_set():
                            # Abort mid-download
                            last_err = 'cancelled'
                            break
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                    if last_err == 'cancelled':
                        try:
                            os.remove(dest)
                        except OSError:
                            pass
                        return False, basename, 'cancelled', encoded_url, 0
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


def process_server(server, cumulative_bytes, global_names, global_stems):
    """Download new images for a server.

    global_names/global_stems are mutated: every stored name assigned here
    (whether downloaded now or already on disk from an interrupted run) is
    reserved for the rest of this process, preventing in-run collisions
    across servers.

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
        base = decoded_fn if decoded_fn else raw_fn
        stored = pick_stored_name(base, server_id, global_names, global_stems)
        global_names.add(stored)
        global_stems.add(os.path.splitext(stored)[0])
        dest = os.path.join(download_dir, stored)

        if os.path.isfile(dest):
            continue
        tasks.append((url, dest, stored))

    if not tasks:
        print(f'  All files already exist.')
        return cumulative_bytes, False

    downloaded = 0
    failed = 0
    failed_urls = []
    remaining_urls = []
    downloaded_urls = []
    downloaded_pairs = []  # (stored, url) for the .map file

    # Thread-safe cumulative size tracking
    lock = threading.Lock()
    stop_event = threading.Event()

    # Submit ALL tasks at once -- workers pick them up as they become free.
    # When the size limit is reached we signal stop_event so in-flight
    # downloads abort at the next chunk boundary and un-started futures
    # are effectively no-ops (they check stop_event immediately).
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for url, dest, filename in tasks:
            future = executor.submit(download_file, url, dest, stop_event)
            futures[future] = (url, dest, filename)

        for future in as_completed(futures):
            url, dest, filename = futures[future]
            success, fn, err, enc_url, fsize = future.result()

            if err == 'cancelled':
                # Was cancelled by stop_event -- defer to next batch
                remaining_urls.append(url)
                continue

            if success:
                with lock:
                    downloaded += 1
                    cumulative_bytes += fsize
                    downloaded_urls.append(url)
                    downloaded_pairs.append((filename, url))
                    current_count = downloaded
                    current_bytes = cumulative_bytes

                if current_count % 50 == 0:
                    size_mb = current_bytes / (1024 * 1024)
                    print(f'  [{server_name}] {current_count} downloaded ({size_mb:.0f} MB cumulative)')
                    sys.stdout.flush()

                if current_bytes >= MAX_BATCH_BYTES and not stop_event.is_set():
                    hit_limit = True
                    stop_event.set()  # signal all workers to stop
            else:
                with lock:
                    failed += 1
                    failed_urls.append(url)
                print(f'  [{server_name}] FAILED: {fn} -- {err}')
                sys.stdout.flush()

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

    # Write successfully downloaded URLs so build_manifest.py can discover them
    if downloaded_urls:
        dl_dir = os.path.join(REPO_DIR, 'Wallpapers', 'downloaded')
        os.makedirs(dl_dir, exist_ok=True)
        dl_path = os.path.join(dl_dir, f'{server_id}.txt')
        # Append to support multiple batches within same run
        with open(dl_path, 'a', encoding='utf-8') as f:
            for url in downloaded_urls:
                f.write(url + '\n')
        # Stored-name mapping (stored<TAB>url) — consumed by build_manifest.py
        # so manifest records the real stored filename + sourceFilename.
        map_path = os.path.join(dl_dir, f'{server_id}.map')
        with open(map_path, 'a', encoding='utf-8') as f:
            for stored, url in downloaded_pairs:
                f.write(f'{stored}\t{url}\n')

    return cumulative_bytes, hit_limit


def main():
    config = load_config()
    print('=== PGR DOWNLOADER START ===')
    sys.stdout.flush()

    global_names, global_stems = load_existing_stored_names()
    print(f'Loaded {len(global_names)} existing stored names from manifest')
    sys.stdout.flush()

    cumulative = 0
    hit_limit = False

    for server in config['servers']:
        cumulative, hit_limit = process_server(server, cumulative,
                                               global_names, global_stems)
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
