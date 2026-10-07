"""Download public Wikimedia photos once, with source attribution."""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import unquote
import requests
from server import ROOT, DOWNLOAD, database, add_media
requests = requests.Session()
requests.headers['User-Agent'] = 'PurpleArchive/1.0 (personal local BTS fan gallery; Wikimedia photo caching)'

class Meta(HTMLParser):
    image = None
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('property') == 'og:image':
            self.image = attrs.get('content')

def download(entry):
    key, page, name = entry
    with database() as db:
        if db.execute('SELECT 1 FROM media WHERE id=?', ('seed-' + key,)).fetchone():
            return key + ': already cached'
    try:
        url = 'https://en.wikipedia.org/wiki/' + page
        response = requests.get(url, timeout=35)
        response.raise_for_status()
        parser = Meta()
        parser.feed(response.text)
        if not parser.image:
            return key + ': no image found'
        response = requests.get(parser.image, timeout=60)
        response.raise_for_status()
        target = DOWNLOAD / ('seed-' + key + '.jpg')
        target.write_bytes(response.content)
        parts = parser.image.split('?')[0].split('/')
        filename = parts[-2] if '/thumb/' in parser.image else parts[-1]
        credit = 'https://commons.wikimedia.org/wiki/File:' + unquote(filename)
        add_media(target, 'seed-' + key, name, key, 'wikimedia', credit)
        return key + ': downloaded'
    except Exception as error:
        return key + ': ' + type(error).__name__ + ' ' + str(error)

if __name__ == '__main__':
    entries = [('all','BTS','Seven artists. One beautiful story.'), ('rm','RM_(musician)','RM · The thoughtful leader'), ('jin','Jin_(singer)','Jin · A voice like silver'), ('suga','Suga','SUGA · Stories in every beat'), ('jhope','J-Hope','j-hope · A little sunshine'), ('jimin','Jimin','Jimin · Poetry in motion'), ('v','V_(singer)','V · An old soul'), ('jungkook','Jungkook','Jung Kook · The golden maknae')]
    with ThreadPoolExecutor(max_workers=3) as executor:
        for result in executor.map(download, entries):
            print(result, flush=True)
    response = requests.get('https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.12.2/lottie.min.js', timeout=40)
    response.raise_for_status()
    (ROOT / 'lottie.min.js').write_bytes(response.content)
