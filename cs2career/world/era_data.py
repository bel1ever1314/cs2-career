"""Sourced opening-roster corrections and honest, read-only quality labels.

Identity verification is separate from attribute calibration. A source proving
a lineup does not prove its ratings, roles or ages. Never apply these corrections
to a loaded career: a fictional slot's history cannot be reassigned to a pro.
"""
from copy import deepcopy
from datetime import date
from functools import lru_cache
import json
import math
import re
from urllib.parse import urlsplit

from ..paths import data_file


def validate_rosters(raw):
    """Reject malformed bundled corrections before they enter a new world."""
    if not isinstance(raw, dict) or raw.get('schema_version') != 1 or not isinstance(raw.get('rosters'), list):
        raise ValueError('年代阵容补丁结构无效')
    out = {}
    for row in raw['rosters']:
        if not isinstance(row, dict):
            raise ValueError('年代阵容必须是对象')
        era, team = row.get('era'), row.get('team')
        if not isinstance(era, str) or not re.fullmatch(r'\d{4}', era) or not isinstance(team, str) or not team.strip():
            raise ValueError('年代和队伍引用无效')
        try:
            as_of = date.fromisoformat(row['as_of'])
            announced = date.fromisoformat(row.get('announced_at') or row['observed_at'])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('阵容补丁缺少有效日期') from exc
        if as_of != date(int(era), 1, 8) or announced > as_of:
            raise ValueError('阵容公告晚于开局日期，不能提前使用未来阵容')
        people = row.get('players')
        if not isinstance(people, list) or len(people) != 5:
            raise ValueError('阵容必须恰好五人')
        names = set()
        for p in people:
            if not isinstance(p, dict) or not isinstance(p.get('name'), str) or not p['name'].strip():
                raise ValueError('选手姓名无效')
            name = p['name'].strip().casefold()
            if name in names or p.get('role') not in ('igl', 'awp', 'entry', 'lurk', 'rifle'):
                raise ValueError('阵容中选手重复或位置无效')
            names.add(name)
            ability = p.get('ability')
            if isinstance(ability, bool) or not isinstance(ability, (int, float)) or not math.isfinite(ability) or not 45 <= ability <= 100:
                raise ValueError('能力必须是 45–100 的有限数值')
        sources = row.get('sources')
        if not isinstance(sources, list) or not sources:
            raise ValueError('阵容补丁必须记录来源')
        for source in sources:
            if not isinstance(source, dict) or not isinstance(source.get('url'), str):
                raise ValueError('阵容来源无效')
            url = urlsplit(source['url'])
            if url.scheme != 'https' or not url.netloc or not isinstance(source.get('title'), str):
                raise ValueError('阵容来源必须是 HTTPS 页面')
            # A later announcement may document WHY an identity is excluded,
            # never justify moving that player into the opening roster early.
            if source.get('purpose') not in (None, 'exclusion'):
                raise ValueError('阵容来源用途无效')
            for field in ('observed_at', 'published_at'):
                if field not in source:
                    continue
                try:
                    source_day = date.fromisoformat(source[field])
                except (TypeError, ValueError) as exc:
                    raise ValueError('阵容来源日期无效') from exc
                if source_day > as_of and source.get('purpose') != 'exclusion':
                    raise ValueError('开局名单不能使用未来来源；排除证据须明确标注')
        if all(s.get('purpose') == 'exclusion' for s in sources):
            raise ValueError('开局名单至少需要一个非排除用途的来源')
        if (era, team) in out:
            raise ValueError('重复的年代战队补丁')
        out[era, team] = deepcopy(row)
    return out


@lru_cache(maxsize=1)
def roster_corrections():
    return validate_rosters(json.loads(data_file('era_rosters.json').read_text(encoding='utf-8')))


def correction_for(era, team):
    world = world_manifest(str(era))
    if world:
        found = next((t for t in world['teams'] if t['name'] == team), None)
        if found:
            return {**deepcopy(found), 'era': str(era), 'team': team, 'as_of': world['as_of'],
                    'revision': world['revision']}
    return deepcopy(roster_corrections().get((str(era), team), {}))


def validate_world(raw):
    """An era owns its organisation list; no aliasing to a modern org shell."""
    if not isinstance(raw, dict) or raw.get('schema_version') != 1 or not isinstance(raw.get('teams'), list) or not raw['teams']:
        raise ValueError('独立年代包必须包含战队列表')
    if not isinstance(raw.get('revision'), str) or not raw['revision']:
        raise ValueError('独立年代包缺少版本号')
    ids, names, seeds, people = set(), set(), set(), set()
    for team in raw['teams']:
        if not isinstance(team, dict) or not isinstance(team.get('id'), str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', team['id']):
            raise ValueError('独立年代组织ID无效')
        name, seed = team.get('name'), team.get('seed')
        if not isinstance(name, str) or not name.strip():
            raise ValueError('独立年代组织名称无效')
        if team['id'] in ids or name in names or isinstance(seed, bool) or not isinstance(seed, int) or seed < 1 or seed in seeds:
            raise ValueError('独立年代组织或游戏排序重复/无效')
        if team.get('region') not in ('EU', 'AM', 'AS'):
            raise ValueError('独立年代赛区无效')
        source_rank = team.get('source_rank')
        if source_rank is not None and (isinstance(source_rank, bool) or not isinstance(source_rank, int) or source_rank < 1):
            raise ValueError('来源排名无效')
        if team.get('roster_quality') not in ('verified','provisional','partial','estimated'):
            raise ValueError('阵容核验状态无效')
        validate_rosters({'schema_version': 1, 'rosters': [{**team, 'era': raw.get('era'), 'team': name, 'as_of': raw.get('as_of')}]})
        for player in team['players']:
            # Fold aliases differing only in case, just like the stable ID
            # factory. A display-name variation cannot occupy a second club.
            key = player['name'].strip().casefold()
            if key in people:
                raise ValueError(f'独立年代选手跨队重复：{player["name"]}')
            if placeholder(player) and team['roster_quality'] == 'verified':
                raise ValueError('含占位选手的阵容不得标为已核验')
            if not isinstance(player.get('is_igl', False), bool):
                raise ValueError('兼任指挥标志必须是布尔值')
            people.add(key)
        ids.add(team['id']); names.add(name); seeds.add(seed)
    if seeds != set(range(1, len(raw['teams']) + 1)):
        raise ValueError('游戏排序必须连续；来源排名可不连续')
    return deepcopy(raw)


@lru_cache(maxsize=8)
def world_manifest(era):
    # IDs are validated before path construction, including calls from addons.
    if not re.fullmatch(r'\d{4}', str(era)):
        return None
    path = data_file(f'eras/{era}.json')
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or raw.get('era') != str(era):
        raise ValueError('年代包文件名与年代ID不一致')
    return validate_world(raw)


def team_rows_for(era, legacy):
    """Legacy tuple adapter keeps the simulation independent of file layout."""
    world = world_manifest(str(era))
    if world is None:
        return list(legacy)
    return [(t['name'], t['region'], t['seed'], 40, [(p['name'], p['ability']) for p in t['players']])
            for t in sorted(world['teams'], key=lambda t: t['seed'])]


def placeholder(row):
    return bool(re.search(r' \d{4} slot[1-5]$', str(row.get('name') or '')))


def quality_view(row, *, team=False):
    """Describe saved provenance, NOT today's updated pack, without mutation."""
    provenance = deepcopy(row.get('era_provenance') or {})
    players = row.get('players') or []
    slots = sum(placeholder(p) for p in players) if team else int(placeholder(row))
    source = str(row.get('source') or '')
    if slots or row.get('data_quality') == 'estimated':
        status, label = 'estimated', '历史资料待补 · 估算占位'
        note = (f'当前阵容含 {slots} 名占位选手。' if team else '') + 'slot 是缺少历史名单时生成的虚构身份，不是真实职业选手。更新资料包不会把该身份的旧战绩转给真人。'
    elif provenance.get('roster_quality') == 'partial':
        status, label = 'partial', '名单有记录 · 所属开局阵容仍有缺失'
        note = provenance.get('note') or '队内其他位置仍待核验，当前选手能力为估算。'
    elif provenance.get('roster_quality') == 'provisional':
        status, label = 'provisional', '过渡阵容 · 含代打身份'
        note = provenance.get('note') or '按已出场的代打阵容暂列，不等同正式签约名单。'
    elif provenance.get('roster_quality') == 'verified':
        status, label = 'verified', '开局阵容已核验 · 能力仍为估算'
        note = provenance.get('note') or '这里只核验开局五人身份，不代表全部历史属性已核验。'
    elif source.startswith('extension:') or row.get('data_quality') == 'extension':
        status, label = 'extension', '扩展包资料 · 作者提供'
        note = '由扩展包提供；加载成功不等于历史资料已核验。'
    elif source.startswith(('historical-roster-', 'opening-world-')) or row.get('data_quality') == 'curated':
        status, label = 'unverified', '旧版内置资料 · 尚未逐队核验'
        note = '当前名单来自旧版内置表，仍需检查开局日期、阵容和属性来源，不能视为完整历史快照。'
    else:
        status, label, note = 'unknown', '', ''
    return {'status': status, 'label': label, 'note': note, 'placeholder_count': slots,
            'as_of': provenance.get('as_of'), 'sources': provenance.get('sources', []), 'source': source,
            'source_rank': provenance.get('source_rank'), 'game_seed': provenance.get('seed'),
            'revision': provenance.get('revision')}


def coverage(teams):
    states = [quality_view(t, team=True) for t in teams]
    return {'teams': len(teams), 'verified_rosters': sum(s['status'] == 'verified' for s in states),
            'estimated_teams': sum(s['status'] == 'estimated' for s in states),
            'placeholder_players': sum(s['placeholder_count'] for s in states),
            'unverified_teams': sum(s['status'] == 'unverified' for s in states),
            'provisional_teams': sum(s['status'] == 'provisional' for s in states),
            'extension_teams': sum(s['status'] == 'extension' for s in states)}
