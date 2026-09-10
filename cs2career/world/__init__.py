# coding=utf-8
"""Static world: teams, rosters, eras, free agents, roles, crests."""

from .brand import BRANDS, crest
from .eras import ERA_META, ERA_RANK_ORDER, ERA_ROSTERS, opening_rank
from .pool import FREE_AGENTS, age_of, agent_rows, birth_label, birthday_md, starter_mates
from .roles import ROLE_LABEL, PLAYABLE_ROLES, apply_roles, role_of
from .teams import (
    MAPS,
    TEAMS,
    build_teams,
    maps_for,
    roster_names,
    slug,
    tier_of,
)

__all__ = [
    "BRANDS",
    "ERA_META",
    "ERA_RANK_ORDER",
    "ERA_ROSTERS",
    "opening_rank",
    "FREE_AGENTS",
    "MAPS",
    "PLAYABLE_ROLES",
    "ROLE_LABEL",
    "TEAMS",
    "age_of",
    "birth_label",
    "birthday_md",
    "agent_rows",
    "apply_roles",
    "starter_mates",
    "build_teams",
    "crest",
    "maps_for",
    "role_of",
    "roster_names",
    "slug",
    "tier_of",
]
