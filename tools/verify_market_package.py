"""Exercise frozen market/supplies endpoints against disposable saves only."""
import argparse
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.request import Request, urlopen
from uuid import uuid4


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--copy-progress',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    data=args.output/'data'
    if args.copy_progress:
        shutil.copytree(args.copy_progress,data,ignore=shutil.ignore_patterns('.service.lock','ready.json','*.log'))
    ready_path=args.output/'ready.json'
    checks=[]
    process=None
    ready={}
    log=(args.output/'backend.log').open('w',encoding='utf-8')
    env=dict(os.environ,CS2CAREER_NO_GAME='1',CS2CAREER3D_MEDIA_CONFIG=str(args.package/'game/data/media.json'))

    def api(path,body=None):
        req=Request(ready['base_url']+path,data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type':'application/json','X-Career-Token':ready['token']})
        with urlopen(req,timeout=45) as response: return json.load(response)

    def start():
        nonlocal process,ready
        if ready_path.exists(): ready_path.unlink()
        process=subprocess.Popen([str(args.package/'backend/CareerBackend.exe'),'--data-dir',str(data),
            '--port','127.0.0.1:0','--ready-file',str(ready_path),'--no-cs2-config'],
            stdout=log,stderr=log,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
        until=time.monotonic()+55
        while time.monotonic()<until:
            if ready_path.exists():
                ready=json.loads(ready_path.read_text('utf-8')); return
            if process.poll() is not None: raise AssertionError('Frozen backend exited; see backend.log')
            time.sleep(.1)
        raise AssertionError('Backend readiness timed out')

    def close():
        if process and process.poll() is None:
            api('/api/3d/shutdown',{})
            process.wait(timeout=20)
            assert process.returncode==0

    def context(): return api('/api/3d/context')
    def write(path,body):
        return api(path,dict(body,revision=context()['calendar']['revision'],request_id=uuid4().hex))
    def settle():
        for _ in range(20):
            rows=context()['stories']
            if not rows: return
            row=rows[0]
            write('/api/3d/story',dict(id=row['id'],choice=row['choices'][0]['id'] if row['choices'] else ''))
        raise AssertionError('Story fixture did not settle')

    try:
        start()
        if args.copy_progress:
            original=json.loads((args.copy_progress/'save/career.json').read_text('utf-8'))
            ctx=context()
            assert not ctx['start']['creation_required']
            for view in ('market','custody','merchant'):
                assert api('/api/3d/market?view='+view)['ok']
            assert api('/api/3d/supplies')['ok']
            saved=json.loads((data/'save/career.json').read_text('utf-8'))
            for key in ('player_name','team_id','money','inventory','equipped_ct','equipped_t','attr_points'):
                assert saved.get(key)==original.get(key),key
            maps = ctx['team']['map_performance']
            assert maps and all(row.get('automatic_training') for row in maps)
            assert all(row['practice_ceiling'] >= row['strength'] for row in maps)
            checks.append('Existing career exposes routine map maintenance and saved recovery limits')
            close(); start()
            assert not context()['start']['creation_required']
            checks.append('Existing long career loads and restarts; money, character, attributes and inventory preserved')
        else:
            assert context()['start']['creation_required']
            team=api('/api/3d/start/options?era=2026')['teams'][0]
            write('/api/3d/start/create',dict(confirm_replace=True,career=dict(mode='join',era='2026',team_id=team['id'],
                player_id=team['players'][0]['player_id'],role='rifle',unified_pace=True)))
            settle()
            checks.append('Fresh frozen package creates a career')
            page=api('/api/3d/market?wear=ft&max_price=1000&sort=price')['market']
            item=page['rows'][0]
            assert Path(item['art_path']).is_file()
            art_root=Path(item['art_path']).parent
            assert len(list(art_root.glob('*.png')))>=150
            body=dict(id=item['id'],wear='ft',quantity=3,expected_total=item['spot']*3,
                revision=context()['calendar']['revision'],request_id=uuid4().hex)
            api('/api/3d/skins/market-buy',body)
            assert api('/api/3d/skins/market-buy',body)['replayed']
            lot=api('/api/3d/market?view=custody')['market']['rows'][0]
            write('/api/3d/skins/market-withdraw',dict(lot_id=lot['lot_id'],quantity=1))
            write('/api/3d/skins/market-sell',dict(lot_id=lot['lot_id'],quantity=1,expected_total=lot['sell']))
            assert api('/api/3d/market?view=custody')['market']['rows'][0]['quantity']==1
            write('/api/3d/skins/market-rumor',{})
            write('/api/3d/skins/market-skill',dict(skill='bargaining'))
            assert api('/api/3d/market')['market']['fee']==.09
            checks.append('150 offline images; batch buy, replay, partial withdrawal, sale, rumors and skills work in frozen backend')
            training=api('/api/3d/controls/training')['data']
            write('/api/3d/scrim/schedule',dict(opponent_id=training['opponents'][0]['id'],date=context()['date'],map='dust2'))
            booking=context()['scrims']['scheduled'][0]
            write('/api/3d/skins/supply-buy',dict(axis='firepower',grade='normal',payer='personal'))
            supply=api('/api/3d/supplies')['supplies']
            player=next(p for p in supply['players'] if p['you'])
            write('/api/3d/skins/supply-prepare',dict(player_id=player['id'],item_id=supply['stock'][0]['id'],target='scrim:'+booking['id']))
            write('/api/3d/scrim/simulate',dict(id=booking['id']))
            after=api('/api/3d/supplies')['supplies']
            assert not after['stock'] and not after['active'] and after['cooldowns']
            checks.append('Prepared supply is consumed once by simulated practice and enters cooldown')
            for _ in range(2):
                tomorrow=(date.fromisoformat(context()['date'])+timedelta(days=1)).isoformat()
                for _ in range(12):
                    settle()
                    if context()['date']==tomorrow: break
                    write('/api/3d/calendar',dict(target_date=tomorrow))
                assert context()['date']==tomorrow
            detail=api('/api/3d/market?view=detail&id='+item['id']+'&wear=ft')['market']['item']
            assert len(detail['history'])>=2 and detail['change_1'] is not None
            saved_date=context()['date']
            close(); start()
            assert context()['date']==saved_date
            assert api('/api/3d/market?view=custody')['market']['rows'][0]['quantity']==1
            assert api('/api/3d/market')['market']['fee']==.09
            checks.append('Calendar builds real history; custody, skills and date survive restart')
        close()
        report=dict(ok=True,checks=checks,live_cs2_started=False)
        (args.output/'QA_RESULT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
    finally:
        if process and process.poll() is None:
            process.terminate(); process.wait(timeout=10)
        log.close()


if __name__=='__main__': main()
