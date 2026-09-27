"""Authored narrative translations, never automatic rewriting or game rules.

The source snapshot binds English to the exact Chinese it translates. Editing
Chinese copy invalidates that field's translation until an author updates it.
Public presentation can also translate unchanged old saved prose, without
editing its choices, rewards, IDs or source text. Unknown pack text stays intact.
"""
from copy import deepcopy
from functools import lru_cache
import json
import re
from ..paths import data_file


@lru_cache(maxsize=1)
def catalog():
    return (json.loads(data_file('story_locale_sources.json').read_text('utf-8')),
            json.loads(data_file('story_locale_en.json').read_text('utf-8')))


def enrich(name, raw):
    source, english = catalog()
    out = deepcopy(raw)
    def node(current, original, translated):
        for field in ('title', 'text', 'name', 'texts'):
            if field+'_en' in translated and current.get(field) == original.get(field):
                current.setdefault(field+'_en', deepcopy(translated[field+'_en']))
        originals = {c['id']: c for c in original.get('choices', [])}
        for choice in current.get('choices', []):
            cid = choice['id']
            if cid in translated.get('choices', {}) and choice.get('label') == originals.get(cid, {}).get('label'):
                choice.setdefault('label_en', translated['choices'][cid])
    if name == 'stories':
        originals = {r['id']: r for r in source[name]['stories']}
        for row in out['stories']:
            node(row, originals.get(row['id'], {}), english[name].get(row['id'], {}))
    else:
        for section in ('chapters', 'endings'):
            for key, row in out.get(section, {}).items():
                node(row, source.get(name, {}).get(section, {}).get(key, {}), english.get(name, {}).get(section, {}).get(key, {}))
        originals = {r['id']:r for r in source.get(name, {}).get('injuries', [])}
        for row in out.get('injuries', []):
            node(row, originals.get(row['id'], {}), english.get(name, {}).get('injuries', {}).get(row['id'], {}))
        for key, values in out.get('birthday', {}).copy().items():
            if values == source.get(name, {}).get('birthday', {}).get(key) and key in english.get(name, {}).get('birthday', {}):
                out['birthday'][key+'_en'] = deepcopy(english[name]['birthday'][key])
    return out


@lru_cache(maxsize=1)
def phrases():
    pairs = {}
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.endswith('_en') and key[:-3] in value:
                    zh = value[key[:-3]]
                    if isinstance(zh, str) and isinstance(item, str): pairs[zh] = item
                    elif isinstance(zh, list) and isinstance(item, list) and len(zh) == len(item):
                        pairs.update((a,b) for a,b in zip(zh,item) if isinstance(a,str) and isinstance(b,str))
                visit(item)
        elif isinstance(value, list):
            for item in value: visit(item)
    for name, raw in catalog()[0].items(): visit(enrich(name, raw))
    pairs.update(json.loads(data_file('story_messages_en.json').read_text('utf-8')))
    return pairs


@lru_cache(maxsize=1)
def templates():
    result=[]
    for zh, en in phrases().items():
        keys=[];parts=[];position=0
        for match in re.finditer(r'\{([a-z_]+)\}', zh):
            parts.append(re.escape(zh[position:match.start()])); key=match[1]
            parts.append('(?P='+key+')' if key in keys else '(?P<'+key+'>.+?)')
            keys.append(key); position=match.end()
        if keys:
            parts.append(re.escape(zh[position:]))
            result.append((zh.split('{',1)[0],re.compile(''.join(parts),re.S),en))
    return result


SEMANTIC = {'partner','opinion','support','assessment','changes','role','class_label'}
AXES_EN = {'火力':'Firepower','突破':'Entrying','补枪':'Trading','首杀':'Opening',
           '残局':'Clutching','狙击':'Sniping','道具':'Utility','指挥':'Calling'}


@lru_cache(maxsize=4096)
def translate(text):
    if not isinstance(text,str) or not text: return text
    if text in phrases(): return phrases()[text]
    effects=re.fullmatch(r'游戏效果：(.*?)。状态暂时([+-]\d+)，到(\d{4}-\d{2}-\d{2})解除。',text)
    if effects:
        changes=effects[1]
        for zh,en in AXES_EN.items():changes=changes.replace(zh+' ',en+' ')
        return f'Game effects: {changes.replace("，", ", ")}. Temporary form: {effects[2]}, until {effects[3]}.'
    reward=re.fullmatch(r'(.*)（属性点\+(\d+)）',text,re.S)
    if reward:
        return translate(reward[1])+f' (+{reward[2]} attribute points)'
    for prefix, pattern, en in templates():
        if prefix and not text.startswith(prefix):continue
        match=pattern.fullmatch(text)
        if match:
            values={k:translate(v) if k in SEMANTIC and v!=text else v for k,v in match.groupdict().items()}
            return re.sub(r'\{([a-z_]+)\}',lambda m:values.get(m[1],m[0]),en)
    if '\n' in text:
        return '\n'.join(translate(line) for line in text.split('\n'))
    return text


def present(row):
    if not isinstance(row,dict):return row
    out=dict(row)
    for field in ('title','text','label','choice','body','from'):
        value=row.get(field)
        if isinstance(value,str) and not row.get(field+'_en'):
            translated=translate(value)
            if translated!=value:out[field+'_en']=translated
    if row.get('choices'):out['choices']=[present(c) for c in row['choices']]
    return out
