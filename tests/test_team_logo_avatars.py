"""Offline avatar hand-off; only temporary game folders, never Steam or CS2."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from cs2career.arena import Arena
from cs2career.cs2 import avatars, launch
from cs2career.cs2.profiles import active_manifest, generate_match_vpk
from cs2career.paths import data_file, static_dir
from test_arena import fixture_state
from test_v15_core import fake_team


class TeamLogoAvatarTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.csgo = self.root / 'game' / 'csgo'
        self.csgo.mkdir(parents=True)
        self.default = static_dir() / 'team_avatars/default.png'

    def mixed_request(self, human=False):
        a, b = fake_team('A', 80), fake_team('B', 82)
        clubs = ['Spirit', 'Vitality', 'Unlisted Club', '', 'Falcons',
                 'Vitality', 'Spirit', 'FURIA', 'The MongolZ', 'NAVI']
        for player, club in zip(a['players'] + b['players'], clubs):
            player['club'] = club
            player['club_id'] = club.lower().replace(' ', '-')
        # These are matchmaking sides, not clubs.
        a.update(id='arena-a', name='Team A')
        b.update(id='arena-b', name='Team B')
        human_id = a['players'][0]['player_id'] if human else ''
        return launch.build_lobby_request(a, b, human_id, 'de_dust2', 'abc123abcd1234')

    @staticmethod
    def bot_rows(request):
        return request['ct']['players'] + request['t']['players']

    def test_all_curated_marks_are_small_square_pngs_with_provenance(self):
        catalog = json.loads(data_file('team_logo_avatars/manifest.json').read_text('utf-8'))
        self.assertEqual(catalog['schema_version'], 1)
        self.assertEqual(catalog['appearance'], 'graphite_translucent_v1')
        self.assertEqual(catalog['background'], '202428b3')
        self.assertEqual(len(catalog['teams']), 48)
        hashes = set()
        for row in catalog['teams'].values():
            with self.subTest(team=row['name']):
                path = avatars.club_mark({'name': row['name']})
                self.assertIsNotNone(path)
                data = path.read_bytes()
                self.assertEqual(data[:8], launch.PNG_SIGNATURE)
                self.assertLessEqual(len(data), launch.AVATAR_MAX_BYTES)
                self.assertEqual(struct.unpack('>II', data[16:24]), (64, 64))
                self.assertEqual(data[25], 6, 'PNG must retain RGBA rather than flatten onto a white RGB tile')
                self.assertEqual(hashlib.sha256(data).hexdigest(), row['sha256'])
                self.assertTrue(row['source'].startswith('https://raw.githubusercontent.com/Juknum/'))
                self.assertEqual(len(row['source_sha256']), 64)
                hashes.add(row['sha256'])
        self.assertEqual(len(hashes), 48)

    def test_only_dark_marks_receive_a_local_contrast_keyline(self):
        catalog = json.loads(data_file('team_logo_avatars/manifest.json').read_text('utf-8'))
        self.assertTrue(catalog['teams']['furia']['dark_mark_keyline'])
        self.assertFalse(catalog['teams']['spirit']['dark_mark_keyline'])
        self.assertFalse(catalog['teams']['falcons']['dark_mark_keyline'])

    def test_lookup_is_exact_normalized_not_fuzzy(self):
        self.assertEqual(avatars.club_mark({'name': '  SPIRIT  '}), avatars.club_mark({'team_id': 'spirit'}))
        self.assertIsNotNone(avatars.club_mark({'team_id': 'the-mongolz'}))
        for name in ('Spirit Academy', 'NAVI Junior', 'My Spirit', '', '../../spirit'):
            self.assertIsNone(avatars.club_mark({'name': name}))

    def test_bad_optional_catalog_and_payload_fall_back(self):
        folder = self.root / 'catalog'
        folder.mkdir()
        mark = folder / 'spirit.png'
        mark.write_bytes(avatars.club_mark({'name': 'Spirit'}).read_bytes())
        manifest = folder / 'manifest.json'
        for entry in ({'file':'../spirit.png', 'sha256':'x'},
                      {'file':'spirit.png', 'sha256':'bad'},
                      {'file':'missing.png', 'sha256':'x'}):
            manifest.write_text(json.dumps({'schema_version':1, 'teams':{'spirit':entry}}), 'utf-8')
            avatars._catalog.cache_clear()
            with patch.object(avatars, 'data_file', return_value=folder):
                self.assertIsNone(avatars.club_mark({'name':'Spirit'}))
                self.assertEqual(launch._safe_avatar_source({'name':'Spirit'}, use_legacy_crest=False), (self.default, 'default'))
        manifest.write_text('{broken', 'utf-8')
        avatars._catalog.cache_clear()
        with patch.object(avatars, 'data_file', return_value=folder):
            self.assertIsNone(avatars.club_mark({'name':'Spirit'}))
        avatars._catalog.cache_clear()

    def test_user_uploaded_safe_logo_still_takes_precedence(self):
        folder = self.root / 'user-logos'
        folder.mkdir()
        uploaded = folder / 'spirit.png'
        uploaded.write_bytes(self.default.read_bytes())
        with patch.object(launch, 'logo_dir', return_value=folder):
            self.assertEqual(launch._safe_avatar_source({'team_id':'spirit', 'name':'Spirit'}), (uploaded, 'custom'))
            uploaded.write_bytes(b'not a png')
            self.assertEqual(launch._safe_avatar_source({'team_id':'spirit', 'name':'Spirit'}),
                             (avatars.club_mark({'name':'Spirit'}), 'team'))

    def test_mixed_clubs_use_individual_marks_and_keep_neutral_fallback(self):
        request = self.mixed_request()
        with patch('urllib.request.urlopen', side_effect=AssertionError('No network for avatars')):
            launch.install_match_avatars(self.csgo, request)
        bots = self.bot_rows(request)
        for bot in bots:
            club = request['avatar_teams'][bot['player_id']]
            expected = avatars.club_mark(club) or self.default
            self.assertEqual(Path(bot['avatar_path']).read_bytes(), expected.read_bytes())
            self.assertEqual(bot['avatar_hash'], hashlib.sha256(expected.read_bytes()).hexdigest())
            self.assertTrue(Path(bot['avatar_path']).is_relative_to(launch.plugin_dir(self.csgo) / 'avatars'))
        self.assertNotEqual(bots[0]['avatar_hash'], bots[1]['avatar_hash'])
        self.assertEqual(bots[0]['avatar_path'], bots[6]['avatar_path'])
        self.assertEqual(bots[1]['avatar_path'], bots[5]['avatar_path'])
        self.assertEqual(bots[2]['avatar_kind'], 'default')
        self.assertEqual(bots[3]['avatar_kind'], 'default')

    def test_missing_mark_does_not_start_using_a_legacy_letter_crest(self):
        request = self.mixed_request()
        bot = self.bot_rows(request)[0]
        with patch.object(avatars, 'club_mark', return_value=None):
            launch.install_match_avatars(self.csgo, request)
        self.assertEqual(bot['avatar_kind'], 'default')
        self.assertEqual(Path(bot['avatar_path']).read_bytes(), self.default.read_bytes())

    def test_human_identity_excluded_and_observer_keeps_ten_distinct_ids(self):
        for human in (False, True):
            with self.subTest(human=human):
                request = self.mixed_request(human)
                count = 9 if human else 10
                self.assertEqual(len(request['avatar_teams']), count)
                self.assertNotIn(request['human_player_id'], request['avatar_teams'])
                launch.install_match_avatars(self.csgo, request)
                manifest = generate_match_vpk(self.csgo, request, 'Medium', self.root / 'cache')
                launch.install_match_identities(self.csgo, request)
                self.assertEqual(manifest['count'], count)
                self.assertEqual(len({row['steam_id'] for row in self.bot_rows(request)}), count)
                self.assertTrue(active_manifest(self.csgo)['valid'])

    def test_profile_regeneration_retains_clubs_after_json_round_trip(self):
        request = self.mixed_request()
        launch.install_match_avatars(self.csgo, request)
        manifest = generate_match_vpk(self.csgo, request, 'Medium', self.root / 'cache')
        hashes = {b['player_id']:b['avatar_hash'] for b in manifest['bots']}
        restored = json.loads(json.dumps(request))
        launch.install_match_avatars(self.csgo, restored)
        regenerated = generate_match_vpk(self.csgo, restored, 'High', self.root / 'cache')
        self.assertEqual(hashes, {b['player_id']:b['avatar_hash'] for b in regenerated['bots']})
        self.assertTrue(active_manifest(self.csgo)['valid'])

    def test_cosmetic_change_does_not_change_abilities_purchases_or_identity(self):
        request = self.mixed_request()
        neutral = deepcopy(request)
        neutral.pop('avatar_teams')
        launch.install_match_avatars(self.csgo, neutral)
        old = generate_match_vpk(self.csgo, neutral, 'High', self.root / 'cache')
        old_ids = launch.install_match_identities(self.csgo, neutral)
        launch.install_match_avatars(self.csgo, request)
        new = generate_match_vpk(self.csgo, request, 'High', self.root / 'cache')
        new_ids = launch.install_match_identities(self.csgo, request)
        self.assertEqual(old['vpk_sha256'], new['vpk_sha256'])
        self.assertEqual(old_ids, new_ids)
        self.assertNotEqual(old['manifest_hash'], new['manifest_hash'])
        for before, after in zip(old['bots'], new['bots']):
            for key in ('profile_hash','parameters','stats','role','overall','effective_strength'):
                self.assertEqual(before[key], after[key])

    def test_old_lobby_with_only_club_name_still_resolves(self):
        request = self.mixed_request()
        for team in request['avatar_teams'].values(): team.pop('team_id')
        launch.install_match_avatars(self.csgo, request)
        self.assertEqual(self.bot_rows(request)[0]['avatar_kind'], 'team')

    def test_old_requests_without_club_metadata_keep_team_fallback(self):
        request = launch.build_request(fake_team('Vitality',90), fake_team('Unknown',80), 'Vitality0', 'de_mirage', 'ct')
        self.assertNotIn('avatar_teams', request)
        launch.install_match_avatars(self.csgo, request)
        self.assertEqual({b['avatar_kind'] for b in request['ct']['players']}, {'team'})
        self.assertEqual({b['avatar_kind'] for b in request['t']['players']}, {'default'})

    def test_lobby_freezes_clubs_and_next_lobby_observes_transfers(self):
        state = fixture_state()
        state.season.teams[0].update(id='spirit', name='Spirit')
        state.season.teams[1].update(id='vitality', name='Vitality')
        arena = Arena(self.root / 'arena.json')
        ids = list(arena.roster(state))[:10]
        arena.create(state, {'revision':0, 'mode':'custom', 'players':ids})
        frozen = arena.data['lobby']['roster'][ids[0]]
        self.assertEqual((frozen['club_id'], frozen['club']), ('spirit', 'Spirit'))
        moved = state.season.teams[0]['players'].pop(0)
        state.season.teams[1]['players'].append(moved)
        self.assertEqual(frozen['club_id'], 'spirit')
        self.assertEqual(arena.roster(state)[ids[0]]['club_id'], 'vitality')
        state.season.teams[1]['players'].remove(moved)
        state.career.free.append(dict(moved, club='Spirit', club_id='spirit'))
        self.assertEqual(arena.roster(state)[ids[0]]['club_id'], '')

    def test_ladder_and_custom_launcher_preserve_individual_clubs(self):
        for mode in ('rank', 'custom'):
            with self.subTest(mode=mode):
                state = fixture_state()
                state.season.teams[0].update(id='spirit', name='Spirit')
                state.season.teams[1].update(id='vitality', name='Vitality')
                arena = Arena(self.root / (mode + '.json'))
                ids = list(arena.roster(state))[:10]
                if mode == 'custom': arena.create(state, {'revision':0, 'mode':mode, 'players':ids})
                else: arena.matchmake(state, {'revision':0})
                for _ in range(30):
                    lobby = arena.data['lobby']
                    body = {'revision':arena.data['revision']}
                    if lobby['phase'] == 'ready': break
                    if not arena.turn(lobby)['human']: arena.advance(body)
                    elif lobby['phase'] == 'draft':
                        arena.pick(dict(body, player_id=next(p for p in lobby['selection'] if p not in lobby['a'] + lobby['b'])))
                    elif lobby['phase'] == 'veto': arena.ban(dict(body, map=lobby['map_pool'][0]))
                    else: arena.choose_side(dict(body, side='ct'))
                else: self.fail('Draft did not finish')
                with patch.object(launch, 'require_cs2_closed'), patch.object(launch, 'start_match', return_value={'msg':'ok'}) as start:
                    arena.launch(state, {'revision':arena.data['revision']})
                request = start.call_args.kwargs['request_override']
                for bot in self.bot_rows(request):
                    pid = bot['player_id']
                    self.assertEqual(request['avatar_teams'][pid]['name'], lobby['roster'][pid]['club'])
                    self.assertEqual(request['avatar_teams'][pid]['team_id'], lobby['roster'][pid]['club_id'])
                self.assertEqual(request['avatar_teams'], arena.data['lobby']['request']['avatar_teams'])

    def test_assets_and_builder_are_in_source_package_inputs(self):
        from tools.career3d_package_sources import source_files
        root = Path(__file__).resolve().parents[1]
        selected = {p.relative_to(root).as_posix() for p in source_files(root)}
        self.assertIn('tools/build_team_logo_avatars.gd', selected)
        self.assertIn('cs2career/cs2/avatars.py', selected)
        for path in data_file('team_logo_avatars').iterdir():
            self.assertIn(path.relative_to(root).as_posix(), selected)
