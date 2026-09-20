"""Bounded timing blockers and whole-batch projection comparison for existing."""
import copy

from coverage_checks import coverage_projection
from time_checks import BoundaryResolver
from .errors import fail


def _ref(kind, record):
    return {'type': kind, 'id': record['id']}


def _targets(record, target_ref):
    return target_ref in record.get('target_refs', [])


def item_time_change_blockers(package, item_ref):
    """Return structured records protecting one Item/Activity timing projection."""
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

    costs = {record['id']: record for record in package.get('costs', [])}
    reservations = {record['id']: record for record in package.get('reservations', [])}
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
        if ((target.get('object_ref') == item_ref or target.get('local_ref') == item_ref)
                and target.get('field') in {'timing', 'movement'}
                and claim['basis'] in {'confirmation', 'observation'}
                and claim.get('disposition', 'adopted') == 'adopted'):
            blockers.append({'kind': 'claim', 'ref': _ref('claim', claim)})
    return blockers


def item_time_review_refs(package, item_ref):
    """List directly related records without inferring that their facts changed."""
    result = []
    for collection, kind in (('reservations', 'reservation'), ('tasks', 'task')):
        for record in package.get(collection, []):
            if _targets(record, item_ref):
                result.append({'kind': kind, 'ref': _ref(kind, record)})
    for coverage in package.get('coverages', []):
        if any(scope.get('target_ref') == item_ref for scope in coverage.get('scopes', [])):
            result.append({'kind': 'coverage', 'ref': _ref('coverage', coverage)})
    return result


def _time_sources(package):
    sources = {}
    for collection, kind in (('items', 'item'), ('activities', 'activity')):
        for record in package.get(collection, []):
            sources[kind, record['id']] = record.get('timing')
    for record in package.get('legs', []):
        sources['leg', record['id']] = record.get('movement')
    for record in package.get('routes', []):
        sources['route', record['id']] = {
            'stops': record.get('stops'), 'segments': record.get('segments')}
    for record in package.get('journeys', []):
        sources['journey', record['id']] = {'leg_refs': record.get('leg_refs')}
    for record in package.get('transport_services', []):
        sources['transport_service', record['id']] = {'calls': record.get('calls')}
    return sources


def _boundary_fact(timing, field):
    if field not in timing:
        return None
    value = timing[field]
    if timing.get('kind') == 'boundaries':
        if isinstance(value, dict) and value.get('kind') == 'unknown':
            return None
        if isinstance(value, dict) and value.get('kind') == 'estimated':
            return ('estimated', value.get('value'))
        return ('exact', value)
    if timing.get('kind') == 'fixed':
        return ('exact', value)
    if timing.get('kind') == 'estimated':
        return ('estimated', value)
    return None


def _contains_all(old_values, new_values):
    remaining = list(new_values)
    for value in old_values:
        if value not in remaining:
            return False
        remaining.remove(value)
    return True


def _changes_existing_timing_fact(previous, current):
    """Allow additions into unknown/missing slots while preserving prior facts."""
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return previous != current
    for field in ('start', 'end'):
        old = _boundary_fact(previous, field)
        if old is not None and _boundary_fact(current, field) != old:
            return True
    for field in ('end_from_ref', 'duration', 'duration_from_ref',
                  'start_not_before', 'start_not_after', 'from_ref'):
        if field in previous and current.get(field) != previous[field]:
            return True
    if not _contains_all(previous.get('constraints', []), current.get('constraints', [])):
        return True
    return False


def _projection_value(value):
    return (value['instant'].isoformat() if value['instant'] is not None else None,
            value['certainty'])


def _dependency_path(node, changed_nodes, edges):
    reverse = {}
    for target, dependents in edges.items():
        for dependent in dependents:
            reverse.setdefault(dependent, set()).add(target)

    def visit(current, active):
        if current in changed_nodes:
            return [current]
        if current in active:
            return None
        for target in sorted(reverse.get(current, set())):
            found = visit(target, active | {current})
            if found is not None:
                return found + [current]
        return None

    return visit(node, set()) or [node]


def _changed_source_nodes(owner, previous, current):
    kind, identifier = owner
    nodes = set()
    if kind in {'item', 'activity'}:
        if _boundary_fact(previous or {}, 'start') != _boundary_fact(current or {}, 'start'):
            nodes.add((kind, identifier, 'start'))
        end_fields = ('end_from_ref', 'duration', 'duration_from_ref', 'from_ref')
        if (_boundary_fact(previous or {}, 'end') != _boundary_fact(current or {}, 'end')
                or any((previous or {}).get(field) != (current or {}).get(field)
                       for field in end_fields)):
            nodes.add((kind, identifier, 'end'))
        return nodes
    if kind == 'route':
        return {(kind, identifier, 'start'), (kind, identifier, 'end'),
                (kind, identifier, 'duration')}
    if kind == 'journey':
        return {(kind, identifier, 'start'), (kind, identifier, 'end'),
                (kind, identifier, 'duration')}
    if kind in {'leg', 'transport_service'}:
        return {(kind, identifier, 'start'), (kind, identifier, 'end')}
    return nodes


def _movement_changes_existing_fact(previous, current):
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return previous != current
    if previous.get('kind') != current.get('kind'):
        return True
    if previous.get('kind') == 'independent':
        if (previous.get('from_ref'), previous.get('to_ref')) != (
                current.get('from_ref'), current.get('to_ref')):
            return True
        return _changes_existing_timing_fact(previous.get('timing', {}), current.get('timing', {}))
    return previous != current


def _leg_owner_path(package, leg_ref):
    owner_ref = None
    for journey in package.get('journeys', []):
        if leg_ref in journey.get('leg_refs', []):
            owner_ref = _ref('journey', journey)
            break
    if owner_ref is None:
        for route in package.get('routes', []):
            segment = next((segment for segment in route.get('segments', [])
                            if segment.get('leg_ref') == leg_ref), None)
            if segment is not None:
                owner_ref = _ref('route', route)
                segment_ref = {'owner': copy.deepcopy(owner_ref), 'kind': 'segment',
                               'id': segment['id']}
                break
    result = [leg_ref]
    if owner_ref is None:
        return result
    if owner_ref['type'] == 'route':
        result.append(segment_ref)
    result.append(owner_ref)
    item = next((value for value in package.get('items', [])
                 if value.get('subject_ref') == owner_ref), None)
    if item is not None:
        result.append(_ref('item', item))
    return result


def protect_leg_movement_fact_change(editor, leg_ref, before, after, parameter):
    """Apply the existing bounded movement blockers to a non-time Leg fact."""
    changes = []
    blocker_refs = []
    path = _leg_owner_path(editor.package, leg_ref)
    for offset, target_ref in enumerate(path):
        blockers = item_time_change_blockers(editor.package, target_ref)
        if not blockers:
            continue
        refs = [copy.deepcopy(value['ref']) for value in blockers]
        blocker_refs.extend(ref for ref in refs if ref not in blocker_refs)
        changes.append({
            'target_ref': copy.deepcopy(target_ref),
            'boundary': 'movement',
            'before': {'expression': {'vehicle_ref': copy.deepcopy(before)}},
            'after': {'expression': {'vehicle_ref': copy.deepcopy(after)}},
            'dependency_path': [
                {**({'type': ref['type']} if 'type' in ref else {
                    'kind': ref['kind'], 'owner': copy.deepcopy(ref['owner'])}),
                 'id': ref['id'], 'field': 'movement' if index == 0 else 'owner'}
                for index, ref in enumerate(path[:offset + 1])
            ],
            'blockers': copy.deepcopy(blockers),
            'blocker_refs': refs,
        })
    if changes:
        fail('PLAN_TIME_CHANGE_BLOCKED',
             'Protected execution facts block this Leg movement change',
             parameter=parameter, changes=changes, blocker_refs=blocker_refs)


def leg_time_review_entries(package, leg_ref):
    """Return direct bounded review records along one Leg ownership chain."""
    result = []
    for target_ref in _leg_owner_path(package, leg_ref):
        for entry in item_time_review_refs(package, target_ref):
            value = {'target_ref': copy.deepcopy(target_ref), **copy.deepcopy(entry)}
            if value not in result:
                result.append(value)
    return result


def protected_time_projection_changes(before, after):
    """Compare one atomic batch and return direct or dependency-projected blockers."""
    if (before is None or after is None
            or after.get('schema_version') not in ('1.0',)):
        return []
    old = BoundaryResolver(before)
    new = BoundaryResolver(after)
    old_projection = old.project_all()
    new_projection = new.project_all()
    old_sources = _time_sources(before)
    new_sources = _time_sources(after)
    changed_owners = {owner for owner, value in old_sources.items()
                      if owner in new_sources and new_sources[owner] != value}
    changed_nodes = set()
    for owner in changed_owners:
        changed_nodes.update(_changed_source_nodes(
            owner, old_sources[owner], new_sources[owner]))
    edges = {}
    for source in (old.edges, new.edges):
        for target, dependents in source.items():
            edges.setdefault(target, set()).update(dependents)

    changes = []
    directly_blocked = set()
    for owner in sorted(changed_owners):
        if owner[0] != 'leg' or not _movement_changes_existing_fact(
                old_sources[owner], new_sources[owner]):
            continue
        leg_ref = {'type': 'leg', 'id': owner[1]}
        path = _leg_owner_path(before, leg_ref)
        for offset, target_ref in enumerate(path):
            blockers = item_time_change_blockers(before, target_ref)
            if not blockers:
                continue
            if 'type' in target_ref:
                directly_blocked.add((target_ref['type'], target_ref['id']))
            changes.append({
                'target_ref': copy.deepcopy(target_ref),
                'boundary': 'movement',
                'before': {'expression': copy.deepcopy(old_sources[owner])},
                'after': {'expression': copy.deepcopy(new_sources[owner])},
                'dependency_path': [
                    {**({'type': ref['type']} if 'type' in ref else {
                        'kind': ref['kind'], 'owner': copy.deepcopy(ref['owner'])}),
                     'id': ref['id'], 'field': 'movement' if index == 0 else 'owner'}
                    for index, ref in enumerate(path[:offset + 1])
                ],
                'blockers': blockers,
                'blocker_refs': [copy.deepcopy(value['ref']) for value in blockers],
            })
    for owner in sorted(changed_owners):
        if owner[0] not in {'item', 'activity'}:
            continue
        previous_timing = old_sources[owner]
        if not _changes_existing_timing_fact(previous_timing, new_sources[owner]):
            continue
        target_ref = {'type': owner[0], 'id': owner[1]}
        blockers = item_time_change_blockers(before, target_ref)
        if blockers:
            directly_blocked.add(owner)
            changes.append({
                'target_ref': target_ref,
                'boundary': 'timing',
                'before': {'expression': copy.deepcopy(previous_timing)},
                'after': {'expression': copy.deepcopy(new_sources[owner])},
                'dependency_path': [{'type': owner[0], 'id': owner[1], 'field': 'timing'}],
                'blockers': blockers,
                'blocker_refs': [copy.deepcopy(value['ref']) for value in blockers],
            })
    for node, previous in old_projection.items():
        if node[0] not in {'item', 'activity'} or previous['instant'] is None:
            continue
        current = new_projection.get(node, _unknown_projection())
        if node[:2] in directly_blocked:
            continue
        if _projection_value(previous) == _projection_value(current):
            continue
        # Supplementing an unknown projection is allowed; this branch starts known by construction.
        path = _dependency_path(node, changed_nodes, edges)
        item_ref = {'type': node[0], 'id': node[1]}
        blockers = item_time_change_blockers(before, item_ref)
        if blockers:
            changes.append({
                'target_ref': item_ref,
                'boundary': node[2],
                'before': {'instant': previous['instant'].isoformat(),
                           'certainty': previous['certainty']},
                'after': {'instant': (current['instant'].isoformat()
                                      if current['instant'] is not None else None),
                          'certainty': current['certainty']},
                'dependency_path': [
                    {'type': kind, 'id': identifier, 'field': field}
                    for kind, identifier, field in path
                ],
                'blockers': blockers,
                'blocker_refs': [copy.deepcopy(value['ref']) for value in blockers],
            })
    return changes


def _unknown_projection():
    return {'instant': None, 'certainty': 'unknown'}
