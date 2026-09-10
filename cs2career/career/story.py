# coding=utf-8
"""Story beats. All copy lives in data/stories.json so new plot can be dropped in
without touching Python.

A beat fires at most once per career. Filters are optional; omit a field to
match everyone.
"""

from __future__ import annotations

import json
from typing import Any

from ..paths import data_file

TRIGGERS = (
    "start",
    "first_lan",
    "first_final",
    "first_major",
    "first_title",
    "title",
    "first_mvp",
    "first_evp",
    "top20_eve",
)


def load_stories() -> list[dict]:
    raw = json.loads(data_file("stories.json").read_text(encoding="utf-8"))
    try:
        from ..content import get_registry

        for payload in get_registry().payloads("stories"):
            raw.setdefault("stories", []).extend(payload.get("stories") or [])
    except (OSError, TypeError, ValueError):
        pass
    out = []
    seen: set[str] = set()
    for row in raw.get("stories") or []:
        if not row.get("id") or row["id"] in seen or not row.get("when") or not (row.get("text") or "").strip():
            continue
        seen.add(row["id"])
        out.append(row)
    return out


STORIES = load_stories()


def reload_stories() -> list[dict]:
    global STORIES
    STORIES = load_stories()
    return STORIES


def _eq(want: Any, got: Any) -> bool:
    if want is None or want == "":
        return True
    if got is None:
        return False
    if isinstance(want, list):
        return any(_eq(item, got) for item in want)
    return str(want).casefold() == str(got).casefold()


def match(story: dict, ctx: dict) -> bool:
    if story.get("when") != ctx.get("when"):
        return False
    for key in ("era", "year", "player", "team", "role", "mode", "origin", "class", "type", "band"):
        if key in story and not _eq(story[key], ctx.get(key)):
            return False
    return True


def render(story: dict, ctx: dict) -> dict:
    mapping = {k: "" if v is None else str(v) for k, v in ctx.items()}
    try:
        text = (story.get("text") or "").format_map(mapping)
        title = (story.get("title") or "").format_map(mapping)
    except (KeyError, ValueError):
        text = story.get("text") or ""
        title = story.get("title") or ""
    return {
        "id": story["id"],
        "when": story["when"],
        "title": title,
        "text": text,
    }


def collect(ctx: dict, seen: set[str], queued: set[str]) -> list[dict]:
    hits = []
    for story in STORIES:
        if story["id"] in seen or story["id"] in queued:
            continue
        if match(story, ctx):
            hits.append(render(story, ctx))
    return hits


def pick(ctx: dict, when: str) -> dict | None:
    """One matching beat. More filters win; same specificity is stable by event."""
    ctx = dict(ctx)
    ctx["when"] = when
    ranked: list[tuple[int, dict]] = []
    for story in STORIES:
        if not (story.get("text") or "").strip():
            continue
        if not match(story, ctx):
            continue
        spec = sum(
            1
            for key in ("era", "year", "player", "team", "role", "mode", "origin", "class", "type", "band")
            if key in story
        )
        ranked.append((spec, story))
    if not ranked:
        return None
    best = max(spec for spec, _ in ranked)
    pool = [story for spec, story in ranked if spec == best]
    key = str(ctx.get("event_id") or ctx.get("event") or "")
    return render(pool[sum(ord(ch) for ch in key) % len(pool)], ctx)
