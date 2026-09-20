"""Movement input normalization; no route finding or inferred geography."""
import copy
import math
from .errors import fail, nonempty

MODES = ('walking', 'cycling', 'driving', 'taxi', 'bus', 'rail', 'metro', 'tram', 'air', 'ferry', 'other')


def validate_mode(mode, mode_label=None):
    if mode not in MODES:
        fail('INVALID_ARGUMENT', 'Choose an explicit transport mode', parameter='mode')
    if mode == 'other':
        nonempty(mode_label, 'mode_label')
    elif mode_label is not None:
        fail('INVALID_ARGUMENT', 'mode_label is only for other mode', parameter='mode_label')


def number(value, parameter):
    if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)) or value < 0:
        fail('INVALID_ARGUMENT', 'Expected a finite nonnegative number', parameter=parameter)
    return value


def duration(value, parameter):
    bounds = value if isinstance(value, list) else [value, value]
    if len(bounds) != 2:
        fail('INVALID_ARGUMENT', 'Duration is minutes or [minimum, maximum]', parameter=parameter)
    low, high = [number(n, parameter) for n in bounds]
    if low > high:
        fail('INVALID_ARGUMENT', 'Duration minimum exceeds maximum', parameter=parameter)
    return {'min_minutes': low, 'max_minutes': high}


def attach_path(editor, fields, path_ref_input):
    path = editor.record(path_ref_input, {'path'})
    if path.get('mode') != fields['mode'] or path.get('mode_label') != fields.get('mode_label'):
        fail('PATH_MODE_MISMATCH', 'Path mode must match the segment or leg')
    fields['path_ref'] = editor.ref(path_ref_input, {'path'})


def path_change_blockers(package, target_ref):
    """Find adopted execution claims that protect one Segment/Leg path_ref."""
    blockers = []
    for claim in package.get('claims', []):
        target = claim.get('target', {})
        if target.get('field') != 'path_ref':
            continue
        if 'owner' in target_ref:
            matches = (target.get('object_ref') == target_ref['owner']
                       and target.get('local_ref') == target_ref)
        else:
            matches = (target.get('object_ref') == target_ref
                       and 'local_ref' not in target)
        if (matches and claim.get('basis') in {'confirmation', 'observation'}
                and claim.get('disposition', 'adopted') == 'adopted'):
            blockers.append({'kind': 'claim',
                             'ref': {'type': 'claim', 'id': claim['id']}})
    return blockers


def protect_path_change(editor, target_ref, current, proposed, parameter):
    """Reject only a real change; exact reattachment remains an idempotent no-op."""
    if current == proposed:
        return
    blockers = path_change_blockers(editor.package, target_ref)
    if blockers:
        fail('PLAN_PATH_CHANGE_BLOCKED',
             'An adopted confirmation or observation protects this path reference',
             parameter=parameter, target_ref=copy.deepcopy(target_ref),
             current_path_ref=copy.deepcopy(current),
             proposed_path_ref=copy.deepcopy(proposed), blockers=blockers,
             blocker_refs=[copy.deepcopy(value['ref']) for value in blockers])


def replace_path(editor, fields, path_ref_input, target_ref, parameter):
    """Bind one Path atomically and reset direction only for a new Path."""
    current = fields.get('path_ref')
    candidate = copy.deepcopy(fields)
    attach_path(editor, candidate, path_ref_input)
    proposed = candidate['path_ref']
    protect_path_change(editor, target_ref, current, proposed, parameter)
    fields['path_ref'] = proposed
    if current != proposed:
        fields.pop('path_direction', None)
