#!/usr/bin/env python3
"""Generate config.json (pure JSON — what every script reads) from
config.jsonc (the human-edited source with // comments beside each line).

Usage:
    python3 src/build_config.py          # regenerate config.json
    python3 src/build_config.py --check  # exit 1 + diff if out of sync

The stripper is a small state machine so `//` inside strings (every
https:// URL in this file) survives untouched.

Edit config.jsonc, never config.json. The nightly batch runs --check
and goes red if the two drift apart.
"""

import difflib
import json
import sys

SRC = 'config.jsonc'
OUT = 'config.json'


def strip_jsonc(text: str) -> str:
    out = []
    i = 0
    n = len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == '\\' and i + 1 < n:  # escaped char inside string
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '/':  # line comment
            while i < n and text[i] != '\n':
                i += 1
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '*':  # block comment
            i += 2
            while i + 1 < n and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def rendered() -> str:
    with open(SRC, encoding='utf-8') as f:
        data = json.loads(strip_jsonc(f.read()))
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


if '--check' in sys.argv:
    expected = rendered()
    with open(OUT, encoding='utf-8') as f:
        current = f.read()
    if current != expected:
        print('config.json is OUT OF SYNC with config.jsonc. '
              'Run: python3 src/build_config.py')
        sys.stdout.writelines(difflib.unified_diff(
            current.splitlines(True), expected.splitlines(True),
            'config.json (committed)', 'config.json (expected)'))
        sys.exit(1)
    print('config.json in sync with config.jsonc')
    sys.exit(0)

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(rendered())
print(f'wrote {OUT} from {SRC}')
