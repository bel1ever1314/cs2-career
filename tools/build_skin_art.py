"""Generate an exact def/paint artwork manifest; never infer from a nickname.

Only the manifest is shipped. Valve artwork is fetched into the user's cache
from the pinned game-asset mirror, rather than silently bundled for resale.
"""
import json
import argparse
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def fetch(url):
    with urlopen(Request(url, headers={'User-Agent': 'CS2Career-art-manifest'}), timeout=30) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit')
    parser.add_argument('--image-commit')
    args = parser.parse_args()
    repo = 'ByMykel/CSGO-API'
    commit = args.commit or fetch(f'https://api.github.com/repos/{repo}/commits/main')['sha']
    image_repo = 'ByMykel/counter-strike-image-tracker'
    image_commit = args.image_commit or fetch(f'https://api.github.com/repos/{image_repo}/commits/main')['sha']
    source = f'https://raw.githubusercontent.com/{repo}/{commit}/public/api/en/skins.json'
    data = fetch(source)
    index = {}
    for row in data:
        try:
            key = int(row['weapon']['weapon_id']), int(row['paint_index'])
        except (KeyError, TypeError, ValueError):
            continue
        index.setdefault(key, row)
    catalog = json.loads((ROOT/'cs2career/data/skins.json').read_text(encoding='utf-8'))
    rows = {}
    for skin in catalog['skins']:
        found = index.get((int(skin.get('def') or 0), int(skin.get('paint') or 0)))
        if not found:
            rows[skin['id']] = {'status': 'unmatched', 'reason': 'No exact weapon/paint match'}
            continue
        image = found.get('image', '').replace(f'/{image_repo}/main/', f'/{image_repo}/{image_commit}/')
        if not (image.startswith(f'https://raw.githubusercontent.com/{image_repo}/{image_commit}/') or image.startswith('https://community.akamai.steamstatic.com/economy/image/')):
            rows[skin['id']] = {'status': 'unmatched', 'reason': 'Artwork outside approved source'}
            continue
        rows[skin['id']] = {'status': 'mapped', 'url': image, 'def': skin['def'], 'paint': skin['paint'], 'source_name': found['name']}
    result = {'schema_version': 1, 'source': source, 'image_commit': image_commit,
              'notice': 'Unofficial metadata; artwork belongs to Valve. Cached for local display.', 'items': rows}
    target = ROOT/'cs2career/data/skin_art.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'mapped': sum(r['status']=='mapped' for r in rows.values()), 'total': len(rows), 'commit': commit}))


if __name__ == '__main__':
    main()
