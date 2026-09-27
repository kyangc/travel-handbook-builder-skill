"""Explicit image metadata and reusable Trip/Place usage relationships."""
import copy

from .errors import fail, nonempty
from url_checks import local_media_locator, web_url


REPRESENTATIONS = {'photo', 'illustration', 'schematic'}
PURPOSE_TARGETS = {'place_intro': 'place', 'trip_overview': 'trip'}


def _require_current_schema(editor):
    if editor.package.get('schema_version') not in {'1.0'}:
        fail('SCHEMA_VERSION_UNSUPPORTED',
             'Media authoring requires schema version 1.0',
             supported_version='1.0')


def _creation(value):
    if value is None:
        return None
    if (not isinstance(value, dict)
            or not isinstance(value.get('kind'), str)
            or value.get('kind') not in {'captured', 'generated'}):
        fail('INVALID_ARGUMENT',
             'creation must be captured or generated with an explicit generator',
             parameter='creation')
    if value['kind'] == 'captured':
        if set(value) != {'kind'}:
            fail('INVALID_ARGUMENT', 'captured creation only accepts kind',
                 parameter='creation')
    elif set(value) != {'kind', 'generator'}:
        fail('INVALID_ARGUMENT',
             'generated creation requires kind and generator only',
             parameter='creation')
    if value['kind'] == 'generated':
        nonempty(value['generator'], 'creation.generator')
    return copy.deepcopy(value)


def _usage(editor, value, parameter='usage'):
    if not isinstance(value, dict) or set(value) != {'target', 'purpose'}:
        fail('INVALID_ARGUMENT', 'Media usage requires target and purpose only',
             parameter=parameter)
    purpose = value['purpose']
    if not isinstance(purpose, str) or purpose not in PURPOSE_TARGETS:
        fail('INVALID_ARGUMENT', 'Unknown Media usage purpose',
             parameter=f'{parameter}.purpose')
    target_ref = editor.ref(value['target'], {'trip', 'place'})
    expected = PURPOSE_TARGETS[purpose]
    if target_ref['type'] != expected:
        fail('MEDIA_USAGE_TARGET_MISMATCH',
             f'{purpose} requires a {expected} target',
             parameter=f'{parameter}.target', purpose=purpose,
             expected_type=expected, actual_type=target_ref['type'])
    return {'target_ref': target_ref, 'purpose': purpose}


def _source(editor, value, creation):
    if value is None:
        return None
    source_ref = editor.ref(value, {'source'})
    source = editor.record(value, {'source'})
    if (creation is not None and creation['kind'] == 'generated'
            and source['kind'] == 'synthetic_fixture'
            and editor.package.get('example') is not True):
        fail('MEDIA_GENERATED_SOURCE_CONFLICT',
             'A real generated asset cannot use synthetic_fixture as its provenance',
             parameter='source')
    return source_ref


def media_image_add(editor, *, locator, alt, representation, creation=None,
                    source=None, usage_rights=None, captured_at=None,
                    caption=None, usages=None):
    _require_current_schema(editor)
    nonempty(locator, 'locator')
    if not (web_url(locator, image=True) or local_media_locator(locator)):
        fail('INVALID_URL', 'Image locator must be HTTPS or a safe local path without traversal', parameter='locator')
    nonempty(alt, 'alt')
    if not isinstance(representation, str) or representation not in REPRESENTATIONS:
        fail('INVALID_ARGUMENT', 'Unknown image representation',
             parameter='representation')
    creation_value = _creation(creation)
    fields = {
        'kind': 'image', 'locator': locator, 'alt': alt,
        'representation': representation,
    }
    if creation_value is not None:
        fields['creation'] = creation_value
    source_ref = _source(editor, source, creation_value)
    if source_ref is not None:
        fields['source_ref'] = source_ref
    for name, value in (('usage_rights', usage_rights), ('caption', caption)):
        if value is not None:
            nonempty(value, name)
            fields[name] = value
    if captured_at is not None:
        if creation_value is not None and creation_value['kind'] == 'generated':
            fail('CONFLICTING_EDIT',
                 'generated creation cannot also claim a captured_at value',
                 parameter='captured_at')
        fields['captured_at'] = copy.deepcopy(captured_at)
    if usages is not None:
        if not isinstance(usages, list) or not usages:
            fail('INVALID_ARGUMENT', 'usages must be a nonempty list when provided',
                 parameter='usages')
        normalized = [_usage(editor, value, f'usages[{index}]')
                      for index, value in enumerate(usages)]
        if len(normalized) != len({(value['target_ref']['type'],
                                    value['target_ref']['id'], value['purpose'])
                                   for value in normalized}):
            fail('DUPLICATE_MEDIA_USAGE',
                 'The same Media target and purpose can only appear once',
                 parameter='usages')
        fields['usages'] = normalized
    return editor.add('media', fields)


def media_update(editor, *, target, set=None, clear=None):
    _require_current_schema(editor)
    from .core import edit_fields
    media = editor.record(target, {'media'})
    changes = {} if set is None else copy.deepcopy(set)
    clear_fields = [] if clear is None else copy.deepcopy(clear)
    if isinstance(changes, dict):
        for field in ('alt', 'caption', 'usage_rights'):
            if field in changes:
                nonempty(changes[field], f'set.{field}')
    edit_fields(media, changes=changes, clear=clear_fields, append_note=None,
                allowed={'alt', 'caption', 'usage_rights'},
                clearable={'caption', 'usage_rights'})
    return editor.handle(target)


def media_usage_add(editor, *, target, subject, purpose):
    _require_current_schema(editor)
    media = editor.record(target, {'media'})
    usage = _usage(editor, {'target': subject, 'purpose': purpose})
    if usage not in media.get('usages', []):
        media.setdefault('usages', []).append(usage)
    return editor.handle(target)


def media_usage_remove(editor, *, target, subject, purpose):
    _require_current_schema(editor)
    media = editor.record(target, {'media'})
    usage = _usage(editor, {'target': subject, 'purpose': purpose})
    current = media.get('usages', [])
    if usage not in current:
        return editor.handle(target)
    remaining = [value for value in current if value != usage]
    if remaining:
        media['usages'] = remaining
    else:
        media.pop('usages', None)
    return editor.handle(target)
