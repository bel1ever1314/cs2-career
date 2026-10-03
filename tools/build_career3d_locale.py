"""Compile authored 3D UI copy with the existing desktop/narrative catalogues.

The build is reproducible and read-only by default. --patch emits an apply_patch
document so repository edits use the same reviewable file editing workflow.
Unknown user/extension prose is intentionally never translated by fragments.
"""
from pathlib import Path
import ast
import argparse
import difflib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'work/career3d_redesign'
TARGET = PROJECT / 'data/locale_en.json'
AUTHORED = PROJECT / 'data/locale_3d_en.txt'
PRINTF = re.compile(r'%(?:[-+0 #]*\d*(?:\.\d+)?)?[sdf]')
BRACES = re.compile(r'\{([a-z_][a-z_0-9]*)\}')
RUNTIME_COMPAT_PHRASES = {
    '兼容组件下载大小不正确。': 'The compatibility component download has an incorrect size.',
    '兼容组件下载大小不符：%s，没有安装。': 'The compatibility component download size does not match: %s. Nothing was installed.',
}


def authored():
    pairs = {}
    for path in [AUTHORED, *sorted((PROJECT/'data').glob('locale_backend*_en.txt'))]:
        for index, line in enumerate(path.read_text('utf-8').splitlines(), 1):
            if not line or line.startswith('#'): continue
            if '\t' not in line: raise ValueError(f'Invalid translation {path.name}:{index}')
            source, english = line.split('\t', 1)
            source, english = source.replace('\\n', '\n'), english.replace('\\n', '\n')
            if not english or re.search(r'[\u3400-\u9fff]', english): raise ValueError(f'Invalid English {path.name}:{index}')
            if PRINTF.findall(source) != PRINTF.findall(english): raise ValueError(f'Changed formatting slots {path.name}:{index}')
            if BRACES.findall(source) and sorted(BRACES.findall(source)) != sorted(BRACES.findall(english)): raise ValueError(f'Changed named slots {path.name}:{index}')
            pairs[source] = english
    return pairs


def template(source, english):
    keys, parts, position = [], [], 0
    tokens = list(PRINTF.finditer(source)) or list(BRACES.finditer(source))
    if not tokens: return None
    for index, token in enumerate(tokens):
        parts.append(re.escape(source[position:token.start()].replace('%%', '%')))
        keys.append(str(index) if token[0].startswith('%') else token[1])
        parts.append('([\\s\\S]+?)' if token[0].startswith('%') and token[0].endswith('s') or token[0].startswith('{') else '([+-]?[\\d,.]+)')
        position = token.end()
    parts.append(re.escape(source[position:].replace('%%', '%')))
    if tokens[0][0].startswith('%'):
        counter = iter(range(len(tokens)))
        replacement = PRINTF.sub(lambda match: '{'+str(next(counter))+'}', english).replace('%%', '%')
    else: replacement = english
    return dict(source=source, pattern='^'+''.join(parts)+'$', replacement=replacement, keys=keys, prefix=source[:tokens[0].start()])


def compile_catalogue():
    # Require the canonical JS module rather than duplicating or parsing JS syntax.
    result = subprocess.run(['node', '-e', "process.stdout.write(JSON.stringify(require('./cs2career/web/static/desk/locales/en.js').phrases))"],
                            cwd=ROOT, check=True, capture_output=True, text=True, encoding='utf-8')
    pairs = json.loads(result.stdout)
    sys.path.insert(0, str(ROOT))
    from cs2career.career.localization import phrases
    pairs.update(phrases())
    pairs.update(RUNTIME_COMPAT_PHRASES)
    def bilingual(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.endswith('_en') and isinstance(item, str) and isinstance(value.get(key[:-3]), str):
                    pairs[value[key[:-3]]] = item
                bilingual(item)
        elif isinstance(value, list):
            for item in value: bilingual(item)
    for path in [ROOT/'cs2career/data/career3d_environment.json']:
        if path.exists(): bilingual(json.loads(path.read_text('utf-8')))
    pairs.update(authored())
    templates = [row for source, english in pairs.items() if (row := template(source, english))]
    # Concatenated UI prefixes/suffixes are authored as complete source fragments,
    # never discovered by replacing individual Chinese words in arbitrary prose.
    for source, english in list(pairs.items()):
        if len(source.strip()) < 2 or PRINTF.search(source) or BRACES.search(source): continue
        if source.endswith((' ', '：', '¥')) and not source.startswith(' '):
            templates.append(dict(source=source+'{tail}', pattern='^'+re.escape(source)+'([\\s\\S]+)$', replacement=english+'{tail}', keys=['tail'], prefix=source))
        if source.startswith(' ') and not source.endswith(' '):
            templates.append(dict(source='{head}'+source, pattern='^([\\s\\S]+?)'+re.escape(source)+'$', replacement='{head}'+english, keys=['head'], prefix=''))
        if source.strip() != source and '\n' not in source:
            pairs.setdefault(source.strip(), english.strip())
    # More specific templates take precedence over broad author-provided slots.
    templates.sort(key=lambda row: len(row['source']) - sum(len(key) for key in row['keys']), reverse=True)
    return dict(schema_version=1, phrases=pairs, templates=templates)


def sources():
    rows = {}
    scripts = sorted((PROJECT / 'scripts').glob('*.gd')) + sorted((ROOT/'work/career_rts/scripts').glob('*.gd'))
    for path in scripts:
        for match in re.finditer(r'"((?:[^"\\]|\\.)*)"', path.read_text('utf-8')):
            value = match[1].replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
            if re.search(r'[\u3400-\u9fff]', value): rows.setdefault(value, path.name)
    for path in [PROJECT / 'data/club_life.json', PROJECT / 'data/phone_social.json', PROJECT / 'data/interactions.json']:
        if not path.exists(): continue
        def visit(value):
            if isinstance(value, str) and re.search(r'[\u3400-\u9fff]', value): rows.setdefault(value, path.name)
            elif isinstance(value, dict):
                for key, item in value.items():
                    if key not in ('name', 'notes', '_notes', 'documentation', 'coordinate_system', 'schema_version') and not key.startswith('_'): visit(item)
            elif isinstance(value, list):
                for item in value: visit(item)
        visit(json.loads(path.read_text('utf-8')))
    for path in sorted((ROOT/'tools').glob('career3d*.py')) + [ROOT/'cs2career/manual_saves.py']:
        if path.stem in ('career3d_locale',) or path.stem.startswith('career3d_package'): continue
        tree = ast.parse(path.read_text('utf-8-sig'))
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        docstrings = {node.body[0].value for node in ast.walk(tree)
                      if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                      and node.body and isinstance(node.body[0], ast.Expr)
                      and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str)}
        def literal(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str): return node.value
            if isinstance(node, ast.JoinedStr): return ''.join(literal(part) if isinstance(part, ast.Constant) else '%s' for part in node.values)
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add): return literal(node.left) + literal(node.right)
            return '%s'
        for node in ast.walk(tree):
            parent = parents.get(node)
            if node in docstrings or isinstance(parent, ast.JoinedStr): continue
            if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Add): continue
            if isinstance(node, (ast.Constant, ast.JoinedStr)) or isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                value = literal(node)
                if re.search(r'[\u3400-\u9fff]', value): rows.setdefault(value, path.name)
    return rows


def covered(source, catalogue):
    return source in catalogue['phrases'] or any(re.fullmatch(row['pattern'], source) for row in catalogue['templates'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--missing', action='store_true')
    parser.add_argument('--patch', action='store_true')
    parser.add_argument('--file', default='')
    args = parser.parse_args()
    catalogue = compile_catalogue()
    if args.missing:
        for source, filename in sources().items():
            if not covered(source, catalogue) and (not args.file or args.file in filename): print(filename+'\t'+source.replace('\n','\\n'))
    else:
        content = json.dumps(catalogue, ensure_ascii=False, indent=2)+'\n'
        if args.patch:
            print('*** Begin Patch')
            if TARGET.exists():
                print('*** Update File: '+str(TARGET))
                difference = list(difflib.unified_diff(TARGET.read_text('utf-8').splitlines(), content.splitlines(), n=3))
                for line in difference[2:]: print('@@' if line.startswith('@@') else line)
            else:
                print('*** Add File: '+str(TARGET))
                print('\n'.join('+'+line for line in content.splitlines()))
            print('*** End Patch')
        else: print(content, end='')


if __name__ == '__main__': main()
