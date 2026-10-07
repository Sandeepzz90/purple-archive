"""Small JSON-lines worker for OpenCV YuNet detection and SFace embeddings.

Runs under the Python installation with OpenCV. Originals are read, never modified.
"""
import json
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
cv2.setNumThreads(2)
detector = cv2.FaceDetectorYN.create(str(ROOT / 'models/yunet.onnx'), '', (320, 320), .88, .3, 5000)
recognizer = cv2.FaceRecognizerSF.create(str(ROOT / 'models/sface.onnx'), '')


def embed(path):
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None:
        return {'faces': [], 'reason': 'Unsupported image'}
    height, width = image.shape[:2]
    original = image
    faces = None
    scale = 1.0
    # YuNet needs smaller passes for very tightly framed, large portraits.
    for limit in (960, 640, 320):
        scale = min(1.0, limit / max(height, width))
        image = cv2.resize(original, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else original
        detector.setInputSize((image.shape[1], image.shape[0]))
        _, faces = detector.detect(image)
        if faces is not None:
            break
    if faces is None:
        return {'faces': [], 'detected': 0}
    faces = sorted(faces, key=lambda face: float(face[2] * face[3]), reverse=True)
    result = []
    for face in faces[:16]:
        if min(float(face[2]), float(face[3])) < 40:
            continue
        aligned = recognizer.alignCrop(image, face)
        feature = recognizer.feature(aligned).reshape(-1).astype(np.float32)
        norm = np.linalg.norm(feature)
        if norm <= 0:
            continue
        feature /= norm
        result.append({'embedding': feature.tolist(), 'box': [round(float(n) / scale, 1) for n in face[:4]], 'detection': round(float(face[-1]), 4)})
    return {'faces': result, 'detected': len(faces)}


for line in sys.stdin:
    try:
        request = json.loads(line)
        if request.get('op') == 'ping':
            answer = {'ok': True, 'opencv': cv2.__version__}
        else:
            answer = {'ok': True, **embed(request['path'])}
    except Exception as error:
        answer = {'ok': False, 'error': type(error).__name__}
    print(json.dumps(answer), flush=True)
