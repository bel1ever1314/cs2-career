"""Read-only transfer scouting. Never stamp an estimate into player growth data."""
import math

from .aging import GUN_HI, GUN_LO, gun_year_delta


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def assessment(player):
    known = _number(player.get('potential'))
    if known is not None and 0 < known <= 100:
        return {'potential': known, 'potential_estimated': False}
    stats = player.get('stats') or {}
    baseline = _number(player.get('long_term_ability', stats.get('role_reference_score', player.get('ability'))))
    age = _number(player.get('age'))
    if baseline is None or not 0 < baseline <= 100 or age is None or not 14 <= age <= 70:
        return {'potential': None, 'potential_estimated': False}
    # Project the current permanent baseline through the existing positive
    # growth years. For older players this is remaining peak, not historical peak.
    peak = baseline
    for future_age in range(int(age) + 1, 26):
        baseline = round(max(GUN_LO, min(GUN_HI, baseline + gun_year_delta(future_age, baseline))), 1)
        peak = max(peak, baseline)
    return {'potential': round(peak, 1), 'potential_estimated': True}
