"""Small, immutable-in-the-receipt scorecard for automatic series playback.

Only saved map rows are read. No event replay, reward or simulation happens
here; per-map rates are never averaged to manufacture series statistics.
"""
from ..presentation import aggregate, measured
from ..engine.rating import career_rating
from copy import deepcopy


def series_report(match, player_id, player_team):
    maps = match.get('maps') or []
    buckets = {}
    complete = bool(maps)
    for mp in maps:
        grouped = mp.get('players') or {}
        lines = [(team, row) for team, rows in grouped.items() for row in rows]
        ids = [row.get('player_id') for _, row in lines]
        complete = complete and (len(lines) == 10 and all(ids) and len(set(ids)) == 10
            and all(len(grouped.get(team, [])) == 5 for team in (match['team_a'], match['team_b'])))
        for team, row in lines:
            pid = row.get('player_id')
            # Legacy rows without stable identity cannot safely be combined.
            if not pid:
                complete = False
                continue
            bucket = buckets.setdefault((team, pid), dict(team=team, player_id=pid,
                name=row.get('name', ''), rows=[]))
            bucket['rows'].append((row, int(mp.get('rounds') or 0)))
            complete = complete and measured(row, mp.get('rounds'))
    totals = []
    for bucket in buckets.values():
        totals.append({k: v for k, v in bucket.items() if k != 'rows'} | aggregate(bucket['rows']))
        totals[-1]['data_complete'] = totals[-1]['data_complete'] and totals[-1]['maps'] == len(maps)
    complete = bool(complete and len(totals) == 10 and all(row['maps'] == len(maps) for row in totals))
    return dict(player_id=player_id, player_team=player_team, totals=totals,
        data_complete=complete, played=bool(match.get('played')), winner=match.get('winner'))


def round_report(mp, teams, rounds):
    """Project a saved event ledger; never estimate missing round measurements.

    Older simulated ledgers omitted assist damage. Their exact K/D/A and KAST
    remain available, while ADR/Rating wait for the saved final box score.
    Identity and final ledger checks prevent partial histories masquerading as
    ten-player telemetry. The returned frames are independent of saved state.
    """
    empty = dict(round_frames=[], round_stats_available=False,
                 round_damage_available=False, round_stats_reason='没有完整回合记录。')
    if not rounds:
        return empty
    if mp.get('rts_round_history'):
        return _rts_round_report(mp, teams, rounds)
    grouped = mp.get('players') or {}
    rows = [dict(row, team=team) for team in teams for row in grouped.get(team, [])]
    names = [row.get('name') for row in rows]
    ids = [row.get('player_id') for row in rows]
    valid = (len(rows) == 10 and all(len(grouped.get(team, [])) == 5 for team in teams)
             and all(names) and len(set(names)) == 10 and all(ids) and len(set(ids)) == 10)
    by_name = {row['name']: row for row in rows} if valid else {}
    stats = {name: {key: 0 for key in ('k', 'd', 'a', 'damage', 'kast_rounds',
              'survived_rounds', 'traded_deaths', 'opening_kills', 'opening_deaths')}
             for name in by_name}
    events_by_round = {number: [] for number in range(1, len(rounds) + 1)}
    for event in mp.get('events') or []:
        if type(event.get('round')) is not int or event['round'] not in events_by_round:
            valid = False
            continue
        if event.get('type') != 'round_end':
            events_by_round[event['round']].append(event)
    damage_complete = valid
    frames = []
    for number, side in enumerate(rounds, 1):
        events = events_by_round[number]
        kills = [event for event in events if event.get('type') == 'kill']
        highlights = []
        if kills:
            first = kills[0]
            highlights.append(dict(kind='opening', name=first.get('killer', ''),
                player_id=by_name.get(first.get('killer'), {}).get('player_id', ''),
                victim=first.get('victim', '')))
        round_kills = {}
        for event in kills:
            killer = event.get('killer', '')
            round_kills[killer] = round_kills.get(killer, 0) + 1
        highlights.extend(dict(kind='multikill', name=name, kills=count,
            player_id=by_name.get(name, {}).get('player_id', ''))
            for name, count in round_kills.items() if count >= 2)
        flags = {name: dict(kill=False, assist=False, dead=False, traded=False) for name in by_name}
        pending = []
        kill_order = 0
        for event in events:
            kind = event.get('type')
            if kind == 'kill':
                killer, victim, assister = (event.get(key, '') for key in ('killer', 'victim', 'assister'))
                if (killer not in by_name or victim not in by_name or (assister and assister not in by_name)
                        or by_name[killer]['team'] == by_name[victim]['team']
                        or (assister and by_name[assister]['team'] != by_name[killer]['team'])):
                    valid = False
                    continue
                for old_victim, old_killer, team, order in pending:
                    if victim == old_killer and by_name[killer]['team'] == team and kill_order - order <= 2:
                        flags[old_victim]['traded'] = True
                        stats[old_victim]['traded_deaths'] += 1
                stats[killer]['k'] += 1
                stats[victim]['d'] += 1
                flags[killer]['kill'] = flags[victim]['dead'] = True
                if kill_order == 0:
                    stats[killer]['opening_kills'] += 1
                    stats[victim]['opening_deaths'] += 1
                if assister:
                    stats[assister]['a'] += 1
                    flags[assister]['assist'] = True
                for name, field in ((killer, 'damage'), (assister, 'assist_damage')):
                    if not name:
                        continue
                    amount = event.get(field)
                    if type(amount) not in (int, float) or amount < 0:
                        damage_complete = False
                    else:
                        stats[name]['damage'] += amount
                pending.append((victim, killer, by_name[victim]['team'], kill_order))
                kill_order += 1
            elif kind == 'hurt':
                attacker, amount = event.get('attacker'), event.get('damage')
                if attacker not in by_name:
                    valid = False
                elif type(amount) not in (int, float) or amount < 0:
                    damage_complete = False
                else:
                    stats[attacker]['damage'] += amount
            else:
                # Unsupported event schemas cannot establish exact player stats.
                valid = False
        for name, flag in flags.items():
            stats[name]['survived_rounds'] += int(not flag['dead'])
            stats[name]['kast_rounds'] += int(flag['kill'] or flag['assist'] or not flag['dead'] or flag['traded'])
        players = []
        for row in rows if by_name else []:
            value = stats[row['name']]
            players.append(dict(team=row['team'], player_id=row['player_id'], name=row['name'],
                **deepcopy(value), rounds=number, kast=round(value['kast_rounds'] / number, 4),
                adr=round(value['damage'] / number, 2) if damage_complete else None,
                rating=career_rating(value['k'], value['d'], value['a'], value['damage'], value['kast_rounds'], number)
                    if damage_complete else None, data_complete=damage_complete))
        frames.append(dict(number=number, winner=teams[0 if side == 'a' else 1],
            events=deepcopy(events), highlights=highlights, players=players))
    # A complete winner history alone is not evidence of player statistics.
    for row in rows if by_name else []:
        final = stats[row['name']]
        if any(row.get(key) != final[key] for key in ('k', 'd', 'a', 'kast_rounds')):
            valid = False
        if damage_complete and row.get('damage') != final['damage']:
            damage_complete = False
    if not valid:
        for frame in frames:
            frame['players'] = []
    elif not damage_complete:
        for frame in frames:
            for row in frame['players']:
                row.update(damage=None, adr=None, rating=None, data_complete=False)
    reason = '' if valid and damage_complete else ('旧回合记录缺少助攻伤害；ADR / Rating 在本图结束后显示。'
        if valid else '回合统计记录不完整；本图结束后显示已保存的十人战绩。')
    return dict(round_frames=frames, round_stats_available=valid,
        round_damage_available=bool(valid and damage_complete), round_stats_reason=reason)


def _rts_round_report(mp, teams, rounds):
    """The RTS engine saves per-round measured deltas under stable identities."""
    unavailable = dict(round_frames=[], round_stats_available=False, round_damage_available=False,
        round_stats_reason='RTS 回合统计记录不完整；本图结束后显示已保存的战绩。')
    history = mp['rts_round_history']
    grouped = mp.get('players') or {}
    roster = [dict(row, team=team) for team in teams for row in grouped.get(team, [])]
    ids = [row.get('player_id') for row in roster]
    if (not isinstance(history, list) or len(history) != len(rounds) or len(roster) != 10
            or not all(ids) or len(set(ids)) != 10
            or any(len(grouped.get(team, [])) != 5 for team in teams)):
        return unavailable
    by_id = {row['player_id']: row for row in roster}
    totals = {pid: dict(k=0, d=0, a=0, damage=0, kast_rounds=0, survived_rounds=0,
        opening_kills=0, opening_deaths=0) for pid in ids}
    events = {number: [] for number in range(1, len(rounds) + 1)}
    for event in mp.get('events') or []:
        if event.get('round') in events and event.get('type') != 'round_end':
            events[event['round']].append(event)
    frames = []
    for number, (rd, side) in enumerate(zip(history, rounds), 1):
        if not isinstance(rd, dict):
            return unavailable
        players = rd.get('players')
        winner = teams[0 if side == 'a' else 1]
        if (rd.get('round') != number or rd.get('winner') != winner or not isinstance(players, list)
                or len(players) != 10 or not all(isinstance(p, dict) for p in players)
                or {p.get('id') for p in players} != set(ids)):
            return unavailable
        highlights = []
        for player in players:
            pid = player['id']
            total = totals[pid]
            for key in ('k', 'd', 'a', 'damage', 'opening_kills', 'opening_deaths'):
                amount = player.get(key)
                if type(amount) not in (int, float) or not 0 <= amount <= 120000 or int(amount) != amount:
                    return unavailable
                total[key] += int(amount)
            if type(player.get('kast')) is not bool or type(player.get('survived')) is not bool:
                return unavailable
            total['kast_rounds'] += int(player['kast'])
            total['survived_rounds'] += int(player['survived'])
            identity = by_id[pid]
            if player['opening_kills']:
                opening = next((event for event in events[number] if event.get('type') == 'kill'
                    and event.get('killer_id', event.get('attacker_id')) == pid), {})
                highlights.append(dict(kind='opening', player_id=pid, name=identity['name'], victim=opening.get('victim', '')))
            if player['k'] >= 2:
                highlights.append(dict(kind='multikill', player_id=pid, name=identity['name'], kills=player['k']))
        reason = str(rd.get('reason', ''))
        if reason in ('defused', 'defuse', 'bomb_exploded', 'exploded', 'time', 'timeout', '炸弹已拆除', '炸弹爆炸', '回合时间耗尽', '回合时间耗尽，炸弹未下包'):
            highlights.append(dict(kind='objective', reason=reason))
        cumulative = []
        for identity in roster:
            total = totals[identity['player_id']]
            cumulative.append(dict(team=identity['team'], player_id=identity['player_id'], name=identity['name'],
                **deepcopy(total), rounds=number, adr=round(total['damage'] / number, 2),
                kast=round(total['kast_rounds'] / number, 4),
                rating=career_rating(total['k'], total['d'], total['a'], total['damage'], total['kast_rounds'], number),
                data_complete=True))
        frames.append(dict(number=number, winner=winner, events=deepcopy(events[number]),
            highlights=highlights, players=cumulative))
    if any(identity.get(key) != totals[identity['player_id']][key] for identity in roster
           for key in ('k', 'd', 'a', 'damage', 'kast_rounds')):
        return unavailable
    return dict(round_frames=frames, round_stats_available=True,
        round_damage_available=True, round_stats_reason='')
