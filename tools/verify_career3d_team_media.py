"""Pinned-logo sanitizer and all 48 generated asset provenance checks."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_career3d_team_media import ADOBE_NAMESPACES, CODES, COMMIT, sanitize_svg
from tools.career3d_resources import resource_context


def main():
    drawing = '<path d="M 0 0 L 1 1" fill="#fff"/>'
    plain = ('<svg xmlns="http://www.w3.org/2000/svg">' + drawing + '</svg>').encode()
    assert sanitize_svg(plain) == plain
    metadata = (f'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd" ['
                f'<!ENTITY ns_ai "{ADOBE_NAMESPACES["ns_ai"]}">]>'
                '<svg xmlns="http://www.w3.org/2000/svg" xmlns:i="&ns_ai;" xmlns:xlink="http://www.w3.org/1999/xlink">'
                '<switch><foreignObject requiredExtensions="&ns_ai;"><i:aipgfRef xlink:href="#adobe_illustrator_pgf"/></foreignObject>'
                '<g>' + drawing + '</g></switch></svg>').encode()
    safe = sanitize_svg(metadata)
    assert b'<!DOCTYPE' not in safe and b'<!ENTITY' not in safe and b'foreignObject' not in safe
    assert drawing.encode() in safe and b'<g>' in safe and ADOBE_NAMESPACES['ns_ai'].encode() in safe
    rejected = [
        b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///private">]><svg xmlns="http://www.w3.org/2000/svg">&x;</svg>',
        b'<!DOCTYPE svg [<!ENTITY ns_ai "https://untrusted.invalid/ns">]><svg xmlns="http://www.w3.org/2000/svg"/>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
        b"<svg xmlns='http://www.w3.org/2000/svg'><image href='https://untrusted.invalid/pixel.png'/></svg>",
        b'<svg xmlns="http://www.w3.org/2000/svg"><path fill="url(https://untrusted.invalid/paint)"/></svg>',
        b'<?xml-stylesheet href="https://untrusted.invalid/style"?><svg xmlns="http://www.w3.org/2000/svg"/>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><body/></foreignObject></svg>',
    ]
    for value in rejected:
        try:
            sanitize_svg(value)
        except ValueError:
            continue
        raise AssertionError('Sanitizer accepted executable/external SVG content')
    manifest = json.loads(Path('E:/CS2CareerTools/Career3DMedia/teams/team-media.json').read_text('utf-8'))
    assert set(manifest['team_backgrounds']) == set(CODES)
    for name, code in CODES.items():
        row = manifest['team_backgrounds'][name]
        original, derivative = Path(row['original_path']).read_bytes(), Path(row['path']).read_bytes()
        assert row['kind'] == 'club_logo' and row['asset_code'] == code and row['source_commit'] == COMMIT
        assert row['original_sha256'] == hashlib.sha256(original).hexdigest()
        assert row['sha256'] == hashlib.sha256(derivative).hexdigest()
        assert sanitize_svg(original) == derivative
        assert row['source'].endswith('/' + code + '.svg')
    previous_config = os.environ.get('CS2CAREER3D_MEDIA_CONFIG')
    try:
        os.environ['CS2CAREER3D_MEDIA_CONFIG'] = str(ROOT / 'work/career3d_redesign/data/media.json')
        projection = resource_context()['media']
        assert set(projection['team_backgrounds']) == set(CODES)
        assert set(projection['team_sources']) == set(CODES)
        for name in CODES:
            assert Path(projection['team_backgrounds'][name]) == Path(manifest['team_backgrounds'][name]['path'])
            assert projection['team_sources'][name] == manifest['team_backgrounds'][name]['source']
    finally:
        if previous_config is None:
            os.environ.pop('CS2CAREER3D_MEDIA_CONFIG', None)
        else:
            os.environ['CS2CAREER3D_MEDIA_CONFIG'] = previous_config
    print(json.dumps(dict(ok=True, logos=len(CODES), checks=[
        'plain drawing is byte-preserved; fixed Adobe namespaces/PGF metadata sanitize without altering paths/groups',
        'scripts, arbitrary entities, foreign bodies, external href/CSS/processing instructions are rejected',
        'all 48 explicit club mappings retain original bytes/hash, derivative hash and pinned source attribution',
        'read-only media projection retains all 48 exact names, paths and pinned source URLs']), ensure_ascii=False))


if __name__ == '__main__':
    main()
