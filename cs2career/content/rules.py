"""Versioned, JSON-only extension contracts. No eval, imports or command strings.

`events` remains tournament calendars; `incidents` is career decisions and
`match_chat` is cosmetic CS2 dialogue. Unknown fields fail closed to catch typos.
"""
import math
import re

ID = re.compile(r'^[a-zA-Z0-9_.-]{1,96}$')
CHAT_NUMBERS = {'round', 'score_for', 'score_against', 'lead', 'kills', 'deaths',
                'assists', 'damage', 'round_kills', 'win_streak', 'loss_streak'}
CHAT_STRINGS = {'result', 'map', 'player_id', 'speaker_id', 'team_id'}
PLACEHOLDERS = CHAT_NUMBERS | CHAT_STRINGS | {'player', 'speaker', 'team', 'opponent'}
INCIDENT_TRIGGERS = {'day', 'before_match', 'after_series', 'event_started', 'coach_absent'}
INCIDENT_TRIGGERS |= {'transfer_offer_received', 'transfer_application_success', 'transfer_application_failed',
                     'transfer_stayed', 'transfer_departed', 'transfer_joined', 'transfer_former_team'}
TRANSFER_FIELDS = {'old_team_id', 'new_team_id', 'transfer_role', 'transfer_source', 'farewell_choice'}
BUILTINS = {'fix_offer', 'major_coach', 'fix_probe', 'fix_ban', 'teammate_birthday',
            'loan_default', 'loan_flee_ban'}


def number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def text(value, maximum=600, placeholders=None):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('文本为空、类型错误或过长')
    if any(ord(c) < 32 and c != '\n' for c in value):
        raise ValueError('文本不能含控制字符')
    if placeholders is not None:
        # Only flat named tokens, never format expressions / object traversal.
        rest = re.sub(r'\{([a-z_]+)\}', lambda m: '' if m[1] in placeholders else m[0], value)
        if '{' in rest or '}' in rest:
            raise ValueError('未知占位符；只支持文档列出的 {字段名}')


def keys(row, allowed):
    if not isinstance(row, dict) or set(row) - set(allowed):
        raise ValueError('对象有未知字段或类型错误')


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('id 只能使用字母、数字、点、横线和下划线')


def validate_chat(row):
    keys(row, {'id', 'when', 'speaker', 'speaker_id', 'channel', 'color', 'text',
               'conditions', 'probability', 'cooldown_rounds', 'max_per_match', 'priority'})
    identifier(row.get('id'))
    if row.get('when') != 'round_end' or row.get('speaker', 'teammate') not in {'teammate', 'opponent', 'coach'}:
        raise ValueError('聊天 when 必须为 round_end；speaker 为 teammate/opponent/coach')
    if row.get('channel', 'team') not in {'team', 'all'} or row.get('color', 'default') not in {'default', 'green', 'blue', 'gold'}:
        raise ValueError('无效聊天频道或颜色')
    if 'speaker_id' in row:
        identifier(row['speaker_id'])
        if row.get('speaker') == 'coach':
            raise ValueError('教练不使用选手 speaker_id')
    if row.get('speaker') == 'opponent' and row.get('channel', 'team') != 'all':
        raise ValueError('对手只能使用 all 频道')
    lines = row.get('text')
    if not isinstance(lines, list) or not 1 <= len(lines) <= 20:
        raise ValueError('text 必须是 1—20 条台词数组')
    for line in lines:
        text(line, 180, PLACEHOLDERS)
    for key, default, lo, hi in [('probability', 1, 0, 1), ('cooldown_rounds', 4, 1, 100),
                                  ('max_per_match', 2, 1, 200), ('priority', 0, -100, 100)]:
        value = row.get(key, default)
        if not number(value, lo, hi) or (key != 'probability' and type(value) is not int):
            raise ValueError('无效聊天参数：' + key)
    conditions = row.get('conditions', {})
    keys(conditions, CHAT_NUMBERS | CHAT_STRINGS)
    for key, value in conditions.items():
        if key in CHAT_NUMBERS:
            keys(value, {'min', 'max'})
            if not value or any(not number(v, -100000, 100000) for v in value.values()) or value.get('min', -100000) > value.get('max', 100000):
                raise ValueError('无效数值条件：' + key)
        else:
            text(value, 120)


def validate_scene(row):
    keys(row, {'id', 'when', 'conditions', 'probability', 'cooldown_rounds',
               'max_per_match', 'priority', 'sequence'})
    common = {k: v for k, v in row.items() if k != 'sequence'}
    validate_chat(dict(common, speaker='coach', text=['场内剧情']))
    if 'speaker_id' in row.get('conditions', {}):
        raise ValueError('剧情没有单一说话者；请在 sequence 内指定 speaker_id')
    sequence = row.get('sequence')
    if not isinstance(sequence, list) or not 1 <= len(sequence) <= 6:
        raise ValueError('sequence 必须有 1—6 句有序台词')
    for step in sequence:
        keys(step, {'speaker', 'speaker_id', 'channel', 'color', 'text', 'delay_seconds'})
        text(step.get('text'), 180, PLACEHOLDERS)
        if not number(step.get('delay_seconds', 2), 0.5, 3):
            raise ValueError('delay_seconds 必须在 0.5—3 秒之间')
        speech = {k: v for k, v in step.items() if k not in {'delay_seconds', 'text'}}
        validate_chat(dict(speech, id='step', when='round_end', text=[step['text']]))


def validate_effects(effects):
    if not isinstance(effects, list) or len(effects) > 10:
        raise ValueError('effects 必须为至多 10 项的数组')
    for effect in effects:
        keys(effect, {'type', 'amount', 'key', 'value'})
        kind = effect.get('type')
        if kind == 'flag':
            if set(effect) != {'type', 'key', 'value'}:
                raise ValueError('flag 需要 key/value')
            identifier(effect.get('key'))
            if type(effect.get('value')) is not bool:
                raise ValueError('flag value 必须是布尔值')
        elif kind in {'mentality', 'pocket_money', 'club_money', 'skill_points', 'competition_pause'}:
            limit = {'mentality': 20, 'skill_points': 100, 'competition_pause': 365}.get(kind, 100000)
            minimum = 0 if kind in {'skill_points', 'competition_pause'} else -limit
            if set(effect) != {'type', 'amount'} or type(effect.get('amount')) is not int or not number(effect['amount'], minimum, limit):
                raise ValueError('无效或超限的效果数值')
        else:
            raise ValueError('未支持的效果；不可运行脚本或修改任意存档字段')
    for kind, limit in [('mentality', 20), ('pocket_money', 100000), ('club_money', 100000), ('skill_points', 100), ('competition_pause', 365)]:
        if sum(abs(e['amount']) for e in effects if e['type'] == kind) > limit:
            raise ValueError('累计效果超出安全范围：' + kind)
    if sum(e['type'] == 'competition_pause' for e in effects) > 1:
        raise ValueError('一个选项只能有一项暂停参赛效果')


def validate_incident(row):
    keys(row, {'id', 'when', 'title', 'text', 'choices', 'conditions', 'probability', 'cooldown_days', 'max_per_career'})
    identifier(row.get('id'))
    if row.get('when') not in INCIDENT_TRIGGERS:
        raise ValueError('未知生涯事件触发点')
    text(row.get('title'), 100)
    text(row.get('text'), 3000)
    choices = row.get('choices')
    if not isinstance(choices, list) or not 1 <= len(choices) <= 4:
        raise ValueError('生涯事件需要 1—4 个选项')
    ids = set()
    for choice in choices:
        keys(choice, {'id', 'label', 'effects'})
        identifier(choice.get('id'))
        if choice['id'] in ids:
            raise ValueError('重复选项 id')
        ids.add(choice['id'])
        text(choice.get('label'), 100)
        validate_effects(choice.get('effects', []))
    if not any(not any((e['type'] in {'club_money', 'pocket_money'} and e['amount'] < 0)
                       or (e['type'] == 'competition_pause' and e['amount'] > 0)
                       for e in c.get('effects', [])) for c in choices):
        raise ValueError('至少需要一个不扣钱且不要求暂停参赛的选项，避免正在比赛或资金不足时无法继续')
    conditions = row.get('conditions', {})
    keys(conditions, {'mode', 'origin', 'event_type', 'flags'} | TRANSFER_FIELDS)
    for key, value in conditions.items():
        if key == 'flags':
            if not isinstance(value, dict) or len(value) > 20:
                raise ValueError('flags 必须是对象')
            for flag, expected in value.items():
                identifier(flag)
                if type(expected) is not bool:
                    raise ValueError('flag 条件必须是布尔值')
        else:
            text(value, 80)
    for key, default, lo, hi in [('probability', 1, 0, 1), ('cooldown_days', 30, 1, 3650), ('max_per_career', 1, 1, 100)]:
        value = row.get(key, default)
        if not number(value, lo, hi) or (key != 'probability' and type(value) is not int):
            raise ValueError('无效事件参数：' + key)


def validate_payload(kind, raw):
    collection = 'rules' if kind == 'match_chat' else 'incidents'
    keys(raw, {'schema_version', collection} | ({'overrides','arc_overrides'} if kind == 'incidents' else {'scenes'}))
    if type(raw.get('schema_version')) is not int or raw['schema_version'] != 1:
        raise ValueError('内容 schema_version 必须为 1')
    if kind == 'incidents' and 'arc_overrides' in raw:
        from ..career.arcs import validate_overrides
        validate_overrides(raw['arc_overrides'])
    rows = raw.get(collection, [])
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError('每文件最多 100 条规则')
    seen = set()
    for row in rows:
        (validate_chat if kind == 'match_chat' else validate_incident)(row)
        if row['id'] in seen:
            raise ValueError('重复规则 id')
        seen.add(row['id'])
    if kind == 'match_chat':
        scenes = raw.get('scenes', [])
        if not isinstance(scenes, list) or len(scenes) > 50:
            raise ValueError('scenes 必须为至多 50 个剧情的数组')
        for row in scenes:
            validate_scene(row)
            if row['id'] in seen:
                raise ValueError('剧情和普通规则不能使用重复 id')
            seen.add(row['id'])
    overrides = raw.get('overrides', [])
    if not isinstance(overrides, list) or len(overrides) > len(BUILTINS):
        raise ValueError('overrides 必须为有限数组')
    seen = set()
    for row in overrides:
        keys(row, {'when', 'title', 'text', 'labels'})
        if row.get('when') not in BUILTINS or row['when'] in seen:
            raise ValueError('未知或重复的内置事件覆盖目标')
        seen.add(row['when'])
        for key in ('title', 'text'):
            if key in row:
                text(row[key], 100 if key == 'title' else 3000)
        labels = row.get('labels', {})
        keys(labels, {'accept', 'refuse', 'wish', 'train', 'flee'})
        for label in labels.values():
            text(label, 100)
