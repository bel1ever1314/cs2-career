# coding=utf-8
"""Personal skin inventory, case opening, and the Inventory Simulator file."""

from __future__ import annotations

import json
import random
from pathlib import Path

from ..paths import data_file

RARITY_WEIGHT = {
    "milspec": 80,
    "restricted": 16,
    "classified": 3.2,
    "covert": 0.64,
    "extraordinary": 0.16,
}

# CS2 item definition indexes. Knives/gloves use their own defs.
WEAPON_DEF = {
    "ak47": 7,
    "m4a1": 60,
    "m4a4": 16,
    "awp": 9,
    "deagle": 1,
    "usp": 61,
    "glock": 4,
}

TEAM_T = 2
TEAM_CT = 3

_CATALOG: dict | None = None


def catalog() -> dict:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = json.loads(data_file("skins.json").read_text(encoding="utf-8"))
    return _CATALOG


def skin_map() -> dict[str, dict]:
    return {row["id"]: row for row in catalog()["skins"]}


def case_map() -> dict[str, dict]:
    return {row["id"]: row for row in catalog()["cases"]}


def market_rows() -> list[dict]:
    skins = skin_map()
    return [skins[sid] for sid in catalog().get("market") or [] if sid in skins]


def _wear() -> float:
    return round(random.uniform(0.01, 0.38), 4)


def _paint_of(skin: dict) -> int:
    return int(skin.get("paint") or 0)


_NAMED_DEF = {
    "weapon_knife_karambit": 507,
    "weapon_bayonet": 500,
    "sport_gloves": 5030,
    "specialist_gloves": 5034,
}


def _def_of(skin: dict) -> int:
    raw = skin.get("def")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    if isinstance(raw, str) and raw in _NAMED_DEF:
        return _NAMED_DEF[raw]
    return int(WEAPON_DEF.get(skin.get("slot") or "", 0) or 0)


def make_item(skin: dict, source: str, seq: int) -> dict:
    return {
        "id": f"inv.{seq}",
        "skin_id": skin["id"],
        "name": skin["name"],
        "weapon": skin["weapon"],
        "slot": skin["slot"],
        "rarity": skin["rarity"],
        "wear": _wear(),
        "source": source,
        "sell": int(skin.get("sell") or 0),
        "def": _def_of(skin),
        "paint": _paint_of(skin),
    }


def open_case(case_id: str) -> dict:
    box = case_map().get(case_id)
    if not box:
        raise ValueError("没有这个箱子。")
    skins = skin_map()
    pool = [skins[sid] for sid in box.get("drops") or [] if sid in skins]
    if not pool:
        raise ValueError("这个箱子是空的。")
    weights = [RARITY_WEIGHT.get(s.get("rarity") or "milspec", 8) for s in pool]
    return random.choices(pool, weights=weights, k=1)[0]


def case_cost(case_id: str) -> int:
    box = case_map().get(case_id)
    if not box:
        return 0
    return int(box.get("price") or 0) + int(box.get("key") or 0)


def _seed_of(row: dict) -> int:
    raw = row.get("seed")
    if isinstance(raw, int) and 1 <= raw <= 1000:
        return raw
    text = str(row.get("id") or row.get("skin_id") or "1")
    return (sum(ord(ch) for ch in text) * 1103515245 + 12345) % 1000 + 1


def _item_payload(row: dict) -> dict:
    cat = skin_map().get(row.get("skin_id") or "") or {}
    slot = row.get("slot") or cat.get("slot") or ""
    paint = int(row.get("paint") or cat.get("paint") or 0)
    defn = _def_of({**cat, **row, "slot": slot})
    return {
        "def": defn,
        "paint": paint,
        "wear": float(row.get("wear") or 0.15),
        "seed": _seed_of(row),
        "stickers": [],
        "slot": slot,
    }


SKIN_API_PORT = 18768
SKIN_API_URL = f"http://127.0.0.1:{SKIN_API_PORT}"


def equipped_v5_body(items: list[dict], equipped: dict) -> dict:
    """Official plugin payload: EquippedV5Response, no steamid wrapper."""
    by_id = {row["id"]: row for row in items}
    ct: dict[str, dict] = {}
    t: dict[str, dict] = {}
    knives: dict[str, dict] = {}
    gloves: dict[str, dict] = {}
    for _slot, inv_id in (equipped or {}).items():
        row = by_id.get(inv_id)
        if not row:
            continue
        payload = _item_payload(row)
        slot = payload.pop("slot")
        if slot == "gloves":
            # SetWearables is the native that has been crashing this CS2 build.
            continue
        if slot == "knife":
            knives[str(TEAM_T)] = dict(payload)
            knives[str(TEAM_CT)] = dict(payload)
        else:
            key = str(payload["def"])
            if not payload["def"]:
                continue
            ct[key] = dict(payload)
            t[key] = dict(payload)
    return {
        "agents": {},
        "collectible": None,
        "ctWeapons": ct,
        "gloves": gloves,
        "graffiti": None,
        "knives": knives,
        "musicKit": None,
        "tWeapons": t,
    }


def equipped_payload(items: list[dict], equipped: dict, steam_id: str) -> dict:
    """Local file: steamid -> EquippedV5Response."""
    sid = "".join(ch for ch in str(steam_id or "") if ch.isdigit())
    if not sid:
        return {}
    return {sid: equipped_v5_body(items, equipped)}


def repair_items(items: list[dict]) -> bool:
    """Fill missing def/paint on old inventory rows from the catalog."""
    changed = False
    for row in items:
        if not isinstance(row, dict):
            continue
        payload = _item_payload(row)
        if row.get("def") != payload["def"] or row.get("paint") != payload["paint"]:
            row["def"] = payload["def"]
            row["paint"] = payload["paint"]
            changed = True
    return changed


def write_inventories(csgo: Path, payload: dict, stamp: str = "") -> None:
    if not payload:
        return
    dest_dir = (
        csgo
        / "addons"
        / "counterstrikesharp"
        / "configs"
        / "plugins"
        / "InventorySimulator"
    )
    dest_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    names = ["inventories.json", "inventories.career.json"]
    if stamp:
        names.append(f"inventories.career.{stamp}.json")
    for name in names:
        (dest_dir / name).write_text(text, encoding="utf-8")
    (csgo / "inventories.career.json").write_text(text, encoding="utf-8")


def sync_live(career) -> None:
    """Push equipped skins to CS2 as soon as the player changes them."""
    if not getattr(career, "real_skins", False):
        return
    try:
        from ..cs2.launch import settings, write_invsim_cfg

        csgo = Path(settings()["csgo_path"])
        if not csgo.is_dir():
            return
        write_inventories(
            csgo,
            equipped_payload(career.inventory, career.equipped, career.steam_id),
        )
        write_invsim_cfg(csgo)
    except (OSError, KeyError, TypeError, ValueError):
        return


def shop_public(items: list[dict], equipped: dict, pending: dict | None) -> dict:
    return {
        "cases": catalog()["cases"],
        "market": market_rows(),
        "inventory": items,
        "equipped": equipped or {},
        "pending": pending,
        "rarities": list(RARITY_WEIGHT),
    }
