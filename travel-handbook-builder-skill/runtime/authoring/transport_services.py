"""Explicit transport services and their ordered local Calls."""
import copy

from .errors import fail, nonempty
from .movement import validate_mode


def require_current_schema(editor, parameter=None):
    if editor.package.get('schema_version') not in ('1.0',):
        fail('SCHEMA_VERSION_UNSUPPORTED', 'This transport shape requires schema version 1.0',
             parameter=parameter, supported_version='1.0')


def _shape(value, required, optional, parameter):
    if (not isinstance(value, dict) or not required <= value.keys()
            or value.keys() - required - optional):
        fail('INVALID_ARGUMENT', 'Missing required or unrecognized fields', parameter=parameter)
    if any(item is None for item in value.values()):
        fail('INVALID_ARGUMENT', 'Omit unknown fields instead of null', parameter=parameter)


def normalize_call_time(value, parameter):
    if not isinstance(value, dict):
        fail('INVALID_ARGUMENT', 'Call time must be an object', parameter=parameter)
    if 'kind' not in value:
        _shape(value, {'local', 'timezone'}, {'offset'}, parameter)
        nonempty(value['local'], parameter + '.local')
        nonempty(value['timezone'], parameter + '.timezone')
        if 'offset' in value:
            nonempty(value['offset'], parameter + '.offset')
        return copy.deepcopy(value)
    kind = value.get('kind')
    if kind == 'estimated':
        _shape(value, {'kind', 'value'}, set(), parameter)
        result = normalize_call_time(value['value'], parameter + '.value')
        if 'kind' in result:
            fail('INVALID_ARGUMENT', 'Estimated time value must be an exact zoned date-time', parameter=parameter + '.value')
        return {'kind': 'estimated', 'value': result}
    if kind == 'unknown':
        _shape(value, {'kind'}, {'notes'}, parameter)
        result = {'kind': 'unknown'}
        if 'notes' in value:
            nonempty(value['notes'], parameter + '.notes')
            result['notes'] = value['notes']
        return result
    fail('INVALID_ARGUMENT', 'Call time must be exact, estimated, or explicit unknown', parameter=parameter)


def call_and_index(editor, value, service_ref, service_record, parameter):
    ref = editor.ref(value)
    if ref.get('kind') != 'call':
        fail('REFERENCE_KIND_MISMATCH', 'Use a Call local handle', parameter=parameter)
    if ref.get('owner') != service_ref:
        fail('REFERENCE_OWNER_MISMATCH', 'Call belongs to another TransportService', parameter=parameter)
    call = editor.record(value)
    index = next((index for index, item in enumerate(service_record['calls']) if item['id'] == call['id']), None)
    if index is None:
        fail('REFERENCE_NOT_FOUND', 'Call is not present in its TransportService', parameter=parameter)
    return call, index


def scheduled_movement(editor, *, mode, service, board_call, alight_call, parameter):
    service_ref = editor.ref(service, {'transport_service'})
    record = editor.record(service)
    if record['mode'] != mode:
        fail('SERVICE_MODE_MISMATCH', 'Leg mode must match the selected service', parameter=parameter + '.mode')
    board, board_index = call_and_index(editor, board_call, service_ref, record, parameter + '.board_call')
    alight, alight_index = call_and_index(editor, alight_call, service_ref, record, parameter + '.alight_call')
    if board_index >= alight_index:
        fail('INVALID_ARGUMENT', 'Board Call must precede alight Call', parameter=parameter)
    if 'departure' not in board:
        fail('INVALID_ARGUMENT', 'Board Call must record departure, including explicit unknown',
             parameter=parameter + '.board_call')
    if 'arrival' not in alight:
        fail('INVALID_ARGUMENT', 'Alight Call must record arrival, including explicit unknown',
             parameter=parameter + '.alight_call')
    return {'kind': 'scheduled', 'service_ref': service_ref,
            'board_call_id': board['id'], 'alight_call_id': alight['id']}


def service_record(editor, *, mode, service_number, service_date, calls,
                   operator=None, mode_label=None, notes=None):
    require_current_schema(editor)
    validate_mode(mode, mode_label)
    nonempty(service_number, 'service_number')
    nonempty(service_date, 'service_date')
    if not isinstance(calls, list) or len(calls) < 2:
        fail('INVALID_ARGUMENT', 'calls must contain at least two ordered Call objects', parameter='calls')
    records, keyed = [], {}
    for index, value in enumerate(calls):
        parameter = f'calls[{index}]'
        _shape(value, {'key', 'endpoint'}, {'arrival', 'departure', 'notes'}, parameter)
        key = value['key']
        nonempty(key, parameter + '.key')
        if key in keyed:
            fail('DUPLICATE_ALIAS', 'Call keys must be unique within a service', parameter=parameter + '.key')
        if 'arrival' not in value and 'departure' not in value:
            fail('INVALID_ARGUMENT', 'Call requires arrival or departure', parameter=parameter)
        record = {'id': editor.allocate_id(),
                  'endpoint_ref': editor.ref(value['endpoint'], {'place', 'access_point'})}
        for field in ('arrival', 'departure'):
            if field in value:
                record[field] = normalize_call_time(value[field], parameter + '.' + field)
        if 'notes' in value:
            nonempty(value['notes'], parameter + '.notes')
            record['notes'] = value['notes']
        records.append(record)
        keyed[key] = record
    fields = {'mode': mode, 'service_number': service_number,
              'service_date': service_date, 'calls': records}
    for field, value in (('mode_label', mode_label), ('operator', operator), ('notes', notes)):
        if value is not None:
            nonempty(value, field)
            fields[field] = value
    service = editor.add('transport_service', fields)
    owner = editor.ref(service)
    editor.parts['calls'] = {key: editor.register_local(owner, 'call', record)
                             for key, record in keyed.items()}
    if operator is None:
        editor.parts['operator_unknown'] = True
    return service


def service_update(editor, *, target, operator=None, call_updates=None):
    require_current_schema(editor)
    service_handle = editor.handle(target)
    service_ref = editor.ref(service_handle, {'transport_service'})
    service = editor.record(service_handle)
    if operator is None and call_updates is None:
        fail('INVALID_ARGUMENT', 'Provide operator or call_updates')
    if operator is not None:
        nonempty(operator, 'operator')
        if 'operator' not in service:
            service['operator'] = operator
        elif service['operator'] != operator:
            fail('SERVICE_FACT_REPLACEMENT_REQUIRED', 'Known operator cannot be replaced by this method',
                 parameter='operator')
    if call_updates is not None:
        if not isinstance(call_updates, list) or not call_updates:
            fail('INVALID_ARGUMENT', 'call_updates must be a nonempty list', parameter='call_updates')
        seen = set()
        for index, value in enumerate(call_updates):
            parameter = f'call_updates[{index}]'
            _shape(value, {'target'}, {'arrival', 'departure', 'refine_endpoint'}, parameter)
            if set(value) == {'target'}:
                fail('INVALID_ARGUMENT', 'Call update requires a time fact or endpoint refinement',
                     parameter=parameter)
            call_ref = editor.ref(value['target'])
            if call_ref.get('kind') != 'call':
                fail('REFERENCE_KIND_MISMATCH', 'Use a Call local handle', parameter=parameter + '.target')
            if call_ref.get('owner') != service_ref:
                fail('REFERENCE_OWNER_MISMATCH', 'Call belongs to another TransportService',
                     parameter=parameter + '.target')
            if call_ref['id'] in seen:
                fail('INVALID_ARGUMENT', 'Update each Call once per operation', parameter=parameter + '.target')
            seen.add(call_ref['id'])
            call = editor.record(value['target'])
            for field in ('arrival', 'departure'):
                if field not in value:
                    continue
                proposed = normalize_call_time(value[field], parameter + '.' + field)
                current = call.get(field)
                if current is None:
                    call[field] = proposed
                elif current == proposed:
                    pass
                elif current.get('kind') == 'unknown' and proposed.get('kind') != 'unknown':
                    call[field] = proposed
                else:
                    fail('SERVICE_FACT_REPLACEMENT_REQUIRED',
                         'Known or explicitly unknown Call time cannot be replaced by this method',
                         parameter=parameter + '.' + field)
            if 'refine_endpoint' in value:
                point_ref = editor.ref(value['refine_endpoint'], {'access_point'})
                current = call['endpoint_ref']
                if current == point_ref:
                    continue
                if current.get('type') != 'place':
                    fail('SERVICE_FACT_REPLACEMENT_REQUIRED',
                         'An AccessPoint endpoint cannot be replaced by this method',
                         parameter=parameter + '.refine_endpoint')
                point = editor.record(value['refine_endpoint'], {'access_point'})
                if point.get('place_ref') != current:
                    fail('SERVICE_FACT_REPLACEMENT_REQUIRED',
                         'Endpoint refinement must select an AccessPoint of the current Place',
                         parameter=parameter + '.refine_endpoint')
                call['endpoint_ref'] = point_ref
    return service_handle
