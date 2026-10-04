"""Read-only, privacy-preserving checks of persistent CS2 launch options."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import re
from stat import S_ISDIR
from threading import RLock


MAX_CONFIG_BYTES = 8 * 1024 * 1024
MAX_TOKENS = 250_000
MAX_CACHE_FILES = 128
INSECURE_REASON = ('Steam 的 CS2 启动选项仍含 -insecure；请在 Steam → CS2 → 属性 → '
                   '启动选项中移除后再打排位。')
UNCHECKED_REASON = '暂时无法确认 Steam 的 CS2 启动选项，请在 Steam 属性中检查。'
_TARGET = ('userlocalconfigstore', 'software', 'valve', 'steam', 'apps', '730', 'launchoptions')
_TOKEN = re.compile(r'\s+|//[^\r\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[{}]|[^\s{}"]+')
_FLAG = re.compile(r'(?:^|[\s"])-insecure(?=$|[\s"])', re.IGNORECASE)
_CACHE: OrderedDict[tuple, bool] = OrderedDict()
_CACHE_LOCK = RLock()


def _decode_quoted(raw):
    if not raw.startswith('"'):
        return raw
    return re.sub(r'\\([\\"nrt])', lambda hit: {
        '\\': '\\', '"': '"', 'n': '\n', 'r': '\r', 't': '\t'}[hit[1]], raw[1:-1])


def _has_insecure(text):
    """Validate all KeyValues syntax, but retain only the target flag boolean."""
    found_root, insecure = False, False
    tokens = []
    at = 0
    for match in _TOKEN.finditer(text):
        if match.start() != at:
            raise ValueError('Malformed Steam KeyValues')
        at = match.end()
        raw = match[0]
        if raw.startswith('/*') and not raw.endswith('*/'):
            raise ValueError('Unclosed Steam KeyValues comment')
        if raw.isspace() or raw.startswith(('//', '/*')):
            continue
        tokens.append((raw if raw in ('{', '}') else _decode_quoted(raw), raw in ('{', '}')))
        if len(tokens) > MAX_TOKENS:
            raise ValueError('Steam KeyValues token limit')
    if at != len(text):
        raise ValueError('Malformed Steam KeyValues')
    index = 0

    def block(path=(), depth=0):
        nonlocal index, found_root, insecure
        if depth > 64:
            raise ValueError('Steam KeyValues nesting limit')
        while index < len(tokens):
            key, structural = tokens[index]
            index += 1
            if structural:
                if key == '}' and depth:
                    return
                raise ValueError('Malformed Steam KeyValues key')
            if index >= len(tokens):
                raise ValueError('Missing Steam KeyValues value')
            value, structural = tokens[index]
            index += 1
            current = (*path, key.casefold())
            if structural:
                if value != '{' or current == _TARGET:
                    raise ValueError('Malformed Steam KeyValues value')
                if current == (_TARGET[0],):
                    found_root = True
                block(current, depth + 1)
            elif current == _TARGET:
                insecure = insecure or bool(_FLAG.search(value))
            elif current == _TARGET[:len(current)]:
                raise ValueError('Malformed Steam KeyValues target subtree')
        if depth:
            raise ValueError('Unclosed Steam KeyValues block')

    block()
    if not found_root:
        raise ValueError('Unknown Steam KeyValues root')
    return insecure


def _stamp(path):
    info = path.stat()
    return (str(path), info.st_dev, info.st_ino, info.st_mtime_ns,
            info.st_ctime_ns, info.st_size)


def _read_config(path):
    """Cache only successful flag checks; paths stay internal, not in results."""
    stamp = _stamp(path)
    if stamp[-1] > MAX_CONFIG_BYTES:
        raise ValueError('Steam KeyValues size limit')
    with _CACHE_LOCK:
        if stamp in _CACHE:
            result = _CACHE.pop(stamp)
            _CACHE[stamp] = result
            return result
    with path.open('rb') as stream:
        content = stream.read(MAX_CONFIG_BYTES + 1)
    if len(content) > MAX_CONFIG_BYTES or _stamp(path) != stamp:
        raise ValueError('Steam KeyValues changed during read')
    result = _has_insecure(content.decode('utf-8-sig'))
    with _CACHE_LOCK:
        # Discard superseded file versions as well as bounding different files.
        for old in tuple(_CACHE):
            if old[0] == stamp[0]:
                _CACHE.pop(old)
        _CACHE[stamp] = result
        while len(_CACHE) > MAX_CACHE_FILES:
            _CACHE.popitem(last=False)
    return result


def launch_options_status(steam_exe: str):
    """Inspect only the chosen Steam installation's local CS2 settings.

    ``checked=False`` is an unknown state, not a declaration that matchmaking
    is safe. No Steam settings, Career data, or process state are changed.
    """
    unknown = dict(checked=False, insecure=False, reason=UNCHECKED_REASON)
    if not isinstance(steam_exe, str) or not steam_exe.strip():
        return unknown
    try:
        exe = Path(steam_exe.strip().strip('"')).resolve(strict=True)
        if exe.name.casefold() != 'steam.exe' or not exe.is_file():
            return unknown
        userdata = (exe.parent / 'userdata').resolve(strict=True)
        if not userdata.is_dir():
            return unknown
        accounts = [entry for entry in userdata.iterdir()
                    if entry.name.isascii() and entry.name.isdigit()]
    except (OSError, ValueError, RuntimeError):
        return unknown
    checked, insecure, read_count = True, False, 0
    for account in accounts:
        try:
            if not S_ISDIR(account.stat().st_mode):
                continue
            candidate = account / 'config' / 'localconfig.vdf'
            # Do not follow an account/config junction to unrelated directories.
            path = candidate.resolve(strict=True)
            if not path.is_relative_to(userdata):
                checked = False
                continue
            read_count += 1
            insecure = _read_config(path) or insecure
        except FileNotFoundError:
            continue  # No persistent options are stored in an absent file.
        except (OSError, ValueError, UnicodeError, RuntimeError):
            checked = False
    checked = checked and read_count > 0
    return dict(checked=checked, insecure=insecure,
                reason=INSECURE_REASON if insecure else '' if checked else UNCHECKED_REASON)
