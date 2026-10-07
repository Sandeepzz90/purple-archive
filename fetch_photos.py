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

# Asiachan KPOP image board tags (high-quality fan photos)
ASIACHAN_TAGS = {
    'all': 'BTS', 'rm': 'Namjoon', 'jin': 'Jin', 'suga': 'SUGA',
    'jhope': 'Jhope', 'jimin': 'Jimin', 'v': 'V', 'jungkook': 'Jungkook',
}

ASIACHAN_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Referer': 'https://kpop.asiachan.com/',
}


def _asiachan(member, count):
    """Scrape Asiachan KPOP board — high-quality fan photos."""
    out = []
    tag = ASIACHAN_TAGS.get(member)
    if not tag:
        return out
    try:
        page = random.randint(1, 25)
        r = requests.get(f'https://kpop.asiachan.com/{tag}?p={page}', headers=ASIACHAN_HEADERS, timeout=30)
        if not r.ok:
            return out
        ids = sorted(set(re.findall(r'static\.asiachan\.com/[^"\s]+?\.full\.(\d+)\.jpg', r.text)))
        random.shuffle(ids)
        for image_id in ids[:count * 2]:
            url = f'https://static.asiachan.com/{tag}.full.{image_id}.jpg'
            identity = 'asian-' + hashlib.sha256(url.encode()).hexdigest()[:18]
            out.append({
                'id': identity, 'url': url, 'member': '',
                'filename': f'asiachan #{image_id}', 'credit': 'https://kpop.asiachan.com/',
            })
    except Exception:
        pass
    return out

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
    """Return up to `count` shuffled candidates — Asiachan first (HQ fan photos),
    then Openverse (internet CC), Wikipedia fallback."""
    page, name = PAGES.get(member, ('BTS', member))
    candidates = _asiachan(member, count)
    queries = [q.format(name=name) for q in QUERIES]
    random.shuffle(queries)
    for q in queries[:2]:
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
