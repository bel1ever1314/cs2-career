"""Assign ranked match positions on copies, never on career club rosters.

There are only 5! = 120 combinations. Maximise the sum of the existing
position-specific ability, not Elo or captain order. Equal totals prefer
players' club positions, then stable IDs so refresh/reload cannot reroll jobs.
The captain remains the drafter; they do not automatically become the IGL.
"""
from copy import deepcopy
from itertools import permutations

from .world.ability import ensure_role_calibration, playing_ability, refresh_player_ability
from .world.roles import PLAYABLE_ROLES

ASSIGNMENT_VERSION = 1


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
    if lobby['mode'] not in ('rank', 'fpl'):
        return
    roster = deepcopy(lobby['roster'])
    for side in ('a', 'b'):
        for player in assign_positions([roster[pid] for pid in lobby[side]]):
            roster[player['player_id']] = player
    lobby['roster'] = roster
    lobby['role_assignment_version'] = ASSIGNMENT_VERSION
