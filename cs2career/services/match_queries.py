"""Read-only fixture queries shared by devices and match coordinators."""

def player_matches(state):
    """Read fixtures without your_series(), which opens a veto and mutates state."""
    s = state.season
    return sorted(((ev, match) for ev in s.events if ev.get("status") == "live"
                   for match in ev.get("matches", [])
                   if not match.get("played") and s.is_yours(match)),
                  key=lambda pair: (pair[1]["date"], pair[1]["id"]))


def due_player_match(state):
    return next(((ev, m) for ev, m in player_matches(state)
                 if m["date"] <= state.season.date or m.get("cs2_session") or m.get('career3d_rts')), None)
