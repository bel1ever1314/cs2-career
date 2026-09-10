# coding=utf-8
"""Turn a CareerMatch JSON dump into the engine's per-map box score."""

from __future__ import annotations

import math

from ..engine.rating import career_rating, skill_tier
from .profiles import stable_player_id
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
    schema = 1_000_000_000 if int(result.get("schema_version") or 0) == 2 else 0
    return schema + (ct + t_score) * 100000 + kills * 10 + decided * 5 + finished + map_pen


def pick_better_result(*cands: dict | None) -> dict:
    rows = [c for c in cands if c]
    if not rows:
        return {"status": "none"}
    return max(rows, key=result_quality)


def result_usable(result: dict | None, session: dict) -> str:
    """Empty string if this dump is a normal end for the current map."""
    if not result or result.get("status") in (None, "none"):
        return "还没有读到比分"
    if int(result.get("schema_version") or 0) != 2:
        return "战绩仍是旧格式，CareerMatch 1.5 尚未加载"
    if session.get("nonce") and result.get("request_nonce") != session.get("nonce"):
        return "战绩 nonce 与当前比赛不匹配"
    if not result.get("complete"):
        return result.get("validation_error") or "十人战绩不完整，已阻止录入"
    players = result.get("players") or []
    if len(players) != 10 or len({p.get("player_id") for p in players}) != 10:
        return "战绩未包含 10 个唯一 player_id"
    if sum((p.get("team") or "").lower() == "ct" for p in players) != 5 \
            or sum((p.get("team") or "").lower() == "t" for p in players) != 5:
        return "战绩不是 CT/T 两边各 5 人"
    expected_ids = set(session.get("expected_player_ids") or [])
    actual_ids = {str(p.get("player_id") or "") for p in players}
    if expected_ids and actual_ids != expected_ids:
        return "战绩十人身份与当前比赛请求不一致"
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
    finished = result.get("status") == "finished"
    if not finished:
        return "比赛还没正常结束，等待 CareerMatch 确认终场；加时中不会提前录入。"
    if ct == t_score:
        return "比分是平局，不像正常结束"
    if max(ct, t_score) < 13:
        return "比分还没到 13，不像正常结束"
    rounds = ct + t_score
    for row in players:
        try:
            numbers = {key: float(row.get(key, 0)) for key in (
                'kills', 'deaths', 'assists', 'damage', 'survived_rounds',
                'opening_kills', 'opening_deaths', 'traded_deaths', 'kast')}
            if any(not math.isfinite(n) or n < 0 for n in numbers.values()):
                return "战绩包含无效或负数统计，已阻止录入"
            if numbers['deaths'] > rounds or numbers['kills'] > 5 * rounds \
                    or numbers['assists'] > 5 * rounds or numbers['kast'] > 1:
                return "个人战绩超过正式回合上限，可能发生身份错绑，已阻止录入"
            if 'survived_rounds' in row and numbers['survived_rounds'] + numbers['deaths'] != rounds:
                return "死亡与存活回合不守恒，已阻止录入"
        except (TypeError, ValueError):
            return "战绩统计不是有效数字，已阻止录入"
    if sum(int(p.get('kills', 0)) for p in players) > sum(int(p.get('deaths', 0)) for p in players):
        return "击杀/死亡不守恒，已阻止录入"
    bindings = result.get('identity_bindings')
    if bindings is not None and (len(bindings) != 10 or set(bindings.values()) != actual_ids):
        return "真人/Bot 槽位身份绑定不完整或重复，已阻止录入"
    return ""


def _pick_roster(name: str, roster: list[dict], human_name: str, is_bot: bool | None, player_id: str = "") -> dict | None:
    if player_id:
        # A schema-v2 ID is authoritative. A mismatched ID must never silently
        # fall back to a nickname or a mutable BotHider is_bot flag.
        return next((p for p in roster if (p.get("player_id") or stable_player_id(p["name"])) == player_id), None)
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


def _line(player: dict, row: dict, rounds: int) -> dict:
    kills, deaths, assists = (int(row.get(k) or 0) for k in ("kills", "deaths", "assists"))
    damage = int(row.get("damage") or 0)
    kast_raw = float(row.get("kast") or 0)
    kast_rounds = kast_raw * rounds if kast_raw <= 1.0 else kast_raw
    return {
        "player_id": player.get("player_id") or stable_player_id(player["name"]),
        "name": player["name"],
        "role": player.get("role") or "",
        "ability": player.get("ability", 70),
        "tier": skill_tier(player.get("ability", 70)).name,
        "k": int(kills),
        "d": int(deaths),
        "a": int(assists),
        "kpr": round(int(kills) / max(1, rounds), 3),
        "rating": career_rating(kills, deaths, assists, damage, kast_rounds, rounds),
        "damage": damage,
        "adr": round(damage / max(1, rounds), 2),
        "kast": round(kast_rounds / max(1, rounds), 4),
        "opening_kills": int(row.get("opening_kills") or 0),
        "opening_deaths": int(row.get("opening_deaths") or 0),
        "survived_rounds": int(row.get("survived_rounds") or 0),
        "traded_deaths": int(row.get("traded_deaths") or 0),
    }


def _side_lines(
    team: dict,
    side: str,
    raw: list[dict],
    human_name: str,
    rounds: int,
    role_by_id: dict | None = None,
) -> list[dict]:
    used: set[str] = set()
    out: list[dict] = []
    for row in raw:
        if (row.get("team") or "").lower() != side:
            continue
        player = _pick_roster(row.get("name") or "", team["players"], human_name, row.get("is_bot"), row.get("player_id") or "")
        if not player or player["name"] in used:
            continue
        if role_by_id is not None:
            player = dict(player, role=role_by_id.get(player.get('player_id') or stable_player_id(player['name']),''))
        used.add(player["name"])
        out.append(
            _line(player, row, rounds)
        )
    if len(out) != 5:
        raise ValueError(f"{team['name']} 只匹配到 {len(out)}/5 名选手，拒绝补 0")
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
                team_a, "ct" if team_a["name"] == ct_team else "t", raw, human_name, rounds, session.get('role_by_id',{})
            ),
            team_b["name"]: _side_lines(
                team_b, "ct" if team_b["name"] == ct_team else "t", raw, human_name, rounds, session.get('role_by_id',{})
            ),
        },
    }
