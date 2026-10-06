"""Read build-time club marks; never download or rasterize during a match."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

from ..paths import data_file


def _key(value: str) -> str:
    # Exact normalized names only, never fuzzy-match another club or academy.
    name = str(value).casefold()
    if "/" in name or "\\" in name:
        return ""
    return re.sub(r"[^a-z0-9]", "", name)


@lru_cache(maxsize=4)
def _catalog(path: Path) -> dict:
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(catalog, dict) and catalog.get("schema_version") == 1 and isinstance(catalog.get("teams"), dict):
            return catalog["teams"]
        return {}
    except (OSError, ValueError, KeyError):
        return {}


def club_mark(team: dict) -> Path | None:
    """An optional, hash-checked 64px mark; callers own the existing fallback."""
    root = data_file("team_logo_avatars")
    catalog = _catalog(root / "manifest.json")
    for name in (team.get("name", ""), team.get("team_id", "")):
        entry = catalog.get(_key(name))
        if not isinstance(entry, dict):
            continue
        filename = entry.get("file", "")
        if not isinstance(filename, str) or not re.fullmatch(r"[a-z0-9-]+\.png", filename):
            continue
        path = root / filename
        try:
            with path.open("rb") as stream:
                payload = stream.read(16 * 1024 + 1)
        except OSError:
            continue
        if (0 < len(payload) <= 16 * 1024 and payload.startswith(b"\x89PNG\r\n\x1a\n")
                and hashlib.sha256(payload).hexdigest() == entry.get("sha256")):
            return path
    return None
