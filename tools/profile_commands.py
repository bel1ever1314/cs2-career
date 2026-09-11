"""Read-only source save -> temporary copy; never advances the source career."""
import os
import sys
import json
import shutil
import tempfile
import cProfile
import pstats
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='career-profile-') as folder:
        root = Path(folder)
        os.environ.update(CS2CAREER_SAVE_DIR=str(root/'save'),
                          CS2CAREER_EXTENSION_DIR=str(root/'extensions'), CS2CAREER_NO_GAME='1')
        (root/'save').mkdir()
        if len(sys.argv) > 1:
            for name in ('career.json', 'season.json'):
                shutil.copy2(Path(sys.argv[1])/name, root/'save'/name)
        from cs2career.application import ApplicationState
        from cs2career.json_bytes import encode
        app = ApplicationState()
        if not app.career.exists:
            app.create_career(dict(mode='create', era='2026', name='Profile', org='Profile',
                                   origin='academy', role='rifle', region='EU'))
        print('Save bytes:', (root/'save'/'season.json').stat().st_size)
        from cs2career.world.ability import ALL_AXES
        def spend_request():
            player = app.career.my_player(app.season.teams)
            axis = next(a for a in ALL_AXES if float(player['stats'].get(a, 0)) < 99)
            before = app.career.attr_points
            app.career.spend_point(app.season, axis)
            assert app.career.attr_points == before-1, 'Point was not actually spent'
            app.persist()
            return encode(app.payload())
        print('Payload bytes:', len(encode(app.payload())))
        for label, command in [('payload', lambda: encode(app.payload())),
                               ('persist', app.persist),
                               ('point_request', spend_request),
                               ('next_stage_request', lambda: (app.season.next_stage(), app.persist(), encode(app.payload())))]:
            app.career.attr_points = max(app.career.attr_points, 10)
            profile = cProfile.Profile()
            start = perf_counter()
            profile.runcall(command)
            print(label, round((perf_counter()-start)*1000), 'ms (profiled)')
            pstats.Stats(profile).sort_stats('cumulative').print_stats(12)
