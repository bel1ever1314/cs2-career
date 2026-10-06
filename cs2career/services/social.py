"""Persisted phone conversations in the isolated career's additive incident state.

GET projection never creates contacts/messages, acknowledges stories or saves.
The service owns its lock, revision and final persist. Story hooks run around
the original ack_story; their copy cannot change career rewards or world rules.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

KEY = 'career3d_social'
COPY_FILE = Path(__file__).resolve().parents[2] / 'work/career3d_redesign/data/phone_social.json'


def _copy():
    cfg = json.loads(COPY_FILE.read_text('utf-8'))
    # Only the selected, isolated extension directory can override phone copy.
    extension_root = os.environ.get('CS2CAREER_EXTENSION_DIR')
    if extension_root:
        override = Path(extension_root) / 'phone_social.json'
        if override.is_file():
            extra = json.loads(override.read_text('utf-8'))
            for section in ('topics', 'birthday'):
                if isinstance(extra.get(section), dict):
                    for key, item in extra[section].items():
                        if isinstance(item, dict):
                            cfg[section][key] = {**cfg[section].get(key, {}), **item}
    return cfg


def _text(value, name=''):
    return str(value or '').replace('{name}', name)[:10000]


def _saved(state):
    return state.career.incident_state.get(KEY, {})


def _store(state):
    return state.career.incident_state.setdefault(KEY, {
        'schema_version': 1, 'contacts': {}, 'events': {}, 'receipts': []})


def _roster(state):
    c, s = state.career, state.season
    team = c.my_team(s.teams) or {}
    you = c.my_player(s.teams) or c.you_card or {}
    rows = []
    if team.get('id'):
        rows.append(dict(id='coach:' + team['id'], name='教练', topic='coach', team_id=team['id']))
    for member in team.get('players', []):
        ident = str(member.get('player_id') or '')
        if ident and not member.get('you') and ident != you.get('player_id'):
            rows.append(dict(id=ident, name=member.get('name') or '队友', topic='teammate', team_id=team.get('id', '')))
    return rows


def social_context(state):
    """Small contacts projection; historical threads keep their identity on transfer."""
    cfg, saved = _copy(), _saved(state)
    current = _roster(state)
    ids = {row['id'] for row in current}
    current += [dict(row, archived=True) for ident, row in saved.get('contacts', {}).items()
                if ident not in ids]
    contacts = []
    for row in current:
        persisted = saved.get('contacts', {}).get(row['id'], {})
        topic = cfg['topics'].get(row.get('topic'), cfg['topics']['teammate'])
        messages = deepcopy(persisted.get('messages', []))
        contacts.append({**deepcopy(row), 'messages': messages,
                         'greeting': _text(topic.get('greeting'), row['name']),
                         'replies': [{'id': str(reply['id']), 'label': _text(reply.get('label')),
                                      **({'page': reply['page']} if reply.get('page') else {})}
                                     for reply in topic.get('replies', [])],
                         'preview': messages[-1]['text'] if messages else _text(topic.get('greeting'), row['name'])})
    return {'contacts': contacts}


def _contact_for_story(state, row):
    explicit = row.get('social') if isinstance(row.get('social'), dict) else {}
    context = row.get('context') or {}
    ident = str(explicit.get('contact_id') or explicit.get('player_id') or row.get('player_id')
                or context.get('target_id') or context.get('person_id') or '')
    roster = _roster(state)
    if not ident and row.get('when') == 'teammate_birthday':
        matches = [r for r in roster if r['topic'] == 'teammate' and r['name'] == row.get('player')]
        return deepcopy(matches[0]) if len(matches) == 1 else None
    if not ident and row.get('when') == 'major_coach':
        return next((deepcopy(r) for r in roster if r['topic'] == 'coach'), None)
    if not ident:
        return None
    match = next((r for r in roster if r['id'] == ident), None)
    if match:
        return deepcopy(match)
    if ident in _saved(state).get('contacts', {}):
        return {k: deepcopy(v) for k, v in _saved(state)['contacts'][ident].items() if k != 'messages'}
    # Only an explicit content-pack identity may introduce a non-roster person.
    if explicit.get('name') and 1 <= len(ident) <= 160:
        return dict(id=ident, name=_text(explicit['name']), topic='person', team_id='')
    return None


def before_story_choice(state, row, choice):
    """Capture an exact person link before a choice can replace the roster."""
    contact = _contact_for_story(state, row)
    if not contact:
        return None
    return dict(row=deepcopy(row), choice=str(choice), contact=contact, date=state.season.date)


def _thread(store, contact):
    saved = store['contacts'].setdefault(contact['id'], {**deepcopy(contact), 'messages': []})
    # Current contact names may change; the stable ID and old frozen lines do not.
    saved.update({k: deepcopy(v) for k, v in contact.items() if k != 'messages'})
    return saved['messages']


def _append(lines, ident, stamp, sender, name, text, **source):
    if not text or any(row['id'] == ident for row in lines):
        return
    lines.append(dict(id=ident, date=stamp, sender=sender, name=name, text=text, **source))


def after_story_choice(state, captured):
    """Mirror successful, person-linked decisions once; preserve original story gates."""
    if not captured:
        return {}
    row, choice, contact = captured['row'], captured['choice'], captured['contact']
    sid = str(row.get('id') or '')
    if not sid or sid not in state.career.seen_stories:
        return {}
    store = _store(state)
    if sid in store['events']:
        return dict(store['events'][sid], replayed=True)
    stamp = captured['date']
    lines = _thread(store, contact)
    prefix = 'story:' + sid
    label = next((c.get('label', choice) for c in row.get('choices', []) if c.get('id') == choice), '')
    source = dict(source_story_id=sid, choice_id=choice)
    focus = prefix + ':narrative'
    if row.get('when') == 'teammate_birthday':
        birthday = _copy()['birthday']['train' if choice == 'train' else 'wish']
        # Domain prose is frozen by arcs.birthday. Never regenerate/reroll it.
        reaction_id = f"arc-notice:{stamp}:birthday:{row.get('player', '')}"
        reaction = next((r for r in state.career.story_queue if r.get('id') == reaction_id), None)
        if reaction is None:
            reaction = next((r for r in state.career.incident_state.get('arcs', {}).get('history', [])
                             if r.get('id') == reaction_id), None)
        if birthday.get('outgoing'):
            _append(lines, prefix + ':you', stamp, 'you', '你', _text(birthday['outgoing'], contact['name']), **source)
        narrative = reaction.get('text', '') if reaction else row.get('text', '')
        _append(lines, focus, stamp, 'narrator', (reaction or row).get('title', '生日'), narrative, **source)
        _append(lines, prefix + ':reply', stamp, 'contact', contact['name'], _text(birthday.get('reply'), contact['name']), **source)
    else:
        _append(lines, focus, stamp, 'narrator', row.get('title', '队内事件'), row.get('text', ''), **source)
        _append(lines, prefix + ':you', stamp, 'you', '你', label, **source)
        explicit = row.get('social') or {}
        reply = (explicit.get('replies') or {}).get(choice, explicit.get('reply', ''))
        # A scene involving somebody is not automatically dialogue spoken by them.
        _append(lines, prefix + ':reply', stamp, 'contact', contact['name'], _text(reply, contact['name']), **source)
    result = dict(social_contact_id=contact['id'], social_focus_message_id=focus,
                  social_message_ids=[r['id'] for r in lines if r.get('source_story_id') == sid])
    store['events'][sid] = deepcopy(result)
    return result


def social_command(state, body):
    """Saved authored quick replies; duplicate receipts never emit a second response."""
    from cs2career.storage.receipts import needs_legacy_receipt
    ident, reply_id = str(body.get('contact_id') or ''), str(body.get('reply_id') or '')
    request_id = body.get('request_id')
    if not isinstance(request_id, str) or not 8 <= len(request_id) <= 100:
        raise ValueError('request_id 必须是 8 至 100 字符的唯一编号。')
    saved = _saved(state)
    receipt = next((r for r in saved.get('receipts', []) if r['request_id'] == request_id), None)
    if receipt:
        if receipt['contact_id'] != ident or receipt['reply_id'] != reply_id:
            raise ValueError('这个 request_id 已用于另一条消息。')
        return dict(receipt['result'], replayed=True)
    from cs2career.services.business import guard_revision
    guard_revision(state, body)
    contact = next((r for r in social_context(state)['contacts'] if r['id'] == ident), None)
    if not contact:
        raise ValueError('联系人不存在，请刷新手机。')
    topic = _copy()['topics'].get(contact.get('topic'), _copy()['topics']['teammate'])
    reply = next((r for r in topic.get('replies', []) if r['id'] == reply_id), None)
    if not reply:
        raise ValueError('请选择当前对话提供的有效回复。')
    contact = {k: v for k, v in contact.items() if k in ('id', 'name', 'topic', 'team_id')}
    store = _store(state)
    lines = _thread(store, contact)
    stamp = state.season.date
    prefix = 'message:' + hashlib.sha256(request_id.encode()).hexdigest()[:24]
    if not lines:
        _append(lines, 'greeting:' + ident, stamp, 'contact', contact['name'], _text(topic.get('greeting'), contact['name']))
    _append(lines, prefix + ':you', stamp, 'you', '你', _text(reply.get('label')))
    _append(lines, prefix + ':reply', stamp, 'contact', contact['name'], _text(reply.get('reply'), contact['name']))
    result = dict(reason='消息已发送。', social_contact_id=ident, social_focus_message_id=prefix + ':you')
    if reply.get('page'):
        result['social_page'] = reply['page']
    if needs_legacy_receipt(request_id):
        store['receipts'].append(dict(request_id=request_id, contact_id=ident, reply_id=reply_id, result=deepcopy(result)))
    return result
