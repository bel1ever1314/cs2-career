"""Calibrated donors and durable schema-2 draw compatibility, isolated on E:."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cs2career.world.ability import AXES
from tools import career3d_attribute_draw as draw


MODEL_VERSION = 'full-roster-prototype-2-positions'
TEST_ROOT = Path(r'E:\CS2CareerTools\CalibrationIntegration-20261002\tests')


def donor_pool(calibrated=False):
    players = []
    for index, role in enumerate(('rifle', 'entry', 'awp', 'lurk', 'igl')):
        player = dict(source_player_id=f'p_donor_{index}', player_id=f'p_donor_{index}',
            source_player=f'Donor {index}', source_team_id='donors', source_team='Donors',
            source_era='2026', source='isolated-fixture', data_quality='estimated',
            role=role, ability=71.5 + index,
            stats={axis: 61.25 + index + offset / 10 for offset, axis in enumerate(AXES)})
        if calibrated:
            player['calibration_model_version'] = MODEL_VERSION
        players.append(player)
    return [dict(team_id='donors', source_team_id='donors', source_team='Donors',
        source_era='2026', vrs_rank=1, vrs_points=1000, vrs_as_of='2026-01-08',
        vrs_model='isolated-fixture', vrs_source='same_era_opening_game_vrs_seed',
        players=players, band='common', band_label='普通', band_color='b8c3cc',
        band_probability=1.0, team_probability=1.0)]


class CalibratedDrawTests(unittest.TestCase):
    def setUp(self):
        TEST_ROOT.mkdir(parents=True, exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(prefix='calibrated-draw-', dir=TEST_ROOT)
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root / 'save').mkdir()
        (self.root / 'extensions').mkdir()
        (self.root / '.career3d-demo.json').write_text(
            json.dumps({'kind': 'cs2career-godot-demo'}), encoding='utf-8')
        self.env = patch.dict(os.environ, {
            'CS2CAREER_SAVE_DIR': str(self.root / 'save'),
            'CS2CAREER_EXTENSION_DIR': str(self.root / 'extensions')})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.metadata = self.root / draw.METADATA_NAME

    def command(self, action, **body):
        return draw.draw_command(None, action, dict(era='2026', **body))

    def legacy_store(self):
        pool = donor_pool()
        team = deepcopy(pool[0])
        team.update(draw_id='old-first-team', attempt=1, selection=None)
        pending = dict(schema_version=2, draft_id='old-schema2-draft', era='2026',
            revision=1, status='pending', max_draws=10,
            selection_scope=draw.SELECTION_SCOPE, value_policy=draw.LEGACY_VALUE_POLICY,
            pool_version='sha256:' + draw._hash(pool), source_pool=pool,
            team_draws=[team], pending_draw_id=team['draw_id'], axes={axis: None for axis in AXES})
        receipt_result = dict(reason='original frozen roll', attribute_draw=draw._public(pending),
            draw=deepcopy(team), rolled_draw_id=team['draw_id'])
        selected = deepcopy(pending)
        selected['team_draws'][0]['selection'] = draw._candidate(
            team['players'][0], AXES[0], selected['team_draws'][0])
        selected['axes'][AXES[0]] = team['draw_id']
        selected['pending_draw_id'] = None
        selected['revision'] = 2
        identity = dict(schema_version=2, action='roll', era='2026',
            draft_id=selected['draft_id'], axis=None, draw_id=None, player_id=None)
        store = draw._empty_store()
        store['drafts'][selected['draft_id']] = selected
        store['active_team_drafts']['2026'] = selected['draft_id']
        store['receipts']['old-roll-request'] = dict(schema_version=2,
            hash=draw._hash(identity), result=receipt_result)
        store['create_receipts']['old-create-receipt'] = dict(hash='old-digest',
            result={'reason': 'previously created career', 'new_career': True})
        draw._save(store)
        return json.loads(self.metadata.read_text(encoding='utf-8'))

    def fill_remaining(self, draft_id, axes):
        values = {}
        for axis in axes:
            rolled = self.command('roll', draft_id=draft_id,
                request_id='fill-roll-' + axis)['draw']
            selected = self.command('select', draft_id=draft_id, draw_id=rolled['draw_id'],
                axis=axis, player_id=rolled['players'][0]['player_id'], value=100,
                request_id='fill-select-' + axis)['selection']
            self.assertEqual(rolled['players'][0]['stats'][axis], selected['value'])
            values[axis] = selected['value']
        return values

    def test_source_pool_freezes_current_position_and_marks_only_calibrated_donors(self):
        originals = [{**deepcopy(player), 'name': player['source_player']}
                     for player in donor_pool()[0]['players']]
        team = dict(id='donors', name='Donors', players=originals)
        before = deepcopy(team)
        viewed = {}
        for index, player in enumerate(originals):
            viewed[player['player_id']] = {axis: value + 4 for axis, value in player['stats'].items()}
            if index == 0:
                viewed[player['player_id']]['position_model'] = {
                    'schema_version': 1, 'model_version': MODEL_VERSION}
        with patch('cs2career.world.ability.playing_stats',
                   side_effect=lambda player: deepcopy(viewed[player['player_id']])) as stats_view, \
             patch('cs2career.world.ability.playing_ability', return_value=88.5) as ability_view:
            rows = draw.source_pool('2026', teams=[team])
        self.assertEqual(5, stats_view.call_count)
        self.assertEqual(5, ability_view.call_count)
        for row in rows:
            self.assertEqual({axis: viewed[row['player_id']][axis] for axis in AXES}, row['stats'])
            self.assertEqual(88.5, row['ability'])
        self.assertEqual(MODEL_VERSION, rows[0]['calibration_model_version'])
        self.assertTrue(all('calibration_model_version' not in row for row in rows[1:]))
        rows[0]['stats']['firepower'] = 99
        self.assertEqual(before, team)

    def test_old_active_schema2_draft_and_receipts_are_preserved(self):
        original = self.legacy_store()
        before = self.metadata.read_bytes()
        old = original['drafts']['old-schema2-draft']
        public = draw.draw_context()['attribute_draw']
        self.assertEqual(draw.LEGACY_VALUE_POLICY, public['value_policy'])
        self.assertEqual(1, public['attempts_used'])
        self.assertEqual(before, self.metadata.read_bytes())
        replay = self.command('roll', draft_id=old['draft_id'], request_id='old-roll-request')
        self.assertEqual({**original['receipts']['old-roll-request']['result'], 'replayed': True}, replay)
        self.assertEqual(before, self.metadata.read_bytes())
        with patch.object(draw, 'team_source_pool', side_effect=AssertionError('must retain old pool')):
            opened = self.command('open', request_id='reopen-old-draft')['attribute_draw']
        self.assertEqual(old['draft_id'], opened['draft_id'])
        self.assertEqual(1, opened['attempts_used'])
        self.assertEqual(9, opened['remaining'])
        current = draw._load()
        self.assertEqual(old, current['drafts'][old['draft_id']])
        self.assertEqual(original['receipts']['old-roll-request'], current['receipts']['old-roll-request'])
        self.assertEqual(original['create_receipts'], current['create_receipts'])

    def test_real_era_donors_match_current_playing_views_without_mutating_world(self):
        from cs2career.world import build_teams
        from cs2career.world.ability import playing_ability, playing_stats
        for era in ('2024', '2025', '2026'):
            with self.subTest(era=era):
                world = build_teams(era)
                before = deepcopy(world)
                originals = {player['player_id']: player for team in world for player in team['players']}
                rows = draw.source_pool(era, teams=world)
                self.assertTrue(rows)
                self.assertTrue(any(row.get('calibration_model_version') for row in rows))
                for row in rows:
                    player = originals[row['player_id']]
                    view = playing_stats(player)
                    self.assertEqual({axis: view[axis] for axis in AXES}, row['stats'])
                    self.assertEqual(playing_ability(player), row['ability'])
                    if view.get('position_model'):
                        self.assertEqual(view['position_model']['model_version'], row['calibration_model_version'])
                self.assertEqual(before, world)
        self.assertFalse(self.metadata.exists())
        self.assertFalse(list((self.root / 'save').iterdir()))

    def test_completed_legacy_draft_reports_its_own_policy_and_exact_values(self):
        original = self.legacy_store()
        old = original['drafts']['old-schema2-draft']
        expected = {AXES[0]: old['team_draws'][0]['selection']['value']}
        expected.update(self.fill_remaining(old['draft_id'], AXES[1:]))
        before = self.metadata.read_bytes()
        values, provenance = draw.selected_attributes(old['draft_id'], '2026')
        self.assertEqual(expected, values)
        self.assertEqual(draw.LEGACY_VALUE_POLICY, provenance['value_policy'])
        self.assertEqual(7, provenance['attempts_used'])
        self.assertEqual(old['pool_version'], provenance['pool_version'])
        self.assertTrue(all('calibration_model_version' not in row for row in provenance['selections'].values()))
        self.assertEqual(before, self.metadata.read_bytes())
        self.assertEqual(old['source_pool'], draw._load()['drafts'][old['draft_id']]['source_pool'])

    def test_new_draft_uses_calibrated_policy_and_persists_source_versions(self):
        pool = donor_pool(calibrated=True)
        with patch.object(draw, 'team_source_pool', return_value=deepcopy(pool)):
            opened = self.command('open', request_id='open-calibrated-draft')['attribute_draw']
        self.assertEqual(draw.VALUE_POLICY, opened['value_policy'])
        self.assertEqual('calibrated_world_axes_v1', draw.draw_options()['value_policy'])
        expected = self.fill_remaining(opened['draft_id'], AXES)
        values, provenance = draw.selected_attributes(opened['draft_id'], '2026')
        self.assertEqual(expected, values)
        self.assertEqual(draw.VALUE_POLICY, provenance['value_policy'])
        self.assertEqual('sha256:' + draw._hash(pool), provenance['pool_version'])
        for row in provenance['selections'].values():
            self.assertEqual(MODEL_VERSION, row['calibration_model_version'])
            self.assertEqual('isolated-fixture', row['source'])
        self.assertEqual(pool, draw._load()['drafts'][opened['draft_id']]['source_pool'])
        self.assertFalse(list((self.root / 'save').iterdir()), 'Draw commands must not create career save files')

    def test_unknown_value_policy_fails_without_resetting_or_rewriting_draft(self):
        store = self.legacy_store()
        store['drafts']['old-schema2-draft']['value_policy'] = 'unknown-policy'
        draw._save(store)
        before = self.metadata.read_bytes()
        with self.assertRaises(ValueError):
            draw.draw_context()
        self.assertEqual(before, self.metadata.read_bytes())


if __name__ == '__main__':
    unittest.main()
