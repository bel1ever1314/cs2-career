# coding=utf-8
"""Year-end Top 20 titles and short blurbs. Special lines are locked to era picks."""

from __future__ import annotations

from zlib import crc32

SPECIAL_TITLE = {
    ("2024", "donk"): "独步红尘笑古今",
    ("2025", "ZywOo"): "人间遇我自生春",
}

NIKO_MAJOR = "十年筹尽英雄泪，一朝问鼎轩辕巅"

VERSES = (
    "一剑霜寒十四州",
    "纵马关山不问年",
    "星河倒泻入刀芒",
    "风起青萍未肯休",
    "醉里挑灯看旧剑",
    "长河落日满关山",
    "匣中夜有龙吟起",
    "潮打空城寂寞回",
    "铁衣犹带旧时霜",
    "大鹏一日同风起",
    "黄沙百战穿金甲",
    "万里悲秋常作客",
    "欲上青天揽明月",
    "楼船夜雪瓜洲渡",
    "黑云压城城欲摧",
    "青山遮不住东流",
    "十年磨剑未曾试",
    "大风起兮云飞扬",
    "江山如画一时新",
    "少年横槊赋新诗",
)

LINE = {
    1: "这一年的名字，最后写在最上面。",
    2: "只差一步，却已让所有人回头。",
    3: "铜冠压鬓，锋芒未收。",
}


def verse_title(era: str, player: str, majors: int, rank: int) -> str:
    if era == "2026" and player == "NiKo" and majors:
        return NIKO_MAJOR
    locked = SPECIAL_TITLE.get((str(era), player))
    if locked:
        return locked
    seed = crc32(f"{era}|{player}|{rank}".encode("utf-8"))
    return VERSES[(seed + rank) % len(VERSES)]


def verse_lines(row: dict, year: int, era: str) -> list[str]:
    titles = int(row.get("titles") or 0)
    majors = int(row.get("majors") or 0)
    trophy = f"冠军 {titles}"
    if majors:
        trophy += f"（Major {majors}）"
    return [
        f"{year} 年 · {row.get('team') or '—'}",
        f"Rating {float(row.get('rating') or 0):.2f} · {int(row.get('maps') or 0)} 图",
        f"{trophy} · MVP {int(row.get('mvp') or 0)} · EVP {int(row.get('evp') or 0)}",
        LINE.get(int(row.get("rank") or 0), "这一年的脚印，都写在这份名单上。"),
    ]


def decorate(row: dict, year: int, era: str) -> dict:
    majors = int(row.get("majors") or 0)
    return {
        "rank": row["rank"],
        "player": row["player"],
        "team": row.get("team") or "",
        "rating": row.get("rating"),
        "maps": row.get("maps") or 0,
        "mvp": row.get("mvp") or 0,
        "evp": row.get("evp") or 0,
        "titles": row.get("titles") or 0,
        "majors": majors,
        "verse": verse_title(era, row["player"], majors, row["rank"]),
        "lines": verse_lines(row, year, era),
    }
