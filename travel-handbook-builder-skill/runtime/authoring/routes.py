"""Selected sightseeing routes, without inferring travel choices or totals."""
import copy
import math

from .errors import fail, nonempty
from .movement import attach_path, protect_path_change, replace_path, validate_mode
from .duration_evidence import duration_input, update_duration_evidence
from .time_plans import normalize_time_plan
from .transport_services import require_current_schema, scheduled_movement
from .journeys import _migrated_timing_fields, _scheduled_endpoints
from .execution_replacements import (
    handle_for_ref, protect_execution_replacement,
    require_execution_edit_version, retire_handles,
)
from .source_topology import (
    finalize_route_source_adoption, prepare_route_source_adoption,
)

MISSING_PURPOSE = '本次游览目的未记录'


def shape(value, required, optional, parameter):
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        fail('INVALID_ARGUMENT', 'Missing required or unrecognized fields', parameter=parameter)
    for key, item in value.items():
        if item is None:
            fail('INVALID_ARGUMENT', 'Omit unknown fields; use clear for removal', parameter=f'{parameter}.{key}')


def distance(value, parameter):
    if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)) or value < 0:
        fail('INVALID_ARGUMENT', 'Distance must be a finite nonnegative number', parameter=parameter)
    return value


def optional_text(source, destination, field, parameter):
    if field in source:
        nonempty(source[field], f'{parameter}.{field}')
        destination[field] = source[field]


def missing_purpose(editor, handle):
    editor.parts.setdefault('missing_facts', []).append({
        'target': handle, 'field': 'purpose', 'reason': 'not_provided'})


def route_compose(editor, *, day, title, stops, segments, participants=None,
                  timing=None, source_adoption=None):
    if source_adoption is not None:
        require_execution_edit_version(editor)
    nonempty(title, 'title')
    editor.record(day, {'day'})
    if not isinstance(stops, list) or len(stops) < 2:
        fail('INVALID_ARGUMENT', 'A route needs at least two stop occurrences', parameter='stops')
    if not isinstance(segments, list) or len(segments) != len(stops) - 1:
        fail('INVALID_ARGUMENT', 'Provide one segment per adjacent stop pair', parameter='segments')
    stop_keys, segment_keys, leg_keys = {}, {}, {}
    stop_records, segment_records = [], []
    missing_keys = []
    origins = []
    for index, value in enumerate(stops):
        parameter = f'stops[{index}]'
        shape(value, {'key', 'place'}, {'purpose', 'dwell_minutes', 'notes'}, parameter)
        key = value['key']
        nonempty(key, parameter + '.key')
        if key in stop_keys:
            fail('DUPLICATE_ALIAS', 'Stop occurrence keys must be unique', parameter=parameter + '.key')
        record = {'id': editor.allocate_id(),
                  'endpoint_ref': editor.ref(value['place'], {'place', 'access_point'}),
                  'role': 'start' if index == 0 else 'end' if index == len(stops) - 1 else 'waypoint',
                  'purpose': MISSING_PURPOSE}
        if 'purpose' in value:
            optional_text(value, record, 'purpose', parameter)
        else:
            missing_keys.append(key)
        optional_text(value, record, 'notes', parameter)
        if 'dwell_minutes' in value:
            record['dwell'], origin = duration_input(value['dwell_minutes'], parameter + '.dwell_minutes')
            if origin is not None:
                origins.append(('stops', key, 'dwell', record['dwell'], origin))
        stop_keys[key] = record
        stop_records.append(record)
    ordered_keys = list(stop_keys)
    for index, value in enumerate(segments):
        parameter = f'segments[{index}]'
        if not isinstance(value, dict):
            fail('INVALID_ARGUMENT', 'Segment must be an object', parameter=parameter)
        leg_input = value.get('leg')
        if 'leg' in value:
            require_current_schema(editor, parameter)
            shape(value, {'key', 'from', 'to', 'leg'}, set(), parameter)
            if not isinstance(leg_input, dict):
                fail('INVALID_ARGUMENT', 'leg must be an object', parameter=parameter + '.leg')
            scheduled = any(field in leg_input for field in ('service', 'board_call', 'alight_call'))
            if scheduled:
                shape(leg_input, {'mode', 'service', 'board_call', 'alight_call'},
                      {'path', 'notes'}, parameter + '.leg')
            else:
                shape(leg_input, {'mode'}, {'timing', 'mode_label', 'path', 'notes'}, parameter + '.leg')
        else:
            scheduled = False
            shape(value, {'key', 'from', 'to', 'mode'},
                  {'mode_label', 'duration_minutes', 'distance_m', 'path', 'notes'}, parameter)
        key = value['key']
        nonempty(key, parameter + '.key')
        if key in segment_keys:
            fail('DUPLICATE_ALIAS', 'Segment keys must be unique', parameter=parameter + '.key')
        if value['from'] != ordered_keys[index] or value['to'] != ordered_keys[index + 1]:
            fail('INVALID_ARGUMENT', 'Segments must connect adjacent stops in their declared order', parameter=parameter)
        record = {'id': editor.allocate_id(), 'from_stop_id': stop_records[index]['id'],
                  'to_stop_id': stop_records[index + 1]['id']}
        if leg_input is not None:
            if scheduled:
                service = editor.record(leg_input['service'], {'transport_service'})
                validate_mode(leg_input['mode'], service.get('mode_label'))
                movement = scheduled_movement(
                    editor, mode=leg_input['mode'], service=leg_input['service'],
                    board_call=leg_input['board_call'], alight_call=leg_input['alight_call'],
                    parameter=parameter + '.leg')
                if _scheduled_endpoints(editor, movement) != (
                        stop_records[index]['endpoint_ref'], stop_records[index + 1]['endpoint_ref']):
                    fail('SERVICE_FACT_REPLACEMENT_REQUIRED',
                         'Scheduled Call endpoints must match the Route stops', parameter=parameter + '.leg')
                leg_fields = {'mode': leg_input['mode'], 'movement': movement}
                if service.get('mode_label') is not None:
                    leg_fields['mode_label'] = service['mode_label']
            else:
                validate_mode(leg_input['mode'], leg_input.get('mode_label'))
                leg_fields = {'mode': leg_input['mode'], 'movement': {
                    'kind': 'independent', 'from_ref': stop_records[index]['endpoint_ref'],
                    'to_ref': stop_records[index + 1]['endpoint_ref'],
                    'timing': normalize_time_plan(editor, leg_input['timing'], parameter + '.leg.timing')
                              if 'timing' in leg_input else {'kind': 'unknown'},
                }}
                optional_text(leg_input, leg_fields, 'mode_label', parameter + '.leg')
            optional_text(leg_input, leg_fields, 'notes', parameter + '.leg')
            if 'path' in leg_input:
                attach_path(editor, leg_fields, leg_input['path'])
            leg_handle = editor.add('leg', leg_fields)
            record['leg_ref'] = editor.ref(leg_handle)
            leg_keys[key] = leg_handle
        else:
            validate_mode(value['mode'], value.get('mode_label'))
            record['mode'] = value['mode']
            optional_text(value, record, 'mode_label', parameter)
            optional_text(value, record, 'notes', parameter)
            if 'duration_minutes' in value:
                record['duration'], origin = duration_input(value['duration_minutes'], parameter + '.duration_minutes')
                if origin is not None:
                    origins.append(('segments', key, 'duration', record['duration'], origin))
            if 'distance_m' in value:
                record['distance_m'] = distance(value['distance_m'], parameter + '.distance_m')
            if 'path' in value:
                attach_path(editor, record, value['path'])
        segment_keys[key] = record
        segment_records.append(record)
    route = editor.add('route', {'title': title, 'stops': stop_records, 'segments': segment_records})
    item_timing = timing
    if isinstance(timing, dict) and timing.get('kind') == 'derived' and 'from_ref' not in timing:
        require_current_schema(editor, 'timing')
        if set(timing) - {'kind', 'notes', 'constraints'}:
            fail('INVALID_ARGUMENT', 'Derived Route timing accepts kind, notes and constraints only', parameter='timing')
        item_timing = normalize_time_plan(editor, {**timing, 'from_ref': editor.ref(route)})
    primary = editor.create_arrangement(day, title, 'route', route, participants=participants, timing=item_timing)
    owner = editor.ref(route)
    stop_handles = {key: editor.register_local(owner, 'stop', record)
                    for key, record in stop_keys.items()}
    segment_handles = {key: editor.register_local(owner, 'segment', record)
                       for key, record in segment_keys.items()}
    editor.parts['stops'] = stop_handles
    editor.parts['segments'] = segment_handles
    editor.parts['legs'] = leg_keys
    for group, key, field, value, origin in origins:
        update_duration_evidence(editor, editor.parts[group][key], field, None, value, origin)
    for key in missing_keys:
        missing_purpose(editor, editor.parts['stops'][key])
    source_context = prepare_route_source_adoption(
        editor, source_adoption, item_handle=primary, route_ref=owner,
        stop_inputs=stops, segment_inputs=segments, initial=True)
    finalize_route_source_adoption(
        editor, source_context, item_handle=primary, route_ref=owner,
        stop_handles=stop_handles, segment_handles=segment_handles,
        leg_handles=leg_keys)
    return primary


def route_edit(editor, *, target, edits):
    item = editor.record(target, {'item'})
    if item.get('kind') != 'route' or item.get('lifecycle', 'current') != 'current':
        fail('REFERENCE_KIND_MISMATCH', 'Use the current route arrangement handle', parameter='target')
    owner = item.get('subject_ref')
    if not isinstance(owner, dict) or owner.get('type') != 'route':
        fail('REFERENCE_KIND_MISMATCH', 'The arrangement must refer to a route', parameter='target')
    if not isinstance(edits, list) or not edits:
        fail('INVALID_ARGUMENT', 'edits must be a nonempty list', parameter='edits')
    purpose_targets = {}
    for index, edit in enumerate(edits):
        parameter = f'edits[{index}]'
        if not isinstance(edit, dict) or not {'action', 'target'} <= set(edit):
            fail('INVALID_ARGUMENT', 'Edit requires action and target', parameter=parameter)
        action = edit['action']
        if action in ('set_leg_timing', 'bind_service'):
            require_current_schema(editor, parameter)
            required = ({'action', 'target', 'timing'} if action == 'set_leg_timing'
                        else {'action', 'target', 'service', 'board_call', 'alight_call'})
            if set(edit) != required:
                fail('INVALID_ARGUMENT', 'Leg edit has missing or unrecognized fields', parameter=parameter)
            reference = editor.ref(edit['target'])
            if reference.get('kind') != 'segment':
                fail('REFERENCE_KIND_MISMATCH', 'Use a Segment local handle', parameter=parameter + '.target')
            if reference.get('owner') != owner:
                fail('REFERENCE_OWNER_MISMATCH', 'Segment belongs to another Route', parameter=parameter + '.target')
            segment = editor.record(edit['target'])
            if 'leg_ref' not in segment:
                fail('UNSUPPORTED_VARIANT', 'Inline Segment has no independent Leg timing', parameter=parameter + '.target')
            leg_ref = segment['leg_ref']
            leg_handle_value = next(({'handle': handle} for handle, stored in editor.state['handles'].items()
                                     if stored == leg_ref), None)
            if leg_handle_value is None:
                fail('REFERENCE_NOT_FOUND', 'Owned Leg has no workspace handle', parameter=parameter + '.target')
            leg = editor.record(leg_handle_value, {'leg'})
            if leg['movement']['kind'] != 'independent':
                fail('UNSUPPORTED_VARIANT' if action == 'set_leg_timing' else 'SERVICE_FACT_REPLACEMENT_REQUIRED',
                     'Scheduled Leg cannot be changed by this action', parameter=parameter + '.target')
            from .journeys import _add_leg_review_refs
            _add_leg_review_refs(editor, leg_handle_value)
            if action == 'set_leg_timing':
                leg['movement']['timing'] = normalize_time_plan(editor, edit['timing'], parameter + '.timing')
            else:
                movement = scheduled_movement(
                    editor, mode=leg['mode'], service=edit['service'], board_call=edit['board_call'],
                    alight_call=edit['alight_call'], parameter=parameter)
                if (leg['movement']['from_ref'], leg['movement']['to_ref']) != _scheduled_endpoints(editor, movement):
                    fail('SERVICE_FACT_REPLACEMENT_REQUIRED',
                         'Selected Service Call endpoints must exactly match the Route Leg', parameter=parameter)
                service = editor.record(edit['service'], {'transport_service'})
                if leg['mode'] == 'other' and leg.get('mode_label') != service.get('mode_label'):
                    fail('SERVICE_MODE_MISMATCH', 'Other-mode label must match the selected service',
                         parameter=parameter + '.service')
                calls = {value['id']: value for value in service['calls']}
                migrated = _migrated_timing_fields(
                    leg['movement']['timing'], calls[movement['board_call_id']]['departure'],
                    calls[movement['alight_call_id']]['arrival'], parameter + '.target')
                leg['movement'] = movement
                editor.parts.setdefault('migrated_timing_fields', {})[
                    editor.handle(edit['target'])['handle']] = migrated
                editor.parts.setdefault('review', []).append({
                    'code': 'TIME_PROJECTION_REVIEW', 'target': editor.handle(target),
                    'message': 'The Item timing was retained and may describe a wider envelope or a duplicate projection.'})
            continue
        shape(edit, {'action', 'target'}, {'set', 'clear'}, parameter)
        if not isinstance(action, str) or action not in ('set_stop', 'set_segment'):
            fail('UNSUPPORTED_VARIANT', 'Unknown Route edit action', parameter=parameter + '.action')
        kind = 'stop' if action == 'set_stop' else 'segment'
        reference = editor.ref(edit['target'])
        if reference.get('kind') != kind:
            fail('REFERENCE_KIND_MISMATCH', 'Use a handle of the selected local kind', parameter=parameter + '.target')
        if reference.get('owner') != owner:
            fail('REFERENCE_OWNER_MISMATCH', 'The local object belongs to another route', parameter=parameter + '.target')
        record = editor.record(edit['target'])
        if kind == 'segment' and 'leg_ref' in record:
            fail('UNSUPPORTED_VARIANT', 'This edit only supports inline route segments', parameter=parameter + '.target')
        allowed = {'purpose', 'dwell_minutes', 'notes'} if kind == 'stop' else {'duration_minutes', 'distance_m', 'path', 'notes'}
        changes, clear = edit.get('set', {}), edit.get('clear', [])
        if not isinstance(changes, dict) or changes.keys() - allowed:
            fail('FIELD_NOT_EDITABLE', 'set contains unsupported fields', parameter=parameter + '.set')
        if (not isinstance(clear, list) or any(not isinstance(field, str) for field in clear)
                or len(set(clear)) != len(clear) or set(clear) - allowed):
            fail('FIELD_NOT_EDITABLE', 'clear must list distinct permitted fields', parameter=parameter + '.clear')
        if not changes and not clear:
            fail('INVALID_ARGUMENT', 'Provide at least one explicit edit', parameter=parameter)
        if changes.keys() & set(clear):
            fail('CONFLICTING_EDIT', 'Do not set and clear the same field', parameter=parameter)
        updated = copy.deepcopy(record)
        duration_changes = []
        mapping = {'dwell_minutes': 'dwell', 'duration_minutes': 'duration', 'path': 'path_ref'}
        for field, value in changes.items():
            field_path = parameter + '.set.' + field
            if value is None:
                fail('INVALID_ARGUMENT', 'Use clear instead of null', parameter=field_path)
            if field in ('purpose', 'notes'):
                nonempty(value, field_path)
                updated[field] = value
            elif field in ('dwell_minutes', 'duration_minutes'):
                normalized, origin = duration_input(value, field_path)
                updated[mapping[field]] = normalized
                duration_changes.append((mapping[field], record.get(mapping[field]), normalized, origin))
            elif field == 'distance_m':
                updated[field] = distance(value, field_path)
            elif field == 'path':
                replace_path(editor, updated, value, reference, field_path)
        for field in clear:
            if field == 'purpose':
                updated['purpose'] = MISSING_PURPOSE
                stable = editor.handle(edit['target'])
                purpose_targets[stable['handle']] = stable
            else:
                updated.pop(mapping.get(field, field), None)
                if field in ('dwell_minutes', 'duration_minutes'):
                    duration_changes.append((mapping[field], record.get(mapping[field]), None, None))
                if field == 'path':
                    protect_path_change(editor, reference, record.get('path_ref'), None,
                                        parameter + '.clear')
                    updated.pop('path_direction', None)
        record.clear()
        record.update(updated)
        for field, old, new, origin in duration_changes:
            update_duration_evidence(editor, edit['target'], field, old, new, origin)
    for handle in purpose_targets.values():
        if editor.record(handle)['purpose'] == MISSING_PURPOSE:
            missing_purpose(editor, handle)
    return editor.handle(target)


def _summary_clear_blockers(package, route_ref, fields):
    blockers = []
    for index, claim in enumerate(package.get('claims', [])):
        target = claim.get('target', {})
        if (target.get('object_ref') == route_ref
                and 'local_ref' not in target
                and target.get('field') in fields
                and claim.get('basis') in {'confirmation', 'observation'}
                and claim.get('disposition', 'adopted') in {'adopted', 'superseded'}):
            blockers.append({
                'kind': 'claim',
                'ref': {'type': 'claim', 'id': claim['id']},
                'field': target['field'],
                'path': f'/claims/{index}',
            })
    return blockers


def _interval_stop(editor, value, parameter):
    shape(value, {'key', 'place'}, {'purpose', 'dwell_minutes', 'notes'}, parameter)
    key = value['key']
    nonempty(key, parameter + '.key')
    if key in {'from', 'to'}:
        fail('INVALID_ARGUMENT', 'Interior Stop key uses a reserved endpoint name',
             parameter=parameter + '.key')
    record = {
        'id': editor.allocate_id(),
        'endpoint_ref': editor.ref(value['place'], {'place', 'access_point'}),
        'role': 'waypoint',
        'purpose': MISSING_PURPOSE,
    }
    missing = 'purpose' not in value
    if not missing:
        optional_text(value, record, 'purpose', parameter)
    optional_text(value, record, 'notes', parameter)
    origin = None
    if 'dwell_minutes' in value:
        record['dwell'], origin = duration_input(
            value['dwell_minutes'], parameter + '.dwell_minutes')
    return key, record, origin, missing


def _interval_segment(editor, value, *, from_record, to_record,
                      expected_from, expected_to, parameter):
    if not isinstance(value, dict):
        fail('INVALID_ARGUMENT', 'Segment must be an object', parameter=parameter)
    leg_input = value.get('leg')
    if 'leg' in value:
        shape(value, {'key', 'from', 'to', 'leg'}, set(), parameter)
        if not isinstance(leg_input, dict):
            fail('INVALID_ARGUMENT', 'leg must be an object', parameter=parameter + '.leg')
        scheduled = any(field in leg_input for field in ('service', 'board_call', 'alight_call'))
        if scheduled:
            shape(leg_input, {'mode', 'service', 'board_call', 'alight_call'},
                  {'path', 'notes'}, parameter + '.leg')
        else:
            shape(leg_input, {'mode'}, {'timing', 'mode_label', 'path', 'notes'},
                  parameter + '.leg')
    else:
        scheduled = False
        shape(value, {'key', 'from', 'to', 'mode'},
              {'mode_label', 'duration_minutes', 'distance_m', 'path', 'notes'},
              parameter)
    key = value['key']
    nonempty(key, parameter + '.key')
    if value['from'] != expected_from or value['to'] != expected_to:
        fail('INVALID_ARGUMENT',
             'Segments must explicitly connect the replacement endpoint keys in order',
             parameter=parameter)
    record = {'id': editor.allocate_id(),
              'from_stop_id': from_record['id'], 'to_stop_id': to_record['id']}
    origin = None
    leg_handle = None
    if leg_input is not None:
        if scheduled:
            service = editor.record(leg_input['service'], {'transport_service'})
            validate_mode(leg_input['mode'], service.get('mode_label'))
            movement = scheduled_movement(
                editor, mode=leg_input['mode'], service=leg_input['service'],
                board_call=leg_input['board_call'], alight_call=leg_input['alight_call'],
                parameter=parameter + '.leg')
            if _scheduled_endpoints(editor, movement) != (
                    from_record['endpoint_ref'], to_record['endpoint_ref']):
                fail('SERVICE_FACT_REPLACEMENT_REQUIRED',
                     'Scheduled Call endpoints must match the Route stops',
                     parameter=parameter + '.leg')
            leg_fields = {'mode': leg_input['mode'], 'movement': movement}
            if service.get('mode_label') is not None:
                leg_fields['mode_label'] = service['mode_label']
        else:
            validate_mode(leg_input['mode'], leg_input.get('mode_label'))
            leg_fields = {'mode': leg_input['mode'], 'movement': {
                'kind': 'independent',
                'from_ref': copy.deepcopy(from_record['endpoint_ref']),
                'to_ref': copy.deepcopy(to_record['endpoint_ref']),
                'timing': (normalize_time_plan(
                    editor, leg_input['timing'], parameter + '.leg.timing')
                           if 'timing' in leg_input else {'kind': 'unknown'}),
            }}
            optional_text(leg_input, leg_fields, 'mode_label', parameter + '.leg')
        optional_text(leg_input, leg_fields, 'notes', parameter + '.leg')
        if 'path' in leg_input:
            attach_path(editor, leg_fields, leg_input['path'])
        leg_handle = editor.add('leg', leg_fields)
        record['leg_ref'] = editor.ref(leg_handle, {'leg'})
    else:
        validate_mode(value['mode'], value.get('mode_label'))
        record['mode'] = value['mode']
        optional_text(value, record, 'mode_label', parameter)
        optional_text(value, record, 'notes', parameter)
        if 'duration_minutes' in value:
            record['duration'], origin = duration_input(
                value['duration_minutes'], parameter + '.duration_minutes')
        if 'distance_m' in value:
            record['distance_m'] = distance(value['distance_m'], parameter + '.distance_m')
        if 'path' in value:
            attach_path(editor, record, value['path'])
    return key, record, leg_handle, origin


def route_replace_interval(editor, *, target, from_stop, to_stop,
                           interior_stops, segments, reason,
                           clear_stale_summary=False, source_adoption=None):
    """Replace one ordered Route interval while retaining both endpoint Stops."""
    require_execution_edit_version(editor)
    nonempty(reason, 'reason')
    if type(clear_stale_summary) is not bool:
        fail('INVALID_ARGUMENT', 'clear_stale_summary must be boolean',
             parameter='clear_stale_summary')
    item_handle = editor.handle(target)
    item = editor.record(item_handle, {'item'})
    if item.get('kind') != 'route' or item.get('lifecycle', 'current') != 'current':
        fail('REFERENCE_KIND_MISMATCH', 'Use a current route Item handle',
             parameter='target')
    route_ref = item.get('subject_ref')
    if not isinstance(route_ref, dict) or route_ref.get('type') != 'route':
        fail('REFERENCE_KIND_MISMATCH', 'Route Item must own a Route', parameter='target')
    route = next((value for value in editor.package.get('routes', [])
                  if {'type': 'route', 'id': value['id']} == route_ref), None)
    if route is None or route.get('lifecycle', 'current') != 'current':
        fail('REFERENCE_NOT_FOUND', 'Current Route is missing', parameter='target')

    endpoint_refs = []
    endpoint_indices = []
    for parameter, value in (('from_stop', from_stop), ('to_stop', to_stop)):
        ref = editor.ref(value)
        if ref.get('kind') != 'stop':
            fail('REFERENCE_KIND_MISMATCH', 'Use a Route Stop handle', parameter=parameter)
        if ref.get('owner') != route_ref:
            fail('REFERENCE_OWNER_MISMATCH', 'Stop belongs to another Route',
                 parameter=parameter)
        index = next((offset for offset, stop in enumerate(route['stops'])
                      if stop['id'] == ref['id']), None)
        if index is None:
            fail('REFERENCE_NOT_FOUND', 'Stop is not current on this Route', parameter=parameter)
        endpoint_refs.append(ref)
        endpoint_indices.append(index)
    from_index, to_index = endpoint_indices
    if from_index >= to_index:
        fail('INVALID_ARGUMENT', 'from_stop must precede a distinct to_stop',
             parameter='from_stop')
    if not isinstance(interior_stops, list):
        fail('INVALID_ARGUMENT', 'interior_stops must be an array',
             parameter='interior_stops')
    if not isinstance(segments, list) or len(segments) != len(interior_stops) + 1:
        fail('INVALID_ARGUMENT',
             'Provide one explicit Segment for every adjacent replacement pair',
             parameter='segments')

    old_stop_refs = [
        {'owner': copy.deepcopy(route_ref), 'kind': 'stop', 'id': stop['id']}
        for stop in route['stops'][from_index + 1:to_index]
    ]
    old_segment_records = route['segments'][from_index:to_index]
    kept_old_segment_records = [*route['segments'][:from_index],
                                *route['segments'][to_index:]]
    old_segment_refs = [
        {'owner': copy.deepcopy(route_ref), 'kind': 'segment', 'id': segment['id']}
        for segment in old_segment_records
    ]
    old_leg_refs = [copy.deepcopy(segment['leg_ref']) for segment in old_segment_records
                    if 'leg_ref' in segment]
    kept_old_leg_refs = [copy.deepcopy(segment['leg_ref'])
                         for segment in kept_old_segment_records if 'leg_ref' in segment]
    removed_refs = [*old_stop_refs, *old_segment_refs, *old_leg_refs]

    summary_fields = [field for field in ('path_ref', 'path_usage', 'overall_estimate')
                      if field in route]
    if summary_fields and not clear_stale_summary:
        fail('ROUTE_SUMMARY_REVIEW_REQUIRED',
             'Route-wide path or duration summaries must be explicitly cleared',
             summary_fields=summary_fields)
    if summary_fields:
        blockers = _summary_clear_blockers(editor.package, route_ref, summary_fields)
        if blockers:
            fail('ROUTE_SUMMARY_REVIEW_REQUIRED',
                 'A protected statement prevents clearing a stale Route summary',
                 summary_fields=summary_fields, blockers=blockers,
                 blocker_refs=[copy.deepcopy(value['ref']) for value in blockers])

    source_context = prepare_route_source_adoption(
        editor, source_adoption, item_handle=item_handle, route_ref=route_ref,
        stop_inputs=interior_stops, segment_inputs=segments)
    removed_handles = protect_execution_replacement(
        editor, removed_refs, structural_owners=[route_ref],
        protected_owner_refs=[route_ref, editor.ref(item_handle, {'item'})])

    keyed_stops = {}
    stop_origins = []
    missing_keys = []
    for index, value in enumerate(interior_stops):
        key, record, origin, missing = _interval_stop(
            editor, value, f'interior_stops[{index}]')
        if key in keyed_stops:
            fail('DUPLICATE_ALIAS', 'Interior Stop keys must be unique',
                 parameter=f'interior_stops[{index}].key')
        keyed_stops[key] = record
        if origin is not None:
            stop_origins.append((key, record['dwell'], origin))
        if missing:
            missing_keys.append(key)

    replacement_stops = [route['stops'][from_index], *keyed_stops.values(),
                         route['stops'][to_index]]
    ordered_keys = ['from', *keyed_stops, 'to']
    keyed_segments = {}
    leg_handles = {}
    segment_origins = []
    for index, value in enumerate(segments):
        key, record, leg_handle, origin = _interval_segment(
            editor, value, from_record=replacement_stops[index],
            to_record=replacement_stops[index + 1],
            expected_from=ordered_keys[index], expected_to=ordered_keys[index + 1],
            parameter=f'segments[{index}]')
        if key in keyed_segments:
            fail('DUPLICATE_ALIAS', 'Segment keys must be unique',
                 parameter=f'segments[{index}].key')
        keyed_segments[key] = record
        if leg_handle is not None:
            leg_handles[key] = leg_handle
        if origin is not None:
            segment_origins.append((key, record['duration'], origin))

    old_leg_ids = {ref['id'] for ref in old_leg_refs}
    route['stops'] = [*route['stops'][:from_index + 1], *keyed_stops.values(),
                      *route['stops'][to_index:]]
    route['segments'] = [*route['segments'][:from_index], *keyed_segments.values(),
                         *route['segments'][to_index:]]
    for field in summary_fields:
        route.pop(field, None)
    if old_leg_ids:
        editor.package['legs'] = [value for value in editor.package.get('legs', [])
                                  if value['id'] not in old_leg_ids]

    stop_handles = {key: editor.register_local(route_ref, 'stop', record)
                    for key, record in keyed_stops.items()}
    segment_handles = {key: editor.register_local(route_ref, 'segment', record)
                       for key, record in keyed_segments.items()}
    for key, value, origin in stop_origins:
        update_duration_evidence(
            editor, stop_handles[key], 'dwell', None, value, origin)
    for key, value, origin in segment_origins:
        update_duration_evidence(
            editor, segment_handles[key], 'duration', None, value, origin)
    for key in missing_keys:
        missing_purpose(editor, stop_handles[key])

    kept_stop_handles = [
        handle_for_ref(editor, {'owner': copy.deepcopy(route_ref), 'kind': 'stop',
                                'id': stop['id']})
        for stop in route['stops'] if stop['id'] not in {value['id'] for value in keyed_stops.values()}
    ]
    kept_segment_handles = [
        handle_for_ref(editor, {'owner': copy.deepcopy(route_ref), 'kind': 'segment',
                                'id': segment['id']})
        for segment in route['segments']
        if segment['id'] not in {value['id'] for value in keyed_segments.values()}
    ]
    kept_leg_handles = [handle_for_ref(editor, ref) for ref in kept_old_leg_refs]
    finalize_route_source_adoption(
        editor, source_context, item_handle=item_handle, route_ref=route_ref,
        stop_handles=stop_handles, segment_handles=segment_handles,
        leg_handles=leg_handles, removed_refs=removed_refs)
    retire_handles(editor, removed_refs)

    editor.parts['reason'] = reason
    editor.parts['stops'] = stop_handles
    editor.parts['segments'] = segment_handles
    editor.parts['legs'] = leg_handles
    editor.parts['kept'] = {
        'items': [item_handle], 'routes': [handle_for_ref(editor, route_ref)],
        'stops': kept_stop_handles, 'segments': kept_segment_handles,
        'legs': kept_leg_handles,
    }
    stop_count = len(old_stop_refs)
    segment_count = len(old_segment_refs)
    editor.parts['removed'] = {
        'stops': removed_handles[:stop_count],
        'segments': removed_handles[stop_count:stop_count + segment_count],
        'legs': removed_handles[stop_count + segment_count:],
    }
    editor.parts['created'] = {
        'stops': list(stop_handles.values()),
        'segments': list(segment_handles.values()),
        'legs': list(leg_handles.values()),
    }
    editor.parts['interval_replacement'] = {
        'from': editor.handle(from_stop), 'to': editor.handle(to_stop),
        'removed': copy.deepcopy(editor.parts['removed']),
        'created': copy.deepcopy(editor.parts['created']),
    }
    if summary_fields:
        editor.parts['cleared_summary_fields'] = summary_fields
    if item.get('timing', {'kind': 'unknown'}) != {'kind': 'unknown'}:
        editor.parts.setdefault('review', []).append({
            'code': 'ROUTE_TIME_PLAN_REVIEW', 'target': item_handle,
            'message': 'The explicit Item TimePlan was retained and must be reviewed against the new Route.'})
    return item_handle
