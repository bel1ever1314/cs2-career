# coding=utf-8
"""Team crests: brand colour + short tag, with an override hook for real logos.

Drop a PNG named <team-slug>.png into the save folder's `logos/` directory and it
replaces the generated crest everywhere in the UI.
"""

from __future__ import annotations

from ..paths import logo_dir, static_dir

# name -> (primary, ink, tag)
BRANDS: dict[str, tuple[str, str, str]] = {
    "Falcons": ("#0f7a4a", "#ffffff", "FLC"),
    "Vitality": ("#f2d600", "#111111", "VIT"),
    "Spirit": ("#e23b3b", "#ffffff", "SPT"),
    "FURIA": ("#f0b323", "#151515", "FUR"),
    "NAVI": ("#ffe000", "#111111", "NAVI"),
    "Aurora": ("#7b4bf0", "#ffffff", "AUR"),
    "BetBoom": ("#f5c518", "#151515", "BB"),
    "MOUZ": ("#e2001a", "#ffffff", "MOUZ"),
    "G2": ("#d81f3c", "#ffffff", "G2"),
    "The MongolZ": ("#d4232a", "#ffffff", "TMG"),
    "Legacy": ("#6b4bd6", "#ffffff", "LEG"),
    "FaZe": ("#e21b1b", "#ffffff", "FAZE"),
    "PARIVISION": ("#00b9a4", "#0d1214", "PARI"),
    "paiN": ("#d5232c", "#ffffff", "PAIN"),
    "GamerLegion": ("#f2c200", "#151515", "GL"),
    "Liquid": ("#1f5fd0", "#ffffff", "TL"),
    "Astralis": ("#e30613", "#ffffff", "AST"),
    "B8": ("#ff5c00", "#ffffff", "B8"),
    "3DMAX": ("#00a3e0", "#ffffff", "3DM"),
    "TYLOO": ("#e2001a", "#ffffff", "TY"),
    "BIG": ("#c8102e", "#ffffff", "BIG"),
    "MIBR": ("#00a859", "#ffffff", "MIBR"),
    "NiP": ("#0057b8", "#ffffff", "NIP"),
    "HEROIC": ("#f5a623", "#151515", "HER"),
    "FlyQuest": ("#12864a", "#ffffff", "FLY"),
    "Lynn Vision": ("#f2a900", "#151515", "LVG"),
    "M80": ("#e94f37", "#ffffff", "M80"),
    "9z": ("#7b2bd9", "#ffffff", "9Z"),
    "Imperial": ("#1b998b", "#ffffff", "IMP"),
    "OG": ("#9aa0a8", "#111111", "OG"),
    "FUT": ("#f2c200", "#151515", "FUT"),
    "NRG": ("#e6194b", "#ffffff", "NRG"),
    "Virtus.pro": ("#f5a300", "#151515", "VP"),
    "100 Thieves": ("#e4002b", "#ffffff", "100T"),
    "Rare Atom": ("#b41f24", "#ffffff", "RA"),
    "SINNERS": ("#9dc800", "#151515", "SIN"),
    "Fluxo": ("#00c9a0", "#0d1214", "FLX"),
    "9INE": ("#ff6b00", "#ffffff", "9INE"),
    "Luminosity": ("#0aa3ff", "#0d1214", "LG"),
    "Sharks": ("#1e88e5", "#ffffff", "SHK"),
    "ENCE": ("#00b2a9", "#0d1214", "ENCE"),
    "fnatic": ("#ff5900", "#ffffff", "FNC"),
    "SAW": ("#eaa300", "#151515", "SAW"),
    "Passion UA": ("#f2d600", "#151515", "PSN"),
    "Complexity": ("#12468f", "#ffffff", "COL"),
    "BESTIA": ("#d92b2b", "#ffffff", "BST"),
    "ATOX": ("#d4a017", "#151515", "ATOX"),
    "HOTU": ("#7a5cff", "#ffffff", "HOTU"),
    "Chinggis Warriors": ("#c8963e", "#151515", "CW"),
}

FALLBACK_INK = "#0d1214"
PALETTE = ("#5b8def", "#3dd68c", "#e7c36a", "#ef6f6c", "#9b7bf0", "#37bec9", "#e08a3c")


def _auto_tag(name: str) -> str:
    words = [w for w in name.replace(".", " ").split() if w]
    if len(words) > 1:
        return "".join(w[0] for w in words)[:4].upper()
    return name[:3].upper()


def _auto_color(name: str) -> str:
    return PALETTE[sum(ord(c) for c in name) % len(PALETTE)]


def crest(team: dict) -> dict:
    """UI payload: uploaded PNG, bundled mark, or generated colour + tag."""
    name = team.get("name", "")
    slug = team.get("id", "")
    custom = team.get("logo")
    color, ink, tag = BRANDS.get(name, (_auto_color(name), FALLBACK_INK, _auto_tag(name)))
    if team.get("color"):
        color = team["color"]
    if custom:
        return {"kind": "image", "src": custom, "color": color, "ink": ink, "tag": tag}
    png = logo_dir() / f"{slug}.png"
    if png.is_file():
        return {"kind": "image", "src": f"/logo/{slug}.png", "color": color, "ink": ink, "tag": tag}
    bundled = static_dir() / "crests" / f"{slug}.svg"
    if bundled.is_file():
        return {"kind": "image", "src": f"/crests/{slug}.svg", "color": color, "ink": ink, "tag": tag}
    return {"kind": "mark", "src": "", "color": color, "ink": ink, "tag": tag}
