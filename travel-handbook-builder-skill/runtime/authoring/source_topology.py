"""Candidate R13 source identity and Route topology adoption protocol.

The adapter is deliberately attached to typed Route writes.  The caller names
source identities; the Route proposal itself is derived from the records that
the typed operation creates.  This module is authoring-workspace metadata and
does not extend the frozen domain schema.
"""
import copy

from .errors import fail, nonempty


ABSENT = {'state': 'not_present'}
IDENTITY_TYPES = {
    'trip', 'item', 'place', 'task', 'issue', 'route', 'journey',
    'stop', 'segment', 'leg',
}


def _require_candidate_version(editor):
    if editor.package.get('schema_version') not in {'1.0'}:
        fail('SCHEMA_VERSION_UNSUPPORTED',
             'Candidate source identity adoption requires schema version 1.0',
             supported_version='1.0')


def _store(editor):
    # Imported lazily so routes -> source_topology does not form a module cycle
    # with source_refresh -> routes.
    from .source_refresh import store
    return store(editor)


def _locate(editor, anchor):
    from .source_refresh import locate
    return locate(editor, anchor)


def _identity(data, document_key, semantic_key):
    return next((value for value in data['identity_index'].values()
                 if value['document_key'] == document_key
                 and value['semantic_key'] == semantic_key), None)


def _identities_for_target(data, document_key, object_type, target_ref):
    return [value for value in data['identity_index'].values()
            if value['document_key'] == document_key
            and value['object_type'] == object_type
            and value['target_ref'] == target_ref]


def _object_type(target_ref):
    return target_ref.get('type', target_ref.get('kind'))


def _handle_for_ref(editor, target_ref):
    handle = next((handle for handle, stored in editor.state['handles'].items()
                   if stored == target_ref), None)
    if handle is None:
        fail('REFERENCE_NOT_FOUND',
             'The active source identity target has no current workspace handle',
             target_ref=copy.deepcopy(target_ref))
    return {'handle': handle}


def _bind_identity(editor, *, document_key, semantic_key, object_type,
                   occurrence_role, target_ref, anchor, outcomes):
    data = _store(editor)
    found = _identity(data, document_key, semantic_key)
    if found is not None:
        if found['status'] != 'active':
            fail('SOURCE_IDENTITY_HISTORY_CONFLICT',
                 'A tombstoned source identity cannot be recreated or redirected',
                 document_key=document_key, semantic_key=semantic_key,
                 identity_id=found['id'], status=found['status'],
                 historical_target_ref=copy.deepcopy(found['target_ref']))
        expected = {
            'object_type': object_type,
            'occurrence_role': occurrence_role,
            'target_ref': target_ref,
        }
        mismatches = {key: {'stored': copy.deepcopy(found[key]),
                            'proposed': copy.deepcopy(value)}
                      for key, value in expected.items() if found[key] != value}
        if mismatches:
            fail('SOURCE_IDENTITY_CONFLICT',
                 'Source identity type, occurrence and target are immutable',
                 document_key=document_key, semantic_key=semantic_key,
                 identity_id=found['id'], mismatches=mismatches)
        outcomes['reused'].append(found['id'])
        return found

    target_bindings = _identities_for_target(
        data, document_key, object_type, target_ref)
    if target_bindings:
        fail('SOURCE_IDENTITY_CONFLICT',
             'A source object target cannot acquire a different semantic key',
             document_key=document_key, semantic_key=semantic_key,
             object_type=object_type, target_ref=copy.deepcopy(target_ref),
             existing=[{'identity_id': value['id'],
                        'semantic_key': value['semantic_key'],
                        'status': value['status']}
                       for value in target_bindings])
    identifier = 'identity-' + editor.allocate_id()
    found = {
        'id': identifier,
        'document_key': document_key,
        'semantic_key': semantic_key,
        'object_type': object_type,
        'occurrence_role': occurrence_role,
        'target_ref': copy.deepcopy(target_ref),
        'status': 'active',
        'first_anchor': copy.deepcopy(anchor),
    }
    data['identity_index'][identifier] = found
    outcomes['created'].append(identifier)
    return found


def bind_target_identity(editor, *, document_key, anchor, semantic_key,
                         target, occurrence=None, expected_type=None):
    """Bind one active target or validate/reuse its existing source identity."""
    nonempty(semantic_key, 'semantic_key')
    if expected_type is not None:
        nonempty(expected_type, 'expected_type')
        if expected_type not in IDENTITY_TYPES:
            fail('INVALID_ARGUMENT', 'Unsupported source identity type',
                 parameter='expected_type')
    target_handle = editor.handle(target)
    target_ref = editor.ref(target_handle)
    object_type = _object_type(target_ref)
    if object_type not in IDENTITY_TYPES:
        fail('UNSUPPORTED_VARIANT',
             'This object type is outside the bounded source identity protocol',
             target_type=object_type)
    if expected_type is not None and expected_type != object_type:
        fail('REFERENCE_KIND_MISMATCH',
             'Source identity target has the wrong business type',
             expected_type=expected_type, target_type=object_type)
    data = _store(editor)
    found = _identity(data, document_key, semantic_key)
    outcomes = {'created': [], 'reused': []}
    if found is None:
        nonempty(occurrence, 'occurrence')
        found = _bind_identity(
            editor, document_key=document_key, semantic_key=semantic_key,
            object_type=object_type, occurrence_role=occurrence,
            target_ref=target_ref, anchor=anchor, outcomes=outcomes)
        outcome = 'created'
    else:
        if found['status'] != 'active':
            fail('SOURCE_IDENTITY_HISTORY_CONFLICT',
                 'A tombstoned source identity has no current writable handle',
                 document_key=document_key, semantic_key=semantic_key,
                 identity_id=found['id'], status=found['status'],
                 historical_target_ref=copy.deepcopy(found['target_ref']))
        if expected_type is not None and found['object_type'] != expected_type:
            fail('SOURCE_IDENTITY_CONFLICT',
                 'Source identity type is immutable',
                 document_key=document_key, semantic_key=semantic_key,
                 stored_type=found['object_type'], expected_type=expected_type)
        if (found['object_type'] != object_type
                or found['target_ref'] != target_ref
                or (occurrence is not None
                    and found['occurrence_role'] != occurrence)):
            fail('SOURCE_IDENTITY_CONFLICT',
                 'Source identity type, occurrence and target are immutable',
                 document_key=document_key, semantic_key=semantic_key,
                 identity_id=found['id'],
                 stored={'object_type': found['object_type'],
                         'occurrence': found['occurrence_role'],
                         'target_ref': copy.deepcopy(found['target_ref'])},
                 proposed={'object_type': object_type,
                           'occurrence': occurrence,
                           'target_ref': copy.deepcopy(target_ref)})
        outcome = 'reused'
    return found, target_handle, outcome


def source_identity_bind(editor, *, anchor, semantic_key, target=None,
                         occurrence=None, expected_type=None):
    """Create one source identity or obtain the current handle for an existing key."""
    _require_candidate_version(editor)
    snapshot, normalized_anchor = _locate(editor, anchor)
    data = _store(editor)
    found = _identity(data, snapshot['document_key'], semantic_key)
    if found is not None and target is None:
        if found['status'] != 'active':
            fail('SOURCE_IDENTITY_HISTORY_CONFLICT',
                 'A tombstoned source identity has no current writable handle',
                 document_key=snapshot['document_key'], semantic_key=semantic_key,
                 identity_id=found['id'], status=found['status'],
                 historical_target_ref=copy.deepcopy(found['target_ref']))
        if expected_type is not None:
            nonempty(expected_type, 'expected_type')
            if found['object_type'] != expected_type:
                fail('SOURCE_IDENTITY_CONFLICT',
                     'Source identity type is immutable',
                     document_key=snapshot['document_key'], semantic_key=semantic_key,
                     stored_type=found['object_type'], expected_type=expected_type)
        handle = _handle_for_ref(editor, found['target_ref'])
        outcome = 'reused'
    else:
        if target is None:
            fail('INVALID_ARGUMENT',
                 'First source identity binding requires target and occurrence',
                 parameter='target')
        found, handle, outcome = bind_target_identity(
            editor, document_key=snapshot['document_key'],
            anchor=normalized_anchor, semantic_key=semantic_key,
            target=target, occurrence=occurrence, expected_type=expected_type)
    editor.parts['identity_id'] = found['id']
    editor.parts['identity_outcome'] = outcome
    editor.parts['document_key'] = snapshot['document_key']
    editor.parts['semantic_key'] = semantic_key
    return handle


def _preflight_new_identity(data, document_key, semantic_key, object_type,
                            target_ref=None):
    found = _identity(data, document_key, semantic_key)
    if found is None:
        if target_ref is not None:
            target_bindings = _identities_for_target(
                data, document_key, object_type, target_ref)
            if target_bindings:
                fail('SOURCE_IDENTITY_CONFLICT',
                     'A source object target cannot acquire a different semantic key',
                     document_key=document_key, semantic_key=semantic_key,
                     object_type=object_type, target_ref=copy.deepcopy(target_ref),
                     existing=[value['semantic_key'] for value in target_bindings])
        return
    if found['status'] != 'active':
        fail('SOURCE_IDENTITY_HISTORY_CONFLICT',
             'A tombstoned source identity cannot be recreated or redirected',
             document_key=document_key, semantic_key=semantic_key,
             identity_id=found['id'], status=found['status'],
             historical_target_ref=copy.deepcopy(found['target_ref']))
    if (target_ref is not None and found['object_type'] == object_type
            and found['target_ref'] == target_ref):
        return
    fail('SOURCE_IDENTITY_CONFLICT',
         'A newly created execution object cannot reuse an active semantic key',
         document_key=document_key, semantic_key=semantic_key,
         identity_id=found['id'], object_type=object_type,
         historical_target_ref=copy.deepcopy(found['target_ref']))


def _descriptor(value, required, optional, parameter):
    if (not isinstance(value, dict) or not required <= set(value)
            or set(value) - required - optional):
        fail('INVALID_ARGUMENT',
             'Source identity descriptor has missing or unrecognized fields',
             parameter=parameter)
    for key in required:
        nonempty(value[key], f'{parameter}.{key}')
    for key in optional & set(value):
        nonempty(value[key], f'{parameter}.{key}')
    return copy.deepcopy(value)


def _normalize_adoption(editor, source_adoption, stop_inputs, segment_inputs):
    if (not isinstance(source_adoption, dict)
            or set(source_adoption) != {'anchor', 'route_key', 'stops', 'segments'}):
        fail('INVALID_ARGUMENT',
             'source_adoption requires anchor, route_key, stops and segments',
             parameter='source_adoption')
    nonempty(source_adoption['route_key'], 'source_adoption.route_key')
    stops = source_adoption['stops']
    segments = source_adoption['segments']
    if any(not isinstance(value, dict) or not {'key', 'place'} <= set(value)
           for value in stop_inputs):
        fail('INVALID_ARGUMENT',
             'Typed Stop inputs must have key and place before source identity mapping',
             parameter='interior_stops')
    if any(not isinstance(value, dict) or 'key' not in value for value in segment_inputs):
        fail('INVALID_ARGUMENT',
             'Typed Segment inputs must have a key before source identity mapping',
             parameter='segments')
    if not isinstance(stops, dict) or set(stops) != {value['key'] for value in stop_inputs}:
        fail('INVALID_ARGUMENT',
             'source_adoption.stops must map every and only typed Stop local key',
             parameter='source_adoption.stops')
    if (not isinstance(segments, dict)
            or set(segments) != {value['key'] for value in segment_inputs}):
        fail('INVALID_ARGUMENT',
             'source_adoption.segments must map every and only typed Segment local key',
             parameter='source_adoption.segments')

    normalized_stops = {}
    place_targets = {}
    for index, value in enumerate(stop_inputs):
        key = value.get('key')
        descriptor = _descriptor(
            stops[key], {'semantic_key', 'place_key'}, set(),
            f'source_adoption.stops.{key}')
        normalized_stops[key] = descriptor
        place_targets[key] = editor.ref(value.get('place'), {'place'})

    normalized_segments = {}
    for index, value in enumerate(segment_inputs):
        key = value.get('key')
        has_leg = 'leg' in value
        descriptor = _descriptor(
            segments[key], {'semantic_key'} | ({'leg_key'} if has_leg else set()),
            set(), f'source_adoption.segments.{key}')
        if not has_leg and 'leg_key' in descriptor:
            fail('INVALID_ARGUMENT',
                 'leg_key is only valid for a typed leg-backed Segment',
                 parameter=f'source_adoption.segments.{key}.leg_key')
        normalized_segments[key] = descriptor

    snapshot, anchor = _locate(editor, source_adoption['anchor'])
    return {
        'document_key': snapshot['document_key'],
        'source_sequence': snapshot['sequence'],
        'anchor': anchor,
        'route_key': source_adoption['route_key'],
        'stops': normalized_stops,
        'segments': normalized_segments,
        'place_targets': place_targets,
    }


def _active_identity_for(data, document_key, object_type, target_ref,
                         *, conflict_code='SOURCE_IDENTITY_CONFLICT'):
    matches = [value for value in _identities_for_target(
        data, document_key, object_type, target_ref)
        if value['status'] == 'active']
    if len(matches) != 1:
        fail(conflict_code,
             'Current Route topology no longer matches its source identity baseline',
             document_key=document_key, object_type=object_type,
             target_ref=copy.deepcopy(target_ref), active_identity_count=len(matches))
    return matches[0]


def _record(package, collection, target_ref):
    return next((value for value in package.get(collection, [])
                 if value.get('id') == target_ref.get('id')), None)


def _claim_view(package, target):
    active = [claim for claim in package.get('claims', [])
              if claim.get('target') == target
              and claim.get('disposition', 'adopted') == 'adopted']
    if len(active) > 1:
        fail('EVIDENCE_CONFLICT',
             'Multiple adopted statements prevent deterministic source comparison',
             target=copy.deepcopy(target))
    if not active:
        return None
    claim = active[0]
    return {key: copy.deepcopy(claim[key]) for key in
            ('basis', 'statement', 'value', 'source_refs') if key in claim}


def _field_view(package, record, field, target):
    return {
        'present': field in record,
        'value': copy.deepcopy(record.get(field)),
        'evidence': _claim_view(package, target),
    }


def _route_snapshot(editor, binding, *, conflict_code='SOURCE_IDENTITY_CONFLICT'):
    package = editor.package
    data = _store(editor)
    document_key = binding['document_key']
    route_ref = binding['route_ref']
    item_ref = binding['item_ref']
    route = _record(package, 'routes', route_ref)
    item = _record(package, 'items', item_ref)
    if route is None or item is None:
        fail(conflict_code, 'Source topology owner is no longer current')

    stop_refs = [{'owner': copy.deepcopy(route_ref), 'kind': 'stop', 'id': value['id']}
                 for value in route['stops']]
    stop_identities = {
        ref['id']: _active_identity_for(data, document_key, 'stop', ref,
                                        conflict_code=conflict_code)
        for ref in stop_refs
    }
    segment_refs = [
        {'owner': copy.deepcopy(route_ref), 'kind': 'segment', 'id': value['id']}
        for value in route['segments']]
    segment_identities = {
        ref['id']: _active_identity_for(data, document_key, 'segment', ref,
                                        conflict_code=conflict_code)
        for ref in segment_refs
    }
    place_identities = {}
    for stop in route['stops']:
        endpoint = stop['endpoint_ref']
        object_type = endpoint['type']
        if object_type != 'place':
            fail(conflict_code,
                 'Candidate Route source adoption currently supports Place endpoints only')
        place_identities[(object_type, endpoint['id'])] = _active_identity_for(
            data, document_key, object_type, endpoint, conflict_code=conflict_code)

    aspects = {}
    topology_segments = []
    for segment in route['segments']:
        identity = segment_identities[segment['id']]
        leg_key = None
        if 'leg_ref' in segment:
            leg_identity = _active_identity_for(
                data, document_key, 'leg', segment['leg_ref'],
                conflict_code=conflict_code)
            leg_key = leg_identity['semantic_key']
        topology_segments.append({
            'semantic_key': identity['semantic_key'],
            'from_stop_key': stop_identities[segment['from_stop_id']]['semantic_key'],
            'to_stop_key': stop_identities[segment['to_stop_id']]['semantic_key'],
            **({'leg_key': leg_key} if leg_key is not None else {}),
        })
    aspects['topology'] = {
        'stops': [stop_identities[value['id']]['semantic_key'] for value in route['stops']],
        'segments': topology_segments,
    }
    aspects['item.timing'] = _field_view(
        package, item, 'timing', {'object_ref': item_ref, 'field': 'timing'})
    aspects['item.place_ref'] = _field_view(
        package, item, 'place_ref', {'object_ref': item_ref, 'field': 'place_ref'})

    for place_identity in sorted(place_identities.values(), key=lambda value: value['semantic_key']):
        target_ref = place_identity['target_ref']
        place = _record(package, 'places', target_ref)
        aspects[f"place:{place_identity['semantic_key']}.location"] = _field_view(
            package, place, 'location', {'object_ref': target_ref, 'field': 'location'})

    for stop in route['stops']:
        stop_ref = {'owner': copy.deepcopy(route_ref), 'kind': 'stop', 'id': stop['id']}
        identity = stop_identities[stop['id']]
        place_identity = place_identities[(stop['endpoint_ref']['type'],
                                           stop['endpoint_ref']['id'])]
        aspects[f"stop:{identity['semantic_key']}.place"] = {
            'place_key': place_identity['semantic_key']}
        aspects[f"stop:{identity['semantic_key']}.dwell"] = _field_view(
            package, stop, 'dwell',
            {'object_ref': route_ref, 'local_ref': stop_ref, 'field': 'dwell'})

    for segment in route['segments']:
        segment_ref = {'owner': copy.deepcopy(route_ref), 'kind': 'segment',
                       'id': segment['id']}
        identity = segment_identities[segment['id']]
        prefix = f"segment:{identity['semantic_key']}"
        aspects[prefix + '.execution'] = {
            key: copy.deepcopy(segment[key]) for key in
            ('mode', 'mode_label', 'distance_m') if key in segment}
        aspects[prefix + '.path'] = _field_view(
            package, segment, 'path_ref',
            {'object_ref': route_ref, 'local_ref': segment_ref,
             'field': 'path_ref'})
        if 'path_direction' in segment:
            aspects[prefix + '.path']['path_direction'] = copy.deepcopy(
                segment['path_direction'])
        aspects[prefix + '.duration'] = _field_view(
            package, segment, 'duration',
            {'object_ref': route_ref, 'local_ref': segment_ref, 'field': 'duration'})
        if 'leg_ref' in segment:
            leg_identity = _active_identity_for(
                data, document_key, 'leg', segment['leg_ref'],
                conflict_code=conflict_code)
            leg = _record(package, 'legs', segment['leg_ref'])
            movement = copy.deepcopy(leg.get('movement', {}))
            timing = movement.pop('timing', ABSENT)
            aspects[f"leg:{leg_identity['semantic_key']}.movement"] = {
                **{key: copy.deepcopy(leg[key]) for key in ('mode', 'mode_label')
                   if key in leg},
                'movement': movement,
            }
            aspects[f"leg:{leg_identity['semantic_key']}.timing"] = {
                'present': timing != ABSENT,
                'value': copy.deepcopy(None if timing == ABSENT else timing),
                'evidence': _claim_view(
                    package, {'object_ref': segment['leg_ref'], 'field': 'timing'}),
            }
    return aspects


def sync_topology_field_baseline(editor, target_ref, aspect):
    """Move only the topology guard aspect justified by one field adoption."""
    data = _store(editor)
    updates = []
    for binding in data['topology_bindings'].values():
        route = _record(editor.package, 'routes', binding['route_ref'])
        matches = False
        if aspect.startswith('item.'):
            matches = target_ref == binding['item_ref']
        elif target_ref.get('kind') in {'stop', 'segment'}:
            matches = target_ref.get('owner') == binding['route_ref']
        elif target_ref.get('type') == 'place' and route is not None:
            matches = any(stop.get('endpoint_ref') == target_ref
                          for stop in route.get('stops', []))
        elif target_ref.get('type') == 'leg' and route is not None:
            matches = any(segment.get('leg_ref') == target_ref
                          for segment in route.get('segments', []))
        if not matches:
            continue
        current = _route_snapshot(
            editor, binding, conflict_code='SOURCE_ADOPTION_CONFLICT')
        identity = _active_identity_for(
            data, binding['document_key'], _object_type(target_ref), target_ref,
            conflict_code='SOURCE_ADOPTION_CONFLICT')
        if aspect in {'item.timing', 'item.place_ref'}:
            key = aspect
        else:
            field = aspect.split('.', 1)[1]
            key = f"{identity['object_type']}:{identity['semantic_key']}.{field}"
        if key not in current:
            fail('SOURCE_ADOPTION_CONFLICT',
                 'The adopted field is outside the bound Route topology guard',
                 binding_id=binding['id'], aspect=key)
        binding['baseline'][key] = copy.deepcopy(current[key])
        updates.append({'binding_id': binding['id'], 'aspect': key})
    return updates


def _changed_aspects(baseline, current):
    return sorted(key for key in set(baseline) | set(current)
                  if baseline.get(key, ABSENT) != current.get(key, ABSENT))


def prepare_route_source_adoption(editor, source_adoption, *, item_handle,
                                  route_ref, stop_inputs, segment_inputs,
                                  initial=False):
    if source_adoption is None:
        return None
    normalized = _normalize_adoption(
        editor, source_adoption, stop_inputs, segment_inputs)
    data = _store(editor)
    document_key = normalized['document_key']
    route_key = normalized['route_key']
    route_identity = _identity(data, document_key, route_key)
    if initial:
        if route_identity is not None:
            fail('SOURCE_IDENTITY_CONFLICT',
                 'Initial Route adoption requires an unused route semantic key',
                 document_key=document_key, semantic_key=route_key,
                 identity_id=route_identity['id'], status=route_identity['status'])
        normalized['initial'] = True
    else:
        if (route_identity is None or route_identity['status'] != 'active'
                or route_identity['object_type'] != 'route'
                or route_identity['occurrence_role'] != 'route'
                or route_identity['target_ref'] != route_ref):
            fail('SOURCE_IDENTITY_CONFLICT',
                 'Route semantic key does not identify the typed replacement target',
                 document_key=document_key, semantic_key=route_key,
                 route_ref=copy.deepcopy(route_ref))
        binding = data['topology_bindings'].get(route_identity['id'])
        if binding is None or binding['item_ref'] != editor.ref(item_handle, {'item'}):
            fail('SOURCE_IDENTITY_CONFLICT',
                 'Route semantic key has no matching topology binding',
                 document_key=document_key, semantic_key=route_key)
        current = _route_snapshot(
            editor, binding, conflict_code='SOURCE_ADOPTION_CONFLICT')
        changed = _changed_aspects(binding['baseline'], current)
        if changed:
            fail('SOURCE_ADOPTION_CONFLICT',
                 'Current values or evidence differ from the last source topology write',
                 binding_id=binding['id'], changed_aspects=changed,
                 baseline=copy.deepcopy(binding['baseline']), current=current)
        normalized['initial'] = False
        normalized['binding_id'] = binding['id']

    # Newly created Stops/Segments/Legs need unused keys.  Place keys may reuse
    # an active identity only when they point to that exact Place target.
    for key, descriptor in normalized['stops'].items():
        _preflight_new_identity(
            data, document_key, descriptor['semantic_key'], 'stop')
        place_ref = normalized['place_targets'][key]
        _preflight_new_identity(
            data, document_key, descriptor['place_key'], place_ref['type'], place_ref)
    for descriptor in normalized['segments'].values():
        _preflight_new_identity(
            data, document_key, descriptor['semantic_key'], 'segment')
        if 'leg_key' in descriptor:
            _preflight_new_identity(
                data, document_key, descriptor['leg_key'], 'leg')
    return normalized


def _tombstone(editor, removed_refs, *, source_context=None):
    data = editor.state.get('source_imports')
    if not data or not data.get('identity_index'):
        return []
    removed = []
    for identity in data['identity_index'].values():
        if identity['status'] != 'active' or identity['target_ref'] not in removed_refs:
            continue
        identity['status'] = 'tombstoned'
        identity['tombstone'] = {
            'revision': editor.state['revision'] + 1,
            **({'document_sequence': source_context['source_sequence'],
                'anchor': copy.deepcopy(source_context['anchor'])}
               if source_context is not None else {'cause': 'typed_replacement'}),
        }
        removed.append(identity['id'])
    return removed


def tombstone_removed_identities(editor, removed_refs):
    """Retire pure source identities after any legal typed replacement."""
    tombstoned = _tombstone(editor, removed_refs)
    if tombstoned:
        editor.parts['source_identity_tombstones'] = tombstoned
    return tombstoned


def _record_history(editor, binding, aspects, context):
    data = _store(editor)
    histories = data['proposal_history'].setdefault(binding['id'], {})
    proposed = copy.deepcopy(aspects)
    # Detect a return to any earlier distinct proposal before changing history.
    for key, value in proposed.items():
        entries = histories.get(key, [])
        if (entries and entries[-1]['value'] != value
                and any(entry['value'] == value for entry in entries[:-1])):
            fail('SOURCE_PROPOSAL_HISTORY_CONFLICT',
                 'A higher source sequence cannot automatically restore an older proposal',
                 binding_id=binding['id'], aspect=key,
                 document_sequence=context['source_sequence'],
                 current=copy.deepcopy(entries[-1]['value']),
                 proposed=copy.deepcopy(value))
    outcomes = {'created': [], 'changed': [], 'unchanged': []}
    for key in sorted(proposed):
        value = proposed[key]
        entries = histories.get(key, [])
        if not entries:
            outcome = 'created'
        elif entries[-1]['value'] == value:
            outcome = 'unchanged'
        else:
            outcome = 'changed'
        histories.setdefault(key, []).append({
            'proposal_sequence': binding.get('proposal_sequence', 0) + 1,
            'document_sequence': context['source_sequence'],
            'anchor': copy.deepcopy(context['anchor']),
            'value': copy.deepcopy(value),
            'outcome': outcome,
        })
        outcomes[outcome].append(key)
    binding['proposal_sequence'] = binding.get('proposal_sequence', 0) + 1
    return outcomes


def finalize_route_source_adoption(editor, context, *, item_handle, route_ref,
                                   stop_handles, segment_handles, leg_handles,
                                   removed_refs=()):
    if context is None:
        tombstone_removed_identities(editor, list(removed_refs))
        return None
    data = _store(editor)
    outcomes = {'created': [], 'reused': [], 'tombstoned': []}
    route_identity = _bind_identity(
        editor, document_key=context['document_key'],
        semantic_key=context['route_key'], object_type='route',
        occurrence_role='route', target_ref=copy.deepcopy(route_ref),
        anchor=context['anchor'], outcomes=outcomes)

    for key, descriptor in context['stops'].items():
        stop_handle = stop_handles[key]
        stop_ref = editor.ref(stop_handle)
        stop = editor.record(stop_handle)
        place_ref = stop['endpoint_ref']
        _bind_identity(
            editor, document_key=context['document_key'],
            semantic_key=descriptor['place_key'], object_type=place_ref['type'],
            occurrence_role='place', target_ref=place_ref,
            anchor=context['anchor'], outcomes=outcomes)
        _bind_identity(
            editor, document_key=context['document_key'],
            semantic_key=descriptor['semantic_key'], object_type='stop',
            occurrence_role=key, target_ref=stop_ref,
            anchor=context['anchor'], outcomes=outcomes)

    for key, descriptor in context['segments'].items():
        segment_handle = segment_handles[key]
        _bind_identity(
            editor, document_key=context['document_key'],
            semantic_key=descriptor['semantic_key'], object_type='segment',
            occurrence_role=key, target_ref=editor.ref(segment_handle),
            anchor=context['anchor'], outcomes=outcomes)
        if 'leg_key' in descriptor:
            _bind_identity(
                editor, document_key=context['document_key'],
                semantic_key=descriptor['leg_key'], object_type='leg',
                occurrence_role=key, target_ref=editor.ref(leg_handles[key]),
                anchor=context['anchor'], outcomes=outcomes)

    outcomes['tombstoned'] = _tombstone(
        editor, list(removed_refs), source_context=context)

    item_ref = editor.ref(item_handle, {'item'})
    if context['initial']:
        binding = {
            'id': 'topology-' + editor.allocate_id(),
            'document_key': context['document_key'],
            'route_key': context['route_key'],
            'route_identity_id': route_identity['id'],
            'route_ref': copy.deepcopy(route_ref),
            'item_ref': copy.deepcopy(item_ref),
        }
        data['topology_bindings'][route_identity['id']] = binding
    else:
        binding = data['topology_bindings'][route_identity['id']]
    aspects = _route_snapshot(editor, binding)
    # Topology history is an explicit typed topology proposal.  Other scanned
    # values remain a guard baseline and are recorded only by source.field.*
    # when the caller actually submits them.
    aspect_outcomes = _record_history(
        editor, binding, {'topology': aspects['topology']}, context)
    binding['baseline'] = copy.deepcopy(aspects)
    binding['last_anchor'] = copy.deepcopy(context['anchor'])
    binding['last_document_sequence'] = context['source_sequence']

    created = set(outcomes['created'])
    retained = [identity['id'] for identity in data['identity_index'].values()
                if identity['document_key'] == context['document_key']
                and identity['status'] == 'active'
                and identity['id'] not in created
                and identity['id'] not in outcomes['reused']]
    editor.parts['source_adoption'] = {
        'candidate_protocol': 'route-topology-source-adoption-1',
        'binding_id': binding['id'],
        'document_key': context['document_key'],
        'document_sequence': context['source_sequence'],
        'route_key': context['route_key'],
        'identities': {**outcomes, 'retained': retained},
        'aspects': aspect_outcomes,
    }
    return binding
