import json, sys, time
from pathlib import Path
import sf2, mlib, tracks
import os
sf = sf2.SoundFont(os.environ.get('CAREER_SF2', str(Path(__file__).with_name('gu.sf2'))))
out = Path(__file__).with_name('out')
names = sys.argv[1:]
manifest = []
for fn in tracks.TRACKS:
    if names and fn.__name__ not in names: continue
    t = time.time()
    song = fn()
    info = mlib.render(song, sf, out)
    info['render_seconds'] = round(time.time() - t, 1)
    manifest.append(info)
    print(json.dumps(info, ensure_ascii=False))
if not names:
    json.dump(manifest, open(out / 'music_manifest.json', 'w'), ensure_ascii=False, indent=1)
