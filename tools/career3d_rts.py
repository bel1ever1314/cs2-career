"""Career RTS maps: frozen ten-person inputs, raw round ledger, normal settlement.

This local-only command adapter runs under ApplicationState's existing lock.
RTS is labelled as a simplified simulation, never as a real CS2 result.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from tools.career3d_matches import _guard, _pair, _reason, _identity, _init_veto, _advance_veto, _result_response


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _map_rows():
    catalog = Path(__file__).resolve().parents[1] / 'work/career_rts/data/map_catalog.json'
    rows = json.loads(catalog.read_text('utf-8')).get('maps', {})
    return rows if isinstance(rows, dict) else {}


def _map_reason(map_id, row):
    return row.get('career_reason_zh', row.get('career_reason', '该图职业 RTS 尚待验证。'))


def rts_context(state):
    active = next((m for ev in state.season.events for m in ev.get('matches', [])
                   if not m.get('played') and m.get('career3d_rts')), None)
    session = deepcopy((active or {}).get('career3d_rts') or {})
    arena_session = deepcopy((state.arena.data.get('lobby') or {}).get('rts_session') or {})
    rows = _map_rows()
    ready = [key for key, row in rows.items() if row.get('status') == 'playable' and row.get('career_ready', False)]
    limitations = {key: _map_reason(key, row)
                   for key, row in rows.items() if key not in ready}
    return {'rts': {'session': session, 'arena_session': arena_session, 'pending': bool(session or arena_session),
                    'career_maps': ready, 'limitations': limitations}}


def _arena_rosters(lobby):
    from cs2career.world.ability import playing_ability, playing_stats
    aliases = dict(aim='firepower', reaction='opening', recoil='trading', awareness='clutching', utility='utility')
    out = {'team_names': {}, 'human_id': lobby.get('human_id', ''), 'skills_source': aliases}
    for side, team in (('ct', lobby['ct']), ('t', 'b' if lobby['ct'] == 'a' else 'a')):
        rows = []
        for pid in lobby[team]:
            player = lobby['roster'][pid]
            ability, stats = playing_ability(player), playing_stats(player)
            rows.append(dict(id=pid, player_id=pid, name=player['name'], role=player.get('role', 'rifle'),
                ability=ability, skills={key: stats.get(axis, ability) for key, axis in aliases.items()}))
        out[side] = rows
        out['team_names'][side] = 'Team ' + team.upper()
    return out


def arena_rts_command(state, action, body):
    from datetime import datetime, timezone
    from tools.career3d_activities import _public_report
    from tools.career3d_matches import career_cs2_pending
    arena = state.arena
    lobby = arena.data.get('lobby') or {}
    if lobby.get('id') != body.get('lobby_id') or lobby.get('mode') not in ('rank', 'fpl'):
        raise ValueError('当前天梯房间已变化。')
    arena.guard_rank_action(state, 'ingest' if action == 'arena_submit' else 'cancel' if action == 'arena_cancel' else 'launch')
    if action == 'arena_submit' and lobby.get('phase') == 'finished':
        if lobby.get('result', {}).get('source') != 'rts' or body.get('nonce') != lobby.get('nonce'):
            raise ValueError('这不是当前已结算的 RTS 对局。')
        return {'status':'finished', 'reason':'这场 RTS 天梯已保存，不重复计分。',
                'arena_result':_public_report(lobby['result']), 'replayed':True}
    _guard(state, body)
    arena._guard(body.get('arena_revision'))
    session = lobby.get('rts_session') or {}
    if action == 'arena_start':
        if session:
            return {'status':'rts_pending', 'reason':'继续这场未结算的 RTS 天梯。', 'rts_session':deepcopy(session), 'replayed':True}
        if lobby.get('phase') != 'ready':
            raise ValueError('先完成选人、地图 BP 与选边，再开始 RTS。')
        if state.career.training_session or career_cs2_pending(state):
            raise ValueError('请先完成另一场等待结算的比赛。')
        code = 'de_' + lobby['map']
        row = _map_rows().get(code, {})
        if row.get('status') != 'playable' or not row.get('career_ready', False):
            raise ValueError(_map_reason(code, row))
        roster = _arena_rosters(lobby)
        session = {'kind':'arena', 'lobby_id':lobby['id'], 'map':code, 'nonce':uuid4().hex,
                   'rosters':roster, 'roster_hash':_hash(roster), 'player_id':lobby['human_id'],
                   'commanded_side':'ct' if lobby['human_id'] in lobby[lobby['ct']] else 't'}
        session['seed'] = int(session['nonce'][:8], 16) % 2147483647
        lobby.update(phase='rts', nonce=session['nonce'], rts_session=session)
        arena._commit()
        return {'status':'rts_pending', 'reason':'天梯 RTS 名单与地图已冻结，胜负只影响本地天梯。',
                'rts_session':deepcopy(session)}
    if not session or body.get('nonce') != session['nonce']:
        raise ValueError('RTS 天梯身份已变化。')
    if action == 'arena_cancel':
        lobby.pop('rts_session', None)
        lobby.pop('nonce', None)
        lobby['phase'] = 'ready'
        arena._commit()
        return {'status':'cancelled', 'reason':'未完赛 RTS 已取消，原名单与 BP 保留，未计算天梯分。'}
    if session['roster_hash'] != _hash(_arena_rosters(lobby)):
        raise ValueError('RTS 阵容已变化，不能覆盖战绩。')
    match = {'team_a':'Team A', 'team_b':'Team B'}
    box = map_box(body.get('report'), session, match)
    reason = arena.ingest_rts({'revision':body['arena_revision'], 'nonce':session['nonce']}, box,
                              datetime.now(timezone.utc).isoformat())
    return {'status':'finished', 'reason':reason, 'arena_result':_public_report(arena.data['lobby']['result'])}


def _rosters(state, match, ct_team):
    from cs2career.world.ability import playing_ability, playing_stats
    from cs2career.world.eras import player_id
    aliases = dict(aim='firepower', reaction='opening', recoil='trading', awareness='clutching', utility='utility')
    by_name = {t['name']: t for t in state.season.teams}
    out = {'team_names': {}, 'human_id': '', 'skills_source': aliases}
    ids = set()
    for side, name in (('ct', ct_team), ('t', match['team_b'] if ct_team == match['team_a'] else match['team_a'])):
        roster = []
        for p in by_name[name]['players']:
            pid = p.get('player_id') or player_id(p['name'])
            if not pid or pid in ids:
                raise ValueError('RTS 阵容身份重复，请检查双方名单。')
            ids.add(pid)
            ability = playing_ability(p)
            stats = playing_stats(p)
            skills = {key: stats.get(axis, ability) for key, axis in aliases.items()}
            roster.append(dict(id=pid, player_id=pid, name=p['name'], role=p.get('role', 'rifle'), ability=ability, skills=skills))
        if len(roster) != 5:
            raise ValueError('RTS 比赛需要双方各五名选手。')
        out[side] = roster
        out['team_names'][side] = name
    return out


def _count(value, upper, label):
    # Godot JSON numbers decode as floats. Only finite, exactly integral values
    # are accepted; strings/bools are not stat counters.
    if type(value) not in (int, float) or not 0 <= value <= upper or int(value) != value:
        raise ValueError('RTS 战绩计数无效：' + label)
    return int(value)


def map_box(report, session, match):
    from cs2career.engine.rating import career_rating
    if not isinstance(report, dict) or report.get('schema_version') != 2 or report.get('finished') is not True:
        raise ValueError('RTS 地图尚未正式结束，不能录入。')
    if report.get('map') != session['map'] or report.get('seed') != session['seed']:
        raise ValueError('RTS 地图或本场种子不一致。')
    history = report.get('round_history')
    if not isinstance(history, list) or not 13 <= len(history) <= 240:
        raise ValueError('RTS 正式回合记录不完整。')
    expected = {p['id']: (side, p) for side in ('ct', 't') for p in session['rosters'][side]}
    totals = {pid: dict(k=0, d=0, a=0, damage=0, survived_rounds=0, kast_rounds=0,
                        opening_kills=0, opening_deaths=0) for pid in expected}
    score = dict(ct=0, t=0)
    events = []
    rounds = []
    id_names = {pid: value[1]['name'] for pid, value in expected.items()}
    for number, rd in enumerate(history, 1):
        if not isinstance(rd, dict) or rd.get('round') != number or rd.get('winner') not in score:
            raise ValueError('RTS 回合顺序或胜方不完整。')
        before = dict(score)
        score[rd['winner']] += 1
        if rd.get('score') != score:
            raise ValueError('RTS 回合比分与累积比分不符。')
        players = rd.get('players')
        if (not isinstance(players, list) or len(players) != 10 or not all(isinstance(p, dict) for p in players)
                or {p.get('id') for p in players} != set(expected)):
            raise ValueError('RTS 正式回合缺少唯一十人名单。')
        for p in players:
            pid = p['id']
            if p.get('team') != expected[pid][0]:
                raise ValueError('RTS 选手队伍身份不一致。')
            row = totals[pid]
            for key, maximum in (('k', 5), ('d', 1), ('a', 5), ('damage', 500), ('opening_kills', 1), ('opening_deaths', 1)):
                row[key] += _count(p.get(key), maximum, key)
            if any(type(p.get(key)) is not bool for key in ('survived', 'kast', 'traded')):
                raise ValueError('RTS 生存/KAST 回合字段不完整。')
            if p['d'] != (0 if p['survived'] else 1):
                raise ValueError('RTS 死亡和生存记录不符。')
            row['survived_rounds'] += int(p['survived'])
            row['kast_rounds'] += int(p['kast'])
        # Preserve actual event identity. Do not recover it from nickname guesses.
        for raw in rd.get('events', []):
            if not isinstance(raw, dict): continue
            kind = {'bomb_planted': 'plant', 'bomb_defused': 'defuse'}.get(raw.get('type'), raw.get('type'))
            if kind == 'shot' and raw.get('hit') is True:
                kind = 'hurt'
            if kind not in ('kill', 'hurt', 'plant', 'defuse', 'bomb_exploded'): continue
            event = {'round': number, 'type': kind, 'source': 'rts'}
            aliases = {'killer': ('killer_id', 'killer', 'attacker_id', 'attacker'),
                       'attacker': ('attacker_id', 'attacker', 'id'),
                       'victim': ('victim_id', 'victim', 'target_id'),
                       'assister': ('assister_id', 'assister'), 'id': ('id', 'actor_id')}
            for key in ('killer', 'victim', 'assister') if kind == 'kill' else ('attacker', 'victim') if kind == 'hurt' else ('id',):
                pid = next((raw.get(alias) for alias in aliases[key] if raw.get(alias) in expected), None)
                if pid:
                    event[key] = id_names[pid]
                    event[key + '_id'] = pid
            for key in ('damage', 'weapon', 'headshot', 'site'):
                if key in raw and isinstance(raw[key], (str, int, float, bool)):
                    event[key] = raw[key]
            events.append(event)
        winner = session['rosters']['team_names'][rd['winner']]
        events.append({'round': number, 'type': 'round_end', 'winner': 'a' if winner == match['team_a'] else 'b',
                       'reason': str(rd.get('reason', '')), 'source': 'rts'})
        rounds.append({'round': number, 'winner': winner, 'players': deepcopy(players),
                       'reason': str(rd.get('reason', '')), 'score': dict(score)})
        # MR12 followed by repeated MR3. A map cannot append rounds after it
        # already won, even when a client sends a plausible final score.
        total_before = sum(before.values())
        target_before = 13 if total_before < 24 else 16 + ((total_before - 24) // 6) * 3
        if max(before.values()) >= target_before:
            raise ValueError('RTS 在终场后仍有额外回合。')
    if report.get('score') != score or score['ct'] == score['t']:
        raise ValueError('RTS 终场比分不一致或仍是平局。')
    n = len(history)
    winning_target = 13 if n <= 24 else 16 + ((n - 25) // 6) * 3
    winner_side = max(score, key=score.get)
    if max(score.values()) != winning_target or report.get('winner') != winner_side:
        raise ValueError('RTS 未到达正式终场条件。')
    lines = report.get('players') or []
    if not isinstance(lines, list) or len(lines) != 10 or not all(isinstance(p, dict) for p in lines) or {p.get('id') for p in lines} != set(expected):
        raise ValueError('RTS 终场十人统计不完整。')
    for p in lines:
        row = totals[p['id']]
        if any(_count(p.get(k), 120000, k) != value for k, value in row.items()):
            raise ValueError('RTS 逐回合与终场个人统计不符。')
    grouped = {}
    for side in ('ct', 't'):
        grouped[session['rosters']['team_names'][side]] = []
        for p in session['rosters'][side]:
            st = totals[p['id']]
            grouped[session['rosters']['team_names'][side]].append({**st, 'player_id': p['id'], 'name': p['name'],
                'role': p['role'], 'ability': p['ability'], 'rounds': n, 'kpr': round(st['k']/n, 3),
                'adr': round(st['damage']/n, 2), 'kast': round(st['kast_rounds']/n, 4),
                'rating': career_rating(st['k'], st['d'], st['a'], st['damage'], st['kast_rounds'], n)})
    a_side = 'ct' if session['rosters']['team_names']['ct'] == match['team_a'] else 't'
    b_side = 't' if a_side == 'ct' else 'ct'
    return {'map': session['map'].removeprefix('de_'), 'score': f"{score[a_side]}-{score[b_side]}", 'rounds': n,
            'winner': session['rosters']['team_names'][winner_side], 'players': grouped, 'events': events,
            'rts_round_history': rounds, 'schema_version': 2, 'source': 'rts', 'request_nonce': session['nonce'],
            'simulation_model': 'RTS simplified local rules', 'seed': session['seed']}


def rts_command(state, action, body):
    if action in ('arena_start', 'arena_submit', 'arena_cancel'):
        return arena_rts_command(state, action, body)
    ev, match = _pair(state, body.get('match_id', ''), True)
    if action not in ('start', 'submit', 'cancel'):
        raise ValueError('没有这个 RTS 操作。')
    nonce = body.get('nonce', '')
    if action == 'submit':
        previous = next((m for m in match.get('maps', []) if m.get('source') == 'rts' and m.get('request_nonce') == nonce), None)
        if previous:
            return {**_result_response(state, ev, match, '这张 RTS 地图已保存。'), 'replayed': True}
    _guard(state, body)
    if action == 'start':
        if body.get('side', 't') not in ('ct', 't'):
            raise ValueError('请选择 CT 或 T 开局。')
        session = match.get('career3d_rts')
        if session:
            return {'status': 'rts_pending', 'reason': '该图已在等待 RTS 战绩；可以重新开始未结算的对局。',
                    'rts_session': deepcopy(session), 'replayed': True}
        state.season._require_yours(match['id'])
        reason = _reason(state, match) or state.career.gate_match(state.season, match['id'])
        if reason or state.career.story_queue:
            return {'status': 'paused', 'reason': reason or '请先处理生涯事件。'}
        _identity(state, match)
        _init_veto(state, ev, match)
        _advance_veto(state, match, all_turns=True)
        if state.season._phase_gate(ev, match):
            return {'status': 'paused', 'reason': '请先处理比赛阶段事件。'}
        name = match.get('pending_map')
        if not name:
            raise ValueError('本系列赛没有待打地图。')
        entry = _map_rows().get('de_' + name)
        if not entry or entry.get('status') != 'playable':
            return {'status': 'paused', 'reason': '该图尚未接入职业 RTS：' + name + '。BP 已保留，可使用常规模拟或进入 CS2。'}
        if not entry.get('career_ready', False):
            return {'status': 'paused', 'reason': _map_reason('de_' + name, entry) + ' BP 已保留。'}
        mine = state.season.your_team_name()
        ct_team = mine if body.get('side', 't') == 'ct' else match['team_b'] if mine == match['team_a'] else match['team_a']
        rosters = _rosters(state, match, ct_team)
        session = {'nonce': uuid4().hex, 'match_id': match['id'], 'map': 'de_' + name,
                   'map_index': len(match.get('maps') or []), 'rosters': rosters, 'roster_hash': _hash(rosters),
                   'commanded_side': 'ct' if ct_team == mine else 't', 'player_id': match['career3d_identity']['player_id']}
        session['seed'] = int(session['nonce'][:8], 16) % 2147483647
        match['career3d_rts'] = session
        return {'status': 'rts_pending', 'reason': 'RTS 阵容与地图已冻结。', 'rts_session': deepcopy(session)}
    session = match.get('career3d_rts')
    if not session or not isinstance(nonce, str) or nonce != session['nonce']:
        raise ValueError('RTS 对局身份已变化，请重新打开当前比赛。')
    if action == 'cancel':
        match.pop('career3d_rts', None)
        return {'status': 'cancelled', 'reason': '已退出未录入的 RTS 地图；此前已保存的地图战绩不变。'}
    if session['map_index'] != len(match.get('maps') or []) or session['roster_hash'] != _hash(_rosters(state, match, session['rosters']['team_names']['ct'])):
        raise ValueError('比赛进度或阵容已变化，不能覆盖战绩。')
    box = map_box(body.get('report'), session, match)
    match.setdefault('maps', []).append(box)
    match.pop('career3d_rts', None)
    from cs2career.league.phases import emit
    emit(state.season, ev, match, 'map_finished', session['map_index'])
    if state.season._series_over(match):
        state.season._finalize_human(ev, match)
    else:
        state.season.open_your_series(ev, match)
    out = _result_response(state, ev, match, 'RTS 地图战绩已保存。', session['map_index'])
    out['status'] = 'finished' if match.get('played') else 'map_collected'
    if match.get('played'):
        match['career3d_result'] = deepcopy(out['result'])
    return out
