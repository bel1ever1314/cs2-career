# coding=utf-8
"""Team payroll vs personal pocket: salaries, living costs, prize splits."""

from __future__ import annotations

PLAYER_PRIZE_SHARE = 0.12
MAJOR_APPEARANCE = 200000


def monthly_salary(ability: float) -> int:
    return int(600 + float(ability or 70) * 85)


def monthly_living(rank: int) -> int:
    if rank <= 8:
        return 20000
    if rank <= 16:
        return 14000
    if rank <= 30:
        return 9000
    return 5500


def payroll(players: list[dict]) -> list[dict]:
    rows = []
    for p in players or []:
        pay = monthly_salary(p.get("ability") or 70)
        rows.append({"name": p.get("name") or "", "ability": p.get("ability") or 70, "pay": pay})
    return rows


def month_burn(players: list[dict], rank: int) -> dict:
    wages = payroll(players)
    salaries = sum(r["pay"] for r in wages)
    living = monthly_living(rank)
    return {"wages": wages, "salaries": salaries, "living": living, "total": salaries + living}


def split_prize(amount: int) -> tuple[int, int]:
    personal = int(amount * PLAYER_PRIZE_SHARE)
    return amount - personal, personal
