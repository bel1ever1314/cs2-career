"""Shared identity/rule envelope, independent of how a map is played.

Old saves keep their nonce and are read with the original competitive format.
New CS2/RTS handoffs freeze the format; explicit mismatches never settle.
"""
from .rules import COMPETITIVE
from hashlib import sha256
import json


def stamp(session, execution):
    session.update(session_id=session['nonce'], execution=execution, rules_id=COMPETITIVE.id)
    return session


def stamp_simulation(result, *identity):
    """Synchronous maps have no remote callback or resumable running process.

    Identify their committed result from the owning match/map, without consuming
    gameplay RNG or making a fixed-seed interrupted run produce different IDs.
    """
    encoded = json.dumps(identity, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    result.update(session_id='sim-' + sha256(encoded).hexdigest(), execution='sim', rules_id=COMPETITIVE.id)
    return result


def rules_error(report, session):
    expected = session.get('rules_id', COMPETITIVE.id)
    if expected != COMPETITIVE.id:
        return '这场比赛的规则版本尚未支持，原战绩已保留。'
    # Older CareerMatch dumps have no echo. Validate them against the saved
    # format/nonce/roster and score, never silently accept a different rule ID.
    if report.get('rules_id', expected) != expected:
        return '回传规则版本与本场比赛不一致，未结算。'
    expected_id = session.get('session_id', session.get('nonce'))
    if expected_id and report.get('session_id') is not None and report['session_id'] != expected_id:
        return '回传会话编号与本场比赛不一致，未结算。'
    return ''
