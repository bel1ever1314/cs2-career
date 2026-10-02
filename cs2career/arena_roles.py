"""Assign local match positions on copies, never on career club rosters.

There are only 5! = 120 combinations. Maximise the sum of the existing
position-specific ability, not Elo or captain order. Equal totals prefer
players' club positions, then stable IDs so refresh/reload cannot reroll jobs.
The captain remains the drafter; they do not automatically become the IGL.
"""
from copy import deepcopy
from itertools import permutations
import math

from .world.ability import ensure_role_calibration, playing_ability, refresh_player_ability
from .world.roles import PLAYABLE_ROLES

ASSIGNMENT_VERSION = 1


def validate_tactical_abilities(value):
    """Internal match metadata, with exactly the five playable duties."""
    if not isinstance(value, dict) or set(value) != set(PLAYABLE_ROLES):
        raise ValueError('战术能力必须包含五种可用职责')
    clean = {}
    for role in PLAYABLE_ROLES:
        score = value[role]
        if type(score) not in (int, float):
            raise ValueError('战术能力必须是 0–100 的有限数值')
        try:
            number = float(score)
        except OverflowError as exc:
            raise ValueError('战术能力必须是 0–100 的有限数值') from exc
        if not math.isfinite(number) or not 0 <= number <= 100:
            raise ValueError('战术能力必须是 0–100 的有限数值')
        clean[role] = number
    return clean


def tactical_abilities(player):
    """Evaluate temporary role fits without changing any career/lobby row."""
    calibrated = deepcopy(player)
    calibrated.setdefault('ability', calibrated.get('overall', 70))
    ensure_role_calibration(calibrated)
    scores = {}
    for role in PLAYABLE_ROLES:
        candidate = deepcopy(calibrated)
        candidate['role'] = role
        score = playing_ability(candidate)
        if not math.isfinite(score):
            raise ValueError('战术能力必须是 0–100 的有限数值')
        scores[role] = max(0.0, min(100.0, score))
    return validate_tactical_abilities(scores)


def assign_positions(players):
    ids = [p.get('player_id') for p in players]
    if len(players) != 5 or not all(ids) or len(set(ids)) != 5:
        raise ValueError('分配位置需要五名不同的选手')
    ordered = sorted(deepcopy(players), key=lambda p: p['player_id'])
    variants = {}
    for player in ordered:
        player.setdefault('club_role', player.get('role') or 'rifle')
        # Calibrate legacy axes to their saved ability before changing role.
        # Incomplete/no-axes players retain their saved level, not invented stats.
        ensure_role_calibration(player)
        for role in PLAYABLE_ROLES:
            candidate = deepcopy(player)
            candidate['role'] = role
            if candidate.get('stats'):
                refresh_player_ability(candidate)
            variants[player['player_id'], role] = candidate

    def score(roles):
        total = sum(round(playing_ability(variants[p['player_id'], r]) * 10)
                    for p, r in zip(ordered, roles))
        preferred = sum(p['club_role'] == r for p, r in zip(ordered, roles))
        return total, preferred

    roles = max(permutations(PLAYABLE_ROLES), key=score)
    assigned = {p['player_id']: variants[p['player_id'], r] for p, r in zip(ordered, roles)}
    # Keep the visible draft order: only the job/role ability changes.
    return [assigned[pid] for pid in ids]


def assign_lobby_positions(lobby):
    if lobby['mode'] not in ('rank', 'fpl', 'custom'):
        return
    roster = deepcopy(lobby['roster'])
    for side in ('a', 'b'):
        for player in assign_positions([roster[pid] for pid in lobby[side]]):
            roster[player['player_id']] = player
    lobby['roster'] = roster
    lobby['role_assignment_version'] = ASSIGNMENT_VERSION
