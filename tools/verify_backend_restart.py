"""Exercise Godot's real owned-service restart with disposable data only."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='career-restart-') as temp:
        fixture = Path(temp)
        (fixture / 'restart-test.marker').touch()
        (fixture / 'fixture-source.json').write_text(json.dumps({'root': str(root)}), encoding='utf-8')
        (fixture / 'tools').mkdir()
        shutil.copy2(root / 'tests/fixtures/storage_recovery_service.py', fixture / 'tools/career3d_service.py')
        result = subprocess.run([str(args.godot), '--headless', '--path',
            str(root / 'work/career3d_redesign'), '--quit-after', '24000',
            'res://tests/backend_restart_test.tscn', '--', '--no-service',
            f'--fixture-root={fixture}', f'--python={sys.executable}', f'--repo={root}'],
            text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=120)
        print(result.stdout)
        if result.returncode or 'RESTART_RESULT checks=15 failures=[]' not in result.stdout:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
