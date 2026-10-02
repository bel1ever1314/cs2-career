"""Explicit offline-media build; never run from a game/UI refresh.

Exports only map loading screens from the owner's installed CS2 via Source 2
Viewer. Optionally warms exact-ID approved skin artwork, using the same pinned
manifest as the desktop version. Outputs must live on D/E, not the source tree.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MAPS = ("dust2", "mirage", "inferno", "nuke", "overpass", "ancient", "anubis", "train", "vertigo", "cache")


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, default=Path("E:/CS2CareerTools/Career3DMedia"))
    parser.add_argument("--csgo", type=Path)
    parser.add_argument("--exporter", type=Path)
    parser.add_argument("--warm-skins", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_absolute() or output.drive.upper() not in ("D:", "E:") or output == Path(output.anchor):
        parser.error("Use a dedicated media folder on D: or E:.")
    output.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": 1, "map_backgrounds": {}, "skin_cache_roots": [str(output / "skin_art")],
              "notice": "Valve game images, exported locally. Source 2 Viewer 20.0 / https://s2v.app"}
    if args.csgo or args.exporter:
        if not args.csgo or not args.exporter:
            parser.error("Map export needs both --csgo and --exporter.")
        (output / "maps").mkdir(exist_ok=True)
        for name in MAPS:
            target = output / "maps" / ("de_" + name + ".png")
            source = "panorama/images/map_icons/screenshots/1080p/de_" + name + "_png.vtex_c"
            if not target.is_file():
                subprocess.run([str(args.exporter), "-i", str(args.csgo / "pak01_dir.vpk"), "-d",
                                "--vpk_filepath", source, "-o", str(target)], check=True, timeout=45,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if target.is_file():
                report["map_backgrounds"]["de_" + name] = {"kind": "loading_art", "path": str(target),
                    "source": "installed CS2 " + source, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    if args.warm_skins:
        os.environ["CS2CAREER_SAVE_DIR"] = str(output)
        sys.path.insert(0, str(ROOT))
        from cs2career.skin_art import artwork, manifest
        rows = manifest()["items"]
        ids = [key for key, row in rows.items() if row.get("status") == "mapped"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(artwork, ids))
        report["skins"] = {"mapped": len(ids), "cached": sum(path is not None for path in results)}
    target = output / "media-manifest.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    print(json.dumps({"output": str(target), "maps": len(report["map_backgrounds"]), "skins": report.get("skins", {})}))


if __name__ == "__main__":
    main()
