"""Bounded participant participant projection and execution-fact protection."""
import copy

from coverage_checks import coverage_projection


def _ref(kind, record):
    return {'type': kind, 'id': record['id']}


def _party(package):
    return package.get('trip', {}).get('party', {})


def _roster_population(package):
    party = _party(package)
    identifiers = frozenset(member['id'] for member in party.get('members', []))
    if party.get('members_status') == 'complete' and identifiers:
        return ('members', identifiers)
    # Missing and incomplete are both unresolved. Count and the identities that
    # are already distinguished still matter; wording alone does not.
    return ('unresolved', party.get('count'), identifiers, False)


def _participant_population(package, value, *, missing_inherits_all):
    if value is None:
        return _roster_population(package) if missing_inherits_all else ('unknown',)
    if not isinstance(value, dict):
        return ('invalid',)
    if value.get('kind') == 'all':
        return _roster_population(package)
    if value.get('kind') == 'unknown':
        return ('unknown',)
    if value.get('kind') == 'count':
        return ('count', value.get('count'))
    if 'member_ids' in value:
        return ('members', frozenset(value['member_ids']))
    if 'group_ids' in value:
        groups = {group['id']: group for group in _party(package).get('groups', [])}
        members = set()
        for identifier in value['group_ids']:
            group = groups.get(identifier)
            if group is None:
                return ('unresolved_group', frozenset(value['group_ids']))
            members.update(group['member_ids'])
        return ('members', frozenset(members))
    return ('invalid',)


def _population_summary(value):
    if value[0] == 'members':
        return {'kind': 'members', 'member_ids': sorted(value[1])}
    if value[0] == 'unresolved':
        result = {'kind': 'all_unresolved', 'member_ids': sorted(value[2]),
                  'members_complete': False}
        if value[1] is not None:
            result['count'] = value[1]
        return result
    if value[0] == 'count':
        return {'kind': 'count', 'count': value[1]}
    if value[0] == 'unresolved_group':
        return {'kind': 'groups_unresolved', 'group_ids': sorted(value[1])}
    return {'kind': value[0]}


def _owned_item_refs(package, item):
    item_ref = _ref('item', item)
    refs = [item_ref]
    subject = item.get('subject_ref')
    if not isinstance(subject, dict) or subject.get('type') not in {'journey', 'route'}:
        return refs
    refs.append(copy.deepcopy(subject))
    if subject['type'] == 'journey':
        owner = next((record for record in package.get('journeys', [])
                      if record['id'] == subject['id']), None)
        if owner is not None:
            refs.extend(copy.deepcopy(owner.get('leg_refs', [])))
        return refs
    owner = next((record for record in package.get('routes', [])
                  if record['id'] == subject['id']), None)
    if owner is None:
        return refs
    for kind, collection in (('stop', 'stops'), ('segment', 'segments')):
        refs.extend({'owner': copy.deepcopy(subject), 'kind': kind, 'id': record['id']}
                    for record in owner.get(collection, []))
    refs.extend(copy.deepcopy(segment['leg_ref']) for segment in owner.get('segments', [])
                if 'leg_ref' in segment)
    return refs


def _targets_any(record, refs):
    return any(target in refs for target in record.get('target_refs', []))


def _matching_targets(record, refs):
    return [copy.deepcopy(target) for target in record.get('target_refs', [])
            if target in refs]


def _participant_claim_matches(claim, target_ref, field):
    target = claim.get('target', {})
    if target.get('field') != field:
        return False
    if 'owner' in target_ref:
        return (target.get('object_ref') == target_ref['owner']
                and target.get('local_ref') == target_ref)
    return target.get('object_ref') == target_ref and 'local_ref' not in target


def participant_change_blockers(package, refs, target_ref, field, *, coverage_refs=None,
                                claim_refs=None):
    """Return only direct or documented owned-chain participant facts."""
    blockers = []
    for reservation in package.get('reservations', []):
        if reservation['status'] == 'confirmed' and _targets_any(reservation, refs):
            blockers.append({'kind': 'reservation', 'ref': _ref('reservation', reservation),
                             'via_target_refs': _matching_targets(reservation, refs)})

    coverage_refs = refs if coverage_refs is None else coverage_refs
    projection = coverage_projection(package)
    effective = {(entry['coverage_ref']['id'], entry['scope_ref']['id'])
                 for entry in projection['effective_scopes']}
    for coverage in package.get('coverages', []):
        for scope in coverage['scopes']:
            if ((coverage['id'], scope['id']) in effective
                    and scope['target_ref'] in coverage_refs):
                blockers.append({
                    'kind': 'coverage', 'ref': _ref('coverage', coverage),
                    'scope_ref': {'owner': _ref('coverage', coverage),
                                  'kind': 'scope', 'id': scope['id']},
                    'via_target_refs': [copy.deepcopy(scope['target_ref'])],
                })

    costs = {record['id']: record for record in package.get('costs', [])}
    reservations = {record['id']: record for record in package.get('reservations', [])}
    for cost in costs.values():
        if cost['status'] == 'active' and 'confirmed' in cost and _targets_any(cost, refs):
            blockers.append({'kind': 'cost', 'ref': _ref('cost', cost),
                             'via_target_refs': _matching_targets(cost, refs)})
    for payment in package.get('payments', []):
        if payment['status'] != 'settled':
            continue
        via = []
        for cost_ref in payment.get('cost_refs', []):
            cost = costs.get(cost_ref.get('id')) if cost_ref.get('type') == 'cost' else None
            if cost is not None and _targets_any(cost, refs):
                via.append(copy.deepcopy(cost_ref))
        reservation_ref = payment.get('reservation_ref')
        reservation = (reservations.get(reservation_ref.get('id'))
                       if isinstance(reservation_ref, dict)
                       and reservation_ref.get('type') == 'reservation' else None)
        if reservation is not None and _targets_any(reservation, refs):
            via.append(copy.deepcopy(reservation_ref))
        if via:
            blockers.append({'kind': 'payment', 'ref': _ref('payment', payment),
                             'via_refs': via,
                             'via_target_refs': [
                                 target for via_ref in via
                                 for target in _matching_targets(
                                     costs.get(via_ref['id'], {}) if via_ref.get('type') == 'cost'
                                     else reservations.get(via_ref['id'], {}), refs)]})

    for task in package.get('tasks', []):
        if task['status'] == 'done' and _targets_any(task, refs):
            blockers.append({'kind': 'task', 'ref': _ref('task', task),
                             'via_target_refs': _matching_targets(task, refs)})
    claim_refs = refs if claim_refs is None else claim_refs
    for claim in package.get('claims', []):
        if (claim['basis'] in {'confirmation', 'observation'}
                and claim.get('disposition', 'adopted') == 'adopted'
                and any(_participant_claim_matches(claim, ref, field)
                        for ref in claim_refs)):
            blockers.append({'kind': 'claim', 'ref': _ref('claim', claim)})
    return blockers


def participant_review_refs(package, target_ref, field):
    if target_ref.get('type') == 'item':
        item = next((record for record in package.get('items', [])
                     if record['id'] == target_ref['id']), None)
        refs = _owned_item_refs(package, item) if item is not None else [target_ref]
        coverage_refs = refs
        claim_refs = refs
    elif target_ref.get('kind') == 'unit' and target_ref.get('owner', {}).get('type') == 'stay':
        refs = [target_ref, target_ref['owner']]
        coverage_refs = [target_ref]
        claim_refs = [target_ref]
    else:
        refs = [target_ref]
        coverage_refs = refs
        claim_refs = refs
    blockers = participant_change_blockers(
        package, refs, target_ref, field, coverage_refs=coverage_refs,
        claim_refs=claim_refs)
    result = []
    for blocker in blockers:
        for ref in (blocker['ref'], blocker.get('scope_ref')):
            if ref is not None and ref not in result:
                result.append(copy.deepcopy(ref))
    return result


def _records_by_id(package, collection):
    return {record['id']: record for record in package.get(collection, [])}


def protected_plan_participant_changes(before, after):
    """Compare the atomic before/after participant populations."""
    if (not before
            or after.get('schema_version') not in ('1.0',)):
        return []
    changes = []
    after_items = _records_by_id(after, 'items')
    for old in before.get('items', []):
        if old.get('lifecycle', 'current') != 'current':
            continue
        new = after_items.get(old['id'])
        if new is None or new.get('lifecycle', 'current') != 'current':
            continue
        previous = _participant_population(before, old.get('participants'),
                                           missing_inherits_all=True)
        proposed = _participant_population(after, new.get('participants'),
                                           missing_inherits_all=True)
        if previous == proposed:
            continue
        if previous == ('unknown',):
            continue
        target_ref = _ref('item', old)
        refs = _owned_item_refs(before, old)
        blockers = participant_change_blockers(before, refs, target_ref, 'participants')
        if blockers:
            changes.append({
                'target_ref': target_ref, 'field': 'participants',
                'previous_population': _population_summary(previous),
                'proposed_population': _population_summary(proposed),
                'blockers': blockers,
                'blocker_refs': [copy.deepcopy(entry['ref']) for entry in blockers],
            })

    after_stays = _records_by_id(after, 'stays')
    for old in before.get('stays', []):
        new = after_stays.get(old['id'])
        if new is None:
            continue
        previous = _participant_population(before, old.get('participants'),
                                           missing_inherits_all=True)
        proposed = _participant_population(after, new.get('participants'),
                                           missing_inherits_all=True)
        target_ref = _ref('stay', old)
        if previous != proposed and previous != ('unknown',):
            blockers = participant_change_blockers(before, [target_ref], target_ref,
                                                   'participants')
            if blockers:
                changes.append({
                    'target_ref': target_ref, 'field': 'participants',
                    'previous_population': _population_summary(previous),
                    'proposed_population': _population_summary(proposed),
                    'blockers': blockers,
                    'blocker_refs': [copy.deepcopy(entry['ref']) for entry in blockers],
                })
        new_units = {unit['id']: unit for unit in new.get('units', [])}
        owner_ref = target_ref
        for unit in old.get('units', []):
            new_unit = new_units.get(unit['id'])
            if new_unit is None:
                continue
            previous = _participant_population(before, unit.get('occupants'),
                                               missing_inherits_all=False)
            proposed = _participant_population(after, new_unit.get('occupants'),
                                               missing_inherits_all=False)
            if previous == proposed:
                continue
            if previous == ('unknown',):
                continue
            unit_ref = {'owner': owner_ref, 'kind': 'unit', 'id': unit['id']}
            blockers = participant_change_blockers(
                before, [unit_ref, owner_ref], unit_ref, 'occupants',
                coverage_refs=[unit_ref], claim_refs=[unit_ref])
            if blockers:
                changes.append({
                    'target_ref': unit_ref, 'field': 'occupants',
                    'previous_population': _population_summary(previous),
                    'proposed_population': _population_summary(proposed),
                    'blockers': blockers,
                    'blocker_refs': [copy.deepcopy(entry['ref']) for entry in blockers],
                })
    return changes


def _dynamic_task_paths(task, index):
    paths = []
    if task.get('status') == 'done':
        for field in ('assignees', 'beneficiaries'):
            if task.get(field) == {'kind': 'all'}:
                paths.append(f'/tasks/{index}/{field}')
        if task.get('completion', {}).get('completed_by') == {'kind': 'all'}:
            paths.append(f'/tasks/{index}/completion/completed_by')
    for hindex, history in enumerate(task.get('completion_history', [])):
        snapshot = history.get('task_snapshot', {})
        for field in ('assignees', 'beneficiaries'):
            if snapshot.get(field) == {'kind': 'all'}:
                paths.append(
                    f'/tasks/{index}/completion_history/{hindex}/task_snapshot/{field}')
        if history.get('completion', {}).get('completed_by') == {'kind': 'all'}:
            paths.append(
                f'/tasks/{index}/completion_history/{hindex}/completion/completed_by')
    return paths


def protected_party_history_changes(before, after):
    if (not before or after.get('schema_version') not in ('1.0',)
            or _roster_population(before) == _roster_population(after)):
        return []
    changes = []
    for index, task in enumerate(after.get('tasks', [])):
        paths = _dynamic_task_paths(task, index)
        if paths:
            changes.append({'task_ref': _ref('task', task), 'field_paths': paths})
    return changes
