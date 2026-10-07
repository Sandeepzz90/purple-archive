"""Full-resolution display metadata. Native image originals are never recompressed."""
import hashlib
import json
import mimetypes
from pathlib import Path
import subprocess

from PIL import Image, ImageOps

NATIVE_FORMATS = {'JPEG', 'PNG', 'GIF', 'WEBP', 'AVIF', 'BMP'}


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS image_info (
        media_id TEXT PRIMARY KEY, width INTEGER, height INTEGER, orientation TEXT,
        mime TEXT, display_filename TEXT, original_bytes INTEGER, original_sha256 TEXT)''')


def inspect(path):
    path = Path(path)
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    display = path.name
    try:
        with Image.open(path) as image:
            width, height = image.size
            original_format = image.format
            mime = Image.MIME.get(original_format, mime)
            orientation = image.getexif().get(274, 1)
            if orientation in (5, 6, 7, 8):
                width, height = height, width
            if original_format not in NATIVE_FORMATS:
                # A full-sized, lossless browser copy for formats such as TIFF.
                converted = ImageOps.exif_transpose(image)
                if converted.mode not in ('RGB', 'RGBA', 'L', 'LA', 'P', 'I', 'I;16'):
                    converted = converted.convert('RGBA' if 'A' in converted.getbands() else 'RGB')
                target = path.with_suffix('.display.png')
                converted.save(target, 'PNG', icc_profile=image.info.get('icc_profile'))
                display = target.name
    except (OSError, ValueError, KeyError):
        if path.suffix.lower() not in ('.webp', '.avif', '.heic', '.heif'):
            return None
        try:
            result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=20)
            stream = json.loads(result.stdout)['streams'][0]
            width, height = int(stream['width']), int(stream['height'])
            if path.suffix.lower() in ('.heic', '.heif'):
                target = path.with_suffix('.display.png')
                subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(path), '-frames:v', '1', str(target)], check=True, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                display = target.name
        except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
            return None
    if width <= 0 or height <= 0:
        return None
    return {'width': width, 'height': height, 'orientation': 'square' if width == height else 'landscape' if width > height else 'portrait', 'mime': mime, 'display_filename': display, 'original_bytes': path.stat().st_size, 'original_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def store(db, identity, info):
    db.execute('INSERT OR REPLACE INTO image_info VALUES (?,?,?,?,?,?,?,?)', (identity, info['width'], info['height'], info['orientation'], info['mime'], info['display_filename'], info['original_bytes'], info['original_sha256']))


def migrate(db, directory):
    changed = 0
    rows = db.execute("SELECT id,filename FROM media WHERE kind='image' AND id NOT IN (SELECT media_id FROM image_info)").fetchall()
    for row in rows:
        info = inspect(Path(directory) / row['filename'])
        if info:
            store(db, row['id'], info)
            db.execute('UPDATE media SET preview=? WHERE id=?', (info['display_filename'], row['id']))
            changed += 1
    return changed
