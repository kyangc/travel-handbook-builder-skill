"""Closed friendly TimePlan inputs shared by public authoring methods."""
import copy
import math

from .errors import fail


def _finite_number(value, parameter):
    if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)):
        fail('INVALID_ARGUMENT', 'offset/minutes must be a finite number', parameter=parameter)
    return value


def _requires_current_schema(value):
    kind = value.get('kind')
    if kind == 'boundaries' or 'end_from' in value or 'end_from_ref' in value:
        return True
    if kind in {'fixed', 'estimated'} and 'start' not in value:
        return True
    return any(entry.get('kind') == 'after' for entry in value.get('constraints', []))


def normalize_time_plan(editor, value, parameter='timing'):
    if not isinstance(value, dict):
        fail('INVALID_ARGUMENT', 'timing must be an object', parameter=parameter)
    if not isinstance(value.get('kind'), str):
        fail('INVALID_ARGUMENT', 'timing.kind must be a string', parameter=parameter + '.kind')
    constraints_input = value.get('constraints', [])
    if not isinstance(constraints_input, list):
        fail('INVALID_ARGUMENT', 'constraints must be an array', parameter=parameter + '.constraints')
    if any(not isinstance(entry, dict) for entry in constraints_input):
        fail('INVALID_ARGUMENT', 'each constraint must be an object', parameter=parameter + '.constraints')
    if (_requires_current_schema(value)
            and editor.package.get('schema_version') not in ('1.0',)):
        fail('SCHEMA_VERSION_UNSUPPORTED', 'This time shape requires schema version 1.0',
             parameter=parameter, supported_version='1.0')
    result = copy.deepcopy(value)
    if 'end_from' in result:
        if 'end_from_ref' in result:
            fail('CONFLICTING_EDIT', 'Use end_from once', parameter=parameter + '.end_from')
        relation = result.pop('end_from')
        if (not isinstance(relation, dict)
                or set(relation) != {'target', 'field', 'offset_minutes'}):
            fail('INVALID_ARGUMENT', 'end_from needs target, field and offset_minutes only',
                 parameter=parameter + '.end_from')
        if not isinstance(relation['field'], str) or relation['field'] not in {'start', 'end'}:
            fail('INVALID_ARGUMENT', 'end_from.field must be start or end',
                 parameter=parameter + '.end_from.field')
        result['end_from_ref'] = {
            'ref': editor.ref(relation['target'], {'item', 'activity'}),
            'field': relation['field'],
            'offset_minutes': _finite_number(
                relation['offset_minutes'], parameter + '.end_from.offset_minutes'),
        }
    constraints = result.get('constraints')
    if constraints is not None:
        if not isinstance(constraints, list):
            fail('INVALID_ARGUMENT', 'constraints must be an array', parameter=parameter + '.constraints')
        normalized = []
        for index, constraint in enumerate(constraints):
            path = f'{parameter}.constraints[{index}]'
            if not isinstance(constraint, dict):
                fail('INVALID_ARGUMENT', 'constraint must be an object', parameter=path)
            entry = copy.deepcopy(constraint)
            relative = entry.get('relative_to')
            if isinstance(relative, dict) and 'target' in relative:
                if set(relative) != {'target', 'field'}:
                    fail('INVALID_ARGUMENT', 'relative_to needs target and field only',
                         parameter=path + '.relative_to')
                if not isinstance(relative['field'], str) or relative['field'] not in {'start', 'end'}:
                    fail('INVALID_ARGUMENT', 'relative_to.field must be start or end',
                         parameter=path + '.relative_to.field')
                entry['relative_to'] = {
                    'ref': editor.ref(relative['target'], {'item', 'activity'}),
                    'field': relative['field'],
                }
            if 'minutes' in entry:
                _finite_number(entry['minutes'], path + '.minutes')
            normalized.append(entry)
        result['constraints'] = normalized
    return result
