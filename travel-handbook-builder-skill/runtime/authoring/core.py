"""Typed authoring actions over the existing model; no natural-language inference."""
import base64
import binascii
import copy
from datetime import date, datetime, timedelta, timezone as utc_timezone
import hashlib
import inspect
import json
from pathlib import Path
import re
import sys
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_trip import validate

FORMAT = 'authoring-first-slice-1'
SUPPORTED_SCHEMA_VERSIONS = ('1.0',)
COLLECTIONS = {
    'day': 'days', 'item': 'items', 'place': 'places',
    'access_point': 'access_points', 'recommendation': 'recommendations',
    'route': 'routes', 'journey': 'journeys', 'leg': 'legs',
    'transport_service': 'transport_services', 'stay': 'stays',
    'activity': 'activities', 'service_use': 'service_uses',
    'vehicle_use': 'vehicle_uses', 'service_bundle': 'service_bundles',
    'task': 'tasks', 'reservation': 'reservations', 'coverage': 'coverages',
    'price_quote': 'price_quotes', 'cost': 'costs', 'payment': 'payments',
    'authorization_hold': 'authorization_holds',
    'exchange_rate': 'exchange_rates', 'source': 'sources', 'claim': 'claims',
    'issue': 'issues', 'media': 'media', 'path': 'paths',
    'guide_note': 'guide_notes',
}

LINK_OWNER_TYPES = frozenset({
    'place', 'access_point', 'transport_service', 'activity', 'service_use',
    'reservation',
})


from .errors import AuthoringError, fail, nonempty
from .availability import meal_availability
from .coordinates import COORDINATE_INPUTS, validate_coordinate_inputs


def set_keys(value):
    return frozenset(value)


def canonical(value):
    try:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        encoded.encode('utf-8')
        return encoded
    except (TypeError, ValueError) as error:
        fail('INVALID_ARGUMENT', f'Input must be finite JSON: {error}')


def place_roles(value):
    if not isinstance(value, list) or not value or not all(isinstance(role, str) for role in value):
        fail('INVALID_ARGUMENT', 'roles must be a nonempty list; omit or clear for unknown classification', parameter='roles')
    # Shared input vocabulary for creation and subsequent classification.
    return ['dining' if role == 'restaurant' else role for role in value]


def flat_links(entries):
    if not isinstance(entries, list) or not entries:
        fail('INVALID_ARGUMENT', 'add_links must be a nonempty list', parameter='add_links')
    result = []
    for index, entry in enumerate(entries):
        path = f'add_links[{index}]'
        if not isinstance(entry, dict) or not {'url', 'label', 'purposes'} <= entry.keys() or entry.keys() - {'key', 'url', 'label', 'purposes', 'platform'}:
            fail('INVALID_ARGUMENT', 'Link needs url, label, purposes; optional key and platform', parameter=path)
        for name in ('url', 'label'):
            nonempty(entry[name], f'{path}.{name}')
        purposes = entry['purposes']
        if not isinstance(purposes, list) or not purposes or any(not isinstance(p, str) or not p.strip() for p in purposes):
            fail('INVALID_ARGUMENT', 'purposes must be a nonempty list of names', parameter=f'{path}.purposes')
        value = {'label': entry['label'], 'purposes': purposes, 'web_url': entry['url']}
        if 'platform' in entry:
            nonempty(entry['platform'], f'{path}.platform')
            value['platform'] = {'id': entry['platform'], 'label': entry['platform']}
        result.append({'action': 'add', 'key': entry.get('key', str(index)), 'value': value})
    return result


def weekly_hours(value, *, root='replace_weekly_hours', allow_empty=False):
    if not isinstance(value, dict) or not {'scope', 'timezone', 'rules'} <= value.keys() or value.keys() - {'scope', 'timezone', 'rules', 'label'}:
        fail('INVALID_ARGUMENT', 'Provide scope, timezone, rules; other scopes also require label', parameter=root)
    if value['scope'] not in ('venue', 'breakfast', 'lunch', 'dinner', 'other'):
        fail('INVALID_ARGUMENT', 'Unknown opening scope', parameter=f'{root}.scope')
    nonempty(value['timezone'], f'{root}.timezone')
    try:
        ZoneInfo(value['timezone'])
    except (ZoneInfoNotFoundError, ValueError):
        fail('INVALID_ARGUMENT', 'Use a valid IANA timezone', parameter=f'{root}.timezone')
    if value['scope'] == 'other':
        nonempty(value.get('label'), f'{root}.label')
    elif 'label' in value:
        fail('INVALID_ARGUMENT', 'label identifies custom other scopes only', parameter=f'{root}.label')
    if not isinstance(value['rules'], list) or (not value['rules'] and not allow_empty):
        fail('INVALID_ARGUMENT', 'rules must be nonempty; missing days remain unspecified', parameter=f'{root}.rules')
    rules, seen_days = [], set()
    weekdays = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    for index, entry in enumerate(value['rules']):
        path = f'{root}.rules[{index}]'
        if not isinstance(entry, dict) or 'days' not in entry or set(entry) - {'days', 'periods', 'all_day', 'closed', 'unknown'}:
            fail('INVALID_ARGUMENT', 'Rule needs days and one of periods/all_day/closed/unknown', parameter=path)
        modes = set(entry) & {'periods', 'all_day', 'closed', 'unknown'}
        if len(modes) != 1:
            fail('INVALID_ARGUMENT', 'Choose exactly one rule form', parameter=path)
        days = entry['days']
        if not isinstance(days, list) or not days or any(not isinstance(d, str) or d not in weekdays for d in days):
            fail('INVALID_ARGUMENT', 'days must list mon/tue/wed/thu/fri/sat/sun', parameter=f'{path}.days')
        if len(set(days)) != len(days) or seen_days.intersection(days):
            fail('INVALID_ARGUMENT', 'Each weekday appears once; combine split hours in periods', parameter=f'{path}.days')
        seen_days.update(days)
        mode = next(iter(modes))
        rule = {'weekdays': [weekdays.index(d) + 1 for d in days], 'state': 'open'}
        if mode != 'periods':
            if entry[mode] is not True:
                fail('INVALID_ARGUMENT', f'{mode} must be true', parameter=f'{path}.{mode}')
            if mode == 'all_day':
                rule['all_day'] = True
            else:
                rule['state'] = mode
        else:
            periods = entry['periods']
            if not isinstance(periods, list) or not periods:
                fail('INVALID_ARGUMENT', 'periods must be nonempty; use closed or unknown explicitly', parameter=f'{path}.periods')
            rule['intervals'] = []
            for offset, period in enumerate(periods):
                interval_path = f'{path}.periods[{offset}]'
                if not isinstance(period, dict) or not {'start', 'end'} <= period.keys() or period.keys() - {'start', 'end', 'next_day'}:
                    fail('INVALID_ARGUMENT', 'Period needs start/end and optional next_day', parameter=interval_path)
                for key in ('start', 'end'):
                    if not isinstance(period[key], str) or re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', period[key]) is None:
                        fail('INVALID_ARGUMENT', 'Use HH:MM in 00:00–23:59; use all_day for 24 hours', parameter=f'{interval_path}.{key}')
                next_day = period.get('next_day', False)
                if type(next_day) is not bool:
                    fail('INVALID_ARGUMENT', 'next_day must be boolean', parameter=f'{interval_path}.next_day')
                if period['end'] == period['start'] and not next_day:
                    fail('INVALID_ARGUMENT', 'Equal times need explicit next_day=true for a 24-hour interval; calendar-day opening uses all_day', parameter=interval_path)
                if period['end'] < period['start'] and not next_day:
                    fail('INVALID_ARGUMENT', 'Overnight hours require next_day=true', parameter=f'{interval_path}.next_day')
                if next_day and period['end'] > period['start']:
                    fail('UNSUPPORTED_VARIANT', 'Periods over 24 hours are not supported', parameter=interval_path)
                rule['intervals'].append({'start': period['start'], 'end': period['end'], 'end_day_offset': int(next_day)})
        rules.append(rule)
    schedule = {'scope': value['scope'], 'timezone': value['timezone'], 'weekly_rules': rules, 'date_overrides': []}
    if value['scope'] == 'other':
        schedule['label'] = value['label']
    return schedule


def closed_days(values, timezone):
    if not isinstance(values, list) or not values:
        fail('INVALID_ARGUMENT', 'closed_dates must list explicit whole local dates', parameter='closed_dates')
    result, seen = [], set()
    for index, value in enumerate(values):
        path = f'closed_dates[{index}]'
        if not isinstance(value, str) or re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value) is None:
            fail('INVALID_ARGUMENT', 'Use YYYY-MM-DD', parameter=path)
        try:
            next_date = (date.fromisoformat(value) + timedelta(days=1)).isoformat()
        except (ValueError, OverflowError):
            fail('INVALID_ARGUMENT', 'Invalid closure date', parameter=path)
        if value in seen:
            fail('INVALID_ARGUMENT', 'Duplicate closure date', parameter=path)
        seen.add(value)
        zone = ZoneInfo(timezone)
        for boundary in (value, next_date):
            local = datetime.fromisoformat(boundary + 'T00:00:00')
            instants = set()
            for fold in (0, 1):
                try:
                    instant = local.replace(tzinfo=zone, fold=fold).astimezone(utc_timezone.utc)
                except OverflowError:
                    fail('UNSUPPORTED_VARIANT', 'Closure boundary is outside the supported absolute date range', parameter=path)
                if instant.astimezone(zone).replace(tzinfo=None) == local:
                    instants.add(instant)
            if len(instants) != 1:
                fail('UNSUPPORTED_VARIANT', 'This local midnight is nonexistent or ambiguous; the tool will not choose an absolute boundary',
                     parameter=path, boundary=boundary, timezone=timezone)
        result.append({'start': {'local': value + 'T00:00:00', 'timezone': timezone},
                       'end': {'local': next_date + 'T00:00:00', 'timezone': timezone}})
    return result


def validate_authored(package):
    report = validate(package)
    if not report['valid']:
        return report
    assessments, warnings = meal_availability(package)
    report['availability_assessments'] = assessments
    report['warnings'].extend(warnings)
    def minutes(clock):
        hour, minute = map(int, clock.split(':'))
        return hour * 60 + minute
    for pindex, place in enumerate(package.get('places', [])):
        for sindex, schedule in enumerate(place.get('availability', [])):
            periods = []
            for rindex, rule in enumerate(schedule['weekly_rules']):
                if rule['state'] != 'open':
                    continue
                intervals = [{'start': '00:00', 'end': '00:00', 'end_day_offset': 1}] if rule.get('all_day') else rule['intervals']
                for day in rule['weekdays']:
                    for iindex, interval in enumerate(intervals):
                        start = (day - 1) * 1440 + minutes(interval['start'])
                        end = (day - 1 + interval['end_day_offset']) * 1440 + minutes(interval['end'])
                        periods.append((start, end, {'rule_index': rindex, 'interval_index': iindex, 'weekday': day}))
            for index, first in enumerate(periods):
                for second in periods[index + 1:]:
                    if any(max(first[0], second[0] + shift) < min(first[1], second[1] + shift) for shift in (-10080, 0, 10080)):
                        report['warnings'].append({'code': 'OPENING_INTERVAL_OVERLAP',
                            'path': f'/places/{pindex}/availability/{sindex}/weekly_rules',
                            'periods': [first[2], second[2]],
                            'message': 'Weekly base periods overlap; retained as supplied. Date exceptions and absolute closures are not evaluated by this diagnostic.'})
    return report


def references_rule(value, owner, identifier):
    if isinstance(value, dict):
        if value.get('kind') == 'availability_rule' and value.get('owner') == owner and value.get('id') == identifier:
            return True
        return any(references_rule(child, owner, identifier) for child in value.values())
    if isinstance(value, list):
        return any(references_rule(child, owner, identifier) for child in value)
    return False


def changed_record_paths(before, after):
    """Attribute diagnostics to related writers, not an invented exact cause."""
    before = before or {}
    paths = []
    if before.get('trip') != after.get('trip'):
        paths.append('/trip')
    for collection in COLLECTIONS.values():
        old = before.get(collection, [])
        for index, record in enumerate(after.get(collection, [])):
            if index >= len(old) or old[index] != record:
                paths.append(f'/{collection}/{index}')
    return paths


def new_workspace(title, *, example=False):
    nonempty(title, 'title')
    if type(example) is not bool:
        fail('INVALID_ARGUMENT', 'example must be boolean')
    return {'format': FORMAT, 'workspace_id': uuid.uuid4().hex, 'revision': 0,
            'title': title, 'example': example, 'package': None, 'handles': {}, 'receipts': {}}


def _domain_records(package):
    """Yield the versioned model's addressable records from explicit owner paths."""
    trip_ref = {'type': 'trip', 'id': package['trip']['id']}
    yield trip_ref, package['trip']
    owners = [('trip', trip_ref, package['trip'])]
    for object_type, collection in COLLECTIONS.items():
        for record in package.get(collection, []):
            ref = {'type': object_type, 'id': record['id']}
            yield ref, record
            owners.append((object_type, ref, record))
    for object_type, owner_ref, owner in owners:
        local_groups = []
        if object_type in LINK_OWNER_TYPES:
            local_groups.append(('link', owner.get('links', [])))
        if object_type == 'route':
            local_groups.extend((('stop', owner.get('stops', [])),
                                 ('segment', owner.get('segments', []))))
        elif object_type == 'journey':
            local_groups.append(('connection', owner.get('connections', [])))
        elif object_type == 'transport_service':
            local_groups.append(('call', owner.get('calls', [])))
        elif object_type == 'stay':
            local_groups.append(('unit', owner.get('units', [])))
        elif object_type == 'service_bundle':
            local_groups.append(('port_call', owner.get('voyage', {}).get('port_calls', [])))
        elif object_type == 'coverage':
            local_groups.append(('scope', owner.get('scopes', [])))
        elif object_type == 'task':
            # Checklist handles are workspace objects rather than model LocalRefs.
            local_groups.append(('checklist', owner.get('checklist', [])))
        elif (object_type == 'trip'
              and package['schema_version'] in {'1.0'}):
            party = owner.get('party', {})
            local_groups.extend((('member', party.get('members', [])),
                                 ('group', party.get('groups', []))))
        if object_type == 'place':
            rules = []
            for schedule in owner.get('availability', []):
                for name in ('weekly_rules', 'date_overrides'):
                    for rule in schedule.get(name, []):
                        rules.append(rule)
                        rules.extend(rule.get('cutoffs', []))
            local_groups.append(('availability_rule', rules))
        for kind, records in local_groups:
            for record in records:
                yield {'owner': copy.deepcopy(owner_ref), 'kind': kind,
                       'id': record['id']}, record


def _register_handle(handles, ref):
    existing = next((handle for handle, stored in handles.items() if stored == ref), None)
    if existing is not None:
        return existing
    handle = 'h-' + ref['id']
    if handle in handles and handles[handle] != ref:
        handle = 'h-local-' + hashlib.sha256(canonical(ref).encode()).hexdigest()[:20]
        sequence = 0
        while handle in handles and handles[handle] != ref:
            sequence += 1
            handle = 'h-ref-' + hashlib.sha256(
                (canonical(ref) + ':' + str(sequence)).encode()).hexdigest()[:20]
    handles[handle] = copy.deepcopy(ref)
    return handle


def import_package(package):
    """Create a new authoring workspace from a complete canonical package."""
    if not isinstance(package, dict):
        fail('INVALID_ARGUMENT', 'package must be a JSON object', parameter='package')
    canonical(package)
    if package.get('schema_version') not in SUPPORTED_SCHEMA_VERSIONS:
        fail('UNSUPPORTED_SCHEMA_VERSION', 'Import accepts only a currently supported schema version',
             schema_version=package.get('schema_version'))
    validation = validate_authored(package)
    if not validation['valid']:
        fail('MODEL_VALIDATION', 'Package is not valid', errors=validation['errors'])
    imported = copy.deepcopy(package)
    handles = {}
    for ref, _ in _domain_records(imported):
        _register_handle(handles, ref)
    state = {
        'format': FORMAT,
        'workspace_id': uuid.uuid4().hex,
        'revision': imported['revision'],
        'title': imported['trip']['title'],
        'example': imported['example'],
        'package': imported,
        'handles': handles,
        'receipts': {},
        'import_report': {
            'recovery_mode': 'canonical_package',
            'preserved': ['all canonical domain values', 'revision',
                          'current and retired arrangements', 'Source, Claim, Issue and GuideNote records'],
            'unavailable_authoring_metadata': [
                'receipts', 'source_imports', 'issue_resolutions'],
            'source_recovery': 'new source.register calls create new snapshots; existing citations remain domain evidence',
        },
    }
    check_workspace(state)
    return state


def check_workspace(state):
    if not isinstance(state, dict) or state.get('format') != FORMAT:
        fail('STATE_FORMAT', 'Not a supported authoring workspace')
    if type(state.get('revision')) is not int or state['revision'] < 0:
        fail('STATE_FORMAT', 'Invalid workspace revision')
    if not all(key in state for key in ('workspace_id', 'title', 'example', 'package', 'handles', 'receipts')):
        fail('STATE_FORMAT', 'Workspace fields missing')
    if not isinstance(state['workspace_id'], str) or not isinstance(state['handles'], dict) or not isinstance(state['receipts'], dict):
        fail('STATE_FORMAT', 'Invalid workspace metadata')
    if state['package'] is not None and (not isinstance(state['package'], dict) or state['package'].get('revision') != state['revision']):
        fail('STATE_FORMAT', 'Package and workspace revision differ')


def check(state):
    check_workspace(state)
    if state['package'] is None:
        return {'valid': False, 'errors': [{'code': 'MISSING_TRIP', 'path': '',
                'message': 'Define dates and timezone before export'}], 'warnings': [], 'scope': 'trip readiness'}
    return validate_authored(state['package'])


def coverage_projection_fields(package):
    if package and package.get('schema_version') in ('1.0',):
        from .coverage_revisions import coverage_projection
        return {'coverage_projection': coverage_projection(package)}
    return {}


def budget_projection_fields(package):
    if package and package.get('schema_version') in ('1.0',):
        from .money import budget_projection
        return {'budget_projection': budget_projection(package)}
    return {}


READ_DEFAULT_LIMIT = 50
READ_MAX_LIMIT = 100
LOCAL_READ_TYPES = frozenset({
    'unit', 'stop', 'segment', 'call', 'link', 'connection',
    'availability_rule', 'scope', 'port_call', 'member', 'group', 'checklist',
})


def _handle_name(value, parameter):
    if isinstance(value, str) and value:
        return value
    if (isinstance(value, dict) and set(value) == {'handle'}
            and isinstance(value['handle'], str) and value['handle']):
        return value['handle']
    fail('INVALID_ARGUMENT', 'Expected a stable handle string or handle object',
         parameter=parameter)


def _normalize_selection(state, selection):
    if selection is None:
        selection = {}
    if not isinstance(selection, dict) or selection.keys() - {'day', 'types', 'handles'}:
        fail('INVALID_ARGUMENT', 'selection accepts day, types and handles only',
             parameter='selection')
    result = {}
    if 'day' in selection:
        day = _handle_name(selection['day'], 'selection.day')
        ref = state['handles'].get(day)
        if ref is None:
            fail('REFERENCE_NOT_FOUND', 'selection.day requires a current Day handle, not a date or name',
                 parameter='selection.day',
                 recovery_hint='Read with types=["day"], follow pagination, then use the returned handle whose record.date matches your intended day.')
        if ref.get('type') != 'day':
            fail('REFERENCE_KIND_MISMATCH', 'selection.day must identify a Day',
                 parameter='selection.day', actual_type=ref.get('type', ref.get('kind')),
                 recovery_hint='Read with types=["day"], then select a returned Day handle.')
        result['day'] = day
    if 'types' in selection:
        values = selection['types']
        supported = {'trip', *COLLECTIONS.keys(), *LOCAL_READ_TYPES}
        if (not isinstance(values, list) or not values
                or any(not isinstance(value, str) or value not in supported for value in values)):
            fail('INVALID_ARGUMENT', 'selection.types must be a nonempty list of supported object types',
                 parameter='selection.types')
        result['types'] = sorted(set(values))
    if 'handles' in selection:
        values = selection['handles']
        if not isinstance(values, list) or not values:
            fail('INVALID_ARGUMENT', 'selection.handles must be a nonempty list',
                 parameter='selection.handles')
        handles = sorted(set(_handle_name(value, f'selection.handles[{index}]')
                             for index, value in enumerate(values)))
        missing = [handle for handle in handles if handle not in state['handles']]
        if missing:
            fail('REFERENCE_NOT_FOUND', 'Selected handle is not in this workspace',
                 parameter='selection.handles', handles=missing)
        result['handles'] = handles
    return result


def _handle_for_ref(state, ref):
    return next((handle for handle, stored in state['handles'].items() if stored == ref), None)


def _day_selection_handles(state, day_handle):
    package = state['package']
    day_ref = state['handles'][day_handle]
    day = resolve_record(package, day_ref)
    selected = {day_handle}

    def include_ref(ref):
        handle = _handle_for_ref(state, ref)
        if handle is None:
            fail('STATE_FORMAT', 'A selected Day dependency has no workspace handle')
        selected.add(handle)
        return handle

    for item_ref in day.get('item_refs', []):
        include_ref(item_ref)
        item = resolve_record(package, item_ref)
        subject_ref = item.get('subject_ref')
        if not isinstance(subject_ref, dict) or subject_ref.get('type') not in {'journey', 'route'}:
            continue
        include_ref(subject_ref)
        subject = resolve_record(package, subject_ref)
        if subject_ref['type'] == 'journey':
            for leg_ref in subject.get('leg_refs', []):
                include_ref(leg_ref)
            child_kinds = {'connection'}
        else:
            for segment in subject.get('segments', []):
                if 'leg_ref' in segment:
                    include_ref(segment['leg_ref'])
            child_kinds = {'stop', 'segment'}
        for handle, ref in state['handles'].items():
            if ref.get('owner') == subject_ref and ref.get('kind') in child_kinds:
                selected.add(handle)
    return selected


def _cursor(selection, state, offset):
    payload = {'version': 1, 'workspace_id': state['workspace_id'],
               'revision': state['revision'], 'selection': selection, 'offset': offset}
    return base64.urlsafe_b64encode(canonical(payload).encode()).decode().rstrip('=')


def _cursor_offset(cursor, selection, state):
    if not isinstance(cursor, str) or not cursor:
        fail('CURSOR_INVALID', 'Cursor is malformed or no longer valid', parameter='cursor')
    try:
        padded = cursor + '=' * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except (ValueError, UnicodeError, json.JSONDecodeError, binascii.Error):
        fail('CURSOR_INVALID', 'Cursor is malformed or no longer valid', parameter='cursor')
    expected = {'version': 1, 'workspace_id': state['workspace_id'],
                'revision': state['revision'], 'selection': selection}
    if (not isinstance(payload, dict) or set(payload) != {*expected, 'offset'}
            or any(payload.get(key) != value for key, value in expected.items())
            or type(payload.get('offset')) is not int or payload['offset'] < 0):
        fail('CURSOR_INVALID', 'Cursor does not match this workspace, revision, or selection',
             parameter='cursor')
    return payload['offset']


def _direct_handle_links(state, entries):
    found = {}

    def walk(value):
        if isinstance(value, dict):
            if set(value) in ({'type', 'id'}, {'owner', 'kind', 'id'}):
                handle = _handle_for_ref(state, value)
                if handle is not None:
                    found[canonical(value)] = {'reference': copy.deepcopy(value), 'handle': handle}
                return
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for entry in entries:
        walk(entry['record'])
        owner_ref = state['handles'][entry['handle']]
        for handle, ref in state['handles'].items():
            if ref.get('owner') == owner_ref:
                found[canonical(ref)] = {'reference': copy.deepcopy(ref), 'handle': handle}
    return [found[key] for key in sorted(found)]


def read_workspace(state, selection=None, limit=None, cursor=None,
                   include_source_text=False, report=None, include_capabilities=True):
    """Small first-slice read surface; handles survive process restarts."""
    check_workspace(state)
    if type(include_capabilities) is not bool:
        fail('INVALID_ARGUMENT', 'include_capabilities must be boolean', parameter='include_capabilities')
    if report is not None:
        if report != 'map-coverage':
            fail('INVALID_ARGUMENT', 'Unknown read report; supported: map-coverage', parameter='report')
        from .map_coverage import read_map_coverage
        return read_map_coverage(state, selection, limit, cursor, include_source_text)
    local_mode = (selection is not None or limit is not None or cursor is not None
                  or include_source_text is not False)
    objects = []
    package = state['package']
    for handle, ref in state['handles'].items():
        record = resolve_record(package, ref)
        entry = {'handle': handle, 'type': ref.get('type', ref.get('kind')), 'record': record}
        if 'owner' in ref:
            owner_handle = next((h for h, value in state['handles'].items() if value == ref['owner']), None)
            if owner_handle is None:
                fail('STATE_FORMAT', 'Stored local owner cannot be resolved')
            entry['owner'] = {'handle': owner_handle}
        if (package and package.get('schema_version') == '1.0'
                and ref.get('type') == 'item'):
            if record.get('lifecycle', 'current') == 'retired':
                entry['ownership'] = {'kind': 'retired'}
            elif ref in package['trip'].get('unassigned_item_refs', []):
                entry['ownership'] = {'kind': 'unassigned'}
            else:
                day = next((value for value in package.get('days', [])
                            if ref in value.get('item_refs', [])), None)
                day_ref = {'type': 'day', 'id': day['id']} if day is not None else None
                day_handle = next((h for h, value in state['handles'].items()
                                   if value == day_ref), None)
                if day_handle is None:
                    fail('STATE_FORMAT', 'Current Item ownership cannot be resolved')
                entry['ownership'] = {'kind': 'day', 'day': {'handle': day_handle}}
        objects.append(entry)
    full = {'revision': state['revision'], 'schema_version': package.get('schema_version') if package else None,
        'title': state['title'], 'objects': objects,
        'capabilities': {'schema_versions': list(SUPPORTED_SCHEMA_VERSIONS), 'new_trip_schema_version': '1.0',
            'write_methods': sorted(METHODS),
            'read_reports': {'map-coverage': {
                'filters': ['day'], 'default_limit': READ_DEFAULT_LIMIT, 'max_limit': READ_MAX_LIMIT,
                'read_only': True, 'scope': 'current_state_projection_not_sdk_or_network',
                'guide': 'authoring/MAP_COVERAGE_GUIDE.md'}},
            'day_weather': {'add_parameter': 'weather_location',
                            'canonical_field': 'weather_location_ref',
                            'update_field': 'weather_location',
                            'target_types': ['place', 'access_point'],
                            'clear_field': 'weather_location',
                            'automatic_location_selection': False,
                            'guide': 'authoring/WEATHER_GUIDE.md'},
            'coordinate_inputs': COORDINATE_INPUTS, 'batch': 'atomic', 'concurrency': 'single_writer',
            'recovery': {'state': 'full_authoring_context',
                         'canonical_package_import': 'domain_values_without_authoring_metadata'},
            'bounded_read': {'default_limit': READ_DEFAULT_LIMIT,
                             'max_limit': READ_MAX_LIMIT,
                             'filters': ['day', 'types', 'handles'],
                             'day_expands': ['item', 'journey', 'leg', 'connection',
                                             'route', 'stop', 'segment']},
            'preview': {'engine': 'apply', 'commits': False,
                        'conflicts': 'diagnostic_only'},
            'unsupported': ['markdown_parsing', 'general_source_refresh',
                            'unknown_trip_dates', 'candidate_arrangements',
                            'retired_arrangement_restore',
                            'route_split', 'path_file_parsing', 'path_coordinate_conversion',
                            'path_reverse_binding', 'external_booking_execution',
                            'owned_vehicle_replacement', 'vehicle_rental_workflow',
                            'vehicle_energy_and_charging',
                            'reservation_updates', 'entitlement_alternative_use',
                            'fine_grained_partial_revocation', 'ticket_credentials_and_seats',
                            'payments', 'public_export']}}
    if not local_mode:
        full.update(coverage_projection_fields(package))
        full.update(budget_projection_fields(package))
        full['source_imports'] = {
            key: value for key, value in state.get('source_imports', {}).items()
            if key != 'signing_key'}
    if 'import_report' in state:
        full['import_report'] = state['import_report']
    if not local_mode:
        if not include_capabilities:
            full.pop('capabilities')
        return copy.deepcopy(full)
    if type(include_source_text) is not bool:
        fail('INVALID_ARGUMENT', 'include_source_text must be boolean',
             parameter='include_source_text')
    normalized = _normalize_selection(state, selection)
    if limit is None:
        limit = READ_DEFAULT_LIMIT
    if type(limit) is not int or not 1 <= limit <= READ_MAX_LIMIT:
        fail('INVALID_ARGUMENT', f'limit must be an integer from 1 through {READ_MAX_LIMIT}',
             parameter='limit')
    allowed = set(state['handles'])
    if 'day' in normalized:
        allowed &= _day_selection_handles(state, normalized['day'])
    if 'types' in normalized:
        allowed &= {entry['handle'] for entry in objects
                    if entry['type'] in normalized['types']}
    if 'handles' in normalized:
        allowed &= set(normalized['handles'])
    ordered = sorted((entry for entry in objects if entry['handle'] in allowed),
                     key=lambda entry: canonical(state['handles'][entry['handle']]))
    offset = 0 if cursor is None else _cursor_offset(cursor, normalized, state)
    if offset > len(ordered):
        fail('CURSOR_INVALID', 'Cursor offset is outside the selected result', parameter='cursor')
    page = ordered[offset:offset + limit]
    next_offset = offset + len(page)
    next_cursor = (_cursor(normalized, state, next_offset)
                   if next_offset < len(ordered) else None)
    result = {
        'workspace_id': state['workspace_id'],
        'revision': state['revision'],
        'schema_version': package.get('schema_version') if package else None,
        'selection': normalized,
        'pagination': {'limit': limit, 'returned': len(page),
                       'has_more': next_cursor is not None, 'next_cursor': next_cursor},
        'objects': page,
        'related_handles': _direct_handle_links(state, page),
        'capabilities': full['capabilities'],
    }
    if 'import_report' in state:
        result['import_report'] = state['import_report']
    if include_source_text:
        explicitly_selected = set(normalized.get('handles', []))
        explicitly_selected_sources = {
            handle for handle in explicitly_selected
            if state['handles'][handle].get('type') == 'source'}
        source_handles = {entry['handle'] for entry in page if entry['type'] == 'source'}
        if not explicitly_selected_sources:
            fail('INVALID_ARGUMENT',
                 'Source text requires explicit Source handles in selection.handles',
                 parameter='include_source_text')
        snapshots = state.get('source_imports', {}).get('snapshots', {}).values()
        result['source_texts'] = [copy.deepcopy(snapshot) for snapshot in snapshots
                                  if snapshot.get('source', {}).get('handle') in source_handles]
    if not include_capabilities:
        result.pop('capabilities')
    return copy.deepcopy(result)


def export_package(state, *, revision):
    check_workspace(state)
    if type(revision) is not int or revision != state['revision']:
        fail('REVISION_CONFLICT', 'Read current revision before exporting', current_revision=state['revision'])
    if state['package'] is None:
        fail('MISSING_TRIP', 'Dates and timezone are required before exporting a trip')
    validation = validate_authored(state['package'])
    if not validation['valid']:
        fail('MODEL_VALIDATION', 'Package is not valid', errors=validation['errors'])
    return {'package': copy.deepcopy(state['package']), 'validation': validation,
            **coverage_projection_fields(state['package']),
            **budget_projection_fields(state['package']),
            'manifest': {'audience': 'private', 'revision': revision,
                         'source_coverage': 'not_assessed',
                         'checks_not_run': ['source interpretation', 'full travel feasibility', 'web rendering']}}


def protect_place_role_details(editor, place_ref, before, after):
    """Do not overwrite adopted evidence on a changed role-details subtree."""
    if before == after:
        return

    missing = object()

    def value_at(details, path):
        value = details
        for part in path:
            if not isinstance(value, dict) or part not in value:
                return missing
            value = value[part]
        return value

    blockers = []
    for claim in editor.package.get('claims', []):
        target = claim.get('target', {})
        field = target.get('field', '')
        if (target.get('object_ref') != place_ref or 'local_ref' in target
                or claim.get('disposition', 'adopted') != 'adopted'
                or not (field == 'role_details' or field.startswith('role_details.'))):
            continue
        path = field.split('.')[1:]
        if value_at(before, path) != value_at(after, path):
            blockers.append({'type': 'claim', 'id': claim['id']})
    if blockers:
        fail('PLACE_ROLE_DETAILS_CHANGE_BLOCKED',
             'Adopted role-details evidence must be handled before changing its field',
             target_ref=copy.deepcopy(place_ref), blocker_refs=blockers)


def edit_fields(record, *, changes, clear, append_note, allowed, clearable):
    changes = {} if changes is None else changes
    clear = [] if clear is None else clear
    if not isinstance(changes, dict) or not isinstance(clear, list) or not all(isinstance(k, str) for k in clear):
        fail('INVALID_ARGUMENT', 'set must be an object and clear a list of field names')
    if not changes and not clear and append_note is None:
        fail('INVALID_ARGUMENT', 'At least one explicit change is required')
    if changes.keys() - allowed or frozenset(clear) - clearable:
        fail('FIELD_NOT_EDITABLE', 'This method cannot edit the requested fields')
    if changes.keys() & frozenset(clear) or (append_note is not None and ('notes' in changes or 'notes' in clear)):
        fail('CONFLICTING_EDIT', 'Do not set, clear, and append the same field together')
    record.update(copy.deepcopy(changes))
    for field in clear:
        record.pop(field, None)
    if append_note is not None:
        nonempty(append_note, 'append_note')
        record['notes'] = record['notes'] + '\n' + append_note if record.get('notes') else append_note


def resolve_record(package, ref):
    if package is None:
        fail('STATE_FORMAT', 'Handle exists without a trip')
    if 'owner' in ref:
        owner = resolve_record(package, ref['owner'])
        kind = ref.get('kind')
        collection = {'scope': 'scopes', 'unit': 'units', 'link': 'links', 'stop': 'stops',
                      'segment': 'segments', 'connection': 'connections', 'call': 'calls',
                      'checklist': 'checklist'}.get(kind)
        if kind in {'member', 'group'}:
            records = owner.get('party', {}).get(kind + 's', [])
        elif kind == 'port_call':
            records = owner.get('voyage', {}).get('port_calls', [])
        elif kind == 'availability_rule':
            rules = [rule for schedule in owner.get('availability', [])
                     for name in ('weekly_rules', 'date_overrides')
                     for rule in schedule.get(name, [])]
            records = rules + [cutoff for rule in rules for cutoff in rule.get('cutoffs', [])]
        elif collection is None:
            fail('STATE_FORMAT', 'Stored local kind is not supported')
        else:
            records = owner.get(collection, [])
    else:
        records = [package['trip']] if ref.get('type') == 'trip' else package.get(COLLECTIONS.get(ref.get('type')), [])
    record = next((record for record in records if record['id'] == ref['id']), None)
    if record is None:
        fail('REFERENCE_NOT_FOUND', 'Stored handle cannot be resolved')
    return record


_WEATHER_UNSET = object()


class Editor:
    def __init__(self, state, request_id):
        self.state = state
        self.aliases = {}
        self.alias_parts = {}
        self.sequence = 0
        self.parts = {}
        self.prefix = hashlib.sha256((state['workspace_id'] + ':' + request_id).encode()).hexdigest()[:20]

    @property
    def package(self):
        if self.state['package'] is None:
            fail('MISSING_TRIP', 'Use trip.define with known dates and timezone first')
        return self.state['package']

    def allocate_id(self):
        self.sequence += 1
        return f'a-{self.prefix}-{self.sequence}'

    def add(self, kind, fields):
        identifier = self.allocate_id()
        record = {'id': identifier, **copy.deepcopy(fields)}
        if kind == 'trip':
            self.package['trip'] = record
        else:
            self.package.setdefault(COLLECTIONS[kind], []).append(record)
        handle = 'h-' + identifier
        self.state['handles'][handle] = {'type': kind, 'id': identifier}
        return {'handle': handle}

    def handle(self, value):
        if not isinstance(value, dict):
            fail('INVALID_REFERENCE', 'Use a stable handle or preceding local alias')
        if set(value) in ({'local'}, {'local', 'part'}):
            alias = value['local']
            if not isinstance(alias, str) or alias not in self.aliases:
                fail('REFERENCE_NOT_FOUND', 'Local alias not found', reference=value)
            if 'part' in value:
                part = value['part']
                groups = {'scope': 'scopes', 'unit': 'units', 'stop': 'stops', 'segment': 'segments',
                          'leg': 'legs', 'connection': 'connections', 'link': 'links',
                          'call': 'calls',
                          'member': 'members', 'group': 'groups',
                          'checklist': 'checklist'}
                if not isinstance(part, dict) or set(part) != {'kind', 'key'} or not all(isinstance(v, str) for v in part.values()):
                    fail('INVALID_REFERENCE', 'part needs kind and key strings')
                group = groups.get(part['kind'])
                value = self.alias_parts[alias].get(group, {}).get(part['key'])
                if value is None:
                    fail('REFERENCE_NOT_FOUND', 'Named part not found')
            else:
                value = self.aliases[alias]
        if not isinstance(value, dict) or set(value) != {'handle'} or not isinstance(value['handle'], str):
            fail('INVALID_REFERENCE', 'Expected a stable handle')
        if value['handle'] not in self.state['handles']:
            fail('REFERENCE_NOT_FOUND', 'Handle is not in this workspace', reference=value)
        return copy.deepcopy(value)

    def ref(self, value, allowed=None):
        handle = self.handle(value)
        ref = self.state['handles'][handle['handle']]
        if allowed is not None and ref.get('type') not in allowed:
            fail('REFERENCE_KIND_MISMATCH', 'Handle has the wrong business type', reference=value, expected=sorted(allowed))
        return copy.deepcopy(ref)

    def record(self, value, allowed=None):
        return resolve_record(self.package, self.ref(value, allowed))

    def register_local(self, owner_ref, kind, record):
        ref = {'owner': copy.deepcopy(owner_ref), 'kind': kind, 'id': record['id']}
        return {'handle': _register_handle(self.state['handles'], ref)}

    def create_arrangement(self, day, title, kind, subject_handle, participants=None, timing=None):
        from .party import normalize_participants
        from .time_plans import normalize_time_plan
        day_record = self.record(day, {'day'})
        item = self.add('item', {'kind': kind, 'title': title, 'subject_ref': self.ref(subject_handle),
            'timing': normalize_time_plan(self, timing) if timing is not None else {'kind': 'unknown'},
            'participants': (normalize_participants(self, participants)
                             if participants is not None else {'kind': 'unknown'})})
        day_record['item_refs'].append(self.ref(item))
        return item

    def trip_define(self, *, start_date, end_date, default_timezone):
        if self.state['package'] is not None:
            fail('TRIP_ALREADY_DEFINED', 'Use an explicit update; trip.define cannot overwrite a trip')
        self.state['package'] = {'schema_version': '1.0', 'revision': 1,
                                 'example': self.state['example'], 'days': [], 'items': []}
        return self.add('trip', {'title': self.state['title'], 'start_date': start_date,
                                'end_date': end_date, 'default_timezone': default_timezone})


    def day_add(self, *, date, timezone, title=None, summary=None, weather_location=_WEATHER_UNSET):
        fields = {'date': date, 'timezone': timezone, 'item_refs': []}
        if weather_location is not _WEATHER_UNSET:
            fields['weather_location_ref'] = self.ref(weather_location, {'place', 'access_point'})
        if title is not None:
            nonempty(title, 'title')
            fields['title'] = title
        if summary is not None:
            nonempty(summary, 'summary')
            fields['summary'] = summary
        return self.add('day', fields)

    def place_add(self, *, name, roles=None, role_details=None):
        fields = {'name': name}
        if roles is None:
            if self.package['schema_version'] not in ('1.0',):
                fail('SCHEMA_VERSION_UNSUPPORTED', 'Unknown classification requires 1.0')
        else:
            fields['roles'] = place_roles(roles)
        if role_details is not None:
            fields['role_details'] = copy.deepcopy(role_details)
        return self.add('place', fields)

    def access_point_add(self, *, place, name, kind, location=None,
                         access_notes=None, notes=None):
        place_ref = self.ref(place, {'place'})
        nonempty(name, 'name')
        nonempty(kind, 'kind')
        fields = {'place_ref': place_ref, 'name': name, 'kind': kind}
        for field, value in (('access_notes', access_notes), ('notes', notes)):
            if value is not None:
                nonempty(value, field)
                fields[field] = value
        if location is not None:
            fields['location'] = copy.deepcopy(location)
        return self.add('access_point', fields)

    def access_point_update(self, *, target, set=None, clear=None, append_note=None):
        point = self.record(target, {'access_point'})
        changes = copy.deepcopy(set) if set is not None else {}
        if not isinstance(changes, dict):
            fail('INVALID_ARGUMENT', 'set must be an object', parameter='set')
        for field in ('name', 'access_notes', 'notes'):
            if field in changes:
                nonempty(changes[field], f'set.{field}')
        edit_fields(point, changes=changes, clear=clear, append_note=append_note,
                    allowed={'name', 'location', 'access_notes', 'notes'},
                    clearable={'location', 'access_notes', 'notes'})
        return self.handle(target)

    def place_update(self, *, target, set=None, clear=None, append_note=None, links=None, add_links=None, replace_weekly_hours=None):
        place = self.record(target, {'place'})
        before_details = copy.deepcopy(place.get('role_details'))
        if add_links is not None:
            if links is not None:
                fail('CONFLICTING_EDIT', 'Use add_links or links, not both', parameter='add_links')
            links = flat_links(add_links)
        if clear is not None and (not isinstance(clear, list) or not all(isinstance(k, str) for k in clear)):
            fail('INVALID_ARGUMENT', 'clear must be a list of field names', parameter='clear')
        changes = copy.deepcopy(set) if set is not None else {}
        if not isinstance(changes, dict):
            fail('INVALID_ARGUMENT', 'set must be an object')
        if 'roles' in changes:
            changes['roles'] = place_roles(changes['roles'])
        if 'roles' in (clear or []) and self.package['schema_version'] not in ('1.0',):
            fail('SCHEMA_VERSION_UNSUPPORTED', 'Unknown classification requires 1.0', parameter='clear')
        if replace_weekly_hours is not None:
            if 'availability' in changes or 'availability' in (clear or []):
                fail('CONFLICTING_EDIT', 'Do not mix weekly replacement with set/clear availability', parameter='replace_weekly_hours')
            self.replace_hours(place, weekly_hours(replace_weekly_hours))
        if 'availability' in changes:
            schedules = changes['availability']
            if not isinstance(schedules, list):
                fail('INVALID_ARGUMENT', 'availability must be a list')
            for schedule in schedules:
                if not isinstance(schedule, dict) or set_keys(schedule) - {'scope', 'timezone', 'weekly_rules'}:
                    fail('UNSUPPORTED_VARIANT', 'This slice accepts weekly opening schedules only')
                schedule['id'] = self.allocate_id()
                schedule['date_overrides'] = []
                if not isinstance(schedule.get('weekly_rules'), list):
                    fail('INVALID_ARGUMENT', 'weekly_rules must be a list')
                for rule in schedule['weekly_rules']:
                    if not isinstance(rule, dict) or 'id' in rule:
                        fail('INVALID_ARGUMENT', 'Weekly rules are objects; IDs are generated internally')
                    rule['id'] = self.allocate_id()
        if changes or clear or append_note is not None:
            edit_fields(place, changes=changes, clear=clear, append_note=append_note,
                        allowed={'name', 'roles', 'role_details', 'local_name', 'aliases', 'address', 'location', 'timezone',
                                 'content', 'notes', 'availability'},
                        clearable={'roles', 'role_details', 'local_name', 'aliases', 'address', 'location', 'timezone', 'content', 'notes', 'availability'})
        elif links is None and replace_weekly_hours is None:
            fail('INVALID_ARGUMENT', 'At least one place edit is required')
        protect_place_role_details(self, self.ref(target), before_details, place.get('role_details'))
        if links is not None:
            if not isinstance(links, list) or not links:
                fail('INVALID_ARGUMENT', 'links must be a nonempty list of actions')
            self.parts['links'] = {}
            for change in links:
                if not isinstance(change, dict) or set_keys(change) != {'action', 'key', 'value'} or change['action'] != 'add':
                    fail('UNSUPPORTED_VARIANT', 'This slice supports links.add with key and value')
                key, value = change['key'], change['value']
                nonempty(key, 'link key')
                if key in self.parts['links']:
                    fail('DUPLICATE_ALIAS', 'Link result keys must be unique in this operation')
                if not isinstance(value, dict) or 'id' in value:
                    fail('INVALID_ARGUMENT', 'Link value must omit its generated ID')
                identifier = self.allocate_id()
                place.setdefault('links', []).append({'id': identifier, **copy.deepcopy(value)})
                handle = 'h-' + identifier
                self.state['handles'][handle] = {'owner': self.ref(target), 'kind': 'link', 'id': identifier}
                self.parts['links'][key] = {'handle': handle}
        return self.handle(target)

    def replace_hours(self, place, schedule):
        existing = [s for s in place.get('availability', []) if s['scope'] == schedule['scope']
                    and (schedule['scope'] != 'other' or s.get('label') == schedule['label'])]
        if len(existing) > 1:
            fail('UNSUPPORTED_VARIANT', 'Multiple schedules in this scope need explicit selection', parameter='replace_weekly_hours.scope')
        if existing:
            current = existing[0]
            if any(current.get(k) for k in ('date_overrides', 'closures', 'valid_from', 'valid_to')) or any(
                    set(rule) - {'id', 'weekdays', 'state', 'intervals', 'all_day'} for rule in current['weekly_rules']):
                fail('UNSUPPORTED_VARIANT', 'This scope has exceptions or annotated rules; shorthand cannot replace them', parameter='replace_weekly_hours')
            old_rules = [{k: v for k, v in r.items() if k != 'id'} for r in current['weekly_rules']]
            if current['timezone'] == schedule['timezone'] and old_rules == schedule['weekly_rules']:
                return
        for rule in schedule['weekly_rules']:
            rule['id'] = self.allocate_id()
        if existing:
            current.update({'timezone': schedule['timezone'], 'weekly_rules': schedule['weekly_rules']})
        else:
            schedule['id'] = self.allocate_id()
            place.setdefault('availability', []).append(schedule)

    def link_update(self, *, target, set=None, clear=None):
        if self.ref(target).get('kind') != 'link':
            fail('REFERENCE_KIND_MISMATCH', 'Use the existing link handle', parameter='target')
        changes = copy.deepcopy(set) if set is not None else {}
        if not isinstance(changes, dict):
            fail('INVALID_ARGUMENT', 'set must be an object', parameter='set')
        if set_keys(changes) - {'url', 'label', 'purposes', 'platform', 'notes', 'language'}:
            fail('FIELD_NOT_EDITABLE', 'Link updates accept url/label/purposes/platform/notes/language', parameter='set')
        if 'url' in changes:
            nonempty(changes['url'], 'set.url')
            changes['web_url'] = changes.pop('url')
        if 'platform' in changes:
            nonempty(changes['platform'], 'set.platform')
            changes['platform'] = {'id': changes['platform'], 'label': changes['platform']}
        edit_fields(self.record(target), changes=changes, clear=clear, append_note=None,
                    allowed={'web_url', 'label', 'purposes', 'platform', 'notes', 'language'},
                    clearable={'platform', 'notes', 'language'})
        return self.handle(target)

    def place_hours_update(self, *, target, scope, timezone, weekly=None, closed_dates=None, label=None):
        place = self.record(target, {'place'})
        if weekly is None and closed_dates is None:
            fail('INVALID_ARGUMENT', 'Provide weekly changes or closed_dates', parameter='weekly')
        values = {'scope': scope, 'timezone': timezone, 'rules': weekly if weekly is not None else []}
        if label is not None:
            values['label'] = label
        proposed = weekly_hours(values, root='place.hours.update', allow_empty=weekly is None)
        closures = closed_days(closed_dates, timezone) if closed_dates is not None else []
        matches = [s for s in place.get('availability', []) if s['scope'] == scope
                   and (scope != 'other' or s.get('label') == label)]
        if len(matches) > 1:
            fail('UNSUPPORTED_VARIANT', 'Multiple schedules need explicit selection', parameter='scope')
        if not matches:
            current = {**proposed, 'id': self.allocate_id(), 'weekly_rules': []}
            place.setdefault('availability', []).append(current)
        else:
            current = matches[0]
        if current['timezone'] != timezone:
            fail('CONFLICTING_EDIT', 'An incremental edit cannot reinterpret the existing timezone', parameter='timezone')
        if current.get('valid_from') or current.get('valid_to'):
            fail('UNSUPPORTED_VARIANT', 'Seasonal schedules require explicit selection', parameter='scope')
        desired = {day: rule for rule in proposed['weekly_rules'] for day in rule['weekdays']}
        changed = set()
        def content(rule):
            return {k: v for k, v in rule.items() if k not in ('id', 'weekdays')}
        for day, rule in desired.items():
            old = [r for r in current['weekly_rules'] if day in r['weekdays']]
            if len(old) > 1:
                fail('UNSUPPORTED_VARIANT', 'Overlapping weekday rules need explicit selection', parameter='weekly')
            if not old or content(old[0]) != content(rule):
                changed.add(day)
        kept = []
        for rule in current['weekly_rules']:
            if not changed.intersection(rule['weekdays']):
                kept.append(rule)
                continue
            if set_keys(rule) - {'id', 'weekdays', 'state', 'intervals', 'all_day'} or references_rule(self.package, self.ref(target), rule['id']):
                fail('UNSUPPORTED_VARIANT', 'Cannot replace annotated rules through a time-only edit', parameter='weekly')
            remaining = [d for d in rule['weekdays'] if d not in changed]
            if remaining:
                kept.append({**rule, 'weekdays': remaining})
        for rule in proposed['weekly_rules']:
            days = [d for d in rule['weekdays'] if d in changed]
            if days:
                kept.append({**rule, 'id': self.allocate_id(), 'weekdays': days})
        if changed:
            current['weekly_rules'] = kept
        for closure in closures:
            if not any(old['start'] == closure['start'] and old['end'] == closure['end'] for old in current.get('closures', [])):
                current.setdefault('closures', []).append(closure)
        return self.handle(target)

    def plan_update(self, *, target, set=None, clear=None, append_note=None):
        from .time_plans import normalize_time_plan
        item = self.record(target, {'item'})
        if item.get('lifecycle', 'current') != 'current' or item['kind'] not in {'meal', 'visit', 'shopping', 'rest', 'errand', 'other', 'route', 'transport', 'stay_action'}:
            fail('UNSUPPORTED_VARIANT', 'Only current ordinary, route, transport or Stay action arrangements can be updated here')
        changes = {} if set is None else copy.deepcopy(set)
        removals = [] if clear is None else clear
        if (not isinstance(changes, dict) or not isinstance(removals, list)
                or not all(isinstance(name, str) for name in removals)):
            fail('INVALID_ARGUMENT', 'set must be an object and clear a list of field names')
        allowed = {'title', 'purpose', 'notes', 'timing', 'participants'}
        clearable = {'purpose', 'notes'}
        if changes.keys() - allowed - {'place'} or frozenset(removals) - clearable - {'place'}:
            fail('FIELD_NOT_EDITABLE', 'This method cannot edit the requested fields')
        if 'timing' in changes:
            changes['timing'] = normalize_time_plan(self, changes['timing'])
            if changes['timing'] != item.get('timing'):
                from .item_times import item_time_review_refs
                review_refs = item_time_review_refs(self.package, self.ref(target, {'item'}))
                if review_refs:
                    self.parts['timing_review_refs'] = review_refs
        if 'participants' in changes:
            from .party import normalize_participants
            changes['participants'] = normalize_participants(
                self, changes['participants'], 'set.participants')
            if (item.get('participants') == {'kind': 'unknown'}
                    and changes['participants'] != {'kind': 'unknown'}):
                from .participant_protection import participant_review_refs
                refs = participant_review_refs(
                    self.package, self.ref(target, {'item'}), 'participants')
                if refs:
                    self.parts['participant_review_refs'] = refs
        place_edit = 'place' in changes or 'place' in removals
        if place_edit:
            if self.package['schema_version'] not in ('1.0',) or item['kind'] != 'shopping':
                fail('FIELD_NOT_EDITABLE', 'Only a schema 1.0 shopping Item can change place', parameter='place')
            if 'place' in changes and 'place' in removals:
                fail('CONFLICTING_EDIT', 'Do not set and clear place together', parameter='place')
            proposed = self.ref(changes['place'], {'place'}) if 'place' in changes else None
            current = item.get('place_ref')
            changes = {key: value for key, value in changes.items() if key != 'place'}
            removals = [name for name in removals if name != 'place']
            if proposed != current:
                from .item_places import item_place_change_blockers
                blockers = item_place_change_blockers(self.package, self.ref(target, {'item'}), proposed)
                if blockers:
                    fail('PLAN_PLACE_CHANGE_BLOCKED',
                         'Recorded execution facts must be handled before changing this shopping place',
                         parameter='place', blockers=blockers,
                         blocker_refs=[copy.deepcopy(value['ref']) for value in blockers])
                if proposed is None:
                    item.pop('place_ref', None)
                else:
                    item['place_ref'] = proposed
                if not changes and not removals and append_note is None:
                    return self.handle(target)
            elif not changes and not removals and append_note is None:
                return self.handle(target)
        edit_fields(item, changes=changes, clear=removals, append_note=append_note,
                    allowed=allowed, clearable=clearable)
        return self.handle(target)

    def quote_record(self, *, subject, unit, value=None, amount=None, currency=None, estimated=False,
                     eligibility=None, inclusions=None, exclusions=None):
        subject_ref = self.ref(subject, {'place'})
        nonempty(unit, 'unit')
        if type(estimated) is not bool:
            fail('INVALID_ARGUMENT', 'estimated must be boolean', parameter='estimated')
        if value is not None and (amount is not None or currency is not None):
            fail('CONFLICTING_EDIT', 'Choose amount/currency or value', parameter='value')
        if value is None:
            if type(amount) is int:
                amount = str(amount)
            if not isinstance(amount, str) or re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', amount) is None:
                fail('INVALID_ARGUMENT', 'amount must be a nonnegative decimal string or integer; use strings for fractional amounts', parameter='amount')
            if not isinstance(currency, str) or re.fullmatch(r'[A-Z]{3}', currency) is None:
                fail('INVALID_ARGUMENT', 'currency must be a three-letter uppercase code', parameter='currency')
            value = {'kind': 'exact', 'money': {'amount': amount, 'currency': currency}}
        if estimated and (not isinstance(value, dict) or value.get('kind') not in ('exact', 'range', 'from')):
            fail('INVALID_ARGUMENT', 'Estimated quotes need a scalar, range, or starting price', parameter='value')
        fields = {'subject_ref': subject_ref, 'value': value, 'unit': unit}
        for name, entries in (('eligibility', eligibility), ('inclusions', inclusions), ('exclusions', exclusions)):
            if entries is not None:
                if not isinstance(entries, list) or any(not isinstance(s, str) or not s.strip() for s in entries):
                    fail('INVALID_ARGUMENT', f'{name} must be a list of nonempty descriptions', parameter=name)
                fields[name] = entries
        result = self.add('price_quote', fields)
        self.record(subject)['price_quote_refs'] = self.record(subject).get('price_quote_refs', []) + [self.ref(result)]
        if estimated:
            evidence = self.add('claim', {'target': {'object_ref': self.ref(result), 'field': 'value'},
                'basis': 'estimate', 'statement': f'编制输入标记的估算参考价（规范表达，非来源摘录）：{canonical(value)} / {unit}'})
            self.record(result)['evidence_refs'] = [self.ref(evidence)]
            self.parts['estimate'] = evidence
        return result

    def plan_add(self, *, kind, title, day=None, place=None, timing=None, participants=None,
                 purpose=None, before=None):
        from .party import normalize_participants
        from .time_plans import normalize_time_plan
        nonempty(kind, 'kind')
        if kind not in {'meal', 'visit', 'shopping', 'rest', 'errand', 'other'}:
            fail('UNSUPPORTED_VARIANT', 'This slice only creates ordinary selected activities')
        owner = None
        if day is None:
            if self.package.get('schema_version') != '1.0':
                fail('SCHEMA_VERSION_UNSUPPORTED',
                     'Selected Items without a Day require schema version 1.0',
                     parameter='day', supported_version='1.0')
            if before is not None:
                fail('INVALID_ARGUMENT', 'before requires an explicit target Day',
                     parameter='before')
        else:
            owner = self.record(day, {'day'})
        before_ref = None
        if before is not None:
            before_ref = self.ref(before, {'item'})
            anchor = resolve_record(self.package, before_ref)
            if anchor.get('lifecycle', 'current') != 'current':
                fail('PLAN_INSERT_ANCHOR_INVALID', 'before must identify a current Item',
                     parameter='before', reference=before)
            if before_ref not in owner['item_refs']:
                fail('PLAN_INSERT_ANCHOR_DAY_MISMATCH',
                     'before must identify a current Item in the target Day',
                     parameter='before', reference=before)
        fields = {'kind': kind, 'title': title,
                  'timing': {'kind': 'unknown'} if timing is None else normalize_time_plan(self, timing),
                  'participants': ({'kind': 'unknown'} if participants is None
                                   else normalize_participants(self, participants))}
        if place is not None:
            fields['place_ref'] = self.ref(place, {'place'})
        if purpose is not None:
            fields['purpose'] = purpose
        result = self.add('item', fields)
        result_ref = self.ref(result)
        if owner is None:
            self.package['trip'].setdefault('unassigned_item_refs', []).append(result_ref)
        elif before_ref is None:
            owner['item_refs'].append(result_ref)
        else:
            owner['item_refs'].insert(owner['item_refs'].index(before_ref), result_ref)
        return result

    def task_add(self, *, title, action, targets, notes=None, category=None,
                 preparation=None, depends_on=None, checklist=None,
                 assignees=None, beneficiaries=None):
        from .party import participant_member_snapshot
        from .tasks import (checklist_records, dependency_refs, normalize_action, normalize_category,
                            normalize_preparation, register_checklist, target_refs)
        fields = {'title': title, 'action': normalize_action(action), 'status': 'open',
                  'target_refs': target_refs(self, targets)}
        if notes is not None:
            fields['notes'] = notes
        if category is not None:
            fields['category'] = normalize_category(category)
        if preparation is not None:
            fields['preparation'] = normalize_preparation(preparation)
        if depends_on is not None:
            fields['depends_on'] = dependency_refs(self, depends_on)
        if assignees is not None:
            fields['assignees'] = participant_member_snapshot(
                self, assignees, 'assignees', allow_count=False)
        if beneficiaries is not None:
            fields['beneficiaries'] = participant_member_snapshot(
                self, beneficiaries, 'beneficiaries')
        keyed_checklist = checklist_records(self, checklist) if checklist is not None else []
        if keyed_checklist:
            fields['checklist'] = [record for _, record in keyed_checklist]
        result = self.add('task', fields)
        register_checklist(self, result, keyed_checklist)
        return result


    def task_complete(self, *, target, record_note, completed_at=None):
        task = self.record(target, {'task'})
        nonempty(record_note, 'record_note')
        if task['status'] == 'not_needed':
            fail('TASK_NOT_OPEN', 'A retired Task cannot be completed')
        open_entries = [entry['id'] for entry in task.get('checklist', [])
                        if entry['status'] == 'open']
        if open_entries:
            fail('TASK_CHECKLIST_OPEN', 'Complete or mark every checklist entry not_needed first',
                 checklist_ids=open_entries)
        completion = {'record_note': record_note}
        if completed_at is not None:
            completion['completed_at'] = completed_at
        if task['status'] == 'done':
            if task.get('completion') != completion:
                fail('TASK_ALREADY_DONE', 'Completion differs; this method cannot overwrite the existing record')
            return self.handle(target)
        task['status'] = 'done'
        task['completion'] = completion
        return self.handle(target)

    def task_amend(self, *, target, set=None, clear=None, append_note=None,
                   checklist_edits=None):
        from .tasks import (dependency_refs, edit_checklist, normalize_action, normalize_category,
                            normalize_preparation, target_refs)
        task = self.record(target, {'task'})
        if task['status'] == 'not_needed':
            fail('TASK_NOT_OPEN', 'A retired Task cannot be amended')
        changes = {} if set is None else copy.deepcopy(set)
        clear_fields = [] if clear is None else copy.deepcopy(clear)
        if not isinstance(changes, dict) or not isinstance(clear_fields, list) or not all(
                isinstance(field, str) for field in clear_fields):
            fail('INVALID_ARGUMENT', 'set must be an object and clear a list of field names')
        allowed = {'title', 'action', 'notes', 'due', 'window', 'category', 'preparation',
                   'depends_on', 'targets'}
        clearable = {'notes', 'due', 'window', 'category', 'preparation', 'depends_on'}
        if self.package.get('schema_version') in ('1.0',):
            allowed |= {'assignees', 'beneficiaries'}
            clearable |= {'assignees', 'beneficiaries'}
        if changes.keys() - allowed or frozenset(clear_fields) - clearable:
            fail('FIELD_NOT_EDITABLE', 'This method cannot edit the requested fields')
        if (not changes and not clear_fields and append_note is None
                and checklist_edits is None):
            fail('INVALID_ARGUMENT', 'At least one explicit change is required')
        protected = {'title', 'action', 'category', 'preparation', 'depends_on', 'targets'}
        if self.package.get('schema_version') in ('1.0',):
            protected |= {'assignees', 'beneficiaries'}
        if (self.package.get('schema_version') in ('1.0',) and task['status'] == 'done'
                and ((frozenset(changes) | frozenset(clear_fields)) & protected
                     or checklist_edits is not None)):
            fail('TASK_REOPEN_REQUIRED', 'Reopen a done Task before changing its definition or checklist')
        if 'category' in changes:
            changes['category'] = normalize_category(changes['category'], 'set.category')
        if 'action' in changes:
            changes['action'] = normalize_action(changes['action'], 'set.action')
        if 'preparation' in changes:
            changes['preparation'] = normalize_preparation(changes['preparation'], 'set.preparation')
        if 'depends_on' in changes:
            changes['depends_on'] = dependency_refs(self, changes['depends_on'], 'set.depends_on')
        if 'targets' in changes:
            changes['target_refs'] = target_refs(
                self, changes.pop('targets'), 'set.targets', require_current_items=True)
        if 'assignees' in changes:
            from .party import participant_member_snapshot
            changes['assignees'] = participant_member_snapshot(
                self, changes['assignees'], 'set.assignees', allow_count=False)
        if 'beneficiaries' in changes:
            from .party import participant_member_snapshot
            changes['beneficiaries'] = participant_member_snapshot(
                self, changes['beneficiaries'], 'set.beneficiaries')
        if changes or clear_fields or append_note is not None:
            edit_fields(task, changes=changes, clear=clear_fields, append_note=append_note,
                        allowed=(allowed - {'targets'}) | {'target_refs'},
                        clearable=clearable)
        if checklist_edits is not None:
            edit_checklist(self, self.handle(target), checklist_edits)
        return self.handle(target)


from .routes import route_bind_visit, route_compose, route_edit, route_replace_interval
from .journeys import (journey_compose, journey_edit, journey_replace_leg,
                       path_add_schematic, path_record)
from .transport_services import service_record, service_update


from .source_refresh import source_register, source_duration_adopt, source_duration_refresh, source_duration_resolve
from .source_topology import source_identity_bind
from .source_fields import source_field_apply, source_field_resolve


from .reservations import reservation_record, coverage_record, require_record_origin
from .coverage_revisions import coverage_replace_confirmation, coverage_revoke_scopes
from .arrangements import (day_update, plan_move, plan_withdraw,
                           trip_change_dates, trip_update)
from .stays import stay_action_add, stay_action_bind, stay_plan, stay_change_plan
from .recommendations import recommendation_add, recommendation_update
from .guide_notes import source_record, guide_note_add, guide_note_update
from .tasks import task_reopen, task_retire
from .media import media_image_add, media_update, media_usage_add, media_usage_remove
from .party import party_describe, party_member_add, party_member_update, party_group_add
from .money import (budget_configure, cost_confirm, cost_record,
                    exchange_rate_record, require_cost_origin)
from .vehicles import vehicle_record_owned
from .issues import (issue_record, issue_resolve,
                     require_issue_resolution_origin)


METHODS = {
    'reservation.record': reservation_record, 'coverage.record': coverage_record,
    'coverage.replace_confirmation': coverage_replace_confirmation, 'coverage.revoke_scopes': coverage_revoke_scopes,
    'stay.plan': stay_plan, 'stay.change_plan': stay_change_plan,
    'stay.action.add': stay_action_add, 'stay.action.bind': stay_action_bind,
    'recommendation.add': recommendation_add, 'recommendation.update': recommendation_update,
    'source.register': source_register, 'source.duration.adopt': source_duration_adopt,
    'source.duration.refresh': source_duration_refresh, 'source.duration.resolve': source_duration_resolve,
    'source.identity.bind': source_identity_bind,
    'source.field.apply': source_field_apply,
    'source.field.resolve': source_field_resolve,
    'source.record': source_record, 'guide.note.add': guide_note_add, 'guide.note.update': guide_note_update,
    'media.image.add': media_image_add, 'media.update': media_update,
    'media.usage.add': media_usage_add, 'media.usage.remove': media_usage_remove,
    'issue.record': issue_record, 'issue.resolve': issue_resolve,
    'route.compose': route_compose, 'route.bind_visit': route_bind_visit,
    'route.edit': route_edit,
    'route.replace_interval': route_replace_interval,
    'journey.compose': journey_compose, 'journey.edit': journey_edit,
    'journey.replace_leg': journey_replace_leg,
    'vehicle.record_owned': vehicle_record_owned,
    'path.add_schematic': path_add_schematic, 'path.record': path_record,
    'service.record': service_record, 'service.update': service_update,
    'trip.define': Editor.trip_define,
    'trip.change_dates': trip_change_dates, 'trip.update': trip_update,
    'day.add': Editor.day_add,
    'day.update': day_update,
    'place.add': Editor.place_add,
    'access_point.add': Editor.access_point_add, 'access_point.update': Editor.access_point_update,
    'quote.record': Editor.quote_record,
    'plan.add': Editor.plan_add, 'task.add': Editor.task_add,
    'task.complete': Editor.task_complete, 'task.amend': Editor.task_amend,
    'task.reopen': task_reopen, 'task.retire': task_retire,
    'party.describe': party_describe, 'party.member.add': party_member_add,
    'party.member.update': party_member_update,
    'party.group.add': party_group_add,
    'cost.record': cost_record, 'cost.confirm': cost_confirm,
    'exchange_rate.record': exchange_rate_record, 'budget.configure': budget_configure,
    'place.update': Editor.place_update, 'plan.update': Editor.plan_update,
    'plan.move': plan_move, 'plan.withdraw': plan_withdraw,
    'link.update': Editor.link_update,
    'place.hours.update': Editor.place_hours_update,
}


def apply(state, request):
    """Return a new workspace and receipt. Never mutate the caller's state."""
    check_workspace(state)
    if not isinstance(request, dict) or set(request) != {'request_id', 'expected_revision', 'operations'}:
        fail('INVALID_REQUEST', 'Expected request_id, expected_revision and operations only')
    nonempty(request['request_id'], 'request_id')
    fingerprint = hashlib.sha256(canonical(request).encode()).hexdigest()
    prior = state['receipts'].get(request['request_id'])
    if prior:
        if prior['fingerprint'] != fingerprint:
            fail('REQUEST_ID_REUSED', 'A successful request ID cannot be reused with different content')
        return copy.deepcopy(state), {**copy.deepcopy(prior['result']), 'replayed': True,
                                      'historical_receipt': (
                                          prior['result']['original_commit_revision']
                                          != state['revision']),
                                      'current_revision': state['revision']}
    if type(request['expected_revision']) is not int or request['expected_revision'] != state['revision']:
        fail('REVISION_CONFLICT', 'Read current state before editing', current_revision=state['revision'])
    if not isinstance(request['operations'], list) or not request['operations']:
        fail('INVALID_REQUEST', 'operations must be a nonempty list')
    candidate = copy.deepcopy(state)
    editor = Editor(candidate, request['request_id'])
    outcomes = []
    writers = {}
    for index, operation in enumerate(request['operations']):
        try:
            if not isinstance(operation, dict) or set(operation) - {'method', 'args', 'as', 'origin'} or not {'method', 'args'} <= set(operation):
                fail('INVALID_OPERATION', 'Expected method, args, optional as and origin')
            method = operation['method']
            if not isinstance(method, str) or method not in METHODS:
                fail('UNKNOWN_METHOD', 'Unsupported authoring method', method=method)
            args = operation['args']
            if not isinstance(args, dict):
                fail('INVALID_ARGUMENT', 'args must be an object')
            validate_coordinate_inputs(method, args)
            if method in {'reservation.record', 'coverage.record', 'coverage.replace_confirmation', 'coverage.revoke_scopes'}:
                require_record_origin(operation.get('origin'), example=editor.state['example'])
            if method == 'issue.resolve':
                require_issue_resolution_origin(
                    operation.get('origin'), example=editor.state['example'])
            if (method == 'cost.confirm'
                    or (method == 'cost.record' and args.get('price_status') == 'confirmed')):
                require_cost_origin(operation.get('origin'), example=editor.state['example'])
            for name, value in args.items():
                if value is None:
                    fail('INVALID_ARGUMENT', 'Omit unknown arguments; use clear for removal', parameter=name)
                if name in {'name', 'title', 'start_date', 'end_date', 'date', 'timezone', 'default_timezone'}:
                    nonempty(value, name)
            alias = operation.get('as')
            if 'as' in operation:
                nonempty(alias, 'as')
                if alias in editor.aliases:
                    fail('DUPLICATE_ALIAS', 'A batch alias may only be declared once')
            try:
                inspect.signature(METHODS[method]).bind(editor, **args)
            except TypeError as error:
                fail('INVALID_ARGUMENT', str(error))
            editor.parts = {}
            editor.operation_origin = copy.deepcopy(operation.get('origin'))
            before_operation = copy.deepcopy(candidate['package'])
            before_sources = copy.deepcopy(candidate.get('source_imports'))
            handle = METHODS[method](editor, **copy.deepcopy(args))
            skip_origin_claim = editor.parts.pop('_skip_origin_claim', False)
            issue_status_claim = editor.parts.pop('_issue_status_claim', None)
            if issue_status_claim is not None:
                origin = issue_status_claim['origin']
                primary_ref = editor.ref(handle, {'issue'})
                evidence = editor.add('claim', {
                    'target': {'object_ref': primary_ref, 'field': 'status'},
                    'basis': origin['basis'], 'statement': origin['statement'],
                    'value': 'resolved', 'disposition': 'adopted'})
                claim_ref = editor.ref(evidence, {'claim'})
                editor.state.setdefault('issue_resolutions', {})[primary_ref['id']] = {
                    **copy.deepcopy(issue_status_claim),
                    'status_claim_ref': claim_ref,
                }
                editor.parts['status_claim'] = evidence
            elif 'origin' in operation and not skip_origin_claim:
                origin = operation['origin']
                if not isinstance(origin, dict) or set(origin) != {'basis', 'statement'}:
                    fail('INVALID_ARGUMENT', 'origin requires basis and statement')
                nonempty(origin['statement'], 'origin.statement')
                primary_ref = editor.ref(handle)
                claim_target = {'object_ref': primary_ref, 'field': 'value' if method == 'quote.record' else 'authoring_statement'}
                if 'owner' in primary_ref:
                    claim_target = {'object_ref': primary_ref['owner'], 'local_ref': primary_ref, 'field': 'authoring_statement'}
                evidence = editor.add('claim', {'target': claim_target,
                    'basis': origin['basis'], 'statement': origin['statement']})
                editor.parts['evidence'] = evidence
                if method == 'quote.record':
                    editor.record(handle).setdefault('evidence_refs', []).append(editor.ref(evidence))
            if alias is not None:
                editor.aliases[alias] = handle
                editor.alias_parts[alias] = copy.deepcopy(editor.parts)
            effect = 'structured' if before_operation != candidate['package'] else (
                'metadata' if before_sources != candidate.get('source_imports') else 'no_change')
            for path in changed_record_paths(before_operation, editor.package):
                writers.setdefault(path, []).append(index)
            outcomes.append({'method': method, 'effect': effect, 'primary': handle, 'parts': copy.deepcopy(editor.parts)})
        except AuthoringError as error:
            error.details['op_index'] = index
            raise
    candidate['revision'] += 1
    editor.package['revision'] = candidate['revision']
    validation = validate_authored(editor.package)
    if not validation['valid']:
        for error in validation['errors']:
            error_path = error['path']
            related = {index for path, indices in writers.items()
                       if not error_path or path == error_path or path.startswith(error_path + '/') or error_path.startswith(path + '/')
                       for index in indices}
            error['related_op_indices'] = sorted(related)
        fail('MODEL_VALIDATION', 'Batch did not produce a valid model', errors=validation['errors'])
    from .item_times import protected_time_projection_changes
    protected_changes = protected_time_projection_changes(state.get('package'), editor.package)
    if protected_changes:
        fail('PLAN_TIME_CHANGE_BLOCKED',
             'Recorded execution facts must be handled before changing known timing.',
             changes=protected_changes,
             blocker_refs=[copy.deepcopy(ref) for change in protected_changes
                           for ref in change['blocker_refs']])
    from .participant_protection import (protected_party_history_changes,
                                         protected_plan_participant_changes)
    history_changes = protected_party_history_changes(state.get('package'), editor.package)
    if history_changes:
        fail('PARTY_HISTORY_SCOPE_BLOCKED',
             'Recorded Task history has dynamic all scope that would change with this roster',
             changes=history_changes,
             blocker_refs=[copy.deepcopy(change['task_ref']) for change in history_changes])
    participant_changes = protected_plan_participant_changes(
        state.get('package'), editor.package)
    if participant_changes:
        fail('PLAN_PARTICIPANTS_CHANGE_BLOCKED',
             'Recorded execution facts must be handled before changing participant scope',
             changes=participant_changes,
             blocker_refs=[copy.deepcopy(ref) for change in participant_changes
                           for ref in change['blocker_refs']])
    result = {'committed': True, 'previous_revision': state['revision'], 'revision': candidate['revision'],
              'original_commit_revision': candidate['revision'], 'current_revision': candidate['revision'],
              'aliases': copy.deepcopy(editor.aliases), 'operations': outcomes, 'replayed': False,
              'warnings': validation['warnings'], 'validation_scope': validation['scope'],
              **({'time_assessments': copy.deepcopy(validation['time_assessments'])}
                 if 'time_assessments' in validation else {}),
              **({'transport_assessments': copy.deepcopy(validation['transport_assessments'])}
                 if 'transport_assessments' in validation else {})}
    candidate['receipts'][request['request_id']] = {'fingerprint': fingerprint, 'result': copy.deepcopy(result)}
    return candidate, result


PREVIEW_KEY_FIELDS = ('title', 'name', 'date', 'kind', 'mode', 'status',
                      'service_number', 'service_date', 'action', 'category',
                      'basis', 'scope')


def _preview_key_fields(record):
    return {key: copy.deepcopy(record[key]) for key in PREVIEW_KEY_FIELDS
            if key in record and isinstance(record[key], (str, int, bool))}


def _preview_safe_value(value, state, candidate, new_refs, alias_by_handle,
                        temporary_prefix):
    if isinstance(value, dict):
        if set(value) in ({'type', 'id'}, {'owner', 'kind', 'id'}):
            handle = _handle_for_ref(candidate, value)
            if canonical(value) in new_refs:
                result = {'preview_object': value.get('type', value.get('kind'))}
                alias = alias_by_handle.get(handle)
                if alias is not None:
                    result['alias'] = alias
                return result
            stable = _handle_for_ref(state, value)
            return {'handle': stable} if stable is not None else copy.deepcopy(value)
        return {key: _preview_safe_value(
                    child, state, candidate, new_refs, alias_by_handle,
                    temporary_prefix)
                for key, child in value.items()
                if key not in {'signature', 'signing_key'}}
    if isinstance(value, list):
        return [_preview_safe_value(
                    child, state, candidate, new_refs, alias_by_handle,
                    temporary_prefix)
                for child in value]
    if isinstance(value, str):
        if (temporary_prefix is not None
                and re.fullmatch(
                    rf'(?:h-)?a-{re.escape(temporary_prefix)}-[0-9]+', value)):
            return '<preview-object>'
        for ref_key in new_refs:
            ref = json.loads(ref_key)
            if value == ref['id'] or value == 'h-' + ref['id']:
                return '<preview-object>'
    return copy.deepcopy(value)


def _preview_changes(state, candidate, alias_by_handle, new_handles, new_refs,
                     temporary_prefix):
    changes = []
    for handle, ref in state['handles'].items():
        before = resolve_record(state['package'], ref)
        try:
            after = resolve_record(candidate['package'], ref)
        except AuthoringError as error:
            if error.code != 'REFERENCE_NOT_FOUND':
                raise
            changes.append({'kind': 'removed', 'handle': handle,
                            'type': ref.get('type', ref.get('kind')),
                            'before': _preview_safe_value(
                                before, state, candidate, new_refs, alias_by_handle,
                                temporary_prefix)})
            continue
        if before == after:
            continue
        fields = sorted(key for key in set(before) | set(after)
                        if before.get(key) != after.get(key) and key != 'id')
        changes.append({
            'kind': 'updated', 'handle': handle,
            'type': ref.get('type', ref.get('kind')),
            'changed_fields': fields,
            'before': _preview_safe_value(
                before, state, candidate, new_refs, alias_by_handle,
                temporary_prefix),
            'after': _preview_safe_value(
                after, state, candidate, new_refs, alias_by_handle,
                temporary_prefix),
        })
    for handle in sorted(new_handles, key=lambda value: canonical(candidate['handles'][value])):
        ref = candidate['handles'][handle]
        record = resolve_record(candidate['package'], ref)
        change = {'kind': 'created', 'type': ref.get('type', ref.get('kind')),
                  'key_fields': _preview_key_fields(record)}
        if handle in alias_by_handle:
            change['alias'] = alias_by_handle[handle]
        changes.append(change)
    return changes


def _preview_error_value(value, temporary_prefix):
    if isinstance(value, dict):
        if set(value) in ({'type', 'id'}, {'owner', 'kind', 'id'}):
            if (temporary_prefix is not None
                    and temporary_prefix in str(value.get('id', ''))):
                return {'preview_object': value.get('type', value.get('kind'))}
        if (set(value) == {'handle'} and temporary_prefix is not None
                and temporary_prefix in str(value.get('handle', ''))):
            return {'preview_object': 'created earlier in this preview'}
        return {key: _preview_error_value(child, temporary_prefix)
                for key, child in value.items()
                if key not in {'signature', 'signing_key', 'conflict', 'ticket'}}
    if isinstance(value, list):
        return [_preview_error_value(child, temporary_prefix) for child in value]
    if (isinstance(value, str) and temporary_prefix is not None
            and temporary_prefix in value):
        return '<preview-object>'
    return copy.deepcopy(value)


def preview(state, request):
    """Run the exact apply engine and return a non-executable review projection."""
    check_workspace(state)
    try:
        candidate, receipt = apply(state, request)
    except AuthoringError as error:
        temporary_prefix = None
        if (isinstance(request, dict)
                and isinstance(request.get('request_id'), str)):
            temporary_prefix = hashlib.sha256(
                (state['workspace_id'] + ':' + request['request_id']).encode()).hexdigest()[:20]
        conflict = error.details.get('conflict')
        details = _preview_error_value(
            {key: value for key, value in error.details.items() if key != 'conflict'},
            temporary_prefix)
        if conflict is not None:
            payload = conflict.get('payload', {}) if isinstance(conflict, dict) else {}
            details['conflict_summary'] = _preview_error_value({
                'kind': payload.get('kind', 'source_conflict'),
                'current': copy.deepcopy(payload.get('current')),
                'proposal': copy.deepcopy(payload.get('proposal')),
                'explanation': ('Preview conflicts are diagnostic only; submit a real refresh '
                                'to receive a resolvable conflict.'),
            }, temporary_prefix)
        raise AuthoringError(error.code, str(error), preview_only=True, **details) from None
    if receipt['replayed']:
        return {'preview_only': True, 'committed': False, 'replayed': True,
                'no_new_change': True, 'revision': state['revision'],
                'proposed_revision': state['revision'], 'changes': [],
                'operations': [], 'warnings': []}
    temporary_prefix = hashlib.sha256(
        (state['workspace_id'] + ':' + request['request_id']).encode()
    ).hexdigest()[:20]
    alias_by_handle = {
        value['handle']: alias for alias, value in receipt['aliases'].items()}
    new_handles = [
        handle for handle in candidate['handles'] if handle not in state['handles']]
    new_refs = {canonical(candidate['handles'][handle]) for handle in new_handles}
    return {
        'preview_only': True,
        'committed': False,
        'replayed': False,
        'no_new_change': False,
        'revision': state['revision'],
        'proposed_revision': candidate['revision'],
        'changes': _preview_changes(
            state, candidate, alias_by_handle, new_handles, new_refs,
            temporary_prefix),
        'operations': [
            {'op_index': index, 'method': outcome['method'], 'effect': outcome['effect']}
            for index, outcome in enumerate(receipt['operations'])],
        'warnings': _preview_safe_value(
            receipt['warnings'], state, candidate, new_refs, alias_by_handle,
            temporary_prefix),
        'validation_scope': receipt['validation_scope'],
    }
