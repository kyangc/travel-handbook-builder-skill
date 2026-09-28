"""Bounded data-model checks, not a complete Schema or travel feasibility engine."""
from datetime import datetime
from zoneinfo import ZoneInfo
from time_constraints import validate_constraint

TYPES = dict(zip(
    'days items places access_points recommendations routes journeys legs transport_services stays activities service_uses vehicle_uses service_bundles tasks reservations coverages price_quotes costs payments authorization_holds exchange_rates sources claims issues media paths guide_notes'.split(),
    'day item place access_point recommendation route journey leg transport_service stay activity service_use vehicle_use service_bundle task reservation coverage price_quote cost payment authorization_hold exchange_rate source claim issue media path guide_note'.split()))
LOCAL = {'unit': 'units', 'stop': 'stops', 'segment': 'segments', 'call': 'calls', 'link': 'links', 'connection': 'connections', 'scope': 'scopes', 'port_call': 'port_calls'}
FIELD_TYPES = {
    # Schema narrows AccessPoint.place_ref to Place while TransferStep.place_ref
    # deliberately accepts either endpoint granularity.
    'place_ref': {'place', 'access_point'}, 'parent_ref': {'place'}, 'weather_location_ref': {'place', 'access_point'}, 'endpoint_ref': {'place', 'access_point'},
    'from_ref': {'place', 'access_point', 'route', 'journey', 'activity', 'service_bundle'},
    'to_ref': {'place', 'access_point'}, 'path_ref': {'path'}, 'vehicle_ref': {'vehicle_use'},
    'service_ref': {'transport_service'}, 'rental_ref': {'service_use'},
    'lodging_ref': {'place', 'service_bundle'}, 'reservation_ref': {'reservation'},
    'original_payment_ref': {'payment'}, 'replaces_cost_ref': {'cost'},
    'source_ref': {'source'}, 'source_refs': {'source'}, 'adopted_claim_ref': {'claim'},
    'item_refs': {'item'}, 'leg_refs': {'leg'}, 'leg_ref': {'leg'},
    'from_leg_ref': {'leg'}, 'to_leg_ref': {'leg'}, 'depends_on': {'task'},
    'cost_refs': {'cost'}, 'budget_rate_refs': {'exchange_rate'},
    'duration_from_ref': {'route', 'journey', 'activity'}, 'captured_payment_refs': {'payment'},
    'component_refs': {'stay', 'journey', 'activity', 'service_use'},
}
SUBJECT_TYPES = {'route': 'route', 'transport': 'journey', 'activity': 'activity',
                 'stay_action': 'stay', 'service_action': 'service_use', 'bundle_action': 'service_bundle'}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def route_duration(route, resolve):
    """Return bounded relative duration only; fixed connections require a solver."""
    low = high = 0
    for segment in route['segments']:
        if 'leg_ref' in segment:
            return {'kind': 'unknown', 'reason': 'execution_leg_requires_connection_evaluation'}
        duration = segment.get('duration')
        if duration is None:
            return {'kind': 'unknown', 'reason': 'missing_segment_duration'}
        low += duration['min_minutes']; high += duration['max_minutes']
    for stop in route['stops']:
        if 'dwell' not in stop:
            return {'kind': 'unknown', 'reason': 'missing_stop_duration'}
        low += stop['dwell']['min_minutes']; high += stop['dwell']['max_minutes']
    return {'kind': 'estimated', 'min_minutes': low, 'max_minutes': high}

def relative_due(due, timing):
    """Do not upgrade estimated/window anchors to a fixed deadline."""
    from datetime import timedelta, timezone
    if timing.get('kind') not in ('fixed', 'estimated') or 'start' not in timing:
        return {'kind': 'unknown', 'reason': 'anchor_not_single_time'}
    value = timing['start']
    dt = datetime.fromisoformat(value['local']).replace(tzinfo=ZoneInfo(value['timezone']))
    if 'offset' in value or dt.replace(fold=0).utcoffset() != dt.replace(fold=1).utcoffset():
        return {'kind': 'unknown', 'reason': 'offset_or_dst_disambiguation_required'}
    if dt.astimezone(timezone.utc).astimezone(dt.tzinfo).replace(tzinfo=None) != datetime.fromisoformat(value['local']):
        return {'kind': 'unknown', 'reason': 'nonexistent_local_time'}
    result = dt.astimezone(timezone.utc) + timedelta(minutes=due['offset_minutes'])
    return {'kind': timing['kind'], 'instant': result.isoformat()}

def coverage_plan_issues(p, resolve):
    """Compare known unit snapshots; do not rewrite either confirmed or planned values."""
    issues = []
    for coverage in p.get('coverages', []):
        for scope in coverage.get('scopes', []):
            target = scope['target_ref']
            if target.get('kind') != 'unit':
                continue
            unit = resolve(target)
            def issue(code):
                issues.append({'code': code, 'coverage_id': coverage['id']})
            confirmed, planned = scope.get('validity', {}), unit.get('period', {})
            if confirmed.get('kind') == planned.get('kind') == 'local_dates' and all(k in v for v in (confirmed, planned) for k in ('check_in', 'check_out', 'timezone')):
                keys = ('check_in', 'check_out', 'timezone')
                if any(confirmed[k] != planned[k] for k in keys): issue('COVERAGE_PERIOD_MISMATCH')
            else:
                issue('COVERAGE_PERIOD_UNKNOWN')
            known, occupants = scope.get('participants', {}), unit.get('occupants', {})
            if 'member_ids' in known and 'member_ids' in occupants:
                if set(known['member_ids']) != set(occupants['member_ids']): issue('COVERAGE_PARTICIPANTS_MISMATCH')
            else:
                issue('COVERAGE_PARTICIPANTS_UNKNOWN')
            quantity = scope.get('quantity', {})
            if quantity.get('unit') == unit.get('kind') and 'count' in quantity and 'count' in unit:
                if quantity['count'] != unit['count']: issue('COVERAGE_QUANTITY_MISMATCH')
            else:
                issue('COVERAGE_QUANTITY_UNKNOWN')
    return issues

def check_package(p, require_example=True):
    require(p.get("schema_version") in ("1.0",), "unsupported schema version")
    require(not require_example or p.get("example") is True, "fixture must declare example")
    objects = {('trip', p['trip']['id']): p['trip']}; ids = {p['trip']['id']}
    for collection, kind in TYPES.items():
        for obj in p.get(collection, []):
            require(obj['id'] not in ids, 'duplicate top-level ID')
            ids.add(obj['id']); objects[kind, obj['id']] = obj
    def resolve(ref):
        require(isinstance(ref, dict), 'reference must be object')
        if 'owner' not in ref:
            require(set(ref) == {'type', 'id'}, 'reference shape')
            require((ref['type'], ref['id']) in objects, 'missing reference')
            return objects[ref['type'], ref['id']]
        require(set(ref) == {'owner', 'kind', 'id'}, 'local reference shape')
        owner = resolve(ref['owner'])
        if ref['kind'] == 'availability_rule':
            rules = [v for s in owner.get('availability', []) for key in ('weekly_rules', 'date_overrides') for v in s.get(key, [])]
            choices = rules + [c for rule in rules for c in rule.get('cutoffs', [])]
        elif ref['kind'] in {'member', 'group'}:
            require(owner is p['trip'], 'member/group owner must be Trip')
            choices = owner.get('party', {}).get(ref['kind'] + 's', [])
        else:
            require(ref['kind'] in LOCAL, 'unknown local reference kind')
            choices = owner.get(LOCAL[ref['kind']], [])
        found = [v for v in choices if v['id'] == ref['id']]
        require(len(found) == 1, 'missing/duplicate local reference')
        return found[0]
    members = {x['id'] for x in p['trip'].get('party', {}).get('members', [])}
    groups = {x['id'] for x in p['trip'].get('party', {}).get('groups', [])}
    def walk(value, field=''):
        if isinstance(value, dict):
            if ((field.endswith('_ref') and field != 'end_from_ref')
                    or ('type' in value and 'id' in value) or 'owner' in value):
                resolve(value)
                if field in FIELD_TYPES:
                    require(value.get('type') in FIELD_TYPES[field], 'wrong target type: ' + field)
            if 'min_minutes' in value:
                require(0 <= value['min_minutes'] <= value['max_minutes'], 'invalid duration range')
            if value.get('kind') in ('fixed', 'estimated', 'window'):
                require(sum(k in value for k in ('end', 'duration', 'duration_from_ref')) <= 1, 'multiple authoritative durations')
            for key, child in value.items():
                if key in {'member_ids', 'driver_member_ids', 'eligible_member_ids'}: require(set(child) <= members and bool(child), 'unknown/empty members')
                if key == 'group_ids': require(set(child) <= groups and bool(child), 'unknown/empty groups')
                if key.endswith('_refs') or key == 'depends_on':
                    for target in child:
                        resolve(target)
                        if key in FIELD_TYPES: require(target.get('type') in FIELD_TYPES[key], 'wrong target type: ' + key)
                walk(child, key)
        elif isinstance(value, list):
            for child in value: walk(child, field)
    walk(p)
    constraint_edges = {}
    for collection, kind in (('items', 'item'), ('activities', 'activity')):
        for obj in p.get(collection, []):
            key = (kind, obj['id'])
            constraints = obj.get('timing', {}).get('constraints', [])
            require(isinstance(constraints, list), 'timing constraints must be array')
            constraint_edges[key] = []
            for constraint in constraints:
                validate_constraint(constraint, resolve)
                if 'relative_to' in constraint:
                    ref = constraint['relative_to']['ref']
                    constraint_edges[key].append((ref['type'], ref['id']))
    checked = set()
    def visit_constraint(key, active):
        require(key not in active, 'relative constraint dependency cycle')
        if key in checked:
            return
        for target in constraint_edges.get(key, []):
            visit_constraint(target, active | {key})
        checked.add(key)
    for key in constraint_edges:
        visit_constraint(key, set())
    time_edges = {}
    for (kind, identifier), obj in objects.items():
        timing = obj.get('timing', {})
        if kind == 'leg' and obj['movement']['kind'] == 'independent':
            timing = obj['movement']['timing']
            require(timing.get('kind') != 'derived', 'independent Leg cannot derive from its owner')
        refs = [timing[field] for field in ('from_ref', 'duration_from_ref') if field in timing]
        if kind == 'activity':
            require(timing.get('kind') != 'derived', 'Activity cannot derive its timing')
        if kind == 'journey':
            refs += obj['leg_refs']
        if kind == 'route':
            refs += [segment['leg_ref'] for segment in obj['segments'] if 'leg_ref' in segment]
        time_edges[kind, identifier] = [(ref['type'], ref['id']) for ref in refs]
    time_checked = set()
    def visit_time(key, active):
        require(key not in active, 'time source dependency cycle')
        if key in time_checked:
            return
        for target in time_edges.get(key, []):
            visit_time(target, active | {key})
        time_checked.add(key)
    if p.get('schema_version') not in ('1.0',):
        for key in time_edges:
            visit_time(key, set())
    item_ids = [r['id'] for day in p['days'] for r in day['item_refs']]
    if p.get('schema_version') == '1.0':
        item_ids += [r['id'] for r in p['trip'].get('unassigned_item_refs', [])]
    require(len(item_ids) == len(set(item_ids)), 'duplicate current Item ownership')
    current_items = {i['id'] for i in p['items'] if i.get('lifecycle', 'current') == 'current'}
    require(set(item_ids) == current_items, 'current/retired Item day ownership')
    for item in p['items']:
        require(item.get('lifecycle', 'current') in ('current', 'retired'), 'invalid Item lifecycle')
        if item['kind'] in SUBJECT_TYPES:
            require(item.get('subject_ref', {}).get('type') == SUBJECT_TYPES[item['kind']], 'wrong Item subject type')
        timing = item['timing']
        if timing.get('kind') == 'derived':
            require(timing['from_ref'] == item.get('subject_ref'), 'derived time must use own subject')
        if 'duration_from_ref' in timing:
            require(item['kind'] in {'route', 'transport', 'activity'} and timing['duration_from_ref'] == item.get('subject_ref'), 'duration source must be own Route/Journey/Activity')
    for collection, item_kind in (('journeys', 'transport'), ('routes', 'route')):
        owners = [i['subject_ref']['id'] for i in p['items'] if i['kind'] == item_kind]
        require(len(owners) == len(set(owners)), 'execution reused by multiple Items')
        owner_items = {i['subject_ref']['id']: i for i in p['items'] if i['kind'] == item_kind}
        for obj in p.get(collection, []):
            lifecycle = obj.get('lifecycle', 'current')
            require(lifecycle in ('current', 'retired'), 'invalid lifecycle')
            owner = owner_items.get(obj['id'])
            require(lifecycle == 'retired' or owner is not None, 'current execution missing Item ownership')
            if owner is not None:
                require(owner.get('lifecycle', 'current') == lifecycle, 'Item/execution lifecycle ownership mismatch')
    leg_ids = [r['id'] for j in p.get('journeys', []) for r in j['leg_refs']]
    leg_ids += [s['leg_ref']['id'] for route in p.get('routes', []) for s in route['segments'] if 'leg_ref' in s]
    require(len(leg_ids) == len(set(leg_ids)), 'Leg has multiple owners')
    require(set(leg_ids) == {x['id'] for x in p.get('legs', [])}, 'unowned Leg')
    for obj in p.get('journeys', []) + p.get('legs', []):
        require('participants' not in obj, 'participants belong to executing Item')
    for route in p.get('routes', []):
        stops = route['stops']; segments = route['segments']
        require(len({s['id'] for s in stops}) == len(stops), 'duplicate Stop')
        require(len(segments) == len(stops)-1, 'wrong segment count')
        for i, segment in enumerate(segments):
            require((segment['from_stop_id'], segment['to_stop_id']) == (stops[i]['id'], stops[i+1]['id']), 'wrong Stop connection')
            if 'leg_ref' in segment:
                require(not set(segment) & {'mode', 'duration', 'path_ref', 'distance_m'}, 'Leg and inline movement conflict')
    for leg in p.get('legs', []):
        movement = leg['movement']
        if movement['kind'] == 'independent':
            require(movement['from_ref'].get('type') in {'place', 'access_point'} and movement['to_ref'].get('type') in {'place', 'access_point'}, 'movement endpoints must be places or access points')
            require(movement['timing'].get('kind') != 'derived', 'independent Leg cannot derive from its owner')
        if movement['kind'] == 'scheduled':
            require(not set(movement) & {'timing', 'from_ref', 'to_ref'}, 'duplicated service time/endpoints')
            calls = resolve(movement['service_ref'])['calls']; keys = [c['id'] for c in calls]
            require(len(keys) == len(set(keys)), 'duplicate Call')
            a, b = keys.index(movement['board_call_id']), keys.index(movement['alight_call_id'])
            require(a < b and 'departure' in calls[a] and 'arrival' in calls[b], 'invalid service calls')
            for value in (calls[a]['departure'], calls[b]['arrival']):
                require(value.get('kind') == 'unknown' or ('local' in value and 'timezone' in value) or (value.get('kind') == 'estimated' and 'value' in value), 'invalid service time')
    for path in p.get('paths', []):
        require(path['kind'] in ('schematic', 'observed_track', 'provider_route', 'authored_route'), 'path kind')
        require(bool(path['parts']), 'empty path')
        for part in path['parts']:
            require(len(part) >= 2, 'short path part')
            for point in part: require(-90 <= point['lat'] <= 90 and -180 <= point['lon'] <= 180, 'coordinate range')
    for media in p.get('media', []):
        usages = media.get('usages', [])
        keys = {(usage['target_ref']['type'], usage['target_ref']['id'],
                 usage['purpose']) for usage in usages}
        require(len(keys) == len(usages), 'duplicate Media usage')
        for usage in usages:
            expected = {'place_intro': 'place', 'trip_overview': 'trip'}[
                usage['purpose']]
            require(usage['target_ref']['type'] == expected,
                    'Media usage purpose/target mismatch')
        if (media.get('creation', {}).get('kind') == 'generated'
                and 'source_ref' in media and p.get('example') is not True):
            require(resolve(media['source_ref'])['kind'] != 'synthetic_fixture',
                    'generated Media cannot use synthetic_fixture as provenance')
    for coverage in p.get('coverages', []):
        require(not set(coverage) & {'target_refs', 'participants', 'validity'}, 'legacy mutable coverage shape')
        require(bool(coverage.get('scopes')), 'missing coverage scopes')
        scope_ids = set()
        for scope in coverage['scopes']:
            require({'id', 'target_ref', 'validity', 'participants', 'quantity'} <= set(scope), 'incomplete coverage snapshot')
            require(scope['id'] not in scope_ids, 'duplicate scope')
            scope_ids.add(scope['id'])
            require('group_ids' not in scope['participants'], 'confirmed scope must not inherit mutable group')
            require('from_ref' not in scope['validity'], 'confirmed scope must not inherit plan period')
    for payment in p.get('payments', []):
        if payment['direction'] == 'refund':
            require(resolve(payment['original_payment_ref'])['direction'] == 'payment', 'refund must refer to payment')
        if payment['status'] == 'settled':
            require('settled_at' in payment and ('record_note' in payment or 'evidence_refs' in payment), 'settled payment evidence')
    for place in p.get('places', []):
        for schedule in place.get('availability', []):
            for rule in schedule.get('date_overrides', []) + schedule.get('weekly_rules', []):
                if 'adopted_claim_ref' in rule:
                    claim = resolve(rule['adopted_claim_ref']); target = claim['target']
                    require(claim.get('disposition') == 'adopted', 'claim is not adopted')
                    require(target['object_ref'] == target['local_ref']['owner'], 'claim owner mismatch')
                    require(resolve(target['local_ref']) is rule, 'claim local target mismatch')
                    require(target['field'] in rule and claim['value'] == rule[target['field']], 'claim value/field mismatch')
    def visit_task(tid, active):
        require(tid not in active, 'task dependency cycle')
        for dep in objects['task', tid].get('depends_on', []): visit_task(dep['id'], active | {tid})
    for task in p.get('tasks', []): visit_task(task['id'], set())
    return resolve
