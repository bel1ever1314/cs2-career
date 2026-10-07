"""Prepare pinned genuine in-game club marks, never fetch during a UI refresh."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.client import HTTPException
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
from xml.etree import ElementTree

COMMIT = '85ec43bd170d0622db8eadf160e666c161976375'
BASE = f'https://raw.githubusercontent.com/Juknum/counter-strike-icons/{COMMIT}/cs2/panorama/images/tournaments/teams/'
# Explicit asset IDs, no fuzzy or random mark matching.
CODES = {'Falcons':'fal','Vitality':'vita','Spirit':'spir','FURIA':'furi','NAVI':'navi',
         'Aurora':'aura','BetBoom':'bb','MOUZ':'mouz','G2':'g2','The MongolZ':'mngz',
         'Legacy':'lgcy','FaZe':'faze','PARIVISION':'pari','paiN':'pain','GamerLegion':'gl',
         'Liquid':'liq','Astralis':'astr','B8':'b8','3DMAX':'3dm','TYLOO':'tyl','BIG':'big',
         'MIBR':'mibr','NiP':'nip','HEROIC':'hero','FlyQuest':'fq','Lynn Vision':'lynn',
         'M80':'m80','9z':'zzn','Imperial':'imp','OG':'og','FUT':'fut','NRG':'nrg',
         'Virtus.pro':'vp','100 Thieves':'thv','Rare Atom':'ratm','SINNERS':'sinn',
         'Fluxo':'flux','9INE':'nein','Luminosity':'lumi','Sharks':'shrk','ENCE':'ence',
         'fnatic':'fntc','SAW':'saw','Passion UA':'psnu','Complexity':'col','BESTIA':'bes',
         'Chinggis Warriors':'cw','Cloud9':'c9',
         'Eternal Fire':'eter','Monte':'mont','Grayhound':'gray','FORZE':'forz',
         'Apeks':'apex','KOI':'koi','9 Pandas':'pand','Nemiga':'nemi',
         'RED Canids':'redc','Wildcard':'wcrd'}

ADOBE_NAMESPACES = {
    'ns_extend':'http://ns.adobe.com/Extensibility/1.0/',
    'ns_ai':'http://ns.adobe.com/AdobeIllustrator/10.0/',
    'ns_graphs':'http://ns.adobe.com/Graphs/1.0/',
    'ns_vars':'http://ns.adobe.com/Variables/1.0/',
    'ns_imrep':'http://ns.adobe.com/ImageReplacement/1.0/',
    'ns_sfw':'http://ns.adobe.com/SaveForWeb/1.0/',
    'ns_custom':'http://ns.adobe.com/GenericCustomNamespace/1.0/',
    'ns_adobe_xpath':'http://ns.adobe.com/XPath/1.0/',
}


def sanitize_svg(content):
    """Keep paths/groups byte-for-byte; discard only Illustrator export metadata.

    No DTD is passed to XML/Godot. Eight fixed namespace aliases are the only
    accepted entity declarations, and they cannot refer to files or URLs as
    resources. Foreign objects must be the known Illustrator PGF reference.
    """
    if not isinstance(content, bytes) or len(content) > 512000:
        raise ValueError('SVG size is unsupported')
    value = content.decode('utf-8-sig')
    declarations = list(re.finditer(r'<!DOCTYPE\b', value, re.IGNORECASE))
    if len(declarations) > 1:
        raise ValueError('Multiple SVG doctypes are unsupported')
    entities = {}
    if declarations:
        start, depth, quoted, finish = declarations[0].start(), 0, '', None
        for offset in range(start, len(value)):
            char = value[offset]
            if quoted:
                if char == quoted:
                    quoted = ''
            elif char in ('"', "'"):
                quoted = char
            elif char == '[':
                depth += 1
            elif char == ']':
                depth -= 1
            elif char == '>' and depth == 0:
                finish = offset + 1
                break
        if finish is None or depth != 0:
            raise ValueError('Malformed SVG doctype')
        declaration = value[start:finish]
        if not re.match(r'<!DOCTYPE\s+svg(?:\s|>)', declaration, re.IGNORECASE):
            raise ValueError('Unexpected SVG doctype')
        subset = declaration[declaration.find('[') + 1:declaration.rfind(']')] if '[' in declaration else ''
        pattern = r'<!ENTITY\s+(ns_[a-z_]+)\s+([\'\"])([^\'\"]+)\2\s*>'
        for item in re.finditer(pattern, subset):
            name, namespace = item[1], item[3]
            if name not in ADOBE_NAMESPACES or namespace != ADOBE_NAMESPACES[name] or name in entities:
                raise ValueError('SVG namespace entity is not a fixed Adobe alias')
            entities[name] = namespace
        if re.sub(pattern, '', subset).strip():
            raise ValueError('SVG contains an unsupported entity or DTD directive')
        value = value[:start] + value[finish:]
    for name, namespace in entities.items():
        value = value.replace('&' + name + ';', namespace)
    if re.search(r'<!ENTITY|<!DOCTYPE|<\?(?!xml\s)', value, re.IGNORECASE):
        raise ValueError('SVG declarations are unsupported')
    try:
        tree = ElementTree.fromstring(value)
    except ElementTree.ParseError as exc:
        raise ValueError('SVG XML cannot be parsed without custom entities') from exc
    if tree.tag != '{http://www.w3.org/2000/svg}svg':
        raise ValueError('SVG root is unsupported')
    foreign_count = 0
    for node in tree.iter():
        local = node.tag.rsplit('}', 1)[-1].lower()
        if local == 'script':
            raise ValueError('SVG scripts are unsupported')
        for attribute, text in node.attrib.items():
            field = attribute.rsplit('}', 1)[-1].lower()
            if field.startswith('on') or (field == 'href' and not text.startswith('#')):
                raise ValueError('SVG executable or external references are unsupported')
        for text in [node.text or '', *node.attrib.values()]:
            if '@import' in text.lower():
                raise ValueError('SVG external styles are unsupported')
            if any(not url.strip().strip('\'"').startswith('#') for url in re.findall(r'url\s*\((.*?)\)', text, re.IGNORECASE)):
                raise ValueError('SVG external paint resources are unsupported')
        if local == 'foreignobject':
            children = list(node)
            if (node.attrib.get('requiredExtensions') != ADOBE_NAMESPACES['ns_ai']
                    or len(children) != 1 or children[0].tag != '{' + ADOBE_NAMESPACES['ns_ai'] + '}aipgfRef'
                    or list(children[0]) or (node.text or '').strip() or (children[0].text or '').strip()
                    or children[0].attrib.get('{http://www.w3.org/1999/xlink}href') != '#adobe_illustrator_pgf'):
                raise ValueError('SVG foreign objects must be Illustrator PGF metadata')
            foreign_count += 1
    value, removed = re.subn(r'<foreignObject\b[^>]*>.*?</foreignObject\s*>', '', value, flags=re.IGNORECASE | re.DOTALL)
    if removed != foreign_count or re.search(r'<(?:[\w-]+:)?foreignObject\b', value, re.IGNORECASE):
        raise ValueError('SVG foreign object cannot be safely removed')
    return value.encode('utf-8')


def main():
    root = Path('E:/CS2CareerTools/Career3DMedia/teams')
    root.mkdir(parents=True, exist_ok=True)
    originals = root / 'source'
    originals.mkdir(exist_ok=True)
    def fetch(item):
        name, code = item
        target = root / (code + '.svg')
        raw_target = originals / (code + '.svg')
        url = BASE + code + '.svg'
        # Keep the original pinned bytes separately so repeat builds preserve
        # provenance instead of hashing yesterday's sanitized derivative.
        content = raw_target.read_bytes() if raw_target.is_file() else None
        last_error = None
        if content is None:
            for _ in range(4):
                try:
                    content = urlopen(Request(url, headers={'User-Agent':'CS2Career-media-preparer'}), timeout=20).read(512001)
                    break
                except (OSError, HTTPException, URLError) as exc:
                    last_error = exc
            if content is None: return name, {'status':'unavailable','reason':str(last_error),'source':url}
        original_hash = hashlib.sha256(content).hexdigest()
        try:
            sanitized = sanitize_svg(content)
        except ValueError as exc:
            raise ValueError('Unsupported mark: ' + name + ': ' + str(exc)) from exc
        if not raw_target.is_file(): raw_target.write_bytes(content)
        if not target.is_file() or target.read_bytes() != sanitized: target.write_bytes(sanitized)
        return name, {'kind':'club_logo','path':str(target),'source':url,'asset_code':code,
                      'source_commit':COMMIT,'sha256':hashlib.sha256(sanitized).hexdigest(), 'original_sha256':original_hash,
                      'original_path':str(raw_target)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = dict(pool.map(fetch, CODES.items()))
    manifest = {'schema_version':1,'team_backgrounds':rows,'source_project':'https://github.com/Juknum/counter-strike-icons',
                'rights':'Marks belong to their teams/Valve; this is not an AGPL grant for the marks.'}
    target = root / 'team-media.json'
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({'logos':sum(r.get('kind')=='club_logo' for r in rows.values()),'unavailable':[n for n,r in rows.items() if r.get('status')=='unavailable'],'manifest':str(target)},ensure_ascii=False))


if __name__ == '__main__': main()
