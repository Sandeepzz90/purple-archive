"""Fetch candidate photos from across the internet (Creative Commons) for owner approval.

Sources: Openverse (aggregates Flickr, Wikimedia, museums, and dozens of
other CC-licensed collections) + Wikipedia media lists as fallback.
Results are shuffled so every /fetch call surfaces different photos.
"""
import hashlib
import random
import re
from html.parser import HTMLParser
from urllib.parse import unquote

import requests as _requests

requests = _requests.Session()
requests.headers['User-Agent'] = 'PurpleArchive/1.0 (personal fan gallery; CC photo curation)'

PAGES = {
    'all': ('BTS', 'BTS group photo'),
    'rm': ('RM_(musician)', 'RM BTS'),
    'jin': ('Jin_(singer)', 'Jin BTS'),
    'suga': ('Suga', 'Suga BTS Agust D'),
    'jhope': ('J-Hope', 'J-Hope BTS'),
    'jimin': ('Jimin', 'Jimin BTS'),
    'v': ('V_(singer)', 'V Kim Taehyung BTS'),
    'jungkook': ('Jungkook', 'Jungkook BTS'),
}

QUERIES = [
    '{name}', '{name} photoshoot', '{name} concert',
    '{name} 2023', '{name} airport fashion', '{name} behind the scenes',
    '{name} portrait', '{name} stage',
]


class Photos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        source = data.get('src', '') or data.get('data-src', '')
        if tag == 'img' and 'wikimedia.org' in source and ('.jpg' in source.lower() or '.jpeg' in source.lower()):
            if int(data.get('width', '0') or 0) >= 220:
                self.images.append(('https:' if source.startswith('//') else '') + source)


def _openverse(query, count):
    """Search Openverse's aggregated CC-image index (whole-internet CC photos)."""
    out = []
    try:
        page = random.randint(1, 3)
        r = requests.get('https://api.openverse.org/v1/images/',
                         params={'q': query, 'page_size': 20, 'page': page, 'license_type': 'all-cc'},
                         timeout=30)
        if not r.ok:
            return out
        for item in r.json().get('results', []):
            url = item.get('url') or ''
            ext = url.split('?')[0].lower().rsplit('.', 1)[-1]
            if ext not in ('jpg', 'jpeg', 'png', 'webp'):
                continue
            width = item.get('width') or 0
            if width and width < 600:
                continue
            identity = 'cand-' + hashlib.sha256(url.encode()).hexdigest()[:18]
            out.append({
                'id': identity, 'url': url, 'member': '', 'filename': (item.get('title') or 'photo')[:60],
                'credit': item.get('foreign_landing_url') or '',
            })
    except Exception:
        pass
    return out


def _wikipedia(page, count):
    """Wikipedia page images as a fallback source."""
    out = []
    try:
        r = requests.get('https://en.wikipedia.org/wiki/' + page, timeout=40)
        r.raise_for_status()
        parser = Photos()
        parser.feed(r.text)
        used = set()
        for source in parser.images:
            parts = source.split('?')[0].split('/')
            filename = parts[-2] if '/thumb/' in source else parts[-1]
            if filename in used:
                continue
            used.add(filename)
            big = re.sub(r'/thumb/(\w/\w\w)/([^/]+)/\d+px-.*$', r'/\1/\2', source.split('?')[0])
            if 'thumb.wikimedia.org' in big:
                big = big.replace('thumb.wikimedia.org', 'upload.wikimedia.org')
            identity = 'cand-' + hashlib.sha256(filename.encode()).hexdigest()[:18]
            out.append({
                'id': identity, 'url': big, 'member': '', 'filename': filename[:60],
                'credit': 'https://commons.wikimedia.org/wiki/File:' + unquote(filename),
            })
            if len(out) >= count * 3:
                break
    except Exception:
        pass
    return out


def search(member, count=4):
    """Return up to `count` shuffled candidates from across the internet."""
    page, name = PAGES.get(member, ('BTS', member))
    candidates = []
    queries = [q.format(name=name) for q in QUERIES]
    random.shuffle(queries)
    for q in queries[:3]:
        candidates.extend(_openverse(q, count))
        if len(candidates) >= count * 4:
            break
    if len(candidates) < count * 2:
        candidates.extend(_wikipedia(page, count))
    seen, unique = set(), []
    for c in candidates:
        if c['url'] not in seen:
            seen.add(c['url'])
            c['member'] = member
            unique.append(c)
    random.shuffle(unique)
    return unique[:count]
