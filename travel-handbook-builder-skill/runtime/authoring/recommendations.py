"""Trip-specific place recommendations, without selecting itinerary activities."""
import copy

from .errors import fail, nonempty
from .movement import duration


EDITABLE = frozenset({'reason', 'related', 'interests', 'duration_advice', 'notes'})
CLEARABLE = EDITABLE - {'reason'}


def normalize_advice(value, parameter):
    if not isinstance(value, list):
        fail('INVALID_ARGUMENT', 'duration_advice must be a list', parameter=parameter)
    result = []
    for index, advice in enumerate(value):
        path = f'{parameter}[{index}]'
        if (not isinstance(advice, dict) or not {'experience', 'minutes'} <= advice.keys()
                or advice.keys() - {'experience', 'minutes', 'conditions', 'notes'}):
            fail('INVALID_ARGUMENT', 'Advice needs experience and minutes; conditions and notes are optional', parameter=path)
        nonempty(advice['experience'], path + '.experience')
        # Advice is not a timed execution. Do not silently accept an evidence
        # object here and then discard its basis/statement during normalization.
        if isinstance(advice['minutes'], dict):
            fail('UNSUPPORTED_VARIANT', 'Advice minutes accepts a number or range, not a duration-evidence object',
                 parameter=path + '.minutes')
        entry = {'experience': advice['experience'],
                 'duration': duration(advice['minutes'], path + '.minutes')}
        for field in ('conditions', 'notes'):
            if field in advice:
                nonempty(advice[field], path + '.' + field)
                entry[field] = advice[field]
        result.append(entry)
    return result


def normalize_fields(editor, values, parameter):
    result = {}
    for field, value in values.items():
        path = f'{parameter}.{field}'
        if value is None:
            fail('INVALID_ARGUMENT', 'Omit unknown fields; use clear for removal', parameter=path)
        if field in ('reason', 'notes'):
            nonempty(value, path)
            result[field] = value
        elif field == 'related':
            if not isinstance(value, list):
                fail('INVALID_ARGUMENT', 'related must be a list of Day or arrangement handles', parameter=path)
            result['related_refs'] = [editor.ref(ref, {'day', 'item'}) for ref in value]
        elif field == 'interests':
            if not isinstance(value, list):
                fail('INVALID_ARGUMENT', 'interests must be a list of strings', parameter=path)
            for index, interest in enumerate(value):
                nonempty(interest, f'{path}[{index}]')
            result[field] = copy.deepcopy(value)
        elif field == 'duration_advice':
            result[field] = normalize_advice(value, path)
    return result


def recommendation_add(editor, *, place, reason, related=None, interests=None,
                       duration_advice=None, notes=None):
    values = {'reason': reason}
    for field, value in (('related', related), ('interests', interests),
                         ('duration_advice', duration_advice), ('notes', notes)):
        if value is not None:
            values[field] = value
    fields = normalize_fields(editor, values, 'args')
    fields['place_ref'] = editor.ref(place, {'place'})
    return editor.add('recommendation', fields)


def recommendation_update(editor, *, target, set=None, clear=None, append_note=None):
    record = editor.record(target, {'recommendation'})
    changes = {} if set is None else set
    removal = [] if clear is None else clear
    if not isinstance(changes, dict):
        fail('INVALID_ARGUMENT', 'set must be an object', parameter='set')
    if changes.keys() - EDITABLE:
        fail('FIELD_NOT_EDITABLE', 'Recommendation identity and place cannot be changed', parameter='set')
    if (not isinstance(removal, list) or any(not isinstance(field, str) for field in removal)
            or len(frozenset(removal)) != len(removal)):
        fail('INVALID_ARGUMENT', 'clear must list distinct field names', parameter='clear')
    if frozenset(removal) - CLEARABLE:
        fail('FIELD_NOT_EDITABLE', 'Only optional recommendation information can be cleared', parameter='clear')
    if (changes.keys() & frozenset(removal)
            or (append_note is not None and ('notes' in changes or 'notes' in removal))):
        fail('CONFLICTING_EDIT', 'Do not set, clear and append the same field together')
    if not changes and not removal and append_note is None:
        fail('INVALID_ARGUMENT', 'Provide at least one explicit recommendation edit')
    normalized = normalize_fields(editor, changes, 'set')
    if append_note is not None:
        nonempty(append_note, 'append_note')
    record.update(normalized)
    for field in removal:
        record.pop('related_refs' if field == 'related' else field, None)
    if append_note is not None:
        record['notes'] = record['notes'] + '\n' + append_note if record.get('notes') else append_note
    return editor.handle(target)
