"""Offline isolated HTTP checks for the 3D business adapters, never a game."""
from copy import deepcopy
from datetime import date, timedelta
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import threading
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.career3d_service import isolate, handler_class, DEMO_SEED


def run(folder):
    isolate(folder / 'data')
    def audit(event, args):
        if event not in ('open', 'os.scandir') or not args or not isinstance(args[0], (str, Path)):
            return
        target = Path(args[0]).resolve()
        if any(target == base or target.is_relative_to(base) for base in (ROOT / 'save', ROOT / 'extensions')):
            raise RuntimeError('Business verification forbids official save/extension access')
    sys.addaudithook(audit)
    from cs2career.application import ApplicationState
    from cs2career.web.server import create_server
    from cs2career.engine.match import RNG
    from cs2career.career import news, player_transfers, transfers
    from cs2career import cs2
    from cs2career.cs2 import launch
    from tools.career3d_business import business_context
    random.seed(DEMO_SEED)
    RNG.seed(DEMO_SEED)
    state = ApplicationState()
    state.create_career(dict(era='2026', mode='create', origin='academy', name='Career3D',
                             org='Morning Academy', region='AS', role='rifle'))
    server = create_server(state, port=0)
    server.RequestHandlerClass, server.game_disabled, server.display_hour = handler_class(), True, 8
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checks = []

    def api(path, body=None, expected=200, token=True):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['X-Career-Token'] = server.token
        request = Request(f'http://127.0.0.1:{server.server_port}' + path,
                          None if body is None else json.dumps(body).encode(), headers)
        try:
            with urlopen(request, timeout=20) as response:
                status, value = response.status, json.loads(response.read())
        except HTTPError as exc:
            status, value = exc.code, json.loads(exc.read())
        assert status == expected, (path, status, value)
        return value

    def context():
        return api('/api/3d/context')

    def command(path, **body):
        return api(path, {'revision': context()['calendar']['revision'], **body})

    def hashes():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (folder / 'data' / 'save').glob('*.json')}

    def reject(path, **body):
        before = hashes()
        result = api(path, {'revision': context()['calendar']['revision'], **body}, expected=400)
        assert not result['ok'] and hashes() == before
        return result

    with patch.object(launch, 'start_match', side_effect=AssertionError('Actual game launch forbidden')), \
         patch.object(cs2, 'read_result', side_effect=AssertionError('Unexpected result ingestion')):
        try:
            initial = context()
            before, defaults = hashes(), deepcopy(state.career.personal_transfers)
            for _ in range(3):
                current = context()
                api('/api/3d/news')
                api('/api/3d/players?span=season')
                api('/api/3d/player?id=' + quote(initial['player']['id']) + '&span=all&page=2')
            assert hashes() == before and defaults == state.career.personal_transfers
            assert not initial['news']['rows'] and not api('/api/3d/players')['rows']
            ops, team = initial['operations'], state.career.my_team(state.season.teams)
            table = {r['id']: r for r in state.season.vrs.table(state.season.teams, state.season.date)}
            original = state.career._ops_public(state.season, team, table)
            assert initial['finance'] == original['finance']
            assert ops['loan'] == state.career._loan_public(state.season, team, table)
            assert not ops['upgrade_supported']
            assert len(initial['transfers']['roster']) == 4
            assert initial['transfers']['players'] == transfers.candidates(state.career, state.season)
            assert initial['player_transfers']['targets'] == player_transfers.public(deepcopy(state.career), state.season)['targets']
            checks.append('GET models preserve original finance/loan/candidate/target rules; no reads mutate saves/defaults or invent news/stats/upgrades')

            for path in ('/api/3d/news?page=0', '/api/3d/news?month=2026-99', '/api/3d/news?category=future',
                         '/api/3d/player?id=x&span=invalid', '/api/3d/player?id=x&page=-1', '/api/3d/players?span=all'):
                api(path, expected=400)
            api('/api/3d/news?id=missing', expected=404)
            api('/api/3d/players', token=False, expected=403)
            api('/api/3d/news', token=False, expected=403)
            checks.append('query bounds, unknown IDs and token requirements enforced')

            state.career.money = 1_000_000  # Explicit isolated fixture funding.
            state.persist()
            before = context()
            for amount in (0, -1, True, '100', 10**12):
                reject('/api/3d/ops/borrow', amount=amount)
            reject('/api/3d/ops/borrow', amount=100, revision=-1)
            command('/api/3d/ops/borrow', amount=1000)
            borrowed = context()
            assert borrowed['operations']['loan']['principal'] == 1000
            assert borrowed['club_money'] == before['club_money'] + 1000  # Founder: bank -> club.
            assert borrowed['personal_money'] == before['personal_money']
            reject('/api/3d/ops/borrow', amount=100)
            command('/api/3d/ops/repay', amount=1100)
            repaid = context()
            assert repaid['personal_money'] == before['personal_money'] - 1000  # No oversized refund.
            assert not repaid['operations']['loan']['active']
            pocket, club = repaid['personal_money'], repaid['club_money']
            command('/api/3d/ops/donate', amount=400)
            assert context()['personal_money'] == pocket - 400 and context()['club_money'] == club + 400
            reject('/api/3d/ops/upgrade', amount=100)
            checks.append('borrow/repay/donate call original commands; bank destination, personal repayment, no free refund, no unsupported upgrade')

            team['money'] = 20_000_000  # Controlled isolated manager fixture.
            state.persist()
            def buy_body(row, mode='guaranteed'):
                roster = context()['transfers']['roster']
                return dict(player_id=row['player_id'], seller_id=row['seller_id'], replace_id=roster[0]['player_id'],
                            mode=mode, fee=row['normal_fee'] if mode == 'normal' else row['guaranteed_fee'])
            row = next(r for r in context()['transfers']['players'] if not r['seller_id'] and r['normal_chance'] and not r['blocked'])
            body = buy_body(row, 'normal')
            old_ids = {p['player_id'] for p in team['players']}
            cash = team['money']
            with patch('cs2career.career.career.random.random', return_value=1.0):
                command('/api/3d/transfers/buy', **body)
            assert team['money'] == cash - row['negotiation_fee'] and {p['player_id'] for p in team['players']} == old_ids
            body = buy_body(row, 'normal')
            cash = team['money']
            with patch('cs2career.career.career.random.random', return_value=0.0):
                command('/api/3d/transfers/buy', **body)
            assert len(team['players']) == 5 and row['player_id'] in {p['player_id'] for p in team['players']}
            assert team['money'] == cash - row['normal_fee']
            assert sum(p.get('you', False) for p in team['players']) == 1
            row = next(r for r in context()['transfers']['players'] if not r['seller_id'] and not r['blocked'])
            body = buy_body(row)
            reject('/api/3d/transfers/buy', **{**body, 'fee': row['guaranteed_fee'] + 1})
            reject('/api/3d/transfers/buy', **{**body, 'replace_id': initial['player']['id']})
            cash = team['money']
            command('/api/3d/transfers/buy', **body)
            assert team['money'] == cash - row['guaranteed_fee'] and len(team['players']) == 5
            checks.append('normal negotiation success/refusal fees and guaranteed free signing use original rules; stale quote/self replacement rejected')

            row = next(r for r in context()['transfers']['players'] if r['seller_id'] and not r['blocked'])
            seller = next(t for t in state.season.teams if t['id'] == row['seller_id'])
            seller_before = {p['player_id'] for p in seller['players']}
            cash = team['money']
            command('/api/3d/transfers/buy', **buy_body(row))
            assert team['money'] == cash - row['guaranteed_fee'] and len(seller['players']) == len(team['players']) == 5
            assert row['player_id'] not in {p['player_id'] for p in seller['players']}
            assert len(seller_before & {p['player_id'] for p in seller['players']}) == 4
            all_ids = [p['player_id'] for t in state.season.teams for p in t['players']]
            assert len(all_ids) == len(set(all_ids))
            checks.append('active buyout uses original seller same-role reserve and stable five-person identities on both sides')

            # Clear only fixture initial decisions, then apply actual original rules.
            while state.career.story_queue:
                row = state.career.story_queue[0]
                api('/api/3d/story', dict(id=row['id'], choice=(row.get('choices') or [{}])[0].get('id', '')))
            targets = context()['player_transfers']['targets']
            target = next(r for r in targets if not r['blocked'])
            body = dict(team_id=target['team_id'], role=target['role'])
            with patch.object(player_transfers, 'draw', return_value=1):
                failed = command('/api/3d/transfers/apply', **body)
            assert failed['transfer']['roll'] == 1 and not failed['transfer']['success']
            until = failed['context']['player_transfers']['apply_until']
            assert until == (date.fromisoformat(state.season.date) + timedelta(days=30)).isoformat()
            reject('/api/3d/transfers/apply', **body)
            state.career.personal_transfers['apply_until'] = ''  # New fixture window, not demo calendar logic.
            state.career.personal_transfers['target_until'] = {}
            state.career.story_queue = []
            with patch.object(player_transfers, 'draw', return_value=20):
                success = command('/api/3d/transfers/apply', **body)
            assert success['transfer']['success'] and success['context']['player_transfers']['pending']
            assert success['context']['team']['id'] == team['id']
            reject('/api/3d/transfers/apply', **body)
            decision = next(r for r in state.career.story_queue if r.get('when') == 'transfer_decision')
            api('/api/3d/story', dict(id=decision['id'], choice='refuse'))
            assert not context()['player_transfers']['pending'] and context()['team']['id'] == team['id']
            checks.append('personal application original D20, failure 30-day cooldown, success pending choice, no auto-transfer and explicit refuse')

            state.career.personal_transfers['apply_until'] = ''
            state.career.story_queue = []
            target = next(r for r in context()['player_transfers']['targets'] if not r['blocked'])
            offer = state.career._push_mail('contract', state.season.date, dict(title='隔离测试真实 Offer 格式', body='test offer'),
                dict(**target, personal_transfer=True, expires=(date.fromisoformat(state.season.date)+timedelta(days=30)).isoformat(), status='open'))
            state.persist()
            assert offer['id'] in {r['id'] for r in context()['player_transfers']['offers']}
            with patch.object(player_transfers, 'draw', side_effect=AssertionError('Offer must not roll D20')):
                api('/api/3d/mail/accept', dict(id=offer['id']))
            assert context()['player_transfers']['pending']['source'] == 'offer'
            pocket = state.career.money
            decision = next(r for r in state.career.story_queue if r.get('when') == 'transfer_decision')
            api('/api/3d/story', dict(id=decision['id'], choice='accept'))
            moved = context()
            assert moved['team']['id'] == target['team_id'] and moved['personal_money'] == pocket
            assert moved['player']['id'] == initial['player']['id'] and moved['operations']['player_only']
            assert moved['player_transfers']['move_until'] == (date.fromisoformat(state.season.date)+timedelta(days=180)).isoformat()
            assert not moved['transfers']['club_allowed']
            reject('/api/3d/transfers/buy', **body)
            reject('/api/3d/transfers/apply', team_id=team['id'], role='rifle')
            assert len(state.career.my_team(state.season.teams)['players']) == len(team['players']) == 5
            checks.append('existing offer needs no dice; phone mail/story transaction commits player identity, preserves pocket, five rosters and 180-day signed-player lock')

            # Publish fixture text using the existing writer, then read unchanged.
            for i in range(23):
                news.publish(state.career, state.season, f'fixture-report:{i:02d}', f'已保存报道 {i}',
                    '全文记录 ' + str(i) + '\n' + '原稿细节。' * 120, sections=[dict(id='saved', title='原稿小节', items=[dict(text='保存事实')])])
            award = dict(id='fixture-award', name='隔离已结束赛事', short='Test', type='t1', champion=moved['team']['name'],
                awards=dict(mvp=dict(player=initial['player']['name'], team=moved['team']['name'], rating=1.25, title='T1 MVP'),
                            evp=[dict(player='fixture EVP', team='test', rating=1.2, title='T1 EVP')], five=[]))
            state.career.story_queue.append(state.career._awards_reveal(state.season, award))
            state.career.story_queue.append(dict(id='top20.2025', kind='top20', when='top20', year=2025,
                rows=[dict(rank=1, player=initial['player']['name'], feature=dict(title='保存专栏', sections=[dict(heading='原文', text='不重写的专栏全文')]))]))
            state.career.incident_state['arcs']['history'].append(dict(id='news:future-fixture', date='2099-01-01', publication_key='future-fixture', title='未来不能展示', text='future'))
            state.persist()
            inbox_before = deepcopy(state.career.inbox)
            before = hashes()
            first = api('/api/3d/news')
            second = api('/api/3d/news?page=2')
            assert first['total'] >= 25 and first['page_size'] == 20 and second['rows']
            assert not any(r['title'] == '未来不能展示' for r in first['rows'] + second['rows'])
            detail = api('/api/3d/news?id=fixture-report:00')['detail']
            assert len(detail['text']) > 600 and detail['sections'][0]['items'][0]['text'] == '保存事实'
            by_mail = next(r for r in state.career.inbox if r.get('publication_key') == 'fixture-report:00')
            assert api('/api/3d/news?id=' + quote(by_mail['id']))['detail']['id'] == detail['id']
            awards = api('/api/3d/news?category=awards')['rows']
            top20 = api('/api/3d/news?category=top20')['rows']
            assert awards[0]['mvp']['rating'] == 1.25 and awards[0]['evp'][0]['title'] == 'T1 EVP'
            assert top20[0]['year'] == 2025 and top20[0]['rows'][0]['feature']['sections'][0]['text'] == '不重写的专栏全文'
            month = state.season.date[:7]
            assert api('/api/3d/news?month=' + month)['total'] == first['total']
            assert hashes() == before and state.career.inbox == inbox_before
            checks.append('saved full news deduplicated archive/mail, 20-row paging/month/category/ID detail, award payload and frozen Top20 feature; no future or mail consumption')

            # A completed event the player never joined is still public fact.
            event = deepcopy(award)
            event.update(year=state.season.year, dates=[state.season.date, state.season.date], status='done', matches=[])
            state.season.events.append(event)
            future = deepcopy(event)
            future.update(id='fixture-future-award', dates=['2099-01-01', '2099-01-02'])
            state.season.events.append(future)
            before = hashes()
            rows = api('/api/3d/news?category=awards')['rows']
            # The original notification must merge with the completed facts.
            assert len([r for r in rows if r.get('event') == event['name']]) == 1
            record = next(r for r in rows if r.get('event') == event['name'])
            assert record['event_id'] == '2026::fixture-award' and record['awards']['mvp']['rating'] == 1.25
            assert not any(r.get('event_id') == '2026::fixture-future-award' for r in rows)
            event2 = deepcopy(event)
            event2.update(id='fixture-other-award', name='本人未参赛的已完赛赛事')
            state.season.events.append(event2)
            records = api('/api/3d/news?category=awards')['rows']
            actual = next(r for r in records if r.get('event_id') == '2026::fixture-other-award')
            assert actual['source'] == 'completed_event' and actual['record_only']
            assert hashes() == before
            state.season.events = [e for e in state.season.events if e['id'] not in ('fixture-award', 'fixture-future-award', 'fixture-other-award')]
            checks.append('nonparticipating completed awards are frozen fact records, stable year-qualified ID, notification dedup and no future end dates')

            # Positive statistics come from the real simulator, not list names.
            from tools.career3d_activities import _simulate
            ranks = state.season.vrs.table(state.season.teams, state.season.date)
            a, b = [next(t for t in state.season.teams if t['id'] == row['id']) for row in ranks[:2]]
            mp = _simulate(a, b, 'dust2', 'business-stat-fixture')
            fixture_match = dict(id='fixture-stat', date=state.season.date, played=True, team_a=a['name'], team_b=b['name'],
                                 series='1-0' if mp['winner'] == a['name'] else '0-1', winner=mp['winner'], maps=[mp])
            state.season.events[0].setdefault('matches', []).append(fixture_match)
            before = hashes()
            players = api('/api/3d/players?span=season')
            assert players['scope'] == 'top30' and players['total'] == 10
            row = players['rows'][0]
            assert row['player_id'] and row['maps'] == 1 and row['rounds'] == mp['rounds']
            detail = api('/api/3d/player?id=' + quote(row['player_id']) + '&span=30d&page=1')['detail']
            assert detail['summary']['maps'] == 1 and detail['summary']['rating'] is not None
            assert detail['records'][0]['match_id'].endswith('::fixture-stat') and detail['total'] == 1
            assert api('/api/3d/player?id=' + quote(row['player_id']) + '&span=all&page=2')['detail']['records'] == []
            assert api('/api/3d/players?search=' + quote(row['player']))['rows'][0]['player_id'] == row['player_id']
            assert hashes() == before
            state.season.events[0]['matches'].pop()
            checks.append('player board and individual span/page/history use original simulator snapshots and read models with stable IDs and real measured metrics')

            old_offer = state.career._push_mail('contract', state.season.date,
                dict(title='旧 Offer 精确读取', body='这份原邮件完整正文仍须可查'),
                dict(**target, personal_transfer=True, expires=(date.fromisoformat(state.season.date)+timedelta(days=30)).isoformat(), status='open'))
            for i in range(45):
                news.publish(state.career, state.season, f'fixture-old-offer-gap:{i}', '新闻不占手机邮件', 'saved news')
            state.persist()
            before = hashes()
            inbox = context()['inbox']
            assert not any(r['kind'] == 'news' for r in inbox)
            assert not any(r['kind'] == 'notification' and (state.career._mail(r['id']).get('notification') or {}).get('kind') in ('awards', 'top20') for r in inbox)
            assert inbox[0]['id'] == old_offer['id']
            assert api('/api/3d/mail?id=' + quote(old_offer['id']))['detail']['body'] == old_offer['body']
            assert hashes() == before
            checks.append('news stays saved outside phone inbox projection; old open offer prioritized and exact mail GET preserves body/read flag')

            # Pending-match fixture locks every identity/ability mutation.
            state.arena.data['lobby'] = dict(id='pending-fixture', mode='rank', phase='launched',
                human_id=initial['player']['id'], nonce='fixture-nonce', started_at='2026-01-08T00:00:00Z',
                map='dust2', roster={}, a=[], b=[], captains=[])
            pending = context()
            assert not pending['transfers']['club_allowed'] and not pending['personal']['growth_allowed']
            reject('/api/3d/transfers/apply', team_id=team['id'], role='rifle')
            reject('/api/3d/transfers/buy', player_id='x', replace_id='x')
            reject('/api/3d/attr', allocations={'firepower': 1})
            reject('/api/3d/mail/accept', id=old_offer['id'])
            reject('/api/3d/mail/decline', id=old_offer['id'])
            story = state.career.story_queue[0]
            reject('/api/3d/story', id=story['id'], choice=(story.get('choices') or [{}])[0].get('id', ''))
            current = pending['date']
            held = command('/api/3d/calendar', target_date=current, request_id='pending-test-calendar')
            assert held['reason_code'] == 'ladder_match' and held['actualdate'] == current and held['steps'] == 0
            before = hashes()
            api('/api/3d/news')
            api('/api/3d/player?id=' + quote(initial['player']['id']) + '&span=30d&page=1')
            assert hashes() == before
            state.arena.data['lobby'] = None
            command('/api/3d/mail/decline', id=old_offer['id'])
            assert state.career._mail(old_offer['id'])['status'] == 'declined'
            checks.append('pending real ladder freezes identity, roster, growth and date while read-only information remains available')
            context_bytes = len(json.dumps(initial, ensure_ascii=False).encode())
        finally:
            server.shutdown()
            thread.join(3)
            server.server_close()
            state.persist()
    return dict(ok=True, checks=checks, initial_context_bytes=context_bytes, actual_cs2_started=False,
                actual_plugins_modified=False, official_saves_accessed=False,
                fixture_note='Test-only funding, D20 extremes and saved report payload fixtures exercise original rules; no demo display data was fabricated.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    if not folder.is_absolute() or folder.exists():
        parser.error('Select a new explicitly isolated directory')
    report = run(folder)
    (folder / 'business-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))
