"""Manual-slot UI adapter; one ApplicationState, no second game ruleset."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib

from cs2career import manual_saves as storage


def _root():
    from cs2career.paths import save_root
    return save_root()


def _revision(state):
    return int(state.career.incident_state.get('career3d_service', {}).get('revision', 0))


def _blocked(state):
    if state.career.training_session:
        return '训练正在等待真实回传，请完成或取消后保存/读取。'
    if state.arena.pending:
        return '天梯/自定义比赛正在启动、等待回传或执行 RTS，请先完成或取消。'
    from cs2career.services.matches import career_cs2_pending
    if career_cs2_pending(state):
        return '职业 CS2/RTS 尚未结算，请完成或取消后保存/读取。'
    if (_root() / 'personal-transfer.pending.json').exists():
        return '生涯事务尚未提交，请重新启动恢复后再保存/读取。'
    if (_root() / 'manual-load.pending.json').exists():
        return '存档恢复事务尚未完成，请重新启动恢复。'
    return ''


def _summary(state):
    team = state.career.my_team(state.season.teams) or {}
    return dict(player=state.career.player_name, team=team.get('name', ''),
                date=state.season.date, era=str(state.season.era))


def saves_context(state):
    root = _root()
    files = [root / name for name in storage.NAMES if (root / name).is_file()]
    stamp = max((file.stat().st_mtime for file in files), default=None)
    reason = _blocked(state)
    return dict(ok=True, revision=_revision(state), current=dict(_summary(state),
                size_bytes=sum(file.stat().st_size for file in files),
                saved_at=datetime.fromtimestamp(stamp, timezone.utc).isoformat() if stamp is not None else ''),
                slots=storage.list_slots(root), blocked=bool(reason), reason=reason)


def _snapshot(state):
    season = state.season.to_json()
    return {name: storage.encode(value) for name, value in
            zip(storage.NAMES, (season, state.career.to_json(), state.arena.data))}


def _objects(payloads, root):
    """Validate and build objects off to the side, without disk writes or RNG use."""
    from cs2career.career import Career
    from cs2career.league import Season
    from cs2career.league.vrs import VRS
    from cs2career.arena import Arena
    from cs2career.random_state import _validated
    raw = {name: storage.decode(payloads[name]) for name in storage.NAMES}
    sb, cb, ab = (raw[name] for name in storage.NAMES)
    if any(not isinstance(blob, dict) or blob.get('schema_version') != 2 for blob in raw.values()):
        raise ValueError('手动存档版本不兼容，当前进度未更改。')
    s = Season.__new__(Season)
    required = ('date', 'year', 'era', 'teams', 'events', 'qualified', 'player_all', 'player_event',
                'history', 'top20', 'log')
    if any(key not in sb for key in required) or not isinstance(sb.get('vrs'), list):
        raise ValueError('手动存档赛季数据不完整。')
    if (type(sb['year']) is not int or not isinstance(sb['date'], str)
            or sb.get('era') not in ('2024', '2025', '2026')
            or any(not isinstance(sb[key], list) for key in ('teams', 'events', 'history', 'log'))
            or any(not isinstance(sb[key], dict) for key in ('qualified', 'player_all', 'player_event', 'top20'))):
        raise ValueError('手动存档赛季结构无效。')
    try:
        datetime.strptime(sb['date'], '%Y-%m-%d')
        s.vrs = VRS.from_json(sb['vrs'])
        for key in required:
            setattr(s, key, deepcopy(sb[key]))
        s.top20_dates = deepcopy(sb.get('top20_dates', {}))
        checkpoint = sb.get('random_state')
        if checkpoint is not None:
            if not isinstance(checkpoint, dict) or checkpoint.get('version') != 1:
                raise ValueError('随机进度版本无效。')
            _validated(checkpoint.get('career'))
            _validated(checkpoint.get('match'))
        c = Career()
        allowed = set(c.to_json())
        if set(cb) - allowed or not allowed.issubset(cb):
            raise ValueError('手动存档角色数据不完整或含未知字段。')
        for key, value in cb.items():
            if key != 'schema_version':
                setattr(c, key, deepcopy(value))
        if (not isinstance(c.incident_state, dict) or not isinstance(c.you_card, dict)
                or not isinstance(c.free, list) or c.era != s.era
                or not isinstance(c.story_queue, list) or not isinstance(c.inbox, list)):
            raise ValueError('手动存档角色结构无效。')
        control = c.incident_state.get('career3d_service', {})
        if (not isinstance(control, dict) or type(control.get('revision', 0)) is not int
                or control.get('revision', 0) < 0):
            raise ValueError('手动存档状态版本无效。')
        if c.exists and not c.unsigned and c.my_team(s.teams) is None:
            raise ValueError('手动存档的角色与战队不匹配。')
        if (type(ab.get('revision')) is not int or ab['revision'] < 0
                or not isinstance(ab.get('ladder'), dict) or not isinstance(ab.get('matches'), list)
                or ab.get('lobby') is not None and not isinstance(ab['lobby'], dict)):
            raise ValueError('手动存档天梯结构无效。')
        arena = Arena.__new__(Arena)
        arena.path = root / 'arena.json'
        arena.data = deepcopy(ab)
        arena._saved = deepcopy(ab)
        arena._migration_backup = False
        s.career = c
        s._role_calibration_changed = s._calendar_changed = False
        # A handcrafted/imported slot cannot introduce an unbound live match.
        pending = c.training_session or arena.pending or any(
            not m.get('played') and (m.get('cs2_session') or m.get('career3d_rts'))
            for ev in s.events for m in ev.get('matches', []))
        if pending:
            raise ValueError('这个存档包含未结算比赛，不能切换到在途身份。')
        return s, c, arena, checkpoint
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('手动存档内部数据不完整，当前进度未更改。') from exc


def _set_revision(state, revision):
    store = state.career.incident_state.setdefault('career3d_service', {'receipts': []})
    store['revision'] = revision


def saves_command(state, action, body):
    if action not in ('save', 'load', 'delete'):
        raise ValueError('没有这个存档操作。')
    request_id = body.get('request_id')
    if (not isinstance(request_id, str) or not 8 <= len(request_id) <= 100
            or any(ord(ch) < 32 for ch in request_id)):
        raise ValueError('请提供 8 至 100 字符的本次存档请求编号。')
    if action == 'save':
        label = body.get('label')
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 64:
            raise ValueError('请输入 1 至 64 字符的存档名称。')
        args = dict(label=label.strip())
    else:
        if body.get('confirm') is not True:
            raise ValueError('请先明确确认读取或删除这个手动存档。')
        storage.slot_path(_root(), body.get('id'))
        args = dict(id=body['id'], confirm=True)
    digest = hashlib.sha256(storage.encode(dict(action=action, **args))).hexdigest()
    root = _root()
    prior = storage.requests(root).get(request_id)
    if prior:
        if prior.get('hash') != digest or prior.get('action') != action:
            raise ValueError('这个请求编号已经用于其他存档操作。')
        if prior.get('status') == 'done':
            return dict(prior['result'], revision=_revision(state), replayed=True)
    from cs2career.services.business import guard_revision
    # A durable pending save/delete can finish after a crash without creating
    # another slot or deleting another target. Rolled-back loads need freshness.
    if action == 'load' or not prior or prior.get('status') != 'pending':
        guard_revision(state, body)
    if action != 'delete':
        reason = _blocked(state)
        if reason:
            raise ValueError(reason)
    revision = max(_revision(state) + 1, int((prior or {}).get('revision', 0)))
    if action == 'save':
        ident = hashlib.sha256(request_id.encode('utf-8')).hexdigest()[:32]
        record = dict(hash=digest, action=action, status='pending', revision=revision)
        storage.record_request(root, request_id, record)
        _set_revision(state, revision)
        state.persist()
        slot = storage.create_slot(root, ident, _snapshot(state),
                                   dict(_summary(state), label=args['label'], created_at=storage.now()), digest)
        result = dict(id=ident, slot=slot, reason='手动存档已保存。', revision=revision)
        storage.record_request(root, request_id, dict(record, status='done', result=result))
        return result
    if action == 'delete':
        if not prior and not storage.slot_path(root, args['id']).exists():
            raise ValueError('这个手动存档不存在。')
        record = dict(hash=digest, action=action, status='pending', revision=revision)
        storage.record_request(root, request_id, record)
        storage.delete_slot(root, args['id'])
        _set_revision(state, revision)
        # No game command or automatic points are run while deleting a slot.
        state.career.save()
        result = dict(id=args['id'], deleted=True, reason='手动存档已删除，当前进度未回退。', revision=revision)
        storage.record_request(root, request_id, dict(record, status='done', result=result))
        return result
    payloads = storage.read_slot(root, args['id'])
    season, career, arena, checkpoint = _objects(payloads, root)
    saved_revision = int(career.incident_state.get('career3d_service', {}).get('revision', 0))
    revision = max(revision, saved_revision + 1)
    career.incident_state.setdefault('career3d_service', {'receipts': []})['revision'] = revision
    arena.data['revision'] = max(state.arena.data['revision'], arena.data['revision']) + 1
    arena._saved = deepcopy(arena.data)
    payloads['career.json'] = storage.encode(career.to_json())
    payloads['arena.json'] = storage.encode(arena.data)
    result = dict(id=args['id'], loaded=True, reason='手动存档已读取。', revision=revision)
    record = dict(hash=digest, action=action, status='pending', revision=revision)
    storage.record_request(root, request_id, record)
    from cs2career.random_state import capture, restore
    old = (state.season, state.career, state.arena, capture())
    try:
        storage.begin_restore(root, payloads, request_id, digest, result)
        storage.apply_restore(root)
        # Keep the holder itself: the server and shutdown closure both refer
        # to this exact ApplicationState, not to a replaceable server.state.
        state.season, state.career, state._arena = season, career, arena
        restore(checkpoint)
        storage.commit_restore(root)
    except Exception:
        journal = root / 'manual-load.pending.json'
        committed = journal.exists() and storage.decode(journal.read_bytes()).get('phase') == 'committed'
        committed = committed or storage.requests(root).get(request_id, {}).get('status') == 'done'
        if not committed:
            try:
                storage.recover(root)
            finally:
                state.season, state.career, state._arena = old[:3]
                restore(old[3])
        raise
    return result
