"""Small cross-field checks that JSON Schema cannot express by itself."""
from decimal import Decimal
import re


def cross_field_errors(package):
    errors = []
    def error(code, path, message):
        errors.append({'code': code, 'path': path, 'message': message})
    def walk(value, path=''):
        if isinstance(value, dict):
            if 'constraints' in value and value.get('kind') in {'fixed', 'estimated', 'boundaries', 'window', 'derived', 'sequence_only', 'unknown'} and not re.fullmatch(r'/(items|activities)/[0-9]+/timing', path):
                error('CONSTRAINT_LOCATION', path, 'timing constraints are supported only on Item/Activity timing')
            if value.get('kind') == 'range' and 'min' in value and 'max' in value:
                low, high = value['min'], value['max']
                if low['currency'] != high['currency'] or Decimal(low['amount']) > Decimal(high['amount']):
                    error('PRICE_RANGE', path, 'range must use one currency with min <= max')
            if value.get('kind') == 'local_dates' and value['check_out'] <= value['check_in']:
                error('STAY_DATE_ORDER', path, 'check_out must follow check_in')
            for key, child in value.items():
                walk(child, path + '/' + key.replace('~', '~0').replace('/', '~1'))
        elif isinstance(value, list):
            ids = [x['id'] for x in value if isinstance(x, dict) and 'id' in x and 'type' not in x and 'owner' not in x]
            if len(ids) != len(set(ids)):
                error('DUPLICATE_LOCAL_ID', path, 'IDs within an owned collection must be unique')
            for index, child in enumerate(value): walk(child, path + '/' + str(index))
    walk(package)
    party = package['trip'].get('party', {})
    members = party.get('members', [])
    if party.get('members_status') == 'complete' and not members:
        error('PARTY_COMPLETE_EMPTY', '/trip/party/members_status',
              'complete member list must contain at least one member')
    if 'count' in party and len(members) > party['count']:
        error('PARTY_COUNT', '/trip/party', 'recorded members exceed party count')
    if (party.get('members_status') == 'complete' and 'count' in party
            and len(members) != party['count']):
        error('PARTY_COUNT', '/trip/party', 'complete member count differs from party count')
    for index, group in enumerate(party.get('groups', [])):
        if len(group['member_ids']) != len(set(group['member_ids'])):
            error('PARTY_GROUP_DUPLICATE_MEMBER', f'/trip/party/groups/{index}/member_ids',
                  'group members must be unique')
    for index, rate in enumerate(package.get('exchange_rates', [])):
        if Decimal(rate['rate']) <= 0:
            error('EXCHANGE_RATE', f'/exchange_rates/{index}/rate', 'exchange rate must be positive')
    for index, hold in enumerate(package.get('authorization_holds', [])):
        parts = [hold[key] for key in ('captured_amount', 'released_amount') if key in hold]
        if any(part['currency'] != hold['amount']['currency'] for part in parts):
            error('HOLD_CURRENCY', f'/authorization_holds/{index}', 'captured/released amounts must use the hold currency')
        elif sum((Decimal(part['amount']) for part in parts), Decimal(0)) > Decimal(hold['amount']['amount']):
            error('HOLD_ALLOCATION', f'/authorization_holds/{index}', 'known captured plus released amount exceeds hold amount')
    for index, task in enumerate(package.get('tasks', [])):
        if task['status'] == 'done' and any(x['status'] == 'open' for x in task.get('checklist', [])):
            error('TASK_CHECKLIST', f'/tasks/{index}', 'done task has an open checklist entry')
        due = task.get('due', {})
        if due.get('kind') == 'relative':
            anchor = due['anchor']
            fields = {'item': {'start', 'end'}, 'activity': {'start', 'end'}, 'service_use': {'pickup', 'dropoff'}, 'trip': {'departure_at'}}
            if anchor['field'] not in fields[anchor['ref']['type']]:
                error('DUE_ANCHOR_FIELD', f'/tasks/{index}/due/anchor', 'field is not defined for anchor type')
    for index, place in enumerate(package.get('places', [])):
        ids = []
        for schedule in place.get('availability', []):
            ids.append(schedule['id'])
            for rule in schedule.get('weekly_rules', []) + schedule.get('date_overrides', []):
                ids.append(rule['id']); ids.extend(c['id'] for c in rule.get('cutoffs', []))
        if len(ids) != len(set(ids)):
            error('AMBIGUOUS_RULE_ID', f'/places/{index}/availability', 'schedule/rule/cutoff IDs must be unique within a Place')
    for nindex, note in enumerate(package.get('guide_notes', [])):
        for pindex, paragraph in enumerate(note['paragraphs']):
            for cindex, citation in enumerate(paragraph.get('citations', [])):
                if 'locator' not in citation:
                    continue
                path = f'/guide_notes/{nindex}/paragraphs/{pindex}/citations/{cindex}'
                start, end = citation['locator']['start'], citation['locator']['end']
                if end <= start:
                    error('GUIDE_CITATION_RANGE', path + '/locator',
                          'Unicode code-point citation range must be nonempty')
                elif len(citation['excerpt']) != end - start:
                    error('GUIDE_CITATION_LENGTH', path + '/excerpt',
                          'Excerpt code-point length must equal locator end minus start')
    errors.extend(duration_claim_errors(package))
    return errors


def duration_claim_errors(package):
    """Bounded adopted-value contract for 1.0 route duration statements."""
    if package.get('schema_version') not in ('1.0',):
        return []
    errors = []
    routes = {r['id']: r for r in package.get('routes', [])}
    current = {}
    for index, claim in enumerate(package.get('claims', [])):
        target = claim['target']
        local = target.get('local_ref', {})
        owner = local.get('owner', {})
        kind, field = local.get('kind'), target['field']
        if (claim.get('disposition') != 'adopted' or owner.get('type') != 'route'
                or kind not in ('stop', 'segment') or field not in ('dwell', 'duration')):
            continue
        path = f'/claims/{index}'
        expected_field = 'dwell' if kind == 'stop' else 'duration'
        if target['object_ref'] != owner or field != expected_field:
            errors.append({'code': 'DURATION_CLAIM_TARGET', 'path': path + '/target',
                           'message': 'Duration evidence must target its owning Route and the matching local field'})
            continue
        route = routes.get(owner['id'], {})
        collection = 'stops' if kind == 'stop' else 'segments'
        record = next((record for record in route.get(collection, []) if record['id'] == local['id']), {})
        if field not in record or 'value' not in claim or claim['value'] != record[field]:
            errors.append({'code': 'DURATION_CLAIM_VALUE', 'path': path + '/value',
                           'message': 'Adopted duration evidence must equal the existing current field value'})
        key = (owner['id'], kind, local['id'], field)
        if key in current:
            errors.append({'code': 'DURATION_CLAIM_CONFLICT', 'path': path + '/disposition',
                           'message': f'Multiple adopted duration statements; earlier claim at /claims/{current[key]}'})
        current[key] = index
    return errors


def shopping_place_warnings(package):
    warnings = []
    for index, item in enumerate(package.get('items', [])):
        if (item.get('lifecycle', 'current') == 'current'
                and item.get('kind') == 'shopping' and 'place_ref' not in item):
            warnings.append({
                'code': 'SHOPPING_PLACE_UNKNOWN',
                'path': f'/items/{index}/place_ref',
                'item_ref': {'type': 'item', 'id': item['id']},
                'unknown': ['map_location', 'opening_hours'],
                'message': ('Shopping place is not recorded; map location and opening hours '
                            'cannot be assessed.'),
            })
    return warnings


def trip_range_warnings(package):
    """Keep out-of-range Days intact while naming the exact review scope."""
    trip = package['trip']
    warnings = []
    for index, day in enumerate(package.get('days', [])):
        if trip['start_date'] <= day['date'] <= trip['end_date']:
            continue
        warnings.append({
            'code': 'DAY_OUTSIDE_TRIP_RANGE',
            'path': f'/days/{index}/date',
            'day_ref': {'type': 'day', 'id': day['id']},
            'day_date': day['date'],
            'trip_start_date': trip['start_date'],
            'trip_end_date': trip['end_date'],
            'message': ('The Day remains recorded outside the Trip date range; review and '
                        'rearrange it explicitly.'),
        })
    return warnings


def task_dependency_warnings(package):
    """Report open direct dependencies without contradicting explicit completion."""
    tasks = {task['id']: task for task in package.get('tasks', [])}
    warnings = []
    for index, task in enumerate(package.get('tasks', [])):
        if task['status'] != 'done':
            continue
        open_refs = [dict(ref) for ref in task.get('depends_on', [])
                     if tasks.get(ref['id'], {}).get('status') == 'open']
        if open_refs:
            warnings.append({
                'code': 'TASK_DEPENDENCY_OPEN',
                'path': f'/tasks/{index}/depends_on',
                'task_ref': {'type': 'task', 'id': task['id']},
                'dependency_refs': open_refs,
                'message': ('Task is explicitly done while one or more direct dependencies '
                            'remain open.'),
            })
    return warnings
