"""Hourly auto-curator: fetch photos from Asiachan KPOP only, learn faces, publish to profiles.

Every cycle:
- picks a random member (or 'all' for group shots)
- scrapes ~20 candidate full-resolution photos from kpop.asiachan.com
- adds them to the site library under that member
- single-clear-face photos also become local OpenCV references (auto /learn)
"""
import random
import re
import hashlib

import requests

requests = requests.Session()
requests.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Referer': 'https://kpop.asiachan.com/',
})

ASIACHAN_TAGS = {
    'all': 'BTS', 'rm': 'Namjoon', 'jin': 'Jin', 'suga': 'SUGA',
    'jhope': 'Jhope', 'jimin': 'Jimin', 'v': 'V', 'jungkook': 'Jungkook',
}


def fetch_batch(member, count=20):
    """Scrape up to `count` full photos for a member from Asiachan."""
    tag = ASIACHAN_TAGS.get(member)
    if not tag:
        return []
    out = []
    try:
        pages = random.sample(range(1, 40), k=min(4, count // 6 + 1))
        seen = set()
        for page in pages:
            if len(out) >= count:
                break
            r = requests.get(f'https://kpop.asiachan.com/{tag}?p={page}', timeout=30)
            if not r.ok:
                continue
            ids = set(re.findall(r'static\.asiachan\.com/[^"\s]+?\.full\.(\d+)\.jpg', r.text))
            for image_id in ids:
                if len(out) >= count:
                    break
                url = f'https://static.asiachan.com/{tag}.full.{image_id}.jpg'
                if image_id in seen:
                    continue
                seen.add(image_id)
                identity = 'asian-' + hashlib.sha256(url.encode()).hexdigest()[:18]
                out.append({'id': identity, 'url': url, 'member': member, 'filename': f'asiachan #{image_id}'})
    except Exception:
        pass
    return out


def random_member():
    """Random individual member — never the group (profiles stay solo)."""
    return random.choice(['rm', 'jin', 'suga', 'jhope', 'jimin', 'v', 'jungkook'])
