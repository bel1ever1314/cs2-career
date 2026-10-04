"""Opt-in real worker QA, limited to temporary game trees and dead owner PIDs.

CAREER_RUN_ENV_WORKER_SMOKE=1 enables source worker execution.
CAREER_ENV_FROZEN_BACKEND=<QA CareerBackend.exe> also enables frozen execution.
No game is launched and no real game configuration or Career save is changed.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cs2career.cs2 import environment, process_state
from tools.career3d_cs2_watchdog import spawn_watch


@unittest.skipUnless(os.environ.get('CAREER_RUN_ENV_WORKER_SMOKE') == '1',
                     'Real worker smoke is manual opt-in')
class IndependentWorkerSmokeTests(unittest.TestCase):
    def setUp(self):
        if process_state.cs2_running() is not False:
            self.skipTest('Actual CS2 must be confirmed closed before fixture worker QA')
        owner = subprocess.Popen([sys.executable, '-B', '-c', 'pass'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000 if os.name == 'nt' else 0)
        owner.wait(timeout=10)
        self.owner_pid = owner.pid
        if process_state.process_running(self.owner_pid) is not False:
            self.skipTest('Could not confirm the disposable owner has exited')
        temporary = tempfile.TemporaryDirectory(prefix='career-exit-worker-QA-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.csgo = self.root / 'game' / 'csgo'
        (self.csgo / 'cfg').mkdir(parents=True)
        self.gameinfo = self.csgo / 'gameinfo.gi'
        self.original = (b'GameInfo\n{\n\tFileSystem\n\t{\n\t\tSearchPaths\n\t\t{\n'
                         b'\t\t\tGame csgo\n\t\t\tGame core\n\t\t}\n\t}\n}\n')
        self.gameinfo.write_bytes(self.original)
        (self.csgo / 'cfg/career_rules.cfg').write_bytes(b'// temporary QA, never executed\n')
        (self.csgo / 'cfg/gamemode_competitive.cfg').write_bytes(b'// temporary Valve cfg\n')
        self.dummy_save = self.root / 'must-not-create-save'
        self.environment_patch = patch.dict(os.environ, {'CS2CAREER_SAVE_DIR': str(self.dummy_save)})
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)

    def smoke(self):
        active = environment.switch_environment(self.csgo, 'enhanced',
            watch_mode='manual', owner_pid=self.owner_pid)
        self.assertEqual('enhanced', active['mode'])
        child = spawn_watch(self.csgo, active['generation'], mode='manual', owner_pid=self.owner_pid)
        try:
            result = child.wait(timeout=20)
        except subprocess.TimeoutExpired:
            # This can happen if someone opens actual CS2 during QA. Only stop
            # our own worker, never a game or another process.
            child.terminate()
            child.wait(timeout=5)
            raise
        self.assertEqual(0, result)
        restored = environment.read_lease(self.csgo)
        self.assertEqual('normal', restored['mode'])
        self.assertFalse(restored['watch']['active'])
        self.assertEqual(self.original, self.gameinfo.read_bytes())
        self.assertNotIn(b'exec career_rules.cfg',
                         (self.csgo / 'cfg/gamemode_competitive.cfg').read_bytes())
        self.assertFalse(self.dummy_save.exists(), 'worker must not initialize any Career save')

    def test_source_worker_survives_closed_owner_and_restores_without_save_initialization(self):
        with patch.object(sys, 'frozen', False, create=True):
            self.smoke()

    def test_frozen_worker_survives_closed_owner_and_restores_without_save_initialization(self):
        executable = Path(os.environ.get('CAREER_ENV_FROZEN_BACKEND', ''))
        if executable.name.casefold() != 'careerbackend.exe' or not executable.is_file():
            self.skipTest('Set CAREER_ENV_FROZEN_BACKEND to an existing local QA backend')
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(executable)):
            self.smoke()


if __name__ == '__main__':
    unittest.main()
