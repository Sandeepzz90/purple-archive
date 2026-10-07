"""Offline BTS member matching against explicit, labelled reference photographs."""
import atexit
import hashlib
import json
import math
import os
from pathlib import Path
import select
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parent
MEMBERS = {'rm', 'jin', 'suga', 'jhope', 'jimin', 'v', 'jungkook'}
THRESHOLD = .50
MARGIN = .10


class LocalSortError(Exception):
    pass


class LocalSorter:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir or ROOT / 'data')
        self.process = None
        self.lock = threading.Lock()
        atexit.register(self.close)

    @property
    def reference_path(self):
        return self.data_dir / 'face_references.json'

    def references(self):
        try:
            data = json.loads(self.reference_path.read_text())
            return data.get('references', [])
        except (OSError, ValueError):
            return []

    def status(self):
        counts = {name: 0 for name in sorted(MEMBERS)}
        for item in self.references():
            if item.get('member') in counts:
                counts[item['member']] += 1
        installed = all((ROOT / 'models' / name).is_file() for name in ('yunet.onnx', 'sface.onnx'))
        return {'installed': installed, 'references': counts, 'ready': installed and all(counts.values()), 'threshold': THRESHOLD, 'margin': MARGIN}

    def close(self):
        process = self.process
        self.process = None
        if process:
            try:
                process.terminate()
                process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            for stream in (process.stdin, process.stdout):
                if stream:
                    stream.close()

    def request(self, request):
        with self.lock:
            try:
                if not self.process or self.process.poll() is not None:
                    self.close()
                    binary = os.getenv('LOCAL_FACE_PYTHON', sys.executable)
                    self.process = subprocess.Popen([binary, '-u', str(ROOT / 'local_face_worker.py')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
                self.process.stdin.write(json.dumps(request) + '\n')
                self.process.stdin.flush()
                readable, _, _ = select.select([self.process.stdout], [], [], 90)
                if not readable:
                    raise LocalSortError('Local image matching timed out')
                result = json.loads(self.process.stdout.readline())
                if not result.get('ok'):
                    raise LocalSortError('Local model could not process this image')
                return result
            except (OSError, ValueError, BrokenPipeError):
                self.close()
                raise LocalSortError('Local OpenCV worker is unavailable') from None
            except LocalSortError:
                self.close()
                raise

    def add_reference(self, path, member, identity):
        if member not in MEMBERS:
            raise LocalSortError('Choose one member for a reference')
        result = self.request({'op': 'embed', 'path': str(Path(path).resolve())})
        if result.get('detected') != 1 or len(result['faces']) != 1:
            raise LocalSortError('A reference must contain exactly one clear face')
        items = [r for r in self.references() if r.get('id') != identity]
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        items.append({'id': identity, 'member': member, 'sha256': digest, 'embedding': result['faces'][0]['embedding']})
        self.data_dir.mkdir(exist_ok=True)
        temporary = self.reference_path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'engine': 'OpenCV YuNet + SFace', 'references': items}))
        os.chmod(temporary, 0o600)
        temporary.replace(self.reference_path)
        return len(items)

    @staticmethod
    def choose(embedding, references, threshold=THRESHOLD, margin=MARGIN):
        scores = {}
        for reference in references:
            member, other = reference.get('member'), reference.get('embedding', [])
            if member not in MEMBERS or len(other) != len(embedding):
                continue
            score = sum(a*b for a, b in zip(embedding, other))
            if not math.isfinite(score):
                continue
            scores[member] = max(scores.get(member, -1), score)
        ranked = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
        if not ranked:
            return None, []
        best = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else -1
        accepted = best[0] if best[1] >= threshold and best[1] - runner_up >= margin else None
        return accepted, [{'member': member, 'score': round(score, 4)} for member, score in ranked[:3]]

    def classify(self, path):
        refs = self.references()
        if not self.status()['ready']:
            raise LocalSortError('Local matching needs reference photos for all seven members')
        result = self.request({'op': 'embed', 'path': str(Path(path).resolve())})
        labels, details = [], []
        for face in result['faces']:
            member, scores = self.choose(face['embedding'], refs)
            if member and member not in labels:
                labels.append(member)
            details.append({'member': member, 'candidates': scores, 'box': face['box']})
        return {'members': labels, 'faces': details, 'detected': result.get('detected', 0)}


if __name__ == '__main__':
    engine = LocalSorter()
    print(json.dumps(engine.classify(sys.argv[1]) if len(sys.argv) > 1 else engine.status(), indent=2))
