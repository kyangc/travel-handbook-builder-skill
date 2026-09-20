"""Bounded structural blockers for changing one current Item place."""
import copy

from coverage_checks import coverage_projection


def _ref(kind, record):
    return {'type': kind, 'id': record['id']}


def _targets(record, item_ref):
    return item_ref in record.get('target_refs', [])


def item_place_change_blockers(package, item_ref, proposed_place_ref):
    """Return structured facts that require explicit handling before place change.

    The check follows direct references and the two documented Payment hops only.
    It does not inspect titles, notes, statements, or other free text.
    """
    item = next((value for value in package.get('items', [])
                 if {'type': 'item', 'id': value['id']} == item_ref), None)
    if item is None:
        raise ValueError('Item reference is not present in the package')
    if item.get('place_ref') == proposed_place_ref:
        return []

    blockers = []
    for reservation in package.get('reservations', []):
        if reservation['status'] == 'confirmed' and _targets(reservation, item_ref):
            blockers.append({'kind': 'reservation', 'ref': _ref('reservation', reservation)})

    if package.get('schema_version') in ('1.0',):
        projection = coverage_projection(package)
        effective = {(entry['coverage_ref']['id'], entry['scope_ref']['id'])
                     for entry in projection['effective_scopes']}
        for coverage in package.get('coverages', []):
            for scope in coverage['scopes']:
                if ((coverage['id'], scope['id']) in effective
                        and scope['target_ref'] == item_ref):
                    blockers.append({
                        'kind': 'coverage',
                        'ref': _ref('coverage', coverage),
                        'scope_ref': {'owner': _ref('coverage', coverage),
                                      'kind': 'scope', 'id': scope['id']},
                    })
    else:
        for coverage in package.get('coverages', []):
            if coverage['state'] != 'active':
                continue
            for scope in coverage['scopes']:
                if scope['target_ref'] == item_ref:
                    blockers.append({
                        'kind': 'coverage',
                        'ref': _ref('coverage', coverage),
                        'scope_ref': {'owner': _ref('coverage', coverage),
                                      'kind': 'scope', 'id': scope['id']},
                    })

    costs = {value['id']: value for value in package.get('costs', [])}
    reservations = {value['id']: value for value in package.get('reservations', [])}
    for cost in costs.values():
        if cost['status'] == 'active' and 'confirmed' in cost and _targets(cost, item_ref):
            blockers.append({'kind': 'cost', 'ref': _ref('cost', cost)})

    for payment in package.get('payments', []):
        if payment['status'] != 'settled':
            continue
        via = []
        for cost_ref in payment.get('cost_refs', []):
            cost = costs.get(cost_ref['id']) if cost_ref.get('type') == 'cost' else None
            if cost is not None and _targets(cost, item_ref):
                via.append(copy.deepcopy(cost_ref))
        reservation_ref = payment.get('reservation_ref')
        if reservation_ref is not None and reservation_ref.get('type') == 'reservation':
            reservation = reservations.get(reservation_ref['id'])
            if reservation is not None and _targets(reservation, item_ref):
                via.append(copy.deepcopy(reservation_ref))
        if via:
            blockers.append({'kind': 'payment', 'ref': _ref('payment', payment),
                             'via_refs': via})

    for task in package.get('tasks', []):
        if task['status'] == 'done' and _targets(task, item_ref):
            blockers.append({'kind': 'task', 'ref': _ref('task', task)})

    for claim in package.get('claims', []):
        target = claim['target']
        if (target.get('object_ref') == item_ref
                and target.get('field') == 'place_ref'
                and claim['basis'] in ('confirmation', 'observation')
                and claim.get('disposition', 'adopted') == 'adopted'):
            blockers.append({'kind': 'claim', 'ref': _ref('claim', claim)})
    return blockers
