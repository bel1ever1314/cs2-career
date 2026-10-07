# coding=utf-8
"""Build a compact immutable-runtime candidate pack from the isolated lab.

Only the explicit output artifact is written. Source JSON, lab outputs and game
saves are never imported or modified. Before writing, every candidate's BASE
and all five expressions/fits are checked against a freshly built lab report.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LAB = Path("E:/CS2CareerTools/FullRosterCalibrationLab-20261002")
DEFAULT_OUTPUT = ROOT / "cs2career" / "data" / "calibrated_players_v1.json"


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _module(path, name):
    # Loading source this way does not create bytecode in the read-only lab.
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = name.rpartition(".")[0]
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


def _runtime():
    # Direct loading avoids executing world/__init__ or any game-state adapter.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    return _module(ROOT / "cs2career" / "world" / "calibrated.py", "cs2career.world.calibrated")


def compact_report(report, runtime):
    parameters = report["parameters"]
    if report["meta"]["model_version"] != runtime.MODEL_VERSION:
        raise ValueError("unsupported_lab_model")
    if parameters["role_fit_cap"] != 3 or parameters["position_expression_cap"] != 3:
        raise ValueError("unsupported_lab_position_caps")
    if parameters["role_prior_weight"] * parameters["position_expression_weight"] != .3:
        raise ValueError("unsupported_lab_expression_weight")
    if parameters["headroom_softening"] is not True:
        raise ValueError("unsupported_lab_headroom_policy")
    for role, prior in runtime.ROLE_PRIORS.items():
        if tuple(parameters["role_priors"][role][axis] for axis in runtime.AXES) != prior:
            raise ValueError("unsupported_lab_prior:" + role)

    records, identities, ids = [], set(), set()
    views_checked = 0
    for row in report["rows"]:
        new = row["new"]
        kind = {"placeholder": "world_roster", "current_library": "library"}.get(row["kind"], row["kind"])
        identity = (kind, row["era"], row["team_id"], row["player_name"])
        if identity in identities or row["id"] in ids:
            raise ValueError("duplicate_export_identity:" + row["id"])
        identities.add(identity)
        ids.add(row["id"])
        stats = dict(new["axes"])
        stats["ability"] = new["overall"]
        stats["position_model"] = runtime.model_marker(new["reference_role"], row["id"])
        if runtime.express_axes(stats, new["reference_role"]) != new["axes"]:
            raise ValueError("reference_parity_failure:" + row["id"])
        for role in runtime.POSITIONS:
            expected = new["positions"][role]
            if runtime.express_axes(stats, role) != expected["axes"]:
                raise ValueError("expression_parity_failure:" + row["id"] + ":" + role)
            fit = runtime.role_fit(stats, role)
            effective = round(max(1.0, min(100.0, new["overall"] + fit)), 3)
            if fit != expected["fit"] or effective != expected["effective"]:
                raise ValueError("role_fit_parity_failure:" + row["id"] + ":" + role)
            views_checked += 1
        record = {
            "id": row["id"], "name": row["player_name"],
            "canonical_name": row["canonical_name"], "hltv_id": row["hltv_id"],
            "kind": kind, "era": row["era"], "team_id": row["team_id"], "team": row["team"],
            "as_of": row["as_of"], "reference_role": new["reference_role"],
            "overall": new["overall"], "axes": dict(new["axes"]),
            "command": row["old"].get("command"), "placeholder": row["kind"] == "placeholder",
            "evidence": {key: row["evidence"][key] for key in (
                "level", "label", "window", "top30_maps", "top30_rating", "evidence_weight", "sources")},
            "uncertainty": {"overall": row["uncertainty"]["overall"],
                            "axes": row["uncertainty"]["axes"]},
        }
        records.append(record)
    pack = {
        "schema_version": 1, "model_version": runtime.MODEL_VERSION,
        "axes": list(runtime.AXES), "positions": report["meta"]["positions"],
        "snapshot_at": report["meta"]["snapshot_at"],
        "snapshot_hash": report["meta"]["snapshot_hash"],
        "parameters_hash": report["meta"]["parameters_hash"],
        "position_parameters": {
            "fit_cap": 3.0, "expression_weight": .3, "expression_cap": 3.0,
            "headroom_softening": True,
            "role_priors": parameters["role_priors"],
            "role_weights": {role: list(weights) for role, weights in runtime.ROLE_WEIGHTS.items()},
        },
        "policy": {
            "axes": "estimated_base_skills_not_observed_hltv_style",
            "overall": "five_annual_anchors_else_provisional_era_baseline",
            "positions": "stateless_expression_from_base_not_growth_or_role_stats",
            "rating": report["meta"]["rating_version"],
            "historical": report["meta"]["historical_policy"],
            "uncertainty": "assumption_ranges_not_statistical_confidence_intervals",
            "limitations": report["meta"]["limitations"],
            "method_sources": report["meta"]["method_sources"],
        },
        "coverage": {
            "records": len(records), "position_views_checked": views_checked,
            "by_kind": dict(Counter(row["kind"] for row in records)),
            "by_era": dict(Counter(row["era"] for row in records)),
            "by_evidence": dict(Counter(row["evidence"]["level"] for row in records)),
        },
        "records": records,
    }
    pack["pack_id"] = _digest(pack)
    return pack


def build_pack(lab=DEFAULT_LAB):
    lab = Path(lab).resolve()
    runtime = _runtime()
    model = _module(lab / "calibration.py", "isolated_calibration_export")
    snapshot = json.loads((lab / "snapshot.json").read_text(encoding="utf-8"))
    parameters = json.loads((lab / "parameters.json").read_text(encoding="utf-8"))
    report = model.build_report(snapshot, parameters)
    pack = compact_report(report, runtime)
    manifests = [json.loads(path.read_text(encoding="utf-8"))
                 for path in sorted((ROOT / 'cs2career/data/eras').glob('20[0-9][0-9].json'))
                 if path.stem in ('2024', '2025', '2026')]
    return reconcile_opening_rosters(pack, manifests, report, model, parameters, runtime)


def reconcile_opening_rosters(pack, manifests, report, model, parameters, runtime):
    """Join identity updates to the approved model, never copy a slot's stats.

    Transfers retain the person's same-era BASE and reference role. A genuinely
    new identity gets the lab's unchanged provisional-prior calculation; roster
    articles are kept separately and never passed in as performance evidence.
    """
    result = deepcopy(pack)
    eras = {world['era'] for world in manifests}
    people = {}
    for row in pack['records']:
        if row['kind'] in ('world_roster', 'free_agent') and not row['placeholder']:
            people.setdefault((row['era'], row['name'].casefold()), row)
    records = [deepcopy(row) for row in pack['records']
               if row['kind'] != 'world_roster' or row['era'] not in eras]
    for world in manifests:
        for team in world['teams']:
            for player in team['players']:
                donor = people.get((world['era'], player['name'].casefold()))
                identity = ['world_roster', world['era'], team['id'], player['name']]
                record_id = world['era'] + ':opening:' + _digest(identity)[:24]
                if donor:
                    row = deepcopy(donor)
                    if (row['kind'], row['team_id'], row['name']) != ('world_roster', team['id'], player['name']):
                        row['id'] = record_id
                    row.update(kind='world_roster', name=player['name'], team_id=team['id'], team=team['name'])
                else:
                    item = {'id': record_id, 'era': world['era'], 'as_of': world['as_of'],
                            'team_id': team['id'], 'team': team['name'], 'kind': 'world_roster',
                            'player': {'name': player['name'], 'role': player['role'],
                                       'ability': player['ability'], 'stats': {}}}
                    identities = {player['name']: {'canonical_name': player['name'],
                                                   'identity_match': 'exact_name', 'hltv_id': None}}
                    new = model.build_row(item, identities, {}, {}, parameters)
                    row = compact_report({**report, 'rows': [new]}, runtime)['records'][0]
                row['roster_provenance'] = {
                    'revision': world['revision'], 'roster_as_of': team.get('roster_as_of') or
                    team.get('announced_at') or team.get('observed_at'),
                    'sources': deepcopy(team['sources']), 'ability_reused': donor is not None,
                }
                records.append(row)
    result['records'] = records
    result['roster_manifest_hash'] = _digest(manifests)
    result['coverage'] = {
        'records': len(records), 'position_views_checked': len(records) * len(runtime.POSITIONS),
        'by_kind': dict(Counter(row['kind'] for row in records)),
        'by_era': dict(Counter(row['era'] for row in records)),
        'by_evidence': dict(Counter(row['evidence']['level'] for row in records)),
    }
    result.pop('pack_id', None)
    result['pack_id'] = _digest(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab", type=Path, default=DEFAULT_LAB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Verify bundled pack without writing")
    args = parser.parse_args()
    output = args.output.resolve()
    if output != DEFAULT_OUTPUT.resolve():
        parser.error("output is restricted to cs2career/data/calibrated_players_v1.json")
    # No bytecode writes outside the one authorized generated build artifact.
    sys.dont_write_bytecode = True
    pack = build_pack(args.lab)
    encoded = json.dumps(pack, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != encoded:
            raise SystemExit("bundled_calibration_pack_is_stale")
    else:
        output.write_text(encoded, encoding="utf-8")
    print(json.dumps({"pack_id": pack["pack_id"], "bytes": len(encoded.encode("utf-8")),
                      "checked": args.check, **pack["coverage"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
