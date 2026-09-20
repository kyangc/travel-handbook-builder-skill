"""participant Trip-scoped member and immutable group authoring."""
import copy
from datetime import date

from .errors import fail, nonempty


def _require_current_schema(editor):
    if editor.package.get('schema_version') not in ('1.0',):
        fail('SCHEMA_VERSION_UNSUPPORTED', 'Party authoring requires 1.0')


def _party(editor):
    return editor.package['trip'].setdefault('party', {})


def _trip_ref(editor):
    trip = editor.package['trip']
    return {'type': 'trip', 'id': trip['id']}


def _trip_handle(editor):
    ref = _trip_ref(editor)
    handle = next((value for value, stored in editor.state['handles'].items()
                   if stored == ref), None)
    if handle is None:
        fail('STATE_FORMAT', 'Workspace Trip handle is missing')
    return {'handle': handle}


def normalize_age(value, parameter='age'):
    if not isinstance(value, dict) or set(value) - {'years', 'as_of'} or 'years' not in value:
        fail('INVALID_ARGUMENT', 'age requires years and optional as_of only', parameter=parameter)
    if type(value['years']) is not int or value['years'] < 0:
        fail('INVALID_ARGUMENT', 'age.years must be a nonnegative integer',
             parameter=f'{parameter}.years')
    if 'as_of' in value:
        if not isinstance(value['as_of'], str):
            fail('INVALID_ARGUMENT', 'age.as_of must be an ISO date',
                 parameter=f'{parameter}.as_of')
        try:
            date.fromisoformat(value['as_of'])
        except ValueError:
            fail('INVALID_ARGUMENT', 'age.as_of must be an ISO date',
                 parameter=f'{parameter}.as_of')
    return copy.deepcopy(value)


def normalize_participants(editor, value, parameter='participants'):
    """Normalize friendly member/group handles while retaining existing variants."""
    if not isinstance(value, dict):
        fail('INVALID_ARGUMENT', 'participants must be an object', parameter=parameter)
    if 'members' in value or 'groups' in value:
        if editor.package.get('schema_version') not in ('1.0',):
            fail('SCHEMA_VERSION_UNSUPPORTED', 'Participant handles require 1.0',
                 parameter=parameter)
        if set(value) not in ({'members'}, {'groups'}):
            fail('INVALID_ARGUMENT', 'Choose exactly one participant form', parameter=parameter)
        source = 'members' if 'members' in value else 'groups'
        values = value[source]
        if not isinstance(values, list) or not values:
            fail('INVALID_ARGUMENT', f'{source} must be a nonempty list of handles',
                 parameter=f'{parameter}.{source}')
        kind = 'member' if source == 'members' else 'group'
        ids = []
        for index, item in enumerate(values):
            ref = editor.ref(item)
            if ref.get('kind') != kind or ref.get('owner') != _trip_ref(editor):
                fail('REFERENCE_KIND_MISMATCH',
                     f'{source} must identify {kind} objects from this Trip',
                     reference=item, parameter=f'{parameter}.{source}[{index}]')
            if ref['id'] in ids:
                fail('INVALID_ARGUMENT', 'Participant handles must be unique',
                     parameter=f'{parameter}.{source}[{index}]')
            ids.append(ref['id'])
        return {kind + '_ids': ids}
    if set(value) == {'member_ids'}:
        ids = value['member_ids']
        if not isinstance(ids, list) or not ids or any(
                not isinstance(identifier, str) or not identifier for identifier in ids):
            fail('INVALID_ARGUMENT', 'member_ids must be nonempty unique IDs', parameter=parameter)
        if len(ids) != len(set(ids)):
            fail('INVALID_ARGUMENT', 'member_ids must be nonempty unique IDs', parameter=parameter)
        return copy.deepcopy(value)
    if set(value) == {'group_ids'}:
        ids = value['group_ids']
        if not isinstance(ids, list) or not ids or any(
                not isinstance(identifier, str) or not identifier for identifier in ids):
            fail('INVALID_ARGUMENT', 'group_ids must be nonempty unique IDs', parameter=parameter)
        if len(ids) != len(set(ids)):
            fail('INVALID_ARGUMENT', 'group_ids must be nonempty unique IDs', parameter=parameter)
        return copy.deepcopy(value)
    kind = value.get('kind')
    if set(value) == {'kind'} and isinstance(kind, str) and kind in {'unknown', 'all'}:
        return copy.deepcopy(value)
    if set(value) == {'kind', 'count'} and kind == 'count' and (
            type(value.get('count')) is int and value['count'] > 0):
        return copy.deepcopy(value)
    fail('INVALID_ARGUMENT', 'Choose one valid participant form', parameter=parameter)


def participant_member_snapshot(editor, value, parameter='participants', *, allow_count=True):
    """Freeze mutable Task/Coverage participant forms to member IDs."""
    if editor.package.get('schema_version') not in ('1.0',):
        fail('SCHEMA_VERSION_UNSUPPORTED', 'Participant identity snapshots require 1.0',
             parameter=parameter)
    normalized = normalize_participants(editor, value, parameter)
    party = editor.package['trip'].get('party', {})
    if 'group_ids' in normalized:
        groups = {group['id']: group for group in party.get('groups', [])}
        member_ids = []
        for identifier in normalized['group_ids']:
            group = groups.get(identifier)
            if group is None:
                fail('REFERENCE_NOT_FOUND', 'Participant group is not present in this Trip',
                     parameter=parameter)
            for member_id in group['member_ids']:
                if member_id not in member_ids:
                    member_ids.append(member_id)
        return {'member_ids': member_ids}
    if normalized == {'kind': 'all'}:
        members = party.get('members', [])
        if party.get('members_status') != 'complete' or not members:
            fail('PARTY_SCOPE_INSUFFICIENT',
                 'all requires a nonempty explicitly complete member list',
                 parameter=parameter)
        return {'member_ids': [member['id'] for member in members]}
    if normalized.get('kind') == 'count' and not allow_count:
        fail('INVALID_ARGUMENT', 'A participant count cannot identify responsible members',
             parameter=parameter)
    return normalized


def party_describe(editor, *, count=None, members_status=None, clear=None):
    _require_current_schema(editor)
    clear = [] if clear is None else copy.deepcopy(clear)
    if not isinstance(clear, list) or any(not isinstance(field, str) for field in clear):
        fail('INVALID_ARGUMENT', 'clear must be a list of party field names', parameter='clear')
    if set(clear) - {'count', 'members_status'}:
        fail('FIELD_NOT_EDITABLE', 'Only count and members_status can be cleared here')
    supplied = {key for key, value in (('count', count), ('members_status', members_status))
                if value is not None}
    if supplied & set(clear):
        fail('CONFLICTING_EDIT', 'Do not set and clear the same party field')
    if not supplied and not clear:
        fail('INVALID_ARGUMENT', 'Provide count, members_status, or clear')
    if count is not None and (type(count) is not int or count < 1):
        fail('INVALID_ARGUMENT', 'count must be a positive integer', parameter='count')
    if members_status is not None and (
            not isinstance(members_status, str)
            or members_status not in {'complete', 'incomplete'}):
        fail('INVALID_ARGUMENT', 'members_status must be complete or incomplete',
             parameter='members_status')
    party = _party(editor)
    if count is not None:
        party['count'] = count
    if members_status is not None:
        party['members_status'] = members_status
    for field in clear:
        party.pop(field, None)
    return _trip_handle(editor)


def party_member_add(editor, *, label, age=None, declared_category=None):
    _require_current_schema(editor)
    nonempty(label, 'label')
    member = {'id': editor.allocate_id(), 'label': label}
    if age is not None:
        member['age'] = normalize_age(age)
    if declared_category is not None:
        nonempty(declared_category, 'declared_category')
        member['declared_category'] = declared_category
    _party(editor).setdefault('members', []).append(member)
    return editor.register_local(_trip_ref(editor), 'member', member)


def party_member_update(editor, *, target, set):
    _require_current_schema(editor)
    if not isinstance(set, dict) or not set or set.keys() - {
            'label', 'age', 'declared_category'}:
        fail('INVALID_ARGUMENT',
             'set must contain label, age, or declared_category only', parameter='set')
    ref = editor.ref(target)
    if ref.get('kind') != 'member' or ref.get('owner') != _trip_ref(editor):
        fail('REFERENCE_KIND_MISMATCH', 'target must be a member of this Trip',
             reference=target, parameter='target')
    member = editor.record(target)
    if 'label' in set:
        nonempty(set['label'], 'set.label')
        member['label'] = set['label']
    if 'age' in set:
        proposed = normalize_age(set['age'], 'set.age')
        current = member.get('age')
        if current is not None and (
                proposed['years'] != current['years']
                or ('as_of' in current and proposed.get('as_of') != current['as_of'])):
            fail('MEMBER_FACT_REPLACEMENT_REQUIRED',
                 'Known age facts require a controlled replacement method', parameter='set.age')
        member['age'] = proposed
    if 'declared_category' in set:
        nonempty(set['declared_category'], 'set.declared_category')
        current = member.get('declared_category')
        if current is not None and current != set['declared_category']:
            fail('MEMBER_FACT_REPLACEMENT_REQUIRED',
                 'Known declared category requires a controlled replacement method',
                 parameter='set.declared_category')
        member['declared_category'] = set['declared_category']
    return editor.handle(target)


def party_group_add(editor, *, members, label=None):
    _require_current_schema(editor)
    if not isinstance(members, list) or not members:
        fail('INVALID_ARGUMENT', 'members must be a nonempty list of member handles',
             parameter='members')
    member_ids = []
    for index, value in enumerate(members):
        ref = editor.ref(value)
        if ref.get('kind') != 'member' or ref.get('owner') != _trip_ref(editor):
            fail('REFERENCE_KIND_MISMATCH', 'Group members must be members of this Trip',
                 reference=value, parameter=f'members[{index}]')
        if ref['id'] not in member_ids:
            member_ids.append(ref['id'])
    group = {'id': editor.allocate_id(), 'member_ids': member_ids}
    if label is not None:
        nonempty(label, 'label')
        group['label'] = label
    _party(editor).setdefault('groups', []).append(group)
    return editor.register_local(_trip_ref(editor), 'group', group)
