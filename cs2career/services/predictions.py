"""Native prediction adapter; HTTP owns lock, revision, receipts and commit."""
from ..career import predictions
from .business import guard_revision


def read(state, query=None):
    return predictions.page(state.career, state.season, query)


def stop_reason(state):
    from .matches import _reason
    from ..league.tournament_auto import blocker
    from ..career.story_timing import window
    from ..career.fast_mode import season_complete
    c, s = state.career, state.season
    reason = _reason(state) or blocker(c, s)
    pause = window(c, s)
    if pause and c.assist.get('quick_break_ack') != pause['key']:
        reason = reason or 'Major 休赛期到了，请先处理休赛安排。'
    if season_complete(s):
        reason = reason or '本赛季已结束，请先继续下一赛季。'
    if s.find_your_series():
        reason = reason or '轮到你的比赛了，请先处理自己的比赛。'
    return reason


def command(state, action, body):
    guard_revision(state, body)
    c, s = state.career, state.season
    if not c.exists or c.over():
        raise ValueError('请先创建一段仍在进行的生涯。')
    if action == 'buy':
        return predictions.buy(c, s, body)
    if action != 'advance':
        raise ValueError('没有这个竞猜操作。')
    reason = stop_reason(state)
    if reason:
        return dict(reason=reason, prediction_status='paused')
    if predictions.available(c, s):
        return dict(reason='已有可参与的对阵，尚未推进比赛。', prediction_status='ready')
    for _ in range(24):
        before = (s.date, tuple((e['id'], e['status'], len(e.get('matches', []))) for e in s.events))
        reason = s.next_stage(stop_at_season_end=True, prepare_only=True, prediction_stop=True)
        state.settle()
        blocked = stop_reason(state)
        ready = bool(predictions.available(c, s))
        if blocked or ready:
            return dict(reason=blocked or '已停在赛前，请选择竞猜或继续推进。',
                        prediction_status='paused' if blocked else 'ready')
        if before == (s.date, tuple((e['id'], e['status'], len(e.get('matches', []))) for e in s.events)):
            break
    return dict(reason=reason, prediction_status='progress')
