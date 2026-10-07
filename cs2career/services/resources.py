"""Local, read-only media projection for the Godot client.

The opt-in manifest points at game loading artwork and already downloaded skin
images. It never opens player saves or fetches a URL during a context refresh.
An absent image stays absent; neither a radar nor another skin is substituted.
"""
from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=4)
def _load_manifest(filename: str, modified_ns: int) -> dict:
    try:
        data = json.loads(Path(filename).read_text("utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) and data.get("schema_version") == 1 else {}


def media_manifest() -> tuple[dict, Path]:
    filename = os.environ.get("CS2CAREER3D_MEDIA_CONFIG", "")
    if not filename:
        return {}, Path(".")
    path = Path(filename)
    if not path.is_absolute():
        return {}, Path(".")
    try:
        return _load_manifest(str(path), path.stat().st_mtime_ns), path.parent
    except OSError:
        return {}, path.parent


def _local_image(value, parent: Path) -> str:
    if not isinstance(value, str) or not value or "://" in value:
        return ""
    path = Path(value)
    if not path.is_absolute():
        path = parent / path
    return str(path.resolve()) if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".svg") and path.is_file() else ""


def cached_skin_art(skin_id: str, art: dict) -> str:
    row = art.get("items", {}).get(skin_id) or {}
    if row.get("status") != "mapped" or not row.get("url"):
        return ""
    from cs2career.paths import save_root
    media, parent = media_manifest()
    roots = [save_root() / "skin_art"]
    for value in media.get("skin_cache_roots", []):
        if isinstance(value, str) and value and "://" not in value:
            root = Path(value)
            roots.append(root if root.is_absolute() else parent / root)
    name = hashlib.sha256(row["url"].encode()).hexdigest() + ".png"
    for root in roots:
        target = root / name
        if target.is_file():
            return str(target.resolve())
    return ""


def resource_context(state=None) -> dict:
    media, parent = media_manifest()
    backgrounds = {}
    sources = {}
    for name, row in media.get("map_backgrounds", {}).items():
        if not isinstance(name, str) or not isinstance(row, dict) or row.get("kind") != "loading_art":
            continue
        path = _local_image(row.get("path"), parent)
        if path:
            backgrounds[name] = path
            backgrounds[name.removeprefix("de_")] = path
            sources[name] = row.get("source", "installed CS2")
    team_backgrounds, team_sources = {}, {}
    team_manifest = media.get('team_manifest', '')
    if isinstance(team_manifest, str) and team_manifest and '://' not in team_manifest:
        target = Path(team_manifest)
        target = target if target.is_absolute() else parent / target
        try:
            marks = _load_manifest(str(target), target.stat().st_mtime_ns)
        except OSError:
            marks = {}
        for name, row in marks.get('team_backgrounds', {}).items():
            if not isinstance(row, dict) or row.get('kind') != 'club_logo': continue
            path = _local_image(row.get('path'), target.parent)
            if path:
                team_backgrounds[name] = path
                team_sources[name] = row.get('source', '')
    if state is not None:
        from .team_marks import mark_path
        for team in state.season.teams:
            path = mark_path(team)
            if path:
                team_backgrounds[team['name']] = str(path)
                team_sources[team['name']] = 'player-uploaded'
    return {"media": {"map_backgrounds": backgrounds, "map_sources": sources,
                       "team_backgrounds": team_backgrounds, "team_sources": team_sources,
                       "skin_cache_roots": media.get("skin_cache_roots", []),
                       "notice": "CS2 地图与饰品图片版权归 Valve；仅使用本地游戏资源和核验缓存。"}}
