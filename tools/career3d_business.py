"""Read projections and small adapters for existing career business rules.

No independent finance/transfer/news ledger lives here. Caller owns the same
ApplicationState and HTTP lock used by the original career commands.
"""
from copy import deepcopy
from datetime import date
import math

NEWS_CATEGORIES = ('news', 'awards', 'top20', 'transfer')
NEWS_PAGE_SIZE = 20


def guard_revision(state, body):
    revision = int(state.career.incident_state.get('career3d_service', {}).get('revision', 0))
    if type(body.get('revision')) is not int or body['revision'] != revision:
        raise ValueError('生涯状态已变化，请刷新后再操作。')


def guard_roster(state):
    if state.career.training_session:
        raise ValueError('训练对局正在等待真实回传，请先录入训练战绩。')
    if state.arena.pending:
        raise ValueError('天梯比赛正在启动或等待真实回传，暂时不能改变选手身份、阵容或能力。')
    from tools.career3d_matches import career_cs2_pending
    if career_cs2_pending(state):
        raise ValueError('职业比赛正在等待真实回传，暂时不能改变选手身份、阵容或能力。')


def mail_detail(state, key):
    """Exact original mailbox row; reading does not mark it read or expire it."""
    row = next((r for r in state.career.inbox if r.get('id') == key), None)
    if not row:
        return None
    return dict(deepcopy(row), **mail_actions(state, row))


def mail_actions(state, row):
    """Explicit mail/choice routes; an invite is never a transfer application."""
    kind, opened = row.get('kind'), row.get('status') == 'open'
    pending = state.career.personal_transfers.get('pending') or {}
    deciding = kind == 'contract' and pending.get('mail_id') == row.get('id')
    decision_id = 'transfer-decision:' + str(pending.get('id', '')) if deciding else ''
    return dict(accept_action='/api/3d/mail/accept' if opened and kind in ('invite', 'contract', 'whisper') else '',
                decline_action='/api/3d/mail/decline' if opened and kind in ('invite', 'contract', 'whisper') else '',
                decision_pending=bool(deciding), decision_id=decision_id,
                action_kind='transfer_decision' if kind == 'contract' else
                    'event_registration' if kind == 'invite' else 'discipline' if kind == 'whisper' else 'read_only')


def mail_command(state, action, body):
    """One validated dispatcher shared by phone mail and computer contracts."""
    if action not in ('accept', 'decline'):
        raise ValueError('没有这个邮件操作。')
    guard_revision(state, body)
    mail_id = body.get('id')
    row = state.career._mail(mail_id) if isinstance(mail_id, str) else None
    if not row or row.get('kind') not in ('invite', 'contract', 'whisper'):
        raise ValueError('这封邮件没有可接受或婉拒的邀请。')
    c, s = state.career, state.season
    if row.get('status') != 'open':
        # Safe replay of exactly the same decision, never changing registration.
        if row.get('status') == ('accepted' if action == 'accept' else 'declined'):
            return dict(reason='这封邀请已经按你的选择处理。', replayed=True,
                        mail_id=mail_id, mail_kind=row['kind'], **mail_actions(state, row))
        raise ValueError('这封邀请已经处理或失效，请刷新。')
    method = 'accept_invite' if action == 'accept' else 'decline_invite'
    if row['kind'] == 'contract':
        guard_roster(state)
        if action == 'accept' and (c.personal_transfers.get('pending') or {}).get('mail_id') == mail_id:
            message = c.accept_contract(s, mail_id)
            return dict(reason=message, mail_id=mail_id, mail_kind=row['kind'], replayed=True,
                        **mail_actions(state, row))
        message = state.personal_command(lambda career, season: getattr(career, method)(season, mail_id))
    else:
        # Tournament registration is not roster movement. A pending employer
        # choice cannot turn an event invitation into apply()/open_offer().
        if row['kind'] == 'whisper':
            guard_roster(state)
        message = getattr(c, method)(s, mail_id, persist=False) if row['kind'] == 'invite' else getattr(c, method)(s, mail_id)
    current = state.career._mail(mail_id) or row
    return dict(reason=message, mail_id=mail_id, mail_kind=row['kind'], **mail_actions(state, current))


def inbox_rows(state):
    rows = [r for r in state.career.inbox if r.get('kind') != 'news' and not
            (r.get('kind') == 'notification' and (r.get('notification') or {}).get('kind') in ('awards', 'top20'))]
    selected = rows[-40:]
    for row in rows:
        if row.get('kind') == 'contract' and row.get('status') == 'open' and row not in selected:
            selected.append(row)
    pending = (state.career.personal_transfers.get('pending') or {}).get('mail_id')
    indexes = {r['id']: index for index, r in enumerate(rows)}
    return sorted(selected, key=lambda r: (r['id'] == pending,
                  r.get('kind') == 'contract' and r.get('status') == 'open', indexes[r['id']]), reverse=True)


def business_context(state):
    from cs2career.career import transfers, player_transfers
    c, s = state.career, state.season
    team = c.my_team(s.teams)
    table = {r['id']: r for r in s.vrs.table(s.teams, s.date)}
    ops = c._ops_public(s, team, table)
    finance = deepcopy(ops.pop('finance'))
    loan = c._loan_public(s, team, table)
    # public() initializes compatibility defaults. Do so on a private copy so
    # opening a device does not mutate missing keys or award a transfer offer.
    personal = player_transfers.public(deepcopy(c), s)
    personal['offers'] = deepcopy([r for r in c.inbox if r.get('kind') == 'contract'][-20:][::-1])
    from tools.career3d_matches import career_cs2_pending
    pending = bool(c.training_session) or state.arena.pending or career_cs2_pending(state)
    reason = ('真实比赛正在启动或等待回传，暂时不能改变阵容。' if pending else
              '你是签约选手，俱乐部引援由管理层负责。' if personal['player_only'] else
              '当前生涯不能签约。' if c.over() or c.unsigned or not team else
              '赛事进行中，结束后再转会。' if transfers.locked(s, team) else '')
    candidates = transfers.candidates(c, s)
    if pending:
        candidates = [dict(row, blocked=reason) for row in candidates]
        personal['targets'] = [dict(row, blocked=reason) for row in personal['targets']]
    roster = [deepcopy(p) for p in (team or {}).get('players', [])
              if not p.get('you') and p.get('player_id') != state.arena.career_player_id(state)]
    operations = dict(ops, loan=loan, player_only=personal['player_only'], unsigned=c.unsigned,
        banned=c.banned, retired=c.retired, crisis=c.crisis, deficit=c.deficit,
        upgrade_supported=False, upgrade_reason='原业务尚无设施升级功能；本样板不新增经营数值规则。')
    return dict(finance=finance, operations=operations,
                transfers=dict(players=candidates, roster=roster, club_money=(team or {}).get('money', 0),
                               club_allowed=not reason, reason=reason),
                player_transfers=personal, news=news_page(state, summaries=True, page_size=8))


def operations_command(state, action, body):
    guard_revision(state, body)
    if action not in ('borrow', 'repay', 'donate'):
        raise ValueError('原经营业务没有这个操作。')
    amount = body.get('amount')
    if type(amount) is not int or amount <= 0:
        raise ValueError('金额必须是正整数。')
    c, s = state.career, state.season
    team = c.my_team(s.teams)
    if not team or c.unsigned:
        raise ValueError('你现在没有俱乐部，不能办理这项经营操作。')
    if action == 'borrow':
        if c.banned or c.loan_default_pending:
            raise ValueError('请先处理禁赛或贷款最后通牒。')
        if c.loan and int(c.loan.get('principal') or 0) > 0:
            raise ValueError('先还清这一笔，才能再借。')
        cap = c._loan_cap(s)
        if amount > cap or cap <= 0:
            raise ValueError(f'当前最多能借 ${cap:,}。')
    else:
        if amount > c.money:
            raise ValueError('个人口袋资金不足。')
        if action == 'repay' and (c.loan_default_pending or not c.loan or int(c.loan.get('principal') or 0) <= 0):
            raise ValueError('没有可偿还的贷款，或必须先处理最后通牒。')
    return {'reason': getattr(c, action)(s, amount)}


def transfer_command(state, action, body):
    from cs2career.career import transfers, player_transfers
    guard_revision(state, body)
    guard_roster(state)
    c, s = state.career, state.season
    if action == 'apply':
        team_id, role = str(body.get('team_id') or ''), str(body.get('role') or '')
        team = next((t for t in s.teams if t['id'] == team_id), None)
        if not team:
            raise ValueError('战队不存在，请刷新。')
        # This original checker initializes defaults, so preflight is copy-only.
        reason = player_transfers.blocked(deepcopy(c), s, team, applying=True)
        if reason:
            raise ValueError(reason)
        if not player_transfers.quote(c, s, team, role):
            raise ValueError('目标队伍没有这个有效位置，请重新选择。')
        message = state.personal_command(lambda career, season: player_transfers.apply(career, season, team_id, role))
        return {'reason': message, 'transfer': deepcopy(state.career.personal_transfers['attempts'][-1])}
    if action != 'buy':
        raise ValueError('没有这个转会操作。')
    mine = c.my_team(s.teams)
    if c.personal_transfers.get('player_only'):
        raise ValueError('你是签约选手，俱乐部引援由管理层负责。')
    if not mine or c.unsigned or c.over():
        raise ValueError('当前生涯不能签约。')
    target_id, seller_id = str(body.get('player_id') or ''), str(body.get('seller_id') or '')
    replace_id, mode = str(body.get('replace_id') or ''), body.get('mode', 'normal')
    if not replace_id:
        raise ValueError('请先选择一名要替换的队友。')
    transfers.outgoing(c, mine, replace_id)
    candidates = transfers.candidates(c, s)
    row = next((r for r in candidates if r['player_id'] == target_id and r['seller_id'] == seller_id), None)
    if not row:
        raise ValueError('选手或卖方身份已变化，请刷新报价。')
    if row['blocked']:
        raise ValueError(row['blocked'])
    if mode not in ('normal', 'guaranteed') or (mode == 'normal' and seller_id):
        raise ValueError('普通谈判仅支持自由球员；现役选手请使用保签买断。')
    fee = row['normal_fee'] if mode == 'normal' else row['guaranteed_fee']
    expected = body.get('fee')
    if expected is not None and (type(expected) is not int or expected != fee):
        raise ValueError('报价已变化，请刷新后确认。')
    if mine.get('money', 0) < fee:
        raise ValueError('俱乐部资金不足。')
    if mode == 'normal' and not row['normal_chance']:
        raise ValueError('当前球队条件不足，选手不接受普通谈判。')
    if mode == 'guaranteed':
        message = transfers.guaranteed(c, s, target_id, seller_id, replace_id, expected)
    else:
        message = c.buy(s, row['name'], replace_id, target_id)
    return {'reason': message}


def _category(row):
    payload = row.get('notification') or row
    kind = payload.get('kind') or row.get('kind')
    if kind in ('awards', 'top20'):
        return kind
    if kind == 'transfer' or str(payload.get('when', '')).startswith('transfer_'):
        return 'transfer'
    return 'news'


def news_rows(state):
    """Saved publications only. Never tick reports, reconcile mail or rank live."""
    from cs2career.career.notifications import _body
    from cs2career.presentation import events, route_key
    c, s = state.career, state.season
    archive = c.incident_state.get('arcs', {}).get('history', [])
    saved = [(r, 'publication_archive') for r in archive if r.get('publication_key')
             or str(r.get('id', '')).startswith(('news:', 'major-report:', 'arc-notice:'))]
    saved += [(r, 'mail') for r in c.inbox if r.get('kind') == 'news' or
              (r.get('kind') == 'notification' and (r.get('notification') or {}).get('kind') in ('awards', 'top20'))]
    saved += [(r, 'story') for r in c.story_queue if r.get('kind') in ('awards', 'top20')]
    grouped, aliases, fingerprints = {}, {}, {}
    for original, source in saved:
        row = deepcopy(original)
        payload = row.get('notification') or row
        stamp = str(row.get('date') or payload.get('date') or '')
        # Existing active award stories omit date. Read their completed event's
        # date; never stamp an undated archived article with the current day.
        if not stamp and source == 'story' and payload.get('kind') == 'top20' and payload.get('year'):
            stamp = f"{int(payload['year'])}-12-31"
        if not stamp and source == 'story' and payload.get('kind') == 'awards':
            event = next((e for e in s.events if payload.get('id') == 'awards.' + e['id'] and e.get('status') == 'done'), None)
            stamp = (event.get('dates') or [''])[-1] if event else ''
        if stamp and stamp > s.date:
            continue
        title = row.get('title') or payload.get('title') or ('年度 Top20' if payload.get('kind') == 'top20' else '')
        text = row.get('text') or row.get('body') or payload.get('text') or _body(payload)
        publication = row.get('publication_key') or payload.get('publication_key') or ''
        canonical = publication or row.get('notification_id') or row.get('id') or ''
        if not canonical:
            continue
        fingerprint = (stamp, title, text)
        canonical = aliases.get(canonical) or fingerprints.get(fingerprint) or canonical
        aliases[row.get('id', canonical)] = canonical
        fingerprints[fingerprint] = canonical
        if canonical in grouped:
            grouped[canonical]['aliases'].append(row.get('id', canonical))
            # Archive owns frozen text; a mail may also own richer award payload.
            if payload.get('kind') in ('awards', 'top20'):
                grouped[canonical].update({k: deepcopy(v) for k, v in payload.items() if k in
                    ('kind', 'year', 'event', 'short', 'class', 'champion', 'mvp', 'evp', 'five', 'rows', 'sections')})
            continue
        detail = {**deepcopy(payload), 'id': canonical, 'date': stamp, 'title': title, 'text': text,
                  'category': _category(row), 'source': source, 'publication_key': publication,
                  'event_id': row.get('event_id') or payload.get('event_id') or '',
                  'aliases': [row.get('id', canonical)]}
        detail.pop('notification', None)
        grouped[canonical] = detail
    # Completed event awards are public frozen facts even when the career
    # player did not participate. No prose generator or current roster lookup.
    for event in events(s):
        stamp = (event.get('dates') or [event.get('date', '')])[-1]
        award = event.get('awards') or {}
        if event.get('status') != 'done' or not stamp or stamp > s.date or not award:
            continue
        eid = event['id']  # Year-qualified read route, not recurring engine ID.
        saved_award = next((r for r in grouped.values() if r['category'] == 'awards' and
            (r.get('event_id') == eid or (r.get('event') == event['name'] and r['date'][:4] == event['route_year']))), None)
        links = [route_key(event['route_year'], m['id']) for m in event.get('matches', []) if m.get('played')]
        if saved_award:
            saved_award.update(event_id=eid, awards=deepcopy(award), match_ids=links)
            continue
        payload = dict(kind='awards', event=event['name'], champion=event.get('champion', ''),
                       **{key: deepcopy(award.get(key)) for key in ('mvp', 'evp', 'five')})
        key = 'event-awards:' + eid
        grouped[key] = dict(payload, id=key, date=stamp, title=event['name'] + ' · 赛事荣誉记录',
            text=_body(payload), category='awards', source='completed_event', record_only=True,
            event_id=eid, publication_key='', awards=deepcopy(award), match_ids=links, aliases=[])
    # Final lists with frozen features are already-published season records,
    # not the current provisional board. Do not call feature_report on a GET.
    for year, rows in s.top20.items():
        stamp, key = f'{year}-12-31', 'top20.' + str(year)
        if stamp > s.date or key in grouped:
            continue
        payload = dict(kind='top20', year=int(year), rows=deepcopy(rows))
        grouped[key] = dict(payload, id=key, date=stamp, title=f'{year} 年度 Top20', text=_body(payload),
                            category='top20', source='final_top20', publication_key='', event_id='', aliases=[])
    return sorted(grouped.values(), key=lambda r: (r['date'], r['id']), reverse=True)


def news_page(state, page=1, category='all', month='', summaries=False, page_size=NEWS_PAGE_SIZE):
    if type(page) is not int or page < 1:
        raise ValueError('新闻页码必须是正整数。')
    if category != 'all' and category not in NEWS_CATEGORIES:
        raise ValueError('没有这个新闻分类。')
    if month:
        try:
            valid = date.fromisoformat(month + '-01').strftime('%Y-%m') == month
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise ValueError('月份必须是 YYYY-MM。')
    all_rows = news_rows(state)
    rows = [r for r in all_rows if (category == 'all' or r['category'] == category)
            and (not month or r['date'].startswith(month))]
    selected = deepcopy(rows[(page - 1) * page_size:page * page_size])
    if summaries:
        selected = [{k: r.get(k, '') for k in ('id', 'date', 'title', 'category', 'kind', 'event_id', 'source')}
                    | {'text': r['text'][:320]} for r in selected]
    return dict(ok=True, rows=selected, page=page, page_size=page_size, pages=max(1, math.ceil(len(rows) / page_size)),
                total=len(rows), months=sorted({r['date'][:7] for r in all_rows if r['date']}, reverse=True),
                categories=list(NEWS_CATEGORIES), category=category, month=month)


def news_detail(state, key):
    return next((r for r in news_rows(state) if r['id'] == key or key in r['aliases']), None)


def players_page(state, span='season', page=1, search=''):
    """The original season board uses Top30 opponents, not all-map averages."""
    if span != 'season' or type(page) is not int or page < 1:
        raise ValueError('榜单本轮仅支持 season 范围，页码必须是正整数；单人资料支持其他范围。')
    from cs2career.presentation import saved_players
    identities = {}
    for player, team, _stamp in saved_players(state):
        identities.setdefault((team, player.get('name')), set()).add(player.get('player_id') or '')
    rows = []
    for original in state.season.ratings_vs_field():
        ids = identities.get((original['team'], original['player']), set())
        row = dict(original, player_id=next(iter(ids)) if len(ids) == 1 and all(ids) else '')
        if not search or search.casefold() in (row['player'] + ' ' + row['team']).casefold():
            rows.append(row)
    size = 20
    return dict(ok=True, rows=rows[(page - 1) * size:page * size], page=page, page_size=size,
                pages=max(1, math.ceil(len(rows) / size)), total=len(rows), range=span, scope='top30',
                note='本赛季对 VRS Top30 对手的已记录地图；无样本不列入。')


def player_detail_projection(state, detail):
    """Add live position views without changing players or historical records.

    ``presentation.inspect`` has already resolved the identity. Never resolve a
    missing stable ID by name: that could attach another player's attributes.
    Match summary/range/pagination remain the original saved-map projection.
    """
    if not detail:
        return detail
    result = deepcopy(detail)
    if result.get('historical') or 'position_views' in result:
        return result
    from cs2career.presentation import current_players
    from cs2career.world.ability import playing_ability, playing_stats, position_views
    ident = result.get('player_id')
    if ident:
        candidates = [p for p, _team in current_players(state) if p.get('player_id') == ident]
    else:
        candidates = [p for p, _team in current_players(state) if p.get('name') == result.get('name')]
    if len(candidates) != 1:
        return result
    player = candidates[0]
    result.update(stats=playing_stats(player), ability=playing_ability(player),
                  position_views=position_views(player))
    return result
