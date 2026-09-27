"""Pure local ladder rules. No live service, game state mutation or name guessing.

Score sources and tunable game defaults live in data/arena_ladder.json.
Scores are initialized once on first queue, then persisted by stable player ID.
"""
from functools import lru_cache
from hashlib import sha256
import json

from .paths import data_file
from .world.ability import playing_ability
from .world.eras import player_id


@lru_cache(maxsize=1)
def rules():
    data = json.loads(data_file('arena_ladder.json').read_text('utf-8'))
    if data.get('schema_version') != 1:
        raise ValueError('Invalid local ladder rules')
    return data


def level(elo):
    return 1 + sum(elo > ceiling for ceiling in (500, 750, 900, 1050, 1200, 1350, 1530, 1750, 2000))


def initial_score(player, origin=None):
    config = rules()
    if origin in config['origins']:
        return config['origins'][origin], dict(kind='origin', origin=origin, revision=config['revision'])
    for row in config['players']:
        # Canonical database IDs only: a similarly named custom/academy player
        # must not inherit a real professional's historical score.
        if player['player_id'] == player_id(row['name']):
            return row['elo'], dict(kind='snapshot', source=row['source'], revision=config['revision'])
    ability = playing_ability(player)
    curve = config['ability_curve']
    score = curve[0][1]
    for (a, low), (b, high) in zip(curve, curve[1:]):
        if ability >= a:
            score = low + (high-low)*max(0, min(1, (ability-a)/(b-a)))
    return round(score), dict(kind='game_curve', ability=round(ability, 2), revision=config['revision'])


def map_preference(player_id, map_name):
    """Stable simulated map taste, NOT scraped real-world veto behaviour."""
    return int(sha256(f'arena-map-v1:{player_id}:{map_name}'.encode()).hexdigest()[:8], 16) % 101
