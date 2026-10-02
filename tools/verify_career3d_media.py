"""Check image identity, loading-art semantics and read-only cache reuse."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.career3d_resources import cached_skin_art, resource_context


def run(folder):
    folder.mkdir(parents=True)
    cache = folder / "cached"
    cache.mkdir()
    image = cache / "map.png"
    from PIL import Image
    Image.new("RGB", (192, 108), (140, 170, 180)).save(image)
    url = "https://community.akamai.steamstatic.com/economy/image/identity"
    skin = cache / (hashlib.sha256(url.encode()).hexdigest() + ".png")
    Image.new("RGB", (64, 32), (200, 160, 110)).save(skin)
    manifest = folder / "media.json"
    manifest.write_text(json.dumps({"schema_version": 1, "skin_cache_roots": [str(cache)],
        "map_backgrounds": {"de_dust2": {"path": str(image), "kind": "loading_art"},
                            "de_mirage": {"path": str(image), "kind": "radar"},
                            "de_nuke": {"path": "https://invalid/art.png", "kind": "loading_art"}}}), "utf-8")
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in cache.iterdir()}
    with patch.dict(os.environ, {"CS2CAREER3D_MEDIA_CONFIG": str(manifest), "CS2CAREER_SAVE_DIR": str(folder / "isolated")}):
        media = resource_context()["media"]
        assert media["map_backgrounds"] == {"de_dust2": str(image), "dust2": str(image)}
        art = {"items": {"exact": {"status": "mapped", "url": url}, "wrong": {"status": "unmatched", "url": url}}}
        assert cached_skin_art("exact", art) == str(skin)
        assert not cached_skin_art("wrong", art) and not cached_skin_art("missing", art)
        with patch.dict(os.environ, {"CS2CAREER3D_MEDIA_CONFIG": ""}):
            assert not resource_context()["media"]["map_backgrounds"]
            assert not cached_skin_art("exact", art)
    assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in cache.iterdir()}
    return {"ok": True, "checks": ["loading images are not radar substitutes", "map aliases resolve to exact same art",
             "remote paths rejected", "skins use exact manifest URL hash", "external cache reads leave images unchanged",
             "optional media manifest does not leak into an unconfigured test"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    if folder.drive.upper() not in ("D:", "E:") or folder.exists():
        parser.error("Choose a new isolated D/E folder.")
    result = run(folder)
    (folder / "media-verification.json").write_text(json.dumps(result, indent=2), "utf-8")
    print(json.dumps(result))
