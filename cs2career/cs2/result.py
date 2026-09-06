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


def result_usable(result: dict | None, session: dict) -> str:
    """Empty string if this dump is a normal end for the current map."""
    if not result or result.get("status") in (None, "none"):
        return "还没有读到比分"
    if result.get("status") != "finished":
        return "比赛还没正常结束，中途退出不会记入战绩"
    if not result.get("ended_at"):
        return "没有终场时间，不算正常结束"
    started = session.get("started_at") or ""
    if started and _ts(result.get("ended_at") or "") < _ts(started):
        return "这是上一场的残留战绩，请重开这张图"
    got = to_sim_map(result.get("map") or "", session.get("map") or "")
    want = session.get("map") or ""
    if want and got and got != want:
        return f"读到的是 {got}，当前这张是 {want}"
    ct = int(result.get("ct_score") or 0)
    t_score = int(result.get("t_score") or 0)
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
