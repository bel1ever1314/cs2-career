# coding=utf-8
"""Team payroll vs personal pocket: salaries, living costs, prize splits, loans."""

from __future__ import annotations

PLAYER_PRIZE_SHARE = 0.12
MAJOR_APPEARANCE = 200000

CLUB_LOAN_RATE = 0.02
BANK_LOAN_RATE = 0.03
CLUB_LOAN_FRACTION = 0.40
BANK_CAP_TOP = 180000
BANK_CAP_FLOOR = 40000
LOAN_MISS_LIMIT = 3


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


def months_after(start: str, end: str) -> list[str]:
    """YYYY-MM months strictly after start, through end inclusive."""
    if not end:
        return []
    if not start:
        return [end]
    if start == end:
        return []
    try:
        sy, sm = int(start[:4]), int(start[5:7])
        ey, em = int(end[:4]), int(end[5:7])
    except (TypeError, ValueError):
        return [end]
    out: list[str] = []
    y, m = sy, sm
    while (y, m) < (ey, em):
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
        out.append(f"{y:04d}-{m:02d}")
    return out


def interest_due(principal: int, rate: float) -> int:
    principal = int(principal or 0)
    if principal <= 0:
        return 0
    return max(1, int(round(principal * float(rate or 0))))


def club_borrow_cap(cash: int, burn_total: int) -> int:
    cash = max(0, int(cash or 0))
    burn = max(0, int(burn_total or 0))
    return max(0, min(int(cash * CLUB_LOAN_FRACTION), cash - burn))


def bank_borrow_cap(rank: int) -> int:
    r = max(1, min(50, int(rank or 45)))
    span = BANK_CAP_TOP - BANK_CAP_FLOOR
    return int(round(BANK_CAP_TOP - (r - 1) * (span / 49.0)))


def loan_kind_for_mode(mode: str) -> str:
    return "bank" if mode == "create" else "club"


def rate_for_kind(kind: str) -> float:
    return BANK_LOAN_RATE if kind == "bank" else CLUB_LOAN_RATE
