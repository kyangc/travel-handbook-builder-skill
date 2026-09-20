"""Pure bounded coverage-history invariants and current-state projection."""

def aggregate_state(scopes):
    states = [scope['state'] for scope in scopes]
    if 'active' in states:
        return 'active'
    return 'revoked' if all(state == 'revoked' for state in states) else 'expired'


def coverage_revision_errors(package):
    """Checks used by both standalone validation and the authoring projection."""
    if package.get('schema_version') not in ('1.0',):
        return []
    records = package.get('coverages', [])
    by_id = {record['id']: record for record in records}
    successors, errors = {}, []

    def error(code, path, message):
        errors.append({'code': code, 'path': path, 'message': message})

    for index, record in enumerate(records):
        path = f'/coverages/{index}'
        if record['state'] != aggregate_state(record['scopes']):
            error('COVERAGE_AGGREGATE_STATE', path + '/state', 'Overall state must summarize scope states: active first, all revoked, otherwise expired')
        previous_ref = record.get('supersedes_ref')
        if previous_ref is None:
            if any('previous_scope_id' in scope for scope in record['scopes']):
                error('COVERAGE_SCOPE_LINEAGE', path + '/scopes', 'An initial confirmation has no predecessor scopes')
            continue
        previous = by_id.get(previous_ref.get('id')) if previous_ref.get('type') == 'coverage' else None
        if previous is None:
            error('COVERAGE_PREDECESSOR', path + '/supersedes_ref', 'Predecessor must be an existing Coverage')
            continue
        predecessor_id = previous['id']
        if predecessor_id in successors:
            error('COVERAGE_FORK', path + '/supersedes_ref', 'A confirmation may have only one direct successor')
        successors[predecessor_id] = record['id']
        if previous['state'] != 'active':
            error('COVERAGE_PREDECESSOR_STATE', path + '/supersedes_ref', 'This slice cannot revise an ended entitlement')
        if record.get('reservation_ref') != previous.get('reservation_ref'):
            error('COVERAGE_RESERVATION_CHANGED', path + '/reservation_ref', 'A confirmation chain cannot switch orders')
        old_scopes = {scope['id']: scope for scope in previous['scopes']}
        linked = []
        for sindex, scope in enumerate(record['scopes']):
            spath = path + f'/scopes/{sindex}'
            old_id = scope.get('previous_scope_id')
            old = old_scopes.get(old_id)
            linked.append(old_id)
            if old is None:
                error('COVERAGE_SCOPE_LINEAGE', spath, 'Each new scope must identify a scope in its direct predecessor')
                continue
            if scope['id'] == old_id:
                error('COVERAGE_SCOPE_ID_REUSED', spath + '/id', 'A snapshot needs a new scope ID; old references remain historical')
            if scope['target_ref'] != old['target_ref']:
                error('COVERAGE_SCOPE_TARGET_CHANGED', spath + '/target_ref', 'Changing execution applicability is outside confirmation replacement')
            if old['state'] != 'active' and scope['state'] != old['state']:
                error('COVERAGE_SCOPE_REACTIVATED', spath + '/state', 'An ended scope cannot be reactivated or reclassified in this slice')
        if len(linked) != len(old_scopes) or len(set(linked)) != len(linked) or set(linked) != set(old_scopes):
            error('COVERAGE_SCOPE_LINEAGE', path + '/scopes', 'Successor scopes must map one-to-one onto every predecessor scope')
    for index, record in enumerate(records):
        seen, current = set(), record
        while current is not None and 'supersedes_ref' in current:
            if current['id'] in seen:
                error('COVERAGE_CYCLE', f'/coverages/{index}/supersedes_ref', 'Confirmation chains must be acyclic')
                break
            seen.add(current['id'])
            current = by_id.get(current['supersedes_ref'].get('id'))
    return errors


def coverage_projection(package):
    """Current confirmation heads and explicitly active scopes; never sum quota.

    These are recorded states, not a clock-based expiry or ticket-usability test.
    The complete package remains the historical record.
    """
    errors = coverage_revision_errors(package)
    if errors:
        raise ValueError('Invalid coverage confirmation history')
    records = package.get('coverages', [])
    historical = {record['supersedes_ref']['id'] for record in records if 'supersedes_ref' in record}
    current = [record for record in records if record['id'] not in historical]
    return {'current_coverage_ids': [record['id'] for record in current],
            'historical_coverage_ids': [record['id'] for record in records if record['id'] in historical],
            'effective_scopes': [
                {'coverage_ref': {'type': 'coverage', 'id': record['id']},
                 'scope_ref': {'owner': {'type': 'coverage', 'id': record['id']}, 'kind': 'scope', 'id': scope['id']}}
                for record in current for scope in record['scopes']
                if record['state'] == 'active' and scope.get('state', record['state']) == 'active']}
