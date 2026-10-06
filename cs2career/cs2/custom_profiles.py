"""Read a user's BotProfile templates without modifying their source VPK.

Only botprofile.db and the existing Bot behavior resource paths are consumed.
Player names are replaced by the current match's identities, not imported.
"""
from pathlib import Path
import hashlib
import re
import struct
from zlib import crc32

from . import bot_behavior

MODEL = 'custom_botprofile_templates_v1'
MAX_FILE = 16 * 1024 * 1024


def _read_blob(path: Path) -> bytes:
    path = Path(path)
    if not path.is_file() or not 12 <= path.stat().st_size <= MAX_FILE:
        raise ValueError('请选择有效的 BotProfile VPK 文件（最大 16 MB）。')
    with path.open('rb') as stream:
        blob = stream.read(MAX_FILE + 1)
    if not 12 <= len(blob) <= MAX_FILE:
        raise ValueError('BotProfile VPK 大小无效。')
    return blob


def read_resources(path: Path, *, blob: bytes | None = None) -> dict[str, bytes]:
    blob = _read_blob(path) if blob is None else blob
    signature, version, tree_size = struct.unpack_from('<III', blob)
    if signature != 0x55AA1234 or version not in (1, 2):
        raise ValueError('BotProfile 文件不是支持的 VPK v1/v2。')
    head = 12 if version == 1 else 28
    end = head + tree_size
    if end > len(blob) or tree_size < 3:
        raise ValueError('VPK 目录不完整。')
    data_end = end + struct.unpack_from('<I', blob, 12)[0] if version == 2 else len(blob)
    if data_end > len(blob):
        raise ValueError('VPK 数据段不完整。')
    cursor, files = head, {}

    def token():
        nonlocal cursor
        stop = blob.find(b'\0', cursor, end)
        if stop < 0:
            raise ValueError('VPK 目录字符串不完整。')
        result = blob[cursor:stop].decode('utf-8')
        cursor = stop + 1
        return result

    while ext := token():
        while folder := token():
            while name := token():
                if cursor + 18 > end:
                    raise ValueError('VPK 条目不完整。')
                crc, preload, archive, offset, size, terminator = struct.unpack_from('<IHHIIH', blob, cursor)
                cursor += 18
                if terminator != 0xFFFF or cursor + preload > end:
                    raise ValueError('VPK 条目无效。')
                prefix = blob[cursor:cursor + preload]
                cursor += preload
                key = ((folder + '/') if folder != ' ' else '') + name + '.' + ext
                if key not in ('botprofile.db', *bot_behavior.RESOURCE_PATHS):
                    continue
                if key in files or (size and archive != 0x7FFF):
                    raise ValueError('BotProfile VPK 含重复条目或需要外部分卷；请使用单文件 VPK。')
                limit = 2 * 1024 * 1024 if key == 'botprofile.db' else 64 * 1024
                if size + preload > limit or end + offset + size > data_end:
                    raise ValueError('VPK 的 BotProfile / 行为脚本条目不完整或过大。')
                payload = prefix + blob[end + offset:end + offset + size]
                if crc32(payload) != crc:
                    raise ValueError('VPK 条目校验失败：' + key)
                files[key] = payload
    if 'botprofile.db' not in files:
        raise ValueError('VPK 内没有根目录 botprofile.db。')
    return files


def load(path: str | Path) -> dict:
    path = Path(path)
    blob = _read_blob(path)
    resources = read_resources(path, blob=blob)
    try:
        source = resources.pop('botprofile.db').decode('utf-8-sig')
    except UnicodeError as exc:
        raise ValueError('botprofile.db 需要使用 UTF-8 编码。') from exc
    blocks, header, body = {}, None, []
    for raw in source.splitlines():
        line = raw.split('//', 1)[0].strip()
        if not line:
            continue
        if header is None:
            header, body = line, []
        elif line.casefold() == 'end':
            name = 'Default' if header == 'Default' else header[9:] if header.startswith('Template ') else None
            if name is not None:
                if not re.fullmatch(r'[A-Za-z0-9_]+', name) or name in blocks or name == 'C2CMatchBase':
                    raise ValueError('BotProfile 模板名称无效或重复：' + name)
                blocks[name] = '\n'.join(body)
            header = None
        else:
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*\s*=\s*[^\x00-\x1f{};]+', line):
                raise ValueError('BotProfile 参数格式无效：' + line[:80])
            body.append('    ' + line)
    if header is not None or 'Default' not in blocks:
        raise ValueError('botprofile.db 缺少完整的 Default / End 模板。')
    # Retain template text, order and repeated WeaponPreference entries. Do
    # not adapt weapons, add career aim parameters or copy the user's roster.
    text = '\n\n'.join(('Default' if k == 'Default' else 'Template ' + k) + '\n' + v + '\nEnd'
                       for k, v in blocks.items()) + '\n\nTemplate C2CMatchBase\nEnd\n\n'
    return dict(text=text, templates=set(blocks) - {'Default'}, resources=resources,
                source_hash=hashlib.sha256(blob).hexdigest(),
                template_hash=hashlib.sha256(text.encode()).hexdigest())


def chain(bot: dict, templates: set[str]) -> str:
    from .profiles import ROLE_STYLE
    weapon, personality = ROLE_STYLE.get(bot['role'], ROLE_STYLE['rifle'])
    selected = [name for name in (bot['tier'], weapon, personality) if name in templates]
    return '+'.join(selected or ['C2CMatchBase'])
