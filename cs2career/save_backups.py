"""Lossless, streaming safety snapshots. Never prune old player backups.

Active saves stay ordinary schema-v2 JSON. New snapshots contain .json.gz plus
SHA-256/size metadata; legacy .json snapshots remain readable. Restore stages
and validates the entire pair before replacing either active file.
"""
from contextlib import contextmanager
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
from uuid import uuid4

NAMES = ('season.json', 'career.json')
CHUNK = 1024 * 1024


def digest(stream, output=None):
    checksum=hashlib.sha256();size=0
    while chunk:=stream.read(CHUNK):
        checksum.update(chunk);size+=len(chunk)
        if output is not None:output.write(chunk)
    return dict(sha256=checksum.hexdigest(),bytes=size)


def metadata(folder):
    file=Path(folder)/'snapshot.json'
    if not file.is_file():return None
    data=json.loads(file.read_text('utf-8'))
    if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('files'),dict) or set(data['files'])-set(NAMES):
        raise ValueError('备份清单格式无效')
    return data['files']


@contextmanager
def open_member(folder,name):
    if name not in NAMES:raise ValueError('无效的存档文件名')
    folder=Path(folder).resolve()
    raw=folder/name;packed=folder/(name+'.gz')
    source=packed if packed.is_file() else raw
    if not source.is_file() or source.resolve().parent!=folder:
        raise ValueError('备份缺少完整存档文件，或引用了目录外的文件')
    with (gzip.open(source,'rb') if source==packed else source.open('rb')) as stream:
        yield stream


def verify(folder,expected=None):
    expected=metadata(folder) if expected is None else expected
    names=tuple(expected) if expected is not None else NAMES
    for name in names:
        with open_member(folder,name) as stream:actual=digest(stream)
        if expected is not None and actual!=expected[name]:
            raise ValueError('备份校验失败：'+name)
    return True


def create(root):
    root=Path(root).resolve()
    files=[root/name for name in NAMES if (root/name).is_file()]
    if not files:return None
    expected={}
    for file in files:
        with file.open('rb') as stream:expected[file.name]=digest(stream)
    parent=root/'backups';parent.mkdir(parents=True,exist_ok=True)
    # Only our complete, committed snapshots qualify for reuse. Old backups
    # are left completely untouched, not compressed/migrated as a side effect.
    latest=max((p for p in parent.iterdir() if p.is_dir() and not p.is_symlink()),
               key=lambda p:(p.stat().st_mtime_ns,p.name),default=None)
    if latest is not None:
        try:
            if metadata(latest)==expected and verify(latest,expected):return latest
        except (OSError,ValueError,EOFError):pass
    folder=parent/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:8])
    folder.mkdir()
    for file in files:
        target=folder/(file.name+'.gz');pending=target.with_suffix('.writing')
        with file.open('rb') as src,pending.open('wb') as dst:
            with gzip.GzipFile(filename='',fileobj=dst,mode='wb',compresslevel=1,mtime=0) as archive:
                actual=digest(src,archive)
        if actual!=expected[file.name]:raise ValueError('备份期间存档发生变化，请关闭其他生涯窗口后重试')
        pending.replace(target)
    verify(folder,expected)
    pending=folder/'snapshot.writing'
    pending.write_text(json.dumps(dict(version=1,files=expected),ensure_ascii=False),encoding='utf-8')
    pending.replace(folder/'snapshot.json')
    return folder


def restore(root,folder,*,require_pair=True):
    root=Path(root).resolve();folder=Path(folder).resolve()
    if not folder.is_relative_to(root/'backups') or folder==root/'backups':
        raise ValueError('备份恢复路径必须位于当前存档的backups子目录')
    expected=metadata(folder)
    names=NAMES if require_pair or expected is None else tuple(expected)
    staged=[]
    for name in names:
        pending=root/(name+'.transfer-restore')
        with open_member(folder,name) as src,pending.open('wb') as dst:
            actual=digest(src,dst)
        if expected is not None and actual!=expected.get(name):
            raise ValueError('备份校验失败，当前存档未替换：'+name)
        staged.append((pending,root/name))
    for pending,target in staged:pending.replace(target)
