"""Create a complete local backup with a consistent SQLite snapshot."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parent


def export(output):
    output=Path(output).resolve()
    if output==ROOT or ROOT in output.parents:
        raise ValueError('Choose a backup directory outside the project.')
    output.mkdir(parents=True,exist_ok=True)
    destination=output/'birthday-website-complete.zip'
    if destination.exists():
        destination=output/('birthday-website-complete-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.zip')
    partial=destination.with_suffix('.zip.part')
    ignored={'.git','__pycache__','.pytest_cache','node_modules','.venv','venv'}
    database=ROOT/'data/gallery.sqlite'
    count=0
    try:
        temporary_root=Path('/tmp/opencode')
        with tempfile.TemporaryDirectory(prefix='birthday-export-',dir=temporary_root if temporary_root.is_dir() else None) as directory:
            snapshot=Path(directory)/'gallery.sqlite'
            if database.is_file():
                source=sqlite3.connect(database)
                backup=sqlite3.connect(snapshot)
                try:
                    source.backup(backup)
                    if backup.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                        raise RuntimeError('Database snapshot failed verification.')
                finally:
                    source.close();backup.close()
            with zipfile.ZipFile(partial,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
                for path in sorted(ROOT.rglob('*')):
                    relative=path.relative_to(ROOT)
                    if path.is_symlink() or not path.is_file() or any(part in ignored for part in relative.parts):
                        continue
                    if path.suffix in ('.log','.pyc','.part','.tmp') or path.name.endswith(('-wal','-shm','-journal')):
                        continue
                    source=snapshot if path==database else path
                    archive.write(source,'birthday-website/'+relative.as_posix())
                    count+=1
                archive.writestr('birthday-website/EXPORT_INFO.json',json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),'files':count,'database':'Consistent SQLite backup','includes_private_configuration':True,'includes_local_media_and_models':True,'excluded':'runtime logs, bytecode, caches and temporary files'},indent=2))
            with zipfile.ZipFile(partial) as archive:
                bad=archive.testzip()
                if bad:
                    raise RuntimeError('Archive verification failed for '+bad)
                required=['server.py','site.html','recipient.js','birthday_names.py','requirements.txt','.env','data/gallery.sqlite','models/yunet.onnx','models/sface.onnx']
                names=set(archive.namelist())
                if any('birthday-website/'+name not in names for name in required):
                    raise RuntimeError('Archive is missing a required project file.')
            partial.replace(destination)
        digest=hashlib.sha256()
        with destination.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):
                digest.update(block)
        checksum=destination.with_suffix('.zip.sha256')
        checksum.write_text(digest.hexdigest()+'  '+destination.name+'\n')
        print(json.dumps({'archive':str(destination),'files':count+1,'bytes':destination.stat().st_size,'sha256':digest.hexdigest(),'checksum_file':str(checksum),'verified':True},indent=2))
    finally:
        partial.unlink(missing_ok=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='/sdcard/birthday')
    args=parser.parse_args()
    export(args.output)
