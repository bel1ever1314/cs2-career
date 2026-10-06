"""Disposable process-stop fixture. No actual game, Steam or plugin access."""
from contextlib import ExitStack
import os
from pathlib import Path
import sys
from unittest.mock import patch

root, mode, point, match_id = sys.argv[1:]
os.environ['CS2CAREER_SAVE_DIR'] = root
os.environ['CS2CAREER_EXTENSION_DIR'] = str(Path(root)/'test-extensions')
os.environ['CS2CAREER_NO_GAME'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cs2career.application import ApplicationState
from cs2career.cs2 import launch
from cs2career.services import matches, match_launch, match_simulation, season_run, activity_launch

state = ApplicationState()
def stop(current):
    if current == point:
        os._exit(73)  # Bypass every finally/context-manager cleanup.

def dispatch(cfg, arguments, kwargs):
    kwargs['before_dispatch']()
    return dict(match=kwargs['request_override'], msg='fixture only')

with ExitStack() as stack:
    stack.enter_context(patch.object(state.career, 'gate_match', return_value=''))
    stack.enter_context(patch.object(state, '_reconcile', state.persist))
    stack.enter_context(patch('cs2career.league.phases.emit'))
    stack.enter_context(patch('tools.career3d_activities._running_cs2', return_value=False))
    stack.enter_context(patch('tools.career3d_activities.read_cs2_config', return_value=dict(launch.DEFAULTS, csgo_path='')))
    stack.enter_context(patch('tools.career3d_activities.config_status', return_value=dict(ready=True, reason='')))
    stack.enter_context(patch.object(launch, 'require_cs2_closed'))
    stack.enter_context(patch.object(matches, '_peek', return_value={'status': 'none'}))
    stack.enter_context(patch.object(matches, '_dispatch_launch', side_effect=dispatch))
    workflow = activity_launch if mode.startswith('activity:') else {'launch': match_launch, 'simulate': match_simulation, 'quick': season_run}[mode]
    stack.enter_context(patch.object(workflow, '_checkpoint', side_effect=stop))
    if workflow is activity_launch:
        kind = mode.split(':')[1]
        if kind == 'training':
            opponent = next(t for t in state.season.teams if t['id'] != state.career.team_id)
            body = dict(opponent_id=opponent['id'], map='de_dust2', side='ct', revision=matches._revision(state))
            path = '/api/3d/controls/training/launch'
        else:
            body = dict(lobby_id=state.arena.data['lobby']['id'], revision=state.arena.data['revision'])
            path = '/api/3d/' + ('ladder' if kind == 'rank' else 'custom') + '/launch'
        workflow.command(state, path, dict(body, request_id='process-stop-0001'))
    else:
        workflow.command(state, dict(match_id=match_id, revision=matches._revision(state), request_id='process-stop-0001'))
raise AssertionError('The requested stop point was never reached')
