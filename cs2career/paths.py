# coding=utf-8
"""Read-only resources vs writable save data. Works frozen (PyInstaller) or from source."""

from __future__ import annotations

import sys
import os
from pathlib import Path

APP_NAME = "CS2Career"


def frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_root() -> Path:
    """Bundled read-only files: data json, web static."""
    if frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def save_root() -> Path:
    """Writable dir for career saves, custom logos, exported match results.

    Always next to the app (E: in this tree), never %LOCALAPPDATA% on C:.
    Frozen builds use <exe>/save; source uses sim/save.
    """
    if os.environ.get('CS2CAREER_SAVE_DIR'):
        base = Path(os.environ['CS2CAREER_SAVE_DIR']).resolve()
        base.mkdir(parents=True, exist_ok=True)
        return base
    if frozen():
        base = Path(sys.executable).resolve().parent / "save"
    else:
        base = Path(__file__).resolve().parents[1] / "save"
    base.mkdir(parents=True, exist_ok=True)
    return base


def data_file(name: str) -> Path:
    return resource_root() / "data" / name


def static_dir() -> Path:
    return resource_root() / "web" / "static"


def logo_dir() -> Path:
    """Drop <team-slug>.png here to override the generated crest."""
    d = save_root() / "logos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_file(name: str) -> Path:
    return save_root() / name


def vendor_root() -> Path:
    """Bundled third-party bits shipped with the sim (plugins, etc.)."""
    if frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "vendor"
    return Path(__file__).resolve().parents[1] / "vendor"


def extension_root() -> Path:
    """User-authored packs live beside the source tree or released executable."""
    if os.environ.get('CS2CAREER_EXTENSION_DIR'):
        root = Path(os.environ['CS2CAREER_EXTENSION_DIR']).resolve()
    elif frozen():
        root = Path(sys.executable).resolve().parent / "extensions"
    else:
        root = Path(__file__).resolve().parents[1] / "extensions"
    root.mkdir(parents=True, exist_ok=True)
    return root
