"""Read-only geographic projection audit; see MAP_COVERAGE_GUIDE.md.

The portable Python runtime has no JS engine. The bounded projection below is
checked against the real buildHandbook output in web/tests/data/map-coverage.test.ts.
"""
import copy
import json

from .errors import fail

COLLECTIONS = {'place': 'places', 'access_point': 'access_points', 'item': 'items',
               'route': 'routes', 'leg': 'legs', 'journey': 'journeys', 'stay': 'stays',
               'transport_service': 'transport_services', 'path': 'paths',
               'recommendation': 'recommendations', 'day': 'days'}


def ref(kind, record):
    return {'type': kind, 'id': record['id']}


def ref_key(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


class MapAudit:
    def __init__(self, state):
        self.state = state
        self.package = state['package']
        self.index = {kind: {r['id']: r for r in self.package.get(collection, [])}
                      for kind, collection in COLLECTIONS.items()}
        self.handles = {ref_key(value): key for key, value in state['handles'].items()}
        self.rows = []
        self.days = []
        self.related = {kind: set() for kind in COLLECTIONS}

    def handle(self, value):
        name = self.handles.get(ref_key(value))
        if name is None:
            fail('STATE_FORMAT', 'Map report reference has no current workspace handle', reference=value)
        return name

    def record(self, value):
        return self.index[value['type']][value['id']]

    def coordinates(self, record):
        location = record.get('location')
        if not location:
            return {'status': 'missing', 'meaning': 'precision_unknown'}
        precision = location['precision']
        return {'status': 'usable' if location['coordinate_system'].upper() == 'WGS84' else 'unsupported_crs',
                'coordinate_system': location['coordinate_system'], 'precision': precision,
                'meaning': {'entrance': 'recorded_entrance', 'building': 'recorded_building',
                            'parcel': 'representative_point', 'area': 'representative_point',
                            'approximate': 'approximate_precision_unknown'}[precision],
                'reality_verified': False}

    def endpoint(self, value):
        record = self.record(value)
        place = record if value['type'] == 'place' else self.record(record['place_ref'])
        own = self.coordinates(record)
        owner = value if own['status'] == 'usable' else ref('place', place)
        effective = self.coordinates(self.record(owner))
        return {'place': place, 'owner': owner, 'own': own, 'effective': effective,
                'point_id': f"{owner['type']}:{owner['id']}",
                'line_eligible': own['status'] == 'usable'}

    def row(self, day, kind, target, **fields):
        result = {'row_id': f'map:{len(self.rows)}', 'kind': kind,
                  'handle': self.handle(target), 'reference': target,
                  'day': None if day is None else {'id': day['id'], 'handle': self.handle(ref('day', day)), 'date': day['date']},
                  **fields}
        self.rows.append(result)
        return result

    def add_point(self, day, endpoint, via, points, *, kind='selected_place', target=None, scheduled=True):
        resolved = self.endpoint(endpoint)
        place = resolved['place']
        point_id = resolved['point_id']
        points.setdefault(point_id, {'id': point_id, 'place_id': place['id'],
                                    'marker_eligible': resolved['effective']['status'] == 'usable',
                                    'scheduled': False, 'recommendation_ids': []})
        points[point_id]['scheduled'] |= scheduled
        if kind == 'recommendation':
            ids = points[point_id]['recommendation_ids']
            if target['id'] not in ids:
                ids.append(target['id'])
        reasons = []
        if resolved['own']['status'] != 'usable':
            reasons.append('missing_coordinates' if resolved['own']['status'] == 'missing' else 'unsupported_crs')
        if endpoint['type'] == 'access_point' and resolved['owner']['type'] == 'place':
            reasons.append('fallback_to_place')
        if self.record(endpoint).get('links') and resolved['own']['status'] == 'missing':
            reasons.append('links_are_not_coordinates')
        if resolved['effective']['meaning'] == 'representative_point':
            reasons.append('representative_point')
        elif resolved['effective']['meaning'] in {'approximate_precision_unknown', 'precision_unknown'}:
            reasons.append('precision_unknown')
        self.row(day, kind, target or endpoint, via=via, endpoint=endpoint,
                 association='scheduled' if scheduled else 'recommendation',
                 place_id=place['id'], place_handle=self.handle(ref('place', place)),
                 map_point_id=point_id, coordinate_owner_handle=self.handle(resolved['owner']),
                 coordinates=resolved['own'], map_coordinates=resolved['effective'],
                 place_coordinates=self.coordinates(place),
                 marker_eligible=resolved['effective']['status'] == 'usable',
                 reasons=reasons, entrance_requirement='not_assessed')
        self.related['place'].add(place['id'])
        if endpoint['type'] == 'access_point':
            self.related['access_point'].add(endpoint['id'])
        return resolved

    def leg_endpoints(self, leg):
        movement = leg['movement']
        if movement['kind'] == 'scheduled':
            calls = {c['id']: c for c in self.record(movement['service_ref'])['calls']}
            return calls[movement['board_call_id']]['endpoint_ref'], calls[movement['alight_call_id']]['endpoint_ref']
        return movement['from_ref'], movement['to_ref']

    def path_binding(self, day, holder, target, line_id, endpoints=None, suppressed=False):
        path = self.record(holder['path_ref']) if 'path_ref' in holder else None
        reasons = []
        if path:
            self.related['path'].add(path['id'])
            status = 'usable' if path['coordinate_system'].upper() == 'WGS84' else 'unsupported_crs'
            if status != 'usable':
                reasons.append('unsupported_crs')
            if len(path['parts']) > 1:
                reasons.append('continuity_not_assessed')
            line = {'id': line_id, 'source': 'path', 'path_id': path['id'],
                    'kind': 'schematic' if path['kind'] == 'schematic' else 'recorded',
                    'source_kind': path['kind'], 'direction': holder.get('path_direction', 'forward'),
                    'parts': len(path['parts']), 'vertices': sum(map(len, path['parts']))} if status == 'usable' else None
        else:
            status = 'missing'
            reasons.append('missing_path')
            line = {'id': line_id, 'source': 'endpoints', 'kind': 'schematic', 'source_kind': 'schematic',
                    'direction': 'forward', 'parts': 1, 'vertices': 2} if endpoints and all(e['line_eligible'] for e in endpoints) else None
        if suppressed:
            reasons.append('filtered_by_route_path_usage')
        result = self.row(day, 'path_binding', target, path_status=status,
                          path_handle=self.handle(ref('path', path)) if path else None,
                          path_id=path['id'] if path else None,
                          projected_line=line if not suppressed else None,
                          path_details={'kind': path['kind'], 'coordinate_system': path['coordinate_system'],
                                        'parts': len(path['parts']),
                                        'source_handle': self.handle(path['source_ref']) if path.get('source_ref') else None} if path else None,
                          reasons=reasons, navigation_verified=False)
        return result

    def day(self, day):
        start = len(self.rows)
        points = {}
        current_items = [self.record(value) for value in day['item_refs']
                         if self.record(value).get('lifecycle') != 'retired']
        for item in current_items:
            self.related['item'].add(item['id'])
            item_start = len(self.rows)
            item_ref = ref('item', item)
            via = {'item_handle': self.handle(item_ref)}
            if 'place_ref' in item:
                self.add_point(day, item['place_ref'], via, points)
            subject = item.get('subject_ref', {})
            if item['kind'] == 'stay_action' and subject.get('type') == 'stay':
                stay = self.record(subject)
                if stay['lodging_ref']['type'] == 'place':
                    self.add_point(day, stay['lodging_ref'], via, points)
                else:
                    self.row(day, 'item', item_ref, reasons=['non_place_lodging_not_projected'], place_requirement='not_assessed')
            if subject.get('type') == 'journey':
                for leg_ref in self.record(subject)['leg_refs']:
                    leg = self.record(leg_ref)
                    ends = [self.add_point(day, end, {**via, 'leg_handle': self.handle(leg_ref), 'side': side}, points)
                            for side, end in zip(('from', 'to'), self.leg_endpoints(leg))]
                    self.path_binding(day, leg, leg_ref, f"leg:{leg['id']}", ends)
            if item['kind'] == 'route' and subject.get('type') == 'route':
                route = self.record(subject)
                if route.get('lifecycle') == 'retired':
                    self.row(day, 'route', subject, reasons=['filtered_retired'], via=via)
                    continue
                self.related['route'].add(route['id'])
                ends = {}
                for stop in route['stops']:
                    target = {'owner': subject, 'kind': 'stop', 'id': stop['id']}
                    ends[stop['id']] = self.add_point(day, stop['endpoint_ref'], via, points, kind='stop', target=target)
                    self.rows[-1]['encounter_kind'] = stop.get('encounter_kind', 'unknown')
                overview = self.record(route['path_ref']) if 'path_ref' in route else None
                overview_selected = bool(overview and overview['coordinate_system'].upper() == 'WGS84'
                                         and route.get('path_usage') != 'segments')
                if overview:
                    self.path_binding(day, route, subject, f"{route['id']}:overview",
                                      suppressed=route.get('path_usage') == 'segments')
                for segment in route['segments']:
                    target = {'owner': subject, 'kind': 'segment', 'id': segment['id']}
                    holder = self.record(segment['leg_ref']) if 'leg_ref' in segment else segment
                    self.path_binding(day, holder, target, f"{route['id']}:{segment['id']}",
                                      [ends[segment['from_stop_id']], ends[segment['to_stop_id']]], overview_selected)
            if len(self.rows) == item_start:
                self.row(day, 'item', item_ref, reasons=['no_map_point_binding'], place_requirement='not_assessed')
        item_ids = {item['id'] for item in current_items}
        for recommendation in self.index['recommendation'].values():
            if not any((r['type'] == 'day' and r['id'] == day['id']) or
                       (r['type'] == 'item' and r['id'] in item_ids)
                       for r in recommendation.get('related_refs', [])):
                continue
            self.related['recommendation'].add(recommendation['id'])
            self.add_point(day, recommendation['place_ref'], {}, points, kind='recommendation',
                           target=ref('recommendation', recommendation), scheduled=False)
        place_ids = {p['place_id'] for p in points.values()}
        endpoint_ids = {r['endpoint']['id'] for r in self.rows[start:] if r.get('endpoint', {}).get('type') == 'access_point'}
        for access in self.index['access_point'].values():
            if access['place_ref']['id'] not in place_ids:
                continue
            self.related['access_point'].add(access['id'])
            coordinates = self.coordinates(access)
            reasons = [] if access['id'] in endpoint_ids else ['not_used_as_map_endpoint']
            if coordinates['status'] != 'usable':
                reasons.append('missing_coordinates' if coordinates['status'] == 'missing' else 'unsupported_crs')
            self.row(day, 'access_point', ref('access_point', access), place_id=access['place_ref']['id'],
                     place_handle=self.handle(access['place_ref']), coordinates=coordinates,
                     declared_kind=access['kind'], endpoint_used=access['id'] in endpoint_ids,
                     reasons=reasons,
                     entrance_requirement='not_assessed')
        rows = self.rows[start:]
        for row in rows:
            if 'map_point_id' in row:
                row['map_point_scheduled'] = points[row['map_point_id']]['scheduled']
                accesses = [a for a in self.index['access_point'].values() if a['place_ref']['id'] == row['place_id']]
                row['access_point_information'] = {
                    'records': len(accesses),
                    'status': 'no_access_point_record' if not accesses else 'recorded_not_verified',
                    'usable_entrance_coordinates': sum(self.coordinates(a)['status'] == 'usable'
                        and a['location']['precision'] == 'entrance' for a in accesses)}
        lines = {row['projected_line']['id']: row['projected_line'] for row in rows if row.get('projected_line')}
        self.days.append({'id': day['id'], 'handle': self.handle(ref('day', day)), 'date': day['date'],
                          **summarize(rows), 'map_points': len(points),
                          'eligible_markers': sum(p['marker_eligible'] for p in points.values()),
                          'projected_lines': len(lines),
                          'point_coverage': 'complete' if points and all(p['marker_eligible'] for p in points.values()) else 'gaps' if points else 'no_related_points'})

    def inventory(self):
        for kind in ('place', 'recommendation', 'route', 'access_point', 'path', 'item'):
            for record in self.index[kind].values():
                if record['id'] in self.related[kind]:
                    continue
                reasons = ['no_day_association']
                if record.get('lifecycle') == 'retired':
                    reasons.append('filtered_retired')
                if kind == 'recommendation' and any(r['type'] == 'item' and self.record(r).get('lifecycle') == 'retired'
                                                     for r in record.get('related_refs', [])):
                    reasons.append('related_item_retired')
                details = {'coordinates': self.coordinates(record)} if kind in {'place', 'access_point'} else {}
                if kind == 'path':
                    details = {'path_kind': record['kind'], 'coordinate_system': record['coordinate_system'],
                               'parts': len(record['parts']), 'navigation_verified': False}
                self.row(None, kind, ref(kind, record), reasons=reasons, **details)
                if kind == 'route':
                    for stop in record['stops']:
                        self.row(None, 'stop', {'owner': ref('route', record), 'kind': 'stop', 'id': stop['id']},
                                 reasons=reasons, endpoint=stop['endpoint_ref'])


def summarize(rows):
    points = [r for r in rows if 'map_point_id' in r]
    pairs = {(r['day']['id'], r['place_id']) for r in points}
    scheduled = [r for r in points if r['association'] == 'scheduled']
    recommendations = [r for r in points if r['kind'] == 'recommendation']
    return {'unique_places': len({p for _, p in pairs}), 'place_day_associations': len(pairs),
            'point_occurrences': len(points),
            'selected_unique_places': len({r['place_id'] for r in scheduled}),
            'selected_place_day_associations': len({(r['day']['id'], r['place_id']) for r in scheduled}),
            'recommendation_unique_places': len({r['place_id'] for r in recommendations}),
            'recommendation_place_day_associations': len({(r['day']['id'], r['place_id']) for r in recommendations}),
            'recommendation_day_records': len(recommendations)}


def read_map_coverage(state, selection=None, limit=None, cursor=None, include_source_text=False):
    from .core import _normalize_selection, _cursor, _cursor_offset, READ_DEFAULT_LIMIT, READ_MAX_LIMIT
    if not state['package']:
        fail('MISSING_TRIP', 'Define a Trip before requesting map coverage')
    if include_source_text or (selection is not None and (not isinstance(selection, dict) or set(selection) - {'day'})):
        fail('INVALID_ARGUMENT', 'map-coverage accepts only day, limit and cursor', parameter='report')
    normalized = _normalize_selection(state, selection)
    limit = READ_DEFAULT_LIMIT if limit is None else limit
    if type(limit) is not int or not 1 <= limit <= READ_MAX_LIMIT:
        fail('INVALID_ARGUMENT', f'limit must be from 1 through {READ_MAX_LIMIT}', parameter='limit')
    scope = {'report': 'map-coverage', **normalized}
    offset = 0 if cursor is None else _cursor_offset(cursor, scope, state)
    audit = MapAudit(state)
    for day in sorted(state['package']['days'], key=lambda d: (d['date'], d['id'])):
        audit.day(day)
    audit.inventory()
    rows = audit.rows
    days = audit.days
    if 'day' in normalized:
        rows = [row for row in rows if row['day'] and row['day']['handle'] == normalized['day']]
        days = [day for day in days if day['handle'] == normalized['day']]
    if offset > len(rows):
        fail('CURSOR_INVALID', 'Cursor offset is outside the report', parameter='cursor')
    page = rows[offset:offset + limit]
    end = offset + len(page)
    next_cursor = _cursor(scope, state, end) if end < len(rows) else None
    return copy.deepcopy({'report': 'map-coverage', 'report_version': 1,
        'workspace_id': state['workspace_id'], 'revision': state['revision'],
        'schema_version': state['package']['schema_version'], 'scope': scope,
        'evidence': {'layer': 'current_state_projection', 'sdk_rendering': 'not_assessed',
                     'network': 'not_assessed', 'navigation': 'not_verified', 'entrance_requirement': 'not_assessed'},
        'summary': {**summarize(rows), 'unassociated_rows': sum(r['day'] is None for r in rows)},
        'days': days, 'rows': page,
        'pagination': {'limit': limit, 'returned': len(page), 'total': len(rows),
                       'has_more': next_cursor is not None, 'next_cursor': next_cursor}})
