#!/usr/bin/env python
"""Nightly backup: dump gallery.sqlite to GitHub as a dated release asset."""
import json
import os
import sqlite3
import sys
import tempfile
import time
import urllib.request

REPO = 'Sandeepzz90/purple-archive'
TOKEN = os.getenv('GITHUB_TOKEN', '')
DB = sys.argv[1] if len(sys.argv) > 1 else 'data/gallery.sqlite'


def api(url, data=None, method='GET', headers=None, raw=False):
    req = urllib.request.Request(url, method=method)
    req.add_header('Authorization', f'token {TOKEN}')
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    body = None
    if data is not None:
        body = data if raw else json.dumps(data).encode()
        req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, body) as r:
        payload = r.read()
        return json.loads(payload) if not raw else payload


def main():
    if not TOKEN:
        print('GITHUB_TOKEN not set; skip')
        return
    # consistent snapshot via sqlite backup API
    src = sqlite3.connect(DB)
    tmp = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
    dst = sqlite3.connect(tmp.name)
    src.backup(dst)
    dst.close(); src.close()
    blob = open(tmp.name, 'rb').read()
    tag = 'db-backup-' + time.strftime('%Y-%m-%d')
    name = f'gallery-{time.strftime("%Y-%m-%d")}.sqlite'
    try:
        api(f'https://api.github.com/repos/{REPO}/releases', {'tag_name': tag, 'name': 'DB backup ' + tag})
    except Exception as e:
        print('release create:', e)
    rel = json.loads(api(f'https://api.github.com/repos/{REPO}/releases/tags/{tag}').decode() if isinstance(api(f'https://api.github.com/repos/{REPO}/releases/tags/{tag}'), bytes) else 'null') if False else api(f'https://api.github.com/repos/{REPO}/releases/tags/{tag}')
    url = f'https://uploads.github.com/repos/{REPO}/releases/{rel["id"]}/assets?name={name}'
    req = urllib.request.Request(url, method='POST', data=blob)
    req.add_header('Authorization', f'token {TOKEN}')
    req.add_header('Content-Type', 'application/octet-stream')
    with urllib.request.urlopen(req) as r:
        print('uploaded:', json.loads(r.read())['browser_download_url'])


if __name__ == '__main__':
    main()
