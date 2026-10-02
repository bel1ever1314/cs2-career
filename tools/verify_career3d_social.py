"""Isolated phone conversations, birthday narrative, deduplication and reload checks."""
from copy import deepcopy
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.career3d_service import isolate, handler_class, DEMO_SEED


def run(folder):
    isolate(folder / 'data')
    def audit(event, args):
        if event not in ('open', 'os.scandir') or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        target = Path(os.fsdecode(args[0])).resolve()
        if any(target == base or target.is_relative_to(base) for base in (ROOT / 'save', ROOT / 'extensions')):
            raise RuntimeError('Social verification forbids official save/extension access')
    sys.addaudithook(audit)
    from cs2career.application import ApplicationState
    from cs2career.web.server import create_server
    from cs2career.engine.match import RNG
    from cs2career.career import arcs, plot
    from tools.career3d_social import KEY, social_context, before_story_choice, after_story_choice
    random.seed(DEMO_SEED)
    RNG.seed(DEMO_SEED)
    state = ApplicationState()
    state.create_career(dict(era='2026', mode='create', origin='academy', name='SocialQA',
                            org='Social Academy', region='AS', role='rifle'))
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
                status, result = response.status, json.loads(response.read())
        except HTTPError as exc:
            status, result = exc.code, json.loads(exc.read())
        assert status == expected, (path, status, result.get('msg'), result.get('reason'))
        return result

    def context():
        return api('/api/3d/context')

    def hashes():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (folder / 'data/save').glob('*.json')}

    try:
        initial = context()
        assert len(initial['contacts']) == 5
        assert len({r['id'] for r in initial['contacts']}) == 5
        assert KEY not in state.career.incident_state
        before, memory, rng = hashes(), deepcopy(state.career.incident_state), random.getstate()
        for _ in range(3):
            assert context()['contacts'] == initial['contacts']
        assert hashes() == before and state.career.incident_state == memory and random.getstate() == rng
        checks.append('contacts GET uses stable teammate/club coach IDs and cannot create state, write saves or consume RNG')
        coach = initial['contacts'][0]
        body = dict(contact_id=coach['id'], reply_id='practice', request_id='social-qa-request-one',
                    revision=initial['calendar']['revision'])
        api('/api/3d/social/send', body, token=False, expected=403)
        sent = api('/api/3d/social/send', body)
        lines = next(r for r in sent['context']['contacts'] if r['id'] == coach['id'])['messages']
        assert len(lines) == 3 and lines[-1]['sender'] == 'contact'
        before, memory = hashes(), deepcopy(state.career.incident_state)
        replay = api('/api/3d/social/send', body)
        assert replay['replayed'] and hashes() == before and state.career.incident_state == memory
        api('/api/3d/social/send', dict(body, reply_id='schedule'), expected=400)
        api('/api/3d/social/send', dict(body, request_id='social-qa-new-invalid', revision=-1), expected=400)
        api('/api/3d/social/send', dict(body, request_id='social-qa-invalid-reply', reply_id='invented',
                                      revision=context()['calendar']['revision']), expected=400)
        assert hashes() == before
        checks.append('quick replies persist; receipt replays and invalid/stale/unauthenticated requests never duplicate a response')

        c, s = state.career, state.season
        team = c.my_team(s.teams)
        mates = [p for p in team['players'] if not p.get('you')]
        dates = s.date
        for index, choice in enumerate(('wish', 'train')):
            mate = mates[index]
            sid = f"bday.{s.date}.{mate['name']}"
            with server.state_lock:
                c._push_plot(dict(plot.birthday_popup(mate['name']), date=s.date), sid)
                state.persist()
            points, mentality = c.attr_points, team['mentality']
            captured = before_story_choice(state, next(r for r in c.story_queue if r['id'] == sid), choice)
            result = api('/api/3d/story', dict(id=sid, choice=choice))
            assert result['social_contact_id'] == mate['player_id']
            thread_lines = next(r for r in result['context']['contacts'] if r['id'] == mate['player_id'])['messages']
            assert len(thread_lines) == (3 if choice == 'wish' else 2)
            assert thread_lines[-1]['sender'] == 'contact' and thread_lines[-1]['text']
            narrative = next(r for r in thread_lines if r['sender'] == 'narrator')
            source = next(r for r in c.incident_state['arcs']['history'] if r['id'] == f"arc-notice:{s.date}:birthday:{mate['name']}")
            assert narrative['text'] == source['text']
            assert result['social_focus_message_id'] == narrative['id']
            assert c.attr_points == points + (arcs.config()['rules']['focus_reward'] if choice == 'train' else 0)
            assert team['mentality'] == mentality + (-1 if choice == 'train' else 2)
            assert s.date == dates
            before = hashes()
            api('/api/3d/story', dict(id=sid, choice=choice), expected=400)
            replay_hook = after_story_choice(state, captured)
            assert replay_hook['replayed'] and hashes() == before
            assert len(c.incident_state[KEY]['contacts'][mate['player_id']]['messages']) == len(thread_lines)
        checks.append('birthday congratulate and train branches show original frozen narrative plus person reply, once; original rewards/mentality/date preserved')

        before, memory = hashes(), deepcopy(c.incident_state)
        assert before_story_choice(state, dict(id='unrelated-money', title='俱乐部工资', text='工资已发。'), '') is None
        assert after_story_choice(state, None) == {}
        assert hashes() == before and c.incident_state == memory
        checks.append('unrelated events never invent a speaker or contact')

        # Author-declared people need a stable ID; the scene remains narration.
        custom = dict(id='social-qa-linked-event', kind='story', when='custom_person', timing='calendar', title='队友的小事', text='你们谈起了下一次训练。',
                      choices=[dict(id='yes', label='一起练')],
                      social=dict(contact_id=mates[2]['player_id'], replies={'yes':'行，我等你。'}))
        with server.state_lock:
            c.story_queue.append(custom)
            state.persist()
        linked = api('/api/3d/story', dict(id=custom['id'], choice='yes'))
        linked_lines = next(r for r in linked['context']['contacts'] if r['id'] == mates[2]['player_id'])['messages']
        assert [r['sender'] for r in linked_lines] == ['narrator', 'you', 'contact']
        assert linked_lines[-1]['text'] == '行，我等你。'
        checks.append('explicit person-linked event metadata supports authored replies without attributing narrative to the person')

        saved_social = deepcopy(c.incident_state[KEY])
        before = hashes()
        for _ in range(3):
            context()
        assert hashes() == before
        loaded = ApplicationState()
        assert loaded.career.incident_state[KEY] == saved_social
        assert social_context(loaded) == social_context(state)
        assert json.loads((folder / 'data/save/career.json').read_text('utf-8'))['schema_version'] == 2
        checks.append('birthday and chat messages survive schema-2 reload; repeat projections remain read-only')

        # Removing somebody from the isolated fixture cannot erase their thread.
        with server.state_lock:
            removed = team['players'].pop(team['players'].index(mates[0]))
            archived = next(r for r in social_context(state)['contacts'] if r['id'] == removed['player_id'])
            assert archived['archived'] and archived['messages'] == saved_social['contacts'][removed['player_id']]['messages']
            team['players'].append(removed)
        checks.append('a contact remains attached to the stable person after roster departure')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)
    return dict(ok=True, checks=checks)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    if folder.drive.upper() not in ('D:', 'E:') or folder.exists():
        parser.error('Select a new explicitly isolated D/E directory')
    result = run(folder)
    (folder / 'social-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
