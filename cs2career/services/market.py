"""Transactional commands and read-only projections for the native market."""
from ..career import skin_market
from .business import guard_revision


def read(state, query=None):
    query = query or {}
    c, day = state.career, state.season.date
    kind = query.get('view', 'market')
    if kind == 'detail':
        return dict(item=skin_market.detail(c,day,query.get('id'),query.get('wear','ft')))
    if kind == 'custody':
        rows = skin_market.custody(c,day)
        page = max(1,int(query.get('page',1)))
        return dict(rows=rows[(page-1)*18:page*18], total=len(rows), page=page, page_size=18,
                    fee=skin_market.fee(c), money=c.money)
    if kind == 'merchant':
        return skin_market.merchant(c,day)
    if kind != 'market':
        raise ValueError('没有这个市场页面。')
    return skin_market.page(c,day,query)


def command(state, action, body):
    guard_revision(state,body)
    if not state.career.exists or state.career.over():
        raise ValueError('先创建人物，再进入饰品市场。')
    return skin_market.command(state.career,state.season.date,action,body)
