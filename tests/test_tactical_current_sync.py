"""Current-session publication fixtures: E: isolation, never real CS2 or saves."""
from copy import deepcopy
import json
import os
import subprocess
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.request import Request, urlopen

from cs2career import tactics
from cs2career.cs2 import launch
from tools import career3d_matches as adapters

STRICT_PROCESS = launch.cs2_is_live_strict


def row(ident='d_1'):
    return dict(id=ident, name='同步测试', side='t', slots=[dict(slot=n, steps=[]) for n in range(1, 6)])


class CurrentTacticSyncTests(unittest.TestCase):
    def setUp(self):
        check_root = Path('E:/CS2CareerTools/Checks/tactics-sync-fixtures')
        check_root.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix='case-', dir=check_root)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.csgo = self.root / 'game' / 'csgo'
        self.folder = launch.plugin_dir(self.csgo)
        self.folder.mkdir(parents=True)
        self.request = dict(schema_version=2, active=True, nonce='fixture-current-nonce', map='de_dust2',
                            human_player_id='p0', ct=dict(players=[dict(player_id='p' + str(n)) for n in range(1, 5)]),
                            t=dict(players=[dict(player_id='p' + str(n)) for n in range(5, 10)]))
        self.session = dict(nonce=self.request['nonce'], cs2_map='de_dust2', map='dust2',
                            expected_player_ids=['p' + str(n) for n in range(10)], started_at='fixture-preserved')
        self.state = SimpleNamespace(career=SimpleNamespace(training_session=None,
            incident_state={'career3d_service': {'revision': 7}}),
            season=SimpleNamespace(events=[dict(matches=[dict(played=False, cs2_session=self.session)])]),
            arena=SimpleNamespace(data={'lobby': None}, pending=False))
        self.request_path = self.folder / 'match_request.json'
        self.request_path.write_text(json.dumps(self.request), 'utf-8')
        for name in ('CareerMatch.dll', 'match_result.json', 'match_result.best.json', 'tactical_routes.json', 'player_ids.json'):
            (self.folder / name).write_bytes(('preserve-' + name).encode())
        self.target = self.folder / 'tactical_playbook.json'
        self.target.write_text(json.dumps(dict(schema_version=1, map='de_dust2', tactics=[row('old')])), 'utf-8')
        self.protected = self.snapshot(exclude_playbook=True)
        resource = tactics.data_file
        for mocking in (patch.dict(os.environ, {'CS2CAREER_SAVE_DIR': str(self.root / 'save')}),
            patch.object(tactics, 'data_file', side_effect=lambda name: self.root / 'missing-examples.json'
                         if name == 'tactical_playbook.json' else resource(name)),
            patch.object(launch, 'cs2_is_live_strict', return_value=False),
            patch('tools.career3d_activities.read_cs2_config', return_value={'csgo_path': str(self.csgo)})):
            mocking.start()
            self.addCleanup(mocking.stop)
        tactics.save_tactic(row())

    def snapshot(self, exclude_playbook=False):
        return {str(p.relative_to(self.csgo)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.csgo.rglob('*') if p.is_file()
                and not (exclude_playbook and p.name == 'tactical_playbook.json')}

    def publish(self, **options):
        return launch.tactical_publication(self.csgo, 'de_dust2', [self.session], **options)

    def unchanged(self, before):
        self.assertEqual(before, self.snapshot())

    def test_closed_sync_changes_only_playbook_and_never_session(self):
        state_before = deepcopy(self.state.__dict__)
        value = self.publish(sync=True)
        self.assertTrue(value['synced'])
        self.assertEqual(['d_1'], value['published_ids'])
        self.assertEqual(self.protected, self.snapshot(exclude_playbook=True))
        self.assertEqual(state_before, self.state.__dict__)
        before = self.snapshot()
        self.assertTrue(self.publish(sync=True)['synced'])
        self.unchanged(before)  # byte/mtime idempotency; no pointless rewrite.

    def test_get_reports_pending_ids_but_never_publishes(self):
        before = self.snapshot()
        value = adapters.tactics_context('de_dust2', self.state)
        self.assertTrue(value['publication']['can_sync'])
        self.assertEqual(['old'], value['publication']['published_ids'])
        self.assertEqual(['d_1'], value['publication']['saved_ids'])
        self.assertNotIn('nonce', value['publication'])
        self.assertNotIn('expected_player_ids', value['publication'])
        self.unchanged(before)

    def test_save_auto_syncs_current_match_without_busy_session_reset(self):
        value = adapters.tactics_command(self.state, 'save', {'revision': 7, 'map': 'de_dust2', 'tactic': row('new')})
        self.assertTrue(value['publication']['synced'])
        self.assertEqual(['d_1', 'new'], value['publication']['published_ids'])
        self.assertEqual(self.protected, self.snapshot(exclude_playbook=True))
        self.assertEqual('fixture-current-nonce', self.session['nonce'])

    def test_live_save_succeeds_but_game_environment_is_unchanged(self):
        before = self.snapshot()
        with patch.object(launch, 'cs2_is_live_strict', return_value=True):
            value = adapters.tactics_command(self.state, 'save', {'revision': 7, 'tactic': row('new')})
        self.assertEqual('saved', value['status'])
        self.assertEqual('pending', value['publication']['status'])
        self.assertFalse(value['publication']['can_sync'])
        self.assertIn('new', [t['id'] for t in tactics.load_library()['tactics']])
        self.unchanged(before)

    def test_explicit_sync_after_close_keeps_same_match(self):
        before_session = deepcopy(self.session)
        value = adapters.tactics_command(self.state, 'sync', {'revision': 7, 'map': 'dust2'})
        self.assertEqual('synced', value['status'])
        self.assertEqual(before_session, self.session)
        self.assertEqual(self.protected, self.snapshot(exclude_playbook=True))

    def test_no_current_session_does_not_resurrect_old_game_request(self):
        before = self.snapshot()
        self.state.season.events[0]['matches'][0]['played'] = True
        value = adapters.tactics_command(self.state, 'save', {'revision': 7, 'tactic': row('new')})
        self.assertEqual('no_session', value['publication']['status'])
        self.assertFalse(value['publication']['can_sync'])
        self.unchanged(before)

    def test_other_map_saved_without_overwriting_current_match(self):
        before = self.snapshot()
        value = adapters.tactics_command(self.state, 'save', {'revision': 7, 'map': 'de_mirage', 'tactic': row('m_1')})
        self.assertEqual('map_mismatch', value['publication']['status'])
        self.assertEqual('de_dust2', value['publication']['prepared_map'])
        self.unchanged(before)

    def test_identity_nonce_and_map_must_all_match(self):
        for change in (dict(nonce='foreign'), dict(expected_player_ids=['wrong'] * 10), dict(cs2_map='de_mirage')):
            with self.subTest(change=tuple(change)):
                before = self.snapshot()
                value = launch.tactical_publication(self.csgo, 'de_dust2', [dict(self.session, **change)], sync=True)
                self.assertEqual('session_mismatch', value['status'])
                self.unchanged(before)

    def test_duplicate_session_identity_is_rejected(self):
        before = self.snapshot()
        value = launch.tactical_publication(self.csgo, 'de_dust2', [self.session, deepcopy(self.session)], sync=True)
        self.assertEqual('session_mismatch', value['status'])
        self.unchanged(before)

    def test_duplicate_extra_player_and_malformed_side_are_rejected(self):
        for malformed in ('duplicate', 'side'):
            with self.subTest(malformed=malformed):
                changed = deepcopy(self.request)
                if malformed == 'duplicate': changed['ct']['players'].append(dict(player_id='p1'))
                else: changed['ct']['players'] = {'wrong': 'shape'}
                self.request_path.write_text(json.dumps(changed), 'utf-8')
                before = self.snapshot()
                self.assertEqual('session_mismatch', self.publish(sync=True)['status'])
                self.unchanged(before)

    def test_foreign_published_map_ids_are_not_reported_as_this_match(self):
        self.target.write_text(json.dumps(dict(schema_version=1, map='de_mirage', tactics=[row('mirage_only')])), 'utf-8')
        value = self.publish()
        self.assertEqual('de_mirage', value['published_map'])
        self.assertEqual([], value['published_ids'])
        self.assertTrue(value['pending'])
        self.assertEqual(['d_1'], self.publish(sync=True)['published_ids'])

    def test_same_id_content_change_still_needs_publication(self):
        self.publish(sync=True)
        changed = row(); changed['name'] = '修改后的名称'
        tactics.save_tactic(changed)
        self.assertTrue(self.publish()['pending'])
        self.assertTrue(self.publish(sync=True)['synced'])
        self.assertEqual('修改后的名称', json.loads(self.target.read_bytes())['tactics'][0]['name'])

    def test_process_unavailable_never_writes_game(self):
        for process in (None, OSError('fixture process query unavailable')):
            with self.subTest(process=str(process)):
                before = self.snapshot()
                kwargs = {'side_effect': process} if isinstance(process, Exception) else {'return_value': process}
                with patch.object(launch, 'cs2_is_live_strict', **kwargs): value = self.publish(sync=True)
                self.assertFalse(value['synced'])
                self.unchanged(before)

    def test_cs2_starting_during_atomic_write_prevents_replace(self):
        before = self.snapshot()
        with patch.object(launch, 'cs2_is_live_strict', side_effect=[False, False, True]):
            value = self.publish(sync=True)
        self.assertEqual('sync_error', value['status'])
        self.unchanged(before)

    def test_changed_request_at_commit_prevents_replace(self):
        before_target = self.target.read_bytes()
        original = tactics.write_library
        def change_request_then_write(path, library, **kwargs):
            self.request_path.write_text(json.dumps(dict(self.request, nonce='external-new-session')), 'utf-8')
            return original(path, library, **kwargs)
        with patch.object(tactics, 'write_library', side_effect=change_request_then_write): value = self.publish(sync=True)
        self.assertEqual('sync_error', value['status'])
        self.assertEqual(before_target, self.target.read_bytes())
        self.assertFalse(list(self.folder.glob('*.tmp')))

    def test_underlying_process_discovery_failure_cannot_look_like_closed(self):
        for failure in (subprocess.CalledProcessError(1, 'fixture-powershell'), FileNotFoundError('fixture'), OSError('fixture')):
            with self.subTest(failure=type(failure).__name__):
                before = self.snapshot()
                with patch.object(launch, 'cs2_is_live_strict', side_effect=STRICT_PROCESS), \
                     patch.object(launch.subprocess, 'check_output', side_effect=failure):
                    value = self.publish(sync=True)
                self.assertEqual('sync_error', value['status'])
                self.assertFalse(value['can_sync'])
                self.unchanged(before)

    def test_strict_process_sentinel_and_commit_query_failure(self):
        for output, expected in (('ok:', False), ('ok:123,456', True)):
            with patch.object(launch.subprocess, 'check_output', return_value=output):
                self.assertEqual(expected, STRICT_PROCESS())
        for output in ('', '123', 'ok:garbage', 'warning\nok:', 'ok:'):
            with self.subTest(output=output):
                before = self.snapshot()
                # Failure/unknown at the FINAL query must leave the old snapshot.
                values = ['ok:', 'ok:', output] if output != 'ok:' else ['ok:', 'ok:', '']
                with patch.object(launch, 'cs2_is_live_strict', side_effect=STRICT_PROCESS), \
                     patch.object(launch.subprocess, 'check_output', side_effect=values):
                    value = self.publish(sync=True)
                self.assertEqual('sync_error', value['status'])
                self.unchanged(before)

    def test_failed_publish_keeps_saved_library_and_previous_snapshot(self):
        before = self.snapshot()
        original_replace = os.replace
        with patch.object(tactics.os, 'replace', side_effect=lambda src, dst:
                          (_ for _ in ()).throw(PermissionError('fixture locked')) if Path(dst) == self.target
                          else original_replace(src, dst)):
            value = adapters.tactics_command(self.state, 'save', {'revision': 7, 'tactic': row('new')})
        self.assertEqual('sync_error', value['publication']['status'])
        self.assertEqual(['d_1', 'new'], [t['id'] for t in tactics.load_library()['tactics']])
        self.unchanged(before)

    def test_stale_revision_and_caller_supplied_identity_are_refused(self):
        before = self.snapshot()
        for body in (dict(revision=6), dict(revision=7, nonce='foreign'), dict(revision=7, csgo_path=str(self.csgo))):
            with self.subTest(body=tuple(body)), self.assertRaises(ValueError):
                adapters.tactics_command(self.state, 'sync', body)
        self.unchanged(before)

    def test_training_and_ladder_sessions_are_read_without_mutation(self):
        self.state.season.events = []
        self.state.career.training_session = self.session
        self.assertEqual([self.session], adapters._tactical_sessions(self.state))
        self.state.career.training_session = None
        self.state.arena.data['lobby'] = dict(phase='launched', nonce=self.session['nonce'], map='dust2',
                                            roster={p: {} for p in self.session['expected_player_ids']})
        before = deepcopy(self.state.arena.data)
        self.assertTrue(adapters.tactics_command(self.state, 'sync', {'revision': 7})['publication']['synced'])
        self.assertEqual(before, self.state.arena.data)

    def test_real_http_sync_preserves_revision_and_never_persists_career(self):
        from cs2career.web.server import create_server
        from tools import career3d_service as service
        self.state.persist = Mock()
        self.state.season.date = '2026-10-03'
        server = create_server(self.state, port=0)
        server.RequestHandlerClass = service.handler_class()
        server.display_hour = 8
        server.game_disabled = True
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        def api(path, body=None):
            req = Request('http://127.0.0.1:' + str(server.server_port) + path,
                          None if body is None else json.dumps(body).encode(),
                          {'Content-Type': 'application/json', 'X-Career-Token': server.token})
            with urlopen(req, timeout=10) as response:
                return json.loads(response.read())
        try:
            with patch.object(service, 'read_context', side_effect=lambda state, hour:
                              {'calendar': {'revision': state.career.incident_state['career3d_service']['revision']}}), \
                 patch.object(service, '_pause', return_value=('', '')):
                view = api('/api/3d/tactics?map=de_dust2')
                self.assertEqual(['old'], view['publication']['published_ids'])
                result = api('/api/3d/tactics/sync', {'revision': 7, 'map': 'de_dust2'})
                self.assertTrue(result['publication']['synced'])
                self.assertEqual(7, result['context']['calendar']['revision'])
                self.state.persist.assert_not_called()
                saved = api('/api/3d/tactics/save', {'revision': 7, 'map': 'de_dust2', 'tactic': row('new')})
                self.assertTrue(saved['publication']['synced'])
                self.assertEqual(8, saved['context']['calendar']['revision'])
                self.state.persist.assert_called_once()
                self.assertEqual(self.protected, self.snapshot(exclude_playbook=True))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
