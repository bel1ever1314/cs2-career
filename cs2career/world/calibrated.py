# coding=utf-8
"""Read-only candidate pack and bounded, stateless position expressions.

Persistent player stats are BASE skills. Expressions are display/task estimates,
never training gains, Rating/ADR observations, or input to ``role_fit``. This
module deliberately does not load, migrate, or write a career save.
"""
from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
import json
import math
from types import MappingProxyType

from ..paths import data_file

AXES = ("firepower", "entrying", "trading", "opening", "clutching", "sniping", "utility")
POSITIONS = ("rifle", "entry", "awp", "lurk", "igl")
MODEL_VERSION = "full-roster-prototype-2-positions"
PACK_FILENAME = "calibrated_players_v1.json"
ROLE_WEIGHTS = MappingProxyType({
    "rifle": (28, 18, 22, 16, 12, 4, 0),
    "entry": (24, 24, 18, 20, 10, 4, 0),
    "awp": (24, 8, 12, 16, 12, 28, 0),
    "lurk": (24, 8, 26, 10, 28, 4, 0),
    "igl": (18, 10, 28, 10, 18, 4, 12),
    "support": (18, 8, 24, 8, 14, 4, 24),
})
ROLE_PRIORS = MappingProxyType({
    "rifle": (1, -1, 2, 0, 1, -6, 1),
    "entry": (2, 5, 1, 3, -2, -7, -1),
    "awp": (0, -3, -1, 3, 1, 8, -2),
    "lurk": (1, -3, 3, -1, 4, -6, 1),
    "igl": (-3, -2, 3, -2, 2, -6, 4),
    "support": (-2, -3, 4, -2, 1, -6, 5),
})


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _clip(value, lo=1.0, hi=100.0):
    return max(lo, min(hi, float(value)))


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _copy_data(value):
    """Return owned JSON-like data, including for recursively frozen metadata."""
    if isinstance(value, Mapping):
        return {key: _copy_data(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_copy_data(item) for item in value]
    return value


def _axes(stats):
    if not isinstance(stats, Mapping):
        raise ValueError("invalid_base_skills")
    values = {axis: stats.get(axis) for axis in AXES}
    if any(not _finite(value) or not 1 <= value <= 100 for value in values.values()):
        raise ValueError("invalid_base_skills")
    return values


def _role(role):
    if role not in ROLE_WEIGHTS:
        raise ValueError("unknown_position:" + str(role))
    return role


def _position_model(stats):
    model = stats.get("position_model") if isinstance(stats, Mapping) else None
    if not isinstance(model, Mapping) or model.get("schema_version") != 1:
        raise ValueError("missing_position_model")
    if model.get("model_version") != MODEL_VERSION:
        raise ValueError("unsupported_position_model")
    _role(model.get("reference_role"))
    for key, default, maximum in (("fit_cap", 3.0, 3.0),
                                  ("expression_weight", .3, 1.0),
                                  ("expression_cap", 3.0, 3.0)):
        value = model.get(key, default)
        if not _finite(value) or not 0 <= value <= maximum:
            raise ValueError("invalid_position_parameter:" + key)
    if not isinstance(model.get("headroom_softening", True), bool):
        raise ValueError("invalid_headroom_switch")
    return model


@lru_cache(maxsize=1)
def load_calibrated_pack():
    """Load a cached, recursively immutable bundled pure-data artifact."""
    with data_file(PACK_FILENAME).open("r", encoding="utf-8") as handle:
        pack = json.load(handle)
    if pack.get("schema_version") != 1 or pack.get("model_version") != MODEL_VERSION:
        raise ValueError("unsupported_calibration_pack")
    if tuple(pack.get("axes", ())) != AXES or not isinstance(pack.get("records"), list):
        raise ValueError("invalid_calibration_pack")
    ids, identities = set(), set()
    for row in pack["records"]:
        _axes(row.get("axes"))
        _role(row.get("reference_role"))
        if not _finite(row.get("overall")) or not 1 <= row["overall"] <= 100:
            raise ValueError("invalid_candidate_overall")
        kind = row.get("kind")
        if kind not in ("world_roster", "free_agent", "library"):
            raise ValueError("invalid_candidate_kind")
        if kind == "world_roster" and row.get("era") not in ("2024", "2025", "2026"):
            raise ValueError("invalid_world_era")
        if kind == "free_agent" and row.get("era") != "2026":
            raise ValueError("invalid_free_agent_era")
        if kind == "library" and row.get("era") != "library":
            raise ValueError("invalid_library_era")
        if not all(isinstance(row.get(key), str) and row[key] for key in ("id", "name", "team_id", "team")):
            raise ValueError("missing_candidate_identity")
        identity = (kind, row["era"], row["team_id"], row["name"])
        if row["id"] in ids or identity in identities:
            raise ValueError("duplicate_candidate_identity")
        ids.add(row["id"])
        identities.add(identity)
    return _freeze(pack)


@lru_cache(maxsize=1)
def _index():
    index = {}
    for row in load_calibrated_pack()["records"]:
        # IDs and display names are both exact team identities, never slugs
        # inferred from a caller's input and never fuzzy player aliases.
        teams = (row["team_id"], row["team"]) if row["kind"] == "world_roster" else (None,)
        for team in teams:
            key = (row["kind"], row["era"], team, row["name"])
            previous = index.get(key)
            if previous is not None and previous["id"] != row["id"]:
                raise ValueError("ambiguous_candidate_identity")
            index[key] = row
    return MappingProxyType(index)


def lookup(name, era="2026", team=None, kind="world_roster"):
    """Find one exact candidate; absence is None, not a cross-era fallback.

    World candidates require an explicit team ID or display name. Free agents
    exist only in 2026. The current library is reachable only by explicitly
    choosing ``kind='library'`` (or ``'current_library'``); its era is library.
    Returned records are immutable; ``stats_for_candidate`` returns owned stats.
    """
    if kind == "current_library":
        kind = "library"
    if kind not in ("world_roster", "free_agent", "library"):
        return None
    if not isinstance(name, str) or not name:
        return None
    era = str(era)
    if kind == "world_roster":
        if not isinstance(team, str) or not team:
            return None
    elif kind == "free_agent":
        if era != "2026":
            return None
        team = None
    else:
        # The kind is the explicit opt-in. This does not leak into world/free
        # lookups, even when an identically named library record exists.
        era, team = "library", None
    return _index().get((kind, era, team, name))


def weighted_score(stats, role):
    """Weighted current BASE skills on their native 1..100 scale."""
    axes = _axes(stats)
    weights = ROLE_WEIGHTS[_role(role)]
    return sum(axes[axis] * weight for axis, weight in zip(AXES, weights)) / sum(weights)


def model_marker(reference_role, source_id="attribute_draw"):
    """A single marker factory for candidate and new-policy blended players.

    A blended draft must use its receipt/source identity, not claim one real
    player's evidence. No BASE copy or mutable expression is kept in the marker.
    """
    _role(reference_role)
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("missing_position_source")
    return {
        "schema_version": 1, "model_version": MODEL_VERSION,
        "reference_role": reference_role, "fit_cap": 3.0,
        "expression_weight": .3, "expression_cap": 3.0,
        "headroom_softening": True,
        "seed_id": source_id, "provenance_id": source_id,
    }


def stats_for_candidate(name, role, era="2026", team=None, kind="world_roster"):
    """Owned BASE axes/overall with a frozen construction-time reference role.

    ``role`` is the caller's current assignment, not a new reference. The
    candidate's original reference is preserved even for counterfactual calls.
    ``reference_score`` is provenance; live growth is anchored by ability.py's
    role_reference_score, never by replacing the BASE axes with a preview.
    """
    role = _role(role)
    row = lookup(name, era, team, kind)
    if row is None:
        return None
    stats = _copy_data(row["axes"])
    stats["ability"] = round(row["overall"], 3)
    if _finite(row.get("command")):
        stats["command"] = row["command"]
    pack = load_calibrated_pack()
    stats["position_model"] = model_marker(row["reference_role"], row["id"])
    stats["position_model"]["reference_score"] = weighted_score(stats, row["reference_role"])
    stats["position_model"]["provenance_id"] = pack["pack_id"] + ":" + row["id"]
    stats["axis_quality"] = "estimated_not_observed"
    stats["calibration_provenance"] = {
        "id": row["id"], "pack_id": pack["pack_id"], "kind": row["kind"],
        "era": row["era"], "team_id": row["team_id"], "team": row["team"],
        "source_reference_role": row["reference_role"], "hltv_id": row.get("hltv_id"),
        "as_of": row["as_of"], "evidence": _copy_data(row["evidence"]),
        "uncertainty": _copy_data(row["uncertainty"]),
        "placeholder": row.get("placeholder", False),
    }
    return stats


def express_axes(stats, role):
    """Return only seven task-expression axes without mutating BASE or overall."""
    axes = _axes(stats)
    model = _position_model(stats)
    role = _role(role)
    reference = model["reference_role"]
    if role == reference:
        return dict(axes)
    cap = model.get("expression_cap", 3.0)
    weight = model.get("expression_weight", .3)
    out = {}
    for index, axis in enumerate(AXES):
        delta = (ROLE_PRIORS[role][index] - ROLE_PRIORS[reference][index]) * weight
        delta = _clip(delta, -cap, cap)
        if model.get("headroom_softening", True):
            room = 100 - axes[axis] if delta > 0 else axes[axis] - 1
            delta *= min(1.0, max(0.0, room) / (cap + 1))
        out[axis] = round(_clip(axes[axis] + delta), 3)
    return out


def role_fit(stats, role):
    """Bounded fit relative to the frozen reference, using current BASE only."""
    model = _position_model(stats)
    reference_score = weighted_score(stats, model["reference_role"])
    fit = weighted_score(stats, role) - reference_score
    cap = model.get("fit_cap", 3.0)
    return round(_clip(fit, -cap, cap), 3)
