"""Immutable history segments. The active JSON commits references to durable
objects; no old segment is overwritten or pruned. Portable saves/backups expand
references, so manual slots remain independent of the current save directory.
"""
import gzip
import hashlib
import json
from pathlib import Path
import re
from collections import OrderedDict
from uuid import uuid4

from ..json_bytes import encode
from .transaction import _durable_write, _replace
from .immutable import FrozenDict

MAX_BYTES = 512 * 1024 * 1024
LOG_TAIL = 200
ARCHIVED_SCHEMA = '2+history-1'
_verified = OrderedDict()


def _stamp(path):
    if path.is_symlink(): raise ValueError('History segment cannot be a link')
    st = path.stat()
    return st.st_size, st.st_mtime_ns, st.st_ctime_ns


def _remember(path):
    _verified[path] = _stamp(path)
    _verified.move_to_end(path)
    while len(_verified) > 2048: _verified.popitem(last=False)


def _folder(root):
    root = Path(root).resolve()
    folder = root / 'history'
    if folder.is_symlink() or getattr(folder, 'is_junction', lambda: False)():
        raise ValueError('History directory cannot be a link')
    return folder


def _write(root, rows):
    sealed = rows[0] if len(rows) == 1 and isinstance(rows[0], FrozenDict) else None
    digest = getattr(sealed, '_segment_digest', None)
    raw = None
    if digest is None:
        raw = encode(rows)
        digest = hashlib.sha256(raw).hexdigest()
        if sealed is not None: sealed._segment_digest = digest
    folder = _folder(root)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (digest + '.json.gz')
    if target.exists():
        # Revalidate an externally changed file. Immutable records and unchanged
        # verified files need not be decoded on every button press. Loading and
        # exporting a backup always perform full content verification.
        if _verified.get(target) != _stamp(target): _read(root, digest)
    else:
        pending = folder / (uuid4().hex + '.next')
        try:
            _durable_write(pending, gzip.compress(raw if raw is not None else encode(rows), compresslevel=1, mtime=0))
            _replace(pending, target)
            _remember(target)
        finally:
            if pending.exists(): pending.unlink()
    return digest


def _read(root, digest):
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Invalid history segment reference')
    path = _folder(root) / (digest + '.json.gz')
    if path.is_symlink():
        raise ValueError('History segment cannot be a link')
    with gzip.open(path, 'rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('History segment checksum/size mismatch')
    rows = json.loads(raw)
    if not isinstance(rows, list): raise ValueError('Invalid history segment')
    _remember(path)
    return rows


def pack(root, blob):
    out = dict(blob)
    # Records retain original order; completed seasons can never be mistaken
    # for current playable events. Chunking bounds the cost of the next append.
    # A completed event can contain thousands of rounds: archive it even when
    # the player has finished fewer than fifty events in total.
    for key, tail, chunk in (('history', 0, 1), ('log', LOG_TAIL, 200)):
        rows = blob.get(key, [])
        # Only seal complete chunks. A moving partial chunk would produce one
        # orphan object every day and make the archive grow quadratically.
        end = max(0, (len(rows) - tail) // chunk) * chunk
        if not end: continue
        refs = [_write(root, rows[i:min(i+chunk, end)]) for i in range(0, end, chunk)]
        out[key] = rows[end:]
        out[key + '_archive'] = refs
    if 'history_archive' in out or 'log_archive' in out:
        out['history_storage'] = 1
        # 1.7.2 interprets unknown integer versions as a reset request. A
        # non-integer storage tag makes that reader reject/preserve the file
        # instead of silently ignoring the archive or resetting the season.
        if out.get('schema_version') == 2: out['schema_version'] = ARCHIVED_SCHEMA
    return out


def expand(root, blob):
    if 'history_storage' not in blob: return blob
    if blob['history_storage'] != 1: raise ValueError('Unsupported history storage version')
    out = dict(blob)
    if out.get('schema_version') == ARCHIVED_SCHEMA: out['schema_version'] = 2
    for key in ('history', 'log'):
        refs = out.pop(key + '_archive', [])
        if not isinstance(refs, list): raise ValueError('Invalid history segment index')
        out[key] = [row for digest in refs for row in _read(root, digest)] + list(out.get(key, []))
    out.pop('history_storage')
    return out


def portable_bytes(path):
    path = Path(path)
    raw = path.read_bytes()
    if path.name != 'season.json': return raw
    blob = json.loads(raw)
    return encode(expand(path.parent, blob)) if 'history_storage' in blob else raw
