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
        "feature": row.get('feature') or (feature_report(row, year) if row['rank'] <= 3 else None),
    }


def feature_report(row: dict, year: int) -> dict:
    """Frozen, evidence-led editorial. No invented matches, quotes or future wins."""
    rank=int(row['rank']); name=row['player']; team=row.get('team') or '赛季记录中的队伍'
    titles=int(row.get('titles') or 0); majors=int(row.get('majors') or 0)
    angles={1:'把这一年写成自己的名字',2:'不是冠军的注脚',3:'领奖台上的第三种答案'}
    leads={1:'第一名并不是某一场精彩集锦的结论。它要求一个名字在赛季结束之后，仍能经受对手强度、个人荣誉与比赛样本的共同检验。',
           2:'第二名很容易被简化成一句“还差一步”。但把一整个赛季缩成与榜首的距离，会漏掉这位选手真正做成的事。',
           3:'在二十个名字中站到第三位，需要的不只是偶尔闪光。铜色名次记录的是一段已经兑现的竞争力，而不是对未来的预支。'}
    def metric(value): return '缺少记录' if value is None else f'{float(value):.2f}'
    sample=f"本榜统计其对Top30对手的 {int(row.get('maps') or 0)} 张地图，Rating 为 {metric(row.get('rating'))}。这里的样本范围不是全年所有比赛，不能把它误读成对任意级别对手的平均表现。"
    strong=f"对Top10的 Rating 为 {metric(row.get('rating_top10'))}（{int(row.get('maps_top10') or 0)} 图），对Top20为 {metric(row.get('rating_top20'))}（{int(row.get('maps_top20') or 0)} 图）。小样本的亮眼数字值得关注，也需要保留判断余地。"
    honours=f"存档记录了 {titles} 次赛事冠军，其中 {majors} 次 Major；个人收获 {int(row.get('mvp') or 0)} 次 MVP 和 {int(row.get('evp') or 0)} 次 EVP。"
    honours+=('没有团队冠军并不等于没有个人价值；这份排名更多需要由个人表现与荣誉支撑。' if not titles else '团队胜利给这段赛季提供了背景，但个人评选并不是把全队的奖杯平均分配。')
    endings={1:'守住第一，比得到第一更难。下一年的排名仍从新的比赛开始；今年的荣誉会留下，却不会替他拿下下一张地图。',
             2:'下一年的问题，不只是能否超过榜首，而是能否继续把高水平表现带到重要对手面前。第二名是一份完成的成绩单，不是一张失败证明。',
             3:'更高的位置当然值得争取，但不必为了谈论未来而抹去现在。这个赛季，他已经让自己的名字留在前三之中。'}
    return {'title':f'{name}：{angles.get(rank,"这一年的答案")}',
            'subtitle':f'{year} 年度人物专栏 · Top {rank} · {team}',
            'sections':[{'heading':'这一年的位置','text':f'{name} 位列 {year} 年度第 {rank}。'+leads[rank]},
                        {'heading':'把表现放回样本','text':sample+'\n\n'+strong},
                        {'heading':'荣誉与下一页','text':honours+'\n\n'+endings[rank]}]}


def history_features(history: dict) -> dict:
    """Read-only enrichment for old final lists; never change ranks/statistics."""
    return {year:[dict(row,feature=row.get('feature') or feature_report(row,int(year)))
                   if 1<=int(row.get('rank') or 0)<=3 else dict(row) for row in rows]
            for year,rows in history.items()}
