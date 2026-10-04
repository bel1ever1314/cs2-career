"""Read-only upstream tuning, stripped of player names and fixed rosters.

The career layer chooses an anonymous tier. This module supplies that tier's
original tuning; it does not add difficulty points to career ability.
"""
from functools import lru_cache
import hashlib
import json
import math
import re

from ..paths import data_file

MODEL = 'bot_improver_career_tuned_v2'
LEVELS = ('Low', 'Medium', 'High')
# Keep the upstream extracts unchanged. This affects only our generated match
# database, on all difficulties and roles; BotBuy enforces the same policy for
# its purchases. It does not restrict a human's inventory or dropped weapons.
EXCLUDED_PURCHASE_PREFERENCES = frozenset(('aug', 'scar20', 'g3sg1'))
# These are the two weapon templates assigned to Career positions. Promote
# existing full-buy rifles before budget rifles, without making the latter
# unavailable on an eco. The designated sniper still considers AWP first.
_MAIN_RIFLE_ORDER = ('ak47', 'm4a1_silencer', 'm4a1', 'sg556', 'famas', 'galilar')
_ROLE_PURCHASE_ORDER = {'RiflePro': _MAIN_RIFLE_ORDER,
                        'SniperPro': ('awp',) + _MAIN_RIFLE_ORDER}
_WEAPON_LINE = re.compile(r'(?mi)^[ \t]*WeaponPreference[ \t]*=[ \t]*(\w+)'
                          r'[^\r\n]*(?:\r?\n|$)')
PARAMETER_KEYS = (
    'Skill', 'ReactionTime', 'AttackDelay', 'AimFocusInitial', 'AimFocusDecay',
    'AimFocusOffsetScale', 'AimfocusInterval', 'LookAngleMaxAccelNormal',
    'LookAngleStiffnessNormal', 'LookAngleDampingNormal',
    'LookAngleMaxAccelAttacking', 'LookAngleStiffnessAttacking', 'LookAngleDampingAttacking',
)


def _prioritize_role_rifles(text: str) -> str:
    """Reorder existing preference rows, preserving every other tuning row."""
    def reorder(block):
        body = block['body']
        rows = list(_WEAPON_LINE.finditer(body))
        priority = {weapon: index for index, weapon in enumerate(_ROLE_PURCHASE_ORDER[block['name']])}
        ordered = sorted(rows, key=lambda row: priority.get(row[1].casefold(), len(priority)))
        replacements = iter(row[0] for row in ordered)
        body = _WEAPON_LINE.sub(lambda _row: next(replacements), body)
        return block['header'] + body + block['end']

    return re.sub(r'(?ms)(?P<header>^Template (?P<name>RiflePro|SniperPro)\b[^\r\n]*\r?\n)'
                  r'(?P<body>.*?)(?P<end>^End[^\r\n]*(?:\r?\n|$))', reorder, text)


@lru_cache(maxsize=3)
def preset(level: str) -> dict:
    if level not in LEVELS:
        raise ValueError(f'未知难度：{level}')
    meta = json.loads(data_file('botprofile_presets/presets.json').read_text(encoding='utf-8'))
    if meta.get('schema_version') != 1 or meta.get('model') != MODEL:
        raise ValueError('Bot Improver 预设版本不支持')
    # Fixed allowlisted paths, never a path supplied by an extension or match.
    text = data_file(f'botprofile_presets/{level}.db').read_text(encoding='utf-8')
    # Upstream has a few difficulty-specific Rank reaction overrides. Keep the
    # archived extracts intact, but use ONE canonical (Medium) set of tiers for
    # every level so only Default changes when selecting a difficulty.
    canonical = data_file('botprofile_presets/Medium.db').read_text(encoding='utf-8')
    default = re.search(r'(?ms)^Default\r?\n.*?^End\s*$', text)
    if default is None:
        raise ValueError(f'预设 {level} 缺少 Default')
    templates = re.findall(r'(?ms)^Template [^\r\n]+\r?\n.*?^End\s*$', canonical)
    text = ('// Base: ' + level + '; shared career tiers: Medium templates only.\n'
            + default[0].rstrip() + '\n\n' + '\n\n'.join(t.rstrip() for t in templates) + '\n')
    text = re.sub(
        r'(?mi)^\s*WeaponPreference\s*=\s*(' + '|'.join(sorted(EXCLUDED_PURCHASE_PREFERENCES))
        + r')\s*(?://[^\r\n]*)?\r?\n',
        '', text,
    )
    text = _prioritize_role_rifles(text)
    blocks = {}
    for block in re.finditer(r'(?ms)^(Default|Template [^\r\n]+)\r?\n(.*?)^End\s*$', text):
        name = block[1].split('//')[0].strip().removeprefix('Template ')
        if name in blocks:
            raise ValueError(f'重复 Bot 模板：{name}')
        values = {}
        for key, raw in re.findall(r'(?m)^\s*(\w+)\s*=\s*([^\r\n]+)', block[2]):
            if key not in PARAMETER_KEYS:
                continue
            token = raw.split('//')[0].strip()
            if key.startswith('LookAngleMaxAccel') and token == meta['compatibility']['raw_acceleration_token']:
                values[key] = token
                continue
            value = float(token)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f'预设 {level}/{name}/{key} 含非法值')
            values[key] = value
        blocks[name] = values
    if 'Default' not in blocks or set(PARAMETER_KEYS) - blocks['Default'].keys():
        raise ValueError(f'预设 {level} 缺少基础参数')
    return dict(text=text, blocks=blocks, medium_aim=meta['medium_aim'],
                raw_acceleration=meta['compatibility']['raw_acceleration_token'],
                source_hash=meta['presets'][level]['source_vpk_sha256'],
                template_hash=hashlib.sha256(text.encode()).hexdigest())


def aim_band(level: str, tier: str, strength: float) -> str:
    if level != 'Medium':
        return 'Default'
    if tier == 'ProTop':
        return 'ProTop98' if strength >= 98 else 'ProTop95' if strength >= 95 else 'ProTop90'
    return tier if tier in preset(level)['medium_aim'] else 'Default'


def parameters(level: str, tier: str, strength: float) -> dict:
    source = preset(level)
    if tier not in source['blocks']:
        raise ValueError(f'预设 {level} 不含模板 {tier}')
    values = {**source['blocks']['Default'], **source['blocks'][tier]}
    # Rank/pro selects personal behavior on all levels. Medium additionally
    # reproduces anonymous per-tier aim tuning; Low/High keep global aiming.
    values.update({key: value for key, value in source['blocks']['Default'].items()
                   if key.startswith('LookAngle')})
    if level == 'Medium':
        values.update(source['medium_aim'].get(aim_band(level, tier, strength), {}))
    for key, value in values.items():
        if key.startswith('LookAngleMaxAccel') and value == source['raw_acceleration']:
            continue  # exact trusted upstream text, NOT an arbitrary injected token
        if key not in PARAMETER_KEYS or not math.isfinite(float(value)) or value < 0:
            raise ValueError(f'预设参数无效：{key}')
        if key.startswith('LookAngleMaxAccel') and value > 20000:
            raise ValueError('瞄准加速度超出兼容上限')
    values['Skill'] = int(values['Skill'])
    return values
