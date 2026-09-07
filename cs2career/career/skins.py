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

RARITY_RANK = {
    "extraordinary": 0,
    "covert": 1,
    "classified": 2,
    "restricted": 3,
    "milspec": 4,
}

WEAPON_DEF = {
    "ak47": 7,
    "m4a1": 60,
    "m4a4": 16,
    "awp": 9,
    "deagle": 1,
    "usp": 61,
    "glock": 4,
}

# Which side can wear this slot. Knives and gloves are independent per team.
SLOT_SIDES = {
    "ak47": ("t",),
    "glock": ("t",),
    "m4a1": ("ct",),
    "m4a4": ("ct",),
    "usp": ("ct",),
    "awp": ("ct", "t"),
    "deagle": ("ct", "t"),
    "knife": ("ct", "t"),
    "gloves": ("ct", "t"),
}

TEAM_T = 2
TEAM_CT = 3
SELL_FEE = 0.10
# Immediate cash-out EV / (case + key). Spend 100, get about 80 back.
CASE_TARGET_RETURN = 0.80
QUOTE_WALK = 0.07

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
    return list(catalog()["skins"])


def sides_for(slot: str) -> tuple[str, ...]:
    return SLOT_SIDES.get(slot or "", ("ct", "t"))


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


def case_pool(case_id: str) -> list[dict]:
    box = case_map().get(case_id) or {}
    skins = skin_map()
    return [skins[sid] for sid in box.get("drops") or [] if sid in skins]


def quote_of(career, skin_id: str) -> int:
    quotes = getattr(career, "skin_quotes", None) or {}
    if skin_id in quotes:
        return max(1, int(quotes[skin_id]))
    row = skin_map().get(skin_id) or {}
    return max(1, int(row.get("buy") or row.get("sell") or 1))


def quote_band(row: dict) -> tuple[int, int]:
    mid = max(1, int(row.get("buy") or row.get("sell") or 1))
    return max(1, int(mid * 0.40)), max(2, int(mid * 1.80))


def sell_proceeds(spot: int) -> int:
    return max(1, int(round(int(spot) * (1.0 - SELL_FEE))))


def _quote_walk(value: int, lo: int, hi: int) -> int:
    factor = 1.0 + random.uniform(-QUOTE_WALK, QUOTE_WALK)
    nxt = int(round(value * factor))
    return max(lo, min(hi, max(1, nxt)))


def ensure_quotes(career) -> bool:
    """Fill missing spot prices from the catalog. Returns True if anything changed."""
    quotes = dict(getattr(career, "skin_quotes", None) or {})
    changed = False
    for row in catalog()["skins"]:
        sid = row["id"]
        if sid in quotes:
            continue
        quotes[sid] = max(1, int(row.get("buy") or row.get("sell") or 1))
        changed = True
    if changed:
        career.skin_quotes = quotes
    return changed


def tick_quotes(career) -> None:
    """One calendar day of independent random walks, clamped per skin."""
    ensure_quotes(career)
    career.skin_quotes_prev = dict(career.skin_quotes)
    nxt = {}
    for row in catalog()["skins"]:
        sid = row["id"]
        lo, hi = quote_band(row)
        nxt[sid] = _quote_walk(int(career.skin_quotes.get(sid) or lo), lo, hi)
    career.skin_quotes = nxt


def case_spot_ev(career, case_id: str) -> float:
    """Expected market value of one open, using current quotes and rarity weights."""
    pool = case_pool(case_id)
    if not pool:
        return 0.0
    weights = [RARITY_WEIGHT.get(s.get("rarity") or "milspec", 8) for s in pool]
    total = sum(weights) or 1.0
    return sum(w * quote_of(career, s["id"]) for s, w in zip(pool, weights)) / total


def _split_case_cost(box: dict, cost: int) -> tuple[int, int]:
    base = max(1, int(box.get("price") or 0) + int(box.get("key") or 0))
    price_share = int(box.get("price") or 0) / base if base else 0.55
    price = max(20, int(round(cost * price_share)))
    key = max(20, cost - price)
    if price + key < cost:
        key += cost - price - key
    return price, key


def retune_cases(career) -> None:
    """Keep each case's expected cash-out below cost, around 80% return."""
    ensure_quotes(career)
    live = dict(getattr(career, "case_prices", None) or {})
    for box in catalog()["cases"]:
        cid = box["id"]
        ev = case_spot_ev(career, cid)
        cash_ev = ev * (1.0 - SELL_FEE)
        cost = max(40, int(round(cash_ev / CASE_TARGET_RETURN))) if cash_ev > 0 else 80
        # Never let the case go +EV even if quotes jump overnight.
        while cash_ev / max(1, cost) >= 0.99:
            cost += 10
        price, key = _split_case_cost(box, cost)
        live[cid] = {
            "price": price,
            "key": key,
            "ev": round(ev, 2),
            "cash_ev": round(cash_ev, 2),
            "ret": round(cash_ev / max(1, price + key), 4),
        }
    career.case_prices = live


def ensure_economy(career) -> bool:
    changed = ensure_quotes(career)
    if not getattr(career, "case_prices", None):
        retune_cases(career)
        return True
    return changed


def advance_day(career) -> None:
    tick_quotes(career)
    retune_cases(career)


def case_cost(case_id: str, career=None) -> int:
    live = (getattr(career, "case_prices", None) or {}).get(case_id) if career is not None else None
    if live:
        return int(live.get("price") or 0) + int(live.get("key") or 0)
    box = case_map().get(case_id)
    if not box:
        return 0
    return int(box.get("price") or 0) + int(box.get("key") or 0)


def migrate_equipped(career) -> None:
    """Old saves had one loadout for both teams."""
    ct = dict(getattr(career, "equipped_ct", None) or {})
    t = dict(getattr(career, "equipped_t", None) or {})
    old = dict(getattr(career, "equipped", None) or {})
    if not ct and not t and old:
        by_id = {row.get("id"): row for row in (career.inventory or [])}
        for slot, inv_id in old.items():
            row = by_id.get(inv_id) or {}
            use = row.get("slot") or slot
            sides = sides_for(use)
            if "ct" in sides:
                ct[use] = inv_id
            if "t" in sides:
                t[use] = inv_id
    career.equipped_ct = ct
    career.equipped_t = t
    career.equipped = {**ct, **t}


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


def _put_item(body: dict, payload: dict, side: str) -> None:
    slot = payload.pop("slot")
    team = str(TEAM_CT if side == "ct" else TEAM_T)
    if slot == "gloves":
        body["gloves"][team] = dict(payload)
        return
    if slot == "knife":
        body["knives"][team] = dict(payload)
        return
    if not payload.get("def"):
        return
    key = str(payload["def"])
    if side == "ct":
        body["ctWeapons"][key] = dict(payload)
    else:
        body["tWeapons"][key] = dict(payload)


def equipped_v5_body(items: list[dict], equipped_ct: dict, equipped_t: dict | None = None) -> dict:
    """Official plugin payload: EquippedV5Response, no steamid wrapper."""
    if equipped_t is None:
        equipped_t = equipped_ct
    by_id = {row["id"]: row for row in items}
    body = {
        "agents": {},
        "collectible": None,
        "ctWeapons": {},
        "gloves": {},
        "graffiti": None,
        "knives": {},
        "musicKit": None,
        "tWeapons": {},
    }
    for inv_id in (equipped_ct or {}).values():
        row = by_id.get(inv_id)
        if row:
            _put_item(body, _item_payload(row), "ct")
    for inv_id in (equipped_t or {}).values():
        row = by_id.get(inv_id)
        if row:
            _put_item(body, _item_payload(row), "t")
    return body


def equipped_payload(items: list[dict], equipped_ct: dict, steam_id: str, equipped_t: dict | None = None) -> dict:
    sid = "".join(ch for ch in str(steam_id or "") if ch.isdigit())
    if not sid:
        return {}
    return {sid: equipped_v5_body(items, equipped_ct, equipped_t)}


def repair_items(items: list[dict]) -> bool:
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


def write_inventories(csgo: Path, payload: dict, stamp: str = "") -> Path | None:
    if not payload:
        return None
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
    return dest_dir / "inventories.json"


def write_owner_steamid(csgo: Path, steam_id: str) -> None:
    digits = "".join(ch for ch in str(steam_id or "") if ch.isdigit())
    dest = (
        csgo
        / "addons"
        / "counterstrikesharp"
        / "configs"
        / "plugins"
        / "InventorySimulator"
        / "owner.txt"
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(digits, encoding="ascii")


def plugin_installed(csgo: Path | None = None) -> bool:
    try:
        if csgo is None:
            from ..cs2.launch import settings

            csgo = Path(settings()["csgo_path"])
    except (OSError, KeyError, TypeError, ValueError):
        return False
    return (csgo / "addons" / "counterstrikesharp" / "plugins" / "InventorySimulator" / "InventorySimulator.dll").is_file()


def sync_live(career) -> None:
    """Push equipped skins to CS2 as soon as the player changes them."""
    if not getattr(career, "real_skins", False):
        return
    try:
        from ..cs2.launch import settings, write_invsim_cfg

        csgo = Path(settings()["csgo_path"])
        if not csgo.is_dir() or not plugin_installed(csgo):
            return
        write_inventories(
            csgo,
            equipped_payload(
                career.inventory,
                getattr(career, "equipped_ct", None) or {},
                career.steam_id,
                getattr(career, "equipped_t", None) or {},
            ),
        )
        write_owner_steamid(csgo, career.steam_id)
        write_invsim_cfg(csgo, career.steam_id)
    except (OSError, KeyError, TypeError, ValueError):
        return


def _decorate_skin(career, row: dict) -> dict:
    spot = quote_of(career, row["id"])
    prev = int((getattr(career, "skin_quotes_prev", None) or {}).get(row["id"]) or spot)
    return {
        **row,
        "spot": spot,
        "prev": prev,
        "delta": spot - prev,
        "sell": sell_proceeds(spot),
        "sides": list(sides_for(row.get("slot") or "")),
    }


def _decorate_item(career, row: dict) -> dict:
    sid = row.get("skin_id") or ""
    spot = quote_of(career, sid) if sid else int(row.get("sell") or 0)
    return {
        **row,
        "spot": spot,
        "sell": sell_proceeds(spot),
        "sides": list(sides_for(row.get("slot") or "")),
    }


def shop_public(career) -> dict:
    ensure_economy(career)
    migrate_equipped(career)
    pending = career.pending_drop
    if pending:
        sid = pending.get("id") or pending.get("skin_id") or ""
        spot = quote_of(career, sid) if sid else int(pending.get("sell") or 0)
        pending = {**pending, "spot": spot, "sell": sell_proceeds(spot)}
    cases = []
    live = getattr(career, "case_prices", None) or {}
    for box in catalog()["cases"]:
        row = dict(box)
        prices = live.get(box["id"]) or {}
        if prices:
            row["price"] = int(prices.get("price") or row.get("price") or 0)
            row["key"] = int(prices.get("key") or row.get("key") or 0)
            row["ev"] = prices.get("ev")
            row["cash_ev"] = prices.get("cash_ev")
            row["ret"] = prices.get("ret")
        row["pool"] = [_decorate_skin(career, s) for s in case_pool(box["id"])]
        cases.append(row)
    weapons = []
    seen = set()
    for row in catalog()["skins"]:
        w = row.get("weapon") or ""
        if w and w not in seen:
            seen.add(w)
            weapons.append(w)
    return {
        "cases": cases,
        "market": [_decorate_skin(career, row) for row in catalog()["skins"]],
        "inventory": [_decorate_item(career, row) for row in (career.inventory or [])],
        "equipped": career.equipped or {},
        "equipped_ct": getattr(career, "equipped_ct", None) or {},
        "equipped_t": getattr(career, "equipped_t", None) or {},
        "pending": pending,
        "rarities": list(RARITY_WEIGHT),
        "fee": SELL_FEE,
        "target_return": CASE_TARGET_RETURN,
        "weapons": weapons,
        "plugin": plugin_installed(),
    }
