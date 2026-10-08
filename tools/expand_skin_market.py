"""Reproducible, pinned catalog/media import (build-time only, never in game).

Valve artwork remains credited. This mechanical importer preserves legacy IDs
and prices, corrects exact model/finish mappings and bundles offline thumbnails.
"""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://raw.githubusercontent.com/ByMykel/CSGO-API/cee33b1c28827cec79cad581a8775e9a51f3f573/public/api/en/skins.json'
SLOTS = {7:'ak47',60:'m4a1',16:'m4a4',9:'awp',1:'deagle',61:'usp',4:'glock',17:'mac10'}
RARITIES = {'Consumer Grade':'consumer','Industrial Grade':'industrial','Mil-Spec Grade':'milspec',
            'Restricted':'restricted','Classified':'classified','Covert':'covert','Extraordinary':'extraordinary','Contraband':'contraband'}
POPULAR = ('Dragon Lore','Fade','Doppler','Asiimov','Redline','Printstream','Wild Lotus','Vulcan',
           'The Empress','Fire Serpent','Bloodsport','Neo-Noir','The Prince','Gungnir','Desert Hydra',
           'Hyper Beast','Golden Coil','Welcome to the Jungle','Howl','Temukau','In Living Color',
           'Kill Confirmed','Monster Mashup','Jawbreaker','Gamma Doppler','Pandora','Vice','Slaughter',
           'Crimson','Marble Fade','Tiger Tooth','Case Hardened','Emerald','Cobalt','Slingshot')


def fetch(url):
    for attempt in range(4):
        try:
            with urlopen(Request(url,headers={'User-Agent':'CS2Career-local-market-import'}),timeout=20) as response:
                return response.read()
        except OSError:
            if attempt==3: raise
            time.sleep(attempt+1)


def clean(name):
    return name.removeprefix('★ ').strip()


def main():
    raw = json.loads(fetch(SOURCE))
    existing = json.loads((ROOT/'cs2career/data/skins.json').read_text('utf-8'))
    art_path = ROOT/'cs2career/data/skin_art.json'
    art = json.loads(art_path.read_text('utf-8'))
    supported = []
    for row in raw:
        definition = int(row['weapon']['weapon_id'])
        if definition not in SLOTS and not 500 <= definition <= 525 and not 5027 <= definition <= 5035:
            continue
        supported.append(row)
    names = {clean(r['name']):r for r in supported}
    keys = {}
    for row in supported:
        keys.setdefault((int(row['weapon']['weapon_id']),int(row.get('paint_index') or 0)),row)
    chosen = []
    used = set()
    fixes = []
    for old in existing['skins']:
        wanted = old['name'].replace('M4A1-S | Temukau','M4A4 | Temukau').replace('M4A1-S | In Living Color','M4A4 | In Living Color').replace('Desert Eagle | Sienna Damask','MAC-10 | Sienna Damask')
        found = names.get(wanted) or (names.get(wanted.replace(' | Vanilla','')) if 'Vanilla' in wanted else None)
        if not found:
            raise ValueError('No exact named finish: '+wanted)
        chosen.append((old,found))
        used.add((int(found['weapon']['weapon_id']),int(found.get('paint_index') or 0)))
    pool = sorted(keys.values(), key=lambda r:(not any(p in r['name'] for p in POPULAR),
                  -list(RARITIES).index(r['rarity']['name']) if r['rarity']['name'] in RARITIES else 0, r['name']))
    counts = {slot:sum(SLOTS.get(int(r['weapon']['weapon_id']), 'knife' if int(r['weapon']['weapon_id'])<1000 else 'gloves')==slot for _,r in chosen)
              for slot in (*SLOTS.values(),'knife','gloves')}
    limits = {**{slot:15 for slot in SLOTS.values()},'mac10':5,'ak47':20,'awp':20,'knife':20,'gloves':10}
    for row in pool:
        key = int(row['weapon']['weapon_id']),int(row.get('paint_index') or 0)
        slot = SLOTS.get(key[0], 'knife' if key[0]<1000 else 'gloves')
        if key in used or counts[slot]>=limits[slot]:
            continue
        chosen.append((None,row)); used.add(key); counts[slot]+=1
        if len(chosen)>=150:
            break
    result=[]
    for old,row in chosen:
        definition,paint=int(row['weapon']['weapon_id']),int(row.get('paint_index') or 0)
        slot=SLOTS.get(definition,'knife' if definition<1000 else 'gloves')
        rarity='extraordinary' if slot in ('knife','gloves') else RARITIES[row['rarity']['name']]
        base={'consumer':60,'industrial':120,'milspec':260,'restricted':650,'classified':2400,'covert':6000,'extraordinary':18000,'contraband':45000}[rarity]
        price=round(base*(.75+(int(hashlib.sha256(row['name'].encode()).hexdigest()[:4],16)%101)/100))
        out={**(old or {}),'id':old['id'] if old else f'market-{definition}-{paint}',
             'name':clean(row['name']),'weapon':row['weapon']['name'],'slot':slot,'rarity':rarity,
             'def':definition,'paint':paint,'buy':old['buy'] if old else price,
             'sell':old.get('sell',round(price*.9)) if old else round(price*.9),
             'min_float':float(row.get('min_float') or 0),'max_float':float(row.get('max_float') if row.get('max_float') is not None else 1)}
        if old and (old.get('def'),old.get('paint'),old['name'])!=(definition,paint,out['name']):
            fixes.append(dict(id=out['id'],before=[old.get('def'),old.get('paint'),old['name']],after=[definition,paint,out['name']]))
        url=row['image']
        if not url.startswith(('https://community.akamai.steamstatic.com/economy/image/','https://raw.githubusercontent.com/ByMykel/counter-strike-image-tracker/')):
            raise ValueError('Unexpected image source')
        art['items'][out['id']]={'status':'mapped','url':url,'def':definition,'paint':paint,'source_name':row['name']}
        result.append(out)
    if len(result)!=150:
        raise ValueError(f'Expected 150, got {len(result)}')
    destination=ROOT/'cs2career/data/skin_images'
    destination.mkdir(exist_ok=True)
    def download(row):
        url=art['items'][row['id']]['url']
        path=destination/(hashlib.sha256(url.encode()).hexdigest()+'.png')
        if path.is_file():
            return row['id']
        blob=fetch(url)
        if not blob.startswith(b'\x89PNG\r\n\x1a\n') or len(blob)>4*1024*1024:
            raise ValueError('Invalid image: '+row['id'])
        path.write_bytes(blob)
        return row['id']
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for i,_ in enumerate(pool.map(download,result),1):
            if i%25==0: print(f'Offline images {i}/150',flush=True)
    existing.update(skins=result,market=[r['id'] for r in result],market_source=SOURCE,
                    market_notice='Local simulated prices. Valve game artwork; metadata from pinned ByMykel/CSGO-API.')
    (ROOT/'cs2career/data/skins.json').write_text(json.dumps(existing,ensure_ascii=False,indent=2)+'\n','utf-8')
    art.update(source=SOURCE,notice='Valve artwork, bundled for offline local display; no online inventory or real-money market.')
    art_path.write_text(json.dumps(art,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(dict(total=len(result),counts=counts,corrected=fixes),ensure_ascii=False))


if __name__=='__main__':
    main()
