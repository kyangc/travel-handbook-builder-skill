"""Selected multimodal transfers and explicit map geometry."""
import copy
import math
from .errors import fail, nonempty
from .movement import (attach_path, number, protect_path_change, replace_path,
                       validate_mode)
from .movement import duration as normalize_duration
from .time_plans import normalize_time_plan
from .transport_services import require_current_schema, scheduled_movement
from .vehicles import bind_owned_vehicle
from .execution_replacements import (
    handle_for_ref, protect_execution_replacement,
    require_execution_edit_version, retire_handles,
)
from .source_topology import tombstone_removed_identities


def shape(value, required, optional, parameter):
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        fail('INVALID_ARGUMENT', 'Missing required or unrecognized fields', parameter=parameter)
    if any(v is None for v in value.values()):
        fail('INVALID_ARGUMENT', 'Omit unknown fields instead of null', parameter=parameter)


def _path_fields(*, kind, coordinate_system, mode, parts, mode_label=None):
    if coordinate_system != 'WGS84':
        fail('UNSUPPORTED_VARIANT', 'This input accepts explicit WGS84 only; no coordinate conversion')
    validate_mode(mode, mode_label)
    if not isinstance(parts, list) or not parts:
        fail('INVALID_ARGUMENT', 'parts must be a nonempty array of coordinate arrays', parameter='parts')
    for i, part in enumerate(parts):
        if not isinstance(part, list) or len(part) < 2:
            fail('INVALID_ARGUMENT', 'Each path part needs at least two vertices', parameter=f'parts[{i}]')
        for j, vertex in enumerate(part):
            parameter = f'parts[{i}][{j}]'
            shape(vertex, {'lat', 'lon'}, set(), parameter)
            for field, bound in [('lat', 90), ('lon', 180)]:
                value = vertex[field]
                if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)) or not -bound <= value <= bound:
                    fail('INVALID_ARGUMENT', 'Invalid coordinate', parameter=parameter + '.' + field)
    fields = {'kind': kind, 'coordinate_system': coordinate_system,
              'mode': mode, 'parts': copy.deepcopy(parts)}
    if mode_label is not None:
        fields['mode_label'] = mode_label
    return fields


def path_add_schematic(editor, *, coordinate_system, mode, parts, mode_label=None, notes=None):
    fields = _path_fields(kind='schematic', coordinate_system=coordinate_system,
                          mode=mode, parts=parts, mode_label=mode_label)
    if notes is not None:
        nonempty(notes, 'notes')
        fields['notes'] = notes
    return editor.add('path', fields)


def path_record(editor, *, kind, coordinate_system, mode, parts, source=None,
                mode_label=None, distance_m=None, distance_basis=None,
                generated_at=None, notes=None):
    if (not isinstance(kind, str)
            or kind not in {'observed_track', 'provider_route', 'authored_route'}):
        fail('INVALID_ARGUMENT', 'Choose observed_track, provider_route or authored_route',
             parameter='kind')
    if kind in {'observed_track', 'provider_route'} and source is None:
        fail('INVALID_ARGUMENT', 'This Path kind requires an explicit Source handle',
             parameter='source')
    if (distance_m is None) != (distance_basis is None):
        fail('INVALID_ARGUMENT', 'distance_m and distance_basis must be provided together',
             parameter='distance_m' if distance_m is None else 'distance_basis')
    fields = _path_fields(kind=kind, coordinate_system=coordinate_system,
                          mode=mode, parts=parts, mode_label=mode_label)
    if source is not None:
        fields['source_ref'] = editor.ref(source, {'source'})
    if distance_m is not None:
        fields['distance_m'] = number(distance_m, 'distance_m')
        nonempty(distance_basis, 'distance_basis')
        fields['distance_basis'] = distance_basis
    if generated_at is not None:
        fields['generated_at'] = copy.deepcopy(generated_at)
    if notes is not None:
        nonempty(notes, 'notes')
        fields['notes'] = notes
    return editor.add('path', fields)


def _optional_connection_field(source, destination, field, values, parameter):
    if field not in source:
        return
    value = source[field]
    if not isinstance(value, str) or value not in values:
        fail('INVALID_ARGUMENT', 'Unknown connection fact value', parameter=parameter + '.' + field)
    destination[field] = value


def _transfer_steps(editor, values, parameter):
    if not isinstance(values, list):
        fail('INVALID_ARGUMENT', 'steps must be an array', parameter=parameter)
    result = []
    for index, value in enumerate(values):
        path = f'{parameter}[{index}]'
        shape(value, {'kind', 'necessity'}, {'duration', 'place', 'deadline', 'notes'}, path)
        nonempty(value['kind'], path + '.kind')
        if value['necessity'] not in ('required', 'not_required', 'unknown'):
            fail('INVALID_ARGUMENT', 'Unknown TransferStep necessity', parameter=path + '.necessity')
        step = {'kind': value['kind'], 'necessity': value['necessity']}
        if 'duration' in value:
            step['duration'] = normalize_duration(value['duration'], path + '.duration')
        if 'place' in value:
            step['place_ref'] = editor.ref(value['place'], {'place', 'access_point'})
        if 'deadline' in value:
            if not isinstance(value['deadline'], dict):
                fail('INVALID_ARGUMENT', 'deadline must be a TimeConstraint object', parameter=path + '.deadline')
            step['deadline'] = copy.deepcopy(value['deadline'])
        if 'notes' in value:
            nonempty(value['notes'], path + '.notes')
            step['notes'] = value['notes']
        result.append(step)
    return result


def _connection_record(editor, value, handles, ordered_keys, index, parameter):
    if isinstance(value, dict) and set(value) - {'from', 'to', 'kind', 'notes'}:
        require_current_schema(editor, parameter)
    shape(value, {'from', 'to', 'kind'},
          {'key', 'steps', 'connection_protection', 'baggage_through',
           'airside_stay', 'required_buffer', 'notes'}, parameter)
    if value['from'] != ordered_keys[index] or value['to'] != ordered_keys[index + 1]:
        fail('INVALID_ARGUMENT', 'Connection must match the ordered adjacent legs', parameter=parameter)
    if not isinstance(value['kind'], str) or value['kind'] not in ('transfer', 'through_stop', 'continuation', 'unknown'):
        fail('INVALID_ARGUMENT', 'Unknown connection kind', parameter=parameter + '.kind')
    record = {'id': editor.allocate_id(), 'from_leg_ref': editor.ref(handles[ordered_keys[index]]),
              'to_leg_ref': editor.ref(handles[ordered_keys[index + 1]]), 'kind': value['kind']}
    if 'steps' in value:
        record['steps'] = _transfer_steps(editor, value['steps'], parameter + '.steps')
    _optional_connection_field(value, record, 'connection_protection',
                               ('protected', 'unprotected', 'unknown'), parameter)
    _optional_connection_field(value, record, 'baggage_through', ('yes', 'no', 'unknown'), parameter)
    _optional_connection_field(value, record, 'airside_stay', ('yes', 'no', 'unknown'), parameter)
    if 'required_buffer' in value:
        record['required_buffer'] = normalize_duration(value['required_buffer'], parameter + '.required_buffer')
    if 'notes' in value:
        nonempty(value['notes'], parameter + '.notes')
        record['notes'] = value['notes']
    return record


def _add_leg(editor, leg, parameter):
    """Create one typed Leg from the same closed input used by compose and replace."""
    if not isinstance(leg, dict):
        fail('INVALID_ARGUMENT', 'Leg must be an object', parameter=parameter)
    scheduled = any(field in leg for field in ('service', 'board_call', 'alight_call'))
    if scheduled:
        require_current_schema(editor, parameter)
        shape(leg, {'key', 'mode', 'service', 'board_call', 'alight_call'},
              {'notes', 'path'}, parameter)
    else:
        shape(leg, {'key', 'mode', 'from', 'to'},
              {'mode_label', 'notes', 'path', 'timing', 'vehicle'}, parameter)
        if 'timing' in leg:
            require_current_schema(editor, parameter + '.timing')
    key = leg['key']
    nonempty(key, parameter + '.key')
    if scheduled:
        selected_service = editor.record(leg['service'], {'transport_service'})
        validate_mode(leg['mode'], selected_service.get('mode_label'))
        movement = scheduled_movement(
            editor, mode=leg['mode'], service=leg['service'],
            board_call=leg['board_call'], alight_call=leg['alight_call'],
            parameter=parameter)
    else:
        selected_service = None
        validate_mode(leg['mode'], leg.get('mode_label'))
        allowed = ({'place', 'access_point'}
                   if editor.package.get('schema_version') in ('1.0',)
                   else {'place'})
        movement = {'kind': 'independent',
                    'from_ref': editor.ref(leg['from'], allowed),
                    'to_ref': editor.ref(leg['to'], allowed),
                    'timing': (normalize_time_plan(editor, leg['timing'], parameter + '.timing')
                               if 'timing' in leg else {'kind': 'unknown'})}
    fields = {'mode': leg['mode'], 'movement': movement}
    if scheduled and selected_service.get('mode_label') is not None:
        fields['mode_label'] = selected_service['mode_label']
    for field in ('notes', 'mode_label'):
        if field in leg:
            nonempty(leg[field], parameter + '.' + field)
            fields[field] = leg[field]
    if 'path' in leg:
        attach_path(editor, fields, leg['path'])
    if 'vehicle' in leg:
        bind_owned_vehicle(editor, fields, leg['vehicle'], parameter + '.vehicle')
    handle = editor.add('leg', fields)
    return key, handle, editor.record(handle)


def _scheduled_endpoints(editor, movement):
    service = next((value for value in editor.package.get('transport_services', [])
                    if value['id'] == movement['service_ref']['id']), None)
    if service is None:
        fail('REFERENCE_NOT_FOUND', 'Scheduled service is missing')
    calls = {value['id']: value for value in service['calls']}
    return (calls[movement['board_call_id']]['endpoint_ref'],
            calls[movement['alight_call_id']]['endpoint_ref'])


def _timing_boundary(timing, field):
    if field not in timing:
        return None
    value = timing[field]
    if timing.get('kind') == 'boundaries':
        return copy.deepcopy(value)
    if timing.get('kind') == 'fixed':
        return copy.deepcopy(value)
    if timing.get('kind') == 'estimated':
        return {'kind': 'estimated', 'value': copy.deepcopy(value)}
    return None


def _migrated_timing_fields(timing, board_time, alight_time, parameter):
    if timing == {'kind': 'unknown'}:
        return []
    forbidden = {'duration', 'duration_from_ref', 'end_from_ref', 'constraints', 'notes',
                 'start_not_before', 'start_not_after', 'from_ref'}
    if set(timing) & forbidden or timing.get('kind') not in {'fixed', 'estimated', 'boundaries'}:
        fail('LEG_TIMING_MIGRATION_REQUIRED',
             'Independent timing contains facts that cannot move into Service Calls', parameter=parameter)
    migrated = []
    for field, selected in (('start', board_time), ('end', alight_time)):
        current = _timing_boundary(timing, field)
        if current is None:
            continue
        if current.get('kind') == 'unknown' or current != selected:
            fail('LEG_TIMING_MIGRATION_REQUIRED',
                 'Independent timing does not exactly match selected Service Calls',
                 parameter=parameter + '.' + field)
        migrated.append(field)
    if not migrated:
        fail('LEG_TIMING_MIGRATION_REQUIRED',
             'Independent timing has no call boundary that can be migrated', parameter=parameter)
    return migrated


def _owner_leg(editor, journey_ref, value, parameter):
    ref = editor.ref(value, {'leg'})
    journey = next(record for record in editor.package.get('journeys', [])
                   if record['id'] == journey_ref['id'])
    if ref not in journey['leg_refs']:
        fail('REFERENCE_OWNER_MISMATCH', 'Leg belongs to another Journey', parameter=parameter)
    return editor.record(value, {'leg'})


def _add_leg_review_refs(editor, value):
    from .item_times import leg_time_review_entries
    entries = leg_time_review_entries(editor.package, editor.ref(value, {'leg'}))
    if entries:
        current = editor.parts.setdefault('review_refs', [])
        current.extend(entry for entry in entries if entry not in current)


def _enrich_connection(editor, journey_ref, edit, parameter):
    allowed = {'action', 'target', 'kind', 'add_steps', 'connection_protection',
               'baggage_through', 'airside_stay', 'required_buffer', 'notes'}
    if set(edit) - allowed:
        fail('INVALID_ARGUMENT', 'Unrecognized connection enrichment field', parameter=parameter)
    ref = editor.ref(edit['target'])
    if ref.get('kind') != 'connection':
        fail('REFERENCE_KIND_MISMATCH', 'Use a Connection local handle', parameter=parameter + '.target')
    if ref.get('owner') != journey_ref:
        fail('REFERENCE_OWNER_MISMATCH', 'Connection belongs to another Journey',
             parameter=parameter + '.target')
    record = editor.record(edit['target'])
    changed = set(edit) - {'action', 'target'}
    if not changed:
        fail('INVALID_ARGUMENT', 'Provide at least one Connection fact', parameter=parameter)
    enums = {
        'kind': ('transfer', 'through_stop', 'continuation', 'unknown'),
        'connection_protection': ('protected', 'unprotected', 'unknown'),
        'baggage_through': ('yes', 'no', 'unknown'),
        'airside_stay': ('yes', 'no', 'unknown'),
    }
    for field, values in enums.items():
        if field not in edit:
            continue
        proposed = edit[field]
        if not isinstance(proposed, str) or proposed not in values:
            fail('INVALID_ARGUMENT', 'Unknown connection fact value', parameter=parameter + '.' + field)
        current = record.get(field)
        if current is None or current == 'unknown':
            record[field] = proposed
        elif current != proposed:
            fail('CONNECTION_FACT_REPLACEMENT_REQUIRED',
                 'Known Connection fact cannot be replaced by this method', parameter=parameter + '.' + field)
    if 'required_buffer' in edit:
        proposed = normalize_duration(edit['required_buffer'], parameter + '.required_buffer')
        current = record.get('required_buffer')
        if current is None:
            record['required_buffer'] = proposed
        elif current != proposed:
            fail('CONNECTION_FACT_REPLACEMENT_REQUIRED',
                 'Known required buffer cannot be replaced by this method',
                 parameter=parameter + '.required_buffer')
    if 'notes' in edit:
        nonempty(edit['notes'], parameter + '.notes')
        if 'notes' not in record:
            record['notes'] = edit['notes']
        elif record['notes'] != edit['notes']:
            fail('CONNECTION_FACT_REPLACEMENT_REQUIRED',
                 'Known Connection notes cannot be replaced by this method', parameter=parameter + '.notes')
    if 'add_steps' in edit:
        steps = _transfer_steps(editor, edit['add_steps'], parameter + '.add_steps')
        if not steps:
            fail('INVALID_ARGUMENT', 'add_steps must be nonempty', parameter=parameter + '.add_steps')
        record.setdefault('steps', []).extend(steps)


def journey_edit(editor, *, target, edits):
    require_current_schema(editor)
    item = editor.record(target, {'item'})
    if item.get('kind') != 'transport' or item.get('lifecycle', 'current') != 'current':
        fail('REFERENCE_KIND_MISMATCH', 'Use a current transport Item handle', parameter='target')
    journey_ref = item.get('subject_ref')
    if not isinstance(journey_ref, dict) or journey_ref.get('type') != 'journey':
        fail('REFERENCE_KIND_MISMATCH', 'Transport Item must own a Journey', parameter='target')
    if not isinstance(edits, list) or not edits:
        fail('INVALID_ARGUMENT', 'edits must be a nonempty list', parameter='edits')
    for index, edit in enumerate(edits):
        parameter = f'edits[{index}]'
        if not isinstance(edit, dict) or not {'action', 'target'} <= set(edit):
            fail('INVALID_ARGUMENT', 'Edit requires action and target', parameter=parameter)
        action = edit['action']
        if action == 'set_independent_timing':
            if set(edit) != {'action', 'target', 'timing'}:
                fail('INVALID_ARGUMENT', 'set_independent_timing needs target and timing only', parameter=parameter)
            leg = _owner_leg(editor, journey_ref, edit['target'], parameter + '.target')
            if leg['movement']['kind'] != 'independent':
                fail('UNSUPPORTED_VARIANT', 'Scheduled Leg timing belongs to Service Calls', parameter=parameter + '.target')
            _add_leg_review_refs(editor, edit['target'])
            leg['movement']['timing'] = normalize_time_plan(editor, edit['timing'], parameter + '.timing')
        elif action == 'bind_service':
            if set(edit) != {'action', 'target', 'service', 'board_call', 'alight_call'}:
                fail('INVALID_ARGUMENT', 'bind_service needs target, service and two Calls only', parameter=parameter)
            leg = _owner_leg(editor, journey_ref, edit['target'], parameter + '.target')
            if leg['movement']['kind'] != 'independent':
                fail('SERVICE_FACT_REPLACEMENT_REQUIRED', 'Leg is already scheduled', parameter=parameter + '.target')
            _add_leg_review_refs(editor, edit['target'])
            movement = scheduled_movement(editor, mode=leg['mode'], service=edit['service'],
                                          board_call=edit['board_call'], alight_call=edit['alight_call'],
                                          parameter=parameter)
            if (leg['movement']['from_ref'], leg['movement']['to_ref']) != _scheduled_endpoints(editor, movement):
                fail('SERVICE_FACT_REPLACEMENT_REQUIRED',
                     'Selected Service Call endpoints must exactly match the independent Leg', parameter=parameter)
            service = editor.record(edit['service'], {'transport_service'})
            if leg['mode'] == 'other' and leg.get('mode_label') != service.get('mode_label'):
                fail('SERVICE_MODE_MISMATCH', 'Other-mode label must match the selected service',
                     parameter=parameter + '.service')
            calls = {value['id']: value for value in service['calls']}
            migrated = _migrated_timing_fields(
                leg['movement']['timing'], calls[movement['board_call_id']]['departure'],
                calls[movement['alight_call_id']]['arrival'], parameter + '.target')
            leg['movement'] = movement
            editor.parts.setdefault('migrated_timing_fields', {})[editor.handle(edit['target'])['handle']] = migrated
            editor.parts.setdefault('review', []).append({
                'code': 'TIME_PROJECTION_REVIEW', 'target': editor.handle(target),
                'message': 'The Item timing was retained and may describe a wider envelope or a duplicate projection.'})
        elif action == 'enrich_connection':
            _enrich_connection(editor, journey_ref, edit, parameter)
        elif action == 'bind_owned_vehicle':
            if set(edit) != {'action', 'target', 'vehicle'}:
                fail('INVALID_ARGUMENT',
                     'bind_owned_vehicle needs target and vehicle only', parameter=parameter)
            leg = _owner_leg(editor, journey_ref, edit['target'], parameter + '.target')
            bind_owned_vehicle(editor, leg, edit['vehicle'], parameter + '.vehicle')
        elif action == 'set_leg_path':
            if set(edit) != {'action', 'target', 'path'}:
                fail('INVALID_ARGUMENT', 'set_leg_path needs target and path only',
                     parameter=parameter)
            leg = _owner_leg(editor, journey_ref, edit['target'], parameter + '.target')
            target_ref = editor.ref(edit['target'], {'leg'})
            replace_path(editor, leg, edit['path'], target_ref, parameter + '.path')
        elif action == 'clear_leg_path':
            if set(edit) != {'action', 'target'}:
                fail('INVALID_ARGUMENT', 'clear_leg_path needs target only',
                     parameter=parameter)
            leg = _owner_leg(editor, journey_ref, edit['target'], parameter + '.target')
            target_ref = editor.ref(edit['target'], {'leg'})
            protect_path_change(editor, target_ref, leg.get('path_ref'), None,
                                parameter + '.target')
            leg.pop('path_ref', None)
            leg.pop('path_direction', None)
        else:
            fail('UNSUPPORTED_VARIANT', 'Unknown Journey edit action', parameter=parameter + '.action')
    return editor.handle(target)


def _replacement_connection(editor, value, *, expected_from, expected_to,
                            replacement_key, from_handle, to_handle,
                            parameter):
    if not isinstance(value, dict):
        fail('INVALID_ARGUMENT', 'Connection must be an object', parameter=parameter)

    def endpoint(candidate, expected, field):
        normalized = replacement_key if candidate == replacement_key else editor.handle(candidate)
        if normalized != expected:
            fail('INVALID_ARGUMENT',
                 'Connection must explicitly match the final adjacent Legs',
                 parameter=f'{parameter}.{field}')

    endpoint(value.get('from'), expected_from, 'from')
    endpoint(value.get('to'), expected_to, 'to')
    normalized = copy.deepcopy(value)
    normalized['from'] = 'from'
    normalized['to'] = 'to'
    return _connection_record(
        editor, normalized, {'from': from_handle, 'to': to_handle},
        ['from', 'to'], 0, parameter)


def journey_replace_leg(editor, *, target, leg, replacement, connections, reason):
    """Replace one execution Leg without re-pointing its stable handle."""
    require_execution_edit_version(editor)
    nonempty(reason, 'reason')
    item_handle = editor.handle(target)
    item = editor.record(item_handle, {'item'})
    if item.get('kind') != 'transport' or item.get('lifecycle', 'current') != 'current':
        fail('REFERENCE_KIND_MISMATCH', 'Use a current transport Item handle',
             parameter='target')
    journey_ref = item.get('subject_ref')
    if not isinstance(journey_ref, dict) or journey_ref.get('type') != 'journey':
        fail('REFERENCE_KIND_MISMATCH', 'Transport Item must own a Journey',
             parameter='target')
    journey = next((value for value in editor.package.get('journeys', [])
                    if {'type': 'journey', 'id': value['id']} == journey_ref), None)
    if journey is None or journey.get('lifecycle', 'current') != 'current':
        fail('REFERENCE_NOT_FOUND', 'Current Journey is missing', parameter='target')
    leg_handle = editor.handle(leg)
    leg_ref = editor.ref(leg_handle, {'leg'})
    if leg_ref not in journey.get('leg_refs', []):
        fail('REFERENCE_OWNER_MISMATCH', 'Leg belongs to another Journey', parameter='leg')
    leg_index = journey['leg_refs'].index(leg_ref)
    existing_leg_handles = [handle_for_ref(editor, ref) for ref in journey['leg_refs']]
    if not isinstance(connections, list):
        fail('INVALID_ARGUMENT', 'connections must be an array', parameter='connections')
    expected_count = int(leg_index > 0) + int(leg_index < len(journey['leg_refs']) - 1)
    if len(connections) != expected_count:
        fail('INVALID_ARGUMENT',
             'Explicitly replace every Connection adjacent to the selected Leg',
             parameter='connections', expected_count=expected_count)

    connection_indices = []
    if leg_index > 0:
        connection_indices.append(leg_index - 1)
    if leg_index < len(journey['leg_refs']) - 1:
        connection_indices.append(leg_index)
    if len(journey.get('connections', [])) != max(0, len(journey['leg_refs']) - 1):
        fail('STATE_FORMAT', 'Journey connections do not match its adjacent Leg chain')
    old_connection_refs = [
        {'owner': copy.deepcopy(journey_ref), 'kind': 'connection',
         'id': journey['connections'][index]['id']}
        for index in connection_indices
    ]
    removed_refs = [leg_ref, *old_connection_refs]
    removed_handles = protect_execution_replacement(
        editor, removed_refs, structural_owners=[journey_ref],
        protected_owner_refs=[journey_ref, editor.ref(item_handle, {'item'})])

    replacement_key, replacement_handle, _ = _add_leg(
        editor, replacement, 'replacement')
    if replacement_key in {'from', 'to'}:
        fail('INVALID_ARGUMENT', 'replacement.key uses a reserved local name',
             parameter='replacement.key')

    new_connections = {}
    new_records = {}
    for offset, index in enumerate(connection_indices):
        incoming = index == leg_index - 1 and leg_index > 0
        from_handle = (existing_leg_handles[leg_index - 1]
                       if incoming else replacement_handle)
        to_handle = (replacement_handle if incoming
                     else existing_leg_handles[leg_index + 1])
        expected_from = from_handle if from_handle != replacement_handle else replacement_key
        expected_to = to_handle if to_handle != replacement_handle else replacement_key
        parameter = f'connections[{offset}]'
        record = _replacement_connection(
            editor, connections[offset], expected_from=expected_from,
            expected_to=expected_to, replacement_key=replacement_key,
            from_handle=from_handle, to_handle=to_handle, parameter=parameter)
        key = connections[offset].get('key', 'incoming' if incoming else 'outgoing')
        nonempty(key, parameter + '.key')
        if key in new_connections:
            fail('DUPLICATE_ALIAS', 'Connection keys must be unique',
                 parameter=parameter + '.key')
        new_connections[key] = record
        new_records[index] = record

    old_connections = journey['connections']
    journey['leg_refs'][leg_index] = editor.ref(replacement_handle, {'leg'})
    journey['connections'] = [
        new_records.get(index, record)
        for index, record in enumerate(old_connections)
    ]
    editor.package['legs'] = [value for value in editor.package.get('legs', [])
                              if value['id'] != leg_ref['id']]

    connection_handles = {
        key: editor.register_local(journey_ref, 'connection', record)
        for key, record in new_connections.items()
    }
    kept_leg_handles = [value for index, value in enumerate(existing_leg_handles)
                        if index != leg_index]
    kept_connection_handles = [
        handle_for_ref(editor, {'owner': copy.deepcopy(journey_ref),
                                'kind': 'connection', 'id': record['id']})
        for index, record in enumerate(old_connections)
        if index not in connection_indices
    ]
    tombstone_removed_identities(editor, removed_refs)
    retire_handles(editor, removed_refs)

    editor.parts['reason'] = reason
    editor.parts['legs'] = {replacement_key: replacement_handle}
    editor.parts['connections'] = connection_handles
    editor.parts['kept'] = {
        'items': [item_handle],
        'journeys': [handle_for_ref(editor, journey_ref)],
        'legs': kept_leg_handles,
        'connections': kept_connection_handles,
    }
    editor.parts['created'] = {
        'legs': [replacement_handle],
        'connections': list(connection_handles.values()),
    }
    editor.parts['removed'] = {
        'legs': [removed_handles[0]],
        'connections': removed_handles[1:],
    }
    editor.parts['replacements'] = [{
        'previous': removed_handles[0], 'current': replacement_handle}]
    return item_handle


def journey_compose(editor, *, day, title, legs, connections, participants=None, timing=None):
    nonempty(title, 'title')
    editor.record(day, {'day'})
    if not isinstance(legs, list) or not legs:
        fail('INVALID_ARGUMENT', 'legs must be a nonempty list', parameter='legs')
    if not isinstance(connections, list) or len(connections) != len(legs) - 1:
        fail('INVALID_ARGUMENT', 'Explicitly describe every adjacent connection', parameter='connections')
    handles, records = {}, []
    for i, leg in enumerate(legs):
        parameter = f'legs[{i}]'
        if not isinstance(leg, dict):
            fail('INVALID_ARGUMENT', 'Leg must be an object', parameter=parameter)
        scheduled = any(field in leg for field in ('service', 'board_call', 'alight_call'))
        if scheduled:
            require_current_schema(editor, parameter)
            shape(leg, {'key', 'mode', 'service', 'board_call', 'alight_call'},
                  {'notes', 'path'}, parameter)
        else:
            shape(leg, {'key', 'mode', 'from', 'to'},
                  {'mode_label', 'notes', 'path', 'timing', 'vehicle'}, parameter)
            if 'timing' in leg:
                require_current_schema(editor, parameter + '.timing')
        key = leg['key']
        nonempty(key, parameter + '.key')
        if key in handles:
            fail('DUPLICATE_ALIAS', 'Leg keys must be unique', parameter=parameter + '.key')
        if scheduled:
            selected_service = editor.record(leg['service'], {'transport_service'})
            validate_mode(leg['mode'], selected_service.get('mode_label'))
            movement = scheduled_movement(editor, mode=leg['mode'], service=leg['service'],
                                          board_call=leg['board_call'], alight_call=leg['alight_call'],
                                          parameter=parameter)
        else:
            validate_mode(leg['mode'], leg.get('mode_label'))
            allowed = ({'place', 'access_point'}
                       if editor.package.get('schema_version') in ('1.0',)
                       else {'place'})
            movement = {'kind': 'independent', 'from_ref': editor.ref(leg['from'], allowed),
                        'to_ref': editor.ref(leg['to'], allowed),
                        'timing': normalize_time_plan(editor, leg['timing'], parameter + '.timing')
                                  if 'timing' in leg else {'kind': 'unknown'}}
        if (editor.package.get('schema_version') not in ('1.0',) and records
                and records[-1]['movement']['to_ref'] != movement['from_ref']):
            fail('DISCONNECTED_JOURNEY', 'Adjacent legs must share the same endpoint; supply a connecting leg explicitly', parameter=parameter + '.from')
        fields = {'mode': leg['mode'], 'movement': movement}
        if scheduled and selected_service.get('mode_label') is not None:
            fields['mode_label'] = selected_service['mode_label']
        for field in ('notes', 'mode_label'):
            if field in leg:
                nonempty(leg[field], parameter + '.' + field)
                fields[field] = leg[field]
        if 'path' in leg:
            attach_path(editor, fields, leg['path'])
        if 'vehicle' in leg:
            bind_owned_vehicle(editor, fields, leg['vehicle'], parameter + '.vehicle')
        handle = editor.add('leg', fields)
        handles[key] = handle
        records.append(editor.record(handle))
    keys = list(handles)
    connection_records, connection_keys = [], {}
    for i, connection in enumerate(connections):
        parameter = f'connections[{i}]'
        record = _connection_record(editor, connection, handles, keys, i, parameter)
        connection_records.append(record)
        connection_key = connection.get('key', f'{keys[i]}->{keys[i + 1]}')
        nonempty(connection_key, parameter + '.key')
        if connection_key in connection_keys:
            fail('DUPLICATE_ALIAS', 'Connection keys must be unique', parameter=parameter + '.key')
        connection_keys[connection_key] = record
    journey = editor.add('journey', {'title': title, 'leg_refs': [editor.ref(h) for h in handles.values()], 'connections': connection_records})
    item_timing = timing
    if isinstance(timing, dict) and timing.get('kind') == 'derived' and 'from_ref' not in timing:
        require_current_schema(editor, 'timing')
        if set(timing) - {'kind', 'notes', 'constraints'}:
            fail('INVALID_ARGUMENT', 'Derived Journey timing accepts kind, notes and constraints only', parameter='timing')
        item_timing = normalize_time_plan(editor, {**timing, 'from_ref': editor.ref(journey)})
    primary = editor.create_arrangement(day, title, 'transport', journey, participants=participants, timing=item_timing)
    owner = editor.ref(journey)
    editor.parts['legs'] = handles
    editor.parts['journey'] = journey
    editor.parts['connections'] = {key: editor.register_local(owner, 'connection', record)
                                   for key, record in connection_keys.items()}
    return primary
