"""Bounded immutable coverage confirmations, not a general event store.

Only current active confirmations may be revised. Entire existing scopes can
be revoked; splitting persons, benefit kinds, dates or shared quotas is absent.
"""
import copy
from .errors import fail, nonempty


from coverage_checks import aggregate_state, coverage_revision_errors
from coverage_checks import coverage_projection as _coverage_projection


def coverage_projection(package):
    errors = coverage_revision_errors(package)
    if errors:
        fail('MODEL_VALIDATION', 'Invalid coverage confirmation history', errors=errors)
    return _coverage_projection(package)


def current_active(editor, target):
    if editor.package['schema_version'] not in ('1.0',):
        fail('SCHEMA_VERSION_UNSUPPORTED', 'Confirmation revisions require schema version 1.0', supported_version='1.0')
    record = editor.record(target, {'coverage'})
    if any(value.get('supersedes_ref') == editor.ref(target) for value in editor.package.get('coverages', [])):
        fail('STALE_CONFIRMATION', 'Use the current confirmation returned by read; historical handles do not move', parameter='target')
    if record['state'] != 'active':
        fail('COVERAGE_NOT_ACTIVE', 'Only an active current entitlement may be revised', parameter='target')
    return record


def scope_from_handle(editor, handle, owner):
    ref = editor.ref(handle)
    if ref.get('kind') != 'scope' or ref.get('owner') != owner:
        fail('COVERAGE_SCOPE_MISMATCH', 'Select a scope owned by this exact current confirmation', parameter='scopes')
    return editor.record(handle)


def handle_for_ref(editor, ref):
    handle = next((handle for handle, candidate in editor.state['handles'].items() if candidate == ref), None)
    if handle is None:
        fail('STATE_FORMAT', 'Expected a registered stable handle for this snapshot')
    return {'handle': handle}


def add_mapping(editor, old_ref, old_scopes, new_handle, keys):
    new_ref = editor.ref(new_handle)
    new = editor.record(new_handle)
    editor.parts['scopes'] = {}
    editor.parts['scope_replacements'] = []
    for key, old, scope in zip(keys, old_scopes, new['scopes']):
        current = editor.register_local(new_ref, 'scope', scope)
        old_scope_ref = {'owner': old_ref, 'kind': 'scope', 'id': old['id']}
        editor.parts['scopes'][key] = current
        editor.parts['scope_replacements'].append({'previous': handle_for_ref(editor, old_scope_ref), 'current': current})


def coverage_replace_confirmation(editor, *, target, benefits, scopes, reservation=None, limits=None):
    """Replace a full confirmation, keeping its order and exact scope targets.

    scopes: [{key, previous_scope, target, validity?, participants?, quantity?}].
    Unknown snapshot inputs stay unknown. Omitted reservation preserves the
    existing association; omitted limits means absent in the new full snapshot.
    """
    from .reservations import coverage_record
    previous = current_active(editor, target)
    previous_ref = editor.ref(target)
    if not isinstance(scopes, list) or not scopes:
        fail('INVALID_ARGUMENT', 'Provide a complete nonempty scope snapshot', parameter='scopes')
    new_scopes, prior_scopes, keys = [], [], []
    for index, value in enumerate(scopes):
        path = f'scopes[{index}]'
        if not isinstance(value, dict) or not {'key', 'previous_scope', 'target'} <= value.keys() or value.keys() - {'key', 'previous_scope', 'target', 'validity', 'participants', 'quantity'}:
            fail('INVALID_ARGUMENT', 'Each full scope needs key, previous_scope and target, plus its known facts', parameter=path)
        nonempty(value['key'], path + '.key')
        old = scope_from_handle(editor, value['previous_scope'], previous_ref)
        if editor.ref(value['target']) != old['target_ref']:
            fail('MODEL_GAP', 'Changing or adding alternative execution applicability needs a separate model', parameter=path + '.target')
        prior_scopes.append(old)
        keys.append(value['key'])
        new_scopes.append({key: copy.deepcopy(v) for key, v in value.items() if key != 'previous_scope'})
    if len(set(keys)) != len(keys):
        fail('INVALID_ARGUMENT', 'Scope keys must be distinct', parameter='scopes')
    if len(prior_scopes) != len(previous['scopes']) or {s['id'] for s in prior_scopes} != {s['id'] for s in previous['scopes']}:
        fail('MODEL_GAP', 'Map every existing scope exactly once; do not split, add or remove applicability', parameter='scopes')
    existing_reservation = previous.get('reservation_ref')
    if reservation is None:
        reservation = handle_for_ref(editor, existing_reservation) if existing_reservation else None
    elif editor.ref(reservation, {'reservation'}) != existing_reservation:
        fail('MODEL_GAP', 'A replacement confirmation cannot switch or newly attach an order', parameter='reservation')
    handle = coverage_record(editor, benefits=benefits, scopes=new_scopes, reservation=reservation, limits=limits)
    record = editor.record(handle)
    record['supersedes_ref'] = previous_ref
    for old, scope in zip(prior_scopes, record['scopes']):
        scope['previous_scope_id'] = old['id']
        scope['state'] = old['state']
    record['state'] = aggregate_state(record['scopes'])
    add_mapping(editor, previous_ref, prior_scopes, handle, keys)
    return handle


def coverage_revoke_scopes(editor, *, target, scopes):
    """Record revocation of complete existing scopes, creating a new snapshot."""
    previous = current_active(editor, target)
    previous_ref = editor.ref(target)
    if not isinstance(scopes, list) or not scopes:
        fail('INVALID_ARGUMENT', 'Select nonempty whole-scope handles', parameter='scopes')
    selected = [scope_from_handle(editor, value, previous_ref) for value in scopes]
    identifiers = {scope['id'] for scope in selected}
    if len(identifiers) != len(selected):
        fail('INVALID_ARGUMENT', 'Do not select a scope twice', parameter='scopes')
    if any(scope['state'] != 'active' for scope in selected):
        fail('COVERAGE_SCOPE_NOT_ACTIVE', 'Only an active scope can be revoked', parameter='scopes')
    fields = {key: copy.deepcopy(value) for key, value in previous.items() if key != 'id'}
    fields['supersedes_ref'] = previous_ref
    for old, scope in zip(previous['scopes'], fields['scopes']):
        scope['id'] = editor.allocate_id()
        scope['previous_scope_id'] = old['id']
        if old['id'] in identifiers:
            scope['state'] = 'revoked'
    fields['state'] = aggregate_state(fields['scopes'])
    handle = editor.add('coverage', fields)
    add_mapping(editor, previous_ref, previous['scopes'], handle, [str(index) for index in range(len(previous['scopes']))])
    return handle
