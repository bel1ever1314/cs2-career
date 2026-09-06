# coding=utf-8
"""List career names that a stock Bot Improver database does not have.

Does not rewrite the mod's Low/Medium/High VPKs. Those three files are the
difficulty pack; we only print / export the extras so a match can append them
to a live copy.

  py -3 -m cs2career.cs2.seed_extras
"""

from __future__ import annotations

from pathlib import Path

from ..paths import data_file
from ..world import build_teams
from .launch import settings
from .profiles import (
    CAREER_MARK,
    career_people,
    classify_tier,
    native_db_text,
    profile_block,
    read_db,
)


def missing_people(db_text: str, people: list[dict]) -> list[dict]:
    from .profiles import db_names

    known = db_names(native_db_text(db_text))
    out: list[dict] = []
    seen: set[str] = set()
    for person in people:
        name = (person.get("name") or "").strip()
        key = name.lower()
        if not name or '"' in name or key in known or key in seen:
            continue
        seen.add(key)
        out.append(person)
    return out


def extras_text(people: list[dict]) -> str:
    lines = [
        f"//---------------------------------------------------------------\n",
        f"// {CAREER_MARK} 2.2\n",
        "// 90+ ProTop (巨星) · 70+ ProSteady (职业) · <70 RankRifler (Rank)\n",
    ]
    for person in people:
        lines.append(
            profile_block(
                person["name"],
                person.get("ability") or 70,
                person.get("role") or "",
                person.get("note") or "",
                bool(person.get("on_roster")),
            )
        )
    return "".join(lines)


def main() -> None:
    people = career_people(build_teams("2026", 2026))
    cfg = settings()
    mod = Path(cfg.get("mod_source_path") or "")
    vpk = mod / "overrides" / "High" / "botprofile.vpk"
    if not vpk.is_file():
        vpk = mod / "overrides" / "Medium" / "botprofile.vpk"
    if vpk.is_file():
        missing = missing_people(read_db(vpk), people)
        print(f"对照 {vpk}（已去掉生涯附录）")
    else:
        missing = missing_people("", people)
        print("找不到人机增强 VPK，按「原生库为空」导出全部生涯人名。")

    buckets = {"ProTop": [], "ProSteady": [], "RankRifler": []}
    for person in sorted(missing, key=lambda p: (-float(p.get("ability") or 0), p.get("name") or "")):
        buckets[classify_tier(person.get("ability") or 70)].append(person)

    print(f"原生没有、生涯有：{len(missing)} 人")
    print(f"  巨星 ProTop   ≥90  {len(buckets['ProTop'])}")
    print(f"  职业 ProSteady ≥70  {len(buckets['ProSteady'])}")
    print(f"  Rank RankRifler <70  {len(buckets['RankRifler'])}")
    for label, rows in buckets.items():
        if not rows:
            continue
        print(f"\n[{label}]")
        for person in rows:
            print(f"  {float(person.get('ability') or 0):5.1f}  {person['name']}")

    dest = data_file("bot_extras.txt")
    # Write every career name once. A stock Bot Improver already has most of
    # them; add_people skips duplicates, so a clean install still gets the rest.
    uniq: dict[str, dict] = {}
    for person in people:
        key = (person.get("name") or "").strip().lower()
        if key:
            uniq[key] = person
    ordered = sorted(uniq.values(), key=lambda p: (-float(p.get("ability") or 0), p.get("name") or ""))
    dest.write_text(extras_text(ordered), encoding="utf-8")
    print(f"\n已写入 {dest}（生涯 {len(ordered)} 人，开局只补原生没有的）")


if __name__ == "__main__":
    main()
