"""Add Career mounts to the installed Valve config, never reuse an old full GI."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile

MOUNTS = ('csgo/overrides/botprofile.vpk', 'csgo/addons/metamod')
_TOKEN = re.compile(r'//[^\r\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[{}]|[^\s{}"]+')


def _structure(text: str):
    """Keep token offsets so unrelated Valve settings/comments remain untouched."""
    tokens = []
    end = 0
    for match in _TOKEN.finditer(text):
        if text[end:match.start()].strip():
            raise ValueError('gameinfo.gi 格式不完整，请在 Steam 验证游戏文件。')
        end = match.end()
        raw = match.group()
        if raw.startswith(('//', '/*')):
            continue
        value = raw[1:-1] if raw.startswith('"') else raw
        tokens.append((value, match.start(), match.end()))
    if text[end:].strip():
        raise ValueError('gameinfo.gi 格式不完整，请在 Steam 验证游戏文件。')
    stack = []
    blocks = []
    layers = []
    for index, (value, start, stop) in enumerate(tokens):
        if value == '{':
            if index == 0 or tokens[index-1][0] in ('{', '}'):
                raise ValueError('gameinfo.gi 的配置块无效。')
            stack.append((tokens[index-1][0].casefold(), index))
        elif value == '}':
            if not stack:
                raise ValueError('gameinfo.gi 的括号不完整。')
            if tuple(key for key, _ in stack) == ('gameinfo', 'filesystem', 'searchpaths'):
                blocks.append((stack[-1][1], index))
            stack.pop()
        elif tuple(key for key, _ in stack) == ('gameinfo',) and value.casefold() == 'layeredonmod':
            if index + 1 >= len(tokens) or tokens[index+1][0] in ('{', '}'):
                raise ValueError('gameinfo.gi 的继承目录无效。')
            layers.append(tokens[index+1][0])
    if stack or len(blocks) != 1:
        raise ValueError('gameinfo.gi 缺少唯一的 FileSystem/SearchPaths，请在 Steam 验证游戏文件。')
    return tokens, blocks[0], layers


def patched_gameinfo(text: str) -> str:
    tokens, (opening, closing), _ = _structure(text)
    entries = tokens[opening+1:closing]
    if len(entries) % 2 or any(t[0] in ('{', '}') for t in entries):
        raise ValueError('gameinfo.gi 的 SearchPaths 格式无效。')
    pairs = list(zip(entries[::2], entries[1::2]))
    existing = {value[0].replace('\\', '/').casefold().rstrip('/')
                for key, value in pairs if key[0].casefold() == 'game'}
    missing = [path for path in MOUNTS if path not in existing]
    if not missing:
        return text
    first_game = next((key for key, _ in pairs if key[0].casefold() == 'game'), None)
    if first_game is None:
        raise ValueError('gameinfo.gi 的 SearchPaths 缺少 Game 项。')
    newline = '\r\n' if '\r\n' in text else '\n'
    at = first_game[1]
    prefix = text[text.rfind('\n', 0, at)+1:at]
    indent = prefix if not prefix.strip() else '\t\t\t'
    insertion = (newline + indent).join('Game\t' + path for path in missing) + newline + indent
    return text[:at] + insertion + text[at:]


def ensure_gameinfo_mounts(csgo: Path) -> bool:
    path = csgo / 'gameinfo.gi'
    if not path.is_file():
        raise FileNotFoundError('缺少 CS2 gameinfo.gi，请在 Steam 验证游戏文件后重试。')
    before = path.read_bytes()
    if len(before) > 1024 * 1024:
        raise ValueError('gameinfo.gi 大小异常，未修改。')
    text = before.decode('utf-8-sig')
    _, _, layers = _structure(text)
    for layer in layers:
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', layer) or not (csgo.parent / layer / 'gameinfo.gi').is_file():
            raise ValueError(f'CS2 配置仍引用已移除的 {layer}/gameinfo.gi；请恢复当前游戏版本的配置，不能使用旧人机包的整份文件。')
    patched = patched_gameinfo(text)
    after = (b'\xef\xbb\xbf' if before.startswith(b'\xef\xbb\xbf') else b'') + patched.encode('utf-8')
    if before == after:
        return False
    stamp = hashlib.sha256(before).hexdigest()[:12]
    backup = path.with_name(path.name + '.career-backup.' + stamp)
    if not backup.exists():
        shutil.copy2(path, backup)
    if backup.read_bytes() != before:
        raise OSError('gameinfo.gi 备份核对失败，未替换。')
    handle, pending = tempfile.mkstemp(prefix='.career-gameinfo-', suffix='.tmp', dir=csgo)
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(after)
            stream.flush()
            os.fsync(stream.fileno())
        if path.read_bytes() != before:
            raise OSError('gameinfo.gi 在准备过程中发生变化，未替换。')
        os.replace(pending, path)
    finally:
        Path(pending).unlink(missing_ok=True)
    return True
