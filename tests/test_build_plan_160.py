"""Inspect build commands without invoking compilers or touching D:."""
from pathlib import Path
import unittest

import build_exe


class BuildPlan160Tests(unittest.TestCase):
    def test_default_release_goes_to_d_and_does_not_rebuild_game_plugins(self):
        output = build_exe.DEFAULT_OUTPUT
        self.assertEqual('D:/CS2CareerBuilds/v1.6.0', output.as_posix())
        commands = build_exe.build_plan(output, 'CS2Career-160', output / 'public')
        self.assertEqual(2, len(commands))
        self.assertIn('--output-root', commands[0])
        self.assertIn(str(output), commands[0])
        self.assertNotIn('powershell', commands[0])
        self.assertIn(str(output / 'release/CS2Career-160/CS2Career-160.exe'), commands[1])
        self.assertIn('1.6.0', commands[1])

    def test_plugin_rebuild_is_explicit_and_uses_external_artifacts_path(self):
        output = Path('D:/BuildSandbox')
        commands = build_exe.build_plan(output, 'CS2Career-160', output / 'public', True)
        self.assertEqual(3, len(commands))
        self.assertEqual('powershell', commands[0][0])
        self.assertIn('-OutputRoot', commands[0])
        self.assertIn(str(output / 'plugins'), commands[0])


if __name__ == '__main__':
    unittest.main()
