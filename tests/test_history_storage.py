from copy import copy, deepcopy
import gzip
import json
import pickle
from pathlib import Path
import tempfile
import unittest

from cs2career.storage import history
from cs2career.storage.immutable import freeze, snapshot_memo
from types import SimpleNamespace
from cs2career import save_backups


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.blob = dict(schema_version=2, date='2030-01-08',
            history=[dict(year=2026+i//30, event='event-'+str(i), maps=[dict(score='13-8')]*30) for i in range(155)],
            log=['Day '+str(i) for i in range(901)], teams=[], events=[])

    def test_round_trip_preserves_every_record_and_reuses_segments(self):
        before = deepcopy(self.blob)
        packed = history.pack(self.root, self.blob)
        stamps = {p.name:p.stat().st_mtime_ns for p in (self.root/'history').iterdir()}
        self.assertEqual(before, self.blob)
        self.assertEqual(before, history.expand(self.root, packed))
        self.assertEqual(history.ARCHIVED_SCHEMA, packed['schema_version'])
        with self.assertRaises(ValueError): int(packed['schema_version'])  # Legacy loader refuses rather than discarding archives.
        self.assertEqual(packed, history.pack(self.root, before))
        self.assertEqual(stamps, {p.name:p.stat().st_mtime_ns for p in (self.root/'history').iterdir()})
        self.assertLess(len(packed['log']), 400)
        self.assertGreaterEqual(len(packed['log']), 200)
        self.assertLess(len(json.dumps(packed)), len(json.dumps(before))//5)

    def test_backup_is_portable_without_original_archive(self):
        (self.root/'season.json').write_text(json.dumps(history.pack(self.root, self.blob)))
        (self.root/'career.json').write_text('{"schema_version":2}')
        folder = save_backups.create(self.root)
        raw = gzip.decompress((folder/'season.json.gz').read_bytes())
        self.assertEqual(self.blob, json.loads(raw))
        self.assertNotIn('history_storage', json.loads(raw))
        self.assertEqual(folder, save_backups.create(self.root))

    def test_missing_or_changed_segment_is_not_silently_ignored(self):
        packed = history.pack(self.root, self.blob)
        segment = self.root/'history'/(packed['history_archive'][0]+'.json.gz')
        segment.write_bytes(gzip.compress(b'[]'))
        with self.assertRaises(ValueError): history.expand(self.root, packed)
        with self.assertRaises(ValueError): history.pack(self.root, self.blob)

    def test_reference_cannot_escape_archive(self):
        with self.assertRaises(ValueError):
            history.expand(self.root, dict(history_storage=1, history_archive=['../outside']))

    def test_single_large_event_is_archived_without_waiting_for_fifty(self):
        blob = dict(history=[dict(matches=[dict(rounds=list(range(500)))])], log=[])
        packed = history.pack(self.root, blob)
        self.assertEqual([], packed['history'])
        self.assertEqual(blob, history.expand(self.root, packed))

    def test_history_is_immutable_but_view_copies_remain_editable(self):
        state = SimpleNamespace(history=[freeze(self.blob['history'][0])])
        old = state.history[0]
        for edit in (lambda: old.update(event='changed'),
                     lambda: old['maps'].append({}),
                     lambda: old['maps'][0].__setitem__('score', '0-0')):
            with self.assertRaises(TypeError): edit()
        snapshot = deepcopy(state, snapshot_memo(state))
        self.assertIsNot(snapshot.history, state.history)
        self.assertIs(snapshot.history[0], old)
        state.history.append(freeze({'event':'next'}))
        self.assertEqual(1, len(snapshot.history))
        view = deepcopy(old)
        view['maps'][0]['score'] = '0-0'
        self.assertEqual('13-8', old['maps'][0]['score'])
        packed = history.pack(self.root, {'history':state.history, 'log':[]})
        self.assertEqual(state.history, history.expand(self.root, packed)['history'])

    def test_shallow_copy_returns_mutable_container_with_shared_children(self):
        old = freeze({'maps': [{'score': '13-8'}]})
        view = copy(old)
        self.assertIs(type(view), dict)
        self.assertIs(view['maps'], old['maps'])
        view['extra'] = True
        items = copy(old['maps'])
        self.assertIs(type(items), list)
        self.assertIs(items[0], old['maps'][0])
        items.append({})
        self.assertEqual(1, len(old['maps']))
        with self.assertRaises(TypeError): items[0]['score'] = '0-0'

    def test_pickle_roundtrip_produces_plain_editable_json_containers(self):
        old = freeze({'maps': [{'score': '13-8'}]})
        for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
            with self.subTest(protocol=protocol):
                view = pickle.loads(pickle.dumps(old, protocol=protocol))
                self.assertEqual(old, view)
                self.assertIs(type(view), dict)
                self.assertIs(type(view['maps']), list)
                self.assertIs(type(view['maps'][0]), dict)
                view['maps'][0]['score'] = '0-0'
                self.assertEqual('13-8', old['maps'][0]['score'])
