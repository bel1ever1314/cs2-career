"""Read-only acknowledgement of current and pre-migration command receipts.

This is not a replay dispatcher. Historical receipts cannot prove that a new
command body is identical; only their original adapters validate that. Missing
or ambiguous records stay unknown and must never authorize an automatic retry.
"""
from ..storage.receipts import compact_result, lookup


def _legacy_results(state, request_id):
    incident = state.career.incident_state
    service = incident.get('career3d_service', {})
    for namespace in ('receipts', 'controls_receipts', 'tactics_import_receipts', 'season_receipts'):
        for row in service.get(namespace, []):
            if row['request_id'] == request_id:
                yield namespace, row['result']
    for row in service.get('start_receipts', []):
        if row['id'] == request_id:
            yield 'start', row['result']
    for row in incident.get('career3d_social', {}).get('receipts', []):
        if row['request_id'] == request_id:
            yield 'social', row['result']
    from .environment import STORE
    row = incident.get(STORE, {}).get('requests', {}).get(request_id)
    if row:
        yield 'environment', row['result']
    # Finished seasons can have been sealed/archived. Read, never rewrite them.
    for event in list(state.season.events) + list(state.season.history):
        for match in event.get('matches', []):
            for row in match.get('career3d_receipts', []):
                if row['request_id'] == request_id:
                    yield 'match:' + str(match['id']), row['result']

    from ..paths import save_root
    from ..manual_saves import requests
    root = save_root()
    row = requests(root).get(request_id)
    if row:
        # Pending is not proof of a completed restore or slot creation.
        yield 'manual_save', row['result'] if row.get('status') == 'done' else None


def request_result(state, request_id, *, independent_receipts=None):
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
        raise ValueError('操作编号格式不正确。')
    response = dict(ok=True, status='unknown', request_id=request_id, result=None)
    current = lookup(state.career, request_id)
    if current:
        if current.get('phase') == 'pending':
            return dict(response, source='central', reason_code='operation_pending')
        return dict(response, status='completed', source='central', result=current['result'])
    candidates = list(_legacy_results(state, request_id))
    # The adapter supplies independent runtime stores. The service does not
    # import a tool or discover/create a 3D directory while answering a read.
    if independent_receipts is not None:
        candidates.extend(independent_receipts(request_id))
    if not candidates:
        return response
    # The same start intent is deliberately mirrored in the career and draft
    # stores. Any other namespace collision is ambiguous, even if text matches.
    unique = {source for source, _ in candidates}
    results = [compact_result(result) for _, result in candidates if result is not None]
    if (len(unique) != 1 or (len(candidates) > 1 and unique != {'start'})
            or len(results) != len(candidates)
            or any(result != results[0] for result in results[1:])):
        return dict(response, reason_code='receipt_not_confirmed')
    return dict(response, status='completed', source=next(iter(unique)),
                result=compact_result(dict(results[0], ok=results[0].get('ok', True), result_summary=True)))
