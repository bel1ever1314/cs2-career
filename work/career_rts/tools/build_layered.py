"""Bake floor-separated NAV centre grids and explicit directed traversal gates.

The two radar floors occupy separate internal coordinate pages. Only source NAV
connections and ladder endpoints can join them; overlapping XY never joins them.
This is a bounded tactical movement model, not CS2 collision/visibility physics.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict, deque
import hashlib
import heapq
import json
import math
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from build_map import DIRECTIONS, point_in_polygon

SIZE, CELL, WIDTH = 1024, 2, 512


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def closest_on_edge(point, a, b):
    v = np.asarray(b, dtype=float) - a
    t = np.clip(np.dot(np.asarray(point)[:2] - np.asarray(a)[:2], v[:2]) / max(1e-12, np.dot(v[:2], v[:2])), 0, 1)
    return np.asarray(a) + v * t


def edge_gate(source, target, source_edge, target_edge):
    a, b = source[source_edge % len(source)], source[(source_edge + 1) % len(source)]
    c, d = target[target_edge % len(target)], target[(target_edge + 1) % len(target)]
    pairs = [(p, closest_on_edge(p, c, d)) for p in (a, b)]
    pairs += [(closest_on_edge(p, a, b), p) for p in (c, d)]
    distance = min(np.linalg.norm(np.asarray(p)[:2] - np.asarray(q)[:2]) for p, q in pairs)
    # Shared edge interval: its centre is a much safer gate than its corner.
    pairs = [(p, q) for p, q in pairs if np.linalg.norm(np.asarray(p)[:2] - np.asarray(q)[:2]) < distance + .1]
    return np.mean([p for p, _ in pairs], axis=0), np.mean([q for _, q in pairs], axis=0)


def traversal_kind(dz, gap, slope=False):
    if slope and abs(dz) <= 18 and gap <= 8: return "ramp"
    if gap > 8: return "jump" if dz >= -18 else "drop"
    if dz > 2: return "step" if dz <= 32 else "jump"
    if dz < -18: return "drop"
    return "walk"


def bake(map_id, cache, destination, registry, radars):
    atlas_path = cache / map_id / "atlas.json"
    atlas = json.loads(atlas_path.read_text("utf-8"))
    source = json.loads((atlas_path.parent / "source.json").read_text("utf-8"))
    meta = registry[map_id]
    cutoff = float(meta["layers"][0]["altitude_min"])
    overview = {key: meta[key] for key in ("pos_x", "pos_y", "scale")}
    scale = overview["scale"]
    stem = map_id.removeprefix("de_")
    data_dir, assets = destination / "data", destination / "assets"
    data_dir.mkdir(parents=True, exist_ok=True); assets.mkdir(parents=True, exist_ok=True)

    def project(world, layer=None):
        layer = int(float(world[2]) < cutoff) if layer is None else layer
        return [(world[0] - overview["pos_x"]) / scale, (overview["pos_y"] - world[1]) / scale + layer * SIZE]

    areas = {}
    floors = [Image.new("L", (SIZE, SIZE), 0) for _ in range(2)]
    owners = defaultdict(set)
    area_cells = defaultdict(list)
    for row in atlas["Areas"]:
        xyz = [[float(c[k]) for k in ("X", "Y", "Z")] for c in row["Corners"]]
        z = float(np.mean([p[2] for p in xyz])); layer = int(z < cutoff)
        polygon = [project(p, layer) for p in xyz]
        plane = np.linalg.lstsq(np.array([[p[0], p[1] - layer * SIZE, 1] for p in polygon]), np.array(xyz)[:, 2], rcond=None)[0]
        areas[int(row["Id"])] = {"corners": xyz, "polygon": polygon, "layer": layer, "z": z, "plane": plane}
        ImageDraw.Draw(floors[layer]).polygon([(x, y - layer * SIZE) for x, y in polygon], fill=255)
        for gy in range(max(layer * WIDTH, math.floor(min(p[1] for p in polygon) / CELL)), min((layer + 1) * WIDTH - 1, math.floor(max(p[1] for p in polygon) / CELL)) + 1):
            for gx in range(max(0, math.floor(min(p[0] for p in polygon) / CELL)), min(WIDTH - 1, math.floor(max(p[0] for p in polygon) / CELL)) + 1):
                if point_in_polygon(gx * CELL + 1, gy * CELL + 1, polygon):
                    node = gy * WIDTH + gx
                    owners[node].add(int(row["Id"])); area_cells[int(row["Id"])].append(node)

    # PIL edge rasterization and analytic polygon centres can disagree by one
    # pixel. Keep the same conservative centre/footprint contract at bake and
    # runtime rather than projecting an objective onto a blocked edge pixel.
    masks = [np.asarray(floor) for floor in floors]
    rejected = {node for node in owners if masks[node // (WIDTH * WIDTH)][(node // WIDTH * CELL + 1) % SIZE, node % WIDTH * CELL + 1] == 0}
    for node in rejected: del owners[node]
    for area in area_cells: area_cells[area] = [node for node in area_cells[area] if node not in rejected]

    # Same-page stacked roof/box surfaces are conservatively represented by
    # their lowest eligible centre. A height jump cannot become a walking edge.
    heights = {node: min(float(np.dot(areas[a]["plane"], [node % WIDTH * CELL + 1, (node // WIDTH * CELL + 1) % SIZE, 1])) for a in ids) for node, ids in owners.items()}
    def cell_z(node): return heights[node]
    walk = np.zeros(WIDTH * WIDTH * 2, dtype=np.bool_)
    for node in owners: walk[node] = True
    bits = np.zeros(len(walk), dtype=np.uint8)
    normal = defaultdict(set)
    evidence = []
    for row in atlas["Links"]:
        a, b = int(row["From"]), int(row["To"])
        p, q = edge_gate(areas[a]["corners"], areas[b]["corners"], int(row["SourceEdge"]), int(row["TargetEdge"]))
        gap = float(np.linalg.norm(p[:2] - q[:2])); dz = float(q[2] - p[2])
        slope = any(np.ptp(np.asarray(areas[n]["corners"])[:, 2]) > 18 for n in (a, b))
        kind = traversal_kind(dz, gap, slope)
        same = areas[a]["layer"] == areas[b]["layer"]
        if same and kind in ("walk", "ramp"): normal[a].add(b)
        else: evidence.append((a, b, p, q, kind if kind != "walk" else "ramp", dz, "NAV_connection"))
    for ladder in atlas.get("Ladders", []):
        bottom = ladder.get("BottomArea")
        if not bottom: continue
        b = int(bottom["AreaId"])
        for key in ("TopForwardArea", "TopLeftArea", "TopRightArea", "TopBehindArea"):
            upper = ladder.get(key)
            if not upper: continue
            a = int(upper["AreaId"])
            p = np.array([ladder["Top"][k] for k in ("X", "Y", "Z")]); q = np.array([ladder["Bottom"][k] for k in ("X", "Y", "Z")])
            evidence += [(a, b, p, q, "ladder", float(q[2] - p[2]), "NAV_ladder"), (b, a, q, p, "ladder", float(p[2] - q[2]), "NAV_ladder")]
    closure = {}
    for a in areas:
        reached, frontier = {a}, {a}
        for _ in range(6):
            frontier = set().union(*(normal[n] for n in frontier)) - reached if frontier else set()
            reached.update(frontier)
        closure[a] = reached
    for node, ids in owners.items():
        y, x = divmod(node, WIDTH)
        for bit, (dx, dy) in enumerate(DIRECTIONS):
            nx, ny = x + dx, y + dy
            other = ny * WIDTH + nx
            if not 0 <= nx < WIDTH or not 0 <= ny < WIDTH * 2 or y // WIDTH != ny // WIDTH or other not in owners: continue
            if dx and dy and (y * WIDTH + nx not in owners or ny * WIDTH + x not in owners): continue
            if abs(cell_z(node) - cell_z(other)) > 32: continue
            if ids & owners[other] or any(closure[a] & owners[other] for a in ids): bits[node] |= 1 << bit

    def position(node): return [int(node % WIDTH) * CELL + 1, int(node // WIDTH) * CELL + 1]
    def near_area(a, world):
        # Tiny intermediate triangles are projected through same-floor walking
        # portals only, never across an unclassified jump or floor boundary.
        candidates = area_cells[a]
        if not candidates:
            candidates = [n for b in closure[a] for n in area_cells[b]]
        if not candidates: return None
        target = project(world, areas[a]["layer"])
        return min(candidates, key=lambda n: math.dist(position(n), target))

    gates, extras = {}, defaultdict(list)
    for a, b, p, q, kind, dz, provenance in evidence:
        first, last = near_area(a, p), near_area(b, q)
        if first is None or last is None or first == last: continue
        if abs(dz) > 64 and kind == "jump": continue # Source link is outside simplified jump capability.
        # A source gate must be local; do not bridge distant islands by projection.
        if math.dist(position(first), project(p, areas[a]["layer"])) > 18 or math.dist(position(last), project(q, areas[b]["layer"])) > 18: continue
        duration = max(.18, abs(dz) / (130 if kind == "ladder" else 300))
        if kind == "jump": duration = max(.45, duration)
        if kind == "step": duration = .22
        gate = {"from": first, "to": last, "kind": kind, "seconds": round(duration, 3), "height_delta": round(dz, 2), "source_area": a, "target_area": b, "evidence": provenance}
        gates[(first, last)] = gate
        extras[first].append(last)

    def neighbors(node):
        y, x = divmod(node, WIDTH)
        for bit, (dx, dy) in enumerate(DIRECTIONS):
            if bits[node] & (1 << bit): yield (y + dy) * WIDTH + x + dx
        yield from extras[node]

    def location(world, used=()):
        target = project(world); page = int(world[2] < cutoff)
        candidates = [n for n in owners if n // (WIDTH * WIDTH) == page]
        candidates.sort(key=lambda n: (math.dist(position(n), target) ** 2 + ((cell_z(n) - world[2]) / scale) ** 2, n))
        for node in candidates:
            if all(math.dist(position(node), point) >= 12 for point in used): return node
        raise ValueError("No legal separated floor spawn")

    spawns, spawn_nodes = {}, {}
    for side, key in (("t", "T"), ("ct", "CT")):
        rows = [row for row in atlas["Spawns"][key] if row.get("Enabled", True) and row.get("Origin")]
        points = []; nodes = []
        for i in range(5):
            world = [rows[i % len(rows)]["Origin"][k] for k in ("X", "Y", "Z")]
            node = location(world, points); points.append(position(node)); nodes.append(node)
        spawns[side], spawn_nodes[side] = points, nodes
    targets = {}
    for site in atlas["BombSites"]:
        if site.get("Designation") not in ("0", "1"): continue
        name = "A_site" if site["Designation"] == "0" else "B_site"
        targets[name] = location([site["Anchor"][k] for k in ("X", "Y", "Z")])
    targets["CT_connector"] = spawn_nodes["ct"][0]

    def route(first, last):
        costs, parent, queue = {first: 0.0}, {}, [(0., first)]
        while queue:
            cost, node = heapq.heappop(queue)
            if cost != costs[node]: continue
            if node == last: break
            for other in neighbors(node):
                gate = gates.get((node, other))
                weight = gate["seconds"] * 70 + math.dist([position(node)[0], position(node)[1] % SIZE], [position(other)[0], position(other)[1] % SIZE]) if gate else math.dist(position(node), position(other))
                value = cost + weight
                if value < costs.get(other, math.inf):
                    costs[other], parent[other] = value, node; heapq.heappush(queue, (value, other))
        if last not in costs:
            print(json.dumps({"map": map_id, "reachable": len(costs), "walk": int(walk.sum()), "gates": len(gates), "kinds": dict(Counter(g["kind"] for g in gates.values())), "reached_lower": sum(n // (WIDTH * WIDTH) for n in costs), "cross_floor_gates": [g for g in gates.values() if g["from"] // (WIDTH * WIDTH) != g["to"] // (WIDTH * WIDTH)]}))
            raise ValueError(f"Directed layered route missing {map_id}: {position(first)} -> {position(last)}")
        nodes = [last]
        while nodes[-1] != first: nodes.append(parent[nodes[-1]])
        return list(reversed(nodes))

    for site, aliases in (("A", ("A_long", "A_short")), ("B", ("B_tunnel", "B_door"))):
        for side, alias in zip(("t", "ct"), aliases):
            nodes = route(spawn_nodes[side][0], targets[site + "_site"])
            # Approach on the objective's floor; a cross-floor alias must not
            # appear physically near the bomb merely because XY overlaps.
            last = targets[site + "_site"]
            targets[alias] = next((n for n in reversed(nodes) if n // (WIDTH * WIDTH) == last // (WIDTH * WIDTH) and math.dist(position(n), position(last)) >= 115), nodes[0])
    for side in spawn_nodes:
        for node in spawn_nodes[side]:
            for objective in ("A_site", "B_site"): route(node, targets[objective])

    grid = {"schema_version": 2, "width": WIDTH, "height": WIDTH * 2, "cell_size": CELL, "actor_clearance": 3.5, "navigation_space": "NAV_agent_centres", "regions": ["Upper", "Lower"],
            "walk_bits": base64.b64encode(np.packbits(walk, bitorder="little").tobytes()).decode(), "edge_bits": base64.b64encode(bits.tobytes()).decode(),
            "region_indices": base64.b64encode(np.concatenate([np.zeros(WIDTH * WIDTH, dtype=np.uint8), np.ones(WIDTH * WIDTH, dtype=np.uint8)]).tobytes()).decode(),
            "traversal_links": list(gates.values()), "portal_policy": "floor_identity_and_directed_NAV_only", "walk_cells": int(walk.sum())}
    grid_path = data_dir / (stem + "_grid.json"); grid_path.write_text(json.dumps(grid, separators=(",", ":")), "utf-8")
    layers = []
    collision = Image.new("L", (SIZE, SIZE * 2), 255)
    clearance = Image.new("L", (SIZE, SIZE * 2), 255)
    for i, layer in enumerate(meta["layers"]):
        suffix = "" if i == 0 else "_lower"
        radar = assets / (stem + suffix + "_radar.png")
        shutil.copyfile(radars / Path(layer["image"]).name, radar)
        floor = np.asarray(floors[i]) > 0
        collision.paste(Image.fromarray(np.where(floor, 0, 255).astype(np.uint8)), (0, i * SIZE))
        # Conservative centre-space clearance; nominal NAV actor remains legal.
        clearance.paste(floors[i].filter(ImageFilter.MinFilter(7)).point(lambda v: 16 if v else 0), (0, i * SIZE))
        rgb = np.asarray(Image.open(radar).convert("RGB"), dtype=float); luma = rgb @ np.array([.299, .587, .114])
        background = np.stack([18 + luma * .24, 23 + luma * .25, 25 + luma * .24], axis=2)
        foreground = np.stack([71 + luma * .25, 68 + luma * .23, 55 + luma * .19], axis=2)
        tactical = assets / (stem + suffix + "_tactical.png")
        Image.fromarray(np.clip(np.where(floor[:, :, None], foreground, background), 0, 255).astype(np.uint8)).save(tactical)
        layers.append({"id": layer["id"], "name": layer["name"], "name_en": "Upper floor" if i == 0 else "Lower floor", "offset": [0, i * SIZE], "image": "res://assets/" + tactical.name})
    collision.save(assets / (stem + "_collision.png")); collision.save(assets / (stem + "_sight.png")); clearance.save(assets / (stem + "_clearance.png"))
    output = {"schema_version": 2, "map": map_id, "name": meta["name"], "world_size": [SIZE, SIZE * 2], "actor_radius": 3.5,
              "radar": {"image": layers[0]["image"], "original": "res://assets/" + stem + "_radar.png", "overview": overview}, "layers": layers,
              "geometry": {"kind": "layered_actual_NAV", "grid_file": "res://data/" + grid_path.name, "cell_size": CELL, "navigation_space": "NAV_agent_centres", "actor_clearance": 3.5,
                           "collision_mask": f"res://assets/{stem}_collision.png", "clearance_mask": f"res://assets/{stem}_clearance.png", "sight_mask": f"res://assets/{stem}_sight.png"},
              "spawns": spawns, "sites": {site: {"center": position(targets[site + "_site"]), "radius": 32} for site in ("A", "B")},
              "tactical_targets": {name: position(node) for name, node in targets.items()},
              "waypoints": [{"id": name, "position": position(node), "source_region": "Lower" if node // (WIDTH * WIDTH) else "Upper"} for name, node in targets.items()],
              "site_entrances": {"A": ["A_long", "A_short", "CT_connector"], "B": ["B_tunnel", "B_door", "CT_connector"]}, "watch_anchors": [], "covers": [],
              "source": {"nav_sha256": atlas["NavSha256"], "atlas_sha256": sha(atlas_path), "grid_sha256": sha(grid_path), "exporter": "tools/build_layered.py", "entity_evidence": source},
              "statistics": {"source_nav_areas": len(areas), "source_directed_links": len(atlas["Links"]), "walk_cells": int(walk.sum()), "traversal_links": len(gates), "traversal_kinds": dict(Counter(g["kind"] for g in gates.values()))},
              "limitations": ["Each main floor has an independent NAV-centre page; only verified directed NAV/ladder gates connect floors.", "NAV footprint conservatively blocks sight. Cross-floor combat is blocked; open stairwells are not a full visibility BSP.", "Automatic jump, step, directed drop, ramp and ladder gates use simplified timings; no CS2 air acceleration or grenade height physics.", "Within a main floor small box/roof overlaps retain the lowest conservative NAV surface; exact ledge collision is not simulated."]}
    (data_dir / (stem + "_game.json")).write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), "utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("E:/CS2CareerTools/RTSMultiMapSources-20261002"))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--maps", nargs="+", default=["de_nuke", "de_vertigo"])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    registry = json.loads((root / "cs2career/data/tactical_maps.json").read_text("utf-8"))["maps"]
    catalog_path = args.output / "data/map_catalog.json"
    catalog = json.loads(catalog_path.read_text("utf-8"))
    for map_id in args.maps:
        output = bake(map_id, args.cache, args.output, registry, root / "cs2career/web/static/tactical_maps")
        catalog["maps"][map_id] = {"name": output["name"], "status": "playable", "career_ready": True, "data_file": f"res://data/{map_id.removeprefix('de_')}_game.json", "geometry": "layered_actual_NAV", "layers": ["upper", "lower"], "nav_sha256": output["source"]["nav_sha256"]}
        print(json.dumps({"map": map_id, **output["statistics"]}))
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), "utf-8")


if __name__ == "__main__": main()
