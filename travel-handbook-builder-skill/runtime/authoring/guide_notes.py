"""Bounded authored guide notes and immutable source metadata."""
import copy
import json

from .errors import fail, nonempty
from .source_refresh import locate


SOURCE_KINDS = {
    'user_statement', 'confirmation', 'official', 'observation',
    'estimate', 'synthetic_fixture', 'other',
}


def require_current_schema(editor):
    if editor.package['schema_version'] not in ('1.0',):
        fail('SCHEMA_VERSION_UNSUPPORTED', 'Guide notes require schema version 1.0',
             supported_version='1.0')


def source_record(editor, *, kind, title, url=None, published_at=None, notes=None):
    if not isinstance(kind, str) or kind not in SOURCE_KINDS:
        fail('INVALID_ARGUMENT', 'Unknown Source kind', parameter='kind')
    nonempty(title, 'title')
    fields = {'kind': kind, 'title': title}
    for name, value in (('url', url), ('notes', notes)):
        if value is not None:
            nonempty(value, name)
            fields[name] = value
    if published_at is not None:
        fields['published_at'] = copy.deepcopy(published_at)
    return editor.add('source', fields)


def citation(editor, value, parameter):
    if not isinstance(value, dict):
        fail('INVALID_ARGUMENT', 'Citation must be a source or exact anchor object', parameter=parameter)
    if set(value) == {'source'}:
        return {'source_ref': editor.ref(value['source'], {'source'})}
    if set(value) == {'anchor'}:
        snapshot, anchor = locate(editor, value['anchor'], require_latest=False)
        return {
            'source_ref': editor.ref(anchor['source'], {'source'}),
            'excerpt': anchor['exact_text'],
            'locator': {
                'kind': 'unicode_codepoint_range',
                'start': anchor['start'],
                'end': anchor['end'],
            },
            'snapshot_sha256': snapshot['sha256'],
        }
    fail('INVALID_ARGUMENT', 'Citation accepts exactly source or anchor', parameter=parameter)


def normalize_paragraphs(editor, values):
    if not isinstance(values, list) or not values:
        fail('INVALID_ARGUMENT', 'paragraphs must be a nonempty ordered list', parameter='paragraphs')
    result = []
    for index, value in enumerate(values):
        parameter = f'paragraphs[{index}]'
        if isinstance(value, str):
            nonempty(value, parameter)
            result.append({'text': value})
            continue
        if not isinstance(value, dict) or 'text' not in value or set(value) - {'text', 'citations'}:
            fail('INVALID_ARGUMENT', 'Paragraph needs text and optional citations only', parameter=parameter)
        nonempty(value['text'], parameter + '.text')
        entry = {'text': value['text']}
        if 'citations' in value:
            values_citations = value['citations']
            if not isinstance(values_citations, list) or not values_citations:
                fail('INVALID_ARGUMENT', 'citations must be nonempty when provided', parameter=parameter + '.citations')
            entry['citations'] = [citation(editor, item, f'{parameter}.citations[{offset}]')
                                  for offset, item in enumerate(values_citations)]
        result.append(entry)
    return result


def related_refs(editor, values):
    if not isinstance(values, list) or not values:
        fail('INVALID_ARGUMENT', 'related must be a nonempty handle list', parameter='related')
    result, seen = [], set()
    for index, value in enumerate(values):
        ref = editor.ref(value)
        key = json.dumps(ref, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        if key not in seen:
            seen.add(key)
            result.append(ref)
    return result


def guide_note_add(editor, *, title, paragraphs: list, related=None):
    require_current_schema(editor)
    nonempty(title, 'title')
    fields = {'title': title, 'paragraphs': normalize_paragraphs(editor, paragraphs)}
    if related is not None:
        fields['related_refs'] = related_refs(editor, related)
    return editor.add('guide_note', fields)


def guide_note_update(editor, *, target, title=None, paragraphs=None, related=None, clear_related=False):
    require_current_schema(editor)
    if type(clear_related) is not bool:
        fail('INVALID_ARGUMENT', 'clear_related must be boolean', parameter='clear_related')
    if related is not None and clear_related:
        fail('CONFLICTING_EDIT', 'Use related or clear_related, not both', parameter='related')
    if title is None and paragraphs is None and related is None and not clear_related:
        fail('INVALID_ARGUMENT', 'Provide at least one GuideNote change')
    record = editor.record(target, {'guide_note'})
    if title is not None:
        nonempty(title, 'title')
        record['title'] = title
    if paragraphs is not None:
        record['paragraphs'] = normalize_paragraphs(editor, paragraphs)
    if related is not None:
        record['related_refs'] = related_refs(editor, related)
    elif clear_related:
        record.pop('related_refs', None)
    return editor.handle(target)
