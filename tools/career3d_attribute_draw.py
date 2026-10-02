"""Durable team draws: one chosen attribute per complete five-player roster.

Opening-era game VRS affects rarity only, never the frozen world values.
Legacy attribute drafts and receipts remain recoverable in the same store.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import threading
from uuid import uuid4

SCHEMA_VERSION = 2
ORIGIN_ID = 'attribute_draw'
MAX_DRAWS = 10
METADATA_NAME = '.career3d-start.json'
LEGACY_VALUE_POLICY = 'existing_world_axes_not_opponent_calibrated'
VALUE_POLICY = 'calibrated_world_axes_v1'
_VALUE_POLICIES = frozenset((LEGACY_VALUE_POLICY, VALUE_POLICY))
SELECTION_SCOPE = 'one_attribute_per_team_draw'
_LOCK = threading.RLock()
_RANDOM = secrets.SystemRandom()
# Band probability, not points multiplied by an arbitrary individual modifier.
# Percentiles are in the eligible roster pool sorted by opening game VRS.
TEAM_BANDS = (
    {'id': 'legendary', 'name': '传奇', 'color': 'e5b85b', 'max_percentile': .10, 'probability': .03},
    {'id': 'epic', 'name': '史诗', 'color': 'b889eb', 'max_percentile': .25, 'probability': .08},
    {'id': 'rare', 'name': '稀有', 'color': '63a8f2', 'max_percentile': .45, 'probability': .16},
    {'id': 'uncommon', 'name': '优秀', 'color': '71c990', 'max_percentile': .70, 'probability': .28},
    {'id': 'common', 'name': '普通', 'color': 'b8c3cc', 'max_percentile': 1.0, 'probability': .45},
)
ATTRIBUTE_BANDS = (
    {'id': 'common', 'name': '普通', 'color': 'b8c3cc', 'min_value': 1},
    {'id': 'uncommon', 'name': '优秀', 'color': '71c990', 'min_value': 50},
    {'id': 'rare', 'name': '稀有', 'color': '63a8f2', 'min_value': 65},
    {'id': 'epic', 'name': '史诗', 'color': 'b889eb', 'min_value': 80},
    {'id': 'legendary', 'name': '传奇', 'color': 'e5b85b', 'min_value': 90},
)
_LEGACY_LIMITS = {'easy': 3, 'normal': 2, 'hard': 1}


def _axes():
    from cs2career.world.ability import AXES, AXIS_LABEL
    return AXES, AXIS_LABEL


def _era(value):
    from cs2career.world import ERA_META
    era = str(value or '2026')
    if era not in ERA_META:
        raise ValueError('请选择 2024、2025 或 2026 年代。')
    return era


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def _metadata_path():
    configured = os.environ.get('CS2CAREER_SAVE_DIR', '')
    if not configured or not Path(configured).is_absolute():
        raise ValueError('队伍抽取只允许在已隔离的 3D 演示目录中使用。')
    save = Path(configured).resolve()
    root = save.parent
    project = Path(__file__).resolve().parents[1]
    protected = (project / 'save', project / 'extensions')
    if save.name != 'save' or root == project or any(
            root == p.resolve() or root.is_relative_to(p.resolve()) for p in protected):
        raise ValueError('队伍抽取不能读取或写入正式存档目录。')
    marker = root / '.career3d-demo.json'
    if not marker.is_file():
        raise ValueError('队伍抽取目录缺少 3D 演示隔离标记。')
    if json.loads(marker.read_text('utf-8')).get('kind') != 'cs2career-godot-demo':
        raise ValueError('队伍抽取目录的隔离标记无效。')
    return root / METADATA_NAME


def _empty_store():
    return {'schema_version': SCHEMA_VERSION, 'kind': 'career3d-attribute-draw',
            'drafts': {}, 'active_drafts': {}, 'active_team_drafts': {},
            'receipts': {}, 'create_receipts': {}}


def _legacy_valid(ident, draft):
    axes, _ = _axes()
    difficulty, limit = draft.get('difficulty', 'easy'), draft.get('max_draws', 3)
    if (draft.get('draft_id') != ident or difficulty not in _LEGACY_LIMITS
            or limit != _LEGACY_LIMITS[difficulty]
            or not isinstance(draft.get('axes'), dict) or set(draft['axes']) != set(axes)):
        raise ValueError('旧属性草稿已损坏，原记录没有删除。')
    for row in draft['axes'].values():
        draws = row.get('draws') if isinstance(row, dict) else None
        if not isinstance(draws, list) or len(draws) > limit:
            raise ValueError('旧属性次数记录无效，原记录没有删除。')
        ids = [draw.get('draw_id') for draw in draws if isinstance(draw, dict)]
        if (len(ids) != len(draws) or len(set(ids)) != len(ids)
                or row.get('selected_draw_id') not in (None, *ids)):
            raise ValueError('旧属性选择记录无效，原记录没有删除。')


def _candidate(player, axis, draw):
    value = player['stats'][axis]
    band = next(b for b in reversed(ATTRIBUTE_BANDS) if value >= b['min_value'])
    candidate = {'axis': axis, 'player_id': player['player_id'],
            'source_player_id': player['source_player_id'], 'source_player': player['source_player'],
            'source_team_id': draw['source_team_id'], 'source_team': draw['source_team'],
            'source_era': draw['source_era'], 'draw_id': draw['draw_id'], 'value': value,
            'band': band['id'], 'band_label': band['name'], 'band_color': band['color']}
    if player.get('calibration_model_version'):
        candidate['calibration_model_version'] = player['calibration_model_version']
        candidate['source'] = player.get('source', '')
    return candidate


def _validate_team_draft(ident, draft):
    axes, _ = _axes()
    if (draft.get('draft_id') != ident or draft.get('schema_version') != SCHEMA_VERSION
            or draft.get('max_draws') != MAX_DRAWS or draft.get('selection_scope') != SELECTION_SCOPE
            or draft.get('value_policy') not in _VALUE_POLICIES or not isinstance(draft.get('source_pool'), list)
            or not draft['source_pool'] or draft.get('pool_version') != 'sha256:' + _hash(draft['source_pool'])
            or not isinstance(draft.get('team_draws'), list) or len(draft['team_draws']) > MAX_DRAWS
            or not isinstance(draft.get('axes'), dict) or set(draft['axes']) != set(axes)):
        raise ValueError('队伍抽取草稿已损坏，次数没有重置。')
    pool = {team['team_id']: team for team in draft['source_pool']}
    ids, selections, pending = set(), {}, []
    for index, draw in enumerate(draft['team_draws'], 1):
        source = pool.get(draw.get('team_id'))
        if (not source or draw.get('draw_id') in ids or draw.get('attempt') != index
                or any(draw.get(key) != value for key, value in source.items())):
            raise ValueError('抽到的队伍与冻结名单不一致，请保留草稿。')
        ids.add(draw['draw_id'])
        selected = draw.get('selection')
        if selected is None:
            pending.append(draw['draw_id'])
        else:
            axis = selected.get('axis')
            player = next((p for p in draw['players'] if p['player_id'] == selected.get('player_id')), None)
            if axis not in axes or not player or selected != _candidate(player, axis, draw):
                raise ValueError('属性选择与真实五人名单不一致，请保留草稿。')
            selections[axis] = draw['draw_id']
    if (len(pending) > 1 or pending and pending[0] != draft['team_draws'][-1]['draw_id']
            or draft.get('pending_draw_id') != (pending[0] if pending else None)
            or any(draft['axes'][axis] != selections.get(axis) for axis in axes)):
        raise ValueError('队伍抽取进度记录无效，次数没有重置。')


def _load():
    path = _metadata_path()
    if not path.exists():
        return _empty_store()
    store = json.loads(path.read_text('utf-8'))
    if (not isinstance(store, dict) or store.get('schema_version') not in (1, SCHEMA_VERSION)
            or store.get('kind') != 'career3d-attribute-draw'
            or any(not isinstance(store.get(key), dict) for key in
                   ('drafts', 'active_drafts', 'receipts', 'create_receipts'))):
        raise ValueError('开局草稿格式不兼容，请保留目录供检查。')
    # Migration is in-memory only: a read never rewrites an old file or quota.
    store.setdefault('active_team_drafts', {})
    if not isinstance(store['active_team_drafts'], dict):
        raise ValueError('队伍抽取活动草稿记录无效。')
    store['schema_version'] = SCHEMA_VERSION
    for ident, draft in store['drafts'].items():
        if not isinstance(draft, dict):
            raise ValueError('开局草稿已损坏。')
        if draft.get('schema_version', 1) == 1:
            _legacy_valid(ident, draft)
        else:
            _validate_team_draft(ident, draft)
    return store


def _save(store):
    path = _metadata_path()
    pending = path.with_name(path.name + '.writing')
    pending.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding='utf-8')
    pending.replace(path)


def source_pool(era, *, teams=None):
    """Freeze current-position values; existing drafts keep their stored pool."""
    from cs2career.world import build_teams
    from cs2career.world.ability import playing_ability, playing_stats
    from cs2career.world.era_data import placeholder
    axes, _ = _axes()
    seen, rows = set(), []
    for team in (teams if teams is not None else build_teams(_era(era))):
        for player in team.get('players') or []:
            name, ident = player.get('name'), player.get('player_id')
            if (not isinstance(name, str) or not name.strip() or not isinstance(ident, str)
                    or not ident or ident in seen or placeholder(player)
                    or re.fullmatch(r'(?:rook|slot|bot)\d+', name.strip(), re.IGNORECASE)
                    or player.get('placeholder') or player.get('fictional')):
                continue
            stats = playing_stats(player)
            if any(isinstance(stats.get(axis), bool) or not isinstance(stats.get(axis), (int, float))
                   or not math.isfinite(stats[axis]) or not 1 <= stats[axis] <= 100 for axis in axes):
                continue
            seen.add(ident)
            row = {'source_player_id': ident, 'player_id': ident, 'source_player': name,
                         'source_team_id': team['id'], 'source_team': team['name'],
                         'source_era': str(era), 'source': player.get('source', team.get('source', '')),
                         'data_quality': player.get('data_quality', team.get('data_quality', '')),
                         'role': player.get('role'), 'ability': playing_ability(player),
                         'stats': {axis: stats[axis] for axis in axes}}
            model = stats.get('position_model')
            if isinstance(model, dict) and model.get('model_version'):
                row['calibration_model_version'] = model['model_version']
            rows.append(row)
    return sorted(rows, key=lambda row: row['source_player_id'])


def team_source_pool(era, *, teams=None):
    """Fresh dated VRS seed, never another career's current earned standings."""
    from cs2career.world import build_teams, ERA_META
    from cs2career.league.vrs import VRS, MODEL_VERSION
    era = _era(era)
    world = teams if teams is not None else build_teams(era)
    dated = ERA_META[era]['start']
    vrs = VRS()
    vrs.seed(world, dated)
    standings = {row['id']: row for row in vrs.table(world, dated)}
    players = source_pool(era, teams=world)
    rows, seen = [], set()
    for team in world:
        ident = team['id']
        roster = [player for player in players if player['source_team_id'] == ident]
        if (ident in seen or len(team.get('players') or []) != 5 or len(roster) != 5
                or len({p['player_id'] for p in roster}) != 5 or len({p['source_player'].casefold() for p in roster}) != 5
                or not isinstance(team.get('name'), str) or not team['name'].strip()):
            continue
        seen.add(ident)
        score = standings[ident]
        rows.append({'team_id': ident, 'source_team_id': ident, 'source_team': team['name'],
                     'source_era': era, 'vrs_rank': score['rank'], 'vrs_points': score['vrs'],
                     'vrs_as_of': dated, 'vrs_model': MODEL_VERSION,
                     'vrs_source': 'same_era_opening_game_vrs_seed', 'players': roster})
    rows.sort(key=lambda team: (team['vrs_rank'], team['team_id']))
    if not rows:
        raise ValueError('这个年代没有完整的真实五人战队可供抽取。')
    for index, row in enumerate(rows):
        percentile = (index + .5) / len(rows)
        band = next(b for b in TEAM_BANDS if percentile <= b['max_percentile'])
        row.update(band=band['id'], band_label=band['name'], band_color=band['color'])
    live = {row['band'] for row in rows}
    mass = sum(b['probability'] for b in TEAM_BANDS if b['id'] in live)
    for row in rows:
        band = next(b for b in TEAM_BANDS if b['id'] == row['band'])
        row['band_probability'] = band['probability'] / mass
        row['team_probability'] = row['band_probability'] / sum(r['band'] == row['band'] for r in rows)
    return rows


def preview_sources(era, *, teams=None, limit=72):
    pool = source_pool(era, teams=teams)
    count = min(int(limit), len(pool))
    return [deepcopy(pool[index * len(pool) // count]) for index in range(count)] if count else []


def preview_teams(era, *, teams=None):
    return deepcopy(team_source_pool(era, teams=teams))


def draw_options():
    axes, labels = _axes()
    return {'schema_version': SCHEMA_VERSION, 'origin_id': ORIGIN_ID, 'max_draws': MAX_DRAWS,
            'axes': [{'id': axis, 'name': labels[axis]} for axis in axes],
            'selection_scope': SELECTION_SCOPE, 'value_policy': VALUE_POLICY,
            'team_bands': deepcopy(TEAM_BANDS), 'bands': deepcopy(ATTRIBUTE_BANDS),
            'source_policy': 'same_era_complete_named_roster',
            'vrs_source': 'same_era_opening_game_vrs_seed',
            'vrs_note': '按所选年代开局的游戏 VRS 分档；不是官方真实积分，也不用于换算个人能力。'}


def _public(draft):
    axes, labels = _axes()
    draws = {draw['draw_id']: draw for draw in draft['team_draws']}
    pending = draws.get(draft['pending_draw_id'])
    unfilled = [axis for axis in axes if draft['axes'][axis] is None]
    remaining = MAX_DRAWS - len(draws)
    selectable = list(axes) if not pending or remaining >= len(unfilled) else unfilled
    rows = []
    for axis in axes:
        selected = (draws.get(draft['axes'][axis]) or {}).get('selection')
        rows.append({'id': axis, 'name': labels[axis],
                     'selected_player_id': selected['player_id'] if selected else None,
                     'selected_value': selected['value'] if selected else None,
                     'selected_draw_id': draft['axes'][axis], 'selection': deepcopy(selected),
                     'candidates': [_candidate(p, axis, pending) for p in pending['players']] if pending else []})
    return {'schema_version': SCHEMA_VERSION, 'origin_id': ORIGIN_ID,
            'draft_id': draft['draft_id'], 'era': draft['era'], 'revision': draft['revision'],
            'status': draft['status'], 'max_draws': MAX_DRAWS, 'attempts_used': len(draws),
            'remaining': remaining, 'team_draws': deepcopy(draft['team_draws']),
            'pending_draw_id': draft['pending_draw_id'], 'axes': rows,
            'unfilled_axes': unfilled, 'selectable_axes': selectable,
            'can_roll': not pending and remaining > 0 and draft['status'] == 'pending',
            'complete': not unfilled and pending is None,
            'bands': deepcopy(ATTRIBUTE_BANDS), 'team_bands': deepcopy(TEAM_BANDS),
            'selection_scope': SELECTION_SCOPE, 'value_policy': draft['value_policy'],
            'pool_version': draft['pool_version'], 'source_count': len(draft['source_pool']),
            'vrs_source': 'same_era_opening_game_vrs_seed',
            'source_policy': 'same_era_complete_named_roster'}


def draw_context(state=None, era='2026'):
    era = _era(era)
    with _LOCK:
        store = _load()
        draft = store['drafts'].get(store['active_team_drafts'].get(era))
        return {'attribute_draw': _public(draft) if draft else None,
                'legacy_draft_preserved': era in store['active_drafts']}


def _request(body):
    request_id = body.get('request_id')
    if not isinstance(request_id, str) or not 8 <= len(request_id) <= 100:
        raise ValueError('请提供本次队伍抽取操作的唯一编号。')
    return request_id


def _active(store, draft_id, era):
    draft = store['drafts'].get(draft_id)
    if (not draft or draft.get('schema_version') != SCHEMA_VERSION or draft['era'] != era
            or draft['status'] != 'pending' or store['active_team_drafts'].get(era) != draft_id):
        raise ValueError('这个队伍草稿已结束或不属于所选年代，请重新读取开局。')
    return draft


def _draw_team(pool):
    # With replacement: the same roster may appear in a later attempt.
    value, total = _RANDOM.random(), 0.0
    for team in pool:
        total += team['team_probability']
        if value < total:
            return deepcopy(team)
    return deepcopy(pool[-1])  # Only floating-point summation residue.


def draw_command(state, action, body):
    if action not in ('open', 'roll', 'select'):
        raise ValueError('没有这个队伍抽取操作。')
    era, request_id = _era(body.get('era')), _request(body)
    identity = {'schema_version': SCHEMA_VERSION, 'action': action, 'era': era,
                'draft_id': body.get('draft_id'), 'axis': body.get('axis'),
                'draw_id': body.get('draw_id'), 'player_id': body.get('player_id')}
    digest = _hash(identity)
    with _LOCK:
        store = _load()
        receipt = store['receipts'].get(request_id)
        if receipt:
            expected = digest
            if receipt.get('schema_version', 1) == 1:
                expected = _hash({'action': action, 'era': era, 'draft_id': body.get('draft_id'),
                                  'difficulty': body.get('difficulty'), 'axis': body.get('axis'),
                                  'draw_id': body.get('draw_id')})
            if receipt['hash'] != expected:
                raise ValueError('这个操作编号已经用于另一套选择。')
            return {**deepcopy(receipt['result']), 'replayed': True}
        if request_id in store['create_receipts']:
            raise ValueError('这个编号已经用于创建生涯。')
        if action == 'open':
            draft = store['drafts'].get(store['active_team_drafts'].get(era))
            if draft is None:
                pool = team_source_pool(era)
                axes, _ = _axes()
                draft = {'schema_version': SCHEMA_VERSION, 'draft_id': uuid4().hex,
                         'era': era, 'revision': 0, 'status': 'pending', 'max_draws': MAX_DRAWS,
                         'selection_scope': SELECTION_SCOPE, 'value_policy': VALUE_POLICY,
                         'pool_version': 'sha256:' + _hash(pool), 'source_pool': pool,
                         'team_draws': [], 'pending_draw_id': None,
                         'axes': {axis: None for axis in axes}}
                store['drafts'][draft['draft_id']] = draft
                store['active_team_drafts'][era] = draft['draft_id']
            reason = '可抽取十次队伍，每次从五人中选取一项能力；七项选齐即可开始。'
        else:
            draft = _active(store, body.get('draft_id'), era)
            revision = body.get('draft_revision')
            if revision is not None and (type(revision) is not int or revision != draft['revision']):
                raise ValueError('草稿已变化，请读取最新选择后再操作。')
            if action == 'roll':
                if draft['pending_draw_id'] is not None:
                    raise ValueError('请先从本次抽到的队伍中选取一项能力。')
                if len(draft['team_draws']) >= MAX_DRAWS:
                    raise ValueError('十次队伍抽取机会已经用完。')
                if body.get('axis') is not None:
                    raise ValueError('现在每次抽取整支队伍，不再单独抽取属性。')
                draw = _draw_team(draft['source_pool'])
                draw.update(draw_id=uuid4().hex, attempt=len(draft['team_draws']) + 1, selection=None)
                draft['team_draws'].append(draw)
                draft['pending_draw_id'] = draw['draw_id']
                reason = '队伍已保存，请从这五人中选取一项能力。'
            else:
                draw_id, axis = body.get('draw_id'), body.get('axis')
                draw = next((d for d in draft['team_draws'] if d['draw_id'] == draw_id), None)
                if not draw or draw_id != draft['pending_draw_id'] or draw.get('selection') is not None:
                    raise ValueError('每次抽到的队伍只能选取一项能力，不能重新改选历史抽取。')
                if axis not in draft['axes']:
                    raise ValueError('请选择七项能力中的一项。')
                missing = sum(value is None for value in draft['axes'].values())
                if draft['axes'][axis] is not None and MAX_DRAWS - len(draft['team_draws']) < missing:
                    raise ValueError('剩余次数只够补齐空缺，请选择尚未获得的能力。')
                player = next((p for p in draw['players'] if p['player_id'] == body.get('player_id')), None)
                if player is None:
                    raise ValueError('只能选择本次队伍真实五人名单中的选手。')
                draw['selection'] = _candidate(player, axis, draw)
                draft['axes'][axis] = draw_id
                draft['pending_draw_id'] = None
                reason = '能力已保存，可继续抽队伍，或在七项选齐后开始生涯。'
            draft['revision'] += 1
        result = {'reason': reason, 'attribute_draw': _public(draft)}
        if action == 'roll':
            result.update(draw=deepcopy(draw), rolled_draw_id=draw['draw_id'])
        if action == 'select':
            result['selection'] = deepcopy(draw['selection'])
        store['receipts'][request_id] = {'schema_version': SCHEMA_VERSION, 'hash': digest, 'result': result}
        _save(store)  # Persist before any client reveal animation.
        return deepcopy(result)


def selected_attributes(draft_id, era, difficulty=None):
    """Resolve the seven values from server metadata, never the create body."""
    with _LOCK:
        store = _load()
        draft = _active(store, draft_id, _era(era))
        if difficulty is not None:
            raise ValueError('队伍抽取开局已经取消难度选项，请刷新开局界面。')
        if not _public(draft)['complete']:
            raise ValueError('请先为七项能力各选择一个结果，并完成当前队伍的选择。')
        draws = {draw['draw_id']: draw for draw in draft['team_draws']}
        chosen = {axis: deepcopy(draws[ident]['selection']) for axis, ident in draft['axes'].items()}
        return {axis: selection['value'] for axis, selection in chosen.items()}, {
            'schema_version': SCHEMA_VERSION, 'draft_id': draft_id, 'era': draft['era'],
            'max_draws': MAX_DRAWS, 'attempts_used': len(draws),
            'selection_scope': SELECTION_SCOPE, 'value_policy': draft['value_policy'],
            'pool_version': draft['pool_version'], 'selections': chosen,
            'vrs_source': 'same_era_opening_game_vrs_seed'}


def create_receipt(request_id, digest):
    with _LOCK:
        store = _load()
        if request_id in store['receipts']:
            raise ValueError('这个编号已经用于抽取操作。')
        receipt = store['create_receipts'].get(request_id)
        if receipt and receipt['hash'] != digest:
            raise ValueError('这个开局编号已经用于另一套选择。')
        return deepcopy(receipt['result']) if receipt else None


def finish_creation(request_id, digest, result, provenance=None):
    with _LOCK:
        store = _load()
        if provenance:
            draft = store['drafts'].get(provenance['draft_id'])
            if not draft or draft['era'] != provenance['era']:
                raise ValueError('新生涯的属性来源草稿缺失，请保留目录供检查。')
            if draft['status'] == 'pending':
                if draft.get('schema_version', 1) == SCHEMA_VERSION:
                    _active(store, provenance['draft_id'], provenance['era'])
                    store['active_team_drafts'].pop(provenance['era'], None)
                else:
                    store['active_drafts'].pop(provenance['era'], None)
                draft['status'] = 'created'
                draft['creation_request_id'] = request_id
            elif draft.get('creation_request_id') != request_id:
                raise ValueError('属性草稿已用于另一份新生涯。')
        store['create_receipts'][request_id] = {'hash': digest, 'result': deepcopy(result)}
        _save(store)
