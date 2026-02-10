#!/usr/bin/env python3
"""Generate release notes for new wallpapers.

Reads new_images/{server_id}_{category}.txt for each server,
looks up metadata from data/manifest.json, and writes release_notes.md.

Sets output: has_files=true/false
"""
import os
import sys
import json
import re
import urllib.parse
from datetime import datetime

repo = os.environ.get('GITHUB_REPOSITORY', '')
config_path = 'config.json'
release_tag = os.environ.get('RELEASE_TAG', '')

# GitHub release body limit is 125000 characters; leave some margin
MAX_BODY_CHARS = 120000
MAX_ROWS_PER_SERVER = 200


def load_config():
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_manifest():
    manifest_path = 'data/manifest.json'
    if os.path.isfile(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def decode_filename(url):
    filename = os.path.basename(url)
    return urllib.parse.unquote(filename)


def encode_filename(filename):
    encoded = re.sub(
        r"[^A-Za-z0-9._~:@!$&'()*+,;=%/-]",
        lambda m: urllib.parse.quote(m.group(0)),
        filename
    )
    encoded = re.sub(r'%(?![0-9A-Fa-f]{2})', '%25', encoded)
    return encoded


def escape_markdown(text):
    # Escape [, ], (, ) for Markdown links
    return text.replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)')


def format_size_bytes(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def main():
    config = load_config()
    manifest = load_manifest()
    wallpapers_branch = config.get('wallpapersBranch', 'wallpapers')
    preview_branch = config.get('previewBranch', 'preview')
    servers = config.get('servers', [])
    release_config = config.get('release', {})
    fields = release_config.get('fields', ["filename", "category", "resolution", "size", "status"])

    # Build manifest lookup: filename -> entry (across all servers)
    manifest_lookup = {}
    for sid, sdata in manifest.items():
        if not isinstance(sdata, dict) or 'wallpapers' not in sdata:
            continue
        for w in sdata['wallpapers']:
            fn = w.get('filename', '')
            if fn:
                manifest_lookup[fn] = w

    # Format timestamp
    try:
        ts_str = release_tag.replace('wallpapers-', '')
        dt = datetime.strptime(ts_str, "%Y%m%d-%H%M%S")
        pretty_time = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        pretty_time = release_tag

    body = f"**Release Time:** {pretty_time}\n\n"
    has_files = False
    total_new = 0
    total_size_bytes = 0

    for server in servers:
        sid = server['id']
        sname = server['name']

        file_count = 0
        file_list_md = ""

        for cat in ['desktop', 'mobile']:
            txt_file = f"new_images/{sid}_{cat}.txt"

            if not os.path.exists(txt_file) or os.path.getsize(txt_file) == 0:
                continue

            with open(txt_file, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip()]

            for url in urls:
                decoded = decode_filename(url)
                local_path = f"branches/{sid}/images/{cat}/{decoded}"

                if os.path.exists(local_path):
                    file_count += 1

                    # Look up metadata from manifest
                    meta = manifest_lookup.get(decoded, {})

                    # Get actual file size from disk
                    try:
                        fsize = os.path.getsize(local_path)
                        size_str = format_size_bytes(fsize)
                        total_size_bytes += fsize
                    except OSError:
                        size_str = meta.get('size', 'N/A')

                    resolution = meta.get('resolution', '')
                    if not resolution:
                        # Try to get resolution from file
                        try:
                            from PIL import Image
                            with Image.open(local_path) as img:
                                w, h = img.size
                                resolution = f'{w}x{h}'
                        except Exception:
                            resolution = 'N/A'

                    cat_label = 'Desktop' if cat == 'desktop' else 'Mobile'

                    # Build row data
                    row = {
                        "filename": decoded,
                        "category": cat_label,
                        "resolution": resolution or 'N/A',
                        "size": size_str,
                        "status": "OK",
                    }

                    # Preview thumbnail for the filename column
                    prev_fn = os.path.splitext(decoded)[0] + '.jpg'
                    enc_prev_fn = encode_filename(prev_fn)
                    preview_url = f'https://raw.githubusercontent.com/{repo}/{preview_branch}/previews/{enc_prev_fn}'

                    # Make filename a link to download
                    enc_fn = encode_filename(decoded)
                    dl_url = f'https://github.com/{repo}/raw/{wallpapers_branch}/{cat}/{enc_fn}'

                    # Override filename field to include thumbnail + link
                    row["filename"] = f'<img src="{preview_url}" height="40"> [{escape_markdown(decoded)}]({dl_url})'

                    file_list_md += "| " + " | ".join(str(row.get(field, '')) for field in fields) + " |\n"

        if file_count > 0:
            has_files = True
            total_new += file_count

            # Truncate table rows if too many to avoid hitting GitHub body limit
            rows = file_list_md.rstrip('\n').split('\n') if file_list_md.strip() else []
            truncated = len(rows) > MAX_ROWS_PER_SERVER
            if truncated:
                rows = rows[:MAX_ROWS_PER_SERVER]

            body += f"<details><summary>📁 {sname} ({file_count} new)</summary>\n\n"
            body += "| " + " | ".join(fields) + " |\n"
            body += "| " + " | ".join(["-" * max(len(field), 3) for field in fields]) + " |\n"
            body += '\n'.join(rows) + '\n'
            if truncated:
                body += f"\n> **Note:** Only showing first {MAX_ROWS_PER_SERVER} of {file_count} wallpapers. Download the ZIP for the full set.\n"
            body += "\n</details>\n\n---\n\n"

    # Summary at top
    if has_files:
        summary = f"**Total new wallpapers:** {total_new}"
        if total_size_bytes > 0:
            summary += f" | **Total size:** {format_size_bytes(total_size_bytes)}"
        summary += "\n\n"
        body = f"**Release Time:** {pretty_time}\n\n{summary}" + body.split('\n\n', 1)[1]

    # Final safety truncation if body is still too long
    if len(body) > MAX_BODY_CHARS:
        truncation_notice = f"\n\n---\n\n> **Note:** Release notes truncated ({len(body)} chars exceeded GitHub's 125000 char limit). Download the ZIP for the complete list.\n"
        body = body[:MAX_BODY_CHARS - len(truncation_notice)] + truncation_notice

    with open('release_notes.md', 'w', encoding='utf-8') as f:
        f.write(body)

    gh_output = os.environ.get('GITHUB_OUTPUT', '')
    if gh_output:
        with open(gh_output, 'a') as f:
            f.write(f"has_files={'true' if has_files else 'false'}\n")
    else:
        print(f"has_files={'true' if has_files else 'false'}")


if __name__ == "__main__":
    main()
