# coding=utf-8
"""Ability bands and HLTV-1.0-style rating. K/D/A only, no ADR or KAST."""

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
    SkillTier("超级巨星", 95, 0.58, 0.06, (1.38, 1.70), (1.08, 1.22), (0.82, 0.96), 1.08),
    SkillTier("巨星", 92, 0.28, 0.10, (1.40, 1.75), (0.94, 1.12), (0.74, 0.90), 1.02),
    SkillTier("准巨星", 88, 0.24, 0.10, (1.38, 1.70), (0.94, 1.12), (0.74, 0.90), 1.00),
    SkillTier("明星", 84, 0.12, 0.12, (1.26, 1.50), (0.90, 1.08), (0.74, 0.90), 1.00),
    SkillTier("主力", 78, 0.05, 0.10, (1.15, 1.32), (0.88, 1.06), (0.80, 0.94), 1.00),
    SkillTier("角色", 72, 0.02, 0.08, (1.08, 1.20), (0.86, 1.04), (0.80, 0.95), 1.00),
    SkillTier("功能", 0, 0.00, 0.06, (1.00, 1.08), (0.84, 1.02), (0.78, 0.94), 1.00),
)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def skill_tier(ability: float) -> SkillTier:
    for tier in SKILL_TIERS:
        if ability >= tier.min_ability:
            return tier
    return SKILL_TIERS[-1]


def expected_dpr(ability: float) -> float:
    """Stars die ~0.55-0.62 per round, role players ~0.68-0.74, IGLs ~0.72-0.80."""
    return clamp(0.72 - 0.20 * (ability - 70.0) / 30.0, 0.52, 0.82)


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
