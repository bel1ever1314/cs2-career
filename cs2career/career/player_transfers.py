"""Personal career moves, distinct from the club's player purchase market.

Commands run under ApplicationState's HTTP lock and are persisted before the
response (and therefore before any dice animation). JSON packs receive frozen
notifications; only this module may change a roster or consume a transfer.
"""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import math

from . import economy, incidents
from .transfers import identity, locked
from ..world.ability import ability_of, ensure_role_calibration, refresh_player_ability, refresh_team_command
from ..world.roles import ROLE_LABEL, PLAYABLE_ROLES


def state(career):
    value = career.personal_transfers
    if 'offers' not in value:
        value['offers'] = [dict(id=r['id'], team_id=r.get('team_id', ''), date=r.get('date', ''))
                           for r in career.inbox if r.get('kind') == 'contract']
    for key, default in [('attempts', []), ('offers', []), ('moves', []), ('hooks', []),
                         ('target_until', {}), ('apply_until', ''), ('move_until', ''),
                         ('checked_month', ''), ('pending', None), ('player_only', False)]:
        value.setdefault(key, deepcopy(default))
    return value


def after(stamp, days):
    return (date.fromisoformat(stamp) + timedelta(days=days)).isoformat()


def draw(career, key, sides):
    # Stable across re-opening the menu/reloading the same saved career; no
    # consumption of the simulation's random stream or client supplied roll.
    seed = f'{career.start_year}|{career.player_name}|{key}'
    return int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], 'big') % sides + 1


def strength(player, role):
    card = deepcopy(player)
    ensure_role_calibration(card)
    return ability_of(card['stats'], role) if card.get('stats') else float(card['ability'])


def wins(roll, modifier):
    return roll == 20 or (roll != 1 and roll + modifier >= 12)


def quote(career, season, team, role):
    you = career._you_stats(season)
    pool = [p for p in team.get('players', []) if p.get('role') == role and not p.get('you')]
    if not you or not pool or team['id'] == career.team_id:
        return None
    target = min(pool, key=lambda p: (strength(p, role), identity(p)))
    own, theirs = strength(you, role), strength(target, role)
    # Truncate toward zero: a difference below three full points gives no bonus.
    modifier = max(-8, min(6, math.trunc(round(own - theirs, 6) / 3)))
    return dict(team_id=team['id'], team=team['name'], role=role,
                replace_id=identity(target), replace=target['name'],
                ability=own, target_ability=theirs, modifier=modifier,
                chance=sum(wins(n, modifier) for n in range(1, 21)) / 20)


def blocked(career, season, team=None, applying=False, deciding=False):
    value = state(career)
    if not career.exists or career.over(): return '当前生涯不能转会。'
    if career.loan_default_pending or career.fix_pending or career.throwing or career.crisis:
        return '先处理当前的经营危机、纪律或待决事项。'
    if career.training_session: return '先结束已准备的 CS2 训练赛，再办理转会。'
    if any(r.get('choices') and r.get('when') not in ('transfer_decision',) for r in career.story_queue):
        return '先处理待决定的剧情。'
    if incidents.pending(career): return '先处理待决定的生涯事件。'
    if value['pending'] and not deciding: return '先决定当前的加盟机会，不能同时申请多队。'
    if value['move_until'] > season.date: return f"加盟锁定期至 {value['move_until']}，期间不能再次转会。"
    if applying and value['apply_until'] > season.date: return f"申请冷却至 {value['apply_until']}。"
    mine = career.my_team(season.teams)
    if (mine and locked(season, mine)) or (team and locked(season, team)):
        return '双方赛事或 CS2 对局尚未结束，暂不能变更名单。'
    if team:
        if team['id'] == career.team_id: return '你已经在这支队伍。'
        if len(team.get('players', [])) != 5: return '目标队伍不是完整五人阵容。'
        if applying and value['target_until'].get(team['id'], '') > season.date:
            return f"这支队伍暂不接受再次试训，请等到 {value['target_until'][team['id']]}。"
    return ''


def public(career, season):
    value = state(career)
    rows = []
    if career.exists and not career.over():
        for team in season.teams:
            for role in sorted({p.get('role', 'rifle') for p in team.get('players', [])}):
                item = quote(career, season, team, role)
                if item:
                    rows.append(dict(item, blocked=blocked(career, season, team, applying=True)))
    return dict(targets=rows, apply_until=value['apply_until'], move_until=value['move_until'],
                offers_this_year=sum(r['date'][:4] == season.date[:4] for r in value['offers']),
                offer_limit=4, pending=deepcopy(value['pending']),
                last_attempt=deepcopy(value['attempts'][-1]) if value['attempts'] else None,
                history=deepcopy(value['moves']), player_only=value['player_only'])


def hook(career, when, occurrence, context):
    state(career)['hooks'].append(dict(when=when, occurrence=occurrence, context=deepcopy(context)))


def drain_hooks(career, season):
    value = state(career)
    if value['pending'] or any(r.get('kind') == 'transfer' for r in career.story_queue):
        return  # Do not put an extension decision behind a blocking transfer dialog.
    while value['hooks'] and not incidents.pending(career):
        item = value['hooks'].pop(0)
        incidents.emit(career, season, item['when'], item['occurrence'], context=item['context'])


def context_for(career, season, item):
    mine = career.my_team(season.teams)
    return dict(player=career.player_name, old_team=(mine or {}).get('name', '自由市场'),
                old_team_id=career.team_id, new_team=item['team'], new_team_id=item['team_id'],
                transfer_role=item['role'], transfer_source=item.get('source', 'application'))


def decision(career, season, item):
    value = state(career)
    item = deepcopy(item)
    item['context'] = context_for(career, season, item)
    value['pending'] = item
    career.story_queue.append(dict(id='transfer-decision:' + item['id'], kind='transfer',
        when='transfer_decision', title='一份新的可能',
        text=(f"试训 D20：{item['roll']} {item['modifier']:+d} = {item['total']}，通过。\n" if 'roll' in item else '') +
             f"{item['team']} 愿意让你担任{ROLE_LABEL.get(item['role'], item['role'])}，接替 {item['replace']}。\n这不是自动离队：签字前，你仍然可以选择留下。\n正式加盟后180天不能再次转会。个人资产保留，俱乐部资金和经营权不随你离开。",
        choices=[dict(id='accept', label='接受，开启下一段生涯'), dict(id='refuse', label='留下，继续未完成的故事')]))


def apply(career, season, team_id, role):
    if role not in PLAYABLE_ROLES: raise ValueError('请选择有效位置。')
    team = next((t for t in season.teams if t['id'] == team_id), None)
    if team is None: raise ValueError('战队不存在，请刷新。')
    reason = blocked(career, season, team, applying=True)
    if reason: raise ValueError(reason)
    item = quote(career, season, team, role)
    if not item: raise ValueError('目标队伍没有这个位置，请重新选择。')
    value = state(career)
    roll = draw(career, f'apply|{season.date}|{team_id}|{role}|{len(value["attempts"])}', 20)
    success = wins(roll, item['modifier'])
    item.update(id=f'apply-{len(value["attempts"])+1}', date=season.date, roll=roll,
                total=roll+item['modifier'], success=success, source='application')
    value['attempts'].append(deepcopy(item))
    value['apply_until'] = after(season.date, 90 if success else 30)
    if not success: value['target_until'][team_id] = after(season.date, 90)
    message = f"试训 D20：{roll} {item['modifier']:+d} = {item['total']}，{'成功' if success else '未通过'}。"
    career.log.append(message)
    if success:
        decision(career, season, item)
    else:
        career.story_queue.append(dict(id='transfer-result:'+item['id'], title='这一次，还差一点',
            text=message + f"\n{team['name']} 没有发来合同。你仍在原来的位置上，接下来的训练和比赛还有意义。\n下一次申请日期：{value['apply_until']}。", when='transfer_result'))
    hook(career, 'transfer_application_success' if success else 'transfer_application_failed', item['id'], context_for(career, season, item))
    return message


def open_offer(career, season, row):
    if row.get('status') != 'open': raise ValueError('这份邀约已经处理。')
    if row.get('expires', '') and row['expires'] < season.date:
        row['status'] = 'expired'
        raise ValueError('这份邀约已过期。')
    team = next((t for t in season.teams if t['id'] == row.get('team_id')), None)
    if not team: raise ValueError('目标战队不存在。')
    reason = blocked(career, season, team)
    if reason: raise ValueError(reason)
    item = quote(career, season, team, row.get('role'))
    if not item or (row.get('replace_id') and item['replace_id'] != row['replace_id']):
        row['status'] = 'expired'
        raise ValueError('邀约对应的位置已经变化，这份邀约失效。')
    item.update(id=row['id'], source='offer', date=season.date, mail_id=row['id'])
    decision(career, season, item)
    return '球队已认可你，无需掷骰。请确认是否正式加盟。'


def resolve(career, season, row, choice):
    value = state(career)
    item = value['pending']
    if not item or row['id'] != 'transfer-decision:'+item['id']: raise ValueError('这次转会决定已经失效。')
    if choice == 'refuse':
        value['pending'] = None
        letter = career._mail(item.get('mail_id', ''))
        if letter: letter.update(status='declined', read=True)
        career.log.append(f"婉拒 {item['team']}，决定留下。")
        career.story_queue.append(dict(id='transfer-stay:'+item['id'], title='留下也是一种选择',
            text='你关掉合同，把椅子拉回训练桌前。\n队友没有追问，只递来耳机：“那就继续，下一场还等着我们。”', when='transfer_stayed'))
        hook(career, 'transfer_stayed', item['id'], item['context'])
        return
    if choice != 'accept': raise ValueError('请选择加盟或留下。')
    if item.get('mail_id'):
        letter = career._mail(item['mail_id']) or {}
        if letter.get('status') != 'open' or (letter.get('expires') and letter['expires'] < season.date):
            raise ValueError('邀约已失效，请选择留下。')
    team = next((t for t in season.teams if t['id'] == item['team_id']), None)
    if not team: raise ValueError('目标战队已不存在，请选择留下。')
    reason = blocked(career, season, team, deciding=True)
    if reason: raise ValueError(reason)
    mine = career.my_team(season.teams)
    you = career._you_stats(season)
    found = [p for p in team['players'] if identity(p) == item['replace_id'] and p.get('role') == item['role']]
    if len(found) != 1 or not you: raise ValueError('原报价的选手或位置已变化，请选择留下后再申请。')
    target = found[0]
    if mine and (len(mine['players']) != 5 or sum(identity(p) == identity(you) for p in mine['players']) != 1):
        raise ValueError('原队名单身份不唯一，暂不能转会。')
    all_ids = [identity(p) for t in season.teams for p in t['players']]
    if any(all_ids.count(pid) != 1 for pid in [identity(target)] + ([identity(you)] if mine else [])):
        raise ValueError('本次转会涉及的选手身份不唯一，暂不能转会。')
    if not mine and identity(you) in all_ids: raise ValueError('自由身选手仍占用现役位置，请先修复名单。')
    # Prepare all cards before mutation. Original club recruits an affordable
    # free player; if none exists, the two clubs exchange the displaced slot.
    # No random/fabricated IDs or partially applied rosters.
    from .career import transfer_fee
    incoming, replacement = deepcopy(you), deepcopy(target)
    reserve = None
    reserve_fee = 0
    if mine:
        eligible = [p for p in career.free if identity(p) not in all_ids and
                    p.get('role') == you.get('role', career.role) and
                    p.get('name') not in career.hidden and
                    transfer_fee(p['ability']) <= mine.get('money', 0)]
        if eligible:
            reserve = max(eligible, key=lambda p: (p['ability'], identity(p)))
            reserve_fee = transfer_fee(reserve['ability'])
            replacement = deepcopy(reserve)
    incoming.update(role=item['role'], you=True, is_igl=bool(target.get('is_igl')))
    replacement.update(role=you.get('role', career.role), you=False, is_igl=bool(you.get('is_igl')))
    refresh_player_ability(incoming)
    refresh_player_ability(replacement)
    from . import news
    news.initialize(career,season)
    old_mode = career.mode
    old_level = sum(strength(p,p['role']) for p in mine['players'])/5 if mine else 0
    team['players'] = [p for p in team['players'] if p is not target] + [incoming]
    if mine:
        mine['players'] = [p for p in mine['players'] if identity(p) != identity(you)] + [replacement]
        mine['custom_roles'] = True
        mine['career_ai_managed'] = True
        mine['career_ops_month'] = season.date[:7]
        mine['money'] -= reserve_fee
        if reserve:
            career.free = [p for p in career.free if identity(p) != identity(reserve)]
            career._player_to_free(season, target, team.get('region', 'EU'))
        if career.loan and career.loan.get('kind') == 'bank':
            mine['career_bank_loan'] = deepcopy(career.loan)
            career.loan = None
        elif career.loan:
            career.loan.setdefault('creditor_team_id', mine['id'])
        refresh_team_command(mine)
    else:
        career._player_to_free(season, replacement, team.get('region', 'EU'))
    occupied = {identity(p) for t in season.teams for p in t['players']}
    career.free = [p for p in career.free if identity(p) not in occupied]
    team['custom_roles'] = True
    team.pop('career_ai_managed', None)
    # A returning founder's bank debt remains a club liability, not a player loan.
    refresh_team_command(team)
    # Tag old invitations BEFORE changing the current club, including old v2 saves.
    career.repair_invite_teams(season)
    career.team_id, career.role, career.mode = team['id'], item['role'], 'join'
    value['pre_join_events']=[f"{season.year}:{e['id']}" for e in season.events if e.get('status')=='done']
    career.unsigned = False
    career.replaced = target['name']
    career.registered = []
    career.crisis, career.deficit = False, 0
    career.fix_rolled = ''
    career._remember_you(season)
    value['player_only'] = True
    value['pending'] = None
    value['move_until'] = after(season.date, 180)
    value['moves'].append(dict(date=season.date, **item['context'], source=item['source']))
    from . import news
    news.capture_roster(career,season)
    for letter in career.inbox:
        if letter.get('kind') in ('contract', 'invite') and letter.get('status') == 'open':
            letter['status'] = 'accepted' if letter.get('id') == item.get('mail_id') else 'expired'
            letter['read'] = True
    career.log.append(f"加盟 {team['name']}，原队继续征战。转会锁定至 {value['move_until']}。")
    if mine:
        career.log.append(f"{mine['name']} {'签下' if reserve else '与新队协商由'} {replacement['name']} 补位" +
                          (f"，俱乐部支付 ${reserve_fee:,}。" if reserve else '，双方没有额外现金交易。'))
    ctx = item['context']
    if old_mode == 'create':
        title, text = '把队名留在身后', f"你最后看了一眼 {ctx['old_team']} 的队标。那是你亲手建立的队伍，却不必成为你一生的边界。\n经营交给了俱乐部，队友仍会继续比赛。你带走的是自己的行李和记忆，不是球队的金库。"
    else:
        old_avg = old_level
        new_avg = sum(strength(p, p['role']) for p in team['players'])/5
        if new_avg >= old_avg + 5:
            title, text = '捷径，还是野心', '有人说你选择了抱团，也有人说更高的舞台值得冒险。\n旧队友看完消息，只问了一句：“你想清楚了吗？”\n外界可以替这次转会起名字，但接下来的比赛仍得由你亲手打。'
        elif draw(career, item['id']+'farewell', 2) == 1:
            title, text = '更大的舞台', '队友帮你把外设装进箱子：“去试试吧，我们不怪你。别把想去的地方一直留到以后。”\n你们约好，下次在服务器里见。'
        else:
            title, text = '一起走过的路', '训练室里少了一张椅子，群聊却没有人退出。\n那些一起熬过的加时和失败，不会因为一份新合同作废。临走前，你还有一句话想说。'
    career.story_queue.append(dict(id='transfer-farewell:'+item['id'], kind='transfer', when='transfer_farewell',
        title=title, text=text, context=ctx, choices=[dict(id='thanks', label='认真道谢，告别这一段路'),
        dict(id='promise', label='约定下次赛场见'), dict(id='quiet', label='把不舍留在心里')]))
    hook(career, 'transfer_departed', item['id'], ctx)
    hook(career, 'transfer_joined', item['id'], ctx)
    career.dispatch_invites(season)


def dispatch(career, season):
    value = state(career)
    for row in career.inbox:
        if row.get('personal_transfer') and row.get('status') == 'open' and row.get('expires', '') < season.date:
            row['status'] = 'expired'
    month = season.date[:7]
    if value['checked_month'] == month or blocked(career, season): return
    value['checked_month'] = month
    previous = [r for r in value['offers'] if r['date'][:4] == season.date[:4]]
    if len(previous) >= 4: return
    if any(r.get('kind') == 'contract' and r.get('status') == 'open' for r in career.inbox): return
    if draw(career, 'offer-month|'+month, 100) > 60: return
    options = []
    for team in season.teams:
        if team['id'] in {r['team_id'] for r in previous} or blocked(career, season, team): continue
        for role in sorted({p.get('role', 'rifle') for p in team['players']}):
            item = quote(career, season, team, role)
            if item and item['ability'] >= item['target_ability'] + 3:
                options.append(item)
    if not options: return
    levels = {t['id']:sum(strength(p,p['role']) for p in t['players'])/5 for t in season.teams if t.get('players')}
    # Prioritise the strongest genuinely interested employer, not the biggest
    # numerical gap (which would make stars receive only bottom-team offers).
    item = max(options, key=lambda r: (levels[r['team_id']], r['ability']-r['target_ability'], r['team_id'], r['role']))
    row = career._push_mail('contract', season.date,
        dict(title=f"{item['team']} 的补强邀约", **{'from':item['team']},
             body=f"我们正在寻找{ROLE_LABEL.get(item['role'], item['role'])}位置的补强，认可你的实力，愿意邀请你接替 {item['replace']}。\n接受邀约不需要掷骰，签字前仍可选择留下。有效期30天。"),
        dict(**item, personal_transfer=True, expires=after(season.date, 30), status='open'))
    value['offers'].append(dict(id=row['id'], team_id=item['team_id'], date=season.date))
    hook(career, 'transfer_offer_received', row['id'], context_for(career, season, dict(item, source='offer')))


def tick(career, season):
    dispatch(career, season)
    drain_hooks(career, season)


def settle_player_club(career, season, team, month):
    """Same wage schedule, but a signed player cannot dissolve their employer."""
    rank = next((r['rank'] for r in season.vrs.table(season.teams, season.date) if r['id'] == team['id']), 40)
    bill = economy.month_burn(team['players'], rank)
    cash = max(0, int(team.get('money', 0)))
    spent = min(cash, bill['total'])
    team['money'] = cash - spent
    team['career_ops_arrears'] = int(team.get('career_ops_arrears', 0)) + bill['total'] - spent
    wage = next((w['pay'] for w in bill['wages'] if w['name'] == career.player_name), 0) if spent == bill['total'] else 0
    career.money += wage
    career._record_cashflow(month, 'club', 'operations', '管理层结算日常开支', -spent, team['money'])
    career._record_cashflow(month, 'pocket', 'salary', '个人月薪', wage, career.money)
    career.crisis, career.deficit = False, 0
    career.ops_log.append(f"{month} 管理层结算，个人工资 ${wage:,}。" + ('本月工资未能足额发放，俱乐部保留欠款记录。' if spent < bill['total'] else ''))


def former_opponent(career, season, match_id):
    value = state(career)
    if not value['moves']: return
    for event in season.events:
        for match in event.get('matches', []):
            if match.get('id') != match_id: continue
            names = {match.get('team_a'), match.get('team_b')}
            mine = career.my_team(season.teams)
            if not mine or mine['name'] not in names: return
            for move in reversed(value['moves']):
                if move['old_team'] in names and move['old_team'] != mine['name']:
                    seen = value.setdefault('reunions', [])
                    if match_id not in seen:
                        seen.append(match_id)
                        hook(career, 'transfer_former_team', match_id, move)
                        drain_hooks(career, season)
                    return


def settle_ai_clubs(career, season, month):
    """Former player-owned teams retain their account and bank debt in world saves."""
    ranks = {r['id']:r['rank'] for r in season.vrs.table(season.teams, month+'-01')}
    for team in season.teams:
        if not team.get('career_ai_managed') and not team.get('career_bank_loan'): continue
        if team.get('career_ops_month', '') >= month: continue
        team['career_ops_month'] = month
        if team.get('career_ai_managed') and team['id'] != career.team_id:
            bill = economy.month_burn(team['players'], ranks.get(team['id'], 40))['total']
            owed = bill + int(team.get('career_ops_arrears', 0))
            paid = min(max(0, int(team.get('money', 0))), owed)
            team['money'] -= paid
            team['career_ops_arrears'] = owed - paid
        loan = team.get('career_bank_loan')
        if loan and loan.get('last_interest_month', '') < month:
            due = economy.interest_due(loan['principal'], loan['rate']) + int(loan.get('arrears', 0))
            paid = min(max(0, int(team.get('money', 0))), due)
            team['money'] -= paid
            loan.update(arrears=due-paid, last_interest_month=month)
