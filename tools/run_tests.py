"""Test entry point: isolate ALL import-time save/cache/extension paths first."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='c2c-tests-') as folder:
        os.environ['CS2CAREER_SAVE_DIR'] = str(Path(folder) / 'save')
        os.environ['CS2CAREER_EXTENSION_DIR'] = str(Path(folder) / 'extensions')
        os.environ['CS2CAREER_NO_GAME'] = '1'
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
