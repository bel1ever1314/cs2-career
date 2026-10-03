"""3D start selection and cosmetic appearance; original Career owns all rules."""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import re
from uuid import UUID

DEFAULT_APPEARANCE = {
    'body_color': 'fff1d2', 'belly_color': 'ffe3a3', 'beak_color': 'efa147',
    'comb_color': 'd65a48', 'jersey_color': '2c4556', 'trim_color': '70b5a5',
    'outfit': 'jersey',
}


def validate_appearance(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_APPEARANCE):
        raise ValueError('请选择有效的形象颜色与服装。')
    result = dict(DEFAULT_APPEARANCE)
    for key, color in value.items():
        if key == 'outfit':
            if color not in ('jersey', 'natural'):
                raise ValueError('请选择队服或自然羽毛。')
            result[key] = color
        else:
            if not isinstance(color, str) or not re.fullmatch(r'#?[0-9a-fA-F]{6}', color):
                raise ValueError('形象颜色须为六位 RGB 颜色。')
            result[key] = color.lstrip('#').lower()
    return result


def requires_creation(state):
    """An internal starter career is not a player-created character."""
    career = state.career
    if not getattr(career, 'exists', True):
        return True
    incident = career.incident_state
    onboarding = incident.get('career3d_start', {})
    if onboarding.get('schema_version') == 1:
        return onboarding.get('pending') is True
    if incident.get('career3d_service', {}).get('start_receipts'):
        return False
    # Recognize only an untouched legacy template. Existing player careers and
    # templates with saved play progress remain continuable without rewriting.
    arcs = incident.get('arcs', {})
    if (getattr(career, 'player_name', '') != 'Career3D' or getattr(career, 'mode', '') != 'create'
            or getattr(career, 'origin', '') != 'academy'
            or arcs.get('seed') != UUID(int=20260930).hex
            or not arcs.get('started') or arcs.get('started') != getattr(state.season, 'date', '')
            or arcs.get('series')):
        return False
    arena = getattr(getattr(state, 'arena', None), 'data', {})
    if arena.get('history'):
        return False
    if any(match.get('played') for event in getattr(state.season, 'events', []) for match in event.get('matches', [])):
        return False
    return True


def startup_context(state):
    from tools.career3d_attribute_draw import draw_context
    saved = state.career.incident_state.get('career3d_avatar', {})
    appearance = validate_appearance(saved.get('appearance', {}))
    return {'avatar': {'schema_version': 1, 'appearance': appearance},
            'start': {'can_continue': bool(state.career.exists) and not requires_creation(state),
                      'creation_required': requires_creation(state),
                      'player': state.career.player_name, 'era': state.career.era,
                      'mode': state.career.mode, 'date': state.season.date,
                      'backup_before_replace': True},
            **draw_context(state, state.career.era)}


@lru_cache(maxsize=3)
def _options(era):
    from cs2career.world import ERA_META, build_teams, ROLE_LABEL, PLAYABLE_ROLES
    from tools.career3d_attribute_draw import draw_options, preview_teams, ORIGIN_ID
    if era not in ERA_META:
        raise ValueError('请选择 2024、2025 或 2026 年代。')
    teams = build_teams(era)
    attribute_draw = draw_options()
    attribute_draw['preview_teams'] = preview_teams(era, teams=teams)
    return {'ok': True, 'era': era, 'eras': [{'id': key, **meta} for key, meta in ERA_META.items()],
            'origins': [{'id': ORIGIN_ID, 'name': '抽队伍开局',
                         'description': '最多抽十次队伍，每次从五人中取一项能力；七项选齐即可开始。'}],
            'attribute_draw': attribute_draw, 'regions': [{'id': key, 'name': title} for key, title in
                [('AS', '亚洲'), ('EU', '欧洲'), ('AM', '美洲')]],
            'roles': [{'id': role, 'name': ROLE_LABEL[role]} for role in PLAYABLE_ROLES],
            'teams': [{'id': t['id'], 'name': t['name'], 'region': t['region'],
                       'players': [{'player_id': p['player_id'], 'name': p['name'],
                                    'role': p['role'], 'ability': p['ability']} for p in t['players']]}
                      for t in teams], 'default_appearance': dict(DEFAULT_APPEARANCE)}


def creation_options(era='2026'):
    # UI edits cannot mutate cached world data.
    return deepcopy(_options(str(era)))


def start_command(state, action, body):
    from tools.career3d_business import guard_revision, guard_roster
    from tools.career3d_attribute_draw import (
        ORIGIN_ID, create_receipt, finish_creation, selected_attributes,
    )
    if action == 'avatar':
        guard_revision(state, body)
        appearance = validate_appearance(body.get('appearance'))
        state.career.incident_state['career3d_avatar'] = {'schema_version': 1, 'appearance': appearance}
        return {'reason': '形象已保存。', 'appearance': appearance}
    if action != 'create':
        raise ValueError('没有这个开局操作。')
    payload = body.get('career')
    if not isinstance(payload, dict):
        raise ValueError('请先选择开局。')
    appearance = validate_appearance(body.get('appearance', {}))
    request_id = body.get('request_id')
    if not isinstance(request_id, str) or not 8 <= len(request_id) <= 100:
        raise ValueError('请提供本次开局的唯一编号。')
    digest = hashlib.sha256(json.dumps({'career': payload, 'appearance': appearance},
                                     sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    store = state.career.incident_state.get('career3d_service', {})
    receipt = next((r for r in store.get('start_receipts', []) if r['id'] == request_id), None)
    if receipt:
        if receipt['hash'] != digest:
            raise ValueError('这个开局编号已经用于另一套选择。')
        # Recover the metadata half if the process stopped after the original
        # atomic career replacement but before retiring its start draft.
        finish_creation(request_id, digest, receipt['result'],
                        state.career.incident_state.get('career3d_attribute_draw'))
        return {**receipt['result'], 'replayed': True}
    prior = create_receipt(request_id, digest)
    if prior:
        return {**prior, 'replayed': True}
    guard_revision(state, body)
    guard_roster(state)
    if state.career.exists and body.get('confirm_replace') is not True:
        raise ValueError('开始新生涯前，请确认备份当前生涯。')
    from cs2career.world import PLAYABLE_ROLES
    era = str(payload.get('era', '2026'))
    options = creation_options(era)
    mode = payload.get('mode')
    if mode not in ('create', 'join') or payload.get('role') not in PLAYABLE_ROLES:
        raise ValueError('请选择有效的生涯方式和位置。')
    if payload.get('region', 'AS') not in ('AS', 'EU', 'AM'):
        raise ValueError('请选择有效的赛区。')
    cleaned = {k: payload[k] for k in ('era', 'mode', 'origin', 'name', 'org', 'role', 'region') if k in payload}
    attributes, provenance = None, None
    if mode == 'create':
        if payload.get('origin') != ORIGIN_ID:
            raise ValueError('3D 自建生涯请使用七维抽取开局。')
        attributes, provenance = selected_attributes(payload.get('draft_id'), era, payload.get('difficulty'))
    if mode == 'join':
        team = next((t for t in options['teams'] if t['id'] == payload.get('team_id')), None)
        player = next((p for p in (team or {}).get('players', [])
                       if p['player_id'] == payload.get('player_id')), None)
        if not team or not player:
            raise ValueError('所选战队或选手不属于这个年代，请重新选择。')
        cleaned.update(team_id=team['id'], replace=player['name'])
    revision = int(store.get('revision', 0))
    owner, real_skins = state.career.steam_id, state.career.real_skins
    result = {'reason': '新生涯已开始。', 'new_career': True}
    metadata = {
        'career3d_start': {'schema_version': 1, 'pending': False},
        'career3d_avatar': {'schema_version': 1, 'appearance': appearance},
        'career3d_service': {'revision': revision, 'receipts': [],
                             'start_receipts': [{'id': request_id, 'hash': digest, 'result': result}]},
    }
    if provenance:
        metadata['career3d_attribute_draw'] = provenance
    # Attributes and receipt belong to the new instance before its original
    # backup/validate/atomic replacement, so no academy-valued intermediate save
    # or receipt-less new career can escape after an interrupted request.
    state.create_career(cleaned, start_attributes=attributes, start_metadata=metadata)
    state.career.steam_id, state.career.real_skins = owner, real_skins
    from cs2career.career.fast_mode import configure_season
    configure_season(state.career, state.season, payload.get('quick_mode') is True, state.season.year)
    finish_creation(request_id, digest, result, provenance)
    return result
