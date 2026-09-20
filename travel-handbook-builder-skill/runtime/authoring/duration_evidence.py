"""Value-bound author statements for route dwell and segment duration."""
import copy
from .errors import fail, nonempty
from .movement import duration

BASES = ('user_statement', 'confirmation', 'official', 'observation', 'estimate', 'synthetic_fixture', 'other')


def duration_input(value, parameter):
    if not isinstance(value, dict):
        return duration(value, parameter), None
    if set(value) != {'minutes', 'basis', 'statement'}:
        fail('INVALID_ARGUMENT', 'Duration evidence requires minutes, basis and statement only', parameter=parameter)
    if value['basis'] not in BASES:
        fail('INVALID_ARGUMENT', 'Unknown statement basis', parameter=parameter + '.basis')
    nonempty(value['statement'], parameter + '.statement')
    normalized = duration(value['minutes'], parameter + '.minutes')
    return normalized, {'basis': value['basis'], 'statement': value['statement']}


def update_duration_evidence(editor, handle, field, old_value, new_value, origin, *, source_ref=None, force_new=False):
    if editor.package['schema_version'] not in ('1.0',):
        if origin is not None:
            fail('SCHEMA_VERSION_UNSUPPORTED', 'Duration evidence authoring requires schema version 1.0')
        return
    reference = editor.ref(handle)
    target = {'object_ref': reference['owner'], 'local_ref': reference, 'field': field}
    active = [claim for claim in editor.package.get('claims', [])
              if claim['target'] == target and claim.get('disposition') == 'adopted']
    if len(active) > 1:
        fail('EVIDENCE_CONFLICT', 'Multiple adopted statements require explicit resolution')
    if origin is None and old_value == new_value:
        return
    evidence_fields = {**origin, 'value': copy.deepcopy(new_value)} if origin is not None else {}
    if source_ref is not None:
        evidence_fields['source_refs'] = [copy.deepcopy(source_ref)]
    if not force_new and origin is not None and active and all(active[0].get(key) == value for key, value in evidence_fields.items()):
        return
    for claim in active:
        claim['disposition'] = 'superseded'
    if origin is not None:
        evidence = editor.add('claim', {'target': target, **evidence_fields, 'disposition': 'adopted'})
        editor.parts.setdefault('duration_evidence', []).append({
            'target': editor.handle(handle), 'field': field, 'claim': evidence})
