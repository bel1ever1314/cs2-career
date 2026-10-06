from application_double import ApplicationDouble
"""Read-only five-position device projections; fixtures never load a save."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs2career.world.ability import (AXES, ALL_AXES, calibrate_role, playing_ability,
                                    playing_stats, position_views)
from cs2career.world.calibrated import model_marker
from tools.career3d_activities import personal_context
from tools.career3d_business import player_detail_projection
from tools.career3d_service import _player


ROLES = ('rifle', 'entry', 'awp', 'lurk', 'igl')


def player(calibrated=True):
    stats = dict(firepower=81.25, entrying=59.5, trading=77.25, opening=65.75,
                 clutching=93.5, sniping=22.25, utility=63.5, command=64)
    if calibrated:
        stats['position_model'] = model_marker('rifle', 'isolated-projection-fixture')
    calibrate_role(stats, 'rifle', 78.2)
    return dict(player_id='p_projection', name='Projection fixture', role='awp',
                age=24, ability=78.2, stats=stats, command=64, form_delta=2)


def state_for(person):
    team = dict(id='fixture_team', name='Fixture team', money=12000, players=[person])
    career = SimpleNamespace(free=[], my_player=lambda teams: person,
        my_team=lambda teams: team, you_card=None, player_name=person['name'],
        training_session=None, over=lambda: False, assist={}, attr_points=5,
        money=800, retired=False, banned=False, unsigned=False, origin='academy', role='awp')
    return ApplicationDouble(season=SimpleNamespace(teams=[team], events=[]),
                           career=career, arena=SimpleNamespace(pending=None))


def detail_for(person):
    return dict(player_id=person['player_id'], name=person['name'], role=person['role'],
                historical=False, stats=deepcopy(person['stats']), ability=person['ability'],
                summary={'rating': 1.11, 'adr': 81.2, 'kast': .71, 'maps': 5},
                records=[{'map': 'de_dust2', 'rating': 1.21}], range='30d', page=2, total=25)


class CalibratedProjectionTests(unittest.TestCase):
    def test_live_detail_uses_original_reference_axes_and_is_read_only(self):
        person = player()
        state, detail = state_for(person), detail_for(person)
        before_player, before_detail = deepcopy(person), deepcopy(detail)
        shown = player_detail_projection(state, detail)
        self.assertEqual(playing_stats(person), shown['stats'])
        self.assertEqual(playing_ability(person), shown['ability'])
        self.assertEqual(position_views(person), shown['position_views'])
        self.assertEqual(before_player, person)
        self.assertEqual(before_detail, detail)
        for key in ('summary', 'records', 'range', 'page', 'total'):
            self.assertEqual(detail[key], shown[key])
        shown['stats']['position_model']['reference_role'] = 'entry'
        shown['position_views'][0]['stats']['firepower'] = 0
        shown['summary']['rating'] = 9
        self.assertEqual(before_player, person)
        self.assertEqual(before_detail, detail)

    def test_five_previews_share_task_boundary_and_do_not_change_command(self):
        person = player()
        before = deepcopy(person)
        views = position_views(person)
        self.assertEqual(list(ROLES), [view['role'] for view in views])
        for view in views:
            self.assertEqual(playing_ability(dict(person, role=view['role'])), view['ability'])
            self.assertEqual({axis: playing_stats(person, view['role']).get(axis) for axis in ALL_AXES}, view['stats'])
            self.assertEqual(64, view['stats']['command'])
        self.assertNotEqual(views[1]['stats']['sniping'], views[2]['stats']['sniping'])
        self.assertEqual(before, person)

    def test_legacy_previews_keep_saved_seven_axes(self):
        person = player(calibrated=False)
        before = deepcopy(person)
        for role in ROLES:
            self.assertEqual(person['stats'], playing_stats(person, role))
        shown = player_detail_projection(state_for(person), detail_for(person))
        for view in shown['position_views']:
            self.assertEqual({axis: person['stats'][axis] for axis in AXES},
                             {axis: view['stats'][axis] for axis in AXES})
        self.assertEqual(before, person)

    def test_historical_rows_never_gain_live_attributes(self):
        person = player()
        detail = dict(detail_for(person), historical=True, stats={}, ability=None)
        before = deepcopy(detail)
        with patch('cs2career.world.ability.playing_stats') as expression:
            self.assertEqual(before, player_detail_projection(state_for(person), detail))
        expression.assert_not_called()
        self.assertNotIn('position_views', detail)
        self.assertIsNone(player_detail_projection(state_for(person), None))

    def test_unknown_stable_id_does_not_fall_back_to_same_name(self):
        person = player()
        detail = dict(detail_for(person), player_id='missing-id')
        self.assertEqual(detail, player_detail_projection(state_for(person), detail))
        self.assertNotIn('position_views', detail)

    def test_ambiguous_live_candidates_are_not_guessed(self):
        person = player()
        state = state_for(person)
        state.career.free = [deepcopy(person)]
        detail = detail_for(person)
        self.assertEqual(detail, player_detail_projection(state, detail))

    def test_already_projected_detail_is_not_expressed_twice(self):
        person = player()
        detail = detail_for(person)
        detail.update(stats=playing_stats(person), ability=playing_ability(person),
                      position_views=position_views(person))
        with patch('cs2career.world.ability.playing_stats') as expression:
            shown = player_detail_projection(state_for(person), detail)
        expression.assert_not_called()
        self.assertEqual(detail, shown)
        self.assertIsNot(detail['stats'], shown['stats'])

    def test_personal_projection_separates_base_growth_and_position_expression(self):
        person = player()
        state = state_for(person)
        before = deepcopy(person)
        summary = {'rating': 1.11, 'adr': 81.2, 'kast': .71, 'maps': 5, 'rounds': 101}
        with patch('cs2career.presentation.inspect', return_value={'summary': summary}):
            shown = personal_context(state)
        self.assertEqual({axis: person['stats'].get(axis) for axis in ALL_AXES}, shown['attributes'])
        self.assertEqual({axis: playing_stats(person).get(axis) for axis in ALL_AXES}, shown['playing_attributes'])
        self.assertEqual(position_views(person), shown['position_views'])
        self.assertEqual(playing_ability(person), shown['ability'])
        for key, value in summary.items():
            self.assertEqual(value, shown['stats'][key])
        self.assertNotIn('rating', shown['position_views'][0]['stats'])
        self.assertNotIn('adr', shown['position_views'][0]['stats'])
        self.assertEqual(before, person)

    def test_small_context_player_ability_matches_simulation(self):
        person = player()
        before = deepcopy(person)
        self.assertEqual(round(playing_ability(person), 1), _player(person)['ability'])
        self.assertEqual(person['role'], _player(person)['role'])
        self.assertEqual(0, _player({})['ability'])
        self.assertEqual(before, person)


if __name__ == '__main__':
    unittest.main()
