"""Locally cached travel photography, separate from the BTS media library."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Catalog embedded directly: Railway mounts a volume at /app/data which shadows
# the repository's data/ directory, so JSON files on disk are not reliable.
_EMBEDDED = json.loads(r"""
[
  {
    "id": "seoul",
    "filename": "korea-seoul.jpg",
    "preview": "korea-seoul.jpg",
    "width": 1280,
    "height": 964,
    "mime": "image/jpeg",
    "title": "Seoul, a city of little possibilities",
    "korean": "\uc11c\uc6b8",
    "source": "https://thumb.wikimedia.org/wikipedia/commons/thumb/3/30/%EC%A4%91%ED%99%94%EC%A0%84%EC%9D%98_%EB%82%AE.jpg/1280px-%EC%A4%91%ED%99%94%EC%A0%84%EC%9D%98_%EB%82%AE.jpg?utm_source=en.wikipedia.org&utm_campaign=index&utm_content=thumbnail",
    "credit": "https://commons.wikimedia.org/wiki/File:\uc911\ud654\uc804\uc758_\ub0ae.jpg"
  },
  {
    "id": "palace",
    "filename": "korea-palace.jpg",
    "preview": "korea-palace.jpg",
    "width": 1280,
    "height": 853,
    "mime": "image/jpeg",
    "title": "A royal afternoon at Gyeongbokgung",
    "korean": "\uacbd\ubcf5\uad81",
    "source": "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/63/%EA%B4%91%ED%99%94%EB%AC%B8_%EC%9B%94%EB%8C%80.jpg/1280px-%EA%B4%91%ED%99%94%EB%AC%B8_%EC%9B%94%EB%8C%80.jpg?utm_source=en.wikipedia.org&utm_campaign=index&utm_content=thumbnail",
    "credit": "https://commons.wikimedia.org/wiki/File:\uad11\ud654\ubb38_\uc6d4\ub300.jpg"
  },
  {
    "id": "hanok",
    "filename": "korea-hanok.jpg",
    "preview": "korea-hanok.jpg",
    "width": 1280,
    "height": 853,
    "mime": "image/jpeg",
    "title": "A walk through Bukchon",
    "korean": "\ubd81\ucd0c\ud55c\uc625\ub9c8\uc744",
    "source": "https://thumb.wikimedia.org/wikipedia/commons/thumb/2/2e/Bukchon_Hanok_Village_01.jpg/1280px-Bukchon_Hanok_Village_01.jpg?utm_source=en.wikipedia.org&utm_campaign=index&utm_content=thumbnail",
    "credit": "https://commons.wikimedia.org/wiki/File:Bukchon_Hanok_Village_01.jpg"
  },
  {
    "id": "busan",
    "filename": "korea-busan.jpg",
    "preview": "korea-busan.jpg",
    "width": 1280,
    "height": 720,
    "mime": "image/jpeg",
    "title": "A little sea breeze in Busan",
    "korean": "\ubd80\uc0b0",
    "source": "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/5d/Gwangan_Bridge1.jpg/1280px-Gwangan_Bridge1.jpg?utm_source=en.wikipedia.org&utm_campaign=index&utm_content=thumbnail",
    "credit": "https://commons.wikimedia.org/wiki/File:Gwangan_Bridge1.jpg"
  },
  {
    "id": "jeju",
    "filename": "korea-jeju.jpg",
    "preview": "korea-jeju.jpg",
    "width": 1280,
    "height": 834,
    "mime": "image/jpeg",
    "title": "A daydream on Jeju Island",
    "korean": "\uc81c\uc8fc\ub3c4",
    "source": "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/61/Seongsan_Ilchulbong_from_the_air.jpg/1280px-Seongsan_Ilchulbong_from_the_air.jpg?utm_source=en.wikipedia.org&utm_campaign=index&utm_content=thumbnail",
    "credit": "https://commons.wikimedia.org/wiki/File:Seongsan_Ilchulbong_from_the_air.jpg"
  },
  {
    "id": "india",
    "filename": "korea-india.jpg",
    "preview": "korea-india.jpg",
    "width": 1280,
    "height": 1397,
    "mime": "image/jpeg",
    "title": "Your little journey begins in India",
    "korean": "\uc778\ub3c4",
    "source": "https://thumb.wikimedia.org/wikipedia/commons/thumb/3/3b/India_Gate_front.jpg/1280px-India_Gate_front.jpg?utm_source=en.wikipedia.org&utm_campaign=index&utm_content=thumbnail",
    "credit": "https://commons.wikimedia.org/wiki/File:India_Gate_front.jpg"
  }
]
""")

def catalog():
    if _EMBEDDED:
        return _EMBEDDED
    try:
        return json.loads((ROOT / 'data' / 'korea_photos.json').read_text())
    except (OSError, ValueError):
        return []


def public_catalog():
    return [{key: item[key] for key in ('id','filename','preview','width','height','title','korean')} for item in catalog()]


def find_file(name):
    return next((item for item in catalog() if name in (item['filename'], item['preview'])), None)
