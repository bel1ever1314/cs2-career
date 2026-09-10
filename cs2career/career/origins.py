# coding=utf-8
"""Config-driven starts for a player-founded organisation.

Keep start balance here instead of in UI code.  Extension packs may present
their own scenarios later, while these three remain the stable built-ins.
"""

from __future__ import annotations


ORIGINS: dict[str, dict] = {
    "street": {
        "id": "street",
        "name": "路人开局",
        "tagline": "钱多、人弱、成长空间最大",
        "description": "你从天梯和小比赛里组队。个人能力最低，但资金最宽裕，并有 3 点自由属性点。",
        "player_ability": 60.0,
        "mate_min": 54.0,
        "mate_max": 64.0,
        "preferred_notes": ("rank", "vet"),
        "club_money": 120000,
        "pocket_money": 30000,
        "attr_points": 3,
        "command": 54,
        "mentality": 58,
    },
    "academy": {
        "id": "academy",
        "name": "青训开局",
        "tagline": "阵容年轻、能力均衡",
        "description": "一支有体系的年轻队。即战力和经营压力居中，并有 1 点自由属性点。",
        "player_ability": 68.0,
        "mate_min": 60.0,
        "mate_max": 70.0,
        "preferred_notes": ("academy",),
        "club_money": 90000,
        "pocket_money": 35000,
        "attr_points": 1,
        "command": 62,
        "mentality": 64,
    },
    "prodigy": {
        "id": "prodigy",
        "name": "天才开局",
        "tagline": "个人最强、队伍最难带",
        "description": "你已经是被关注的天才，但队友和预算有限。开局能扛比赛，经营容错最低。",
        "player_ability": 78.0,
        "mate_min": 54.0,
        "mate_max": 64.0,
        "preferred_notes": ("rank", "academy"),
        "club_money": 70000,
        "pocket_money": 40000,
        "attr_points": 0,
        "command": 56,
        "mentality": 66,
    },
}

DEFAULT_ORIGIN = "academy"


def origin_config(value: str | None) -> dict:
    """Return a copy so a career cannot mutate the global balance table."""
    key = str(value or DEFAULT_ORIGIN)
    return dict(ORIGINS.get(key) or ORIGINS[DEFAULT_ORIGIN])


def public_origins() -> list[dict]:
    return [dict(row) for row in ORIGINS.values()]
