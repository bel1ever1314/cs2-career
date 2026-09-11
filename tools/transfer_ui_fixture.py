"""Ephemeral real-business UI rehearsal. Never reads or writes player saves."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='career-transfer-ui-') as folder:
        os.environ['CS2CAREER_SAVE_DIR'] = str(Path(folder)/'save')
        os.environ['CS2CAREER_EXTENSION_DIR'] = str(Path(folder)/'extensions')
        os.environ['CS2CAREER_NO_GAME'] = '1'
        from cs2career.application import ApplicationState
        from cs2career.web.server import create_server
        app=ApplicationState()
        app.create_career(dict(mode='create',era='2026',name='TransferUITest',org='Transfer UI Club',origin='academy',role='rifle',region='EU'))
        while app.career.story_queue:
            row=app.career.story_queue[0]
            app.career.ack_story(row['id'],(row.get('choices') or [{'id':''}])[0]['id'],app.season)
        if '--transferred' in sys.argv:
            from unittest.mock import patch
            from cs2career.career import player_transfers as pt
            target=next(r for r in pt.public(app.career,app.season)['targets'] if not r['blocked'])
            with patch.object(pt,'draw',return_value=20):
                pt.apply(app.career,app.season,target['team_id'],target['role'])
            row=next(r for r in app.career.story_queue if r.get('when')=='transfer_decision')
            app.career.ack_story(row['id'],'accept',app.season)
        app.persist()
        server=create_server(app)
        print(f'http://127.0.0.1:{server.server_port}/?token={server.token}',flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()
