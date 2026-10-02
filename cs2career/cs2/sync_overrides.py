# coding=utf-8
"""Sync player_stats.json into game/csgo/overrides (the VPK CS2 actually loads).

  py -3 -m cs2career.cs2.sync_overrides
"""

from __future__ import annotations

from .launch import sync_live_profiles


def main() -> None:
    out = sync_live_profiles()
    print(out["msg"])


if __name__ == "__main__":
    main()
