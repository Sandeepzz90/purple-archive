"""Cache Wikimedia travel photographs as delivered, with source records kept privately."""
from concurrent.futures import ThreadPoolExecutor
import json
from urllib.parse import urlsplit,unquote
from pathlib import Path
from seed import requests,Meta
import image_quality

ROOT=Path(__file__).resolve().parent
ENTRIES=[('seoul','Seoul','Seoul, a city of little possibilities','서울'),('palace','Gyeongbokgung','A royal afternoon at Gyeongbokgung','경복궁'),('hanok','Bukchon_Hanok_Village','A walk through Bukchon','북촌한옥마을'),('busan','Gwangan_Bridge','A little sea breeze in Busan','부산'),('jeju','Seongsan_Ilchulbong','A daydream on Jeju Island','제주도'),('india','India_Gate','Your little journey begins in India','인도')]


def download(entry):
    slug,page,title,korean=entry
    try:
        response=requests.get('https://en.wikipedia.org/wiki/'+page,timeout=40);response.raise_for_status()
        parser=Meta();parser.feed(response.text)
        if not parser.image:raise RuntimeError('No lead photo')
        parsed=urlsplit(parser.image)
        source_path=parsed.path.replace('/thumb/','/',1).rsplit('/',1)[0] if '/thumb/' in parsed.path else parsed.path
        source=parser.image
        image=requests.get(source,timeout=90);image.raise_for_status()
        filename='korea-'+slug+'.jpg';target=ROOT/'Download'/filename
        target.write_bytes(image.content)
        info=image_quality.inspect(target)
        if not info:raise RuntimeError('Photo could not be decoded')
        return {'id':slug,'filename':filename,'preview':info['display_filename'],'width':info['width'],'height':info['height'],'mime':info['mime'],'title':title,'korean':korean,'source':source,'credit':'https://commons.wikimedia.org/wiki/File:'+unquote(source_path.rsplit('/',1)[-1])}
    except Exception as error:
        print(slug+': '+type(error).__name__,flush=True)
        return None


if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=1) as pool:
        items=[item for item in pool.map(download,ENTRIES) if item]
    (ROOT/'data/korea_photos.json').write_text(json.dumps(items,indent=2))
    for item in items:print(item['id'],str(item['width'])+'×'+str(item['height']),flush=True)
    if len(items)!=len(ENTRIES):raise SystemExit('Some travel photos are missing')
