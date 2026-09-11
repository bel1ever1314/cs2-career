"""Read-only score reveal contract. Never simulate or settle from this module.

The result is already persisted before it reaches the viewer. Its round path
comes exclusively from saved round_end events; missing history isn't invented.
"""
from __future__ import annotations


def reveal_series(match: dict, start: int = 0) -> dict:
    teams = [match["team_a"], match["team_b"]]
    initial = [0, 0]
    maps = match.get("maps") or []
    for mp in maps[:start]:
        if mp.get("winner") in teams:
            initial[teams.index(mp["winner"])] += 1
    out = []
    for index, mp in enumerate(maps[start:], start):
        rounds = []
        valid = True
        for event in mp.get("events") or []:
            if event.get("type") != "round_end":
                continue
            winner = event.get("winner")
            side = winner if winner in ("a", "b") else "a" if winner == teams[0] else "b" if winner == teams[1] else None
            if side is None or event.get("round") != len(rounds) + 1:
                valid = False
            rounds.append(side)
        totals = [rounds.count("a"), rounds.count("b")]
        score = str(mp.get("score") or "")
        valid = valid and bool(rounds) and score.replace(":", "-").replace(" ", "") == f"{totals[0]}-{totals[1]}"
        out.append({"index": index, "map": mp.get("map"), "score": score,
                    "winner": mp.get("winner"), "rounds": rounds if valid else [],
                    "events_available": valid})
    return {"match_id": match["id"], "teams": teams, "best_of": match.get("best_of", 3),
            "initial": initial, "maps": out}
