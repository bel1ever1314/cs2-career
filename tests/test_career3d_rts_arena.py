"""Frozen local RTS ladder tests; no real save, deployment, or CS2 process."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cs2career.arena import Arena
from test_arena import fixture_state
from tools.career3d_rts import _hash, _map_rows, rts_command, rts_context


def completed_report(session, number_of_rounds=13):
    """Real-shaped 13-0 ledger: five identified kills/deaths in each round.

    Per-round counters and final totals agree; no summary Rating/ADR is trusted.
    Floats intentionally mirror integral numbers arriving from Godot's JSON.
    """
    totals = {}
    for side in ('ct', 't'):
        for player in session['rosters'][side]:
            totals[player['id']] = dict(id=player['id'], name=player['name'], team=side,
                k=0, d=0, a=0, damage=0, survived_rounds=0, kast_rounds=0,
                opening_kills=0, opening_deaths=0)
    rounds = []
    for number in range(1, number_of_rounds + 1):
        players, events = [], []
        for side in ('ct', 't'):
            for index, player in enumerate(session['rosters'][side]):
                row = dict(id=player['id'], team=side,
                    k=1.0 if side == 'ct' else 0.0, d=0.0 if side == 'ct' else 1.0,
                    a=0.0, damage=100.0 if side == 'ct' else 0.0,
                    opening_kills=1.0 if side == 'ct' and index == 0 else 0.0,
                    opening_deaths=1.0 if side == 't' and index == 0 else 0.0,
                    survived=side == 'ct', kast=side == 'ct', traded=False)
                players.append(row)
                total = totals[player['id']]
                for key in ('k', 'd', 'a', 'damage', 'opening_kills', 'opening_deaths'):
                    total[key] += row[key]
                total['survived_rounds'] += int(row['survived'])
                total['kast_rounds'] += int(row['kast'])
        for attacker, victim in zip(session['rosters']['ct'], session['rosters']['t']):
            events.extend([
                dict(type='shot', hit=True, attacker_id=attacker['id'], victim_id=victim['id'],
                     damage=100, weapon='ak47', time_s=20),
                dict(type='kill', killer_id=attacker['id'], victim_id=victim['id'],
                     weapon='ak47', headshot=False, time_s=20),
            ])
        rounds.append(dict(round=number, winner='ct', score={'ct': number, 't': 0},
                           reason='elimination', players=players, events=events))
    return dict(schema_version=2, finished=True, map=session['map'], seed=session['seed'],
                winner='ct', score={'ct': number_of_rounds, 't': 0}, round_history=rounds,
                players=list(totals.values()))


class CareerRTSArenaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rts-arena-')
        self.addCleanup(self.temp.cleanup)
        self.arena = Arena(Path(self.temp.name) / 'arena.json')
        self.state = fixture_state()
        self.state.arena = self.arena
        self.state.career.incident_state = {'career3d_service': {'revision': 7, 'receipts': []}}
        self.human = self.arena.career_player_id(self.state)
        # Make the real career human the first captain, so the test explicitly
        # bans maps not presently validated for ranked RTS, using normal BP.
        self.arena.data['ladder'][self.human] = dict(elo=7000, wins=0, losses=0, recent=[])

    def arena_body(self, **kwargs):
        return dict(revision=self.arena.data['revision'], **kwargs)

    def body(self, **kwargs):
        lobby = self.arena.data['lobby'] or {}
        return dict(revision=7, arena_revision=self.arena.data['revision'],
                    lobby_id=lobby.get('id'), **kwargs)

    def ready(self, mode='rank'):
        self.arena.matchmake(self.state, self.arena_body(human_id=self.human))
        while self.arena.data['lobby']['phase'] in ('draft', 'veto', 'side'):
            lobby = self.arena.data['lobby']
            if not self.arena.turn(lobby)['human']:
                self.arena.advance(self.arena_body())
            elif lobby['phase'] == 'draft':
                available = next(pid for pid in lobby['selection'] if pid not in lobby['a'] + lobby['b'])
                self.arena.pick(self.arena_body(player_id=available))
            elif lobby['phase'] == 'veto':
                remaining = [name for name in lobby['map_pool'] if name not in [row['map'] for row in lobby['bans']]]
                unavailable = [name for name in remaining if not _map_rows().get('de_' + name, {}).get('career_ready')]
                self.arena.ban(self.arena_body(map=(unavailable or remaining)[0]))
            else:
                self.arena.choose_side(self.arena_body(side='ct'))
        lobby = self.arena.data['lobby']
        self.assertTrue(_map_rows()['de_' + lobby['map']]['career_ready'])
        if mode == 'fpl':
            # Current matchmaking creates Rank. A previously saved FPL room
            # still uses the same ledger and must retain its compatible mode.
            lobby['mode'] = 'fpl'
            self.arena._commit()
        return lobby

    def start(self, mode='rank'):
        self.ready(mode)
        return rts_command(self.state, 'arena_start', self.body())['rts_session']

    def submit(self, session, report=None, **kwargs):
        return rts_command(self.state, 'arena_submit', self.body(
            nonce=session['nonce'], report=report if report is not None else completed_report(session), **kwargs))

    def test_rank_and_legacy_fpl_freeze_ten_ids_map_seed_and_side(self):
        for mode in ('rank', 'fpl'):
            with self.subTest(mode=mode):
                session = self.start(mode)
                lobby = self.arena.data['lobby']
                self.assertEqual('arena', session['kind'])
                self.assertEqual(lobby['id'], session['lobby_id'])
                self.assertEqual('de_' + lobby['map'], session['map'])
                self.assertEqual(int(session['nonce'][:8], 16) % 2147483647, session['seed'])
                self.assertEqual(self.human, session['player_id'])
                rows = session['rosters']['ct'] + session['rosters']['t']
                self.assertEqual(10, len({row['id'] for row in rows}))
                self.assertEqual(set(lobby['selection']), {row['id'] for row in rows})
                self.assertEqual(_hash(session['rosters']), session['roster_hash'])
                side = 'ct' if self.human in lobby[lobby['ct']] else 't'
                self.assertEqual(side, session['commanded_side'])
                frozen = deepcopy(lobby['rts_session'])
                for team in self.state.season.teams:
                    for player in team['players']:
                        player['name'] = 'later-club-name'
                        player['ability'] = 1
                session['rosters']['ct'][0]['name'] = 'client-copy-mutation'
                self.assertEqual(frozen, lobby['rts_session'])
                self.arena = Arena(self.arena.path)
                self.state.arena = self.arena
                self.assertEqual(frozen, self.arena.data['lobby']['rts_session'])
                self.arena.cancel(self.arena_body())

    def test_start_and_cancel_reject_both_stale_revisions_without_writes(self):
        self.ready()
        before = deepcopy(self.arena.data)
        disk = self.arena.path.read_bytes()
        for field in ('revision', 'arena_revision'):
            body = self.body()
            body[field] -= 1
            with self.assertRaises(ValueError):
                rts_command(self.state, 'arena_start', body)
            self.assertEqual(before, self.arena.data)
            self.assertEqual(disk, self.arena.path.read_bytes())
        session = rts_command(self.state, 'arena_start', self.body())['rts_session']
        before = deepcopy(self.arena.data)
        for field in ('revision', 'arena_revision'):
            body = self.body(nonce=session['nonce'])
            body[field] -= 1
            with self.assertRaises(ValueError):
                rts_command(self.state, 'arena_cancel', body)
            self.assertEqual(before, self.arena.data)

    def test_pending_start_and_read_context_are_owned_idempotent_copies(self):
        session = self.start()
        before = deepcopy(self.arena.data)
        with patch.object(self.arena, 'save') as save:
            response = rts_command(self.state, 'arena_start', self.body())
            self.assertTrue(response['replayed'])
            public = rts_context(self.state)
            self.assertTrue(public['rts']['pending'])
            self.assertEqual(session, public['rts']['arena_session'])
            response['rts_session']['seed'] = -1
            public['rts']['arena_session']['rosters']['ct'][0]['name'] = 'not-owned'
            save.assert_not_called()
        self.assertEqual(before, self.arena.data)

    def test_cancel_keeps_frozen_bp_and_does_not_settle_elo(self):
        self.ready()
        ready = deepcopy(self.arena.data['lobby'])
        ladder = deepcopy(self.arena.data['ladder'])
        session = rts_command(self.state, 'arena_start', self.body())['rts_session']
        response = rts_command(self.state, 'arena_cancel', self.body(nonce=session['nonce']))
        self.assertEqual('cancelled', response['status'])
        self.assertEqual(ready, self.arena.data['lobby'])
        self.assertEqual(ladder, self.arena.data['ladder'])
        self.assertFalse(self.arena.data['matches'])
        self.assertFalse(self.arena.pending)
        new_session = rts_command(self.state, 'arena_start', self.body())['rts_session']
        self.assertNotEqual(session['nonce'], new_session['nonce'])
        self.assertEqual(session['roster_hash'], new_session['roster_hash'])
        self.assertEqual(session['map'], new_session['map'])

    def test_cancel_old_identity_is_allowed_but_new_start_cannot_use_alt(self):
        session = self.start()
        self.state.career.you_card = deepcopy(self.state.season.teams[1]['players'][0])
        response = rts_command(self.state, 'arena_cancel', self.body(nonce=session['nonce']))
        self.assertEqual('cancelled', response['status'])
        before = deepcopy(self.arena.data)
        with self.assertRaises(ValueError):
            rts_command(self.state, 'arena_start', self.body())
        self.assertEqual(before, self.arena.data)

    def test_valid_ledger_settles_local_elo_only_and_replays_after_reload(self):
        for mode in ('rank', 'fpl'):
            with self.subTest(mode=mode):
                session = self.start(mode)
                career, season = deepcopy(self.state.career), deepcopy(self.state.season)
                ladder = deepcopy(self.arena.data['ladder'])
                response = self.submit(session)
                self.assertEqual('finished', response['status'])
                result = self.arena.data['lobby']['result']
                self.assertEqual('rts', result['source'])
                self.assertEqual(mode, result['mode'])
                self.assertEqual('rts', result['map']['source'])
                self.assertEqual(session['nonce'], result['map']['request_nonce'])
                self.assertEqual(session['seed'], result['map']['seed'])
                self.assertEqual(13, result['map']['rounds'])
                self.assertEqual(13, len(result['map']['rts_round_history']))
                self.assertEqual(65, sum(row['k'] for rows in result['map']['players'].values() for row in rows))
                self.assertEqual(143, len(result['map']['events']))
                self.assertEqual(5, sum(row['wins'] for row in self.arena.data['ladder'].values())
                                 - sum(row['wins'] for row in ladder.values()))
                self.assertEqual(5, sum(row['losses'] for row in self.arena.data['ladder'].values())
                                 - sum(row['losses'] for row in ladder.values()))
                self.assertEqual(sum(row['elo'] for row in ladder.values()),
                                 sum(row['elo'] for row in self.arena.data['ladder'].values()))
                self.assertEqual(set(session['rosters'][side][i]['id'] for side in ('ct', 't') for i in range(5)),
                                 set(result['changes']))
                self.assertEqual(career, self.state.career)
                self.assertEqual(season, self.state.season)
                settled = deepcopy(self.arena.data)
                self.arena = Arena(self.arena.path)
                self.state.arena = self.arena
                with patch.object(self.arena, 'save') as save:
                    repeat = rts_command(self.state, 'arena_submit', dict(
                        self.body(nonce=session['nonce'], report={}), revision=-1, arena_revision=-1))
                    self.assertTrue(repeat['replayed'])
                    save.assert_not_called()
                self.assertEqual(settled, self.arena.data)
                self.arena.cancel(self.arena_body())

    def test_submit_rejects_stale_revisions_before_map_settlement(self):
        session = self.start()
        before = deepcopy(self.arena.data)
        for field in ('revision', 'arena_revision'):
            body = self.body(nonce=session['nonce'], report=completed_report(session))
            body[field] -= 1
            with self.assertRaises(ValueError):
                rts_command(self.state, 'arena_submit', body)
            self.assertEqual(before, self.arena.data)
            self.assertEqual(before, Arena(self.arena.path).data)

    def test_malformed_ledger_and_identity_do_not_end_session(self):
        session = self.start()
        report = completed_report(session)
        variants = [dict(report, map='de_wrong'), dict(report, seed=session['seed'] + 1),
                    dict(report, round_history=report['round_history'][:12]),
                    dict(report, score={'ct': 12, 't': 1}), dict(report, winner='t'),
                    completed_report(session, 14)]
        for mutation in ('id', 'team', 'fraction', 'bool_counter', 'summary'):
            wrong = deepcopy(report)
            row = wrong['round_history'][0]['players'][0]
            if mutation == 'id': row['id'] = 'invented-player'
            elif mutation == 'team': row['team'] = 't'
            elif mutation == 'fraction': row['k'] = .5
            elif mutation == 'bool_counter': row['damage'] = True
            else: wrong['players'][0]['k'] += 1
            variants.append(wrong)
        before = deepcopy(self.arena.data)
        for wrong in variants:
            with self.assertRaises(ValueError):
                self.submit(session, wrong)
            self.assertEqual(before, self.arena.data)
            self.assertEqual(before, Arena(self.arena.path).data)
        for body in (self.body(nonce='wrong', report=report),
                     dict(self.body(nonce=session['nonce'], report=report), lobby_id='another-room')):
            with self.assertRaises(ValueError):
                rts_command(self.state, 'arena_submit', body)
            self.assertEqual(before, self.arena.data)

    def test_changed_lobby_roster_cannot_rewrite_frozen_player_statistics(self):
        session = self.start()
        player = self.arena.data['lobby']['roster'][self.human]
        player['name'] = 'corrupt-identity-snapshot'
        before = deepcopy(self.arena.data)
        with self.assertRaisesRegex(ValueError, '阵容'):
            self.submit(session)
        self.assertEqual(before, self.arena.data)
        self.assertFalse(self.arena.data['matches'])

    def test_training_and_career_result_pending_block_arena_start(self):
        self.ready()
        before = deepcopy(self.arena.data)
        for pending in ('training', 'cs2', 'rts'):
            with self.subTest(pending=pending):
                self.state.career.training_session = {'nonce': 'training'} if pending == 'training' else None
                self.state.season.events = [] if pending == 'training' else [dict(matches=[{
                    ('cs2_session' if pending == 'cs2' else 'career3d_rts'): {'nonce': pending}, 'played': False}])]
                with self.assertRaises(ValueError):
                    rts_command(self.state, 'arena_start', self.body())
                self.assertEqual(before, self.arena.data)

    def test_settlement_save_failure_preserves_elo_and_pending_ledger(self):
        session = self.start()
        before = deepcopy(self.arena.data)
        with patch('cs2career.arena.os.replace', side_effect=OSError('isolated disk failure')):
            with self.assertRaises(OSError):
                self.submit(session)
        self.assertEqual(before, self.arena.data)
        self.assertEqual(before, Arena(self.arena.path).data)


if __name__ == '__main__':
    unittest.main()
