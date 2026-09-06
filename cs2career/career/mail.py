# coding=utf-8
"""Inbox helpers and letter copy for invites, prize money, and sponsors."""

from __future__ import annotations

from datetime import datetime

INVITE_NEED = {"cct": 45, "qual": 40, "t2": 32, "t1": 16}
LEGEND_RANK = 8
MAJOR_VRS_RANK = 16
PLAYIN_RANK = 40

PLACE_ZH = {
    "champion": "冠军",
    "final": "亚军",
    "sf": "四强",
    "qf": "八强",
    "stage": "小组赛 / 瑞士轮",
}

REGION_ZH = {"EU": "欧洲", "AM": "美洲", "AS": "亚洲"}


def invite_tone(rank: int) -> str:
    if rank <= 8:
        return "top"
    if rank <= 20:
        return "mid"
    return "bottom"


def _dates(ev: dict) -> str:
    days = ev.get("dates") or []
    if not days:
        return ""
    a = days[0][5:].replace("-", "/")
    b = days[-1][5:].replace("-", "/")
    return a if a == b else f"{a} – {b}"


def _money(n: int) -> str:
    return f"${int(n):,}"


def invite_letter(ev: dict, team_name: str, rank: int, earned: bool = False) -> dict:
    short = ev.get("short") or ev.get("name") or "赛事"
    event = ev.get("name") or short
    prize = _money(ev.get("prize") or 0)
    region = REGION_ZH.get(ev.get("region"), ev.get("region") or "")
    dates = _dates(ev)
    if earned:
        return {
            "tone": "earned",
            "title": f"{short} 席位确认",
            "from": f"{event} 主办方",
            "body": (
                f"{team_name}：\n\n"
                f"预选赛的结果已经写进签表。{event} 的一个席位记在你们名下。\n"
                "这不是施舍出来的邀请，是你们自己打上来的。请确认出席。\n\n"
                f"赛程：{dates} · {region}\n"
                f"奖金池：{prize}\n\n"
                "请回复确认。缺席会把这个席位让给别人。"
            ),
        }
    tone = invite_tone(rank)
    if tone == "bottom":
        title = f"{short} 向你们伸出手"
        sender = f"{event} 组委会"
        body = (
            f"{team_name} 的各位：\n\n"
            "这封信不是客套。签表上还有空位，而我们想把其中一个留给你们。\n"
            "外面怎么看你们并不重要——能站上这张台子的队伍，本来就不该等人来定义。"
            "来吧。把这站当成一次被看见的机会，也当成一次把自己打进下一档的机会。\n\n"
            f"开赛：{dates} · {region}\n"
            f"奖金池：{prize}\n\n"
            "请回复是否出席。拒绝不会有人笑话你们；来了，才有人记得你们。"
        )
    elif tone == "mid":
        title = f"{short} 正式邀请"
        sender = f"{event} 竞赛部"
        body = (
            f"{team_name}：\n\n"
            "组委会看过近半年的积分和赛场表现，认为你们已经具备在这个级别稳定出场的实力。\n"
            "席位有限，签表不会等人。我们按职业赛事的标准接待你们，"
            "同样也按这个标准衡量你们。\n\n"
            f"开赛：{dates} · {region}\n"
            f"奖金池：{prize}\n\n"
            "请在开赛前确认是否接受邀请。"
        )
    else:
        title = f"{short} · 席位确认"
        sender = f"{event} 主办方"
        body = (
            f"{team_name}：\n\n"
            "作为目前赛场上的标杆之一，本站的签表需要你们的名字。\n"
            "观众在等，对手也在等。缺席会被记成一次让位，而不是一次休息。\n"
            "我们默认你们会来——但最终仍由你们决定。\n\n"
            f"赛程：{dates} · {region}\n"
            f"奖金池：{prize}\n\n"
            "请回复确认出席。"
        )
    return {"tone": tone, "title": title, "from": sender, "body": body}


def qualify_letter(qual_ev: dict, dest_ev: dict | None, team_name: str) -> dict:
    short = qual_ev.get("short") or qual_ev.get("name") or "附加赛"
    event = qual_ev.get("name") or short
    dest_name = (dest_ev or {}).get("name") or "正赛"
    dest_short = (dest_ev or {}).get("short") or dest_name
    dates = _dates(dest_ev) if dest_ev else ""
    return {
        "title": f"出线：{short} → {dest_short}",
        "from": f"{event} 组委会",
        "body": (
            f"{team_name}：\n\n"
            f"这不是邀请，这是结果。你们从 {event} 打出了 {dest_name} 的席位。\n"
            "VRS 没请到的队伍，也可以把自己写进大赛签表——前提是附加赛里真的赢下来。\n"
            "席位已经记在你们名下。确认函会另附一封。\n\n"
            f"正赛：{dest_name}\n"
            + (f"赛程：{dates}\n" if dates else "")
        ),
    }


def prize_letter(ev: dict, team_name: str, spot: str, amount: int) -> dict:
    short = ev.get("short") or ev.get("name") or "赛事"
    event = ev.get("name") or short
    place = PLACE_ZH.get(spot, spot)
    return {
        "title": f"{short} 赛事奖金待领取",
        "from": f"{event} 财务处",
        "body": (
            f"{team_name} 在 {event} 获得{place}。\n"
            f"应发奖金 {_money(amount)} 已就绪。领取后 88% 进俱乐部，12% 进你的口袋。"
        ),
    }


def sponsor_letter(month: str, rank: int, amount: int) -> dict:
    label = month
    try:
        dt = datetime.strptime(month + "-01", "%Y-%m-%d")
        label = f"{dt.year}年{dt.month}月"
    except ValueError:
        pass
    return {
        "title": f"{label} 赞助到账待领取",
        "from": "俱乐部商务",
        "body": (
            f"根据当前 VRS 世界第 {rank}，本月赞助 {_money(amount)} 已到账。\n"
            "赞助全部进俱乐部，用来发工资和维持吃住。你的个人收入来自工资和奖金分成。"
        ),
    }


def new_mail(kind: str, date: str, payload: dict, extra: dict | None = None) -> dict:
    row = {
        "id": "",
        "kind": kind,
        "date": date,
        "read": False,
        "title": payload.get("title") or "",
        "from": payload.get("from") or "",
        "body": payload.get("body") or "",
        "tone": payload.get("tone") or "",
        "status": "open",
    }
    if extra:
        row.update(extra)
    return row
