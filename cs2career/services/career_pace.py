"""Unified career policy and identity checks; playback speed is never saved."""


def enable(state):
    c, s = state.career, state.season
    if not c.exists or c.over():
        raise ValueError('请先创建一段仍在进行的生涯。')
    c.assist.update(unified_pace=1, quick_mode=True,
                    season_mode=dict(year=s.year, mode='quick'))
    c.assist.setdefault('season_run', dict(year=s.year, status='ready'))


def map_key(state, event, match):
    return f"{state.season.year}:{event['id']}:{match['id']}:{len(match.get('maps') or [])}"


def guard_map(state, event, match, body):
    if 'map_key' in body and body['map_key'] != map_key(state, event, match):
        raise ValueError('地图进度已变化，请刷新后选择；本次未执行。')


def next_match(state):
    pair = state.season.find_your_series()
    if not pair:
        return None
    event, match = pair
    return dict(match_id=match['id'], map_key=map_key(state, event, match))
