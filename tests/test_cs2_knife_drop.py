"""Keep knife dropping in local match rules, without altering normal CS2 cfgs."""
from pathlib import Path
import tempfile
import unittest

from cs2career.cs2 import launch


class LocalKnifeDropTests(unittest.TestCase):
    def test_player_and_observer_rules_allow_dropping_at_every_difficulty(self):
        for observer in (False, True):
            for level in launch.DIFFICULTIES:
                with self.subTest(observer=observer, difficulty=level), tempfile.TemporaryDirectory() as folder:
                    game = Path(folder) / 'game' / 'csgo'
                    cfg = game / 'cfg'
                    cfg.mkdir(parents=True)
                    normal = cfg / 'gamemode_competitive.cfg'
                    normal.write_bytes(b'// normal CS2 configuration\r\n')
                    match = {'observer': observer, 'quota': 10 if observer else 9,
                             'map': 'de_mirage',
                             'ct': {'name': 'A', 'logo': '', 'players': []},
                             't': {'name': 'B', 'logo': '', 'players': []}}
                    launch.write_career_cfg(game, match, dict(launch.DEFAULTS, difficulty=level))
                    for name in ('career_rules.cfg', 'career_quick.cfg'):
                        body = (cfg / name).read_text('utf-8')
                        self.assertEqual(1, body.splitlines().count('mp_drop_knife_enable 1'))
                        self.assertNotIn('sv_cheats', body)
                        self.assertNotIn('mp_restartgame', body)
                        self.assertNotIn('bot_kick', body)
                    self.assertEqual(normal.read_bytes(), b'// normal CS2 configuration\r\n')


if __name__ == '__main__':
    unittest.main()
