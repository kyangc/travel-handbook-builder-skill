"""Bounded typed transport ordering, buffer, and transfer-detail diagnostics."""

from time_checks import BoundaryResolver


def _endpoint(package, leg, boundary):
    movement = leg.get('movement', {})
    if movement.get('kind') == 'independent':
        return movement.get('from_ref' if boundary == 'start' else 'to_ref')
    if movement.get('kind') != 'scheduled':
        return None
    service = next((value for value in package.get('transport_services', [])
                    if value['id'] == movement.get('service_ref', {}).get('id')), None)
    if service is None:
        return None
    call_id = movement.get('board_call_id' if boundary == 'start' else 'alight_call_id')
    call = next((value for value in service.get('calls', []) if value['id'] == call_id), None)
    return call.get('endpoint_ref') if call else None


def _parent_place(package, ref):
    if not isinstance(ref, dict):
        return None
    if ref.get('type') == 'place':
        return ref
    if ref.get('type') != 'access_point':
        return None
    point = next((value for value in package.get('access_points', [])
                  if value['id'] == ref.get('id')), None)
    return point.get('place_ref') if point else None


def _transfer_is_explicit(package, connection, departure_endpoint, arrival_endpoint):
    if (not isinstance(departure_endpoint, dict) or not isinstance(arrival_endpoint, dict)
            or departure_endpoint.get('type') != 'access_point'
            or arrival_endpoint.get('type') != 'access_point'
            or _parent_place(package, departure_endpoint) != _parent_place(package, arrival_endpoint)):
        return False
    return any(step.get('kind') in {'transfer', 'terminal_transfer'}
               and step.get('necessity') != 'not_required'
               and step.get('place_ref') == arrival_endpoint
               for step in connection.get('steps', []))


def transport_diagnostics(package):
    resolver = BoundaryResolver(package)
    resolver.project_all()
    errors, warnings, assessments = [], [], []
    legs = {value['id']: value for value in package.get('legs', [])}

    for index, leg in enumerate(package.get('legs', [])):
        if leg.get('movement', {}).get('kind') != 'scheduled':
            continue
        ref = {'type': 'leg', 'id': leg['id']}
        start, end = resolver.boundary(ref, 'start'), resolver.boundary(ref, 'end')
        if (start['instant'] is not None and end['instant'] is not None
                and start['certainty'] == end['certainty'] == 'exact'
                and end['instant'] < start['instant']):
            errors.append({
                'code': 'LEG_TIME_REVERSED', 'path': f'/legs/{index}/movement',
                'target_ref': ref, 'start_certainty': 'exact', 'end_certainty': 'exact',
                'message': 'The scheduled alight arrival is earlier than the board departure.',
            })

    for jindex, journey in enumerate(package.get('journeys', [])):
        journey_ref = {'type': 'journey', 'id': journey['id']}
        for cindex, connection in enumerate(journey.get('connections', [])):
            path = f'/journeys/{jindex}/connections/{cindex}'
            local_ref = {'owner': journey_ref, 'kind': 'connection', 'id': connection['id']}
            before_ref, after_ref = connection['from_leg_ref'], connection['to_leg_ref']
            before, after = resolver.boundary(before_ref, 'end'), resolver.boundary(after_ref, 'start')
            if (before['instant'] is not None and after['instant'] is not None
                    and after['instant'] < before['instant']):
                errors.append({
                    'code': 'CONNECTION_TIME_REVERSED', 'path': path,
                    'target_ref': local_ref, 'from_certainty': before['certainty'],
                    'to_certainty': after['certainty'],
                    'message': 'The next recorded Leg starts before the preceding Leg ends.',
                })

            assessment = {'kind': 'required_buffer', 'target_ref': local_ref,
                          'path': path + '/required_buffer'}
            required = connection.get('required_buffer')
            if required is None:
                assessment.update(status='unknown', reason='required_buffer_not_recorded')
            elif before['instant'] is None or after['instant'] is None:
                assessment.update(status='unknown', reason='connection_boundary_unknown')
            elif before['certainty'] != 'exact' or after['certainty'] != 'exact':
                assessment.update(status='unknown', reason='connection_boundary_estimated')
            else:
                gap = (after['instant'] - before['instant']).total_seconds() / 60
                assessment['gap_minutes'] = gap
                if gap >= required['max_minutes']:
                    assessment['status'] = 'satisfied'
                elif gap < required['min_minutes']:
                    assessment['status'] = 'violated'
                    warnings.append({
                        'code': 'CONNECTION_BUFFER_VIOLATED', **assessment,
                        'message': 'The exact recorded connection gap is below the explicit required buffer.',
                    })
                else:
                    assessment.update(status='unknown', reason='buffer_interval_indeterminate')
            assessments.append(assessment)

            before_leg, after_leg = legs.get(before_ref['id']), legs.get(after_ref['id'])
            departure_endpoint = _endpoint(package, before_leg or {}, 'end')
            arrival_endpoint = _endpoint(package, after_leg or {}, 'start')
            if (departure_endpoint != arrival_endpoint
                    and not _transfer_is_explicit(package, connection, departure_endpoint, arrival_endpoint)):
                warnings.append({
                    'code': 'JOURNEY_TRANSFER_DETAILS_UNKNOWN', 'path': path,
                    'target_ref': local_ref,
                    'message': 'Adjacent Leg endpoints differ and the explicit transfer details remain incomplete.',
                })

    for rindex, route in enumerate(package.get('routes', [])):
        route_ref = {'type': 'route', 'id': route['id']}
        stops = {value['id']: value for value in route.get('stops', [])}
        for sindex, segment in enumerate(route.get('segments', [])):
            leg_ref = segment.get('leg_ref')
            if not isinstance(leg_ref, dict):
                continue
            leg = legs.get(leg_ref.get('id'))
            if leg is None:
                continue
            actual_from = _endpoint(package, leg, 'start')
            actual_to = _endpoint(package, leg, 'end')
            from_stop, to_stop = stops.get(segment['from_stop_id']), stops.get(segment['to_stop_id'])
            expected_from = from_stop.get('endpoint_ref') if from_stop else None
            expected_to = to_stop.get('endpoint_ref') if to_stop else None
            if actual_from == expected_from and actual_to == expected_to:
                continue
            warnings.append({
                'code': 'ROUTE_LEG_ENDPOINT_REVIEW',
                'path': f'/routes/{rindex}/segments/{sindex}/leg_ref',
                'target_ref': {'owner': route_ref, 'kind': 'segment', 'id': segment['id']},
                'leg_ref': leg_ref,
                'from_stop_ref': {'owner': route_ref, 'kind': 'stop', 'id': segment['from_stop_id']},
                'to_stop_ref': {'owner': route_ref, 'kind': 'stop', 'id': segment['to_stop_id']},
                'actual_from_ref': actual_from, 'actual_to_ref': actual_to,
                'message': 'The Leg endpoints no longer exactly match the connected Route Stop endpoints; Route connection details require review.',
            })
    return errors, warnings, assessments
