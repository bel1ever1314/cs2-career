"""Authored English display fields on detached, read-only HTTP projections.

Never replace source text, IDs, names, dates, numbers or command values. This
adapter is presentation only and does not inspect or write career state.
"""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re

CATALOGUE = Path(__file__).resolve().parents[1] / 'work/career3d_redesign/data/locale_en.json'
DISPLAY_FIELDS = {'title', 'text', 'body', 'label', 'from', 'heading', 'summary',
                  'preview', 'greeting', 'reason', 'msg', 'message', 'description', 'hint', 'blocked', 'note'}


@lru_cache(maxsize=1)
def _catalogue():
    if not CATALOGUE.is_file(): return {}, []
    value = json.loads(CATALOGUE.read_text('utf-8'))
    return value.get('phrases', {}), [(re.compile(row['pattern']), row['replacement'], row['keys'])
                                   for row in value.get('templates', [])]


def english(value, protected=()):
    if not isinstance(value, str) or not value: return value
    if value in protected: return value
    from cs2career.career.localization import translate
    authored = translate(value)
    if authored != value: return authored
    phrases, templates = _catalogue()
    if value in phrases: return phrases[value]
    for pattern, replacement, keys in templates:
        match = pattern.fullmatch(value)
        if match:
            for index, key in enumerate(keys, 1):
                captured = match[index]
                translated = english(captured, protected) if captured != value else captured
                replacement = replacement.replace('{'+str(key)+'}', translated)
            return replacement
    if '\n' in value: return '\n'.join(english(line, protected) for line in value.split('\n'))
    return value


def localize_projection(value):
    """Return a detached response with _en siblings; the input remains untouched."""
    identities = set()
    def collect(item):
        if isinstance(item, dict):
            if isinstance(item.get('name'), str) and any(key in item for key in ('player_id', 'ability', 'roster', 'players')):
                identities.add(item['name'])
            for key in ('player', 'player_name', 'team_a', 'team_b', 'opponent', 'champion', 'winner'):
                if isinstance(item.get(key), str): identities.add(item[key])
            for child in item.values(): collect(child)
        elif isinstance(item, list):
            for child in item: collect(child)
    collect(value)
    return _localize_projection(value, identities)


def _localize_projection(value, identities):
    if isinstance(value, list): return [_localize_projection(item, identities) for item in value]
    if not isinstance(value, dict): return deepcopy(value)
    out = {key: _localize_projection(item, identities) for key, item in value.items()}
    for key in DISPLAY_FIELDS:
        if isinstance(value.get(key), str) and not value.get(key+'_en'):
            translated = english(value[key], identities)
            if translated != value[key]: out[key+'_en'] = translated
    return out
