import os
import sys
import json
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
    preview_branch = config.get('previewBranch', 'preview')
    servers = config.get('servers', [])

    # Format timestamp
    # Assumes tag format wallpapers-YYYYMMDD-HHMMSS
    try:
        ts_str = release_tag.replace('wallpapers-', '')
        dt = datetime.strptime(ts_str, "%Y%m%d-%H%M%S")
        pretty_time = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        pretty_time = release_tag

    body = f"📅 **Release Time:** {pretty_time}\n\n"
    has_files = False
    
    # Create staging dir for python zipping later (handled by caller, but we check files here)
    
    for server in servers:
        sid = server['id']
        sname = server['name']
        txt_file = f"Wallpapers/images_url/{sid}.txt"
        
        if not os.path.exists(txt_file) or os.path.getsize(txt_file) == 0:
            continue

        file_count = 0
        file_list_md = ""
        
        # Determine actual downloaded files
        with open(txt_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
            
        for url in urls:
            decoded = decode_filename(url)
            # Check if file exists in the downloaded folder
            local_path_decoded = f"branches/{sid}/images/{decoded}"
            
            # Simple check if file exists locally (it should after download step)
            if os.path.exists(local_path_decoded):
                file_count += 1
                encoded_fn = urllib.parse.quote(decoded, safe="%/~@!$&'()*+,;=")
                thumb_url = f"https://raw.githubusercontent.com/{repo}/{preview_branch}/{sid}/thumbnails/{encoded_fn}"
                dl_url = f"https://github.com/{repo}/raw/{wallpapers_branch}/{encoded_fn}"
                
                file_list_md += f"| <img src=\"{thumb_url}\" width=\"100\"> | `{decoded}` | [Download]({dl_url}) | ✅ |\n"

        if file_count > 0:
            has_files = True
            body += f"<details><summary>📋 File list & preview {sname} ({file_count} new)</summary>\n\n"
            body += "| Preview | Filename | Download | Status |\n"
            body += "|---------|----------|----------|--------|\n"
            body += file_list_md
            body += "\n</details>\n\n---\n\n"

    # Output for GitHub Actions
    with open('release_notes.md', 'w', encoding='utf-8') as f:
        f.write(body)
    
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f"has_files={'true' if has_files else 'false'}\n")

if __name__ == "__main__":
    main()
