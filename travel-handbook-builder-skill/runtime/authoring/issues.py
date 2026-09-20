"""Bounded OpenIssue creation and monotonic resolution for schema 1.0."""
import copy

from .errors import fail, nonempty
from .reservations import require_record_origin


ISSUE_VERSIONS = {'1.0'}
CLAIM_BASES = {
    'user_statement', 'confirmation', 'official', 'observation',
    'estimate', 'synthetic_fixture', 'other',
}


def require_issue_version(editor):
    if editor.package.get('schema_version') not in ISSUE_VERSIONS:
        fail('SCHEMA_VERSION_UNSUPPORTED', 'Issue authoring requires schema version 1.0',
             supported_version='1.0')


def require_issue_resolution_origin(origin, *, example):
    require_record_origin(origin, example=example)
    if not isinstance(origin.get('basis'), str) or origin['basis'] not in CLAIM_BASES:
        fail('INVALID_ARGUMENT', 'Unknown origin basis', parameter='origin.basis')


def issue_record(editor, *, title, targets, impact, resolution_needed=None):
    require_issue_version(editor)
    nonempty(title, 'title')
    nonempty(impact, 'impact')
    if not isinstance(targets, list) or not targets:
        fail('INVALID_ARGUMENT', 'targets must be a nonempty list of Place handles',
             parameter='targets')
    refs = []
    for index, target in enumerate(targets):
        ref = editor.ref(target, {'place'})
        if ref in refs:
            fail('INVALID_ARGUMENT', 'Issue targets must be unique',
                 parameter=f'targets[{index}]')
        refs.append(ref)
    fields = {'title': title, 'target_refs': refs, 'status': 'open', 'impact': impact}
    if resolution_needed is not None:
        nonempty(resolution_needed, 'resolution_needed')
        fields['resolution_needed'] = resolution_needed
    return editor.add('issue', fields)


def issue_resolve(editor, *, target, resolution_note):
    require_issue_version(editor)
    nonempty(resolution_note, 'resolution_note')
    handle = editor.handle(target)
    issue = editor.record(handle, {'issue'})
    issue_ref = editor.ref(handle, {'issue'})
    proposed = {
        'resolution_note': resolution_note,
        'origin': copy.deepcopy(editor.operation_origin),
    }
    resolutions = editor.state.setdefault('issue_resolutions', {})
    if not isinstance(resolutions, dict):
        fail('STATE_FORMAT', 'Issue resolution metadata must be an object')
    if issue['status'] == 'resolved':
        existing = resolutions.get(issue_ref['id'])
        if existing is None or any(existing.get(field) != value
                                   for field, value in proposed.items()):
            fail('ISSUE_ALREADY_RESOLVED',
                 'Issue is already resolved with a different explicit record')
        claim_ref = existing.get('status_claim_ref')
        claim_handle = next((value for value, ref in editor.state['handles'].items()
                             if ref == claim_ref), None)
        if claim_handle is None:
            fail('STATE_FORMAT', 'Resolved Issue status Claim handle is missing')
        editor.parts['resolution_note'] = resolution_note
        editor.parts['status_claim'] = {'handle': claim_handle}
        editor.parts['already_resolved'] = True
        editor.parts['_skip_origin_claim'] = True
        return handle
    if issue['status'] != 'open':
        fail('STATE_FORMAT', 'Issue status must be open or resolved')
    issue['status'] = 'resolved'
    editor.parts['resolution_note'] = resolution_note
    editor.parts['_issue_status_claim'] = proposed
    return handle
