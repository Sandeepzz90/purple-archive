"""Cache more member and group photographs, once per source image."""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
import hashlib
from urllib.parse import unquote
from seed import requests
from server import DOWNLOAD, database, add_media


class Photos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        source = data.get('src', '')
        if tag == 'img' and ('wikimedia.org' in source) and ('.jpg' in source.lower() or '.jpeg' in source.lower()):
            if int(data.get('width', '0') or 0) >= 170:
                self.images.append(('https:' if source.startswith('//') else '') + source)


def populate(entry):
    member, page, label = entry
    try:
        response = requests.get('https://en.wikipedia.org/wiki/' + page, timeout=40)
        response.raise_for_status()
        parser = Photos()
        parser.feed(response.text)
        count = 0
        used = set()
        for source in parser.images[1:]:
            parts = source.split('?')[0].split('/')
            filename = parts[-2] if '/thumb/' in source else parts[-1]
            if filename in used:
                continue
            used.add(filename)
            identity = 'extra-' + hashlib.sha256(filename.encode()).hexdigest()[:18]
            with database() as db:
                if db.execute('SELECT 1 FROM media WHERE id=?', (identity,)).fetchone():
                    count += 1
                    if count >= (4 if member == 'all' else 2):
                        break
                    continue
            try:
                image = requests.get(source, timeout=45)
                image.raise_for_status()
                target = DOWNLOAD / (identity + '.jpg')
                target.write_bytes(image.content)
                add_media(target, identity, label + [' · little moments', ' · in the spotlight', ' · a day to remember', ' · together, always'][count % 4], member, 'wikimedia', 'https://commons.wikimedia.org/wiki/File:' + unquote(filename))
                count += 1
            except Exception:
                continue
            if count >= (4 if member == 'all' else 2):
                break
        return f'{member}: {count} additional photos cached'
    except Exception as error:
        return f'{member}: {type(error).__name__}'


if __name__ == '__main__':
    entries = [('all','BTS','BTS 방탄소년단'), ('rm','RM_(musician)','RM 남준'), ('jin','Jin_(singer)','Jin 석진'), ('suga','Suga','SUGA 윤기'), ('jhope','J-Hope','j-hope 호석'), ('jimin','Jimin','Jimin 지민'), ('v','V_(singer)','V 태형'), ('jungkook','Jungkook','Jung Kook 정국')]
    with ThreadPoolExecutor(max_workers=3) as executor:
        for result in executor.map(populate, entries):
            print(result, flush=True)
