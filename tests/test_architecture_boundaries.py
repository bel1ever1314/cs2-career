"""Production services never import executable tools or HTTP/bootstrap state."""
import ast
import importlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ArchitectureBoundariesTests(unittest.TestCase):
    def test_core_has_no_reverse_tool_imports(self):
        violations = []
        for path in (ROOT / 'cs2career').rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text('utf-8-sig'))):
                modules = ([node.module or ''] if isinstance(node, ast.ImportFrom) else
                           [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
                for module in modules:
                    if module == 'tools' or module.startswith('tools.'):
                        violations.append(f'{path.relative_to(ROOT)}:{node.lineno}: {module}')
        self.assertEqual([], violations)

    def test_compatibility_imports_share_the_implementation(self):
        modules = {
            'activities': 'services.activities', 'start': 'services.start',
            'attribute_draw': 'services.attribute_draw', 'resources': 'services.resources',
            'skin_bundles': 'services.skin_bundles', 'install': 'services.installation',
            'runtime_compat': 'cs2.runtime_compat', 'cs2_environment': 'services.game_environment',
            'cs2_lifecycle': 'services.match_recovery', 'cs2_watchdog': 'cs2.watchdog',
        }
        for old, new in modules.items():
            with self.subTest(module=old):
                self.assertIs(importlib.import_module('tools.career3d_' + old),
                              importlib.import_module('cs2career.' + new))

    def test_match_queries_do_not_open_veto_or_modify_matches(self):
        from copy import deepcopy
        from types import SimpleNamespace
        from cs2career.services.match_queries import player_matches, due_player_match
        events = [dict(status='live', matches=[
            dict(id='later', date='2026-10-09'), dict(id='now', date='2026-10-05'),
            dict(id='old', date='2026-10-01', played=True)])]
        original = deepcopy(events)
        state = SimpleNamespace(season=SimpleNamespace(events=events, date='2026-10-05', is_yours=lambda m: True))
        self.assertEqual(['now', 'later'], [m['id'] for _, m in player_matches(state)])
        self.assertEqual('now', due_player_match(state)[1]['id'])
        self.assertEqual(original, events)
