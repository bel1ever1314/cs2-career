"""Explicit manual slots and recoverable three-file restore transactions.

No automatic history or pruning. Global configuration, start-draw receipts,
resources and the old safety backups are outside the slot. The caller holds
the application lock; recover() runs before ApplicationState is loaded.
"""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import uuid4
import zlib

NAMES = ('season.json', 'career.json', 'arena.json')
VERSION = 1
MAX_MEMBER_BYTES = 512 * 1024 * 1024
_ID = re.compile(r'[0-9a-f]{32}')


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def decode(payload):
    def invalid(value):
        raise ValueError('存档包含无效数值：' + value)
    return json.loads(payload, parse_constant=invalid)


def atomic_bytes(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name('.' + path.name + '.' + uuid4().hex + '.writing')
    try:
        with pending.open('wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        if pending.exists():
            pending.unlink()


def _base(root, create=False):
    root = Path(root).resolve()
    base = root / 'manual'
    if base.is_symlink() or base.resolve().parent != root:
        raise ValueError('手动存档目录不能指向其他位置。')
    if create:
        base.mkdir(exist_ok=True)
    return base


def slot_path(root, ident):
    if not isinstance(ident, str) or not _ID.fullmatch(ident):
        raise ValueError('手动存档编号无效。')
    base = _base(root)
    folder = base / ident
    if folder.is_symlink() or folder.resolve().parent != base.resolve():
        raise ValueError('手动存档路径无效。')
    return folder


def _read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('存档文件缺失或不是普通文件。')
    if path.stat().st_size > MAX_MEMBER_BYTES:
        raise ValueError('存档文件过大，未读取或覆盖。')
    return path.read_bytes()


def requests(root):
    path = _base(root) / 'requests.json'
    if not path.exists():
        return {}
    value = decode(_read(path))
    if not isinstance(value, dict) or value.get('version') != VERSION or not isinstance(value.get('requests'), dict):
        raise ValueError('手动存档请求记录损坏，请保留原文件。')
    return value['requests']


def record_request(root, request_id, row):
    rows = requests(root)
    rows[request_id] = row
    atomic_bytes(_base(root, True) / 'requests.json', encode({'version': VERSION, 'requests': rows}))


def manifest(root, ident):
    folder = slot_path(root, ident)
    value = decode(_read(folder / 'manifest.json'))
    if (not isinstance(value, dict) or value.get('version') != VERSION
            or value.get('kind') != 'cs2career-manual-save' or value.get('id') != ident
            or not isinstance(value.get('files'), dict) or set(value['files']) != set(NAMES)
            or not isinstance(value.get('summary'), dict)):
        raise ValueError('手动存档清单损坏。')
    summary = value['summary']
    if (any(not isinstance(summary.get(key), str) for key in
            ('label', 'player', 'team', 'date', 'era', 'created_at'))
            or not 1 <= len(summary['label']) <= 64):
        raise ValueError('手动存档摘要无效。')
    for name, meta in value['files'].items():
        if (not isinstance(meta, dict) or type(meta.get('bytes')) is not int
                or not 0 < meta['bytes'] <= MAX_MEMBER_BYTES
                or not isinstance(meta.get('sha256'), str)
                or not re.fullmatch(r'[0-9a-f]{64}', meta['sha256'])):
            raise ValueError('手动存档校验信息无效。')
        member = folder / (name + '.gz')
        if member.is_symlink() or not member.is_file():
            raise ValueError('手动存档缺少完整的三份进度。')
    return value


def list_slots(root):
    base = _base(root)
    if not base.exists():
        return []
    rows = []
    for folder in base.iterdir():
        if not folder.is_dir() or folder.is_symlink() or not _ID.fullmatch(folder.name):
            continue
        try:
            value = manifest(root, folder.name)
            row = dict(value['summary'], id=folder.name)
            row['size_bytes'] = sum((folder / name).stat().st_size
                                    for name in ['manifest.json', *(n + '.gz' for n in NAMES)])
        except (OSError, ValueError, TypeError):
            row = dict(id=folder.name, label='损坏的手动存档', player='', team='', date='',
                       era='', created_at='', size_bytes=0, corrupt=True)
        rows.append(row)
    return sorted(rows, key=lambda row: (row.get('created_at', ''), row['id']), reverse=True)


def read_slot(root, ident):
    value = manifest(root, ident)
    result = {}
    for name in NAMES:
        member = slot_path(root, ident) / (name + '.gz')
        expected = value['files'][name]
        chunks, size, checksum = [], 0, hashlib.sha256()
        try:
            with gzip.open(member, 'rb') as stream:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > expected['bytes'] or size > MAX_MEMBER_BYTES:
                        raise ValueError('手动存档解压大小不符。')
                    checksum.update(chunk)
                    chunks.append(chunk)
        except (OSError, EOFError, zlib.error) as exc:
            raise ValueError('手动存档压缩文件损坏，当前进度未更改。') from exc
        if size != expected['bytes'] or checksum.hexdigest() != expected['sha256']:
            raise ValueError('手动存档校验失败，当前进度未更改。')
        payload = b''.join(chunks)
        if not isinstance(decode(payload), dict):
            raise ValueError('手动存档内容不是有效进度。')
        result[name] = payload
    return result


def create_slot(root, ident, payloads, summary, request_hash):
    if set(payloads) != set(NAMES):
        raise ValueError('手动存档必须包含完整三份进度。')
    folder = slot_path(root, ident)
    if folder.exists():
        value = manifest(root, ident)
        if value.get('request_hash') != request_hash:
            raise ValueError('手动存档编号已被其他请求占用。')
        read_slot(root, ident)
        return next(row for row in list_slots(root) if row['id'] == ident)
    base = _base(root, True)
    staging = base / ('.writing-' + ident)
    if staging.exists():
        _cleanup(staging)
    staging.mkdir()
    try:
        files = {}
        for name in NAMES:
            data = payloads[name]
            if not isinstance(data, bytes) or not 0 < len(data) <= MAX_MEMBER_BYTES:
                raise ValueError('手动存档进度大小无效。')
            files[name] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            atomic_bytes(staging / (name + '.gz'), gzip.compress(data, compresslevel=1, mtime=0))
        atomic_bytes(staging / 'manifest.json', encode(dict(version=VERSION, kind='cs2career-manual-save',
                    id=ident, request_hash=request_hash, summary=summary, files=files)))
        os.replace(staging, folder)
    finally:
        if staging.exists():
            _cleanup(staging)
    read_slot(root, ident)
    return next(row for row in list_slots(root) if row['id'] == ident)


def _cleanup(folder):
    """Remove only known transaction members, never recursively follow a tree."""
    folder = Path(folder)
    if folder.is_symlink():
        raise ValueError('存档临时目录不能是链接。')
    allowed = {'manifest.json', *(n + '.gz' for n in NAMES),
               *(n + '.before' for n in NAMES), *(n + '.after' for n in NAMES)}
    for path in folder.iterdir():
        if path.name not in allowed or path.is_symlink() or not path.is_file():
            raise ValueError('存档目录含未知内容，未删除。')
    for path in folder.iterdir():
        path.unlink()
    folder.rmdir()


def delete_slot(root, ident):
    folder = slot_path(root, ident)
    if folder.exists():
        _cleanup(folder)  # Corrupt known-format slots can still be explicitly deleted.


def _journal_path(root):
    return Path(root).resolve() / 'manual-load.pending.json'


def begin_restore(root, payloads, request_id, request_hash, result):
    root = Path(root).resolve()
    if _journal_path(root).exists():
        raise ValueError('存档恢复事务尚未完成，请重启后再试。')
    token = uuid4().hex
    work = _base(root, True) / ('.restore-' + token)
    work.mkdir()
    before = {}
    try:
        for name in NAMES:
            target = root / name
            data = _read(target) if target.exists() else None
            before[name] = None if data is None else dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            if data is not None:
                atomic_bytes(work / (name + '.before'), data)
            atomic_bytes(work / (name + '.after'), payloads[name])
        journal = dict(version=VERSION, phase='prepared', token=token, before=before,
                       request_id=request_id, request_hash=request_hash, result=result)
        atomic_bytes(_journal_path(root), encode(journal))
    except Exception:
        if not _journal_path(root).exists():
            _cleanup(work)
        raise
    return journal


def _transaction(root):
    root = Path(root).resolve()
    journal = decode(_read(_journal_path(root)))
    if (not isinstance(journal, dict) or journal.get('version') != VERSION
            or journal.get('phase') not in ('prepared', 'committed')
            or not isinstance(journal.get('token'), str) or not _ID.fullmatch(journal['token'])
            or not isinstance(journal.get('before'), dict) or set(journal['before']) != set(NAMES)):
        raise ValueError('存档恢复记录损坏，未替换当前进度。')
    work = _base(root) / ('.restore-' + journal['token'])
    if work.is_symlink() or work.resolve().parent != _base(root).resolve():
        raise ValueError('存档恢复临时路径无效。')
    return journal, work


def apply_restore(root):
    _, work = _transaction(root)
    for name in NAMES:
        atomic_bytes(Path(root) / name, _read(work / (name + '.after')))


def commit_restore(root):
    journal, _ = _transaction(root)
    journal['phase'] = 'committed'
    atomic_bytes(_journal_path(root), encode(journal))
    recover(root)


def recover(root):
    """Prepared restore rolls back; committed restore completes its receipt."""
    root = Path(root).resolve()
    if not _journal_path(root).exists():
        return False
    journal, work = _transaction(root)
    if journal['phase'] == 'prepared':
        # Validate all old files before touching any current file. Copies remain
        # in the work directory so another interrupted rollback can retry.
        old = {}
        for name, expected in journal['before'].items():
            if expected is None:
                old[name] = None
                continue
            data = _read(work / (name + '.before'))
            if expected != dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest()):
                raise ValueError('存档回滚文件校验失败，已保留恢复记录。')
            old[name] = data
        for name, data in old.items():
            target = root / name
            if data is None:
                if target.exists():
                    if target.is_symlink():
                        raise ValueError('当前存档不能是链接。')
                    target.unlink()
            else:
                atomic_bytes(target, data)
        row = requests(root).get(journal['request_id'])
        if row and row.get('status') == 'pending':
            record_request(root, journal['request_id'], dict(row, status='rolled_back'))
    else:
        record_request(root, journal['request_id'], dict(status='done', hash=journal['request_hash'],
                       action='load', result=journal['result']))
    # Remove the journal before housekeeping: a crash during cleanup cannot
    # turn a committed load into a missing-work-directory recovery failure.
    _journal_path(root).unlink()
    _cleanup(work)
    return True
