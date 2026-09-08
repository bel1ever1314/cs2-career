# coding=utf-8
"""Turn a CareerMatch JSON dump into the engine's per-map box score."""

from __future__ import annotations

from ..engine.rating import kda_rating, skill_tier
from ..world import MAPS

CS2_OF = {name: f"de_{name}" for name in MAPS}


def to_cs2_map(name: str) -> str:
    raw = (name or "").strip().lower()
    if raw.startswith("de_"):
        return raw
    return CS2_OF.get(raw, f"de_{raw}" if raw else "de_dust2")


def to_sim_map(name: str, fallback: str = "") -> str:
    raw = (name or "").strip().lower().replace("de_", "")
    if raw in MAPS:
        return raw
    return fallback


def _ts(value: str) -> str:
    return (value or "").replace("Z", "").split(".")[0]


def _norm_name(name: str) -> str:
    text = (name or "").strip()
    if text.upper().startswith("BOT "):
        text = text[4:].strip()
    return text


def result_quality(result: dict | None) -> int:
    """Higher is a more complete dump. 0:0 empty maps lose to a real score."""
    if not result or result.get("status") in (None, "none"):
        return -1
    raw_map = (result.get("map") or "").strip().lower()
    if raw_map in ("", "<empty>", "empty"):
        map_pen = -1000
    else:
        map_pen = 0
    ct = int(result.get("ct_score") or 0)
    t_score = int(result.get("t_score") or 0)
    kills = sum(int(p.get("kills") or 0) for p in (result.get("players") or []))
    decided = 1 if ct != t_score and max(ct, t_score) >= 13 else 0
    finished = 1 if result.get("status") == "finished" else 0
    return (ct + t_score) * 100000 + kills * 10 + decided * 5 + finished + map_pen


def pick_better_result(*cands: dict | None) -> dict:
    rows = [c for c in cands if c]
    if not rows:
        return {"status": "none"}
    return max(rows, key=result_quality)


def result_usable(result: dict | None, session: dict) -> str:
    """Empty string if this dump is a normal end for the current map."""
    if not result or result.get("status") in (None, "none"):
        return "还没有读到比分"
    started = session.get("started_at") or ""
    ended = _ts(result.get("ended_at") or "")
    if started and ended and ended < _ts(started):
        return "这是上一场的残留战绩，请重开这张图"
    raw_map = (result.get("map") or "").strip()
    got = to_sim_map(raw_map, session.get("map") or "")
    want = session.get("map") or ""
    empty_map = raw_map.lower() in ("", "<empty>", "empty")
    if want and got and got != want and not empty_map:
        return f"读到的是 {got}，当前这张是 {want}"
    ct = int(result.get("ct_score") or 0)
    t_score = int(result.get("t_score") or 0)
    decided = ct != t_score and max(ct, t_score) >= 13
    finished = result.get("status") == "finished" or decided
    if not finished:
        return "比赛还没正常结束。打到 13 分就会自动记；如果刚退出，等一两秒再点录入。"
    if ct == t_score:
        return "比分是平局，不像正常结束"
    if max(ct, t_score) < 13:
        return "比分还没到 13，不像正常结束"
    return ""


def _pick_roster(name: str, roster: list[dict], human_name: str, is_bot: bool | None) -> dict | None:
    if is_bot is False and human_name:
        hit = next((p for p in roster if p["name"] == human_name), None)
        if hit:
            return hit
    want = _norm_name(name).lower()
    if not want:
        return None
    for p in roster:
        if p["name"].lower() == want:
            return p
    for p in roster:
        if p["name"].lower().startswith(want) or want.startswith(p["name"].lower()):
            return p
    return None


def _line(player: dict, kills: int, deaths: int, assists: int, rounds: int, damage: int = 0) -> dict:
    return {
        "name": player["name"],
        "ability": player.get("ability", 70),
        "tier": skill_tier(player.get("ability", 70)).name,
        "k": int(kills),
        "d": int(deaths),
        "a": int(assists),
        "kpr": round(int(kills) / max(1, rounds), 3),
        "rating": kda_rating(int(kills), int(deaths), int(assists), rounds),
        "damage": int(damage or 0),
    }


def _side_lines(
    team: dict,
    side: str,
    raw: list[dict],
    human_name: str,
    rounds: int,
) -> list[dict]:
    used: set[str] = set()
    out: list[dict] = []
    for row in raw:
        if (row.get("team") or "").lower() != side:
            continue
        player = _pick_roster(row.get("name") or "", team["players"], human_name, row.get("is_bot"))
        if not player or player["name"] in used:
            continue
        used.add(player["name"])
        out.append(
            _line(
                player,
                row.get("kills") or 0,
                row.get("deaths") or 0,
                row.get("assists") or 0,
                rounds,
                row.get("damage") or 0,
            )
        )
    for player in team["players"]:
        if player["name"] not in used:
            out.append(_line(player, 0, 0, 0, rounds))
    out.sort(key=lambda x: (-x["rating"], -x["k"]))
    return out


def cs2_to_map(result: dict, session: dict, team_a: dict, team_b: dict, human_name: str) -> dict:
    """Build one engine map from a finished CareerMatch dump."""
    side = "t" if session.get("side") == "t" else "ct"
    my_name = session.get("my_team") or team_a["name"]
    opp_name = session.get("opp") or team_b["name"]
    if side == "ct":
        ct_team, t_team = my_name, opp_name
    else:
        ct_team, t_team = opp_name, my_name

    ct = int(result.get("ct_score") or 0)
    t_score = int(result.get("t_score") or 0)
    rounds = max(1, ct + t_score)
    winner = ct_team if ct > t_score else t_team
    if team_a["name"] == ct_team:
        score = f"{ct}-{t_score}"
    else:
        score = f"{t_score}-{ct}"

    raw = list(result.get("players") or [])
    return {
        "map": session.get("map") or to_sim_map(result.get("map") or "", "dust2"),
        "score": score,
        "rounds": rounds,
        "winner": winner,
        "source": "cs2",
        "players": {
            team_a["name"]: _side_lines(
                team_a, "ct" if team_a["name"] == ct_team else "t", raw, human_name, rounds
            ),
            team_b["name"]: _side_lines(
                team_b, "ct" if team_b["name"] == ct_team else "t", raw, human_name, rounds
            ),
        },
    }
