"""Bake and inventory locally extracted NAV maps; unsupported floors fail closed."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import build_map


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("E:/CS2CareerTools/RTSMultiMapSources-20261002"))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--overview", type=Path, default=Path(__file__).resolve().parents[3] / "cs2career/data/tactical_maps.json")
    parser.add_argument("--radars", type=Path, default=Path(__file__).resolve().parents[3] / "cs2career/web/static/tactical_maps")
    parser.add_argument("--maps", nargs="+", default=["de_mirage", "de_inferno", "de_ancient", "de_anubis", "de_overpass", "de_train", "de_cache"])
    args = parser.parse_args()
    overview = json.loads(args.overview.read_text(encoding="utf-8"))["maps"]
    catalog_path = args.output / "data/map_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    report = {"schema_version": 2, "maps": {}}
    for map_id, row in catalog["maps"].items():
        source_path = args.cache / map_id / "source.json"
        if source_path.exists():
            report["maps"][map_id] = {"status": row["status"], "source": json.loads(source_path.read_text(encoding="utf-8"))}
    for map_id in args.maps:
        atlas_path = args.cache / map_id / "atlas.json"
        evidence = json.loads(atlas_path.read_text(encoding="utf-8"))
        source = json.loads((atlas_path.parent / "source.json").read_text(encoding="utf-8"))
        metadata = {"name": overview[map_id]["name"], "spawns": {}, "sites": {}, "source": source}
        for side, source_side in [("t", "T"), ("ct", "CT")]:
            metadata["spawns"][side] = [[row["Origin"][k] for k in ("X", "Y", "Z")] for row in evidence["Spawns"][source_side]
                                         if row.get("Enabled", True) and row.get("Origin")]
        for row in evidence["BombSites"]:
            designation = row.get("Designation")
            if designation not in ("0", "1") or not row.get("Anchor"): continue
            key = "A" if designation == "0" else "B"
            metadata["sites"][key] = {"center": [row["Anchor"][k] for k in ("X", "Y", "Z")], "entity": row}
        (atlas_path.parent / "game_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        try:
            build_map.build(atlas_path, args.output, overview[map_id], args.radars / (map_id + ".png"), metadata)
            previous = catalog["maps"].get(map_id, {})
            catalog["maps"][map_id] = {"name": overview[map_id]["name"], "status": "playable", "data_file": "res://data/" + map_id.removeprefix("de_") + "_game.json",
                                       "career_ready": previous.get("career_ready", True),
                                       "geometry": "actual_NAV_agent_centres", "layers": ["upper"], "nav_sha256": source["nav_sha256"]}
            if previous.get("career_reason"):
                catalog["maps"][map_id]["career_reason"] = previous["career_reason"]
            report["maps"][map_id] = {"status": "playable", "source": source}
        except (ValueError, RuntimeError, AssertionError) as error:
            catalog["maps"][map_id]["status"] = "unavailable"
            catalog["maps"][map_id]["career_ready"] = False
            catalog["maps"][map_id]["reason"] = str(error)
            report["maps"][map_id] = {"status": "unavailable", "reason": str(error), "source": source}
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    for map_id in ("de_nuke", "de_vertigo"):
        source_path = args.cache / map_id / "source.json"
        catalog["maps"][map_id]["career_ready"] = False
        if source_path.exists():
            source = json.loads(source_path.read_text(encoding="utf-8"))
            catalog["maps"][map_id]["nav_sha256"] = source["nav_sha256"]
            catalog["maps"][map_id]["reason"] = "Real NAV extracted with XYZ; current 2D runtime cannot preserve overlapping floor identity or traversal physics. Gameplay disabled to prevent false floor connections."
            report["maps"][map_id] = {"status": "awaiting_layered_nav", "source": source, "reason": catalog["maps"][map_id]["reason"]}
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.cache / "bake_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
