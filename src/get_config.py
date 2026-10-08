#!/usr/bin/env python3
"""CLI access to config.jsonc — for shell scripts and workflow steps.

Usage:
    python3 src/get_config.py servers             # one region id per line
    python3 src/get_config.py protected-branches  # branch names not to delete
    python3 src/get_config.py <dotted.key>        # e.g. wallpapersBranch,
                                                  #      site.baseUrl, servers.0.id
Scalars print raw; lists of strings print space-joined (shell-friendly);
anything else prints as JSON.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import load_config


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ''
    config = load_config()

    if arg == 'servers':
        for s in config['servers']:
            print(s['id'])
        return

    if arg == 'protected-branches':
        branches = ['main',
                    config.get('wallpapersBranch', 'wallpapers'),
                    config.get('previewBranch', 'preview')]
        branches += config.get('categoryBranches', ['desktop', 'mobile'])
        for b in branches:
            print(b)
        return

    if not arg:
        print('usage: get_config.py servers | protected-branches | <dotted.key>',
              file=sys.stderr)
        sys.exit(2)

    cur = config
    for part in arg.split('.'):
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur[part]

    if isinstance(cur, str):
        print(cur)
    elif isinstance(cur, list) and all(isinstance(x, str) for x in cur):
        print(' '.join(cur))
    else:
        print(json.dumps(cur, ensure_ascii=False))


if __name__ == '__main__':
    main()
