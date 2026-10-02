"""Extract installed CS2 NAV and entity evidence into a private offline cache.

Uses the pinned ValveResourceFormat exporter; no game, plugin, or save writes.
The output atlas preserves full XYZ and portal edges. NAV is not a collision BSP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import struct
import subprocess
import zlib

MAPS = ['de_mirage', 'de_inferno', 'de_nuke', 'de_ancient', 'de_anubis',
        'de_overpass', 'de_train', 'de_vertigo', 'de_cache']


def read_entry(vpk: Path, wanted: str) -> bytes:
    with vpk.open('rb') as stream:
        magic, version, size = struct.unpack('<III', stream.read(12))
        if magic != 0x55AA1234 or version not in (1, 2) or not 0 < size <= 64 * 1024 * 1024:
            raise ValueError('unsupported_vpk')
        header_size = 12 if version == 1 else 28
        stream.seek(header_size)
        tree = stream.read(size)
        cursor = 0

        def string():
            nonlocal cursor
            end = tree.index(b'\0', cursor)
            value = tree[cursor:end].decode('utf-8')
            cursor = end + 1
            return value

        found = None
        while (extension := string()):
            while (directory := string()):
                while (name := string()):
                    crc, preload_size, archive, offset, length, terminator = struct.unpack_from('<IHHIIH', tree, cursor)
                    cursor += 18
                    if terminator != 0xFFFF or cursor + preload_size > size:
                        raise ValueError('invalid_vpk_entry')
                    preload = tree[cursor:cursor + preload_size]
                    cursor += preload_size
                    path = ('' if directory == ' ' else directory + '/') + name + ('' if extension == ' ' else '.' + extension)
                    if path == wanted:
                        if found is not None:
                            raise ValueError('duplicate_vpk_entry')
                        found = (crc, archive, offset, length, preload)
        if cursor != len(tree) or found is None:
            raise ValueError('entry_not_found: ' + wanted)
        crc, archive, offset, length, preload = found
        if archive != 0x7FFF or length + len(preload) > 64 * 1024 * 1024:
            raise ValueError('external_or_oversized_entry')
        stream.seek(header_size + size + offset)
        data = preload + stream.read(length)
        if len(data) != len(preload) + length or zlib.crc32(data) & 0xFFFFFFFF != crc:
            raise ValueError('vpk_crc_mismatch')
        return data


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def enrich_entities(atlas, vpk, output, exporter):
    records = []
    for match in re.finditer(r'^====(\d+)====\s*\r?\n(.*?)(?=^====\d+====|\Z)', atlas['EntityDump'], re.M | re.S):
        props = {}
        for line in match.group(2).splitlines():
            row = re.match(r'^(\S+)\s+(.+)$', line)
            if row:
                key, value = row.groups()
                try:
                    props[key] = json.loads(value)
                except ValueError:
                    props[key] = value
        if props.get('classname') in ('info_player_terrorist', 'info_player_counterterrorist', 'func_bomb_target', 'info_bomb_target'):
            records.append({'EntityIndex': int(match.group(1)), 'Properties': props})
    atlas['Spawns'] = {'T': [], 'CT': []}
    atlas['BombSites'] = []
    for record in records:
        props = record['Properties']
        origin = props.get('origin')
        record['Origin'] = dict(zip(('X', 'Y', 'Z'), origin)) if isinstance(origin, list) else None
        cls = props['classname']
        if cls.startswith('info_player_'):
            record['Enabled'] = props.get('enabled', True)
            record['Priority'] = props.get('priority', 0)
            atlas['Spawns']['T' if cls == 'info_player_terrorist' else 'CT'].append(record)
        else:
            record['Designation'] = str(props.get('bomb_site_designation', 'Unknown'))
            model_match = re.fullmatch(r'resource_name:"([^"]+)"', str(props.get('model', '')))
            if model_match:
                model_entry = model_match[1] + '_c'
                model_path = output / ('bombsite_' + record['Designation'] + '.vmdl_c')
                model_bytes = read_entry(vpk, model_entry)
                if model_path.exists() and model_path.read_bytes() != model_bytes:
                    raise ValueError('existing_model_evidence_mismatch')
                if not model_path.exists():
                    model_path.write_bytes(model_bytes)
                model_json = output / ('bombsite_' + record['Designation'] + '_model.json')
                if not model_json.exists():
                    subprocess.run(['dotnet', exporter, '--model', str(model_path), str(model_json)], check=True)
                record['ModelEntry'] = model_entry
                record['ModelEvidenceFile'] = model_json.name
                physics = json.loads(model_json.read_text())['PhysicsData'] or ''
                centers = [json.loads(v) for v in re.findall(r'm_vCentroid\s*=\s*(\[[^\]]+\])', physics)]
                minimums = [json.loads(v) for v in re.findall(r'm_vMinBounds\s*=\s*(\[[^\]]+\])', physics)]
                maximums = [json.loads(v) for v in re.findall(r'm_vMaxBounds\s*=\s*(\[[^\]]+\])', physics)]
                record['ModelHulls'] = [{'Min': mn, 'Max': mx, 'Centroid': c} for mn, mx, c in zip(minimums, maximums, centers)]
                if record['ModelHulls'] and all(float(v) == 0 for v in props.get('angles', [0, 0, 0])):
                    hull = max(record['ModelHulls'], key=lambda h: math.prod(h['Max'][i] - h['Min'][i] for i in range(3)))
                    scale = props.get('scales', [1, 1, 1])
                    anchor = [hull['Centroid'][i] * scale[i] + origin[i] for i in range(3)]
                    record['Anchor'] = dict(zip(('X', 'Y', 'Z'), anchor))
                    record['AnchorEvidence'] = 'centroid of largest actual bomb-target physics hull, translated/scaled by actual entity transform; NAV projection still required'
            record['AnchorStatus'] = 'Entity origin is a model pivot; use extracted model bounds for a NAV-projected anchor'
            atlas['BombSites'].append(record)
    atlas['EntityEvidence'] = {'SourceEntry': 'maps/' + atlas['Map'] + '/entities/default_ents.vents_c',
                               'CoordinateSpace': 'world XYZ; spawns may be above the floor',
                               'BombSiteDesignation': 'raw game bomb_site_designation, 0=A, 1=B'}


def extract(args, map_name):
    vpk = args.game / 'maps' / (map_name + '.vpk')
    output = args.output / map_name
    if output.exists():
        if not args.enrich_existing:
            raise ValueError('output_exists: ' + str(output))
        source_path = output / 'source.json'
        manifest = json.loads(source_path.read_text())
        if digest(vpk) != manifest['source_vpk_sha256']:
            raise ValueError('existing_cache_source_mismatch')
        atlas_path = output / 'atlas.json'
        atlas = json.loads(atlas_path.read_text())
        enrich_entities(atlas, vpk, output, args.exporter)
        atlas_path.write_text(json.dumps(atlas, indent=2), encoding='utf-8')
        manifest['atlas_sha256'] = digest(atlas_path)
        source_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        print(map_name + ': existing cache enriched with actual entity and bomb-target hull evidence')
        return
    source_hash = digest(vpk)
    nav = read_entry(vpk, 'maps/' + map_name + '.nav')
    entities = read_entry(vpk, 'maps/' + map_name + '/entities/default_ents.vents_c')
    if digest(vpk) != source_hash:
        raise ValueError('source_changed_during_extraction')
    output.mkdir(parents=True)
    nav_path = output / (map_name + '.nav')
    entity_path = output / 'default_ents.vents_c'
    nav_path.write_bytes(nav)
    entity_path.write_bytes(entities)
    atlas_path = output / 'atlas.json'
    subprocess.run(['dotnet', args.exporter, map_name, str(nav_path), str(entity_path), str(atlas_path)], check=True)
    atlas = json.loads(atlas_path.read_text(encoding='utf-8'))
    enrich_entities(atlas, vpk, output, args.exporter)
    atlas_path.write_text(json.dumps(atlas, indent=2), encoding='utf-8')
    manifest = {'schema_version': 1, 'map': map_name, 'source_vpk': str(vpk.resolve()),
                'source_vpk_sha256': source_hash, 'nav_entry': 'maps/' + map_name + '.nav',
                'nav_sha256': digest(nav_path), 'entity_entry': 'maps/' + map_name + '/entities/default_ents.vents_c',
                'entity_sha256': digest(entity_path), 'nav_format': list(struct.unpack_from('<III', nav)),
                'areas': len(atlas['Areas']), 'hull0_areas': sum(a['HullIndex'] == 0 for a in atlas['Areas']),
                'links': len(atlas['Links']), 'parser': atlas['Parser'], 'atlas_sha256': digest(atlas_path),
                'constraints': ['private local Valve map data', 'full source XYZ retained',
                                'NAV not collision or LOS geometry', 'traversal connections unclassified',
                                'entity coordinates require NAV projection before movement']}
    steam_inf = args.game / 'steam.inf'
    if steam_inf.is_file():
        manifest['installed_game'] = dict(line.split('=', 1) for line in steam_inf.read_text(encoding='utf-8-sig').splitlines()
                                         if '=' in line and line.split('=', 1)[0] in ('ClientVersion', 'ServerVersion', 'PatchVersion', 'SourceRevision'))
    (output / 'source.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, default=Path('D:/steam/steamapps/common/Counter-Strike Global Offensive/game/csgo'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exporter', default='E:/CS2CareerTools/RTSMultiMapSources-20261002/exporter/bin/NavExport.dll')
    parser.add_argument('--maps', nargs='+', choices=MAPS, default=MAPS)
    parser.add_argument('--enrich-existing', action='store_true', help='Add entity/hull metadata to verified existing caches')
    args = parser.parse_args()
    args.output = args.output.resolve()
    for map_name in args.maps:
        extract(args, map_name)


if __name__ == '__main__':
    main()
