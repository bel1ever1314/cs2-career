"""Bounded computer views and adapters for the original career controls.

The HTTP owner holds the original application lock. Reads never call payload(),
advance dates, process assistance, settle rewards, or generate contract offers.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path


PAGES = ('management', 'training', 'assistance', 'rankings', 'workshop')


def _revision(state):
    return int(state.career.incident_state.get('career3d_service', {}).get('revision', 0))


def _busy(state, training=True):
    from cs2career.services.matches import career_cs2_pending
    if state.arena.pending or career_cs2_pending(state):
        return '真实比赛正在启动或等待回传，请先完成当前比赛。'
    if training and state.career.training_session:
        return 'CS2 训练赛正在等待核验，请先完成本次训练。'
    return ''


def management_context(state):
    from .team_marks import context as mark_context
    from cs2career.world.roles import PLAYABLE_ROLES, ROLE_LABEL
    c, s = state.career, state.season
    team = c.my_team(s.teams) or {}
    rows = [r for r in c.inbox if r.get('kind') == 'contract']
    selected = rows[-20:]
    for row in rows:
        if row.get('status') == 'open' and row not in selected:
            selected.append(row)
    pending = c.personal_transfers.get('pending') or {}
    reason = _busy(state) or ('当前没有所属战队。' if not team else '')
    return dict(team_id=team.get('id', ''), team=team.get('name', ''), marks=mark_context(state),
        roster=[{key: deepcopy(p.get(key)) for key in
                 ('player_id', 'name', 'role', 'ability', 'age', 'you', 'roster_status')}
                for p in team.get('players', [])],
        roles=list(PLAYABLE_ROLES), role_labels=dict(ROLE_LABEL),
        unsigned=bool(c.unsigned), player_only=bool(c.personal_transfers.get('player_only')),
        roles_allowed=not reason, contract_allowed=not _busy(state), reason=reason, offers=deepcopy(selected[::-1]),
        pending=deepcopy(pending), history=deepcopy(c.personal_transfers.get('moves', [])[-20:][::-1]),
        contract_note='合同沿用原生涯邀约规则；接受后进入原加盟选择，再由你决定签字或留下。')


def training_context(state):
    from cs2career.world import map_form
    from cs2career.services.activities import personal_context, config_status, team_directory
    from cs2career.arena import MAPS
    from cs2career.career.story_timing import public
    c, s = state.career, state.season
    team = c.my_team(s.teams) or {}
    reason = _busy(state) or ('今天的训练奖励已经结算，请在下一游戏日再启动真实训练；模拟训练赛仍可安排。'
        if c.last_scrim == s.date else
        '需要有效生涯和完整五人阵容。' if c.over() or c.unsigned or len(team.get('players', [])) != 5 else '')
    session = c.training_session or {}
    return dict(date=s.date, team=team.get('name', ''), mentality=team.get('mentality'),
        map_performance=map_form.public(team) if team else [], map_practice=deepcopy(team.get('map_practice') or {}),
        last_training=c.last_scrim, today_rewarded=c.last_scrim == s.date,
        pending=bool(session), session={key: session.get(key, '') for key in ('nonce', 'map', 'date', 'opponent', 'started_at')},
        launch_allowed=not reason, reason=reason, config=config_status(),
        opponents=[t for t in team_directory(state) if t['id'] != c.team_id], maps=list(MAPS),
        personal=personal_context(state), growth_window=public(c, s),
        rule='完成真实 CS2 训练赛后核验；每个游戏日最多一次全队心态收益，收益沿用原边际递减规则，不增加个人能力。')


def assistance_context(state):
    from cs2career.career.assistance import LEVELS
    from cs2career.world.ability import ALL_AXES, AXIS_LABEL
    c = state.career
    return dict(invites=deepcopy(c.assist.get('invites') or {}), points=c.assist.get('points') or 'off',
        quick_mode=bool(c.assist.get('quick_mode')), notice=c.assist.get('notice') or '',
        levels=list(LEVELS), axes=list(ALL_AXES), axis_labels=dict(AXIS_LABEL),
        reason=_busy(state), allowed=not _busy(state),
        note='保存后，现有邀请与可用点数按原规则处理；转会合同与剧情仍由你决定。快速模式在 Major 后休赛期分配属性点。')


def rankings_context(state, board='top20', year=None, page=1, search=''):
    from cs2career.services.business import players_page
    if board not in ('top20', 'players'):
        raise ValueError('榜单只支持 top20 或 players。')
    if type(page) is not int or page < 1 or not isinstance(search, str) or len(search) > 100:
        raise ValueError('请提供有效页码与不超过 100 字符的搜索文字。')
    s = state.season
    year = s.year if year is None else year
    if type(year) is not int or not 2000 <= year <= 3000:
        raise ValueError('请提供有效年份。')
    years = sorted({s.year, *[int(y) for y in s.top20]}, reverse=True)
    if board == 'players':
        if year != s.year:
            raise ValueError('选手数据榜沿用原本赛季对 VRS Top30 对手的口径。')
        return dict(players_page(state, page=page, search=search), board=board, year=year, years=years)
    final = str(year) in s.top20
    if not final and year != s.year:
        raise ValueError('没有这个年份的已存 Top20。')
    rows = deepcopy(s.top20[str(year)]) if final else s.top20_live()
    if search:
        rows = [r for r in rows if search.casefold() in (str(r.get('player', '')) + ' ' + str(r.get('team', ''))).casefold()]
    # Preserve the original board order, thresholds, honour weights and score.
    return dict(rows=rows[(page - 1) * 20:page * 20], board=board, year=year, years=years,
        final=final, page=page, page_size=20, pages=max(1, math.ceil(len(rows) / 20)), total=len(rows),
        note='年度最终榜单' if final else '本赛季暂定 Top20 · 原业务荣誉与 Top10 / Top20 对手评分，样本不足不列入。')


def controls_context(state, section, **query):
    if section == 'management':
        data = management_context(state)
    elif section == 'training':
        data = training_context(state)
    elif section == 'assistance':
        data = assistance_context(state)
    elif section == 'rankings':
        data = rankings_context(state, **query)
    elif section == 'workshop':
        from cs2career.content import get_registry
        data = deepcopy(get_registry().public())
        data['reason'] = _busy(state)
    else:
        raise ValueError('没有这个电脑控制页面。')
    return dict(ok=True, page=section, revision=_revision(state), data=data)


def _receipt(state, action, body, perform, namespace='controls'):
    from cs2career.storage.receipts import needs_legacy_receipt
    request_id = body.get('request_id')
    if request_id is not None and (not isinstance(request_id, str) or not 8 <= len(request_id) <= 100):
        raise ValueError('request_id 必须是 8 至 100 字符的唯一编号。')
    identity = {key: value for key, value in body.items() if key not in ('revision', 'request_id')}
    fingerprint = hashlib.sha256(json.dumps([action, identity], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    store = state.career.incident_state.get('career3d_service') or {}
    receipts = store.get(namespace + '_receipts') or []
    prior = next((r for r in receipts if r['request_id'] == request_id), None) if request_id else None
    if prior:
        if prior['fingerprint'] != fingerprint:
            raise ValueError('这个 request_id 已用于另一项操作。')
        return dict(deepcopy(prior['result']), replayed=True)
    from cs2career.services.business import guard_revision
    guard_revision(state, body)
    out = perform()
    if needs_legacy_receipt(request_id):
        store = state.career.incident_state.setdefault('career3d_service', {'revision': 0, 'receipts': []})
        store[namespace + '_receipts'] = (receipts + [dict(request_id=request_id, fingerprint=fingerprint,
                                                        result=deepcopy(out))])[-32:]
    return out


def _training_launch(state, body, *, dispatch=None, reward=True):
    from cs2career.cs2 import launch
    from cs2career.services.activities import read_cs2_config, config_status, _running_cs2
    from cs2career import tactics
    c, s = state.career, state.season
    team = c.my_team(s.teams)
    opponent = next((t for t in s.teams if t['id'] == body.get('opponent_id')), None)
    if c.over() or c.unsigned or not team or len(team.get('players', [])) != 5:
        raise ValueError('需要有效生涯和完整五人阵容。')
    if reward and c.last_scrim == s.date:
        raise ValueError('今天的训练奖励已经结算，请在下一游戏日再启动真实训练；模拟训练赛仍可安排。')
    if not opponent or opponent['id'] == team['id'] or len(opponent.get('players', [])) != 5:
        raise ValueError('请选择另一支完整队伍作为训练对手。')
    code = tactics.canonical_map(body.get('map', 'de_dust2'))
    side = body.get('side', 'ct')
    if side not in ('ct', 't'):
        raise ValueError('请选择 CT 或 T 开局。')
    if _running_cs2():
        raise ValueError('请完全退出 CS2 后再启动训练赛。')
    launch.require_cs2_closed('启动 3D 训练赛')
    config = config_status()
    if not config['ready']:
        raise ValueError(config['reason'])
    cfg = read_cs2_config()
    from .matches import _dispatch_launch
    request = launch.build_request(team, opponent, c.player_name, code, side)
    # Freeze cosmetics off the live career: the external adapter cannot save
    # training progress from inside Steam preparation.
    value = (dispatch or _dispatch_launch)(cfg,
        (team, opponent, c.player_name, code, side, s.teams, deepcopy(c)),
        dict(purpose='series', request_override=request))
    c.remember_training(request)
    from cs2career.world.map_form import expectation
    c.training_session.update(opponent_id=opponent['id'], my_team=team['name'], opp=opponent['name'], side=side,
                              map_expectation=expectation(team, opponent, code))
    return dict(reason=value['msg'], status='waiting')


def controls_command(state, action, body, *, dispatch=None):
    from cs2career.career.assistance import configure
    from cs2career.world.roles import PLAYABLE_ROLES
    c, s = state.career, state.season
    def perform():
        reason = _busy(state, training=action not in ('training/finish', 'training/cancel'))
        if reason:
            raise ValueError(reason)
        if action == 'team-logo':
            from .team_marks import command
            return command(state, body)
        if action == 'roles':
            team = c.my_team(s.teams)
            mapping = body.get('roles')
            if not team or not isinstance(mapping, dict) or set(mapping) != {p['name'] for p in team['players']}:
                raise ValueError('名单对不上，请刷新后再试。')
            if any(role not in PLAYABLE_ROLES for role in mapping.values()):
                raise ValueError('请选择原有位置。')
            return dict(reason=c.set_roles(s, deepcopy(mapping), str(body.get('player') or '')))
        if action == 'assistance':
            if set(body) - {'revision', 'request_id', 'invites', 'points'} or not {'invites', 'points'}.intersection(body):
                raise ValueError('请选择邀请规则或自动加点方向。')
            return dict(reason=configure(c, s, body))
        if action in ('contract/accept', 'contract/decline'):
            mail_id = body.get('id')
            row = c._mail(mail_id)
            if not row or row.get('kind') != 'contract' or row.get('status') != 'open':
                raise ValueError('这封合同已经处理或失效，请刷新。')
            from cs2career.services.business import mail_command
            return mail_command(state, action.rsplit('/', 1)[1], body)
        if action == 'training/map-focus':
            from cs2career.world.map_form import schedule_practice
            team = c.my_team(s.teams)
            if not team or c.over() or c.unsigned:
                raise ValueError('加入队伍后才能安排专项练图。')
            schedule_practice(team, body.get('map', ''), s.date)
            return dict(reason='专项练图已安排，跨日后结算；今天只训练这一张图。')
        if action == 'training/launch':
            return _training_launch(state, body, dispatch=dispatch)
        if action == 'training/finish':
            if (c.training_session or {}).get('booking_id'):
                from .scrims import command
                return command(state, 'collect', dict(id=c.training_session['booking_id'], nonce=c.training_session['nonce']))
            if c.last_scrim == s.date and not c.training_session:
                raise ValueError('今天的训练奖励已经结算。')
            if not c.training_session:
                raise ValueError('没有待核验的真实 CS2 训练赛。')
            return dict(reason=c.finish_training(s))
        if action == 'training/cancel':
            if (c.training_session or {}).get('booking_id'):
                from .scrims import command
                return command(state, 'cancel', dict(body, id=c.training_session['booking_id']))
            from cs2career.services.activities import _running_cs2
            session = c.training_session or {}
            if body.get('confirmed') is not True or not session or body.get('nonce') != session.get('nonce'):
                raise ValueError('请明确确认取消当前这场待核验训练。')
            try:
                running = _running_cs2()
            except (OSError, RuntimeError) as exc:
                raise ValueError(str(exc)) from None
            if running is not False:
                raise ValueError('请先完全退出 CS2，再取消待核验训练。')
            # Connection bookkeeping only: do not invoke rewards or erase the
            # original CS2 result/history, last training date or player stats.
            from cs2career.services.activities import read_cs2_config
            from .external_effects import retire
            cfg = read_cs2_config()
            if cfg.get('csgo_path'):
                retire(state, cfg['csgo_path'], session['nonce'])
            c.training_session = None
            return dict(reason='本次训练核验已取消，未发放奖励；现有战绩记录保留。')
        if action == 'workshop/reload':
            from cs2career.content import reload_registry
            from cs2career.career import story, skins
            from cs2career.league.season import reload_calendar
            from cs2career.world.eras import reload_era_extensions
            registry = reload_registry()
            story.reload_stories()
            skins.reload_catalog()
            reload_calendar()
            reload_era_extensions()
            from cs2career.services.start import _options
            _options.cache_clear()
            return dict(reason='扩展已重载。生涯事件下次触发、聊天下次准备比赛生效；赛事及年代用于新生涯。')
        raise ValueError('没有这个电脑控制操作。')
    return _receipt(state, action, body, perform)


def tactics_import(state, body):
    from cs2career import tactics
    from cs2career.services.matches import tactics_context, _tactics_publication
    def perform():
        if _busy(state):
            raise ValueError(_busy(state))
        if set(body) - {'revision', 'request_id', 'map', 'value'} or 'value' not in body:
            raise ValueError('战术导入只接受 value 和可选 map。')
        # Bound the nested JSON to the original editor's limit before validation.
        encoded = json.dumps(body['value'], ensure_ascii=False, allow_nan=False).encode('utf-8')
        value = tactics.decode_json(encoded)
        code = tactics.canonical_map(body['map']) if 'map' in body else None
        result = tactics.import_tactics(value, code)
        publication = _tactics_publication(state, result['map'], sync=True)
        message = publication['reason']
        return dict(tactics_context(result['map'], state, publication), reason=message, msg=message,
                    library_message='战术已导入独立库。', status='saved',
                    imported_count=result['imported_count'], overwritten_ids=result['overwritten_ids'])
    return _receipt(state, 'import', body, perform, namespace='tactics_import')
