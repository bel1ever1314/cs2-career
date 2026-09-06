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
    header += "// Career players added by CS2 Career 2.2\n"
    return db_text.rstrip("\n") + "\n" + header + "".join(blocks), len(blocks)


def build_profile_vpk(dst: Path, base_vpk: Path, teams: list[dict]) -> int:
    """Rebuild the game's botprofile.vpk with the career roster inside."""
    db_text, added = add_people(read_db(base_vpk), career_people(teams))
    write_vpk(dst, db_text)
    return added


def seed_mod_profiles(mod_source: Path, teams: list[dict]) -> int:
    """Do not rewrite the mod's Low/Medium/High VPKs.

    Those files are the Bot Improver difficulty pack. Writing them back
    with our packer is what made 极难 feel like 简单.
    """
    return 0
