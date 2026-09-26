"""Bounded Task preparation, checklist, dependency, and reopen helpers."""
import copy
import math

from .errors import fail, nonempty


CATEGORIES = {
    'documents', 'clothing', 'health_supplies', 'connectivity',
    'equipment', 'booking', 'verification', 'other',
}
ACTIONS = {
    'pack', 'obtain', 'purchase', 'install', 'activate', 'verify',
    'reserve', 'return', 'cancel', 'pay', 'other',
}
CHECKLIST_STATUSES = {'open', 'done', 'not_needed'}
SNAPSHOT_FIELDS = (
    'title', 'action', 'target_refs', 'category', 'assignees',
    'beneficiaries', 'requirement', 'preparation', 'depends_on',
)


def target_refs(editor, values, parameter='targets', *, require_current_items=False):
    if not isinstance(values, list) or not values:
        fail('INVALID_ARGUMENT', 'targets must be a nonempty list', parameter=parameter)
    refs = []
    for index, value in enumerate(values):
        ref = editor.ref(value)
        allowed_types = {'trip', 'item', 'stay'}
        if editor.package.get('schema_version') == '1.0':
            allowed_types.add('issue')
        if not (ref.get('type') in allowed_types or
                (ref.get('kind') == 'unit' and ref.get('owner', {}).get('type') == 'stay')):
            fail('REFERENCE_KIND_MISMATCH',
                 'Task targets must be Trip, Item, Stay, a Stay Unit, or an Issue',
                 reference=value, parameter=f'{parameter}[{index}]')
        if (require_current_items and ref.get('type') == 'item'
                and editor.record(value, {'item'}).get('lifecycle', 'current') != 'current'):
            fail('TASK_TARGET_RETIRED', 'A replacement Task Item target must be current',
                 reference=value, parameter=f'{parameter}[{index}]')
        refs.append(ref)
    return refs


def normalize_category(value, parameter='category'):
    if not isinstance(value, str) or value not in CATEGORIES:
        fail('INVALID_ARGUMENT', 'category is not a supported Task category',
             parameter=parameter)
    return value


def normalize_action(value, parameter='action'):
    if not isinstance(value, str) or value not in ACTIONS:
        fail('INVALID_ARGUMENT', 'action is not a supported Task action',
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


def task_retire(editor, *, target, reason):
    """Mark one explicitly selected open Task no longer needed, retaining its history."""
    if editor.package.get('schema_version') != '1.0':
        fail('SCHEMA_VERSION_UNSUPPORTED', 'task.retire requires 1.0')
    nonempty(reason, 'reason')
    task_ref = editor.ref(target, {'task'})
    task = editor.record(target, {'task'})
    if task['status'] != 'open':
        fail('TASK_NOT_OPEN', 'Only an open Task can be retired')
    review_refs = []
    for other in editor.package.get('tasks', []):
        if task_ref in other.get('depends_on', []):
            review_refs.append({'type': 'task', 'id': other['id']})
    for note in editor.package.get('guide_notes', []):
        if task_ref in note.get('related_refs', []):
            review_refs.append({'type': 'guide_note', 'id': note['id']})
    for issue in editor.package.get('issues', []):
        if issue.get('task_ref') == task_ref:
            review_refs.append({'type': 'issue', 'id': issue['id']})
    for claim in editor.package.get('claims', []):
        if claim.get('target', {}).get('object_ref') == task_ref:
            review_refs.append({'type': 'claim', 'id': claim['id']})
    task['status'] = 'not_needed'
    task['retirement'] = {'reason': reason}
    editor.parts['review_refs'] = review_refs
    return editor.handle(target)
