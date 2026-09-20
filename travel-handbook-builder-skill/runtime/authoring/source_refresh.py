"""Narrow, transactional Markdown refresh for one route duration field."""
import copy
import hashlib
import hmac
import json
import secrets
from .errors import fail, nonempty
from .duration_evidence import duration_input, update_duration_evidence
from .routes import route_edit


def store(editor):
    if editor.package['schema_version'] not in ('1.0',):
        fail('SCHEMA_VERSION_UNSUPPORTED', 'Source duration authoring requires schema version 1.0')
    data = editor.state.setdefault('source_imports', {
        'format': 'duration-sources-1', 'signing_key': secrets.token_hex(32),
        'documents': {}, 'snapshots': {}, 'bindings': {}, 'claim_anchors': {}, 'decisions': []})
    # R13's candidate topology adapter shares the existing source workspace.
    # These are authoring metadata only: the frozen domain package and the
    # duration binding shape remain unchanged.
    data.setdefault('identity_index', {})
    data.setdefault('topology_bindings', {})
    data.setdefault('proposal_history', {})
    data.setdefault('field_bindings', {})
    data.setdefault('field_proposal_history', {})
    data.setdefault('field_decisions', [])
    return data


def source_register(editor, *, document_key, text, title=None):
    nonempty(document_key, 'document_key')
    if not isinstance(text, str):
        fail('INVALID_ARGUMENT', 'text must be an exact Unicode string', parameter='text')
    title = document_key if title is None else title
    nonempty(title, 'title')
    data = store(editor)
    document = data['documents'].setdefault(document_key, {'snapshots': []})
    if document['snapshots']:
        latest = data['snapshots'][document['snapshots'][-1]]
        if latest['text'] == text and latest['title'] == title:
            editor.parts['snapshot'] = {k: v for k, v in latest.items() if k != 'text'}
            return latest['source']
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    source = editor.add('source', {'kind': 'other', 'title': title,
        'notes': f'编制原文不可变快照；文档键 {document_key}；SHA256 {digest}'})
    identifier = editor.ref(source)['id']
    snapshot = {'source': source, 'document_key': document_key, 'sequence': len(document['snapshots']) + 1,
                'title': title, 'text': text, 'sha256': digest}
    data['snapshots'][identifier] = snapshot
    document['snapshots'].append(identifier)
    editor.parts['snapshot'] = {k: v for k, v in snapshot.items() if k != 'text'}
    return source


def locate(editor, anchor, document_key=None, *, require_latest=True):
    if not isinstance(anchor, dict) or set(anchor) != {'source', 'start', 'end', 'exact_text'}:
        fail('INVALID_ARGUMENT', 'anchor requires source, start, end and exact_text', parameter='anchor')
    data = store(editor)
    ref = editor.ref(anchor['source'], {'source'})
    snapshot = data['snapshots'].get(ref['id'])
    if snapshot is None:
        fail('SOURCE_NOT_FOUND', 'Source is not a registered text snapshot', parameter='anchor.source')
    if document_key is not None and snapshot['document_key'] != document_key:
        fail('SOURCE_DOCUMENT_MISMATCH', 'Binding belongs to another document', parameter='anchor.source')
    if require_latest and data['documents'][snapshot['document_key']]['snapshots'][-1] != ref['id']:
        fail('STALE_SOURCE_SNAPSHOT', 'Use the latest registered snapshot for this document', parameter='anchor.source')
    start, end = anchor['start'], anchor['end']
    nonempty(anchor['exact_text'], 'anchor.exact_text')
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(snapshot['text']):
        fail('INVALID_SOURCE_RANGE', 'Use a nonempty half-open Unicode code-point range', parameter='anchor')
    if snapshot['text'][start:end] != anchor['exact_text']:
        fail('SOURCE_TEXT_MISMATCH', 'Exact text does not match the saved code-point range', parameter='anchor')
    return snapshot, {**anchor, 'source': editor.handle(anchor['source'])}


def target_field(editor, target, part):
    item = editor.record(target, {'item'})
    local = editor.ref(part)
    if item.get('kind') != 'route' or item.get('lifecycle', 'current') != 'current':
        fail('REFERENCE_KIND_MISMATCH', 'target must be a current route arrangement')
    if local.get('kind') not in ('stop', 'segment') or local.get('owner') != item.get('subject_ref'):
        fail('REFERENCE_OWNER_MISMATCH', 'part must be a Stop/Segment of this route')
    record = editor.record(part)
    if 'leg_ref' in record:
        fail('UNSUPPORTED_VARIANT', 'Source refresh supports inline segments only')
    return 'dwell' if local['kind'] == 'stop' else 'duration'


def current(editor, binding):
    field = target_field(editor, binding['target'], binding['part'])
    record = editor.record(binding['part'])
    local = editor.ref(binding['part'])
    claim_target = {'object_ref': local['owner'], 'local_ref': local, 'field': field}
    active = [c for c in editor.package.get('claims', []) if c['target'] == claim_target and c.get('disposition') == 'adopted']
    if len(active) > 1:
        fail('EVIDENCE_CONFLICT', 'Multiple adopted statements cannot be refreshed')
    claim = active[0] if active else None
    return copy.deepcopy({'present': field in record, 'value': record.get(field), 'claim': claim,
        'anchor': store(editor)['claim_anchors'].get(claim['id']) if claim else None})


def proposed(editor, anchor, minutes, basis, document_key=None):
    snapshot, anchor = locate(editor, anchor, document_key)
    value, origin = duration_input({'minutes': minutes, 'basis': basis, 'statement': anchor['exact_text']}, 'minutes')
    return {'anchor': anchor, 'value': value, 'basis': origin['basis'], 'document_key': snapshot['document_key']}


def write_value(editor, binding, proposal):
    field = binding['field']
    prior = current(editor, binding)
    minutes = [proposal['value']['min_minutes'], proposal['value']['max_minutes']]
    action = 'set_stop' if field == 'dwell' else 'set_segment'
    parameter = 'dwell_minutes' if field == 'dwell' else 'duration_minutes'
    route_edit(editor, target=binding['target'], edits=[{
        'action': action, 'target': binding['part'], 'set': {parameter: minutes}}])
    update_duration_evidence(editor, binding['part'], field, prior['value'], proposal['value'],
        {'basis': proposal['basis'], 'statement': proposal['anchor']['exact_text']},
        source_ref=editor.ref(proposal['anchor']['source'], {'source'}),
        force_new=prior['anchor'] != proposal['anchor'])
    adopted = current(editor, binding)['claim']
    store(editor)['claim_anchors'][adopted['id']] = copy.deepcopy(proposal['anchor'])
    binding['baseline'] = current(editor, binding)
    binding['last_adopted'] = copy.deepcopy(proposal)
    binding.pop('handled', None)


def source_duration_adopt(editor, *, target, part, key, anchor, minutes, basis):
    nonempty(key, 'key')
    field = target_field(editor, target, part)
    proposal = proposed(editor, anchor, minutes, basis)
    data = store(editor)
    part_ref = editor.ref(part)
    if any(value.get('target_ref') == part_ref
           and value.get('aspect') == ('stop.dwell' if field == 'dwell'
                                       else 'segment.duration')
           for value in data.get('field_bindings', {}).values()):
        fail('FIELD_ALREADY_BOUND', 'This duration already has a source field binding')
    for bound in data['bindings'].values():
        if bound['document_key'] == proposal['document_key'] and bound['key'] == key:
            fail('MAPPING_ALREADY_BOUND', 'This document key is already bound; use refresh')
        if editor.ref(bound['part']) == editor.ref(part) and bound['field'] == field:
            fail('FIELD_ALREADY_BOUND', 'This duration already has a source binding')
    identifier = 'binding-' + editor.allocate_id()
    binding = {'id': identifier, 'key': key, 'document_key': proposal['document_key'],
               'target': editor.handle(target), 'part': editor.handle(part), 'field': field}
    data['bindings'][identifier] = binding
    write_value(editor, binding, proposal)
    editor.parts['binding_id'] = identifier
    editor.parts['source_outcome'] = 'adopted'
    return editor.handle(target)


def get_binding(editor, identifier):
    nonempty(identifier, 'binding_id')
    binding = store(editor)['bindings'].get(identifier)
    if binding is None:
        fail('BINDING_NOT_FOUND', 'No source binding; explicitly adopt once before refreshing')
    return binding


def signature(data, payload):
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hmac.new(bytes.fromhex(data['signing_key']), encoded, hashlib.sha256).hexdigest()


def make_payload(editor, binding, proposal):
    return {'workspace_id': editor.state['workspace_id'], 'revision': editor.state['revision'],
            'binding_id': binding['id'], 'baseline': copy.deepcopy(binding['baseline']),
            'current': current(editor, binding), 'proposal': copy.deepcopy(proposal)}


def same_content(view, proposal):
    claim = view['claim']
    return (view['present'] and view['value'] == proposal['value'] and claim is not None
            and claim['basis'] == proposal['basis'] and claim['statement'] == proposal['anchor']['exact_text'])


def source_duration_refresh(editor, *, binding_id, anchor, minutes, basis):
    binding = get_binding(editor, binding_id)
    proposal = proposed(editor, anchor, minutes, basis, binding['document_key'])
    view = current(editor, binding)
    handled = binding.get('handled')
    if handled and handled['proposal'] == proposal and handled['current'] == view:
        outcome = handled['outcome']
    elif view == binding['baseline']:
        write_value(editor, binding, proposal)
        outcome = 'adopted'
    elif same_content(view, proposal):
        outcome = 'already_matches'
        binding['handled'] = {'proposal': copy.deepcopy(proposal), 'current': view, 'outcome': outcome}
    else:
        payload = make_payload(editor, binding, proposal)
        fail('IMPORT_CONFLICT', 'Current value or evidence differs from the last source write',
             conflict={'payload': payload, 'signature': signature(store(editor), payload)})
    editor.parts['binding_id'] = binding_id
    editor.parts['source_outcome'] = outcome
    return editor.handle(binding['target'])


def source_duration_resolve(editor, *, conflict, choice, reason):
    if choice not in ('apply_proposed', 'keep_current'):
        fail('INVALID_ARGUMENT', 'Choose apply_proposed or keep_current', parameter='choice')
    nonempty(reason, 'reason')
    if not isinstance(conflict, dict) or set(conflict) != {'payload', 'signature'}:
        fail('INVALID_CONFLICT', 'Use the conflict returned by a failed refresh unchanged')
    payload, provided = conflict['payload'], conflict['signature']
    data = store(editor)
    if (not isinstance(payload, dict) or not isinstance(provided, str) or len(provided) != 64
            or any(c not in '0123456789abcdef' for c in provided)
            or not hmac.compare_digest(signature(data, payload), provided)):
        fail('INVALID_CONFLICT', 'Conflict was not issued by this workspace or has been changed')
    if payload['workspace_id'] != editor.state['workspace_id'] or payload['revision'] != editor.state['revision']:
        fail('STALE_CONFLICT', 'Workspace changed since this conflict; refresh again')
    if any(decision['conflict'] == payload for decision in data['decisions']):
        fail('CONFLICT_ALREADY_RESOLVED', 'This conflict has already been resolved in this batch')
    binding = get_binding(editor, payload['binding_id'])
    old = payload['proposal']
    proposal = proposed(editor, old['anchor'], [old['value']['min_minutes'], old['value']['max_minutes']],
                        old['basis'], binding['document_key'])
    if make_payload(editor, binding, proposal) != payload:
        fail('STALE_CONFLICT', 'Binding, source or current field changed; refresh again')
    if choice == 'apply_proposed':
        write_value(editor, binding, proposal)
        outcome = 'adopted'
    else:
        outcome = 'kept_current'
        binding['handled'] = {'proposal': copy.deepcopy(proposal), 'current': current(editor, binding), 'outcome': outcome}
    data['decisions'].append({'id': 'decision-' + editor.allocate_id(), 'binding_id': binding['id'],
        'choice': choice, 'reason': reason, 'conflict': copy.deepcopy(payload)})
    editor.parts['binding_id'] = binding['id']
    editor.parts['source_outcome'] = outcome
    return editor.handle(binding['target'])
