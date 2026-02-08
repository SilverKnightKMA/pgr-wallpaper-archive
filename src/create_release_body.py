import os
import sys
import json
import re
import urllib.parse
from datetime import datetime

# Environment variables
repo = os.environ.get('GITHUB_REPOSITORY')
config_path = 'config.json'
release_tag = os.environ.get('RELEASE_TAG', '')

def load_config():
    with open(config_path, 'r') as f:
        return json.load(f)

def decode_filename(url):
    filename = os.path.basename(url)
    return urllib.parse.unquote(filename)


def main():
    config = load_config()
    wallpapers_branch = config.get('wallpapersBranch', 'wallpapers')
    servers = config.get('servers', [])
    release_config = config.get('release', {})
    fields = release_config.get('fields', ["filename", "category", "size", "status"])

    # Format timestamp
    try:
        ts_str = release_tag.replace('wallpapers-', '')
        dt = datetime.strptime(ts_str, "%Y%m%d-%H%M%S")
        pretty_time = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        pretty_time = release_tag

    body = f"📅 **Release Time:** {pretty_time}\n\n"
    has_files = False

    for server in servers:
        sid = server['id']
        sname = server['name']

        file_count = 0
        file_list_md = ""

        for cat in ['desktop', 'mobile']:
            txt_file = f"new_images/{sid}_{cat}.txt"

            if not os.path.exists(txt_file) or os.path.getsize(txt_file) == 0:
                continue

            with open(txt_file, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]

            for url in urls:
                decoded = decode_filename(url)
                local_path_decoded = f"branches/{sid}/images/{cat}/{decoded}"

                if os.path.exists(local_path_decoded):
                    file_count += 1
                    encoded_fn = urllib.parse.quote(decoded, safe="/~@!$&'()*+,;=")
                    encoded_fn = re.sub(r'%(?![0-9A-Fa-f]{2})', '%25', encoded_fn)
                    dl_url = f"https://github.com/{repo}/raw/{wallpapers_branch}/{cat}/{encoded_fn}"
                    thumb_url = f"https://raw.githubusercontent.com/{repo}/{wallpapers_branch}/{cat}/{encoded_fn}"
                    cat_label = '🖥️' if cat == 'desktop' else '📱'

                    row = {"filename": decoded, "category": cat_label, "size": "N/A", "status": "✅", "url": dl_url}
                    file_list_md += "| " + " | ".join(str(row.get(field, '')) for field in fields) + " |\n"

        if file_count > 0:
            has_files = True
            body += f"<details><summary>📋 File list & preview {sname} ({file_count} new)</summary>\n\n"
            body += "| " + " | ".join(fields) + " |\n"
            body += "| " + " | ".join(["-" * len(field) for field in fields]) + " |\n"
            body += file_list_md
            body += "\n</details>\n\n---\n\n"

    with open('release_notes.md', 'w', encoding='utf-8') as f:
        f.write(body)

    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f"has_files={'true' if has_files else 'false'}\n")

if __name__ == "__main__":
    main()
