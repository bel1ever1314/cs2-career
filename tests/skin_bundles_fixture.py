"""Generate actual bundle UI data in an explicit D/E QA project, offline."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cs2career.career import skins
from cs2career.paths import data_file
from tests.test_career3d_skin_bundles import MemoryCareer
from tools.career3d_skin_bundles import bundle_context


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    if target.drive.upper() not in ('D:', 'E:') or target.exists() or not target.parent.is_dir():
        parser.error('Choose a new fixture JSON in an existing explicit D/E QA folder.')
    catalog = json.loads(data_file('skins.json').read_text(encoding='utf-8'))
    def local_art(skin_id, art):
        row = art.get('items', {}).get(skin_id) or {}
        if row.get('status') != 'mapped' or not row.get('url'): return ''
        name = hashlib.sha256(row['url'].encode()).hexdigest() + '.png'
        cached = Path('E:/CS2CareerTools/Career3DMedia/skin_art') / name
        return str(cached.resolve()) if cached.is_file() else ''
    state = SimpleNamespace(career=MemoryCareer())
    with patch.object(skins, 'catalog', return_value=deepcopy(catalog)), \
            patch('tools.career3d_resources.cached_skin_art', side_effect=local_art):
        skins.pro_bundle.cache_clear()
        bundles = bundle_context(state)
    payload = {'fixture': True, 'backend': 'memory only', 'shop': {
        'personal_money': state.career.money, 'loadout_packs': bundles,
        'market': [], 'inventory': [], 'cases': [], 'pending': None}}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'fixture': str(target), 'packs': len(bundles),
                      'items': sum(row['count'] for row in bundles),
                      'prices': {row['display_name']: row['price'] for row in bundles},
                      'local_art_items': sum(bool(item['art_path']) for row in bundles for item in row['items'])}, ensure_ascii=False))


if __name__ == '__main__': main()
