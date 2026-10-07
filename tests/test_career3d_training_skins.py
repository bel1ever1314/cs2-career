from application_double import ApplicationDouble
"""Real training uses the same local cosmetic handoff as other match modes."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from cs2career.cs2 import launch
from tools import career3d_activities, career3d_controls


class TrainingSkinHandoffTests(unittest.TestCase):
    def test_all_inventory_modes_use_local_preparation(self):
        team = dict(id='home', name='Home', players=[dict(name=f'home{i}') for i in range(5)])
        opponent = dict(id='away', name='Away', players=[dict(name=f'away{i}') for i in range(5)])
        for mode, enabled in (('career', True), ('career', False), ('external', True)):
            with self.subTest(mode=mode, enabled=enabled):
                career = SimpleNamespace(unsigned=False, last_scrim='', player_name='home0',
                    real_skins=enabled, over=lambda: False, my_team=lambda teams: team, remember_training=Mock(), training_session={})
                state = ApplicationDouble(career=career,
                    season=SimpleNamespace(date='2026-10-04', teams=[team, opponent]))
                cfg = dict(skins_inventory_mode=mode)
                captured = []

                def start(*args, **kwargs):
                    self.assertEqual(kwargs['purpose'], 'series')
                    self.assertIsNot(args[6], career)
                    self.assertEqual(args[6].real_skins, enabled)
                    self.assertTrue(kwargs['existing_plugins'])
                    captured.append(launch.prepare_existing_skins(Path('fixture-game/csgo'), career, kwargs['config']))
                    return dict(msg='training started')

                with patch.object(career3d_activities, '_running_cs2', return_value=False), \
                     patch.object(launch, 'require_cs2_closed'), \
                     patch.object(career3d_activities, 'config_status', return_value=dict(ready=True)), \
                     patch.object(career3d_activities, 'read_cs2_config', return_value=cfg), \
                     patch.object(launch, 'prepare_existing_skins', return_value=7) as prepare, \
                     patch.object(launch, 'start_match', side_effect=start):
                    result = career3d_controls._training_launch(state,
                        dict(opponent_id='away', map='de_dust2', side='ct'))
                self.assertEqual(result, dict(reason='training started', status='waiting'))
                self.assertEqual(captured, [7])
                career.remember_training.assert_called_once()
                prepare.assert_called_once_with(Path('fixture-game/csgo'), career, cfg)


if __name__ == '__main__':
    unittest.main()
