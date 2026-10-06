"""Pure CS2 launch/exit projection shared by the local match adapters."""
from datetime import datetime, timezone


LAUNCH_GRACE_SECONDS = 45


def utc_stamp():
    return datetime.now(timezone.utc).isoformat()


def recovery_state(session, running, result_ready=False, now=None, seen_running=False):
    """No process shortly after Steam dispatch is not yet an interrupted game.

    An unknown process state never grants permission to overwrite game files.
    Legacy sessions use their original dispatch timestamp. Reading this view
    does not change a persisted session, score, nonce or launch receipt.
    """
    if result_ready:
        return dict(status='result_ready', can_resume=False, can_switch=False,
                    launch_grace=False, reason='真实战绩已回传，请先录入。')
    if not session:
        return dict(status='idle', can_resume=False, can_switch=False,
                    launch_grace=False, reason='')
    if running is True:
        return dict(status='waiting', can_resume=False, can_switch=False,
                    launch_grace=False, reason='CS2 正在运行，等待这场比赛结束。')
    if running is not False:
        return dict(status='process_unknown', can_resume=False, can_switch=False,
                    launch_grace=False, reason='请刷新连接状态，确认 CS2 已退出。')
    stamp = session.get('launch_requested_at') or session.get('started_at')
    grace = False
    if isinstance(stamp, str):
        try:
            instant = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            if instant.tzinfo is None:
                instant = instant.replace(tzinfo=timezone.utc)
            age = ((now or datetime.now(timezone.utc)) - instant).total_seconds()
            grace = -5 <= age < LAUNCH_GRACE_SECONDS
        except ValueError:
            pass
    if grace and not seen_running:
        return dict(status='starting', can_resume=False, can_switch=False,
                    launch_grace=True, reason='CS2 正在启动，请稍候再刷新。')
    return dict(status='interrupted', can_resume=True, can_switch=True,
                launch_grace=False,
                reason='CS2 已退出。可以重新进入当前地图，或改用模拟／RTS；已完成地图保留。')


def retire_session(owner, session, mode):
    """Retired nonces stay distinct from the next map's CS2/RTS nonce.

    Late callbacks are only ingestible against an active session, never these
    records. Keep a bounded audit trail rather than counting a reset as a loss.
    """
    from copy import deepcopy
    identity = {key: deepcopy(session[key]) for key in
        ('nonce', 'map', 'cs2_map', 'map_index', 'match_id', 'started_at', 'expected_player_ids')
        if key in session}
    row = dict(session=identity, mode=mode, retired_at=utc_stamp(),
               reason='unfinished_map_restarted' if mode == 'cs2' else 'execution_mode_changed')
    owner['career3d_retired_sessions'] = (owner.get('career3d_retired_sessions', []) + [row])[-8:]
