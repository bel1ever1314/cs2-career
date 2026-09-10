# coding=utf-8
"""Shared Career Rating v2 for real CS2 and simulated event ledgers."""

from __future__ import annotations

import math
from dataclasses import dataclass

AVG_KPR = 0.67
AVG_SURV = 0.33
AVG_APR = 0.20
AVG_ADR = 74.0
AVG_KAST = 0.72


@dataclass(frozen=True)
class SkillTier:
    name: str
    min_ability: int
    floor: float


# FIFA/NBA-style display bands. There is no fixed hot/cold explosion roll in v2.
SKILL_TIERS = (
    SkillTier("超级巨星", 95, 1.05),
    SkillTier("巨星", 92, 1.03),
    SkillTier("准巨星", 88, 1.02),
    SkillTier("明星", 84, 1.00),
    SkillTier("主力", 78, 1.00),
    SkillTier("角色", 72, 1.00),
    SkillTier("功能", 0, 1.00),
)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def skill_tier(ability: float) -> SkillTier:
    for tier in SKILL_TIERS:
        if ability >= tier.min_ability:
            return tier
    return SKILL_TIERS[-1]


def expected_dpr(ability: float) -> float:
    """Stars die less; role players eat more of the team's deaths."""
    return clamp(0.66 - 0.18 * (ability - 70.0) / 30.0, 0.48, 0.74)


def career_rating(
    kills: int,
    deaths: int,
    assists: int,
    damage: int,
    kast_rounds: float,
    rounds: int,
) -> float:
    n = max(1, rounds)
    kpr = kills / n
    survival = 1.0 - min(deaths / n, 1.0)
    apr = assists / n
    adr = max(0, damage) / n
    kast = clamp(kast_rounds / n, 0.0, 1.0)
    raw = (
        0.35 * kpr / AVG_KPR
        + 0.15 * survival / AVG_SURV
        + 0.10 * apr / AVG_APR
        + 0.20 * adr / AVG_ADR
        + 0.20 * kast / AVG_KAST
    )
    return round(clamp(raw, 0.20, 2.50), 2)


def kda_rating(
    kills: int,
    deaths: int,
    assists: int,
    rounds: int,
    damage: int | None = None,
    kast_rounds: float | None = None,
) -> float:
    """Compatibility entry point, now always routed through Rating v2.

    Historical aggregate callers lack damage/KAST. Conservative estimates keep
    old saves readable; all new real and simulated maps pass measured values.
    """
    n = max(1, rounds)
    if damage is None:
        damage = int(round((kills * 100 + assists * 35) * 0.78))
    if kast_rounds is None:
        survived = max(0, n - deaths)
        kast_rounds = min(n, survived + kills * 0.55 + assists * 0.35)
    return career_rating(kills, deaths, assists, damage, kast_rounds, n)


_OVERALL_RATING = ((60, .85), (70, .95), (76, 1.00), (82, 1.05), (89, 1.10), (93, 1.15), (96, 1.20), (98, 1.30))


def expected_rating(overall: float) -> float:
    value = float(overall)
    if value <= 60:
        return max(.60, .85 + (value - 60) / 100.0)
    for (o0, r0), (o1, r1) in zip(_OVERALL_RATING, _OVERALL_RATING[1:]):
        if value <= o1:
            return r0 + (value - o0) / (o1 - o0) * (r1 - r0)
    return min(1.50, 1.30 + (value - 98) * .05)


def allocate_ints(weights: list[float], total: int) -> list[int]:
    weights = [max(0.01, w) for w in weights]
    s = sum(weights)
    raw = [total * w / s for w in weights]
    out = [int(math.floor(x)) for x in raw]
    remain = total - sum(out)
    order = sorted(range(len(out)), key=lambda i: raw[i] - out[i], reverse=True)
    for i in range(remain):
        out[order[i % len(out)]] += 1
    return out
