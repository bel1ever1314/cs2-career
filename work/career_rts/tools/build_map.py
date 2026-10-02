"""Bake radar-aligned conservative maps from local, verified NAV evidence.

This exporter reads only area geometry, directed connections and human watch
anchors. It never copies Demo routes, account identifiers or the source atlas.
Raster floor/LOS is an approximation: NAV is not a collision or visibility BSP.
"""
from __future__ import annotations

import argparse
import base64
from collections import defaultdict, deque
import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
CELL = 2
GRID = SIZE // CELL
RADIUS = 3.5
OVERVIEW = {"pos_x": -2476, "pos_y": 3239, "scale": 4.4}
DIRECTIONS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]


def project(point):
    return ((float(point["X"]) - OVERVIEW["pos_x"]) / OVERVIEW["scale"],
            (OVERVIEW["pos_y"] - float(point["Y"])) / OVERVIEW["scale"])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def edt_1d(values):
    """Squared Euclidean distance transform, lower envelope in linear time."""
    count = len(values)
    indices = np.empty(count, dtype=np.int32)
    cuts = np.empty(count + 1, dtype=np.float64)
    result = np.empty(count, dtype=np.float64)
    top = 0
    indices[0] = 0
    cuts[0], cuts[1] = -math.inf, math.inf
    for q in range(1, count):
        p = int(indices[top])
        cut = ((values[q] + q*q) - (values[p] + p*p)) / (2*q - 2*p)
        while cut <= cuts[top]:
            top -= 1
            p = int(indices[top])
            cut = ((values[q] + q*q) - (values[p] + p*p)) / (2*q - 2*p)
        top += 1
        indices[top], cuts[top], cuts[top + 1] = q, cut, math.inf
    top = 0
    for q in range(count):
        while cuts[top + 1] < q:
            top += 1
        p = int(indices[top])
        result[q] = (q - p)**2 + values[p]
    return result


def distances(floor):
    # A blocked border prevents clearance from extending outside the overview.
    values = np.where(floor, 1.0e12, 0.0)
    values[[0, -1], :] = 0
    values[:, [0, -1]] = 0
    for y in range(SIZE):
        values[y] = edt_1d(values[y])
    for x in range(SIZE):
        values[:, x] = edt_1d(values[:, x])
    return np.sqrt(values)


def point_in_polygon(x, y, polygon):
    inside = False
    previous = polygon[-1]
    for current in polygon:
        ax, ay = previous
        bx, by = current
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay) + ax:
            inside = not inside
        previous = current
    return inside


def component(edges, start):
    seen = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        x, y = current % GRID, current // GRID
        mask = int(edges[y, x])
        for bit, (dx, dy) in enumerate(DIRECTIONS):
            if mask & (1 << bit):
                target = (y+dy)*GRID + x+dx
                if target not in seen:
                    seen.add(target)
                    queue.append(target)
    return seen


def build(source, destination, overview=None, radar_source=None, metadata=None):
    global OVERVIEW
    atlas = json.loads(source.read_text(encoding="utf-8"))
    map_id = atlas["Map"]
    stem = map_id.removeprefix("de_")
    original_dust2 = map_id == "de_dust2"
    if overview is not None:
        OVERVIEW = {key: overview[key] for key in ["pos_x", "pos_y", "scale"]}
    if not original_dust2 and overview is None:
        raise ValueError("Other maps require verified overview metadata")
    if map_id in ("de_nuke", "de_vertigo"):
        raise ValueError("Layered map bake disabled: 2D floor identity must be preserved before enabling gameplay")
    metadata = metadata or {}
    assets = destination / "assets"
    data = destination / "data"
    assets.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    radar = assets / (stem + "_radar.png")
    if radar_source is not None:
        if radar_source.resolve() != radar.resolve(): shutil.copyfile(radar_source, radar)
    assert Image.open(radar).size == (SIZE, SIZE)
    regions = sorted({str(a.get("Region", "Unknown")) for a in atlas["Areas"]})
    region_index = {region: i for i, region in enumerate(regions)}
    area_by_id = {}
    polygons = []
    floor_image = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(floor_image)
    owners = defaultdict(set)
    for row in atlas["Areas"]:
        points = [project(corner) for corner in row["Corners"]]
        if len(points) < 3 or not all(math.isfinite(v) for point in points for v in point):
            continue
        region = str(row.get("Region", "Unknown"))
        z = [float(c["Z"]) for c in row["Corners"]]
        index = len(polygons)
        area_by_id[int(row["Id"])] = index
        polygons.append({"points": [[round(x, 2), round(y, 2)] for x, y in points],
                         "region": region, "z_min": round(min(z), 2), "z_max": round(max(z), 2)})
        draw.polygon(points, fill=255)
        min_x = max(0, math.floor(min(p[0] for p in points)/CELL))
        max_x = min(GRID-1, math.floor(max(p[0] for p in points)/CELL))
        min_y = max(0, math.floor(min(p[1] for p in points)/CELL))
        max_y = min(GRID-1, math.floor(max(p[1] for p in points)/CELL))
        for gy in range(min_y, max_y+1):
            for gx in range(min_x, max_x+1):
                if point_in_polygon((gx+.5)*CELL, (gy+.5)*CELL, points):
                    owners[gy*GRID+gx].add(index)

    floor = np.asarray(floor_image) > 0
    distance = distances(floor)
    # Quarter-pixel, rounded DOWN; runtime subtracts .75 for pixel-centre error.
    clearance = np.floor(np.minimum(distance, 63.75)*4).astype(np.uint8)
    collision = np.where(floor, 0, 255).astype(np.uint8)
    Image.fromarray(collision).save(assets / (stem + "_collision.png"))
    Image.fromarray(clearance).save(assets / (stem + "_clearance.png"))
    # Separate asset and contract: conservative floor-footprint LOS, not CS2 BSP.
    Image.fromarray(collision).save(assets / (stem + "_sight.png"))
    pixel = np.arange(GRID)*CELL + CELL//2
    # NAV polygons describe legal AGENT CENTRES, not a wall BSP. Shrinking
    # their footprint by the body radius a second time deletes narrow doors.
    # A dense 2px grid keeps tiny source NAV portals; a centre must still have
    # a source polygon owner and never sit in a blocked footprint pixel.
    valid = floor[np.ix_(pixel, pixel)]
    valid &= np.array([[y*GRID+x in owners for x in range(GRID)] for y in range(GRID)])

    def clear_pixels(ax, ay, bx, by):
        # Exact pixel-grid traversal, matching the runtime predicate. Sampling
        # at a step-dependent interval can miss a cell at a door/corner and
        # then contradict the same path when the actor takes shorter steps.
        dx, dy = bx-ax, by-ay
        x, y = math.floor(ax), math.floor(ay)
        sx = 1 if dx > 0 else -1 if dx < 0 else 0
        sy = 1 if dy > 0 else -1 if dy < 0 else 0
        tx = ((x+(1 if sx > 0 else 0))-ax)/dx if dx else math.inf
        ty = ((y+(1 if sy > 0 else 0))-ay)/dy if dy else math.inf
        dtx = abs(1/dx) if dx else math.inf
        dty = abs(1/dy) if dy else math.inf
        if not floor[y,x]: return False
        while min(tx,ty) < 1-1e-10:
            if abs(tx-ty) < 1e-10:
                # No diagonally cutting the single pixel of a solid corner.
                if not floor[y,x+sx] or not floor[y+sy,x]: return False
                x += sx; y += sy; tx += dtx; ty += dty
            elif tx < ty:
                x += sx; tx += dtx
            else:
                y += sy; ty += dty
            if not floor[y,x]: return False
        return bool(floor[math.floor(by),math.floor(bx)])

    links = defaultdict(set)
    for row in atlas["Links"]:
        a, b = area_by_id.get(int(row["From"])), area_by_id.get(int(row["To"]))
        if a is not None and b is not None:
            links[a].add(b)
    # Tiny NAV polygons can lie between sample centres. A bounded six-hop
    # portal closure preserves those seams; collision still checks the actual
    # swept floor footprint and no reverse connection is invented.
    portal = {}
    for index in range(len(polygons)):
        adjacent = {index}
        frontier = {index}
        for _ in range(6):
            following = set().union(*(links[neighbor] for neighbor in frontier))-adjacent if frontier else set()
            adjacent.update(following)
            frontier=following
        portal[index] = adjacent

    edge_bits = np.zeros((GRID, GRID), dtype=np.uint8)
    region_ids = np.full((GRID, GRID), 255, dtype=np.uint8)
    overlaps = 0
    for flat, ids in owners.items():
        y, x = divmod(flat, GRID)
        if not valid[y, x]:
            continue
        # Region annotation chooses the lowest surface. Routing still consults
        # every overlapping owner; the resulting floor alias is documented.
        lowest = min(ids, key=lambda i: (polygons[i]["z_min"], i))
        region_ids[y, x] = region_index[polygons[lowest]["region"]]
        if max(polygons[i]["z_max"] for i in ids)-min(polygons[i]["z_min"] for i in ids) > 64:
            overlaps += 1
        for bit, (dx, dy) in enumerate(DIRECTIONS):
            nx, ny = x+dx, y+dy
            if not (0 <= nx < GRID and 0 <= ny < GRID and valid[ny, nx]):
                continue
            if dx and dy and (not valid[y, nx] or not valid[ny, x]):
                continue
            other = owners[ny*GRID+nx]
            if not (ids & other or any(portal[a] & other for a in ids)):
                continue
            # The nominal agent body is already represented by source NAV.
            # Additional body radii are checked against remaining centre-space
            # clearance at runtime; this bake never invents a source portal.
            clear = clear_pixels((x+.5)*CELL,(y+.5)*CELL,(nx+.5)*CELL,(ny+.5)*CELL)
            if clear:
                edge_bits[y, x] |= 1 << bit

    cells_by_region = defaultdict(list)
    for y, x in zip(*np.nonzero(valid)):
        cells_by_region[regions[int(region_ids[y, x])]].append((int(x), int(y)))

    def location(region, world=None, used=None):
        candidates = cells_by_region[region]
        if world:
            anchor = project({"X": world[0], "Y": world[1]})
        else:
            anchor = tuple(np.median([(x*CELL+CELL//2, y*CELL+CELL//2) for x, y in candidates], axis=0))
        ordered = sorted(candidates, key=lambda cell: ((cell[0]*CELL+CELL//2-anchor[0])**2+(cell[1]*CELL+CELL//2-anchor[1])**2, cell))
        for x, y in ordered:
            point = [x*CELL+CELL//2, y*CELL+CELL//2]
            if not used or all(math.dist(point, other) >= 12 for other in used):
                return point
        raise RuntimeError("No separated spawn point: " + region)

    if not original_dust2:
        assert metadata.get("spawns", {}).get("t") and metadata.get("spawns", {}).get("ct"), "Verified spawn entities missing"
        assert all(site in metadata.get("sites", {}) for site in ("A", "B")), "Verified bombsite entity/NAV labels missing"
    seed_region = "TSpawn" if original_dust2 else str(atlas["Areas"][0].get("Region", "Unknown"))
    seed_world = (-750, -820) if original_dust2 else metadata["spawns"]["t"][0][:2]
    seed = location(seed_region, seed_world)
    playable = component(edge_bits,(seed[1]//CELL)*GRID+seed[0]//CELL)
    discarded_cells = int(valid.sum())-len(playable)
    # Raster islands commonly come from tiny box-top/ledge NAV surfaces. The
    # playable board keeps only the directed component reached from T spawn.
    for region, cells in cells_by_region.items():
        cells_by_region[region]=[(x,y) for x,y in cells if y*GRID+x in playable]
    for y,x in zip(*np.nonzero(valid)):
        if y*GRID+x not in playable:valid[y,x]=False

    anchors = {
        "A_site": ("BombsiteA", (1130, 2650)), "B_site": ("BombsiteB", (-1800, 2650)),
        "A_long": ("LongA", (1450, 1600)), "A_short": ("ShortStairs", (390, 1800)),
        "B_tunnel": ("UpperTunnel", (-1650, 1540)), "B_door": ("BDoors", (-1200, 2340)),
        "CT_connector": ("CTSpawn", (-100, 2260)),
    }
    if not original_dust2:
        anchors = {
            "A_site": (seed_region, metadata["sites"]["A"]["center"][:2]),
            "B_site": (seed_region, metadata["sites"]["B"]["center"][:2]),
            "CT_connector": (seed_region, metadata["spawns"]["ct"][0][:2]),
        }
    targets = {name: location(region, world) for name, (region, world) in anchors.items()}
    spawns = {"t": [], "ct": []}
    for side, region, world in [("t", "TSpawn", (-750, -820)), ("ct", "CTSpawn", (-100, 2320))]:
        for index in range(5):
            if not original_dust2:
                region = seed_region
                supplied = metadata["spawns"][side]
                world = supplied[index % len(supplied)][:2]
            spawns[side].append(location(region, world, spawns[side]))
    if not original_dust2:
        # Contract aliases are NAV route staging points, not claimed CS2 callouts.
        # Pick reachable approach nodes on real directed shortest paths.
        import heapq
        def route_points(start, finish):
            first = (start[1]//CELL)*GRID + start[0]//CELL
            last = (finish[1]//CELL)*GRID + finish[0]//CELL
            cost, parents, queue = {first: 0.0}, {}, [(0.0, first)]
            while queue:
                distance, node = heapq.heappop(queue)
                if distance != cost[node]: continue
                if node == last: break
                y, x = divmod(node, GRID)
                for bit, (dx, dy) in enumerate(DIRECTIONS):
                    if not int(edge_bits[y, x]) & (1 << bit): continue
                    other = (y+dy)*GRID + x+dx
                    value = distance + math.hypot(dx,dy)
                    if value < cost.get(other, math.inf):
                        cost[other], parents[other] = value, node
                        heapq.heappush(queue,(value,other))
            if last not in cost: raise ValueError(f"No true NAV path {map_id}: {start} -> {finish}")
            nodes, node = [last], last
            while node != first:
                node = parents[node]
                nodes.append(node)
            return [[(node%GRID)*CELL+CELL//2,(node//GRID)*CELL+CELL//2] for node in reversed(nodes)]
        for site, first_alias, second_alias in [("A", "A_long", "A_short"), ("B", "B_tunnel", "B_door")]:
            for origin, alias in [(spawns["t"][0],first_alias),(spawns["ct"][0],second_alias)]:
                route = route_points(origin, targets[site+"_site"])
                point = next((p for p in reversed(route) if math.dist(p, targets[site+"_site"]) >= 115),route[0])
                targets[alias] = point
                anchors[alias] = (seed_region, None)
            if math.dist(targets[first_alias], targets[second_alias]) < 70 or math.dist(targets[second_alias], targets[site+"_site"]) < 70:
                center = targets[site+"_site"]
                candidates = [[int(x)*CELL+CELL//2,int(y)*CELL+CELL//2] for y,x in zip(*np.nonzero(valid))
                              if 105 <= math.dist([x*CELL+CELL//2,y*CELL+CELL//2],center) <= 135
                              and math.dist([x*CELL+CELL//2,y*CELL+CELL//2],targets[first_alias]) >= 90]
                candidates.sort(key=lambda p: math.dist(p,targets[second_alias]))
                for point in candidates[:20]:
                    try:
                        route_points(spawns["t"][0],point)
                        route_points(point,center)
                    except ValueError:
                        continue
                    targets[second_alias] = point
                    break
    waypoints = [{"id": name, "position": targets[name], "source_region": region}
                 for name, (region, _) in anchors.items()]
    for region in regions:
        if cells_by_region[region]:
            waypoints.append({"id": "region_"+region, "position": location(region), "source_region": region})
    waypoints.extend([{"id": "t_spawn", "position": spawns["t"][0], "source_region": "TSpawn" if original_dust2 else seed_region},
                      {"id": "ct_spawn", "position": spawns["ct"][0], "source_region": "CTSpawn" if original_dust2 else seed_region}])
    watches = []
    for row in atlas.get("Watches", []):
        area_index = area_by_id.get(int(row.get("Area", -1)))
        if area_index is None or not row.get("Feet"):
            continue
        region = polygons[area_index]["region"]
        if not cells_by_region[region]:
            continue
        yaw = math.radians(float(row.get("Yaw", 0)))
        side = "ct" if row.get("CaptureSide") == "CounterTerrorist" else "t"
        watches.append({"position": location(region, (row["Feet"]["X"], row["Feet"]["Y"])),
                        "direction": [round(math.cos(yaw), 5), round(-math.sin(yaw), 5)],
                        "region": region, "side": side,
                        "source": "human_watch_anchor_projected_without_pitch"})

    required = [p for side in spawns.values() for p in side]+list(targets.values())
    origin = (spawns["t"][0][1]//CELL)*GRID + spawns["t"][0][0]//CELL
    reachable = component(edge_bits, origin)
    missing = [p for p in required if (p[1]//CELL)*GRID+p[0]//CELL not in reachable]
    if missing:
        free_edges=np.zeros_like(edge_bits)
        for y,x in zip(*np.nonzero(valid)):
            for bit,(dx,dy) in enumerate(DIRECTIONS):
                nx,ny=x+dx,y+dy
                if 0<=nx<GRID and 0<=ny<GRID and valid[ny,nx]:
                    free_edges[y,x]|=1<<bit
        print(json.dumps({"diagnostic":"required_route_disconnected","walk_cells":int(valid.sum()),"nav_connected":len(reachable),"floor_connected":len(component(free_edges,origin)),"spawns":spawns,"missing":missing}))
        raise RuntimeError("Required map routes disconnected: "+str(missing))
    for side in ("t", "ct"):
        root = (spawns[side][0][1]//CELL)*GRID + spawns[side][0][0]//CELL
        seen = component(edge_bits, root)
        assert all((p[1]//CELL)*GRID+p[0]//CELL in seen for p in targets.values()), side

    grid = {"schema_version": 1, "width": GRID, "height": GRID, "cell_size": CELL,
            "actor_clearance": RADIUS, "navigation_space": "NAV_agent_centres", "directions": DIRECTIONS, "regions": regions,
            "walk_bits": base64.b64encode(np.packbits(valid.flatten(), bitorder="little").tobytes()).decode(),
            "edge_bits": base64.b64encode(edge_bits.tobytes()).decode(),
            "region_indices": base64.b64encode(region_ids.tobytes()).decode(),
            "portal_policy": "same_NAV_area_or_directed_1_to_6_hop_NAV_connection_with_exact_centre_pixel_trace",
            "walk_cells": int(valid.sum()), "reachable_cells_from_t_spawn": len(reachable)}
    grid_path = data / (stem + "_grid.json")
    grid_path.write_text(json.dumps(grid, separators=(",", ":")), encoding="utf-8")

    # Desaturate radar markings, then blend muted sand into the real floor.
    radar_rgb = np.array(Image.open(radar).convert("RGB"), dtype=np.float64)
    luma = radar_rgb @ np.array([.299, .587, .114])
    backdrop = np.stack([18+luma*.24, 23+luma*.25, 25+luma*.24], axis=2)
    floor_color = np.stack([71+luma*.25, 68+luma*.23, 55+luma*.19], axis=2)
    baked = np.where(floor[:, :, None], floor_color, backdrop)
    border = np.asarray(floor_image.filter(ImageFilter.MinFilter(3))) < np.asarray(floor_image)
    baked[border] = baked[border]*.65 + np.array([130, 117, 87])*.35
    Image.fromarray(np.clip(baked, 0, 255).astype(np.uint8)).save(assets / (stem + "_tactical.png"))

    generated = [stem+suffix for suffix in ["_collision.png", "_clearance.png", "_sight.png", "_tactical.png"]]
    result = {"schema_version": 2, "map": map_id, "name": metadata.get("name", "Dust II" if original_dust2 else map_id), "world_size": [SIZE, SIZE],
              "actor_radius": RADIUS, "radar": {"image": f"res://assets/{stem}_tactical.png", "original": f"res://assets/{stem}_radar.png", "overview": OVERVIEW},
              "geometry": {"kind": "projected_actual_NAV_2D", "grid_file": f"res://data/{stem}_grid.json", "cell_size": CELL,
                           "actor_clearance": RADIUS, "navigation_space": "NAV_agent_centres", "collision_mask": f"res://assets/{stem}_collision.png",
                           "clearance_mask": f"res://assets/{stem}_clearance.png", "sight_mask": f"res://assets/{stem}_sight.png",
                           "mask_semantics": "NAV-centre footprint/sight:255 blocked,0 open;clearance:L8/4 pixels beyond nominal agent centre envelope"},
              "sites": {"A": {"center": targets["A_site"], "radius": 32}, "B": {"center": targets["B_site"], "radius": 34}},
              "spawns": spawns, "tactical_targets": targets, "waypoints": waypoints,
              "nav_polygons": polygons, "watch_anchors": watches, "covers": [],
              "source": {"atlas_file": source.name, "atlas_sha256": digest(source), "nav_sha256": atlas.get("NavHash", atlas.get("NavSha256", "")),
                         "map_sha256": str(atlas.get("MapHash", "")).lower(), "radar_sha256": digest(radar),
                         "exporter": "tools/build_map.py", "exporter_sha256": digest(Path(__file__)),
                         "derived_sha256": {name: digest(assets / name) for name in generated}, "grid_sha256": digest(grid_path)},
              "statistics": {"source_nav_areas": len(polygons), "source_directed_links": len(atlas["Links"]),
                             "walk_cells": int(valid.sum()), "reachable_cells": len(reachable), "overlapping_height_cells": overlaps,
                             "watch_anchors": len(watches), "excluded_disconnected_raster_cells": discarded_cells},
              "limitations": ["Actual NAV agent-centre footprint, not an authored rectangle schematic; navigation raster precision is two radar pixels.",
                              "The nominal 3.5px body radius is represented by source NAV centre eligibility, not reapplied as a second erosion. Bigger agents require additional clearance.",
                              "NAV is not the collision/visibility BSP. Non-walkable footprint conservatively blocks sight; windows, height, doors and cover are approximate.",
                              "Overlapping surfaces share 2D positions. Directed NAV portals constrain movement, but upper/lower floors cannot be faithfully separated.",
                              "NAV links have unclassified traversal; jump/drop/ladder physics are not simulated.",
                              "Disconnected raster islands are excluded from actor navigation; some small ledges/box tops cannot be visited.",
                              "Five separated spawn-region NAV points are used, not exact CS2 spawn entity coordinates.",
                              "Human watch yaw is projected and clipped by the 2D sight mask; it is not proof of true 3D visibility.",
                              "No Demo routes, account identifiers, live CS2 controls or career saves are included."]}
    if not original_dust2:
        result["source"]["entity_evidence"] = metadata.get("source", {})
        result["limitations"].append("Tactical route keys A_long/A_short/B_tunnel/B_door are interface aliases for verified NAV approach points, not native map callout names.")
        result["limitations"].append("Source NAV36 no longer exports place names; no Dust2 Bot Lab route/watch knowledge is applied to this map.")
        result["limitations"][6] = "Spawn entities are projected onto nearest connected real NAV cells; five separate legal actor centres preserve roster spacing."
    result["site_entrances"] = {"A": ["A_long", "A_short", "CT_connector"], "B": ["B_tunnel", "B_door", "CT_connector"]}
    (data / (stem + "_game.json")).write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"map": map_id, "statistics": result["statistics"], "spawns": spawns, "targets": targets,
                      "files": {p.name: p.stat().st_size for p in [data/(stem+"_game.json"), grid_path]+[assets/name for name in generated]}}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atlas", type=Path, default=Path("D:/CS2BotLab/data/teamplay/dust2_team_atlas.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--overview", type=Path, help="Versioned tactical_maps.json")
    parser.add_argument("--radar", type=Path, help="Verified official radar PNG, never used as navigation")
    parser.add_argument("--metadata", type=Path, help="Extracted spawn/bombsite entity metadata JSON")
    arguments = parser.parse_args()
    atlas_map = json.loads(arguments.atlas.read_text(encoding="utf-8"))["Map"]
    overview = json.loads(arguments.overview.read_text(encoding="utf-8"))["maps"][atlas_map] if arguments.overview else None
    metadata = json.loads(arguments.metadata.read_text(encoding="utf-8")) if arguments.metadata else None
    build(arguments.atlas, arguments.output, overview, arguments.radar, metadata)
