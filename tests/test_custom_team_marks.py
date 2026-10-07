"""Uploaded club marks across transactions, media and CS2 request freezing."""
import base64
import binascii
from copy import deepcopy
import json
import struct
from unittest.mock import patch
import zlib
import unittest

import test_recovery_http as fixtures
from cs2career.services import team_marks, resources
from cs2career.cs2 import launch
from cs2career.storage import transaction as tx
from cs2career.arena import Arena


def png(size=64, color=b'\x20\x40\x60\xff'):
    def chunk(kind, content):
        return struct.pack('>I', len(content)) + kind + content + struct.pack('>I', binascii.crc32(kind + content) & 0xffffffff)
    return (team_marks.PNG + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress((b'\0' + color * size) * size)) + chunk(b'IEND', b''))


class CustomTeamMarksTests(unittest.TestCase):
    serving = fixtures.RecoveryHttpTests.serving
    request = fixtures.RecoveryHttpTests.request
    career_fixture = fixtures.RecoveryHttpTests.career_fixture

    def setUp(self):
        fixtures.RecoveryHttpTests.setUp(self)
        self.career_fixture()
        self.state.career.mode = 'create'
        self.state.career.personal_transfers['player_only'] = False
        self.team = self.state.career.my_team(self.state.season.teams)
        self.body = dict(team_id=self.team['id'], kind='club', revision=0,
            panel_png=base64.b64encode(png(128)).decode(), avatar_png=base64.b64encode(png()).decode())

    def test_upload_http_commits_images_team_and_receipt_and_retry_once(self):
        with self.serving():
            code, out = self.request('/api/3d/controls/team-logo', self.body, rid='custom-logo-save-001')
            self.assertEqual(200, code, out)
            mark = team_marks.mark_path(self.team)
            self.assertTrue(mark.is_file())
            self.assertEqual(str(mark), out['context']['media']['team_backgrounds'][self.team['name']])
            disk = json.loads((self.root/'season.json').read_text('utf-8'))
            saved = next(t for t in disk['teams'] if t['id'] == self.team['id'])
            self.assertEqual(saved['career_marks'], self.team['career_marks'])
            code, repeat = self.request('/api/3d/controls/team-logo', self.body, rid='custom-logo-save-001')
            self.assertEqual(200, code, repeat)
            self.assertTrue(repeat['replayed'])
            self.assertEqual(2, len(list(self.root.glob('team-mark-*.png'))))

    def test_invalid_second_image_and_stale_or_foreign_team_make_no_changes(self):
        for change in [dict(panel_png='broken'), dict(avatar_png=base64.b64encode(png(65)).decode()),
                       dict(team_id='../not-our-team'), dict(revision=-1)]:
            with self.subTest(change=list(change)), self.serving():
                before = deepcopy(self.team)
                code, result = self.request('/api/3d/controls/team-logo', dict(self.body, **change))
                self.assertEqual(400, code, result)
                self.assertEqual(before, self.state.career.my_team(self.state.season.teams))
                self.assertFalse(list(self.root.glob('team-mark-*.png')))

    def test_joined_club_is_not_editable(self):
        self.state.career.mode = 'join'
        with self.serving():
            code, _ = self.request('/api/3d/controls/team-logo', self.body)
        self.assertEqual(400, code)
        self.assertFalse(list(self.root.glob('team-mark-*.png')))

    def test_transaction_failure_leaves_old_mark_and_no_new_images(self):
        with self.state.operation():
            team_marks.command(self.state, self.body)
            self.state.persist()
        before = deepcopy(self.team['career_marks'])
        files = set(self.root.glob('team-mark-*.png'))
        def fail(point):
            if point == 'before_commit': raise OSError('fixture disk failure')
        with patch.object(tx, '_checkpoint', side_effect=fail):
            with self.assertRaises(OSError), self.state.operation():
                team_marks.command(self.state, dict(self.body, kind='avatar', avatar_png=base64.b64encode(png(color=b'\xff\x00\x00\xff')).decode()))
                self.state.persist()
        self.assertEqual(before, self.state.career.my_team(self.state.season.teams)['career_marks'])
        self.assertEqual(files, set(self.root.glob('team-mark-*.png')))

    def test_cs2_avatar_frozen_and_separate_avatar_preserves_panel(self):
        with self.state.operation():
            team_marks.command(self.state, self.body)
            self.state.persist()
        previous = deepcopy(self.team['career_marks'])
        opponent = next(t for t in self.state.season.teams if t['id'] != self.team['id'])
        request = launch.build_request(self.team, opponent, self.state.career.player_name, 'de_dust2', 'ct')
        with self.state.operation():
            team_marks.command(self.state, dict(self.body, kind='avatar', avatar_png=base64.b64encode(png(color=b'\xaa\x33\x22\xff')).decode()))
            self.state.persist()
        self.assertEqual(previous['panel'], self.team['career_marks']['panel'])
        self.assertNotEqual(previous['avatar'], self.team['career_marks']['avatar'])
        self.assertEqual(previous, request['ct']['career_marks'])
        path, kind = launch._safe_avatar_source(request['ct'])
        self.assertEqual('custom', kind)
        self.assertIn(previous['avatar'], path.name)
        game = self.root/'fake-game'
        launch.install_match_avatars(game, request)
        self.assertTrue(all(p['avatar_hash'] == previous['avatar'] for p in request['ct']['players']))
        # Read-only projection never regenerates/rewrites assets.
        stamps = {p:p.stat().st_mtime_ns for p in self.root.glob('team-mark-*.png')}
        resources.resource_context(self.state)
        self.assertEqual(stamps, {p:p.stat().st_mtime_ns for p in stamps})

    def test_rejects_truncated_oversized_animation_and_crc_invalid_png(self):
        for blob in [png()[:-1], png(513), png()+b'extra', png().replace(b'IDAT', b'acTL'), b'not png']:
            with self.assertRaises(ValueError): team_marks.validate_png(blob)
        team_marks.validate_png(png())

    def test_custom_and_ladder_rosters_freeze_uploaded_avatar_with_club(self):
        with self.state.operation():
            team_marks.command(self.state, self.body)
            self.state.persist()
        roster = list(Arena(self.root/'arena.json').roster(self.state).values())
        ours = [p for p in roster if p.get('club_id') == self.team['id']]
        self.assertTrue(ours)
        self.assertTrue(all(p['club_marks'] == self.team['career_marks'] for p in ours))
        players = ours[:5] + [p for p in roster if p.get('club_id') != self.team['id']][:5]
        a = dict(id='custom-a', name='A', players=players[:5])
        b = dict(id='custom-b', name='B', players=players[5:])
        request = launch.build_lobby_request(a, b, '', 'de_dust2', 'mark-fixture')
        launch.install_match_avatars(self.root/'fake-game', request)
        for player in request['ct']['players']:
            self.assertEqual(player['avatar_hash'], self.team['career_marks']['avatar'])

    def test_committed_crash_recovers_mark_bytes_and_team_reference_together(self):
        def fail(point):
            if point == 'committed': raise OSError('fixture process stopped after commit')
        with patch.object(tx, '_checkpoint', side_effect=fail):
            with self.assertRaises(tx.CommitPending), self.state.operation():
                team_marks.command(self.state, self.body)
                self.state.persist()
        tx.recover(self.root)
        season = json.loads((self.root/'season.json').read_text('utf-8'))
        team = next(t for t in season['teams'] if t['id'] == self.team['id'])
        self.assertEqual(png(128), team_marks.mark_path(team).read_bytes())
        self.assertEqual(png(), team_marks.mark_path(team, 'avatar').read_bytes())
