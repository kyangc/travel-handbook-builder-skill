"""Bounded Task preparation, checklist, dependency, and reopen helpers."""
import copy
import math

from .errors import fail, nonempty


CATEGORIES = {
    'documents', 'clothing', 'health_supplies', 'connectivity',
    'equipment', 'booking', 'verification', 'other',
}
CHECKLIST_STATUSES = {'open', 'done', 'not_needed'}
SNAPSHOT_FIELDS = (
    'title', 'action', 'target_refs', 'category', 'assignees',
    'beneficiaries', 'requirement', 'preparation', 'depends_on',
)


def normalize_category(value, parameter='category'):
    if not isinstance(value, str) or value not in CATEGORIES:
        fail('INVALID_ARGUMENT', 'category is not a supported Task category',
             parameter=parameter)
    return value


def normalize_preparation(value, parameter='preparation'):
    if not isinstance(value, dict) or set(value) - {'item_label', 'quantity', 'unit', 'notes'}:
        fail('INVALID_ARGUMENT', 'preparation accepts item_label, quantity, unit and notes only',
             parameter=parameter)
    if 'item_label' not in value:
        fail('INVALID_ARGUMENT', 'preparation.item_label is required',
             parameter=f'{parameter}.item_label')
    nonempty(value['item_label'], f'{parameter}.item_label')
    has_quantity = 'quantity' in value
    has_unit = 'unit' in value
    if has_quantity != has_unit:
        fail('INVALID_ARGUMENT', 'preparation quantity and unit must be provided together',
             parameter=parameter)
    if has_quantity:
        quantity = value['quantity']
        valid_quantity = (type(quantity) is int and quantity > 0) or (
            type(quantity) is float and math.isfinite(quantity) and quantity > 0)
        if not valid_quantity:
            fail('INVALID_ARGUMENT', 'preparation.quantity must be a positive number',
                 parameter=f'{parameter}.quantity')
        nonempty(value['unit'], f'{parameter}.unit')
    if 'notes' in value:
        nonempty(value['notes'], f'{parameter}.notes')
    return copy.deepcopy(value)


def dependency_refs(editor, values, parameter='depends_on'):
    if not isinstance(values, list):
        fail('INVALID_ARGUMENT', 'depends_on must be a list of Task handles',
             parameter=parameter)
    result = []
    for index, value in enumerate(values):
        ref = editor.ref(value, {'task'})
        if ref not in result:
            result.append(ref)
    return result


def checklist_records(editor, values, parameter='checklist'):
    if not isinstance(values, list) or not values:
        fail('INVALID_ARGUMENT', 'checklist must be a nonempty list', parameter=parameter)
    result = []
    keys = set()
    for index, value in enumerate(values):
        path = f'{parameter}[{index}]'
        if not isinstance(value, dict) or set(value) != {'key', 'title'}:
            fail('INVALID_ARGUMENT', 'Each checklist entry requires key and title only',
                 parameter=path)
        nonempty(value['key'], f'{path}.key')
        nonempty(value['title'], f'{path}.title')
        if value['key'] in keys:
            fail('INVALID_ARGUMENT', 'Checklist keys must be unique within an operation',
                 parameter=f'{path}.key')
        keys.add(value['key'])
        result.append((value['key'], {
            'id': editor.allocate_id(),
            'title': value['title'],
            'status': 'open',
        }))
    return result


def register_checklist(editor, task_handle, keyed_records):
    if not keyed_records:
        return
    owner_ref = editor.ref(task_handle, {'task'})
    editor.parts.setdefault('checklist', {})
    for key, record in keyed_records:
        editor.parts['checklist'][key] = editor.register_local(owner_ref, 'checklist', record)


def edit_checklist(editor, task_handle, edits):
    if not isinstance(edits, list) or not edits:
        fail('INVALID_ARGUMENT', 'checklist_edits must be a nonempty list',
             parameter='checklist_edits')
    task = editor.record(task_handle, {'task'})
    task_ref = editor.ref(task_handle, {'task'})
    additions = []
    addition_keys = set()
    for index, edit in enumerate(edits):
        path = f'checklist_edits[{index}]'
        if not isinstance(edit, dict) or not isinstance(edit.get('op'), str):
            fail('INVALID_ARGUMENT', 'Checklist edit needs an op', parameter=path)
        if edit['op'] == 'add':
            if set(edit) != {'op', 'key', 'title'}:
                fail('INVALID_ARGUMENT', 'Checklist add requires op, key and title only',
                     parameter=path)
            nonempty(edit['key'], f'{path}.key')
            nonempty(edit['title'], f'{path}.title')
            if edit['key'] in addition_keys:
                fail('INVALID_ARGUMENT', 'Checklist add keys must be unique within an operation',
                     parameter=f'{path}.key')
            addition_keys.add(edit['key'])
            record = {'id': editor.allocate_id(), 'title': edit['title'], 'status': 'open'}
            task.setdefault('checklist', []).append(record)
            additions.append((edit['key'], record))
        elif edit['op'] == 'set_status':
            if set(edit) != {'op', 'target', 'status'}:
                fail('INVALID_ARGUMENT', 'Checklist set_status requires op, target and status only',
                     parameter=path)
            if not isinstance(edit['status'], str) or edit['status'] not in CHECKLIST_STATUSES:
                fail('INVALID_ARGUMENT', 'Checklist status must be open, done or not_needed',
                     parameter=f'{path}.status')
            handle = editor.handle(edit['target'])
            ref = editor.state['handles'][handle['handle']]
            if (ref.get('kind') != 'checklist' or ref.get('owner') != task_ref):
                fail('REFERENCE_KIND_MISMATCH', 'Checklist entry does not belong to the target Task',
                     reference=edit['target'], parameter=f'{path}.target')
            record = next((entry for entry in task.get('checklist', [])
                           if entry['id'] == ref['id']), None)
            if record is None:
                fail('REFERENCE_NOT_FOUND', 'Checklist entry is not present on the target Task',
                     reference=edit['target'], parameter=f'{path}.target')
            record['status'] = edit['status']
        elif edit['op'] == 'rename':
            if set(edit) != {'op', 'target', 'title'}:
                fail('INVALID_ARGUMENT', 'Checklist rename requires op, target and title only',
                     parameter=path)
            nonempty(edit['title'], f'{path}.title')
            handle = editor.handle(edit['target'])
            ref = editor.state['handles'][handle['handle']]
            if (ref.get('kind') != 'checklist' or ref.get('owner') != task_ref):
                fail('REFERENCE_KIND_MISMATCH', 'Checklist entry does not belong to the target Task',
                     reference=edit['target'], parameter=f'{path}.target')
            record = next((entry for entry in task.get('checklist', [])
                           if entry['id'] == ref['id']), None)
            if record is None:
                fail('REFERENCE_NOT_FOUND', 'Checklist entry is not present on the target Task',
                     reference=edit['target'], parameter=f'{path}.target')
            record['title'] = edit['title']
        else:
            fail('INVALID_ARGUMENT', 'Checklist edit op must be add, set_status or rename',
                 parameter=f'{path}.op')
    register_checklist(editor, task_handle, additions)


def task_reopen(editor, *, target, reason, reopened_at=None):
    if editor.package.get('schema_version') not in ('1.0',):
        fail('SCHEMA_VERSION_UNSUPPORTED', 'task.reopen requires 1.0')
    task = editor.record(target, {'task'})
    if task['status'] != 'done':
        fail('TASK_NOT_DONE', 'Only a done Task can be reopened')
    nonempty(reason, 'reason')
    snapshot = {field: copy.deepcopy(task[field]) for field in SNAPSHOT_FIELDS if field in task}
    reopened = {'reason': reason}
    if reopened_at is not None:
        reopened['reopened_at'] = copy.deepcopy(reopened_at)
    history = {
        'completion': copy.deepcopy(task['completion']),
        'task_snapshot': snapshot,
        'checklist_snapshot': copy.deepcopy(task.get('checklist', [])),
        'reopened': reopened,
    }
    task.setdefault('completion_history', []).append(history)
    task['status'] = 'open'
    del task['completion']
    return editor.handle(target)
