"""Fresh-save smoke checks for a staged or extracted Windows preview. No CS2 writes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
from urllib.error import HTTPError


def verify_backend(executable, qa, media=None, bundled=None):
    qa = Path(qa).resolve()
    qa.mkdir(parents=True, exist_ok=False)
    ready = qa / 'ready.json'
    args = [str(executable), '--data-dir', str(qa / 'career'), '--ready-file', str(ready),
            '--no-cs2-config', '--port', '127.0.0.1:0']
    if media:
        args += ['--media-config', str(Path(media).resolve())]
    env = os.environ.copy()
    env.pop('CS2CAREER_BUNDLED_MOD', None)
    env.pop('CS2CAREER_SAVE_DIR', None)
    env.pop('CS2CAREER_EXTENSION_DIR', None)
    with (qa / 'backend.log').open('w', encoding='utf-8') as log:
        proc = subprocess.Popen(args, cwd=qa, env=env, stdout=log, stderr=subprocess.STDOUT)
        report = {'frozen_backend': str(executable), 'live_cs2_test': False}
        try:
            deadline = time.monotonic() + 75
            while not ready.exists():
                if proc.poll() is not None:
                    raise RuntimeError('Backend exited before ready; see ' + str(qa / 'backend.log'))
                if time.monotonic() > deadline:
                    raise TimeoutError('Backend ready timed out')
                time.sleep(.1)
            connection = json.loads(ready.read_text('utf-8'))
            if connection['host'] != '127.0.0.1':
                raise ValueError('Not loopback-only')

            def request(path, body=None, expected=200):
                payload = json.dumps(body).encode() if body is not None else None
                req = urllib.request.Request(connection['base_url'] + path, data=payload,
                    headers={'X-Career-Token': connection['token'], 'Content-Type': 'application/json'})
                try:
                    response = urllib.request.urlopen(req, timeout=60)
                except HTTPError as error:
                    response = error
                with response:
                    if response.status != expected:
                        raise ValueError('Unexpected endpoint status ' + path + ': ' + str(response.status))
                    return json.load(response)

            context = request('/api/3d/context')
            for key in ('player', 'team', 'settings', 'media', 'start', 'calendar'):
                if key not in context:
                    raise ValueError('Missing context field ' + key)
            if not context['isolated']:
                raise ValueError('Save not isolated')
            if not context['start'].get('creation_required') or context['start'].get('can_continue'):
                raise ValueError('A fresh player must complete character creation')
            blocked = request('/api/3d/calendar', {'revision':context['calendar']['revision'],
                'date':'2026-10-03'}, expected=400)
            if blocked.get('ok') or '创建角色' not in blocked.get('msg', ''):
                raise ValueError('Uncreated character bypassed the backend gate')
            endpoints = {}
            for path in ('/api/3d/start/options', '/api/3d/settings', '/api/3d/saves',
                         '/api/3d/skin-tools', '/api/3d/custom/catalog', '/api/3d/tactics'):
                result = request(path)
                if not result.get('ok'):
                    raise ValueError('Endpoint failed ' + path)
                endpoints[path] = True
            actual = context['settings']['setup']['available']
            if bundled is not None and actual != bundled:
                raise ValueError('Bundled install availability mismatch')
            report.update(ready=True, endpoints=endpoints, bundle_available=actual,
                          character_creation_required=True, premature_calendar_blocked=True,
                          map_images=len(context['media']['map_backgrounds']),
                          team_images=len(context['media']['team_backgrounds']),
                          skin_tools_default_enabled=context['settings']['skin_tools_enabled'],
                          real_skins_default_enabled=context['settings']['real_skins'],
                          skin_inspect_default_enabled=context['settings']['skin_inspect_enabled'])
            if any(context['settings'][key] for key in
                   ('real_skins', 'skin_tools_enabled', 'skin_inspect_enabled')):
                raise ValueError('Skins and optional skin tools must be disabled by default')
            request('/api/3d/shutdown', {})
            proc.wait(timeout=20)
            if proc.returncode:
                raise ValueError('Backend shutdown failed')
            if ready.exists():
                raise ValueError('Backend did not remove its own ready handshake')
            report['clean_shutdown'] = True
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=15)
        (qa / 'QA_RESULT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', type=Path, required=True)
    parser.add_argument('--qa', type=Path, required=True)
    parser.add_argument('--media', type=Path)
    parser.add_argument('--bundled', choices=('yes', 'no'))
    args = parser.parse_args()
    print(json.dumps(verify_backend(args.backend, args.qa, args.media,
        {'yes': True, 'no': False}.get(args.bundled)), ensure_ascii=False, indent=2))
