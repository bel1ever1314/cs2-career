"""Versioned local economy defaults; not real-world quotes or money."""

SPONSOR_FLOOR = 55_000
FREE_SIGN_MULTIPLIER = 1.15
NEGOTIATION_FAILURE_RATE = .02
SKILL_COSTS = (3_000, 8_000, 18_000)
SELL_FEES = (.10, .09, .08, .07)
HISTORY_DAYS = 90
MAX_BATCH = 100
RUMOR_PRICE = 750


def potential_stars(value):
    if value is None:
        return None
    return 1 + sum(float(value) >= edge for edge in (65, 75, 80, 90))
