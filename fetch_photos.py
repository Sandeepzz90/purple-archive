"""Fetch candidate photos from the Asiachan KPOP image board ONLY.

kpop.asiachan.com — 34,000+ BTS images. Used by /fetch (owner approval),
the hourly auto-curator shares the same tags via auto_curate.py.
"""
import hashlib
import random
import re

import requests as _requests

requests = _requests.Session()
requests.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Referer': 'https://kpop.asiachan.com/',
})

ASIACHAN_TAGS = {
    'all': 'BTS', 'rm': 'Namjoon', 'jin': 'Jin', 'suga': 'SUGA',
    'jhope': 'Jhope', 'jimin': 'Jimin', 'v': 'V', 'jungkook': 'Jungkook',
}


def _scrape(tag, count, page_range=40, max_pages=4):
    """Scrape up to `count` full-resolution photo URLs from a tag board."""
    out, seen = [], set()
    try:
        pages = random.sample(range(1, page_range), k=min(max_pages, 4))
        for page in pages:
            if len(out) >= count:
                break
            r = requests.get(f'https://kpop.asiachan.com/{tag}?p={page}', timeout=30)
            if not r.ok:
                continue
            ids = set(re.findall(r'static\.asiachan\.com/[^"\s]+?\.full\.(\d+)\.jpg', r.text))
            ids -= seen
            for image_id in ids:
                if len(out) >= count:
                    break
                seen.add(image_id)
                url = f'https://static.asiachan.com/{tag}.full.{image_id}.jpg'
                identity = 'asian-' + hashlib.sha256(url.encode()).hexdigest()[:18]
                out.append({
                    'id': identity, 'url': url, 'member': '',
                    'filename': f'asiachan #{image_id}', 'credit': 'https://kpop.asiachan.com/',
                })
    except Exception:
        pass
    return out


def search(member, count=4):
    """Return up to `count` shuffled Asiachan candidates for a member."""
    tag = ASIACHAN_TAGS.get(member)
    if not tag:
        return []
    candidates = _scrape(tag, count)
    for c in candidates:
        c['member'] = member
    random.shuffle(candidates)
    return candidates[:count]
