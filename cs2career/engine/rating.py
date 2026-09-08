# coding=utf-8
"""Ability bands and HLTV-1.0-style rating. K/D/A only, no ADR or KAST.

Raw composite uses public HLTV 1.0 anchors (KPR 0.67 / surv 0.33 / APR 0.26).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

AVG_KPR = 0.67
AVG_SURV = 0.33
AVG_APR = 0.26


@dataclass(frozen=True)
class SkillTier:
    name: str
    min_ability: int
    carry_p: float
    cold_p: float
    hot: tuple[float, float]
    normal: tuple[float, float]
    cold: tuple[float, float]
    floor: float


# FIFA/NBA overall bands. carry_p = chance to eat the team's kills on a map.
SKILL_TIERS = (
    SkillTier("超级巨星", 95, 0.20, 0.08, (1.40, 1.86), (1.08, 1.22), (0.86, 0.98), 1.05),
    SkillTier("巨星", 92, 0.16, 0.08, (1.36, 1.80), (1.04, 1.18), (0.80, 0.94), 1.03),
    SkillTier("准巨星", 88, 0.14, 0.08, (1.32, 1.70), (1.00, 1.16), (0.78, 0.92), 1.02),
    SkillTier("明星", 84, 0.10, 0.10, (1.22, 1.52), (0.94, 1.10), (0.76, 0.90), 1.00),
    SkillTier("主力", 78, 0.05, 0.10, (1.12, 1.32), (0.88, 1.06), (0.80, 0.94), 1.00),
    SkillTier("角色", 72, 0.03, 0.10, (1.08, 1.22), (0.86, 1.04), (0.80, 0.95), 1.00),
    SkillTier("功能", 0, 0.02, 0.10, (1.00, 1.16), (0.84, 1.02), (0.78, 0.94), 1.00),
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


def kda_rating(kills: int, deaths: int, assists: int, rounds: int) -> float:
    n = max(1, rounds)
    kpr = kills / n
    dpr = min(deaths / n, 1.0)
    apr = assists / n
    raw = 0.50 * (kpr / AVG_KPR) + 0.35 * ((1.0 - dpr) / AVG_SURV) + 0.15 * (apr / AVG_APR)
    return round(clamp(raw, 0.20, 2.50), 2)


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
