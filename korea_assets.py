"""Locally cached travel photography, separate from the BTS media library."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def catalog():
    try:
        return json.loads((ROOT/'data/korea_photos.json').read_text())
    except (OSError,ValueError):
        return []


def public_catalog():
    return [{key:item[key] for key in ('id','filename','preview','width','height','title','korean')} for item in catalog()]


def find_file(name):
    return next((item for item in catalog() if name in (item['filename'],item['preview'])),None)
