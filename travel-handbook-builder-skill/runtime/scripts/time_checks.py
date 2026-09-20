"""Shared finite time parsing and diagnostics for 1.0 packages."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _pointer(parts):
    return '/' + '/'.join(str(part).replace('~', '~0').replace('/', '~1') for part in parts)


def _offset_minutes(value):
    sign = -1 if value.startswith('-') else 1
    hours, minutes = value[1:].split(':')
    return sign * (int(hours) * 60 + int(minutes))


def resolve_zoned(value):
    """Return a unique UTC instant or a stable diagnostic reason."""
    if not isinstance(value, dict) or not isinstance(value.get('local'), str) or not isinstance(value.get('timezone'), str):
        return None, 'TIME_VALUE_INVALID'
    try:
        local = datetime.fromisoformat(value['local'])
        zone = ZoneInfo(value['timezone'])
    except (ValueError, ZoneInfoNotFoundError):
        return None, 'TIME_VALUE_INVALID'
    if local.tzinfo is not None:
        return None, 'TIME_VALUE_INVALID'
    candidates = {}
    for fold in (0, 1):
        try:
            aware = local.replace(tzinfo=zone, fold=fold)
            instant = aware.astimezone(timezone.utc)
            if instant.astimezone(zone).replace(tzinfo=None) == local:
                candidates[(instant, aware.utcoffset())] = aware
        except (OverflowError, ValueError):
            continue
    if not candidates:
        return None, 'TIME_LOCAL_NONEXISTENT'
    offset = value.get('offset')
    if offset is None and len(candidates) > 1:
        return None, 'TIME_OFFSET_REQUIRED'
    if offset is not None:
        wanted = _offset_minutes(offset)
        matches = [aware for aware in candidates.values()
                   if aware.utcoffset() == timedelta(minutes=wanted)]
        if not matches:
            return None, 'TIME_OFFSET_MISMATCH'
        aware = matches[0]
    else:
        aware = next(iter(candidates.values()))
    return aware.astimezone(timezone.utc), None


def _explicit_boundary(timing, field):
    """Return (ZonedDateTime, certainty) without following relations."""
    if not isinstance(timing, dict) or field not in timing:
        return None, 'unknown'
    value = timing[field]
    if timing.get('kind') == 'boundaries':
        if isinstance(value, dict) and value.get('kind') == 'unknown':
            return None, 'unknown'
        if isinstance(value, dict) and value.get('kind') == 'estimated':
            return value.get('value'), 'estimated'
        return value, 'exact'
    if timing.get('kind') == 'fixed':
        return value, 'exact'
    if timing.get('kind') == 'estimated':
        return value, 'estimated'
    return None, 'unknown'


def _unknown():
    return {'instant': None, 'certainty': 'unknown'}


class BoundaryResolver:
    """Evaluate only documented time dependencies, at boundary-node granularity."""

    def __init__(self, package):
        self.package = package
        self.objects = {}
        self.paths = {}
        for collection, kind in (
                ('items', 'item'), ('activities', 'activity'), ('legs', 'leg'),
                ('journeys', 'journey'), ('routes', 'route'),
                ('transport_services', 'transport_service')):
            for index, record in enumerate(package.get(collection, [])):
                key = (kind, record['id'])
                self.objects[key] = record
                self.paths[key] = f'/{collection}/{index}'
        self.cache = {}
        self.duration_cache = {}
        self.edges = {}
        self.errors = []
        self._error_keys = set()

    @staticmethod
    def _key(ref, field):
        return (ref.get('type'), ref.get('id'), field)

    def _path(self, ref, suffix='/timing'):
        return self.paths.get((ref.get('type'), ref.get('id')), '') + suffix

    def _error(self, code, path, message, **details):
        marker = (code, path)
        if marker not in self._error_keys:
            self._error_keys.add(marker)
            self.errors.append({'code': code, 'path': path, 'message': message, **details})

    def _edge(self, target, dependent):
        self.edges.setdefault(target, set()).add(dependent)

    def _zoned_result(self, value, certainty):
        instant, reason = resolve_zoned(value)
        return _unknown() if reason is not None else {'instant': instant, 'certainty': certainty}

    def _call_time(self, value):
        if not isinstance(value, dict) or value.get('kind') == 'unknown':
            return _unknown()
        if value.get('kind') == 'estimated':
            return self._zoned_result(value.get('value'), 'estimated')
        return self._zoned_result(value, 'exact')

    def boundary(self, ref, field, active=()):
        key = self._key(ref, field)
        if key in self.cache:
            return self.cache[key]
        if key in active:
            self._error('TIME_DEPENDENCY_CYCLE', self._path(ref),
                        'Time boundary evaluation contains a cycle.',
                        dependency_path=[{'type': kind, 'id': identifier, 'field': boundary}
                                         for kind, identifier, boundary in active + (key,)])
            return _unknown()
        record = self.objects.get((ref.get('type'), ref.get('id')))
        if record is None:
            return _unknown()
        next_active = active + (key,)
        kind = ref['type']
        if kind in {'item', 'activity'}:
            result = self._time_plan_boundary(ref, record.get('timing', {}), field, next_active)
        elif kind == 'leg':
            result = self._leg_boundary(ref, record, field, next_active)
        elif kind == 'journey':
            refs = record.get('leg_refs', [])
            target = refs[0] if field == 'start' and refs else refs[-1] if refs else None
            result = self._dependent_boundary(key, target, field, next_active)
        elif kind == 'route':
            segments = record.get('segments', [])
            segment = segments[0] if field == 'start' and segments else segments[-1] if segments else None
            target = segment.get('leg_ref') if isinstance(segment, dict) else None
            stops = record.get('stops', [])
            edge_stop = stops[0] if field == 'start' and stops else stops[-1] if stops else None
            dwell = edge_stop.get('dwell') if isinstance(edge_stop, dict) else None
            if (not isinstance(dwell, dict) or dwell.get('min_minutes') != 0
                    or dwell.get('max_minutes') != 0):
                result = _unknown()
            else:
                result = self._dependent_boundary(key, target, field, next_active)
        else:
            result = _unknown()
        self.cache[key] = result
        return result

    def _dependent_boundary(self, dependent_key, target, field, active):
        if not isinstance(target, dict):
            return _unknown()
        target_key = self._key(target, field)
        self._edge(target_key, dependent_key)
        return self.boundary(target, field, active)

    def _time_plan_boundary(self, owner_ref, timing, field, active):
        value, certainty = _explicit_boundary(timing, field)
        if value is not None:
            return self._zoned_result(value, certainty)
        dependent_key = self._key(owner_ref, field)
        if timing.get('kind') == 'derived':
            return self._dependent_boundary(dependent_key, timing.get('from_ref'), field, active)
        if field != 'end':
            return _unknown()
        relation = timing.get('end_from_ref')
        if isinstance(relation, dict):
            target = relation.get('ref')
            if target == {'type': owner_ref.get('type'), 'id': owner_ref.get('id')}:
                self._error('TIME_SELF_REFERENCE', self._path(owner_ref) + '/end_from_ref',
                            'end_from_ref cannot target another boundary of the same object.')
                return _unknown()
            target_key = self._key(target or {}, relation.get('field'))
            self._edge(target_key, dependent_key)
            projected = self.boundary(target or {}, relation.get('field'), active)
            if projected['instant'] is None:
                return _unknown()
            try:
                instant = projected['instant'] + timedelta(minutes=relation['offset_minutes'])
            except (OverflowError, TypeError):
                return _unknown()
            return {'instant': instant, 'certainty': projected['certainty']}
        if 'duration' in timing or 'duration_from_ref' in timing:
            start_key = self._key(owner_ref, 'start')
            self._edge(start_key, dependent_key)
            start = self.boundary(owner_ref, 'start', active)
            duration = self._duration_from_timing(timing, active, dependent_key)
            if start['instant'] is None or duration is None:
                return _unknown()
            try:
                instant = start['instant'] + timedelta(minutes=duration)
            except OverflowError:
                return _unknown()
            return {'instant': instant, 'certainty': 'estimated'}
        return _unknown()

    def _leg_boundary(self, ref, leg, field, active):
        movement = leg.get('movement', {})
        if movement.get('kind') == 'independent':
            return self._time_plan_boundary(ref, movement.get('timing', {}), field, active)
        if movement.get('kind') != 'scheduled':
            return _unknown()
        service_ref = movement.get('service_ref', {})
        service = self.objects.get((service_ref.get('type'), service_ref.get('id')))
        if service is None:
            return _unknown()
        call_id = movement.get('board_call_id') if field == 'start' else movement.get('alight_call_id')
        call_field = 'departure' if field == 'start' else 'arrival'
        call = next((value for value in service.get('calls', []) if value.get('id') == call_id), None)
        return self._call_time(call.get(call_field)) if call and call_field in call else _unknown()

    def _duration_from_timing(self, timing, active, dependent_key=None):
        value = timing.get('duration')
        if isinstance(value, dict) and value.get('min_minutes') == value.get('max_minutes'):
            return value['min_minutes']
        ref = timing.get('duration_from_ref')
        if not isinstance(ref, dict):
            return None
        duration_key = self._key(ref, 'duration')
        if dependent_key is not None:
            self._edge(duration_key, dependent_key)
        return self.duration(ref, active)

    def duration(self, ref, active=()):
        key = self._key(ref, 'duration')
        if key in self.duration_cache:
            return self.duration_cache[key]
        if key in active:
            self._error('TIME_DEPENDENCY_CYCLE', self._path(ref),
                        'Time duration evaluation contains a cycle.',
                        dependency_path=[{'type': kind, 'id': identifier, 'field': boundary}
                                         for kind, identifier, boundary in active + (key,)])
            return None
        record = self.objects.get((ref.get('type'), ref.get('id')))
        if record is None:
            return None
        next_active = active + (key,)
        if ref['type'] == 'activity':
            timing = record.get('timing', {})
            result = self._duration_from_timing(timing, next_active, key)
            if result is None:
                result = self._duration_between(ref, next_active, key)
        elif ref['type'] == 'journey':
            result = self._duration_between(ref, next_active, key)
        elif ref['type'] == 'route':
            result = self._route_duration(record, next_active, key)
        else:
            result = None
        self.duration_cache[key] = result
        return result

    def _duration_between(self, ref, active, dependent_key):
        start_key = self._key(ref, 'start')
        end_key = self._key(ref, 'end')
        self._edge(start_key, dependent_key)
        self._edge(end_key, dependent_key)
        start = self.boundary(ref, 'start', active)
        end = self.boundary(ref, 'end', active)
        if start['instant'] is None or end['instant'] is None:
            return None
        return (end['instant'] - start['instant']).total_seconds() / 60

    def _route_duration(self, route, active, dependent_key):
        total = 0
        for stop in route.get('stops', []):
            dwell = stop.get('dwell')
            if not isinstance(dwell, dict) or dwell.get('min_minutes') != dwell.get('max_minutes'):
                return None
            total += dwell['min_minutes']
        for segment in route.get('segments', []):
            if 'leg_ref' in segment:
                # A Leg-backed segment may include unmodeled waiting before or after
                # execution. Summing its movement time would understate Route duration.
                return None
            else:
                duration = segment.get('duration')
                if not isinstance(duration, dict) or duration.get('min_minutes') != duration.get('max_minutes'):
                    return None
                total += duration['min_minutes']
        return total

    def project_all(self):
        for (kind, identifier) in list(self.objects):
            if kind in {'item', 'activity', 'leg', 'journey', 'route'}:
                ref = {'type': kind, 'id': identifier}
                self.boundary(ref, 'start')
                self.boundary(ref, 'end')
        return self.cache


def item_day_ownership_assessment(package, item_ref, day, resolver=None):
    """Assess one Item start against a Day using the shared boundary resolver."""
    resolver = resolver or BoundaryResolver(package)
    start = resolver.boundary(item_ref, 'start')
    if start['instant'] is None:
        return {'status': 'unknown', 'certainty': start['certainty']}
    projected = start['instant'].astimezone(ZoneInfo(day['timezone'])).date().isoformat()
    return {
        'status': 'matches' if projected == day['date'] else 'mismatch',
        'projected_date': projected,
        'certainty': start['certainty'],
    }


def time_diagnostics(package):
    """Return path-specific semantic errors for all explicit ZonedDateTimes."""
    errors = []

    def walk(value, parts):
        if isinstance(value, dict):
            if {'local', 'timezone'} <= value.keys():
                _, reason = resolve_zoned(value)
                if reason is not None:
                    messages = {
                        'TIME_LOCAL_NONEXISTENT': 'The local time does not exist in the supplied timezone.',
                        'TIME_OFFSET_REQUIRED': 'This local time is ambiguous; provide its explicit offset.',
                        'TIME_OFFSET_MISMATCH': 'The offset is not valid for this local time and timezone.',
                        'TIME_VALUE_INVALID': 'The zoned date-time cannot be resolved.',
                    }
                    errors.append({'code': reason, 'path': _pointer(parts), 'message': messages[reason]})
                return
            for key, child in value.items():
                walk(child, parts + [key])
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, parts + [index])

    walk(package, [])

    timing_records = []
    assessments = []
    for collection, kind in (('items', 'item'), ('activities', 'activity')):
        for index, record in enumerate(package.get(collection, [])):
            timing_records.append((f'/{collection}/{index}/timing',
                                   {'type': kind, 'id': record['id']}))
    for index, leg in enumerate(package.get('legs', [])):
        movement = leg.get('movement', {})
        if movement.get('kind') == 'independent':
            timing_records.append((f'/legs/{index}/movement/timing',
                                   {'type': 'leg', 'id': leg['id']}))
    resolver = BoundaryResolver(package)
    resolver.project_all()
    errors.extend(resolver.errors)
    for path, ref in timing_records:
        start = resolver.boundary(ref, 'start')
        end = resolver.boundary(ref, 'end')
        if start['instant'] is None or end['instant'] is None:
            continue
        if end['instant'] < start['instant']:
            errors.append({
                'code': 'TIME_RANGE_REVERSED',
                'path': path,
                'start_certainty': start['certainty'],
                'end_certainty': end['certainty'],
                'message': 'The end instant is earlier than the start instant.',
            })

    warnings = []
    day_by_item = {}
    for day in package.get('days', []):
        for ref in day.get('item_refs', []):
            if ref.get('type') == 'item':
                day_by_item[ref.get('id')] = day
    unassigned = {ref.get('id') for ref in package.get('trip', {}).get(
        'unassigned_item_refs', []) if ref.get('type') == 'item'}
    for index, item in enumerate(package.get('items', [])):
        if item.get('lifecycle', 'current') != 'current':
            continue
        if item.get('id') not in day_by_item:
            if item.get('id') in unassigned:
                warnings.append({
                    'code': 'TIME_DAY_UNASSIGNED',
                    'path': f'/items/{index}/timing',
                    'item_ref': {'type': 'item', 'id': item['id']},
                    'message': ('The selected Item has no assigned Day; date ownership '
                                'cannot be assessed or inferred.'),
                })
            continue
        day = day_by_item[item['id']]
        item_ref = {'type': 'item', 'id': item['id']}
        assessment = item_day_ownership_assessment(
            package, item_ref, day, resolver=resolver)
        if assessment['status'] == 'unknown':
            warnings.append({
                'code': 'TIME_DAY_OWNERSHIP_UNKNOWN',
                'path': f'/items/{index}/timing',
                'item_ref': {'type': 'item', 'id': item['id']},
                'day_ref': {'type': 'day', 'id': day['id']},
                'message': 'The start boundary is unknown, so Day ownership cannot be checked.',
            })
            continue
        if assessment['status'] == 'mismatch':
            warnings.append({
                'code': 'TIME_DAY_OWNERSHIP_MISMATCH',
                'path': f'/items/{index}/timing/start',
                'item_ref': {'type': 'item', 'id': item['id']},
                'day_ref': {'type': 'day', 'id': day['id']},
                'day_date': day['date'],
                'projected_date': assessment['projected_date'],
                'certainty': assessment['certainty'],
                'message': 'The known start instant falls on a different date in the owning Day timezone.',
            })
    for collection, kind in (('items', 'item'), ('activities', 'activity')):
        for index, record in enumerate(package.get(collection, [])):
            if record.get('lifecycle', 'current') != 'current':
                continue
            timing = record.get('timing', {})
            ref = {'type': kind, 'id': record['id']}
            for number, constraint in enumerate(timing.get('constraints', [])):
                path = f'/{collection}/{index}/timing/constraints/{number}'
                actual = resolver.boundary(ref, constraint['applies_to'])
                reason = None
                if actual['instant'] is None:
                    reason = 'target_boundary_unknown'
                elif actual['certainty'] != 'exact':
                    reason = 'target_boundary_estimated'
                bound = None
                if 'time' in constraint:
                    bound, bound_reason = resolve_zoned(constraint['time'])
                    if bound_reason is not None:
                        reason = reason or 'constraint_time_unresolved'
                else:
                    relative = constraint['relative_to']
                    anchor = resolver.boundary(relative['ref'], relative['field'])
                    if anchor['instant'] is None:
                        reason = reason or 'anchor_boundary_unknown'
                    elif anchor['certainty'] != 'exact':
                        reason = reason or 'anchor_boundary_estimated'
                    else:
                        try:
                            bound = anchor['instant'] + timedelta(minutes=constraint['minutes'])
                        except OverflowError:
                            reason = reason or 'relative_bound_out_of_range'
                if reason is not None or bound is None:
                    assessment = {'target_ref': ref, 'path': path, 'status': 'unknown',
                                  'reason': reason or 'bound_unknown'}
                    assessments.append(assessment)
                    warnings.append({'code': 'TIME_CONSTRAINT_UNKNOWN', **assessment})
                    continue
                matches = {
                    'not_before': actual['instant'] >= bound,
                    'not_after': actual['instant'] <= bound,
                    'before': actual['instant'] < bound,
                    'after': actual['instant'] > bound,
                }
                if not matches[constraint['kind']]:
                    assessment = {'target_ref': ref, 'path': path, 'status': 'violated'}
                    assessments.append(assessment)
                    warnings.append({'code': 'TIME_CONSTRAINT_VIOLATED', **assessment})
                else:
                    assessments.append({'target_ref': ref, 'path': path, 'status': 'satisfied'})
    return errors, warnings, assessments
