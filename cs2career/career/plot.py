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
FLEE_P = 0.10

ENDINGS = {
    "legend": {
        "id": "legend",
        "title": "传奇满载而归",
        "text": (
            "喧嚣终有落幕之日，你收起陪伴多年的鼠标。一座座奖杯静静陈列在荣誉墙，"
            "每一道划痕都镌刻着属于你的传奇。你在无数大赛上演过力挽狂澜的对局，"
            "留下无数令人反复回味的高光时刻。赛场的呐喊渐渐远去，但你的名字永远留在 CS2 的史册之中。"
            "不必再有胜负的枷锁，这段辉煌的征程，已然圆满。"
        ),
    },
    "veteran": {
        "id": "veteran",
        "title": "老将淡然谢幕",
        "text": (
            "岁月磨平了锋芒，反应不再如同巅峰时期锐利。你没有拿下足以封神的至高桂冠，"
            "却长年坚守赛场，一次又一次带领队伍向前冲锋。没有惊天动地的传奇，只有日复一日的坚持。"
            "当灯光缓缓熄灭，你坦然告别舞台。你拼尽了全部热爱，纵使留有遗憾，职业生涯依旧值得所有人尊敬。"
        ),
    },
    "plain": {
        "id": "plain",
        "title": "平凡落幕，无名离场",
        "text": (
            "一路走来，你穿梭在大大小小的联赛与预选赛之中，见过场馆沸腾的人潮，"
            "也经历过无人关注的冷清赛场。你努力追赶顶尖选手的脚步，却始终没能站上最高领奖台。"
            "没有载入史册的名场面，没有琳琅满目的奖杯，但你为梦想全力以赴。"
            "当选择退役，过往每一场拼搏都真实存在，这段职业旅程，无怨无悔。"
        ),
    },
    "flee": {
        "id": "flee",
        "title": "背负巨额债务，狼狈逃离赛场",
        "text": (
            "巨额债务如同枷锁死死缠住了你。为偿还欠款，你早早耗尽竞技状态，成绩一路断崖式下滑。"
            "赛场不再是追逐梦想的舞台，只剩沉重的生存压力。最终你仓皇宣布退役，匆匆逃离职业圈。"
            "追逐名利带来的沉重负债，碾碎了最初的电竞理想，曾经的热爱彻底被现实吞噬，只留下一地狼狈与叹息。"
        ),
    },
    "fix": {
        "id": "fix",
        "title": "假赛丑闻曝光，身败名裂",
        "text": (
            "操纵对局、收受利益的黑幕公之于众，丑闻席卷整个电竞圈。"
            "所有曾经的成绩蒙上无法抹去的污点，粉丝失望离去，战队将你除名。"
            "你亲手玷污了公平竞技的底线，背叛赛场、辜负信任。"
            "再多华丽的数据也无法掩盖卑劣的行径，职业生涯在唾骂声中惨淡终结，"
            "最终被 CS 的历史永久钉在耻辱之上。"
        ),
    },
}


def honour_ending(honours: dict, context: dict | None = None) -> dict:
    # Ordinary voluntary retirement copy now lives in career_retirement.json.
    # ENDINGS above remains compatible with older explicit incident endings.
    from .retirement import choose
    return choose(honours,context)


def birthday_popup(name: str) -> dict:
    return {
        "id": "",
        "when": "teammate_birthday",
        "kind": "plot",
        "title": f"{name} 的生日",
        "text": f"今天是 {name} 的生日。队里等你一句话。",
        "choices": [
            {"id": "wish", "label": "祝贺生日"},
            {"id": "train", "label": "独自训练"},
        ],
        "player": name,
    }


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
    ending = ENDINGS["fix"]
    return {
        "id": "",
        "when": "fix_ban",
        "kind": "plot",
        "title": ending["title"],
        "text": ending["text"],
        "ending": "fix",
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


def loan_default_popup() -> dict:
    return {
        "id": "",
        "when": "loan_default",
        "kind": "plot",
        "title": "最后通牒",
        "text": (
            "财务把账本摊在桌上。利息已经连续三个月没有进账。\n"
            "俱乐部可以按合同把你除名，个人名下的钱和饰品一并清掉。\n"
            "另一条路没有人愿意写进会议纪要：收拾东西走。成不成，看你自己。"
        ),
        "choices": [
            {"id": "refuse", "label": "承担后果"},
            {"id": "flee", "label": "带着东西走"},
        ],
    }


def loan_flee_news(player: str, ability: float) -> dict:
    ending = ENDINGS["flee"]
    return {
        "id": "",
        "when": "loan_flee_ban",
        "kind": "plot",
        "title": ending["title"],
        "text": ending["text"],
        "ending": "flee",
    }


def loan_flee_ban_letter(player: str) -> dict:
    return {
        "title": "永久禁赛通知",
        "from": "CS2 赛事纪律委员会",
        "body": (
            f"{player}：\n\n"
            "经查，你在俱乐部债务尚未结清时转移个人财产，并拒绝配合财务清算。\n"
            "现决定对你处以永久禁赛。已登记的赛事席位全部作废。\n"
            "这份档案到此为止。若还想站上签表，只能另开一份新的生涯。"
        ),
    }


def loan_release_letter(player: str, team: str, wiped: bool) -> dict:
    if wiped:
        body = (
            f"{player}：\n\n"
            f"{team} 已按合同解除与你的关系。个人账户与饰品库存已清零。\n"
            "你现在是自由身。若有俱乐部愿意给你一份位置，信会送到这只邮箱。"
        )
    else:
        body = (
            f"{player}：\n\n"
            f"你已经离开 {team}。目前没有俱乐部合同。\n"
            "自由市场的报价会送到这只邮箱，接下其中一封才能重新上场。"
        )
    return {
        "title": "你目前是自由身",
        "from": "球员事务",
        "body": body,
    }
