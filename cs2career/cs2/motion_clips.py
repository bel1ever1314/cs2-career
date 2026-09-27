"""Validated, data-only, original-location motion samples for the live pilot.

This file is deliberately separate from the coarse tactical node contract.
Adding actions does not change rosters, combat difficulty or career saves.
"""
from __future__ import annotations

import json
import math
import sys
from functools import lru_cache
from pathlib import Path

from ..paths import data_file

FRAME_COLUMNS = ['t','x','y','z','yaw','pitch','vx','vy','vz','ground','walk','duck','jump']


def validate(pack):
    clips = pack.get('clips')
    if (pack.get('schema_version') != 1 or pack.get('map') != 'de_dust2'
            or pack.get('execution') != 'trajectory_guidance_live_physics'
            or pack.get('frame_columns') != FRAME_COLUMNS
            or not isinstance(clips, list) or not 1 <= len(clips) <= 512):
        raise ValueError('连续动作包版本、地图、字段或数量错误')
    ids = set()
    for clip in clips:
        cid = clip.get('id')
        frames = clip.get('frames')
        if (not isinstance(cid, str) or not 1 <= len(cid) <= 80 or cid in ids
                or clip.get('side') not in {'ct','t'}
                or clip.get('kind') not in {'mid_cross','mid_clear','b_clear'}
                or clip.get('phase') not in {'opening','middle'}
                or clip.get('direction') not in {'west','north','south'}
                or not isinstance(clip.get('weapon_id'), int) or not 1 <= clip['weapon_id'] <= 64
                or not isinstance(clip.get('scoped'), bool)
                or not isinstance(frames, list) or not 32 <= len(frames) <= 385):
            raise ValueError(f'连续动作元数据错误：{cid}')
        ids.add(cid)
        previous = -1
        previous_frame = None
        for frame in frames:
            if (not isinstance(frame, list) or len(frame) != 13
                    or any(not isinstance(v, (int,float)) or not math.isfinite(v) for v in frame)
                    or not 0 <= frame[0] <= 6
                    or previous >= 0 and not 0 < frame[0]-previous <= .04
                    or any(abs(v) > 10000 for v in frame[1:4])
                    or abs(frame[4]) > 360 or abs(frame[5]) > 45
                    or math.hypot(*frame[6:8]) > 315 or abs(frame[8]) > 350
                    or frame[9] not in {0,1} or frame[10] not in {0,1}
                    or not 0 <= frame[11] <= 1 or frame[12] not in {0,1}):
                raise ValueError(f'连续动作帧错误：{cid}')
            previous = frame[0]
            if previous_frame is not None:
                dt = frame[0]-previous_frame[0]
                if (math.dist(frame[1:3], previous_frame[1:3]) > 315*dt+.05
                        or abs(frame[3]-previous_frame[3]) > 350*dt+.05):
                    raise ValueError(f'连续动作位置跳变：{cid}')
            previous_frame = frame
        jumps = [f[0] for f in frames if f[12]]
        if (frames[0][0] != 0 or frames[0][9] != 1 or frames[-1][9] != 1 or len(jumps) > 1
                or clip['kind'] == 'mid_cross' and (clip['side'] != 'ct' or clip['direction'] != 'west'
                    or len(jumps) != 1 or not .15 <= jumps[0] <= frames[-1][0]-.15)
                or clip['kind'] != 'mid_cross' and any(not f[9] or f[12] for f in frames)):
            raise ValueError(f'连续动作起落状态错误：{cid}')
    return pack


@lru_cache(maxsize=1)
def motion_clip_pack():
    root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2]
    adjacent = root/'natural_routes'/'de_dust2_clips.json'
    path = adjacent if adjacent.is_file() else data_file('natural_behavior/de_dust2_clips.json')
    raw = path.read_bytes()
    if len(raw) > 8*1024*1024:
        raise ValueError('连续动作包超过8 MB')
    return path.resolve(), validate(json.loads(raw)), raw
