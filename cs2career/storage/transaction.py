"""Recoverable, roll-forward multi-file JSON commits.

The durable manifest is the commit point. Before it, authoritative files are
unchanged; after it, recovery must finish, never roll back. All readers/writers
of one application state are serialized by the application lock. Recovery runs
before loading that state. This journal is not a replacement for user backups.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from uuid import uuid4

_lock = threading.RLock()
_batch = ContextVar('save_batch', default=None)
_discard = ContextVar('discard_save', default=False)
_callbacks = ContextVar('save_commit_callbacks', default=None)
JOURNAL = '.save-transaction'


class CommitPending(Exception):
    """The commit is durable; restart/recover before accepting another command."""


def _checkpoint(_point):
    """Fault-injection seam. Production never changes this function."""


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _durable_write(path, data):
    with path.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _sync_dir(path):
    if os.name != 'nt':
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _replace_once(source, destination):
    if os.name != 'nt':
        os.replace(source, destination)
        return
    # Request write-through for the rename as well as fsync of file contents.
    import ctypes
    from ctypes import wintypes
    move = ctypes.WinDLL('kernel32', use_last_error=True).MoveFileExW
    move.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD)
    move.restype = wintypes.BOOL
    if not move(str(source), str(destination), 0x1 | 0x8):
        raise ctypes.WinError(ctypes.get_last_error())


def _replace(source, destination):
    for attempt in range(6):
        try:
            _replace_once(source, destination)
            _sync_dir(destination.parent)
            return
        except OSError as exc:
            if getattr(exc, 'winerror', None) not in (5, 32, 33) or attempt == 5:
                raise
            time.sleep(.02 * (2 ** attempt))


def _manifest(root):
    folder = root / JOURNAL
    if folder.is_symlink() or getattr(folder, 'is_junction', lambda: False)():
        raise ValueError('Save transaction directory cannot be a link')
    return folder / 'commit.json'


def _recover(root):
    marker = _manifest(root)
    if not marker.exists():
        # Only our own uncommitted staging files, never player saves/backups.
        if marker.parent.exists():
            for orphan in marker.parent.glob('*.next'):
                orphan.unlink()
        return False
    data = json.loads(marker.read_text('utf-8'))
    if data.get('version') != 1 or not isinstance(data.get('files'), list) or not data['files']:
        raise ValueError('Invalid save commit manifest; preserved for recovery')
    rows = []
    for entry in data['files']:
        name, staged, digest = entry['name'], entry['staged'], entry['sha256']
        if (not isinstance(name, str) or Path(name).name != name or name in ('', '.', '..')
                or '/' in name or '\\' in name or ':' in name
                or Path(staged).name != staged or not staged.endswith('.next')
                or '/' in staged or '\\' in staged or ':' in staged
                or len(digest) != 64):
            raise ValueError('Invalid save commit path/hash; preserved for recovery')
        target, source = root / name, marker.parent / staged
        if target.is_symlink() or source.is_symlink():
            raise ValueError('Save transaction files cannot be links')
        if source.exists():
            if _hash(source) != digest:
                raise ValueError('Staged save checksum mismatch; preserved for recovery')
        elif not target.is_file() or _hash(target) != digest:
            raise ValueError('Committed save data is missing; preserved for recovery')
        rows.append((source, target))
    # Validate the whole set before performing any remaining replacement.
    for source, target in rows:
        if source.exists():
            _replace(source, target)
            _checkpoint('replaced:' + target.name)
    marker.unlink()
    _sync_dir(marker.parent)
    _checkpoint('finished')
    return True


def recover(root):
    with _lock:
        return _recover(Path(root).resolve())


def commit(payloads):
    if not payloads:
        return
    values = {Path(p).absolute(): data for p, data in payloads.items()}
    roots = {p.parent for p in values}
    if len(roots) != 1:
        raise ValueError('A save transaction must belong to one save directory')
    root = roots.pop()
    root.mkdir(parents=True, exist_ok=True)
    with _lock:
        _recover(root)
        marker = _manifest(root)
        marker.parent.mkdir(exist_ok=True)
        rows = []
        committed = False
        try:
            for target, data in sorted(values.items()):
                if target.is_symlink():
                    raise ValueError('A save target cannot be a link')
                staged = marker.parent / (uuid4().hex + '.next')
                _durable_write(staged, data)
                rows.append(dict(name=target.name, staged=staged.name,
                                 sha256=hashlib.sha256(data).hexdigest()))
                _checkpoint('staged:' + target.name)
            pending = marker.with_name('manifest.next')
            _durable_write(pending, json.dumps(dict(version=1, files=rows)).encode('utf-8'))
            _sync_dir(marker.parent)
            _checkpoint('before_commit')
            _replace(pending, marker)
            committed = True
            _checkpoint('committed')
            _recover(root)
        except Exception as exc:
            if committed or marker.exists():
                raise CommitPending('Save committed; recovery is required before continuing') from exc
            _recover(root)  # Discard staging only; authoritative files are untouched.
            raise


def save(path, serialize):
    """Coalesce repeated domain saves; serialize the final state once."""
    if _discard.get():
        return
    pending = _batch.get()
    if pending is not None:
        pending[Path(path).absolute()] = serialize
    else:
        commit({Path(path): serialize()})


def read_bytes(path, *, max_bytes=None):
    """Read this operation's pending value, or the last committed file.

    Used for small configuration files needed to build the response before
    commit. Other threads still see only the committed file. Domain snapshots
    continue reading their in-memory objects, not serializing pending saves.
    """
    target = Path(path).absolute()
    pending = _batch.get()
    if pending is not None and target in pending:
        value = pending[target]()
        return value if max_bytes is None else value[:max_bytes]
    with target.open('rb') as stream:
        return stream.read() if max_bytes is None else stream.read(max_bytes)


def on_commit(key, callback):
    callbacks = _callbacks.get()
    if callbacks is None:
        callback()
    else:
        callbacks[key] = callback


@contextmanager
def batch():
    """Nested business operations share the outer commit; exceptions abort it."""
    if _batch.get() is not None:
        yield
        return
    pending = {}
    token = _batch.set(pending)
    callbacks = {}
    callback_token = _callbacks.set(callbacks)
    try:
        yield
        commit({path: serialize() for path, serialize in pending.items()})
        try:
            for callback in callbacks.values():
                callback()
        except Exception as exc:
            # Disk is already committed. Never restore old memory over it.
            raise CommitPending('Save committed; reload after notification failure') from exc
    finally:
        _callbacks.reset(callback_token)
        _batch.reset(token)


@contextmanager
def discard_writes():
    """Build a new, unattached career without replacing live save methods."""
    token = _discard.set(True)
    try:
        yield
    finally:
        _discard.reset(token)
