# coding=utf-8
"""Rare career incidents: travel drama, a quiet offer, and the fallout."""

from __future__ import annotations

FIX_BASE = 0.08
FIX_MIN = 0.015
FIX_MAX = 0.40
FIX_REFUSE = 0.55
FIX_ACCEPT = 0.07
CATCH_P = 0.25
COACH_P = 0.42
THROW_MULT = 0.40
PAYOUT = 12000
FAMOUS_ABILITY = 80


def famous_label(ability: float) -> str:
    return "CS2知名选手" if float(ability or 0) >= FAMOUS_ABILITY else "某名选手"


def coach_popup(event_name: str) -> dict:
    return {
        "id": "",
        "when": "major_coach",
        "kind": "plot",
        "title": "出发前",
        "text": (
            f"{event_name} 的机票已经出了。夜里教练发来一条很短的消息：家里有事，他不去了。\n"
            "没人追问细节。第二天集合少了一个会盯签表的人，队里每个人心里都空了一截。"
        ),
    }


def whisper_letter(player: str) -> dict:
    return {
        "title": "关于明晚",
        "from": "一个不愿留名的人",
        "body": (
            f"{player}：\n\n"
            "不必回得太快。有人觉得这场不必打满全力。\n"
            "事成之后，会有一笔不会出现在任何合同里的答谢。"
            "你只需让比分看起来像那么回事。\n\n"
            "回这封信就可以。沉默，也会被当成一种答案。"
        ),
    }


def whisper_popup() -> dict:
    return {
        "id": "",
        "when": "fix_offer",
        "kind": "plot",
        "title": "一封没有署名的信",
        "text": (
            "信写得很短。对方不谈胜负，只说这场不必打满全力，"
            "事成之后会有一笔不会写进合同的答谢。\n"
            "回绝，或者按他说的办。没有第三种体面的说法。"
        ),
        "choices": [
            {"id": "refuse", "label": "回绝"},
            {"id": "accept", "label": "按他说的办"},
        ],
    }


def probe_popup() -> dict:
    return {
        "id": "",
        "when": "fix_probe",
        "kind": "plot",
        "title": "CS2 赛事方",
        "text": "目前发现假赛痕迹，正在调查。",
    }


def ban_popup(player: str, ability: float) -> dict:
    label = famous_label(ability)
    return {
        "id": "",
        "when": "fix_ban",
        "kind": "plot",
        "title": "通报",
        "text": f"{label} {player} 或参与假赛，现已暂时禁赛。",
    }


def ban_letter(player: str) -> dict:
    return {
        "title": "关于你的参赛资格",
        "from": "CS2 赛事纪律委员会",
        "body": (
            f"{player}：\n\n"
            "调查已经结束。你的参赛资格被暂停，在此之前登记的席位一并作废。\n"
            "这份档案到此为止。若还想站上签表，只能另开一份新的生涯。"
        ),
    }
