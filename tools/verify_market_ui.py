"""Bounded native UI checks in an isolated project, optionally capture frames."""
from pathlib import Path
import os
import json
import hashlib
import shutil
import subprocess
import sys
import argparse

ROOT=Path(__file__).resolve().parents[1]
QA=Path('E:/CS2CareerTools/Verification/market-supplies-20261007')
ENGINE=Path('D:/CS2CareerBuilds/v1.7.2-refresh-20261007-final/release/CS2Career-1.7.2/engine/Godot.exe')


def main():
    global QA, ENGINE
    parser=argparse.ArgumentParser()
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--qa-dir', type=Path, default=QA)
    parser.add_argument('--engine', type=Path, default=ENGINE)
    parser.add_argument('--scene', default='market_supplies_ui_test')
    args=parser.parse_args()
    QA, ENGINE = args.qa_dir, args.engine
    scene=args.scene
    project=QA/'game'
    shutil.copytree(ROOT/'work/career3d_redesign',project,dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('.godot','runtime','temp','renders','*.log'))
    if not (project/'.godot').exists(): shutil.copytree(ENGINE.parent.parent/'game/.godot',project/'.godot')
    env=dict(os.environ,CS2CAREER_SAVE_DIR=str(QA/'isolated-save'),CS2CAREER_NO_GAME='1')
    render='--render' in sys.argv
    args=[str(ENGINE),'--path',str(project),'--rendering-method','gl_compatibility']
    if not render: args+=['--headless']
    args+=['res://tests/'+scene+'.tscn','--','--no-service']
    if render: args+=['--capture-market']
    url=json.loads((ROOT/'cs2career/data/skin_art.json').read_text('utf-8'))['items']['ak-redline']['url']
    args+=['--market-art='+str(ROOT/'cs2career/data/skin_images'/(hashlib.sha256(url.encode()).hexdigest()+'.png'))]
    info=subprocess.STARTUPINFO(); info.dwFlags|=subprocess.STARTF_USESHOWWINDOW; info.wShowWindow=0
    log=QA/('market-ui-render.log' if render else 'market-ui.log')
    with log.open('w',encoding='utf-8') as stream:
        try:
            result=subprocess.run(args,stdout=stream,stderr=subprocess.STDOUT,timeout=55,env=env,
                creationflags=subprocess.CREATE_NO_WINDOW,startupinfo=info)
        except subprocess.TimeoutExpired:
            print(log.read_text('utf-8')[-7000:]); raise
    text=log.read_text('utf-8'); print(text[-7000:])
    assert result.returncode==0 and 'SCRIPT ERROR' not in text and any(
        marker in text for marker in ('MARKET_UI_RESULT', 'PREDICTION_UI_RESULT', 'BETTING_INPUT_RESULT',
                                     'MAP_FORM_UI_RESULT', 'SCROLL_MEMORY_RESULT', 'ACTION_FEEDBACK_RESULT',
                                     'RECRUITMENT_UI_RESULT', 'BREAK_TRAINING_UI_RESULT',
                                     'UNIFIED_PACE_RESULT', 'WORLD_FEED_RESULT', 'DEVICE_FRAGMENTS_RESULT'))


if __name__=='__main__': main()
