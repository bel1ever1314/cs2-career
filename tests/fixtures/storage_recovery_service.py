"""Copied into a marked temporary repo by verify_backend_restart.py only.

No fault injection endpoint or configuration is included in the real service.
This wrapper adds one disposable command and fails after the commit point.
"""
import json
from pathlib import Path
import sys

fixture = Path(__file__).resolve().parents[1]
if not (fixture / 'restart-test.marker').is_file():
    raise SystemExit('Requires a disposable restart fixture')
source = Path(json.loads((fixture / 'fixture-source.json').read_text())['root'])
sys.path.insert(0, str(source))

from tools import career3d_service as service

# The import-time save paths must be selected before importing game modules.
data_dir = Path(sys.argv[sys.argv.index('--data-dir') + 1])
if data_dir.resolve() != (fixture / 'career').resolve():
    raise SystemExit('Fixture data path mismatch')
service.isolate(data_dir)
from cs2career.storage import transaction as tx


def checkpoint(point):
    marker = fixture / 'fault-armed.marker'
    if point == 'replaced:career.json' and marker.exists():
        marker.replace(fixture / 'fault-consumed.marker')
        raise OSError('Test interruption after durable commit')


base_factory = service.handler_class


def fixture_handler():
    class FixtureHandler(base_factory()):
        def _post(self):
            if self.path == '/api/fixture/spend':
                self.state.career.money += 37
                self.state.persist()
                self._json({'ok': True, 'status': 'saved', 'amount': 37})
                return
            super()._post()
    return FixtureHandler


tx._checkpoint = checkpoint
service.handler_class = fixture_handler
raise SystemExit(service.main())
