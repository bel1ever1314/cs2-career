# coding=utf-8
"""Put career players into the mod's bot database.

The Bot Improver ships bot personalities as `botprofile.db` inside a one-file
VPK. A bot only keeps the name we ask for if that name has a profile in there,
so before every match we rebuild the VPK with the whole career roster added,
each one tiered by ability and shaped by role.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import struct
from pathlib import Path
from zlib import crc32

from ..world import agent_rows

VPK_SIGNATURE = 0x55AA1234
ENTRY_NAME = "botprofile"
ENTRY_EXT = "db"
NO_ARCHIVE = 0x7FFF

# Bot Improver has no "Superstar" template. ProTop is the 23-name star tier
# (ZywOo, donk, NiKo…). ProSteady is the common pro rifle; RankRifler is Rank.
ROLE_STYLE = {
    "awp": ("SniperPro", "SniperPersonality"),
    "entry": ("Rusher", "RusherPersonality"),
    "lurk": ("Camper", "CamperPersonality"),
    "support": ("RiflePro", "ScoperPersonality"),
    "igl": ("RiflePro", "RiflePersonality"),
    "rifle": ("RiflePro", "RiflePersonality"),
}
DEFAULT_STYLE = ROLE_STYLE["rifle"]

NAME_RE = re.compile(r'^\S+\s+"([^"]+)"', re.MULTILINE)
PUNCT_RE = re.compile(r"[-_.\s]+")
LEVELS = ("Low", "Medium", "High")
STOCK_DIR = "_stock"


def classify_tier(ability: float, note: str = "", on_roster: bool = False) -> str:
    """Map career ability onto Bot Improver identity templates."""
    gun = float(ability or 70)
    if gun >= 90:
        return "ProTop"
    if gun >= 70:
        return "ProSteady"
    return "RankRifler"


CAREER_MARK = "Career players added by CS2 Career"


def native_db_text(db_text: str) -> str:
    """Strip our appendix so a previously seeded VPK still has a clean name list."""
    cut = db_text.find(CAREER_MARK)
    if cut < 0:
        return db_text
    return db_text[:cut].rstrip() + "\n"


def read_db(vpk: Path) -> str:
    """Pull botprofile.db out of a single-entry VPK."""
    blob = vpk.read_bytes()
    sig, version, tree_size = struct.unpack_from("<III", blob, 0)
    if sig != VPK_SIGNATURE:
        raise ValueError(f"不是 VPK 文件：{vpk}")
    head = 12 if version == 1 else 28
    cursor = head

    def text() -> str:
        nonlocal cursor
        end = blob.index(b"\x00", cursor)
        out = blob[cursor:end].decode("utf-8", "replace")
        cursor = end + 1
        return out

    while True:
        ext = text()
        if not ext:
            break
        while True:
            folder = text()
            if not folder:
                break
            while True:
                name = text()
                if not name:
                    break
                _crc, preload, _archive, offset, length, _term = struct.unpack_from(
                    "<IHHIIH", blob, cursor
                )
                cursor += 18 + preload
                if name == ENTRY_NAME and ext == ENTRY_EXT:
                    start = head + tree_size + offset
                    return blob[start : start + length].decode("utf-8", "replace")
    raise ValueError(f"VPK 里没有 botprofile.db：{vpk}")


def write_vpk(dst: Path, db_text: str) -> None:
    """Write botprofile.db back out as a VPK v2 the game will mount."""
    data = db_text.encode("utf-8")
    tree = (
        f"{ENTRY_EXT}\x00".encode("ascii")
        + b" \x00"
        + f"{ENTRY_NAME}\x00".encode("ascii")
        + struct.pack("<IHHIIH", crc32(data), 0, NO_ARCHIVE, 0, len(data), 0xFFFF)
        + b"\x00\x00\x00"
    )
    header = struct.pack("<IIIIIII", VPK_SIGNATURE, 2, len(tree), len(data), 0, 48, 0)
    body = header + tree + data
    body += hashlib.md5(tree).digest() + hashlib.md5(b"").digest()
    body += hashlib.md5(body).digest()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(body)


def db_names(db_text: str) -> set[str]:
    return {name.lower() for name in NAME_RE.findall(db_text)}


def profile_block(name: str, ability: float, role: str, note: str = "", on_roster: bool = False) -> str:
    weapon, personality = ROLE_STYLE.get((role or "").lower(), DEFAULT_STYLE)
    pitch = 92 + crc32(name.encode("utf-8")) % 21
    tier = classify_tier(ability, note, on_roster)
    return (
        f"\n{tier}+{weapon}+{personality} \"{name}\"\n"
        f"    VoicePitch = {pitch}\n"
        "End\n"
    )


def career_people(teams: list[dict]) -> list[dict]:
    """Everyone a match could put on the server: rosters plus free agents."""
    people: list[dict] = []
    for team in teams:
        for player in team.get("players") or []:
            people.append(
                {
                    "name": player.get("name") or "",
                    "ability": float(player.get("ability") or 70),
                    "role": player.get("role") or "rifle",
                    "note": "",
                    "on_roster": True,
                }
            )
    people += [
        {
            "name": row["name"],
            "ability": row["ability"],
            "role": row["role"],
            "note": row.get("note") or "",
            "on_roster": False,
        }
        for row in agent_rows()
    ]
    return people


def add_people(db_text: str, people: list[dict]) -> tuple[str, int]:
    """Append profiles for names the mod does not already know."""
    known = db_names(db_text)
    blocks: list[str] = []
    for person in people:
        name = (person.get("name") or "").strip()
        if not name or '"' in name or name.lower() in known:
            continue
        known.add(name.lower())
        blocks.append(
            profile_block(
                name,
                person.get("ability") or 70,
                person.get("role") or "",
                person.get("note") or "",
                bool(person.get("on_roster")),
            )
        )
    if not blocks:
        return db_text, 0
    header = "\n//---------------------------------------------------------------\n"
    header += "// Career players added by CS2 Career\n"
    return db_text.rstrip("\n") + "\n" + header + "".join(blocks), len(blocks)


def build_profile_vpk(dst: Path, base_vpk: Path, teams: list[dict]) -> int:
    """Rebuild the game's botprofile.vpk with the career roster inside."""
    db_text, added = add_people(read_db(base_vpk), career_people(teams))
    write_vpk(dst, db_text)
    return added


def seed_mod_profiles(mod_source: Path, teams: list[dict]) -> int:
    """Do not rewrite the mod's Low/Medium/High VPKs at match launch."""
    return 0


def fold_name(name: str) -> str:
    return PUNCT_RE.sub("", (name or "").strip().lower())


def name_keys(name: str) -> set[str]:
    n = (name or "").strip()
    if not n:
        return set()
    return {n.lower(), fold_name(n)}


def known_keys(db_text: str) -> set[str]:
    keys: set[str] = set()
    for name in NAME_RE.findall(db_text):
        keys |= name_keys(name)
    return keys


def people_from_stats() -> list[dict]:
    from ..world.ability import load_player_stats

    people: list[dict] = []
    for name, row in load_player_stats().items():
        people.append(
            {
                "name": name,
                "ability": float(row.get("ability") or 70),
                "role": row.get("role") or "rifle",
                "note": "",
                "on_roster": False,
            }
        )
    people.sort(key=lambda p: (-float(p["ability"]), p["name"].lower()))
    return people


def missing_people(db_text: str, people: list[dict] | None = None) -> list[dict]:
    people = people_from_stats() if people is None else people
    known = known_keys(db_text)
    out: list[dict] = []
    seen: set[str] = set()
    for person in people:
        name = (person.get("name") or "").strip()
        keys = name_keys(name)
        if not name or '"' in name or keys & known or keys & seen:
            continue
        seen |= keys
        known |= keys
        out.append(person)
    return out


def read_level_db(level_dir: Path) -> str:
    vpk = level_dir / "botprofile.vpk"
    dbp = level_dir / "botprofile.db"
    if vpk.is_file():
        return read_db(vpk)
    if dbp.is_file():
        return dbp.read_text(encoding="utf-8")
    raise FileNotFoundError(f"没有 botprofile：{level_dir}")


def write_level(level_dir: Path, db_text: str) -> None:
    level_dir.mkdir(parents=True, exist_ok=True)
    dbp = level_dir / "botprofile.db"
    if dbp.is_file():
        dbp.write_bytes(db_text.encode("utf-8"))
    write_vpk(level_dir / "botprofile.vpk", db_text)


def backup_stock(overrides: Path) -> Path:
    stock = overrides / STOCK_DIR
    if (stock / "Medium" / "botprofile.vpk").is_file() or (stock / "Medium" / "botprofile.db").is_file():
        return stock
    for level in LEVELS:
        for name in ("botprofile.db", "botprofile.vpk"):
            src = overrides / level / name
            if src.is_file():
                dst = stock / level / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
    root = overrides / "botprofile.vpk"
    if root.is_file():
        shutil.copy2(root, stock / "botprofile.vpk")
    return stock


def _missing_rows(people: list[dict]) -> list[dict]:
    return [
        {
            "name": person["name"],
            "ability": float(person.get("ability") or 70),
            "role": person.get("role") or "rifle",
            "tier": classify_tier(person.get("ability") or 70),
        }
        for person in people
    ]


def sync_overrides(overrides: Path, people: list[dict] | None = None, write: bool = True, live_level: str = "Medium") -> dict:
    """Append player_stats names onto game/csgo/overrides Low/Medium/High, then copy the selected difficulty to live."""
    people = people_from_stats() if people is None else people
    if live_level not in LEVELS:
        live_level = "Medium"
    report: dict = {"path": str(overrides), "levels": {}, "missing": [], "live": live_level}
    if write:
        backup_stock(overrides)
    preview: list[dict] | None = None
    for level in LEVELS:
        level_dir = overrides / level
        if not (level_dir / "botprofile.vpk").is_file() and not (level_dir / "botprofile.db").is_file():
            continue
        current = read_level_db(level_dir)
        base = native_db_text(current)
        stock = overrides / STOCK_DIR / level / "botprofile.vpk"
        if stock.is_file():
            try:
                base = native_db_text(read_db(stock))
            except (OSError, ValueError):
                pass
        missing_now = missing_people(current, people)
        rows = _missing_rows(missing_now)
        new_text, _ = add_people(base, people)
        if write and new_text != current:
            write_level(level_dir, new_text)
        report["levels"][level] = {"missing": rows, "added": len(missing_now)}
        if preview is None:
            preview = rows
    has_levels = any((overrides / lv / "botprofile.vpk").is_file() for lv in LEVELS)
    if write and has_levels:
        chosen = overrides / live_level / "botprofile.vpk"
        if chosen.is_file():
            shutil.copy2(chosen, overrides / "botprofile.vpk")
    report["missing"] = preview or []
    report["added"] = len(preview or [])
    return report

