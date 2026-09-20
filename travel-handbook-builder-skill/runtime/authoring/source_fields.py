"""Candidate R13 typed source-field adoption and conflict resolution."""
import copy
import hmac

from .coordinates import validate_coordinate_inputs
from .duration_evidence import BASES
from .errors import AuthoringError, fail, nonempty
from .execution_replacements import require_execution_edit_version
from .movement import duration
from .routes import route_edit
from .source_refresh import locate, signature, store
from .source_topology import (
    _handle_for_ref, _identity, bind_target_identity,
    sync_topology_field_baseline,
)
from .time_plans import normalize_time_plan


ASPECT_TYPES = {
    'item.timing': 'item',
    'item.place_ref': 'item',
    'place.location': 'place',
    'stop.dwell': 'stop',
    'segment.duration': 'segment',
    'segment.path': 'segment',
    'leg.timing': 'leg',
}


def _claim_target(target_ref, aspect):
    fields = {
        'item.timing': 'timing',
        'item.place_ref': 'place_ref',
        'place.location': 'location',
        'stop.dwell': 'dwell',
        'segment.duration': 'duration',
        'segment.path': 'path_ref',
        'leg.timing': 'timing',
    }
    target = {'object_ref': (target_ref['owner']
                             if 'owner' in target_ref else target_ref),
              'field': fields[aspect]}
    if 'owner' in target_ref:
        target['local_ref'] = target_ref
    return target


def _active_claim(editor, target):
    claims = [claim for claim in editor.package.get('claims', [])
              if claim.get('target') == target
              and claim.get('disposition', 'adopted') == 'adopted']
    if len(claims) > 1:
        fail('EVIDENCE_CONFLICT',
             'Multiple adopted statements prevent deterministic source comparison',
             target=copy.deepcopy(target))
    return claims[0] if claims else None


def _view(editor, target_ref, aspect):
    record = editor.record(_handle_for_ref(editor, target_ref))
    if aspect == 'item.timing':
        present, value = 'timing' in record, record.get('timing')
    elif aspect == 'item.place_ref':
        present, value = 'place_ref' in record, record.get('place_ref')
    elif aspect == 'place.location':
        present, value = 'location' in record, record.get('location')
    elif aspect == 'stop.dwell':
        present, value = 'dwell' in record, record.get('dwell')
    elif aspect == 'segment.duration':
        present, value = 'duration' in record, record.get('duration')
    elif aspect == 'segment.path':
        present, value = 'path_ref' in record, record.get('path_ref')
    else:
        movement = record.get('movement', {})
        present, value = 'timing' in movement, movement.get('timing')
    claim = _active_claim(editor, _claim_target(target_ref, aspect))
    evidence = None if claim is None else {
        key: copy.deepcopy(claim[key]) for key in
        ('basis', 'statement', 'value', 'source_refs') if key in claim
    }
    return {'present': present, 'value': copy.deepcopy(value),
            'evidence': evidence}


def _normalize_value(editor, aspect, value):
    if aspect in {'stop.dwell', 'segment.duration'}:
        return duration(value, 'value')
    if aspect in {'item.timing', 'leg.timing'}:
        return normalize_time_plan(editor, value, 'value')
    if aspect == 'item.place_ref':
        return editor.ref(value, {'place'})
    if aspect == 'place.location':
        validate_coordinate_inputs('place.update', {'set': {'location': value}})
        if not isinstance(value, dict):
            fail('INVALID_ARGUMENT', 'Location must be an object',
                 parameter='value')
        return copy.deepcopy(value)
    return editor.ref(value, {'path'})


def _proposal(editor, anchor, aspect, value, basis, document_key=None):
    if basis not in BASES:
        fail('INVALID_ARGUMENT', 'Unknown statement basis', parameter='basis')
    snapshot, normalized = locate(
        editor, anchor, document_key=document_key)
    return {
        'document_key': snapshot['document_key'],
        'document_sequence': snapshot['sequence'],
        'anchor': normalized,
        'value': _normalize_value(editor, aspect, value),
        'basis': basis,
        'statement': normalized['exact_text'],
        'source_ref': editor.ref(normalized['source'], {'source'}),
    }


def _history_value(proposal):
    return {key: copy.deepcopy(proposal[key]) for key in
            ('value', 'basis', 'statement', 'source_ref')}


def _same_content(view, proposal):
    evidence = view['evidence']
    return (
        view['present'] and view['value'] == proposal['value']
        and evidence is not None
        and evidence.get('basis') == proposal['basis']
        and evidence.get('statement') == proposal['statement']
        and evidence.get('value') == proposal['value']
        and evidence.get('source_refs') == [proposal['source_ref']]
    )


def _replace_claim(editor, target_ref, aspect, proposal):
    target = _claim_target(target_ref, aspect)
    active = [claim for claim in editor.package.get('claims', [])
              if claim.get('target') == target
              and claim.get('disposition', 'adopted') == 'adopted']
    fields = {
        'basis': proposal['basis'],
        'statement': proposal['statement'],
        'value': copy.deepcopy(proposal['value']),
        'source_refs': [copy.deepcopy(proposal['source_ref'])],
    }
    if (len(active) == 1
            and all(active[0].get(key) == value
                    for key, value in fields.items())):
        return
    for claim in active:
        claim['disposition'] = 'superseded'
    evidence = editor.add('claim', {
        'target': target, **fields, 'disposition': 'adopted'})
    editor.parts.setdefault('source_evidence', []).append(evidence)


def _segment_for_leg(editor, leg_ref):
    matches = []
    for route in editor.package.get('routes', []):
        owner = {'type': 'route', 'id': route['id']}
        matches.extend(
            {'owner': owner, 'kind': 'segment', 'id': segment['id']}
            for segment in route.get('segments', [])
            if segment.get('leg_ref') == leg_ref)
    if len(matches) != 1:
        fail('UNSUPPORTED_VARIANT',
             'Leg timing adoption requires exactly one current Route Segment',
             target_ref=copy.deepcopy(leg_ref),
             current_route_segment_count=len(matches))
    return _handle_for_ref(editor, matches[0])


def _item_for_route(editor, route_ref):
    matches = [
        {'type': 'item', 'id': item['id']}
        for item in editor.package.get('items', [])
        if item.get('kind') == 'route'
        and item.get('lifecycle', 'current') == 'current'
        and item.get('subject_ref') == route_ref
    ]
    if len(matches) != 1:
        fail('REFERENCE_NOT_FOUND',
             'Source field Route owner has no unique current Item',
             route_ref=copy.deepcopy(route_ref),
             current_item_count=len(matches))
    return _handle_for_ref(editor, matches[0])


def _write(editor, binding, proposal):
    target_ref = binding['target_ref']
    target = _handle_for_ref(editor, target_ref)
    aspect, value = binding['aspect'], proposal['value']
    if aspect == 'item.timing':
        editor.plan_update(target=target, set={'timing': value})
    elif aspect == 'item.place_ref':
        editor.plan_update(
            target=target, set={'place': _handle_for_ref(editor, value)})
    elif aspect == 'place.location':
        editor.place_update(target=target, set={'location': value})
    elif aspect in {'stop.dwell', 'segment.duration'}:
        kind = 'stop' if aspect == 'stop.dwell' else 'segment'
        parameter = 'dwell_minutes' if kind == 'stop' else 'duration_minutes'
        route_edit(
            editor, target=_item_for_route(editor, target_ref['owner']),
            edits=[{'action': 'set_' + kind, 'target': target, 'set': {
                parameter: {
                    'minutes': [value['min_minutes'], value['max_minutes']],
                    'basis': proposal['basis'],
                    'statement': proposal['statement'],
                }}}])
    elif aspect == 'segment.path':
        # A prior source-owned observation is the baseline this explicit source
        # action is replacing.  Retire only that exact Claim before delegating
        # to route.edit; unrelated/manual path protection remains active.
        current = _view(editor, target_ref, aspect)
        if (current['value'] != value and binding.get('last_adopted')
                and current == binding.get('baseline')
                and (current.get('evidence') or {}).get('source_refs')):
            claim = _active_claim(
                editor, _claim_target(target_ref, aspect))
            if claim is not None:
                claim['disposition'] = 'superseded'
        route_edit(
            editor, target=_item_for_route(editor, target_ref['owner']),
            edits=[{'action': 'set_segment', 'target': target,
                    'set': {'path': _handle_for_ref(editor, value)}}])
    elif aspect == 'leg.timing':
        segment = _segment_for_leg(editor, target_ref)
        route_edit(
            editor,
            target=_item_for_route(editor, editor.ref(segment)['owner']),
            edits=[{'action': 'set_leg_timing', 'target': segment,
                    'timing': value}])
    _replace_claim(editor, target_ref, aspect, proposal)
    binding['baseline'] = _view(editor, target_ref, aspect)
    binding['last_adopted'] = copy.deepcopy(proposal)
    binding.pop('handled', None)
    synced = sync_topology_field_baseline(editor, target_ref, aspect)
    if synced:
        editor.parts.setdefault('topology_baseline_updates', []).extend(synced)


def _append_history(editor, binding, proposal, outcome, reason=None):
    entries = store(editor)['field_proposal_history'].setdefault(
        binding['id'], [])
    entry = {
        'proposal_sequence': len(entries) + 1,
        'document_sequence': proposal['document_sequence'],
        'anchor': copy.deepcopy(proposal['anchor']),
        'proposal': _history_value(proposal),
        'outcome': outcome,
    }
    if reason is not None:
        entry['reason'] = reason
    entries.append(entry)


def _returns_to_old(binding, proposal, data):
    entries = data['field_proposal_history'].get(binding['id'], [])
    # A new snapshot still returns to an old business proposal when the value
    # and basis return to A after B.  The statement/source remain in history
    # for audit but do not let a higher sequence silently bypass A→B→A review.
    proposed = {key: copy.deepcopy(proposal[key])
                for key in ('value', 'basis')}
    adopted = [
        {key: copy.deepcopy(entry['proposal'][key])
         for key in ('value', 'basis')}
        for entry in entries
        if entry['outcome'] in {'adopted', 'already_matches'}
    ]
    return bool(adopted and adopted[-1] != proposed
                and any(entry == proposed for entry in adopted[:-1]))


def _payload(editor, binding, proposal, *, history_return=False):
    return {
        'workspace_id': editor.state['workspace_id'],
        'revision': editor.state['revision'],
        'binding_id': binding['id'],
        'baseline': copy.deepcopy(binding['baseline']),
        'current': _view(editor, binding['target_ref'], binding['aspect']),
        'proposal': copy.deepcopy(proposal),
        'history_return': history_return,
    }


def _issued_conflict(editor, binding, proposal, *, history_return=False):
    payload = _payload(
        editor, binding, proposal, history_return=history_return)
    return {'payload': payload, 'signature': signature(store(editor), payload)}


def _binding_for(data, identity_id, aspect):
    return next((binding for binding in data['field_bindings'].values()
                 if binding['identity_id'] == identity_id
                 and binding['aspect'] == aspect), None)


def _assert_unbound(editor, data, target_ref, aspect):
    duplicate = next((binding for binding in data['field_bindings'].values()
                      if binding['target_ref'] == target_ref
                      and binding['aspect'] == aspect), None)
    if duplicate is not None:
        fail('FIELD_ALREADY_BOUND',
             'This field already belongs to another source identity binding',
             binding_id=duplicate['id'])
    if aspect in {'stop.dwell', 'segment.duration'}:
        target_handle = _handle_for_ref(editor, target_ref)
        old_field = aspect.split('.', 1)[1]
        for old in data.get('bindings', {}).values():
            if old.get('part') == target_handle and old.get('field') == old_field:
                fail('FIELD_ALREADY_BOUND',
                     'This duration already has a source.duration binding',
                     binding_id=old['id'])


def source_field_apply(editor, *, anchor, identity_key, aspect, value, basis,
                       target=None, occurrence=None):
    require_execution_edit_version(editor)
    nonempty(identity_key, 'identity_key')
    if aspect not in ASPECT_TYPES:
        fail('INVALID_ARGUMENT', 'Unsupported source field aspect',
             parameter='aspect')
    snapshot, normalized_anchor = locate(editor, anchor)
    data = store(editor)
    identity = _identity(data, snapshot['document_key'], identity_key)
    if identity is None:
        if target is None:
            fail('INVALID_ARGUMENT',
                 'First field adoption requires target and occurrence',
                 parameter='target')
        identity, target_handle, _ = bind_target_identity(
            editor, document_key=snapshot['document_key'],
            anchor=normalized_anchor, semantic_key=identity_key,
            target=target, occurrence=occurrence,
            expected_type=ASPECT_TYPES[aspect])
    else:
        if identity['status'] != 'active':
            fail('SOURCE_IDENTITY_HISTORY_CONFLICT',
                 'A tombstoned source identity has no writable field',
                 document_key=snapshot['document_key'],
                 semantic_key=identity_key, identity_id=identity['id'])
        if identity['object_type'] != ASPECT_TYPES[aspect]:
            fail('SOURCE_IDENTITY_CONFLICT',
                 'Source identity type does not support this field aspect',
                 semantic_key=identity_key,
                 stored_type=identity['object_type'], aspect=aspect)
        target_handle = _handle_for_ref(editor, identity['target_ref'])
        if target is not None and editor.ref(target) != identity['target_ref']:
            fail('SOURCE_IDENTITY_CONFLICT',
                 'Source identity target is immutable',
                 semantic_key=identity_key,
                 stored_target_ref=copy.deepcopy(identity['target_ref']),
                 proposed_target_ref=editor.ref(target))
        if occurrence is not None and occurrence != identity['occurrence_role']:
            fail('SOURCE_IDENTITY_CONFLICT',
                 'Source identity occurrence is immutable',
                 semantic_key=identity_key,
                 stored_occurrence=identity['occurrence_role'],
                 proposed_occurrence=occurrence)

    proposal = _proposal(
        editor, anchor, aspect, value, basis, snapshot['document_key'])
    binding = _binding_for(data, identity['id'], aspect)
    if binding is None:
        _assert_unbound(editor, data, identity['target_ref'], aspect)
        binding = {
            'id': 'field-' + editor.allocate_id(),
            'document_key': snapshot['document_key'],
            'identity_id': identity['id'],
            'semantic_key': identity_key,
            'target': target_handle,
            'target_ref': copy.deepcopy(identity['target_ref']),
            'aspect': aspect,
            'baseline': _view(editor, identity['target_ref'], aspect),
        }
        data['field_bindings'][binding['id']] = binding
        _write(editor, binding, proposal)
        outcome = 'adopted'
    else:
        current = _view(editor, binding['target_ref'], aspect)
        handled = binding.get('handled')
        if (handled is not None
                and handled['proposal'] == _history_value(proposal)
                and handled['current'] == current):
            outcome = handled['outcome']
        elif _returns_to_old(binding, proposal, data):
            fail('SOURCE_PROPOSAL_HISTORY_CONFLICT',
                 'A higher source sequence cannot automatically restore an older field proposal',
                 binding_id=binding['id'], aspect=aspect,
                 conflict=_issued_conflict(
                     editor, binding, proposal, history_return=True))
        elif _same_content(current, proposal):
            binding['baseline'] = copy.deepcopy(current)
            binding['last_adopted'] = copy.deepcopy(proposal)
            binding.pop('handled', None)
            synced = sync_topology_field_baseline(
                editor, binding['target_ref'], aspect)
            if synced:
                editor.parts.setdefault(
                    'topology_baseline_updates', []).extend(synced)
            outcome = 'already_matches'
        elif current == binding['baseline']:
            _write(editor, binding, proposal)
            outcome = 'adopted'
        else:
            fail('SOURCE_FIELD_CONFLICT',
                 'Current value or evidence differs from the last source field write',
                 binding_id=binding['id'], aspect=aspect,
                 conflict=_issued_conflict(editor, binding, proposal))
    _append_history(editor, binding, proposal, outcome)
    editor.parts['binding_id'] = binding['id']
    editor.parts['identity_id'] = identity['id']
    editor.parts['source_outcome'] = outcome
    editor.parts['aspect'] = aspect
    return target_handle


def _get_conflict(editor, conflict):
    if not isinstance(conflict, dict) or set(conflict) != {'payload', 'signature'}:
        fail('INVALID_CONFLICT',
             'Use the conflict returned by source.field.apply unchanged')
    payload, provided = conflict['payload'], conflict['signature']
    data = store(editor)
    if (not isinstance(payload, dict) or not isinstance(provided, str)
            or not hmac.compare_digest(signature(data, payload), provided)):
        fail('INVALID_CONFLICT',
             'Conflict was not issued by this workspace or has been changed')
    if (payload.get('workspace_id') != editor.state['workspace_id']
            or payload.get('revision') != editor.state['revision']):
        fail('STALE_CONFLICT', 'Workspace changed since this conflict; apply again')
    binding = data['field_bindings'].get(payload.get('binding_id'))
    if binding is None:
        fail('BINDING_NOT_FOUND', 'Source field binding no longer exists')
    try:
        locate(editor, payload['proposal']['anchor'],
               document_key=binding['document_key'])
    except AuthoringError as error:
        if error.code == 'STALE_SOURCE_SNAPSHOT':
            fail('STALE_CONFLICT',
                 'A newer snapshot for this source document exists; apply again')
        raise
    if _payload(editor, binding, payload['proposal'],
                history_return=payload.get('history_return', False)) != payload:
        fail('STALE_CONFLICT',
             'Binding, source proposal or current field changed; apply again')
    return binding, payload['proposal']


def source_field_resolve(editor, *, conflict, choice, reason):
    require_execution_edit_version(editor)
    if choice not in {'apply_proposed', 'keep_current'}:
        fail('INVALID_ARGUMENT', 'Choose apply_proposed or keep_current',
             parameter='choice')
    nonempty(reason, 'reason')
    binding, proposal = _get_conflict(editor, conflict)
    data = store(editor)
    if choice == 'apply_proposed':
        _write(editor, binding, proposal)
        outcome = 'adopted'
    else:
        current = _view(editor, binding['target_ref'], binding['aspect'])
        binding['handled'] = {
            'proposal': _history_value(proposal),
            'current': copy.deepcopy(current),
            'outcome': 'kept_current',
        }
        synced = sync_topology_field_baseline(
            editor, binding['target_ref'], binding['aspect'])
        if synced:
            editor.parts.setdefault(
                'topology_baseline_updates', []).extend(synced)
        outcome = 'kept_current'
    decision = {
        'id': 'field-decision-' + editor.allocate_id(),
        'binding_id': binding['id'],
        'choice': choice,
        'reason': reason,
        'proposal': _history_value(proposal),
        'current': _view(editor, binding['target_ref'], binding['aspect']),
    }
    data['field_decisions'].append(decision)
    _append_history(editor, binding, proposal, outcome, reason=reason)
    editor.parts['binding_id'] = binding['id']
    editor.parts['decision_id'] = decision['id']
    editor.parts['source_outcome'] = outcome
    editor.parts['aspect'] = binding['aspect']
    return _handle_for_ref(editor, binding['target_ref'])
