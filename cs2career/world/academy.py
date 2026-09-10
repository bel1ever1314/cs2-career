# coding=utf-8
"""Year-end academy intake from a fixed unused-name pool."""

from __future__ import annotations

import json

from ..paths import data_file
from .ability import ability_of, calibrate_role, generate_axes, generate_command
from .aging import starting_igl_years
from .eras import player_id

ROLES = ("rifle", "entry", "awp", "lurk", "igl")


def load_names() -> list[str]:
    path = data_file("academy_names.json")
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [str(n).strip() for n in raw if str(n).strip()]
    return []


def _pick(name: str, kind: str) -> dict:
    seed = sum((i + 1) * ord(ch) for i, ch in enumerate(name))
    role = ROLES[seed % (4 if kind == "wonder" else 5)]
    if kind == "wonder":
        ability = 74.0 + (seed % 5)
        potential = 94.0 + (seed % 5)
        age = 16 + (seed % 3)
        note = "wonder"
        region = ("EU", "AM", "AS")[seed % 3]
    else:
        ability = 62.0 + (seed % 7)
        potential = 78.0 + (seed % 9)
        age = 16 + (seed % 3)
        note = "academy"
        region = ("EU", "AM", "AS")[seed % 3]
    axes = generate_axes(name, role, ability)
    gun = round(ability_of(axes, role), 1)
    cmd = generate_command(name, role, gun)
    stats = {**axes, "command": cmd, "ability": gun}
    calibrate_role(stats, role, gun)
    return {
        "player_id": player_id(name),
        "name": name,
        "role": role,
        "ability": gun,
        "command": cmd,
        "stats": stats,
        "form_delta": 0.0,
        "form": gun,
        "age": age,
        "potential": round(potential, 1),
        "igl_years": starting_igl_years(name, role, age),
        "region": region,
        "note": note,
        "team": None,
        "fee": None,
    }


def wonderkid_year(year: int, start_year: int) -> bool:
    """Year 3/7/11… counted from the career start year."""
    idx = int(year) - int(start_year)
    return idx >= 2 and (idx - 2) % 4 == 0


def intake(year: int, start_year: int, used: list[str], taken: set[str]) -> list[dict]:
    # Stable IDs fold case and whitespace. Name-pool aliases must obey the
    # same identity rule, including duplicate entries inside an author list.
    seen = {str(n).strip().casefold() for n in [*used, *taken]}
    pool = []
    for name in load_names():
        key = name.strip().casefold()
        if key not in seen:
            pool.append(name)
            seen.add(key)
    need = 2 + (1 if wonderkid_year(year, start_year) else 0)
    picked = pool[:need]
    rows = []
    for i, name in enumerate(picked):
        kind = "wonder" if wonderkid_year(year, start_year) and i == 0 else "academy"
        row = _pick(name, kind)
        row['academy_year'] = int(year)
        rows.append(row)
    return rows
