"""Single-source config access.

config.jsonc is the ONLY config file in this repo — hand-edited, with
// comments beside each line. Every consumer parses it through this
module (or the src/get_config.py CLI); nothing reads a stripped copy.

The stripper is an in-string-aware state machine, so `//` inside strings
(every https:// URL in the file) survives untouched.
"""

import json
import os

_CANDIDATES = [
    'config.jsonc',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 'config.jsonc'),
]


def _strip_jsonc(text):
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


def load_config(path=None):
    """Parse config.jsonc (cwd first, then repo root relative to this file)."""
    paths = [path] if path else _CANDIDATES
    for p in paths:
        if p and os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                return json.loads(_strip_jsonc(f.read()))
    raise FileNotFoundError('config.jsonc not found (looked in: %s)' % ', '.join(x for x in paths if x))
