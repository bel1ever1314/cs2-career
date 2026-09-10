# coding=utf-8
"""Pure match engine public API: simulation, morale updates, and ratings.

Keep this package independent from HTTP, save files, and the optional CS2 bridge
so its numerical rules can be exercised without launching the application.
"""

from .match import play_map, play_series, series_ratings, update_player_forms, veto_maps
from .morale import (
    after_event,
    after_series,
    init_mentality,
    rest_delta,
    shift_mentality,
    travel_delta,
)
from .rating import kda_rating, skill_tier

__all__ = [
    "after_event",
    "after_series",
    "init_mentality",
    "kda_rating",
    "play_map",
    "play_series",
    "rest_delta",
    "series_ratings",
    "shift_mentality",
    "skill_tier",
    "travel_delta",
    "update_player_forms",
    "veto_maps",
]
