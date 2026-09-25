"""R10 arrangement ownership and calendar edits over frozen model structures."""
import copy
from datetime import date as calendar_date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import fail, nonempty


EDIT_VERSIONS = {'1.0'}
CALENDAR_CLAIM_FIELDS = {
    'timing', 'movement', 'period', 'validity', 'date', 'service_date',
    'timezone', 'calls', 'departure', 'arrival', 'start', 'end', 'pickup', 'dropoff',
}


def require_edit_version(editor):
    if editor.package.get('schema_version') not in EDIT_VERSIONS:
        fail('SCHEMA_VERSION_UNSUPPORTED',
             'Arrangement and calendar edits require 1.0 or later',
             supported_version='1.0')


def _date_value(value, parameter):
    nonempty(value, parameter)
    try:
        calendar_date.fromisoformat(value)
    except ValueError:
        fail('INVALID_ARGUMENT', 'Use a valid ISO calendar date', parameter=parameter)
    return value


def _timezone_value(value, parameter):
    nonempty(value, parameter)
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError):
        fail('INVALID_ARGUMENT', 'Use a valid IANA timezone', parameter=parameter)
    return value


def _item_ownership(package, item_ref):
    owners = []
    for day in package.get('days', []):
        if item_ref in day.get('item_refs', []):
            owners.append(('day', day))
    if item_ref in package.get('trip', {}).get('unassigned_item_refs', []):
        owners.append(('unassigned', package['trip']))
    if len(owners) != 1:
        fail('STATE_FORMAT', 'Current Item must have exactly one Day or Trip ownership')
    return owners[0]


def _execution_refs(package, item, item_ref):
    refs = []

    def add(ref):
        value = copy.deepcopy(ref)
        if value not in refs:
            refs.append(value)

    def add_leg(leg_ref):
        add(leg_ref)
        leg = next((value for value in package.get('legs', [])
                    if value['id'] == leg_ref['id']), None)
        movement = leg.get('movement', {}) if leg is not None else {}
        service_ref = movement.get('service_ref')
        if not isinstance(service_ref, dict):
            return
        add(service_ref)
        service = next((value for value in package.get('transport_services', [])
                        if value['id'] == service_ref['id']), None)
        if service is not None:
            for call in service.get('calls', []):
                add({'owner': copy.deepcopy(service_ref), 'kind': 'call',
                     'id': call['id']})

    add(item_ref)
    subject = item.get('subject_ref')
    if not isinstance(subject, dict):
        return refs
    add(subject)
    if subject.get('type') == 'journey':
        journey = next((value for value in package.get('journeys', [])
                        if value['id'] == subject['id']), None)
        if journey is not None:
            for leg_ref in journey.get('leg_refs', []):
                add_leg(leg_ref)
    elif subject.get('type') == 'route':
        route = next((value for value in package.get('routes', [])
                      if value['id'] == subject['id']), None)
        if route is not None:
            for kind, collection in (('stop', 'stops'), ('segment', 'segments')):
                for value in route.get(collection, []):
                    add({'owner': copy.deepcopy(subject), 'kind': kind,
                         'id': value['id']})
            for value in route.get('segments', []):
                if 'leg_ref' in value:
                    add_leg(value['leg_ref'])
    elif subject.get('type') == 'stay':
        stay = next((value for value in package.get('stays', [])
                     if value['id'] == subject['id']), None)
        if stay is not None:
            for unit in stay.get('units', []):
                add({'owner': copy.deepcopy(subject), 'kind': 'unit',
                     'id': unit['id']})
    return refs


def _calendar_change_blockers(package, item, item_ref):
    from .item_times import item_time_change_blockers
    blockers = []
    for ref in _execution_refs(package, item, item_ref):
        for blocker in item_time_change_blockers(package, ref):
            value = {**copy.deepcopy(blocker), 'via_target_ref': copy.deepcopy(ref)}
            if value not in blockers:
                blockers.append(value)
        for claim in package.get('claims', []):
            target = claim.get('target', {})
            matches = (target.get('local_ref') == ref if 'owner' in ref
                       else target.get('object_ref') == ref
                       and 'local_ref' not in target)
            if (matches and target.get('field') in CALENDAR_CLAIM_FIELDS
                    and claim.get('basis') in {'confirmation', 'observation'}
                    and claim.get('disposition', 'adopted') == 'adopted'):
                value = {
                    'kind': 'claim',
                    'ref': {'type': 'claim', 'id': claim['id']},
                    'via_target_ref': copy.deepcopy(ref),
                }
                if value not in blockers:
                    blockers.append(value)
    return blockers


def _fail_calendar_change(item_ref, before, after, parameter, blockers):
    blocker_refs = []
    for value in blockers:
        if value['ref'] not in blocker_refs:
            blocker_refs.append(copy.deepcopy(value['ref']))
    fail('PLAN_TIME_CHANGE_BLOCKED',
         'Recorded execution facts must be handled before changing Day calendar meaning',
         parameter=parameter,
         changes=[{
             'target_ref': copy.deepcopy(item_ref),
             'boundary': 'day_calendar',
             'before': copy.deepcopy(before),
             'after': copy.deepcopy(after),
             'blockers': blockers,
             'blocker_refs': copy.deepcopy(blocker_refs),
         }],
         blocker_refs=blocker_refs)


def _protect_calendar_change(package, item, item_ref, before, after, parameter):
    if (before['date'], before['timezone']) == (after['date'], after['timezone']):
        return
    blockers = _calendar_change_blockers(package, item, item_ref)
    if blockers:
        _fail_calendar_change(item_ref, before, after, parameter, blockers)


def _protect_unassigned_assignment(package, item, item_ref, target_day, target_day_ref):
    from time_checks import item_day_ownership_assessment
    assessment = item_day_ownership_assessment(package, item_ref, target_day)
    if assessment['status'] != 'mismatch':
        return
    blockers = _calendar_change_blockers(package, item, item_ref)
    if blockers:
        _fail_calendar_change(
            item_ref,
            {'kind': 'unassigned', 'projected_date': assessment['projected_date'],
             'certainty': assessment['certainty']},
            {'day_ref': copy.deepcopy(target_day_ref), 'date': target_day['date'],
             'timezone': target_day['timezone']},
            'day', blockers)


def _protect_day_claim_changes(package, day_ref, before, after, changed_fields):
    changes = []
    blocker_refs = []
    for field in changed_fields:
        blockers = []
        for claim in package.get('claims', []):
            target = claim.get('target', {})
            if (target.get('object_ref') == day_ref and 'local_ref' not in target
                    and target.get('field') == field
                    and field in {'date', 'timezone'}
                    and claim.get('basis') in {'confirmation', 'observation'}
                    and claim.get('disposition', 'adopted') == 'adopted'):
                ref = {'type': 'claim', 'id': claim['id']}
                blockers.append({'kind': 'claim', 'ref': ref, 'field': field})
                if ref not in blocker_refs:
                    blocker_refs.append(copy.deepcopy(ref))
        if blockers:
            changes.append({
                'target_ref': copy.deepcopy(day_ref),
                'boundary': field,
                'before': {'value': before[field]},
                'after': {'value': after[field]},
                'blockers': blockers,
                'blocker_refs': [copy.deepcopy(value['ref']) for value in blockers],
            })
    if changes:
        fail('PLAN_TIME_CHANGE_BLOCKED',
             'An adopted execution Claim protects this Day calendar field',
             parameter=changes[0]['boundary'], changes=changes,
             blocker_refs=blocker_refs)


def _withdrawal_review_refs(package, item, item_ref):
    refs = _execution_refs(package, item, item_ref)
    result = []

    def add(kind, record):
        ref = {'type': kind, 'id': record['id']}
        if ref not in result:
            result.append(ref)

    related_reservations = []
    for record in package.get('reservations', []):
        if any(target in refs for target in record.get('target_refs', [])):
            add('reservation', record)
            related_reservations.append({'type': 'reservation', 'id': record['id']})

    current_coverage = None
    if package.get('schema_version') in EDIT_VERSIONS:
        from coverage_checks import coverage_projection
        current_coverage = set(coverage_projection(package)['current_coverage_ids'])
    for record in package.get('coverages', []):
        if (current_coverage is None or record['id'] in current_coverage) and any(
                scope.get('target_ref') in refs for scope in record.get('scopes', [])):
            add('coverage', record)

    related_costs = []
    for record in package.get('costs', []):
        if (record.get('status') == 'active'
                and any(target in refs for target in record.get('target_refs', []))):
            add('cost', record)
            related_costs.append({'type': 'cost', 'id': record['id']})

    for record in package.get('payments', []):
        if (any(ref in related_costs for ref in record.get('cost_refs', []))
                or record.get('reservation_ref') in related_reservations):
            add('payment', record)

    for record in package.get('tasks', []):
        if any(target in refs for target in record.get('target_refs', [])):
            add('task', record)

    claim_targets = refs + copy.deepcopy(result)
    for record in package.get('claims', []):
        target = record.get('target', {})
        if (target.get('object_ref') in claim_targets
                or target.get('local_ref') in refs):
            add('claim', record)
    return result


def plan_move(editor, *, target, day, before=None):
    require_edit_version(editor)
    item_ref = editor.ref(target, {'item'})
    item = editor.record(target, {'item'})
    if item.get('lifecycle', 'current') != 'current':
        fail('PLAN_MOVE_TARGET_RETIRED', 'Only a current Item can move',
             parameter='target')
    target_day_ref = editor.ref(day, {'day'})
    target_day = editor.record(day, {'day'})
    if item.get('kind') == 'stay_action':
        from .stays import validate_stay_action_day
        validate_stay_action_day(editor.package, item, target_day, parameter='day')
    source_kind, source = _item_ownership(editor.package, item_ref)

    before_ref = None
    if before is not None:
        before_ref = editor.ref(before, {'item'})
        anchor = editor.record(before, {'item'})
        if anchor.get('lifecycle', 'current') != 'current':
            fail('PLAN_MOVE_ANCHOR_INVALID', 'before must identify a current Item',
                 parameter='before', reference=before)
        if before_ref not in target_day['item_refs']:
            fail('PLAN_MOVE_ANCHOR_DAY_MISMATCH',
                 'before must identify a current Item in the target Day',
                 parameter='before', reference=before)
        if before_ref == item_ref:
            if source_kind == 'day' and source is target_day:
                return editor.handle(target)
            fail('PLAN_MOVE_ANCHOR_DAY_MISMATCH',
                 'An Item from another owner cannot use itself as the target Day anchor',
                 parameter='before', reference=before)

    previous = ({'kind': 'day', 'day_ref': {'type': 'day', 'id': source['id']}}
                if source_kind == 'day' else {'kind': 'unassigned'})
    if source_kind == 'day':
        _protect_calendar_change(
            editor.package, item, item_ref,
            {'day_ref': {'type': 'day', 'id': source['id']},
             'date': source['date'], 'timezone': source['timezone']},
            {'day_ref': copy.deepcopy(target_day_ref),
             'date': target_day['date'], 'timezone': target_day['timezone']},
            'day')
    else:
        _protect_unassigned_assignment(
            editor.package, item, item_ref, target_day, target_day_ref)
    if source_kind == 'day':
        source['item_refs'].remove(item_ref)
    else:
        editor.package['trip']['unassigned_item_refs'].remove(item_ref)
    if before_ref is None:
        target_day['item_refs'].append(item_ref)
    else:
        target_day['item_refs'].insert(target_day['item_refs'].index(before_ref), item_ref)
    editor.parts['ownership_change'] = {
        'from': previous,
        'to': {'kind': 'day', 'day_ref': copy.deepcopy(target_day_ref)},
        **({'before_ref': copy.deepcopy(before_ref)} if before_ref is not None else {}),
    }
    return editor.handle(target)


def plan_withdraw(editor, *, target, reason):
    require_edit_version(editor)
    nonempty(reason, 'reason')
    item_ref = editor.ref(target, {'item'})
    item = editor.record(target, {'item'})
    editor.parts['reason'] = reason
    editor.parts['review_refs'] = _withdrawal_review_refs(
        editor.package, item, item_ref)
    if item.get('lifecycle', 'current') == 'retired':
        return editor.handle(target)

    owner_kind, owner = _item_ownership(editor.package, item_ref)
    if owner_kind == 'day':
        owner['item_refs'].remove(item_ref)
    else:
        editor.package['trip']['unassigned_item_refs'].remove(item_ref)
    item['lifecycle'] = 'retired'
    retired_refs = [copy.deepcopy(item_ref)]
    subject_ref = item.get('subject_ref')
    if isinstance(subject_ref, dict) and subject_ref.get('type') in {'journey', 'route'}:
        subject = next((value for value in editor.package[
            'journeys' if subject_ref['type'] == 'journey' else 'routes']
                        if value['id'] == subject_ref['id']), None)
        if subject is None:
            fail('STATE_FORMAT', 'Arrangement execution owner is missing')
        subject['lifecycle'] = 'retired'
        retired_refs.append(copy.deepcopy(subject_ref))
    editor.parts['retired_refs'] = retired_refs
    return editor.handle(target)


def day_update(editor, *, target, date=None, timezone=None):
    require_edit_version(editor)
    if date is None and timezone is None:
        fail('INVALID_ARGUMENT', 'Provide date, timezone, or both')
    day_ref = editor.ref(target, {'day'})
    day = editor.record(target, {'day'})
    proposed = {
        'day_ref': copy.deepcopy(day_ref),
        'date': day['date'] if date is None else _date_value(date, 'date'),
        'timezone': (day['timezone'] if timezone is None
                     else _timezone_value(timezone, 'timezone')),
    }
    previous = {'day_ref': copy.deepcopy(day_ref), 'date': day['date'],
                'timezone': day['timezone']}
    changed = [name for name in ('date', 'timezone')
               if proposed[name] != previous[name]]
    if not changed:
        return editor.handle(target)
    _protect_day_claim_changes(
        editor.package, day_ref, previous, proposed, changed)
    items = {value['id']: value for value in editor.package.get('items', [])}
    for item_ref in day.get('item_refs', []):
        item = items.get(item_ref['id'])
        if item is None or item.get('lifecycle', 'current') != 'current':
            fail('STATE_FORMAT', 'Day owns a missing or retired Item')
        if item.get('kind') == 'stay_action':
            from .stays import validate_stay_action_day
            validate_stay_action_day(editor.package, item, proposed,
                                     parameter=changed[0])
        _protect_calendar_change(editor.package, item, item_ref, previous, proposed,
                                 changed[0])
    if date is not None:
        day['date'] = proposed['date']
    if timezone is not None:
        day['timezone'] = proposed['timezone']
    editor.parts['calendar_change'] = {
        'before': previous, 'after': proposed, 'changed_fields': changed}
    return editor.handle(target)


def trip_change_dates(editor, *, start_date=None, end_date=None):
    require_edit_version(editor)
    if start_date is None and end_date is None:
        fail('INVALID_ARGUMENT', 'Provide start_date, end_date, or both')
    trip = editor.package['trip']
    proposed_start = (trip['start_date'] if start_date is None
                      else _date_value(start_date, 'start_date'))
    proposed_end = (trip['end_date'] if end_date is None
                    else _date_value(end_date, 'end_date'))
    if proposed_start > proposed_end:
        fail('TRIP_DATE_ORDER', 'Trip start_date must not be later than end_date',
             parameter='start_date')
    previous = {'start_date': trip['start_date'], 'end_date': trip['end_date']}
    if start_date is not None:
        trip['start_date'] = proposed_start
    if end_date is not None:
        trip['end_date'] = proposed_end
    current = {'start_date': proposed_start, 'end_date': proposed_end}
    if current != previous:
        editor.parts['date_range_change'] = {'before': previous, 'after': current}
    trip_ref = {'type': 'trip', 'id': trip['id']}
    handle = next((value for value, ref in editor.state['handles'].items()
                   if ref == trip_ref), None)
    if handle is None:
        fail('STATE_FORMAT', 'Workspace trip handle is missing')
    return {'handle': handle}


def trip_update(editor, *, set=None, clear=None):
    """Edit the one public descriptive Trip field without widening calendar edits."""
    require_edit_version(editor)
    from .core import edit_fields
    changes = {} if set is None else copy.deepcopy(set)
    clear_fields = [] if clear is None else copy.deepcopy(clear)
    if isinstance(changes, dict) and 'summary' in changes:
        nonempty(changes['summary'], 'set.summary')
    edit_fields(editor.package['trip'], changes=changes, clear=clear_fields,
                append_note=None, allowed={'summary'}, clearable={'summary'})
    trip_ref = {'type': 'trip', 'id': editor.package['trip']['id']}
    handle = next((value for value, ref in editor.state['handles'].items()
                   if ref == trip_ref), None)
    if handle is None:
        fail('STATE_FORMAT', 'Workspace trip handle is missing')
    return {'handle': handle}
