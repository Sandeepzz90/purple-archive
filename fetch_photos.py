"""Fetch candidate photos from Wikimedia for owner approval.

/fetch member [count] — searches Wikipedia member pages for large images,
sends them to the owner with Approve buttons. Approved photos enter the
site library like normal uploads (pending source, hidden until approved
is NOT used — approval itself adds them).
"""
import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

import requests as _requests

requests = _requests.Session()
requests.headers['User-Agent'] = 'PurpleArchive/1.0 (personal fan gallery; Wikimedia photo curation)'

PAGES = {
    'all': 'BTS', 'rm': 'RM_(musician)', 'jin': 'Jin_(singer)', 'suga': 'Suga',
    'jhope': 'J-Hope', 'jimin': 'Jimin', 'v': 'V_(singer)', 'jungkook': 'Jungkook',
}


class Photos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        source = data.get('src', '') or data.get('data-src', '')
        if tag == 'img' and 'wikimedia.org' in source and '.jpg' in source.lower() or '.jpeg' in source.lower():
            if 'wikimedia.org' in source and int(data.get('width', '0') or 0) >= 220:
                self.images.append(('https:' if source.startswith('//') else '') + source)


def search(member, count=4):
    """Return up to `count` candidate dicts: id, url, member, credit."""
    page = PAGES.get(member)
    if not page:
        return []
    try:
        response = requests.get('https://en.wikipedia.org/wiki/' + page, timeout=40)
        response.raise_for_status()
        parser = Photos()
        parser.feed(response.text)
        out, used = [], set()
        for source in parser.images:
            parts = source.split('?')[0].split('/')
            filename = parts[-2] if '/thumb/' in source else parts[-1]
            if filename in used:
                continue
            used.add(filename)
            # thumb URLs can 400; use the ORIGINAL full-resolution file instead
            # .../thumb/a/ab/File.jpg/640px-File.jpg -> .../a/ab/File.jpg
            big = re.sub(r'/thumb/(\w/\w\w)/([^/]+)/\d+px-.*$', r'/\1/\2', source.split('?')[0])
            if 'thumb.wikimedia.org' in big:
                big = big.replace('thumb.wikimedia.org', 'upload.wikimedia.org')
            identity = 'cand-' + hashlib.sha256(filename.encode()).hexdigest()[:18]
            out.append({
                'id': identity,
                'url': big,
                'member': member,
                'filename': filename,
                'credit': 'https://commons.wikimedia.org/wiki/File:' + unquote(filename),
            })
            if len(out) >= count:
                break
        return out
    except Exception:
        return []
