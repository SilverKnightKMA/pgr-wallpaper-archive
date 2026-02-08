#!/usr/bin/env python3
"""Generate README files for main branch and per-server pages.

Usage:
    python3 src/generate_readme.py main
    python3 src/generate_readme.py server <server_id>

Thumbnails use raw.githubusercontent.com URLs from the preview branch.
Server READMEs are output to the preview branch directory.

Environment variables:
    MANIFEST_PATH         - path to manifest.json (default: data/manifest.json)
    README_OUTPUT         - output path for main README (default: README.md)
    BRANCH_README_OUTPUT  - output path for server README
    PREVIEW_DIR           - preview branch checkout dir
    FAILED_DIR            - directory containing per-category failed URL files
    GITHUB_REPOSITORY     - repo slug (default: SilverKnightKMA/pgr-wallpaper-archive)
"""

import json
import os
import sys
import re
import urllib.parse
import html

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(SCRIPT_DIR, '..')
CONFIG_PATH = os.path.join(REPO_DIR, 'config.json')

CATEGORIES = ['desktop', 'mobile']


def load_config():
    with open(CONFIG_PATH, encoding='utf-8') as f:
        return json.load(f)


def escape_html(s):
    return html.escape(s, quote=True)


def encode_filename(filename):
    """Encode filename for use in URLs, preserving existing %XX sequences."""
    encoded = re.sub(
        r"[^A-Za-z0-9._~:@!$&'()*+,;=%/-]",
        lambda m: urllib.parse.quote(m.group(0)),
        filename
    )
    encoded = re.sub(r'%(?![0-9A-Fa-f]{2})', '%25', encoded)
    return encoded


def preview_filename(filename):
    """Get the preview filename (always .jpg extension)."""
    base, ext = os.path.splitext(filename)
    return base + '.jpg'


def is_valid_url(url):
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme in ('http', 'https')
    except Exception:
        return False


def load_manifest():
    manifest_path = os.environ.get('MANIFEST_PATH',
                                    os.path.join(REPO_DIR, 'data', 'manifest.json'))
    if os.path.isfile(manifest_path):
        with open(manifest_path, encoding='utf-8') as f:
            return json.load(f)
    return {}


def generate_main_readme(config):
    manifest = load_manifest()
    repo_slug = os.environ.get('GITHUB_REPOSITORY', 'SilverKnightKMA/pgr-wallpaper-archive')
    wallpapers_branch = config.get('wallpapersBranch', 'wallpapers')
    preview_branch = config.get('previewBranch', 'preview')
    owner = repo_slug.split('/')[0]
    repo_name = repo_slug.split('/')[1]
    pages_url = f'https://{owner}.github.io/{repo_name}/'

    lines = []
    lines.append('# PGR Wallpaper Archive\n')
    lines.append('Automated repository to archive high-quality wallpapers from Punishing: Gray Raven.\n')
    lines.append(f'[Browse & Filter Wallpapers on Web]({pages_url})\n')
    lines.append('## Server Galleries\n')
    lines.append(f'All wallpapers are stored in the [`{wallpapers_branch}`](https://github.com/{repo_slug}/tree/{wallpapers_branch}) branch.\n')
    lines.append(f'Previews and server pages are in the [`{preview_branch}`](https://github.com/{repo_slug}/tree/{preview_branch}) branch.\n')
    lines.append('| Server | Total | Success | Failed | Last Updated |')
    lines.append('|--------|-------|---------|--------|--------------|')

    for server in config['servers']:
        server_url = f'https://github.com/{repo_slug}/tree/{preview_branch}/{server["id"]}'
        sd = manifest.get(server['id'], {})
        total = sd.get('total', 0)
        success = sd.get('success', 0)
        failed = sd.get('failed', 0)
        last_updated = sd.get('lastUpdated', 'N/A')
        lines.append(f'| [{server["name"]}]({server_url}) | {total} | {success} | {failed} | {last_updated} |')

    lines.append('\n---\n')
    lines.append('## Wallpaper Preview\n')

    for server in config['servers']:
        sd = manifest.get(server['id'], {})
        wallpapers = sd.get('wallpapers', [])
        lines.append(f'### {server["name"]}\n')

        if wallpapers:
            # Sort by startTime (descending) for most recent first
            recent = sorted(wallpapers, key=lambda w: w.get('startTime', 0), reverse=True)[:15]
            lines.append('<table>')
            for i in range(0, len(recent), 5):
                lines.append('  <tr>')
                chunk = recent[i:i+5]
                for w in chunk:
                    fn = w.get('filename', 'unknown')
                    cat = w.get('category', 'desktop')
                    prev_fn = preview_filename(fn)
                    enc_prev_fn = encode_filename(prev_fn)
                    enc_fn = encode_filename(fn)
                    safe_fn = escape_html(fn)
                    # Thumbnail from preview branch
                    thumb = f'https://raw.githubusercontent.com/{repo_slug}/{preview_branch}/{enc_prev_fn}'
                    # Full image from wallpapers branch
                    raw = f'https://github.com/{repo_slug}/raw/{wallpapers_branch}/{cat}/{enc_fn}'
                    lines.append(f'    <td width="20%" align="center" valign="middle">')
                    lines.append(f'      <a href="{raw}">')
                    lines.append(f'        <img src="{thumb}" width="100%" alt="{safe_fn}" title="{safe_fn}">')
                    lines.append(f'      </a>')
                    lines.append(f'    </td>')
                lines.append('  </tr>')
            lines.append('</table>\n')
        else:
            lines.append('_No wallpapers yet._\n')

    lines.append('---\n')
    lines.append('## Releases\n')
    lines.append(f'All wallpapers are also available as downloads in [Releases](https://github.com/{repo_slug}/releases).\n')

    content = '\n'.join(lines)
    output_path = os.environ.get('README_OUTPUT', os.path.join(REPO_DIR, 'README.md'))
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Main README.md updated!')


def generate_server_readme(config, server):
    manifest = load_manifest()
    repo_slug = os.environ.get('GITHUB_REPOSITORY', 'SilverKnightKMA/pgr-wallpaper-archive')
    wallpapers_branch = config.get('wallpapersBranch', 'wallpapers')
    preview_branch = config.get('previewBranch', 'preview')
    owner = repo_slug.split('/')[0]
    repo_name = repo_slug.split('/')[1]

    sd = manifest.get(server['id'], {})
    wallpapers = sd.get('wallpapers', [])
    total = sd.get('total', len(wallpapers))

    # Read failed URLs
    failed_dir = os.environ.get('FAILED_DIR',
                                  os.path.join(REPO_DIR, 'Wallpapers', 'failed'))
    failed_urls = []
    failed_file = os.path.join(failed_dir, f'{server["id"]}.txt')
    if os.path.isfile(failed_file):
        with open(failed_file, encoding='utf-8') as f:
            failed_urls.extend([line.strip() for line in f if line.strip()])

    failed_filenames = set()
    for url in failed_urls:
        try:
            failed_filenames.add(urllib.parse.unquote(url.split('/')[-1]))
        except Exception:
            pass

    # Output to preview branch directory
    preview_dir = os.environ.get('PREVIEW_DIR', '')
    if preview_dir:
        output_dir = os.path.join(preview_dir, server['id'])
    else:
        output_dir = os.path.join(REPO_DIR, 'preview', server['id'])

    lines = []
    lines.append(f'# {server["name"]} — PGR Wallpaper Archive\n')
    lines.append(f'> Total: {total} wallpapers\n')
    lines.append(f'[Back to Main](https://github.com/{repo_slug})\n')

    pages_url = f'https://{owner}.github.io/{repo_name}/?server={server["id"]}'
    lines.append(f'[View & Filter on GitHub Pages]({pages_url})\n')
    lines.append('## Gallery\n')

    # Sort by startTime (descending) for consistent ordering
    sorted_wp = sorted(wallpapers, key=lambda w: w.get('startTime', 0), reverse=True)

    if not sorted_wp and not failed_urls:
        lines.append('_No wallpapers yet._\n')
    else:
        for w in sorted_wp:
            fn = w.get('filename', 'unknown')
            cat = w.get('category', 'desktop')
            prev_fn = preview_filename(fn)
            enc_fn = encode_filename(fn)
            enc_prev_fn = encode_filename(prev_fn)
            safe_fn = escape_html(fn)
            # Thumbnail from preview branch
            thumb_src = f'https://raw.githubusercontent.com/{repo_slug}/{preview_branch}/{enc_prev_fn}'
            # Full image from wallpapers branch
            dl = f'https://github.com/{repo_slug}/raw/{wallpapers_branch}/{cat}/{enc_fn}'
            status = 'Failed' if (w.get('status') == 'failed' or fn in failed_filenames) else 'Success'
            release_time = w.get('releaseTime', 'N/A')
            start_time = w.get('startTime_formatted', '')
            size = w.get('size', 'N/A')
            resolution = w.get('resolution', 'N/A')
            name_in = w.get('nameIn', '')
            source_url = w.get('imgUrl', '')
            source_link = f'<a href="{escape_html(source_url)}">Original</a>' if (source_url and is_valid_url(source_url)) else ''

            lines.append('<details>')
            lines.append('<summary>')
            lines.append(f'<img src="{thumb_src}" width="200" alt="{safe_fn}" title="{safe_fn}"> <strong>{safe_fn}</strong>')
            lines.append('</summary>\n')
            if name_in:
                lines.append(f'- **Name:** {name_in}')
            if start_time:
                lines.append(f'- **Published:** {start_time}')
            lines.append(f'- **Archived:** {release_time}')
            lines.append(f'- **Resolution:** {resolution}')
            lines.append(f'- **Size:** {size}')
            lines.append(f'- **Category:** {cat}')
            lines.append(f'- **Status:** {status}')
            lines.append(f'- **Download Raw:** [Download]({dl})')
            if source_link:
                lines.append(f'- **Original:** {source_link}')
            lines.append('\n</details>\n')

    if failed_urls:
        lines.append('\n## Broken Links\n')
        lines.append('The following URLs failed to download and will be retried on the next run:\n')
        lines.append('| # | URL | Status |')
        lines.append('|---|-----|--------|')
        for i, url in enumerate(failed_urls, 1):
            lines.append(f'| {i} | `{url}` | Failed |')
        lines.append('')

    content = '\n'.join(lines)
    output_path = os.environ.get('BRANCH_README_OUTPUT',
                                  os.path.join(output_dir, 'README.md'))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Server README for {server["name"]} updated at {output_path}!')


def main():
    config = load_config()
    mode = sys.argv[1] if len(sys.argv) > 1 else 'main'

    if mode == 'main':
        generate_main_readme(config)
    elif mode in ('branch', 'server'):
        if len(sys.argv) < 3:
            print('Server ID required for server mode', file=sys.stderr)
            sys.exit(1)
        server_id = sys.argv[2]
        server = next((s for s in config['servers'] if s['id'] == server_id), None)
        if not server:
            print(f'Server not found: {server_id}', file=sys.stderr)
            sys.exit(1)
        generate_server_readme(config, server)
    else:
        print(f'Unknown mode: {mode}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
