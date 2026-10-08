"""Seed the Railway database from the GitHub-shipped Download/ photos.

Run once at startup when the media table has no local photos yet:
- scans Download/*.jpg (originals, not .preview/.browser derivatives)
- creates media rows (source='local') with image metadata
- distributes photos round-robin across the 7 members so every
  member page gets photos, rest stay 'all'
"""
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import image_quality  # noqa: E402

import os as _os
from pathlib import Path as _Path
ROOT = _Path(__file__).resolve().parent
MEDIA_DIR = _os.getenv('MEDIA_DIR', '')
DOWNLOAD = _Path(MEDIA_DIR) if MEDIA_DIR and _Path(MEDIA_DIR).exists() else (ROOT / 'Download')
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
MEMBERS = ['rm', 'jin', 'suga', 'jhope', 'jimin', 'v', 'jungkook']
PER_MEMBER = 5


def main():
    db = sqlite3.connect(DATA / 'gallery.sqlite', timeout=30)
    db.row_factory = sqlite3.Row
    existing = db.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    if existing:
        print(f'seed skipped: {existing} media rows already present')
        return

    photos = sorted(p for p in DOWNLOAD.glob('*.jpg') if not p.name.endswith(('.preview.jpg', '.browser.jpg')))
    print(f'found {len(photos)} local photos')

    # pick PER_MEMBER photos per member (evenly spaced through the list), rest -> all
    tagged = {}
    for i, member in enumerate(MEMBERS):
        step = max(1, len(photos) // (PER_MEMBER * len(MEMBERS)))
        picks = photos[i::max(1, len(photos) // 7)][:PER_MEMBER]
        tagged[member] = picks
    tagged_ids = {p.name for picks in tagged.values() for p in picks}

    now = time.time()
    count = 0
    for idx, path in enumerate(photos):
        member = 'all'
        for m, picks in tagged.items():
            if path in picks:
                member = m
                break
        meta = image_quality.inspect(path) or {}
        title = f'A little more than a photograph · without a hurry'
        db.execute(
            "INSERT INTO media(id, filename, preview, kind, title, member, created, source, credit) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                path.stem, path.name, meta.get('display_filename', path.name),
                'image', title, member, now - (len(photos) - idx), 'local', '',
            ),
        )
        count += 1
    db.commit()
    print(f'seeded {count} photos ({PER_MEMBER} each for {len(MEMBERS)} members, rest all)')


if __name__ == '__main__':
    main()
