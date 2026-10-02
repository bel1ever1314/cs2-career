"""Manual slots use generated E-drive fixtures; never live saves or CS2.

These tests exercise the public 3D adapter, including its storage transaction.
No fixture is copied from a user's career and no game process is started.
"""
from contextlib import ExitStack
from copy import deepcopy
from datetime import date, timedelta
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from cs2career.application import ApplicationState
from cs2career.arena import Arena
from cs2career.career import Career
from cs2career import manual_saves
from cs2career.random_state import capture, restore
from tools.career3d_saves import saves_command, saves_context


CORE_NAMES = ('season.json', 'career.json', 'arena.json')
FIXTURE_BASE = Path('E:/CS2CareerTools/SaveManager-20261002/temp/backend-tests')


def tree_snapshot(root):
    """Content and timestamps detect even an unnecessary read-side write."""
    return {
        str(path.relative_to(root)): (hashlib.sha256(path.read_bytes()).hexdigest(),
                                     path.stat().st_mtime_ns)
        for path in root.rglob('*') if path.is_file()
    }


def without_control_revisions(career, arena):
    """Slot commands may advance guard counters, never gameplay ledgers."""
    career, arena = deepcopy((career, arena))
    (career.get('incident_state', {}).get('career3d_service') or {}).pop('revision', None)
    arena.pop('revision', None)
    return career, arena


class ManualSavesTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        # Windows verification is explicitly confined to the requested E tree.
        # A non-Windows checkout remains able to run the ordinary test suite.
        base = FIXTURE_BASE if os.name == 'nt' else Path(tempfile.gettempdir()) / 'cs2career-manual-tests'
        base.mkdir(parents=True, exist_ok=True)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='fixture-', dir=base)))
        self.stack.enter_context(patch.dict(os.environ, {
            'CS2CAREER_SAVE_DIR': str(self.root),
            'CS2CAREER_EXTENSION_DIR': str(self.root / 'extensions'),
            'CS2CAREER_NO_GAME': '1',
        }))
        self.stack.enter_context(patch('cs2career.paths.save_root', return_value=self.root))
        self.stack.enter_context(patch('cs2career.league.season.STATE_PATH', self.root / 'season.json'))
        self.stack.enter_context(patch.object(Career, 'path', return_value=self.root / 'career.json'))
        checkpoint = capture()
        self.addCleanup(restore, checkpoint)
        self.state = ApplicationState()
        team = self.state.season.teams[0]
        player = team['players'][0]
        self.state.create_career(dict(era='2026', mode='join', team_id=team['id'],
                                      replace=player['name'], role=player['role']))
        self.state._arena = Arena(self.root / 'arena.json')
        self.state.arena.save()
        self.state.career.incident_state['career3d_service'] = dict(revision=13, receipts=[])
        self.state.career.incident_state['manual_fixture'] = dict(
            appearance={'hair': 'fixture-style', 'shirt': '#1f3a52'},
            honours_seen=['fixture-award'], frozen_nonce='fixture-old-result')
        self.state.persist()
        self.global_files = {
            'cs2.json': b'{"path":"fixture-machine","difficulty":"Medium"}',
            'tactics.json': b'{"fixture_tactic":"keep latest global"}',
            '.career3d-start.json': b'{"draws_used":7,"creation_request":"global-latest"}',
            'cs2_matches.json': b'{"fixture_external_match":"never rewind"}',
        }
        for name, value in self.global_files.items():
            (self.root / name).write_bytes(value)

    def body(self, **fields):
        return dict(revision=saves_context(self.state)['revision'],
                    request_id=str(uuid4()), **fields)

    def command(self, action, **fields):
        return saves_command(self.state, action, self.body(**fields))

    def save(self, label='手动槽 · Fixture'):
        result = self.command('save', label=label)
        self.assertEqual(result['id'], result['slot']['id'])
        return result['slot']

    def folder(self, slot):
        return self.root / 'manual' / slot['id']

    def core_bytes(self):
        return {name: (self.root / name).read_bytes() for name in CORE_NAMES}

    def state_snapshot(self):
        return deepcopy((self.state.career.to_json(), self.state.arena.data,
                         self.state.season.date, self.state.season.teams,
                         self.state.season.events, self.state.season.history,
                         self.state.season.player_all, self.state.season.player_event))

    def current_progress(self):
        current = {name: json.loads(value) for name, value in self.core_bytes().items()}
        career, arena = without_control_revisions(current['career.json'], current['arena.json'])
        return current['season.json'], career, arena

    def memory_progress(self):
        career, arena = without_control_revisions(self.state.career.to_json(), self.state.arena.data)
        return deepcopy((career, arena, self.state.season.date, self.state.season.teams,
                         self.state.season.events, self.state.season.history,
                         self.state.season.player_all, self.state.season.player_event))

    def change_current(self):
        self.state.career.money += 321
        self.state.career.incident_state['manual_fixture']['appearance']['hair'] = 'latest-style'
        self.state.season.history.append(dict(id='latest-history', matches=[]))
        self.state.season.player_all['latest-player'] = dict(rounds=99, kills=123)
        self.state.arena.data['matches'].append(dict(id='latest-local-ladder'))
        self.state.arena.data['revision'] += 1
        self.state.arena.save()
        self.state.career.incident_state['career3d_service']['revision'] += 10
        random.random()
        self.state.persist()

    def test_empty_and_populated_context_are_read_only_owned_projections(self):
        for populated in (False, True):
            if populated:
                self.save()
            before_disk, before_state = tree_snapshot(self.root), self.state_snapshot()
            with (patch.object(self.state, 'persist', side_effect=AssertionError('GET persisted')),
                  patch.object(self.state.arena, 'save', side_effect=AssertionError('GET arena write'))):
                response = saves_context(self.state)
            self.assertTrue(response['ok'])
            self.assertFalse(response['blocked'])
            self.assertEqual(self.state.season.date, response['current']['date'])
            self.assertEqual(self.state.season.era, response['current']['era'])
            self.assertEqual(sum(len(value) for value in self.core_bytes().values()),
                             response['current']['size_bytes'])
            self.assertTrue(response['current']['player'])
            self.assertTrue(response['current']['team'])
            self.assertIn('saved_at', response['current'])
            if populated:
                response['slots'][0]['label'] = 'client mutation'
            self.assertEqual(before_disk, tree_snapshot(self.root))
            self.assertEqual(before_state, self.state_snapshot())

    def test_explicit_save_compresses_complete_three_file_slot_with_hashes(self):
        slot = self.save('  生涯及天梯  ')
        folder = self.folder(slot)
        self.assertEqual('生涯及天梯', slot['label'])
        self.assertTrue((folder / 'manifest.json').is_file())
        manifest = (folder / 'manifest.json').read_text('utf-8')
        self.assertEqual({'manifest.json', *(name + '.gz' for name in CORE_NAMES)},
                         {path.name for path in folder.iterdir()})
        for name, current in self.core_bytes().items():
            compressed = (folder / (name + '.gz')).read_bytes()
            archived = gzip.decompress(compressed)
            self.assertEqual(json.loads(current), json.loads(archived))
            self.assertIn(hashlib.sha256(archived).hexdigest(), manifest)
        self.assertFalse(any((folder / name).exists() for name in self.global_files))
        self.assertEqual(1, len(saves_context(self.state)['slots']))

    def test_distinct_explicit_requests_create_separate_named_slots(self):
        first = self.save('同名槽')
        second = self.save('同名槽')
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual({first['id'], second['id']},
                         {row['id'] for row in saves_context(self.state)['slots']})

    def test_duplicate_save_survives_reload_without_duplicate_slot(self):
        body = self.body(label='幂等槽')
        first = saves_command(self.state, 'save', body)
        before = tree_snapshot(self.root)
        second = saves_command(self.state, 'save', body)
        self.assertEqual(first['id'], second['id'])
        self.assertTrue(second['replayed'])
        self.assertEqual(before, tree_snapshot(self.root))
        self.state = ApplicationState()
        replay = saves_command(self.state, 'save', body)
        self.assertEqual(first['id'], replay['id'])
        self.assertTrue(replay['replayed'])
        self.assertEqual(1, len(saves_context(self.state)['slots']))
        self.change_current()
        latest_revision, latest_disk = saves_context(self.state)['revision'], self.core_bytes()
        replay = saves_command(self.state, 'save', body)
        self.assertTrue(replay['replayed'])
        self.assertEqual(latest_revision, replay['revision'])
        self.assertEqual(latest_disk, self.core_bytes())
        self.assertEqual(1, len(saves_context(self.state)['slots']))

    def test_same_request_cannot_be_reused_for_different_command_or_label(self):
        body = self.body(label='original')
        first = saves_command(self.state, 'save', body)
        before = tree_snapshot(self.root)
        for action, changed in (
            ('save', dict(body, label='changed')),
            ('delete', dict(body, id=first['id'], confirm=True)),
        ):
            with self.subTest(action=action), self.assertRaises(ValueError):
                saves_command(self.state, action, changed)
        self.assertEqual(before, tree_snapshot(self.root))

    def test_validation_and_stale_revision_do_not_write(self):
        before_disk, before_state = tree_snapshot(self.root), self.state_snapshot()
        good = self.body(label='valid')
        invalid = [dict(good, label=''), dict(good, label=' '),
                   dict(good, label='x' * 65), dict(good, label=3),
                   dict(good, request_id='tiny'), dict(good, request_id='x' * 101),
                   dict(good, request_id=True), dict(good, revision=good['revision'] - 1),
                   dict(good, revision=True), dict(good, revision=str(good['revision']))]
        for body in invalid:
            with self.subTest(body=body), self.assertRaises(ValueError):
                saves_command(self.state, 'save', body)
        with self.assertRaises(ValueError):
            saves_command(self.state, 'unknown-action', good)
        self.assertEqual(before_disk, tree_snapshot(self.root))
        self.assertEqual(before_state, self.state_snapshot())

    def test_load_and_delete_require_boolean_confirmation(self):
        slot = self.save()
        before_disk, before_state = tree_snapshot(self.root), self.state_snapshot()
        for action in ('load', 'delete'):
            for confirmation in (None, False, 1, 'true'):
                body = self.body(id=slot['id'])
                if confirmation is not None:
                    body['confirm'] = confirmation
                with self.subTest(action=action, confirm=confirmation), self.assertRaises(ValueError):
                    saves_command(self.state, action, body)
        self.assertEqual(before_disk, tree_snapshot(self.root))
        self.assertEqual(before_state, self.state_snapshot())

    def test_load_restores_career_season_arena_and_rng_without_rewinding_globals(self):
        slot = self.save()
        archived = {name: json.loads(value) for name, value in self.core_bytes().items()}
        expected_rng = capture()
        expected_money = self.state.career.money
        self.change_current()
        current_revision = saves_context(self.state)['revision']
        latest_globals = {name: value + b'\n' for name, value in self.global_files.items()}
        for name, value in latest_globals.items():
            (self.root / name).write_bytes(value)
        holder = self.state
        result = self.command('load', id=slot['id'], confirm=True)
        self.assertTrue(result['loaded'])
        self.assertIs(holder, self.state)
        self.assertIs(self.state.career, self.state.season.career)
        self.assertGreater(saves_context(self.state)['revision'], current_revision)
        self.assertEqual(expected_money, self.state.career.money)
        self.assertEqual(archived['season.json']['history'], self.state.season.history)
        self.assertEqual(archived['season.json']['player_all'], self.state.season.player_all)
        self.assertEqual(archived['career.json']['incident_state']['manual_fixture'],
                         self.state.career.incident_state['manual_fixture'])
        self.assertEqual(archived['career.json']['story_queue'], self.state.career.story_queue)
        self.assertEqual(archived['career.json']['inventory'], self.state.career.inventory)
        self.assertGreater(self.state.arena.data['revision'], archived['arena.json']['revision'])
        self.assertEqual(without_control_revisions({}, archived['arena.json'])[1],
                         without_control_revisions({}, self.state.arena.data)[1])
        self.assertEqual(expected_rng, capture())
        self.assertEqual(latest_globals, {name: (self.root / name).read_bytes() for name in latest_globals})
        self.assertTrue(self.folder(slot).is_dir())
        self.assertFalse((self.root / 'manual-load.pending.json').exists())

    def test_load_replay_does_not_reapply_archive_or_rewind_later_changes(self):
        slot = self.save()
        body = self.body(id=slot['id'], confirm=True)
        saves_command(self.state, 'load', body)
        self.change_current()
        latest = self.core_bytes()
        before = self.state_snapshot()
        result = saves_command(self.state, 'load', body)
        self.assertTrue(result['replayed'])
        self.assertEqual(saves_context(self.state)['revision'], result['revision'])
        self.assertEqual(latest, self.core_bytes())
        self.assertEqual(before, self.state_snapshot())
        self.state = ApplicationState()
        before = self.core_bytes()
        result = saves_command(self.state, 'load', body)
        self.assertTrue(result['replayed'])
        self.assertEqual(saves_context(self.state)['revision'], result['revision'])
        self.assertEqual(before, self.core_bytes())

    def test_load_preserves_newer_request_receipts_outside_archived_career(self):
        old_slot = self.save('old archive')
        later_request = self.body(label='after old archive')
        later = saves_command(self.state, 'save', later_request)
        self.command('load', id=old_slot['id'], confirm=True)
        receipt = self.root / 'manual' / 'requests.json'
        self.assertIn(later_request['request_id'], receipt.read_text('utf-8'))
        response = saves_command(self.state, 'save', later_request)
        self.assertTrue(response['replayed'])
        self.assertEqual(later['id'], response['id'])
        self.assertEqual(2, len(saves_context(self.state)['slots']))

    def test_delete_is_explicit_idempotent_and_does_not_change_current(self):
        slot = self.save()
        core_before, state_before = self.current_progress(), self.memory_progress()
        body = self.body(id=slot['id'], confirm=True)
        result = saves_command(self.state, 'delete', body)
        self.assertEqual(slot['id'], result['id'])
        self.assertFalse(self.folder(slot).exists())
        self.assertEqual(core_before, self.current_progress())
        self.assertEqual(state_before, self.memory_progress())
        result = saves_command(self.state, 'delete', body)
        self.assertTrue(result['replayed'])
        self.state = ApplicationState()
        self.assertTrue(saves_command(self.state, 'delete', body)['replayed'])

    def test_traversal_and_unknown_slot_ids_are_rejected_without_writes(self):
        self.save()
        before_disk, before_state = tree_snapshot(self.root), self.state_snapshot()
        ids = ('../career.json', '../../outside', 'C:/outside', '.', '', 'f' * 32,
               True, ['f' * 32], 'a' * 33)
        for action in ('load', 'delete'):
            for ident in ids:
                with self.subTest(action=action, id=ident), self.assertRaises(ValueError):
                    self.command(action, id=ident, confirm=True)
        self.assertEqual(before_disk, tree_snapshot(self.root))
        self.assertEqual(before_state, self.state_snapshot())

    def test_corrupt_gzip_hash_and_missing_member_never_replace_current(self):
        for damage in ('gzip', 'hash', 'missing'):
            with self.subTest(damage=damage):
                slot = self.save(damage)
                member = self.folder(slot) / 'arena.json.gz'
                if damage == 'gzip':
                    member.write_bytes(b'not gzip')
                elif damage == 'hash':
                    member.write_bytes(gzip.compress(b'{"schema_version":2,"wrong":"hash"}'))
                else:
                    member.unlink()
                before_disk, before_state = self.core_bytes(), self.state_snapshot()
                rows = {row['id']: row for row in saves_context(self.state)['slots']}
                # GET checks structure without expanding every saved career.
                # Deep gzip/hash integrity is checked before any load write.
                if damage == 'missing':
                    self.assertTrue(rows[slot['id']]['corrupt'])
                with self.assertRaises(ValueError):
                    self.command('load', id=slot['id'], confirm=True)
                self.assertEqual(before_disk, self.core_bytes())
                self.assertEqual(before_state, self.state_snapshot())
                self.command('delete', id=slot['id'], confirm=True)
                self.assertFalse(self.folder(slot).exists())

    def test_missing_or_malformed_manifest_is_visible_and_deletable(self):
        for damage in ('missing', 'json'):
            with self.subTest(damage=damage):
                slot = self.save(damage)
                path = self.folder(slot) / 'manifest.json'
                if damage == 'missing':
                    path.unlink()
                else:
                    path.write_bytes(b'{malformed')
                row = next(row for row in saves_context(self.state)['slots'] if row['id'] == slot['id'])
                self.assertTrue(row['corrupt'])
                current = self.core_bytes()
                with self.assertRaises(ValueError):
                    self.command('load', id=slot['id'], confirm=True)
                self.assertEqual(current, self.core_bytes())
                self.command('delete', id=slot['id'], confirm=True)

    def test_pending_training_career_cs2_rts_and_arena_gate_save_and_load_but_not_delete(self):
        pending_cases = ('training', 'career_cs2', 'career_rts', 'arena_starting',
                         'arena_launched', 'arena_rts')
        for pending in pending_cases:
            with self.subTest(pending=pending):
                slot = self.save(pending)
                career, events, arena = deepcopy((self.state.career.training_session,
                                                 self.state.season.events, self.state.arena.data))
                try:
                    if pending == 'training':
                        self.state.career.training_session = dict(nonce='pending-training', status='launched')
                    elif pending.startswith('career_'):
                        field = 'cs2_session' if pending == 'career_cs2' else 'career3d_rts'
                        self.state.season.events.append(dict(id='pending-fixture', matches=[
                            dict(id='pending-map', played=False, **{field: dict(nonce='frozen-nonce')})]))
                    else:
                        self.state.arena.data['lobby'] = dict(phase=pending.removeprefix('arena_'),
                                                            nonce='frozen-arena-nonce')
                    # A real pending launch is durable before its UI response.
                    self.state.career.save()
                    self.state.season.save()
                    self.state.arena.save()
                    before_disk, before_state = self.core_bytes(), self.state_snapshot()
                    context = saves_context(self.state)
                    self.assertTrue(context['blocked'])
                    self.assertTrue(context['reason'])
                    for action, fields in (('save', dict(label='must not save')),
                                           ('load', dict(id=slot['id'], confirm=True))):
                        with self.assertRaises(ValueError):
                            self.command(action, **fields)
                    self.assertEqual(before_disk, self.core_bytes())
                    self.assertEqual(before_state, self.state_snapshot())
                    progress_before, memory_before = self.current_progress(), self.memory_progress()
                    self.command('delete', id=slot['id'], confirm=True)
                    self.assertEqual(progress_before, self.current_progress())
                    self.assertEqual(memory_before, self.memory_progress())
                finally:
                    self.state.career.training_session = career
                    self.state.season.events = events
                    self.state.arena.data = arena
                    self.state.career.save()
                    self.state.season.save()
                    self.state.arena.save()

    def test_failed_second_live_replace_rolls_back_every_file_and_memory(self):
        slot = self.save()
        self.change_current()
        disk, memory, rng = self.core_bytes(), self.state_snapshot(), capture()
        original = manual_saves.atomic_bytes
        failed = False

        def once(path, payload):
            nonlocal failed
            if Path(path) == self.root / 'career.json' and not failed:
                failed = True
                raise OSError('injected second live replacement failure')
            return original(path, payload)

        with patch.object(manual_saves, 'atomic_bytes', side_effect=once):
            with self.assertRaises((OSError, ValueError)):
                self.command('load', id=slot['id'], confirm=True)
        self.assertTrue(failed)
        self.assertEqual(disk, self.core_bytes())
        self.assertEqual(memory, self.state_snapshot())
        self.assertEqual(rng, capture())
        self.assertFalse((self.root / 'manual-load.pending.json').exists())
        self.assertTrue(self.command('load', id=slot['id'], confirm=True)['loaded'])

    def test_failed_prepare_does_not_make_old_load_request_bypass_new_revision(self):
        slot = self.save()
        body = self.body(id=slot['id'], confirm=True)
        original = manual_saves.atomic_bytes

        def fail_preparation(path, payload):
            if Path(path).name == 'season.json.before':
                raise OSError('injected failure before restore journal exists')
            return original(path, payload)

        before_disk, before_state = self.core_bytes(), self.state_snapshot()
        with patch.object(manual_saves, 'atomic_bytes', side_effect=fail_preparation):
            with self.assertRaises((OSError, ValueError)):
                saves_command(self.state, 'load', body)
        self.assertEqual(before_disk, self.core_bytes())
        self.assertEqual(before_state, self.state_snapshot())
        self.assertFalse((self.root / 'manual-load.pending.json').exists())
        self.change_current()
        latest_disk, latest_state = self.core_bytes(), self.state_snapshot()
        with self.assertRaises(ValueError):
            saves_command(self.state, 'load', body)
        self.assertEqual(latest_disk, self.core_bytes())
        self.assertEqual(latest_state, self.state_snapshot())

    def test_failed_save_receipt_retry_does_not_create_another_slot(self):
        body = self.body(label='durable pending save')
        original = manual_saves.record_request

        def fail_final_receipt(root, request_id, row):
            if row.get('status') == 'done':
                raise OSError('injected final save receipt failure')
            return original(root, request_id, row)

        with patch.object(manual_saves, 'record_request', side_effect=fail_final_receipt):
            with self.assertRaises(OSError):
                saves_command(self.state, 'save', body)
        slots = saves_context(self.state)['slots']
        self.assertEqual(1, len(slots))
        saved_id = slots[0]['id']
        self.state = ApplicationState()
        retried = saves_command(self.state, 'save', body)
        self.assertEqual(saved_id, retried['id'])
        self.assertEqual(1, len(saves_context(self.state)['slots']))
        self.assertTrue(saves_command(self.state, 'save', body)['replayed'])

    def test_committed_load_receipt_failure_keeps_loaded_progress_and_finishes_on_recovery(self):
        slot = self.save()
        archived = self.current_progress()
        self.change_current()
        body = self.body(id=slot['id'], confirm=True)
        original = manual_saves.record_request

        def fail_final_receipt(root, request_id, row):
            if row.get('status') == 'done' and row.get('action') == 'load':
                raise OSError('injected final load receipt failure')
            return original(root, request_id, row)

        with patch.object(manual_saves, 'record_request', side_effect=fail_final_receipt):
            with self.assertRaises(OSError):
                saves_command(self.state, 'load', body)
        journal = json.loads((self.root / 'manual-load.pending.json').read_bytes())
        self.assertEqual('committed', journal['phase'])
        self.assertEqual(archived, self.current_progress())
        self.assertTrue(manual_saves.recover(self.root))
        self.state = ApplicationState()
        before = self.core_bytes()
        self.assertTrue(saves_command(self.state, 'load', body)['replayed'])
        self.assertEqual(before, self.core_bytes())
        self.assertEqual(archived, self.current_progress())

    def test_committed_cleanup_failure_does_not_restore_old_memory_after_journal_removal(self):
        slot = self.save()
        archived = self.current_progress()
        archived_memory = self.memory_progress()
        archived_rng = capture()
        self.change_current()
        body = self.body(id=slot['id'], confirm=True)
        original = manual_saves._cleanup
        failed = False

        def fail_transaction_cleanup(folder):
            nonlocal failed
            if Path(folder).name.startswith('.restore-') and not failed:
                failed = True
                raise OSError('injected cleanup failure after durable commit and receipt')
            return original(folder)

        with patch.object(manual_saves, '_cleanup', side_effect=fail_transaction_cleanup):
            with self.assertRaises(OSError):
                saves_command(self.state, 'load', body)
        self.assertTrue(failed)
        self.assertFalse((self.root / 'manual-load.pending.json').exists())
        self.assertEqual(archived, self.current_progress())
        self.assertEqual(archived_memory, self.memory_progress())
        self.assertEqual(archived_rng, capture())
        self.assertEqual('done', manual_saves.requests(self.root)[body['request_id']]['status'])
        before_disk, before_state = self.core_bytes(), self.state_snapshot()
        self.assertTrue(saves_command(self.state, 'load', body)['replayed'])
        self.assertEqual(before_disk, self.core_bytes())
        self.assertEqual(before_state, self.state_snapshot())

    def test_corrupt_rollback_copy_retains_journal_and_never_partially_rewrites_current(self):
        slot = self.save()
        self.change_current()
        payloads = manual_saves.read_slot(self.root, slot['id'])
        journal = manual_saves.begin_restore(self.root, payloads, str(uuid4()), 'fixture-hash', {})
        work = self.root / 'manual' / ('.restore-' + journal['token'])
        (work / 'career.json.before').write_bytes(b'corrupt before-image')
        before = self.core_bytes()
        with self.assertRaises(ValueError):
            manual_saves.recover(self.root)
        self.assertEqual(before, self.core_bytes())
        self.assertTrue((self.root / 'manual-load.pending.json').exists())
        self.assertTrue(work.is_dir())

    def test_interrupted_restore_is_rolled_back_by_startup_recovery_protocol(self):
        slot = self.save()
        self.change_current()
        before = self.core_bytes()
        original = manual_saves.atomic_bytes
        stopped = False

        def simulate_process_exit(path, payload):
            nonlocal stopped
            if Path(path) == self.root / 'career.json' and not stopped:
                stopped = True
                raise SystemExit('simulated process interruption, not a running game')
            return original(path, payload)

        with patch.object(manual_saves, 'atomic_bytes', side_effect=simulate_process_exit):
            with self.assertRaises(SystemExit):
                self.command('load', id=slot['id'], confirm=True)
        self.assertTrue(stopped)
        self.assertTrue((self.root / 'manual-load.pending.json').exists())
        self.assertNotEqual(before, self.core_bytes())
        # The service invokes recovery before constructing its one holder.
        self.assertTrue(manual_saves.recover(self.root))
        self.state = ApplicationState()
        self.assertEqual(before, self.core_bytes())
        self.assertFalse((self.root / 'manual-load.pending.json').exists())
        self.assertFalse(any((self.root / 'manual').glob('.restore-*')))

    def test_slot_member_schema_validation_happens_before_replacing_current(self):
        slot = self.save()
        folder = self.folder(slot)
        bad = manual_saves.encode(dict(schema_version=2, money=999, exists='not boolean'))
        (folder / 'career.json.gz').write_bytes(gzip.compress(bad))
        manifest = json.loads((folder / 'manifest.json').read_bytes())
        manifest['files']['career.json'] = dict(bytes=len(bad), sha256=hashlib.sha256(bad).hexdigest())
        (folder / 'manifest.json').write_bytes(manual_saves.encode(manifest))
        before_disk, before_state = self.core_bytes(), self.state_snapshot()
        with self.assertRaises(ValueError):
            self.command('load', id=slot['id'], confirm=True)
        self.assertEqual(before_disk, self.core_bytes())
        self.assertEqual(before_state, self.state_snapshot())

    def test_real_http_save_mutate_load_shutdown_and_reopen_keep_one_holder(self):
        from cs2career.web.server import create_server
        from tools.career3d_service import handler_class

        def context(holder, hour=8):
            return dict(calendar={'revision': saves_context(holder)['revision']},
                        avatar=deepcopy(holder.career.incident_state.get('career3d_avatar', {})),
                        date=holder.season.date, player=holder.career.player_name)

        server = create_server(self.state)
        server.RequestHandlerClass = handler_class()
        server.game_disabled = True
        server.display_hour = 16
        holder = self.state  # Exactly the object captured by the service shutdown closure.
        thread = threading.Thread(target=server.serve_forever,
                                  kwargs={'poll_interval': 0.05}, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'

        def request(path, body=None, token=True):
            headers = {'Content-Type': 'application/json'}
            if token:
                headers['X-Career-Token'] = server.token
            raw = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
            req = Request(origin + path, data=raw, headers=headers,
                          method='GET' if body is None else 'POST')
            try:
                with urlopen(req, timeout=5) as response:
                    return response.status, json.load(response)
            except HTTPError as exc:
                return exc.code, json.load(exc)

        try:
            # Keep resource caches out of this storage test; requests still pass
            # through the real handler, authentication, whitelist and state lock.
            with patch('tools.career3d_service.read_context', side_effect=context):
                before = tree_snapshot(self.root)
                self.assertEqual(403, request('/api/3d/saves', token=False)[0])
                self.assertEqual(404, request('/api/state')[0])
                self.assertEqual(403, request('/api/3d/saves/save',
                    self.body(label='forbidden'), token=False)[0])
                code, public = request('/api/3d/saves')
                self.assertEqual(200, code)
                self.assertTrue(public['ok'])
                self.assertEqual(before, tree_snapshot(self.root))
                code, saved = request('/api/3d/saves/save',
                    dict(revision=public['revision'], request_id=str(uuid4()), label='HTTP Archive'))
                self.assertEqual(200, code)
                self.assertTrue(saved['ok'])
                archived_progress = self.current_progress()
                archived_avatar = deepcopy(holder.career.incident_state.get('career3d_avatar'))
                code, changed = request('/api/3d/avatar',
                    dict(revision=saved['revision'], appearance={'body_color': '123456'}))
                self.assertEqual(200, code)
                self.assertTrue(changed['ok'])
                self.assertEqual('123456', holder.career.incident_state['career3d_avatar']['appearance']['body_color'])
                _, public = request('/api/3d/saves')
                code, loaded = request('/api/3d/saves/load',
                    dict(revision=public['revision'], request_id=str(uuid4()),
                         id=saved['id'], confirm=True))
                self.assertEqual(200, code)
                self.assertTrue(loaded['ok'])
                self.assertTrue(loaded['loaded'])
                self.assertIs(holder, server.state)
                self.assertIs(holder, self.state)
                self.assertEqual(8, server.display_hour)
                self.assertEqual(archived_avatar, holder.career.incident_state.get('career3d_avatar'))
                self.assertEqual(archived_progress, self.current_progress())
                code, stopped = request('/api/3d/shutdown', {})
                self.assertEqual(200, code)
                self.assertEqual('stopping', stopped['status'])
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())
        finally:
            if thread.is_alive():
                server.shutdown()
                thread.join(timeout=5)
            server.server_close()
            # Mirror main()'s real shutdown closure, which must persist the
            # restored holder instead of the pre-load career/season objects.
            with server.state_lock:
                holder.persist()
        manual_saves.recover(self.root)
        self.state = ApplicationState()
        self.assertEqual(archived_progress, self.current_progress())
        self.assertEqual(archived_avatar, self.state.career.incident_state.get('career3d_avatar'))
        self.assertEqual(1, len(saves_context(self.state)['slots']))

    def test_full_unpatched_read_context_uses_restored_objects_through_shutdown_and_reopen(self):
        from cs2career.cs2 import launch
        from tools.career3d_service import isolate, read_context

        # Use the real service directory shape and isolation marker. The draw
        # store is naturally absent/empty; no projection or metadata function
        # is replaced to make the complete context succeed.
        original_files = self.core_bytes()
        data_dir = self.root / 'full-context-service'
        isolate(data_dir)
        self.root = data_dir / 'save'
        for name, payload in original_files.items():
            (self.root / name).write_bytes(payload)
        self.stack.enter_context(patch('cs2career.paths.save_root', return_value=self.root))
        self.stack.enter_context(patch('cs2career.league.season.STATE_PATH', self.root / 'season.json'))
        self.stack.enter_context(patch.object(Career, 'path', return_value=self.root / 'career.json'))
        self.stack.enter_context(patch.object(launch, 'SETTINGS_PATH', self.root / 'cs2.json'))
        self.stack.enter_context(patch.dict(os.environ, {'CS2CAREER3D_MEDIA_CONFIG': ''}))
        (self.root / 'cs2.json').write_bytes(manual_saves.encode(dict(
            launch.DEFAULTS, csgo_path='', steam_exe='', mod_source_path='')))
        self.state = ApplicationState()
        holder = self.state
        human = holder.arena.career_player_id(holder)
        holder.arena.data['ladder'][human] = dict(elo=1711, wins=3, losses=2, recent=[])
        holder.arena.save()
        holder.persist()
        archived_player = holder.career.my_player(holder.season.teams)
        expected = dict(player_id=archived_player['player_id'], name=archived_player['name'],
                        date=holder.season.date, elo=1711, wins=3, losses=2)
        slot = self.save('Full actual context')

        def checked_context(expected_values):
            before_disk = tree_snapshot(data_dir)
            context = read_context(holder)
            # The actual HTTP response encoder also rejects non-JSON values.
            from cs2career.json_bytes import encode
            public = json.loads(encode(context))
            self.assertTrue(public['ok'])
            self.assertEqual(expected_values['player_id'], public['player']['id'])
            self.assertEqual(expected_values['name'], public['player']['name'])
            self.assertEqual(expected_values['date'], public['date'])
            self.assertEqual(expected_values['player_id'], public['ladder']['rank_human_id'])
            self.assertEqual({key: expected_values[key] for key in ('elo', 'wins', 'losses')},
                             public['ladder']['player'])
            self.assertEqual(before_disk, tree_snapshot(data_dir))
            return public

        # The current state is deliberately different in all three visible
        # domains, so reuse of a captured pre-load c/s/arena cannot pass.
        old_career, old_season, old_arena = holder.career, holder.season, holder.arena
        current_player = old_career.my_player(old_season.teams)
        current_player['name'] = 'Later Fixture Player'
        old_career.player_name = current_player['name']
        old_career.you_card['name'] = current_player['name']
        old_season.date = (date.fromisoformat(expected['date']) + timedelta(days=1)).isoformat()
        old_career.current_date = old_season.date
        old_arena.data['ladder'][human] = dict(elo=2809, wins=9, losses=5, recent=[])
        old_arena.save()
        holder.persist()
        checked_context(dict(expected, name='Later Fixture Player', date=old_season.date,
                             elo=2809, wins=9, losses=5))
        self.assertTrue(self.command('load', id=slot['id'], confirm=True)['loaded'])
        self.assertIs(holder, self.state)
        self.assertIsNot(old_career, holder.career)
        self.assertIsNot(old_season, holder.season)
        self.assertIsNot(old_arena, holder.arena)
        self.assertIs(holder.career, holder.season.career)
        # Poison obsolete objects without mocking any live projection. A
        # stale reference would either return the sentinels or fail outright.
        old_career.player_name, old_career.team_id = '__obsolete__', '__obsolete__'
        old_season.date, old_season.teams = '2099-12-31', []
        old_arena.data = dict(revision=999999, ladder={}, lobby=None, matches=[])
        checked_context(expected)
        holder.persist()  # Same captured holder as the real shutdown closure.
        checked_context(expected)
        manual_saves.recover(self.root)
        self.state = ApplicationState()
        holder = self.state
        checked_context(expected)


if __name__ == '__main__':
    unittest.main()
