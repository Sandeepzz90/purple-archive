"""Install official OpenCV Zoo models, verifying their published Git LFS hashes."""
import hashlib
import json
from pathlib import Path
import re

import requests

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / 'models'
FILES = {
    'yunet.onnx': 'face_detection_yunet/face_detection_yunet_2023mar.onnx',
    'sface.onnx': 'face_recognition_sface/face_recognition_sface_2021dec.onnx',
}


def install():
    MODEL_DIR.mkdir(exist_ok=True)
    manifest = {}
    session = requests.Session()
    session.headers['User-Agent'] = 'PurpleArchive local OpenCV model installer/1.0'
    for name, relative in FILES.items():
        raw = 'https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/' + relative
        pointer = session.get(raw, timeout=40)
        pointer.raise_for_status()
        match = re.search(r'oid sha256:([a-f0-9]{64})', pointer.text)
        if not match:
            raise RuntimeError('Missing published checksum for ' + name)
        expected = match[1]
        target = MODEL_DIR / name
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            source = 'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/' + relative
            response = session.get(source, timeout=180)
            response.raise_for_status()
            if hashlib.sha256(response.content).hexdigest() != expected:
                raise RuntimeError('Model checksum mismatch: ' + name)
            partial = target.with_suffix('.part')
            partial.write_bytes(response.content)
            partial.replace(target)
        license_url = raw.rsplit('/', 1)[0] + '/LICENSE'
        license_response = session.get(license_url, timeout=40)
        license_response.raise_for_status()
        (MODEL_DIR / (name + '.LICENSE')).write_text(license_response.text)
        manifest[name] = {'source': raw, 'sha256': expected, 'bytes': target.stat().st_size, 'license': license_url}
        print(name + ': verified and ready', flush=True)
    (MODEL_DIR / 'manifest.json').write_text(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    install()
