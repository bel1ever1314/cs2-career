"""Shared palette and typography for the career desk. No gameplay rules here."""

BG = "#101215"
SIDEBAR = "#15171a"
PANEL = "#1b1e22"
RAISED = "#24282d"
LINE = "#30353c"
TEXT = "#f2f3f5"
MUTED = "#a0a5ad"
DIM = "#737b86"
ACCENT = "#ff854a"
GREEN = "#77d6aa"
BLUE = "#87adff"
RED = "#f28d94"
FONT = "Microsoft YaHei UI"
DISPLAY = "Bahnschrift"

REGIONS = {"AS": "亚洲", "EU": "欧洲", "AM": "美洲"}
STATUS = {"upcoming": "未开始", "active": "进行中", "live": "进行中", "done": "已结束",
          "open": "待回复", "accepted": "已接受", "declined": "已婉拒", "expired": "已过期", "closed": "已处理"}


def money(value):
    return f"${int(value or 0):,}"


def signed_money(value):
    return ("+" if (value or 0) >= 0 else "−") + money(abs(value or 0))
