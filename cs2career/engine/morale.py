# coding=utf-8
"""Team mentality: rest, travel, streaks. It nudges results, it does not decide them."""

from __future__ import annotations

from .rating import clamp

START_MENTALITY = {"t1_top": 78, "t1": 75, "t1_bottom": 72, "t2": 68, "t3": 64, "t4": 60}


def mentality_mult(value: float) -> float:
    # 40 -> 0.98, 70 -> 1.02, 90 -> 1.05
    return 0.92 + 0.14 * (clamp(value, 0.0, 100.0) / 100.0)


def rest_delta(days: int) -> tuple[int, str]:
    if days <= 5:
        return -3, "packed"
    if days <= 10:
        return 4, "short_rest"
    if days <= 20:
        return 7, "good_rest"
    if days <= 28:
        return 2, "long_rest"
    return -6, "rusty"


def travel_delta(from_region: str, to_region: str) -> tuple[int, str]:
    if from_region == to_region:
        return 0, "local"
    if {from_region, to_region} == {"AS", "AM"}:
        return -12, "long_haul"
    return -8, "travel"


def init_mentality(teams: list[dict]) -> None:
    for t in teams:
        t["mentality"] = START_MENTALITY.get(t["tier"], 65)
        t["series_streak"] = 0
        t["loss_streak"] = 0
        t["last_region"] = t["region"]
        t["mentality_log"] = []


def shift_mentality(team: dict, delta: float) -> float:
    team["mentality"] = round(clamp(team.get("mentality", 65) + delta, 35.0, 100.0), 1)
    return team["mentality"]


def scrim_mentality_gain(mentality: float) -> float:
    """Daily training bump. Strong when the room is cold, almost nothing when hot.

    Mentality only nudges map odds (~3% from 70 to 94), so this cannot replace
    match results. Training also cannot push a team past 94.
    """
    current = float(mentality or 0)
    if current >= 94:
        return 0.0
    gap = 94.0 - current
    gain = 3.8 * (gap / 44.0) ** 1.4
    return round(max(0.0, min(3.8, gain)), 2)


def after_series(team_a: dict, team_b: dict, series: dict) -> None:
    winner = team_a if series["winner"] == team_a["name"] else team_b
    loser = team_b if winner is team_a else team_a
    gap = abs(team_a["world_rank"] - team_b["world_rank"])
    underdog = winner["world_rank"] > loser["world_rank"]

    winner["series_streak"] = winner.get("series_streak", 0) + 1
    winner["loss_streak"] = 0
    win_d = 4.0
    if underdog:
        win_d += 2.0
    if winner["series_streak"] <= 3:
        win_d += 2.0
    elif winner["series_streak"] >= 6:
        win_d -= 5.0
    shift_mentality(winner, win_d)
    if winner["series_streak"] >= 6:
        winner["mentality"] = round(winner["mentality"] * 0.90 + 72.0 * 0.10, 1)

    loser["series_streak"] = 0
    loser["loss_streak"] = loser.get("loss_streak", 0) + 1
    lose_d = -3.5
    if not underdog and gap >= 5:
        lose_d -= 2.0
    if series.get("stage") == "GF":
        lose_d -= 1.5
    if loser["loss_streak"] >= 3:
        lose_d -= 2.0
    shift_mentality(loser, lose_d)


def after_event(teams: list[dict], event: dict) -> None:
    champ_name = event.get("champion")
    early_out = set()
    for m in event.get("matches", []):
        if m.get("stage") in ("QF", "R16", "SW"):
            loser = m.get("team_a") if m.get("winner") != m.get("team_a") else m.get("team_b")
            if loser and loser != "BYE":
                early_out.add(loser)
    for t in teams:
        if t["name"] == champ_name:
            shift_mentality(t, 6.0)
        elif t["name"] in early_out and t["tier"] in ("t1_top", "t1"):
            shift_mentality(t, -4.0)
        t.setdefault("mentality_log", []).append(
            {
                "event": event.get("event") or event.get("id"),
                "when": "leave",
                "after": t.get("mentality"),
                "streak": t.get("series_streak", 0),
                "champion": t["name"] == champ_name,
            }
        )
