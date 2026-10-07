"""Custom club marks: immutable PNGs committed with the owning team and receipt.

The client decodes/resizes the user's local image. Only bounded, static RGBA PNGs
cross the API; filenames are content hashes, never user paths or team names.
Old images remain available to older manual slots; reads do not generate files.
"""
import base64
import binascii
import hashlib
import re
import struct
import zlib

from .. import paths
from ..storage import transaction as tx

PNG = b'\x89PNG\r\n\x1a\n'
LIMIT = 1200 * 1024


def validate_png(blob, *, avatar=False):
    limit = 16384 if avatar else LIMIT
    if not isinstance(blob, bytes) or not 32 <= len(blob) <= limit or not blob.startswith(PNG):
        raise ValueError('请选择有效的静态 PNG 图片。')
    offset, chunks, compressed, size = 8, [], bytearray(), None
    while offset < len(blob):
        if offset + 12 > len(blob): raise ValueError('PNG 数据不完整。')
        length = struct.unpack_from('>I', blob, offset)[0]
        tag = blob[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(blob): raise ValueError('PNG 数据不完整。')
        data = blob[offset + 8:end - 4]
        if binascii.crc32(tag + data) & 0xffffffff != struct.unpack_from('>I', blob, end - 4)[0]:
            raise ValueError('PNG 校验失败。')
        if not chunks and tag != b'IHDR': raise ValueError('PNG 缺少尺寸。')
        if tag == b'IHDR':
            if chunks or length != 13: raise ValueError('PNG 尺寸无效。')
            width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', data)
            if (not 1 <= width <= 512 or not 1 <= height <= 512 or
                    (avatar and (width, height) != (64, 64)) or
                    (depth, color, compression, filtering, interlace) != (8, 6, 0, 0, 0)):
                raise ValueError('请重新选择图片，由程序生成队标尺寸。')
            size = width, height
        elif tag == b'IDAT':
            if b'IEND' in chunks or (b'IDAT' in chunks and chunks[-1] != b'IDAT'):
                raise ValueError('PNG 图像块顺序无效。')
            compressed.extend(data)
        elif tag == b'IEND':
            if length or end != len(blob) or not compressed: raise ValueError('PNG 结尾无效。')
        elif tag not in (b'sRGB', b'gAMA', b'pHYs'):
            raise ValueError('只接受程序生成的静态 PNG，不支持动画或附加内容。')
        chunks.append(tag)
        offset = end
    if not size or not chunks or chunks[-1] != b'IEND': raise ValueError('PNG 数据不完整。')
    width, height = size
    expected = height * (1 + width * 4)
    try:
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(bytes(compressed), expected + 1)
        if (len(pixels) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail
                or any(pixels[n] > 4 for n in range(0, expected, width * 4 + 1))):
            raise ValueError('PNG 像素数据无效。')
    except zlib.error as exc:
        raise ValueError('PNG 像素数据无效。') from exc
    return blob


def decode(value, *, avatar=False):
    if not isinstance(value, str) or len(value) > (16384 if avatar else LIMIT) * 4 // 3 + 4:
        raise ValueError('队标图片太大，请重新选择。')
    try:
        blob = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError('队标图片编码无效。') from exc
    return validate_png(blob, avatar=avatar)


def mark_path(team, kind='panel'):
    marks = team.get('career_marks') or {}
    checksum = marks.get(kind, '') if isinstance(marks, dict) else ''
    if not isinstance(checksum, str) or not re.fullmatch('[0-9a-f]{64}', checksum): return None
    target = paths.save_root() / ('team-mark-' + checksum + '.png')
    if target.is_symlink(): return None
    try:
        blob = tx.read_bytes(target, max_bytes=(16384 if kind == 'avatar' else LIMIT) + 1)
        validate_png(blob, avatar=kind == 'avatar')
        return target if hashlib.sha256(blob).hexdigest() == checksum else None
    except (ValueError, OSError):
        return None


def context(state):
    c = state.career
    team = c.my_team(state.season.teams) or {}
    allowed = bool(team and c.mode == 'create' and not c.unsigned and not c.personal_transfers.get('player_only'))
    return dict(allowed=allowed, team_id=team.get('id', ''),
        panel_path=str(mark_path(team) or ''), avatar_path=str(mark_path(team, 'avatar') or ''),
        reason='' if allowed else '自建战队可以在这里设置队标。')


def command(state, body):
    if not context(state)['allowed']: raise ValueError('只能修改自己创建并管理的战队队标。')
    team = state.career.my_team(state.season.teams)
    if body.get('team_id') != team['id']: raise ValueError('当前队伍已变化，请刷新后重新选择图片。')
    kind = body.get('kind')
    if kind not in ('club', 'avatar'): raise ValueError('请选择队标或 CS2 头像。')
    # Validate everything before enqueueing either image or changing the team.
    images = {'avatar':decode(body.get('avatar_png'), avatar=True)}
    if kind == 'club': images['panel'] = decode(body.get('panel_png'))
    marks = dict(team.get('career_marks') or {})
    for slot, blob in images.items():
        checksum = hashlib.sha256(blob).hexdigest()
        path = paths.save_root() / ('team-mark-' + checksum + '.png')
        if path.is_symlink(): raise ValueError('队标保存位置异常，请检查存档目录。')
        tx.save(path, lambda payload=blob: payload)
        marks[slot] = checksum
    team['career_marks'] = marks
    return dict(reason='队标已保存，CS2 顶部与计分板头像将在下一次开赛时同步。', team_id=team['id'])
