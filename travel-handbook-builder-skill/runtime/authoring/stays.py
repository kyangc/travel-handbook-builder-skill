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


def stay_change_plan(editor, *, target, set=None, clear=None, append_note=None, units=None):
    from .core import edit_fields
    changes = copy.deepcopy({} if set is None else set)
    clear = [] if clear is None else clear
    if not isinstance(changes, dict) or not isinstance(clear, list) or any(not isinstance(k, str) for k in clear):
        fail('INVALID_ARGUMENT', 'set must be an object and clear a list of field names')
    stay = editor.record(target, {'stay'})
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
    return editor.handle(target)
