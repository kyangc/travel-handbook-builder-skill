"""Shared R11/R12 deletion protection and stable-handle retirement."""
import copy

from .errors import fail


EDIT_VERSIONS = {'1.0'}

COLLECTION_TYPES = {
    'days': 'day', 'items': 'item', 'stays': 'stay',
    'recommendations': 'recommendation', 'reservations': 'reservation',
    'coverages': 'coverage', 'tasks': 'task', 'price_quotes': 'price_quote',
    'costs': 'cost', 'payments': 'payment', 'exchange_rates': 'exchange_rate',
    'claims': 'claim', 'routes': 'route', 'paths': 'path',
    'journeys': 'journey', 'legs': 'leg',
    'transport_services': 'transport_service', 'vehicle_uses': 'vehicle_use',
    'sources': 'source', 'guide_notes': 'guide_note',
    'activities': 'activity', 'service_uses': 'service_use',
    'service_bundles': 'service_bundle', 'issues': 'issue', 'media': 'media',
}

OWNER_EXECUTION_CLAIM_FIELDS = {
    'item': {'timing', 'movement'},
    'journey': {'leg_refs', 'connections', 'timing', 'movement',
                'start', 'end', 'duration'},
    'route': {'stops', 'segments', 'timing', 'movement',
              'start', 'end', 'duration'},
}
EXECUTION_CLAIM_DISPOSITIONS = {'adopted', 'superseded'}


def require_execution_edit_version(editor):
    if editor.package.get('schema_version') not in EDIT_VERSIONS:
        fail('SCHEMA_VERSION_UNSUPPORTED',
             'Execution replacement requires schema version 1.0',
             supported_version='1.0')


def handle_for_ref(editor, ref, parameter=None):
    handle = next((value for value, stored in editor.state['handles'].items()
                   if stored == ref), None)
    if handle is None:
        fail('STATE_FORMAT', 'Current execution object has no stable workspace handle',
             parameter=parameter, target_ref=copy.deepcopy(ref))
    return {'handle': handle}


def _reference_paths(value, target, path):
    found = []
    if isinstance(value, dict):
        if value == target:
            return [path]
        for key, child in value.items():
            found.extend(_reference_paths(child, target, f'{path}/{key}'))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_reference_paths(child, target, f'{path}/{index}'))
    return found


def _record_ref(collection, record):
    kind = COLLECTION_TYPES.get(collection)
    if kind is None or not isinstance(record, dict) or 'id' not in record:
        return None
    return {'type': kind, 'id': record['id']}


def _path_for_ref(package, ref):
    if not isinstance(ref, dict) or 'type' not in ref:
        return None
    for collection, kind in COLLECTION_TYPES.items():
        if kind != ref['type']:
            continue
        for index, record in enumerate(package.get(collection, [])):
            if record.get('id') == ref.get('id'):
                return f'/{collection}/{index}'
    return None


def domain_reference_blockers(package, removed_refs, *, structural_owners):
    """Find live domain references while ignoring the owner topology being replaced."""
    blockers = []
    for collection, records in package.items():
        if not isinstance(records, list):
            continue
        for index, record in enumerate(records):
            record_ref = _record_ref(collection, record)
            if record_ref in structural_owners:
                continue
            root = f'/{collection}/{index}'
            for removed in removed_refs:
                for path in _reference_paths(record, removed, root):
                    value = {'kind': 'domain_reference', 'path': path,
                             'target_ref': copy.deepcopy(removed)}
                    if record_ref is not None:
                        value['ref'] = record_ref
                    if value not in blockers:
                        blockers.append(value)
    return blockers


def active_source_binding_blockers(editor, removed_handles):
    """Only active field bindings protect deletion in the current R13 storage shape.

    Pure identity indexes and topology baselines deliberately do not participate
    here. Legal typed replacement tombstones identities separately without
    turning historical snapshots into live object references.
    """
    blockers = []
    bindings = editor.state.get('source_imports', {}).get('bindings', {})
    for binding_id, binding in bindings.items():
        for field in ('target', 'part'):
            if binding.get(field) not in removed_handles:
                continue
            blockers.append({
                'kind': 'source_field_binding',
                'binding_id': binding_id,
                'field': field,
                'path': f'/source_imports/bindings/{binding_id}/{field}',
                'handle': copy.deepcopy(binding[field]),
            })
    field_bindings = editor.state.get(
        'source_imports', {}).get('field_bindings', {})
    for binding_id, binding in field_bindings.items():
        if binding.get('target') not in removed_handles:
            continue
        blockers.append({
            'kind': 'source_field_binding',
            'binding_id': binding_id,
            'field': binding.get('aspect'),
            'path': f'/source_imports/field_bindings/{binding_id}/target',
            'handle': copy.deepcopy(binding['target']),
        })
    return blockers


def owner_execution_blockers(package, refs):
    """Reuse the bounded existing definition of confirmation/completion protection."""
    from .item_times import item_time_change_blockers

    blockers = []
    for target_ref in refs:
        for blocker in item_time_change_blockers(package, target_ref):
            value = {**copy.deepcopy(blocker),
                     'via_target_ref': copy.deepcopy(target_ref)}
            path = _path_for_ref(package, blocker.get('ref'))
            if path is not None:
                value['path'] = path
            if value not in blockers:
                blockers.append(value)
    # Reusing the owner identity changes the meaning of historical records too.
    # existing projects only current effective facts, so include durable execution
    # history that still names the whole Journey/Route/Item.
    for index, coverage in enumerate(package.get('coverages', [])):
        if any(scope.get('target_ref') in refs for scope in coverage.get('scopes', [])):
            value = {'kind': 'coverage',
                     'ref': {'type': 'coverage', 'id': coverage['id']},
                     'path': f'/coverages/{index}', 'historical': True}
            if value not in blockers:
                blockers.append(value)
    for index, reservation in enumerate(package.get('reservations', [])):
        if (reservation.get('status') in {'confirmed', 'cancelled'}
                and any(ref in refs for ref in reservation.get('target_refs', []))):
            value = {'kind': 'reservation',
                     'ref': {'type': 'reservation', 'id': reservation['id']},
                     'path': f'/reservations/{index}', 'historical': True}
            if value not in blockers:
                blockers.append(value)
    for index, cost in enumerate(package.get('costs', [])):
        if ('confirmed' in cost
                and any(ref in refs for ref in cost.get('target_refs', []))):
            value = {'kind': 'cost', 'ref': {'type': 'cost', 'id': cost['id']},
                     'path': f'/costs/{index}', 'historical': True}
            if value not in blockers:
                blockers.append(value)
    for index, claim in enumerate(package.get('claims', [])):
        target = claim.get('target', {})
        target_ref = target.get('object_ref')
        affected_fields = OWNER_EXECUTION_CLAIM_FIELDS.get(
            target_ref.get('type') if isinstance(target_ref, dict) else None, set())
        disposition = claim.get('disposition', 'adopted')
        if (target_ref in refs and 'local_ref' not in target
                and target.get('field') in affected_fields
                and claim.get('basis') in {'confirmation', 'observation'}
                and disposition in EXECUTION_CLAIM_DISPOSITIONS):
            ref = {'type': 'claim', 'id': claim['id']}
            if any(value.get('ref') == ref
                   and value.get('via_target_ref') == target_ref
                   for value in blockers):
                continue
            value = {'kind': 'claim', 'ref': ref,
                     'path': f'/claims/{index}',
                     'field': target['field'], 'disposition': disposition,
                     'historical': disposition == 'superseded',
                     'via_target_ref': copy.deepcopy(target_ref)}
            if value not in blockers:
                blockers.append(value)
    return blockers


def protect_execution_replacement(editor, removed_refs, *, structural_owners,
                                  protected_owner_refs=()):
    removed_handles = [handle_for_ref(editor, ref) for ref in removed_refs]
    blockers = domain_reference_blockers(
        editor.package, removed_refs, structural_owners=structural_owners)
    blockers.extend(active_source_binding_blockers(editor, removed_handles))
    blockers.extend(owner_execution_blockers(editor.package, protected_owner_refs))
    deduplicated = []
    for blocker in blockers:
        if blocker not in deduplicated:
            deduplicated.append(blocker)
    if deduplicated:
        blocker_refs = []
        for value in deduplicated:
            if 'ref' in value and value['ref'] not in blocker_refs:
                blocker_refs.append(copy.deepcopy(value['ref']))
        fail('EXECUTION_HISTORY_REQUIRED',
             'The current model cannot delete execution objects that still have live references',
             removed_refs=copy.deepcopy(removed_refs), blockers=deduplicated,
             blocker_refs=blocker_refs)
    return removed_handles


def retire_handles(editor, refs):
    handles = [handle_for_ref(editor, ref) for ref in refs]
    for handle in handles:
        del editor.state['handles'][handle['handle']]
    return handles
