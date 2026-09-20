"""First recording of accommodation or transport orders and independently stated entitlements."""
import copy
from .errors import fail, nonempty


def require_record_origin(origin, *, example):
    if not isinstance(origin, dict) or set(origin) != {'basis', 'statement'}:
        fail('MISSING_FACTS', 'Recording an external order or entitlement requires operation.origin with basis and statement', parameter='origin')
    nonempty(origin['statement'], 'origin.statement')
    if origin['basis'] == 'estimate' or (origin['basis'] == 'synthetic_fixture' and not example):
        fail('INVALID_EVIDENCE', 'An estimate or invented real-trip fixture cannot establish an external order or entitlement', parameter='origin.basis')


def execution_ref(editor, target):
    ref = editor.ref(target)
    if ref.get('type') not in ('stay', 'journey', 'leg') and not (ref.get('kind') == 'unit' and ref.get('owner', {}).get('type') == 'stay'):
        fail('REFERENCE_KIND_MISMATCH', 'Use a Stay, Stay Unit, Journey or Leg handle; an arrangement Item is not its Journey', parameter='target')
    return ref


def reservation_record(editor, *, provider, status, targets, cancellation_terms=None, recorded_at=None):
    nonempty(provider, 'provider')
    if not isinstance(targets, list) or not targets:
        fail('INVALID_ARGUMENT', 'targets must be a nonempty list of Stay, Unit, Journey or Leg handles', parameter='targets')
    refs = []
    for target in targets:
        ref = execution_ref(editor, target)
        if ref in refs:
            fail('INVALID_ARGUMENT', 'Do not repeat a reservation target', parameter='targets')
        refs.append(ref)
    fields = {'provider': provider, 'status': status, 'target_refs': refs}
    if recorded_at is not None:
        fields['recorded_at'] = recorded_at
    if cancellation_terms is not None:
        if not isinstance(cancellation_terms, list):
            fail('INVALID_ARGUMENT', 'cancellation_terms must be a list', parameter='cancellation_terms')
        for index, term in enumerate(cancellation_terms):
            parameter = f'cancellation_terms[{index}]'
            if not isinstance(term, dict) or 'description' not in term or set(term) - {'description', 'deadline', 'boundary'} or any(v is None for v in term.values()):
                fail('INVALID_ARGUMENT', 'A cancellation term needs description; deadline and boundary are optional together', parameter=parameter)
            nonempty(term['description'], parameter + '.description')
            if ('deadline' in term) != ('boundary' in term):
                fail('MISSING_FACTS', 'Supply both deadline and its before/not_after boundary, or preserve description alone', parameter=parameter)
        fields['cancellation_terms'] = cancellation_terms
    return editor.add('reservation', fields)


def build_scope(editor, *, target, validity=None, participants=None, quantity=None):
    target_ref = execution_ref(editor, target)
    validity = {'kind': 'unknown'} if validity is None else copy.deepcopy(validity)
    if not isinstance(validity, dict) or not (validity.get('kind') in ('unknown', 'local_dates') or ('kind' not in validity and 'date' in validity)):
        fail('UNSUPPORTED_VARIANT', 'Provide independent unknown/local_dates/single-date validity; never inherit a plan period', parameter='validity')
    if 'from_ref' in validity:
        fail('INVALID_ARGUMENT', 'Confirmed validity cannot inherit from a plan', parameter='validity')
    quantity = {'kind': 'unknown'} if quantity is None else copy.deepcopy(quantity)
    if quantity != {'kind': 'unknown'}:
        if not isinstance(quantity, dict) or set(quantity) != {'unit', 'count'} or type(quantity['count']) is not int or quantity['count'] <= 0:
            fail('INVALID_ARGUMENT', 'Quantity must be unknown or an explicit positive integer count with a unit', parameter='quantity')
        nonempty(quantity['unit'], 'quantity.unit')
    participant_value = {'kind': 'unknown'}
    if participants is not None:
        if editor.package.get('schema_version') in ('1.0',):
            from .party import participant_member_snapshot
            participant_value = participant_member_snapshot(
                editor, participants, 'participants')
        else:
            participant_value = copy.deepcopy(participants)
    scope = {'id': editor.allocate_id(), 'target_ref': target_ref, 'validity': validity,
             'participants': participant_value, 'quantity': quantity}
    if editor.package['schema_version'] in ('1.0',):
        scope['state'] = 'active'
    return scope


def reservation_covers(editor, booking, target_ref):
    targets = booking['target_refs']
    if target_ref in targets:
        return True
    if target_ref.get('kind') == 'unit' and target_ref.get('owner') in targets:
        return True
    if target_ref.get('type') == 'leg':
        return any({'type': 'journey', 'id': journey['id']} in targets and target_ref in journey['leg_refs']
                   for journey in editor.package.get('journeys', []))
    return False


def coverage_record(editor, *, benefits, target=None, scopes=None, reservation=None, validity=None,
                    participants=None, quantity=None, limits=None):
    if (target is None) == (scopes is None):
        fail('INVALID_ARGUMENT', 'Choose exactly one target or explicit scopes list')
    if scopes is not None and any(value is not None for value in (validity, participants, quantity)):
        fail('CONFLICTING_EDIT', 'With scopes, put validity/participants/quantity inside each scope')
    if not isinstance(benefits, list) or not benefits:
        fail('INVALID_ARGUMENT', 'Provide explicitly acquired benefits, not desired requests', parameter='benefits')
    for index, benefit in enumerate(benefits):
        parameter = f'benefits[{index}]'
        if not isinstance(benefit, dict) or 'kind' not in benefit or set(benefit) - {'kind', 'notes', 'value'}:
            fail('INVALID_ARGUMENT', 'Each benefit needs kind; optional notes and value are text', parameter=parameter)
        for field, value in benefit.items():
            nonempty(value, parameter + '.' + field)
    if target is not None:
        scope_records = [build_scope(editor, target=target, validity=validity, participants=participants, quantity=quantity)]
        keys = ['scope']
    else:
        if not isinstance(scopes, list) or not scopes:
            fail('INVALID_ARGUMENT', 'scopes must be a nonempty list', parameter='scopes')
        keys, scope_records = [], []
        for entry in scopes:
            if not isinstance(entry, dict) or not {'key', 'target'} <= entry.keys() or set(entry) - {'key', 'target', 'validity', 'participants', 'quantity'} or any(v is None for v in entry.values()):
                fail('INVALID_ARGUMENT', 'Each scope needs key/target and optional independent validity/participants/quantity', parameter='scopes')
            key = entry['key']; nonempty(key, 'scopes.key')
            if key in keys:
                fail('DUPLICATE_ALIAS', 'Scope keys must be unique within this operation', parameter='scopes.key')
            keys.append(key)
            scope_records.append(build_scope(editor, **{k: v for k, v in entry.items() if k != 'key'}))
    fields = {'state': 'active', 'benefits': benefits, 'scopes': scope_records}
    if reservation is not None:
        booking = editor.record(reservation, {'reservation'})
        if booking['status'] != 'confirmed':
            fail('RESERVATION_NOT_CONFIRMED', 'This order does not establish an active entitlement; do not auto-upgrade its status', parameter='reservation')
        if any(not reservation_covers(editor, booking, scope['target_ref']) for scope in scope_records):
            fail('RESERVATION_SCOPE_MISMATCH', 'An entitlement target is outside the recorded reservation scope', parameter='target')
        fields['reservation_ref'] = editor.ref(reservation, {'reservation'})
    if limits is not None:
        fields['limits'] = limits
    result = editor.add('coverage', fields)
    editor.parts['scopes'] = {key: editor.register_local(editor.ref(result), 'scope', scope)
                              for key, scope in zip(keys, editor.record(result)['scopes'])}
    return result
