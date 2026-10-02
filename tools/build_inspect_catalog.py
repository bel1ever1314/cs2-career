"""Build the small, pinned viewer-ID/placement manifest; no game assets are copied.

Run with --cache on D/E. The runtime never downloads a catalog or reads Steam.
cs2-lib IDs are NOT Valve weapon/sticker definition indexes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'd3372d56609c8f0567becfb5d090b190bccf7043'
URL = f'https://raw.githubusercontent.com/ianlucas/cs2-lib/{COMMIT}/scripts/data/items.json'


def build(rows, weapon_definitions, sticker_definitions):
    by_id = {row['id']: row for row in rows}
    items, models, stickers, images = {}, {}, {}, {}
    for row in rows:
        definition = row.get('definitionIndex')
        if row.get('type') == 'sticker' and row.get('variantIndex') in sticker_definitions:
            kit = str(row['variantIndex'])
            stickers[kit] = row['id']
            images[kit] = 'https://cdn.cstrike.app' + row['imagePath']
        if row.get('type') not in ('weapon', 'melee', 'glove') or definition not in weapon_definitions:
            continue
        paint = row.get('variantIndex', 0)
        key = f'{definition}:{paint}'
        if key in items and items[key] != row['id']:
            raise ValueError(f'Ambiguous viewer appearance: {key}')
        items[key] = row['id']
        parent = by_id.get(row.get('parentId'), row)
        prefix = 'legacySticker' if row.get('isLegacyModel') else 'sticker'
        count = parent.get(prefix + 'SchemaCount')
        if not count:
            continue
        models[str(row['id'])] = {
            'x_min': parent[prefix + 'OffsetXMin'],
            'x_max': parent[prefix + 'OffsetXMax'],
            'y_min': parent[prefix + 'OffsetYMin'],
            'y_max': parent[prefix + 'OffsetYMax'],
            'schema_count': count, 'rotation_min': -180, 'rotation_max': 180,
            'model_variant': 'legacy' if row.get('isLegacyModel') else 'hd',
        }
    missing = sticker_definitions - {int(key) for key in stickers}
    if missing:
        raise ValueError(f'Missing sticker mappings: {sorted(missing)}')
    return {'schema_version': 1, 'source_commit': COMMIT, 'source_url': URL,
            'embed_url': 'https://3d.cstrike.app/view',
            'source_notice': 'cs2-lib MIT metadata only; the hosted renderer is a separate online service.',
            'items': items, 'stickers': stickers, 'images': images, 'models': models}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    if args.cache.resolve().drive.upper() == 'C:':
        parser.error('Use a D/E cache, not C:')
    args.cache.mkdir(parents=True, exist_ok=True)
    cached = args.cache / f'cs2-lib-items-{COMMIT}.json'
    if not cached.exists():
        with urllib.request.urlopen(URL, timeout=30) as response:
            payload = response.read(12 * 1024 * 1024 + 1)
        if len(payload) > 12 * 1024 * 1024:
            raise ValueError('Unexpected oversized catalog')
        json.loads(payload)
        cached.write_bytes(payload)
    payload = cached.read_bytes()
    # Seven existing supported guns plus catalogued knives/gloves. This compact
    # subset still includes all finishes for those models, allowing skin packs.
    from cs2career.career import skins
    definitions = {skins._def_of(row) for row in skins.catalog()['skins']}
    pro = json.loads((ROOT / 'cs2career/data/public_pro_loadouts.json').read_text(encoding='utf-8'))
    definitions.update(row['def'] for row in pro['skin_catalog'])
    known = json.loads((ROOT / 'cs2career/data/stickers.json').read_text(encoding='utf-8'))
    result = build(json.loads(payload), definitions, {row['def'] for row in known['stickers']})
    result['source_sha256'] = hashlib.sha256(payload).hexdigest()
    output = ROOT / 'cs2career/data/inspect_catalog.json'
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f"Built {len(result['items'])} appearances, {len(result['stickers'])} sticker mappings; {output.stat().st_size} bytes")


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(ROOT))
    main()
