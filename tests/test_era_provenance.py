"""Data coverage is not historical accuracy; never relabel an old identity."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from cs2career import presentation
from cs2career.content.loader import PackRegistry
from cs2career.world import build_teams, apply_roles
from cs2career.world.eras import player_id, roster_for
from cs2career.world.era_data import correction_for, coverage, quality_view, validate_rosters


class EraProvenanceTests(unittest.TestCase):
    def test_parivision_2024_dated_roster_and_roles(self):
        teams = build_teams('2024')
        apply_roles(teams, '2024')
        pari = next(t for t in teams if t['name'] == 'PARIVISION')
        self.assertEqual({'Jerry', 'X5G7V', 'Patsi', 'Qikert', 'ArtFr0st'}, {p['name'] for p in pari['players']})
        self.assertEqual('igl', next(p for p in pari['players'] if p['name'] == 'Jerry')['role'])
        self.assertEqual('awp', next(p for p in pari['players'] if p['name'] == 'ArtFr0st')['role'])
        self.assertEqual({73, 70, 68, 66, 63}, {p['ability'] for p in pari['players']})
        self.assertEqual('verified', quality_view(pari, team=True)['status'])
        self.assertEqual('2024-01-08', quality_view(pari, team=True)['as_of'])
        self.assertTrue(all(p['era_provenance']['ability_quality'] == 'estimated' for p in pari['players']))
        ids = [p['player_id'] for t in teams for p in t['players']]
        self.assertEqual(len(ids), len(set(ids)))

    def test_future_announcement_duplicate_and_nonfinite_are_rejected(self):
        row = correction_for('2024', 'PARIVISION')
        for field, value in [('announced_at', '2024-01-09'), ('as_of', '2025-01-08')]:
            bad = deepcopy(row)
            bad[field] = value
            with self.assertRaises(ValueError):
                validate_rosters({'schema_version': 1, 'rosters': [bad]})
        for mutate in (lambda r: r['players'][0].update(ability=float('nan')),
                       lambda r: r['players'][0].update(name=r['players'][1]['name']),
                       lambda r: r['sources'][0].update(url='javascript:alert(1)'),
                       lambda r: r['players'].pop()):
            bad = deepcopy(row)
            mutate(bad)
            with self.assertRaises(ValueError):
                validate_rosters({'schema_version': 1, 'rosters': [bad]})

    def test_old_slot_warning_is_read_only_and_not_rebound_to_real_player(self):
        name = 'PARIVISION 2024 slot2'
        old = {'name': name, 'player_id': player_id(name), 'role': 'rifle', 'ability': 70,
               'source': 'same-era-role-template-2024', 'data_quality': 'estimated'}
        original = deepcopy(old)
        career = SimpleNamespace(free=[old], inspect_player=Mock(return_value={'name': name}))
        season = SimpleNamespace(teams=[], events=[], history=[], year=2024, date='2024-02-01',
                                 records=lambda **kwargs: [], top20={})
        out = presentation.inspect(SimpleNamespace(career=career, season=season), 'player', old['player_id'])
        self.assertEqual('estimated', out['data_provenance']['status'])
        self.assertEqual(name, out['name'])
        self.assertEqual(original, old)
        self.assertEqual(old['player_id'], out['player_id'])
        self.assertIsNone(presentation.inspect(SimpleNamespace(career=career, season=season), 'player', player_id('Patsi')))

    def test_coverage_does_not_claim_legacy_curated_is_verified(self):
        expected = {'2024': (47, 22), '2025': (41, 28), '2026': (0, 1)}
        for era, (verified, placeholders) in expected.items():
            with self.subTest(era=era):
                result = coverage(build_teams(era))
                self.assertEqual(verified, result['verified_rosters'])
                self.assertEqual(placeholders, result['placeholder_players'])
                self.assertEqual({'2024': 54, '2025': 59, '2026': 49}[era], result['teams'])
                if era == '2024':
                    self.assertEqual(1, result['provisional_teams'])
                    self.assertEqual(6, result['estimated_teams'])
                elif era == '2025':
                    self.assertEqual(1, result['provisional_teams'])
                    self.assertEqual(17, result['estimated_teams'])
                    self.assertEqual(0, result['unverified_teams'])
                else:
                    self.assertGreater(result['unverified_teams'], 0)

    def test_correction_does_not_leak_to_other_era_or_read_future_axes(self):
        self.assertTrue(correction_for('2025', 'PARIVISION'))
        rows, _, quality = roster_for('2025', 'PARIVISION', [('future', 100)], 43)
        self.assertEqual('mixed', quality)
        self.assertEqual({'Qikert', 'BELCHONOKK', 'ArtFr0st'}, {name for name, _ in rows if '2025 slot' not in name})
        self.assertEqual(2, sum('2025 slot' in name for name, _ in rows))
        from cs2career.world import ability
        original = ability.stats_for
        def guard(name, *args):
            if name in {'Jerry', 'X5G7V', 'Patsi', 'Qikert', 'ArtFr0st'}:
                self.fail('Dated correction must not read global 2026 statistics')
            return original(name, *args)
        with patch.object(ability, 'stats_for', side_effect=guard):
            build_teams('2024')

    def test_2024_team_extension_overrides_new_world_only(self):
        # Exercise the real registry, not a direct dict injection. Existing
        # built-in era IDs can be patched through era-scoped TEAM packs.
        before = build_teams('2024')
        snapshot = deepcopy(before)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pack = root / 'historical-test'
            (pack / 'teams').mkdir(parents=True)
            (pack / 'pack.json').write_text(json.dumps({'id': 'historical-test', 'schema_version': 1, 'types': ['teams']}), encoding='utf-8')
            people = [{'name': f'PackPlayer{i}', 'role': role, 'ability': 70} for i, role in enumerate(('igl','awp','rifle','lurk','entry'))]
            people[0]['name'] = 'DANK1NG'  # Deliberately overrides the global AWP role.
            (pack / 'teams' / '2024.json').write_text(json.dumps({'era': '2024', 'teams': [{'id': 'parivision', 'name': 'PARIVISION', 'players': people}]}), encoding='utf-8')
            registry = PackRegistry(root)
            self.assertEqual('ready', registry.packs[0].status)
            with patch('cs2career.content.get_registry', return_value=registry):
                updated = next(t for t in build_teams('2024') if t['id'] == 'parivision')
                untouched = next(t for t in build_teams('2025') if t['id'] == 'parivision')
            apply_roles([updated], '2024')
            self.assertEqual('igl', next(p for p in updated['players'] if p['name'] == 'DANK1NG')['role'])
            self.assertEqual({p['name'] for p in people}, {p['name'] for p in updated['players']})
            self.assertEqual('extension', quality_view(updated, team=True)['status'])
            self.assertFalse(any(p['name'].startswith('PackPlayer') for p in untouched['players']))
        self.assertEqual(snapshot, before)
