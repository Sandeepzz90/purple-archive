"""Locally cached travel photography, separate from the BTS media library."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def catalog():
    for candidate in (ROOT/'data'/'korea_photos.json',):
        try:
            items=json.loads(candidate.read_text())
            if items:
                return items
        except (OSError,ValueError):
            continue
    return []


def public_catalog():
    return [{key:item[key] for key in ('id','filename','preview','width','height','title','korean')} for item in catalog()]


def find_file(name):
    return next((item for item in catalog() if name in (item['filename'],item['preview'])),None)
