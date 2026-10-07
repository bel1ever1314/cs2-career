"""Candidate-to-game parity, reversible duties, growth, and save isolation."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs2career.world import build_teams, apply_roles
from cs2career.world.ability import (AXES, ability_of, calibrate_role, playing_ability,
                                    playing_stats, position_views, refresh_player_ability)
from cs2career.world.calibrated import (POSITIONS, express_axes, lookup, model_marker,
                                       role_fit, weighted_score)
from cs2career.world.aging import apply_player_year
from cs2career.world.pool import agent_rows
from cs2career.engine.match import snapshot_players
from cs2career.cs2.launch import build_request, install_match_avatars
from cs2career.cs2.profiles import prepare_bots
from cs2career.career import Career

QA_ROOT = Path(r'E:\CS2CareerTools\CalibrationIntegration-20261002\tests')


class CalibrationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = build_teams('2026')

    def selected(self, name='donk'):
        return deepcopy(next(p for t in self.world for p in t['players'] if p['name'] == name))

    def test_all_opening_eras_match_their_exact_candidate_base(self):
        for era in ('2024', '2025', '2026'):
            teams = build_teams(era)
            for team in teams:
                for player in team['players']:
                    candidate = lookup(player['name'], era, team['name'])
                    self.assertIsNotNone(candidate)
                    self.assertEqual({axis: player['stats'][axis] for axis in AXES}, dict(candidate['axes']))
                    self.assertEqual(player['stats']['ability'], candidate['overall'])
                    self.assertEqual(player['stats']['position_model']['reference_role'], candidate['reference_role'])
                    self.assertEqual(playing_ability(player),
                        round(candidate['overall'] + role_fit(player['stats'], player['role']), 3))
            def bases():
                return [{key: deepcopy(p['stats'][key]) for key in
                         (*AXES, 'ability', 'role_reference', 'role_reference_score', 'position_model')}
                        for t in teams for p in t['players']]
            frozen = bases()
            apply_roles(teams, era)
            self.assertEqual(frozen, bases())

    def test_preview_and_repeated_switches_do_not_grow_or_mutate_baseline(self):
        player = self.selected()
        original = deepcopy(player['stats'])
        views = {view['role']: view for view in position_views(player)}
        self.assertEqual(set(POSITIONS), set(views))
        for _ in range(30):
            for role in POSITIONS:
                player['role'] = role
                refresh_player_ability(player)
                self.assertEqual(views[role]['ability'], player['ability'])
                self.assertEqual({axis: views[role]['stats'][axis] for axis in AXES},
                                 express_axes(original, role))
                self.assertEqual(original, player['stats'])
        player['role'] = original['role_reference']
        refresh_player_ability(player)
        self.assertEqual(original['ability'], player['ability'])
        self.assertEqual(original, player['stats'])

    def test_miq_and_mongolz_axes_are_not_the_legacy_raw_style_percentiles(self):
        miq = next(p for t in build_teams('2025') for p in t['players'] if p['name'] == 'MiQ')
        self.assertEqual(lookup('MiQ', '2025', 'ATOX')['overall'], miq['stats']['ability'])
        self.assertLess(miq['stats']['firepower'], 90)
        mongolz = next(t for t in self.world if t['name'] == 'The MongolZ')
        self.assertTrue(all(p['stats']['entrying'] < 100 for p in mongolz['players']))

    def test_reference_training_improves_without_position_switch_bonus(self):
        player = self.selected('Westmelon')
        base = deepcopy(player['stats'])
        before = playing_ability(player)
        player['stats']['utility'] += 1
        refresh_player_ability(player)
        self.assertGreater(player['long_term_ability'], before)
        trained = deepcopy(player['stats'])
        reference = player['stats']['role_reference']
        expected = round(base['ability'] + weighted_score(trained, reference)
                         - weighted_score(base, reference), 3)
        player['role'] = 'awp'
        refresh_player_ability(player)
        self.assertEqual(expected, player['long_term_ability'])
        player['role'] = reference
        refresh_player_ability(player)
        self.assertEqual(expected, player['ability'])
        self.assertEqual(trained, player['stats'])

    def test_annual_growth_uses_same_reference_for_every_selected_duty(self):
        a = self.selected('donk')
        b = deepcopy(a)
        b['role'] = 'igl'
        refresh_player_ability(b)
        apply_player_year(a)
        apply_player_year(b)
        self.assertEqual(a['long_term_ability'], b['long_term_ability'])
        self.assertEqual(a['stats'], b['stats'])
        b['role'] = a['role']
        refresh_player_ability(b)
        self.assertEqual(a['ability'], b['ability'])

    def test_simulation_and_nine_cs2_bots_use_same_position_view(self):
        team = deepcopy(next(t for t in self.world if t['name'] == 'Spirit'))
        opponent = deepcopy(next(t for t in self.world if t['name'] == 'Vitality'))
        target = next(p for p in team['players'] if p['name'] == 'donk')
        target['role'] = 'awp'
        # A request boundary must not depend on a stale stored player.ability.
        expected = playing_ability(target)
        expected_axes = playing_stats(target)
        human = next(p for p in team['players'] if p is not target)
        before = deepcopy((team, opponent))
        request = build_request(team, opponent, human['name'], 'de_dust2', 'ct')
        QA_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='profiles-', dir=QA_ROOT) as raw:
            install_match_avatars(Path(raw), request)
            for difficulty in ('Low', 'Medium', 'High'):
                bots = prepare_bots(request, difficulty)
                self.assertEqual(9, len(bots))
                bot = next(b for b in bots if b['player_id'] == target['player_id'])
                self.assertEqual(expected, bot['overall'])
                self.assertEqual(expected_axes, bot['stats'])
        simulation = next(row for row in snapshot_players(team, opponent, 'dust2')
                          if row['player_id'] == target['player_id'])
        self.assertEqual(expected, simulation['ability'])
        self.assertEqual(before, (team, opponent))

    def test_all_free_agents_keep_their_calibrated_reference(self):
        for player in agent_rows():
            candidate = lookup(player['name'], '2026', kind='free_agent')
            self.assertIsNotNone(candidate)
            self.assertEqual(candidate['overall'], player['stats']['ability'])
            self.assertEqual(dict(candidate['axes']), {axis: player['stats'][axis] for axis in AXES})

    def test_legacy_saved_rows_are_not_overlaid_with_opening_candidates(self):
        player = self.selected()
        player['stats'].pop('position_model')
        calibrate_role(player['stats'], 'rifle', 64.7)
        player.update(ability=64.7, long_term_ability=64.7, role='rifle', you=True)
        team = dict(id='old', name='Old Save', players=[player], custom_roles=True, allow_no_awp=True)
        before = deepcopy(player['stats'])
        apply_roles([team], '2026')
        self.assertEqual(before, player['stats'])
        self.assertEqual(64.7, player['ability'])
        self.assertNotIn('position_model', player['stats'])

    def test_new_and_old_draw_creation_formulas_remain_distinct(self):
        for policy in ('calibrated_world_axes_v1', 'existing_world_axes_not_opponent_calibrated'):
            season = SimpleNamespace(teams=deepcopy(self.world), year=2026,
                date='2026-01-08', vrs=SimpleNamespace(seed=lambda *a: None))
            career = Career()
            career.player_name = 'Isolated Draw Rookie'
            career.origin, career.role, career.team_id = 'attribute_draw', 'entry', 'draw-rookie'
            career.incident_state = {'career3d_attribute_draw': {'value_policy': policy}}
            values = {axis: 80.0 for axis in AXES}
            career._spawn_org(season, 'Isolated Draw Club', {'_start_attributes': values})
            player = next(p for p in season.teams[-1]['players'] if p.get('you'))
            self.assertEqual(values, {axis: player['stats'][axis] for axis in AXES})
            if policy == 'calibrated_world_axes_v1':
                self.assertEqual(80.0, player['ability'])
                self.assertIn('position_model', player['stats'])
            else:
                self.assertEqual(ability_of(values, 'entry'), player['ability'])
                self.assertNotIn('position_model', player['stats'])
            self.assertTrue(all(p['stats'].get('position_model') for p in season.teams[-1]['players'] if not p.get('you')))

    def test_save_roundtrip_preserves_growth_and_position_without_reseeding(self):
        from contextlib import ExitStack
        from cs2career.application import ApplicationState
        QA_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='roundtrip-', dir=QA_ROOT) as raw, ExitStack() as stack:
            root = Path(raw)
            stack.enter_context(patch('cs2career.league.season.STATE_PATH', root / 'season.json'))
            stack.enter_context(patch.object(Career, 'path', return_value=root / 'career.json'))
            stack.enter_context(patch('cs2career.paths.save_root', return_value=root))
            state = ApplicationState()
            state.create_career(dict(era='2026', mode='join', team_id='spirit', replace='magixx', role='rifle'))
            player = state.career.my_player(state.season.teams)
            player['stats']['firepower'] += 1
            player['role'] = 'lurk'
            state.career.my_team(state.season.teams)['custom_roles'] = True
            refresh_player_ability(player)
            state.persist()
            frozen = deepcopy(player)
            # If load accidentally calls new-world calibration this sentinel
            # would replace both the user's growth and selected position.
            with patch('cs2career.world.teams.build_teams', side_effect=AssertionError('reseed on load')):
                restored = ApplicationState()
            after = restored.career.my_player(restored.season.teams)
            for key in ('stats', 'role', 'ability', 'long_term_ability'):
                self.assertEqual(frozen[key], after[key])

    def test_custom_rts_uses_current_position_expression_without_mutating_axes(self):
        from tools.career3d_activities import _custom_rts_rosters
        players = [deepcopy(p) for team in self.world[:2] for p in team['players']]
        ids = [p['player_id'] for p in players]
        lobby = dict(ct='a', map='dust2', human_id=ids[0], a=ids[:5], b=ids[5:],
                     roster=dict(zip(ids, players)))
        baseline = [deepcopy(p['stats']) for p in players]
        aliases = dict(aim='firepower', reaction='opening', recoil='trading',
                       awareness='clutching', utility='utility')
        for role in POSITIONS:
            players[0]['role'] = role
            projection = _custom_rts_rosters(lobby)
            actual = projection['ct'][0]
            expression = playing_stats(players[0])
            self.assertEqual(actual['ability'], playing_ability(players[0]))
            self.assertEqual(actual['skills'], {key: expression[axis] for key, axis in aliases.items()})
            self.assertEqual([p['stats'] for p in players], baseline)


if __name__ == '__main__':
    unittest.main()
