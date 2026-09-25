"""Planned accommodation, independent from supplier confirmation and billing."""
import copy
from .errors import fail, nonempty


def period_input(value, use_kind=None):
    value = {'kind': 'unknown'} if value is None else copy.deepcopy(value)
    if not isinstance(value, dict) or value.get('kind') not in ('unknown', 'local_dates'):
        fail('UNSUPPORTED_VARIANT', 'This slice accepts unknown or local_dates periods only', parameter='period')
    if use_kind == 'day_use' and value.get('kind') != 'unknown':
        fail('UNSUPPORTED_VARIANT', 'Known day-use clock intervals need a later fixed-period entry point', parameter='period')
    return value


def unit_fields(editor, value):
    allowed = {'kind', 'count', 'period', 'description', 'occupants', 'notes'}
    if not isinstance(value, dict) or not {'kind', 'count'} <= value.keys() or value.keys() - allowed:
        fail('INVALID_ARGUMENT', 'Unit requires kind/count and optional period/description/occupants/notes')
    if any(v is None for v in value.values()):
        fail('INVALID_ARGUMENT', 'Omit unknown unit fields; null is not an unknown period')
    record = copy.deepcopy(value)
    record['period'] = period_input(value.get('period'))
    if 'occupants' in record:
        from .party import normalize_participants
        record['occupants'] = normalize_participants(editor, record['occupants'],
                                                       'units.occupants')
    return record


def add_unit(editor, stay, owner_ref, key, value):
    nonempty(key, 'units.key')
    handles = editor.parts.setdefault('units', {})
    if key in handles:
        fail('DUPLICATE_ALIAS', 'Unit keys must be unique within an operation')
    unit = {'id': editor.allocate_id(), **unit_fields(editor, value)}
    period_input(unit['period'], stay['use_kind'])
    stay.setdefault('units', []).append(unit)
    handles[key] = editor.register_local(owner_ref, 'unit', unit)


def stay_plan(editor, *, lodging, use_kind, period=None, units=None, participants=None,
              requests=None, night_count=None, notes=None):
    from .party import normalize_participants
    fields = {'lodging_ref': editor.ref(lodging, {'place'}), 'use_kind': use_kind,
              'period': period_input(period, use_kind),
              'participants': ({'kind': 'unknown'} if participants is None
                               else normalize_participants(editor, participants))}
    for key, value in (('requests', requests), ('night_count', night_count), ('notes', notes)):
        if value is not None:
            fields[key] = value
    result = editor.add('stay', fields)
    stay = editor.record(result, {'stay'})
    if units is not None:
        if not isinstance(units, list):
            fail('INVALID_ARGUMENT', 'units must be a list')
        for entry in units:
            if not isinstance(entry, dict) or 'key' not in entry:
                fail('INVALID_ARGUMENT', 'Each unit needs a local key')
            add_unit(editor, stay, editor.ref(result), entry['key'], {k: v for k, v in entry.items() if k != 'key'})
    return result


def _stay_action_day_check(stay, action, day, *, parameter='day'):
    """Reject explicit local-date contradictions; unknown periods remain unknown."""
    period = stay.get('period', {})
    if period.get('kind') != 'local_dates':
        return
    if day['timezone'] != period['timezone']:
        fail('STAY_ACTION_DAY_CONFLICT',
             'Stay action Day timezone conflicts with the Stay local-date period',
             parameter=parameter, action=action, day_date=day['date'],
             day_timezone=day['timezone'], stay_period=copy.deepcopy(period))
    expected = {'check_in': period['check_in'], 'check_out': period['check_out']}.get(action)
    valid = (day['date'] == expected if expected is not None
             else period['check_in'] <= day['date'] <= period['check_out'])
    if not valid:
        fail('STAY_ACTION_DAY_CONFLICT',
             'Stay action Day date conflicts with the Stay local-date period',
             parameter=parameter, action=action, day_date=day['date'],
             expected_date=expected, stay_period=copy.deepcopy(period))


def validate_stay_action_day(package, item, day, *, parameter='day'):
    if item.get('kind') != 'stay_action':
        return
    stay_ref = item.get('subject_ref')
    if not isinstance(stay_ref, dict) or stay_ref.get('type') != 'stay':
        fail('STATE_FORMAT', 'stay_action Item must reference a Stay')
    stay = next((value for value in package.get('stays', [])
                 if value['id'] == stay_ref['id']), None)
    if stay is None:
        fail('STATE_FORMAT', 'stay_action Item references a missing Stay')
    _stay_action_day_check(stay, item['action'], day, parameter=parameter)


def _validate_actions_for_stay(package, stay):
    stay_ref = {'type': 'stay', 'id': stay['id']}
    items = [item for item in package.get('items', [])
             if item.get('lifecycle', 'current') == 'current'
             and item.get('kind') == 'stay_action'
             and item.get('subject_ref') == stay_ref]
    for item in items:
        item_ref = {'type': 'item', 'id': item['id']}
        owner = _current_item_owner(package, item_ref)
        if owner is not None:
            _stay_action_day_check(stay, item['action'], owner, parameter='set.period')


def _stay_action_fields(editor, stay_handle, action, title, timing, participants,
                        purpose, notes):
    from .party import normalize_participants
    from .time_plans import normalize_time_plan
    nonempty(action, 'action')
    nonempty(title, 'title')
    stay_ref = editor.ref(stay_handle, {'stay'})
    stay = editor.record(stay_handle, {'stay'})
    fields = {
        'kind': 'stay_action',
        'title': title,
        'subject_ref': stay_ref,
        'action': action,
        'timing': ({'kind': 'unknown'} if timing is None
                   else normalize_time_plan(editor, timing)),
        'participants': ({'kind': 'unknown'} if participants is None
                         else normalize_participants(editor, participants)),
    }
    lodging_ref = stay['lodging_ref']
    if lodging_ref.get('type') == 'place':
        fields['place_ref'] = copy.deepcopy(lodging_ref)
    if purpose is not None:
        nonempty(purpose, 'purpose')
        fields['purpose'] = purpose
    if notes is not None:
        nonempty(notes, 'notes')
        fields['notes'] = notes
    return stay, fields


def stay_action_add(editor, *, stay, action, title, day=None, timing=None,
                    participants=None, purpose=None, notes=None, before=None):
    stay_record, fields = _stay_action_fields(
        editor, stay, action, title, timing, participants, purpose, notes)
    owner = None
    if day is None:
        if before is not None:
            fail('INVALID_ARGUMENT', 'before requires an explicit target Day',
                 parameter='before')
    else:
        owner = editor.record(day, {'day'})
        _stay_action_day_check(stay_record, action, owner)
    before_ref = None
    if before is not None:
        before_ref = editor.ref(before, {'item'})
        anchor = editor.record(before, {'item'})
        if anchor.get('lifecycle', 'current') != 'current':
            fail('PLAN_INSERT_ANCHOR_INVALID', 'before must identify a current Item',
                 parameter='before', reference=before)
        if before_ref not in owner['item_refs']:
            fail('PLAN_INSERT_ANCHOR_DAY_MISMATCH',
                 'before must identify a current Item in the target Day',
                 parameter='before', reference=before)
    result = editor.add('item', fields)
    result_ref = editor.ref(result)
    if owner is None:
        editor.package['trip'].setdefault('unassigned_item_refs', []).append(result_ref)
    elif before_ref is None:
        owner['item_refs'].append(result_ref)
    else:
        owner['item_refs'].insert(owner['item_refs'].index(before_ref), result_ref)
    return result


def _current_item_owner(package, item_ref):
    owners = [day for day in package.get('days', [])
              if item_ref in day.get('item_refs', [])]
    unassigned = item_ref in package.get('trip', {}).get('unassigned_item_refs', [])
    if len(owners) + int(unassigned) != 1:
        fail('STATE_FORMAT', 'Current Item must have exactly one Day or Trip ownership')
    return None if unassigned else owners[0]


def _stay_action_binding_claim_blockers(package, item_ref, changed_fields):
    blockers = []
    for claim in package.get('claims', []):
        target = claim.get('target', {})
        if (target.get('object_ref') == item_ref
                and 'local_ref' not in target
                and target.get('field') in changed_fields
                and claim.get('basis') in {'confirmation', 'observation'}
                and claim.get('disposition', 'adopted') == 'adopted'):
            blockers.append({'kind': 'claim',
                             'ref': {'type': 'claim', 'id': claim['id']},
                             'field': target['field']})
    return blockers


def stay_action_bind(editor, *, target, stay, action):
    nonempty(action, 'action')
    item_ref = editor.ref(target, {'item'})
    item = editor.record(target, {'item'})
    stay_ref = editor.ref(stay, {'stay'})
    stay_record = editor.record(stay, {'stay'})
    if item.get('lifecycle', 'current') != 'current':
        fail('STAY_ACTION_TARGET_RETIRED', 'Only a current Item can be bound',
             parameter='target')
    lodging_ref = stay_record['lodging_ref']
    desired_place = lodging_ref if lodging_ref.get('type') == 'place' else None
    if item['kind'] == 'stay_action':
        current_place = item.get('place_ref')
        if (item.get('subject_ref') != stay_ref or item.get('action') != action
                or (current_place is not None and current_place != desired_place)):
            fail('STAY_ACTION_REPLACEMENT_REQUIRED',
                 'Changing an existing Stay action needs a controlled replacement method',
                 parameter='target')
        owner = _current_item_owner(editor.package, item_ref)
        if owner is not None:
            _stay_action_day_check(stay_record, action, owner, parameter='target')
        editor.parts['_skip_origin_claim'] = True
        return editor.handle(target)
    if item['kind'] not in {'meal', 'visit', 'shopping', 'rest', 'errand', 'other'}:
        fail('UNSUPPORTED_VARIANT', 'Only a current ordinary Item can be bound to a Stay',
             parameter='target')
    if 'subject_ref' in item and item['subject_ref'] != stay_ref:
        fail('STAY_ACTION_BIND_CONFLICT',
             'Item already refers to a different subject', parameter='target')
    if 'action' in item and item['action'] != action:
        fail('STAY_ACTION_BIND_CONFLICT',
             'Item already records a different action', parameter='action')
    current_place = item.get('place_ref')
    if desired_place is None:
        if current_place is not None:
            fail('STAY_ACTION_PLACE_CONFLICT',
                 'A mobile lodging Stay cannot adopt an existing fixed Item place',
                 parameter='target')
    elif current_place is not None and current_place != desired_place:
        fail('STAY_ACTION_PLACE_CONFLICT',
             'Item place differs from the Stay lodging place', parameter='target',
             item_place_ref=copy.deepcopy(current_place),
             stay_lodging_ref=copy.deepcopy(desired_place))
    owner = _current_item_owner(editor.package, item_ref)
    if owner is not None:
        _stay_action_day_check(stay_record, action, owner, parameter='target')
    proposed = {
        'kind': 'stay_action', 'subject_ref': stay_ref, 'action': action,
        **({'place_ref': desired_place} if desired_place is not None else {}),
    }
    changed_fields = {field for field, value in proposed.items()
                      if item.get(field) != value}
    blockers = _stay_action_binding_claim_blockers(
        editor.package, item_ref, changed_fields)
    if blockers:
        fail('STAY_ACTION_BIND_BLOCKED',
             'An adopted confirmation or observation protects the Item binding fields',
             parameter='target', blockers=blockers,
             blocker_refs=[copy.deepcopy(value['ref']) for value in blockers])
    preserved = [field for field in ('id', 'title', 'timing', 'participants',
                                      'purpose', 'notes', 'lifecycle')
                 if field in item]
    item.update(copy.deepcopy(proposed))
    editor.parts['preserved_fields'] = preserved
    return editor.handle(target)


def stay_change_plan(editor, *, target, set=None, clear=None, append_note=None, units=None):
    from .core import edit_fields
    changes = copy.deepcopy({} if set is None else set)
    clear = [] if clear is None else clear
    if not isinstance(changes, dict) or not isinstance(clear, list) or any(not isinstance(k, str) for k in clear):
        fail('INVALID_ARGUMENT', 'set must be an object and clear a list of field names')
    stay = editor.record(target, {'stay'})
    period_changed = 'period' in changes
    if 'participants' in changes:
        from .party import normalize_participants
        changes['participants'] = normalize_participants(
            editor, changes['participants'], 'set.participants')
        if (stay.get('participants') == {'kind': 'unknown'}
                and changes['participants'] != {'kind': 'unknown'}):
            from .participant_protection import participant_review_refs
            refs = participant_review_refs(
                editor.package, editor.ref(target, {'stay'}), 'participants')
            if refs:
                editor.parts['participant_review_refs'] = refs
    if 'night_count' in stay and any(k in changes and changes[k] != stay[k] for k in ('period', 'use_kind')):
        if 'night_count' not in changes and 'night_count' not in clear:
            fail('NIGHT_COUNT_REVIEW_REQUIRED', 'Changing period/use_kind requires explicitly setting or clearing the recorded night_count')
    if changes or clear or append_note is not None:
        edit_fields(stay, changes=changes, clear=clear, append_note=append_note,
                    allowed={'use_kind', 'period', 'participants', 'requests', 'night_count', 'notes'},
                    clearable={'requests', 'night_count', 'notes'})
    elif not units:
        fail('INVALID_ARGUMENT', 'At least one explicit change is required')
    period_input(stay['period'], stay['use_kind'])
    if units is not None:
        if not isinstance(units, list):
            fail('INVALID_ARGUMENT', 'units must be a list of add/update edits')
        owner_ref = editor.ref(target, {'stay'})
        for entry in units:
            if not isinstance(entry, dict) or any(v is None for v in entry.values()):
                fail('INVALID_ARGUMENT', 'Each unit edit must be an object without null values')
            if entry.get('action') == 'add' and entry.keys() == {'action', 'key', 'value'}:
                add_unit(editor, stay, owner_ref, entry['key'], entry['value'])
            elif entry.get('action') == 'update' and {'action', 'target'} <= entry.keys() and not entry.keys() - {'action', 'target', 'set', 'clear', 'append_note'}:
                ref = editor.ref(entry['target'])
                if ref.get('owner') != owner_ref or ref.get('kind') != 'unit':
                    fail('REFERENCE_KIND_MISMATCH', 'Unit must belong to the target Stay')
                unit = editor.record(entry['target'])
                changes = copy.deepcopy(entry.get('set')) if entry.get('set') is not None else None
                if changes is not None and not isinstance(changes, dict):
                    fail('INVALID_ARGUMENT', 'units.set must be an object',
                         parameter='units.set')
                if changes is not None and 'occupants' in changes:
                    from .party import normalize_participants
                    changes['occupants'] = normalize_participants(
                        editor, changes['occupants'], 'units.set.occupants')
                    if (unit.get('occupants') in (None, {'kind': 'unknown'})
                            and changes['occupants'] != {'kind': 'unknown'}):
                        from .participant_protection import participant_review_refs
                        refs = participant_review_refs(
                            editor.package, ref, 'occupants')
                        if refs:
                            current = editor.parts.setdefault('participant_review_refs', [])
                            current.extend(value for value in refs if value not in current)
                edit_fields(unit, changes=changes, clear=entry.get('clear'), append_note=entry.get('append_note'),
                            allowed={'kind', 'count', 'period', 'description', 'occupants', 'notes'},
                            clearable={'description', 'occupants', 'notes'})
                period_input(unit['period'])
            else:
                fail('INVALID_ARGUMENT', 'Use add(key,value) or update(target,set/clear/append_note); unit deletion is not supported')
    for unit in stay.get('units', []):
        period_input(unit['period'], stay['use_kind'])
    if period_changed:
        _validate_actions_for_stay(editor.package, stay)
    return editor.handle(target)
