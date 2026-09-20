"""Owned vehicle identities and bounded binding to independent driving Legs."""
import copy

from .errors import fail, nonempty


def require_owned_vehicle_schema(editor, parameter=None):
    if editor.package.get('schema_version') not in ('1.0',):
        fail('SCHEMA_VERSION_UNSUPPORTED', 'Owned vehicle authoring requires 1.0',
             **({'parameter': parameter} if parameter is not None else {}))


def _trip_ref(editor):
    return {'type': 'trip', 'id': editor.package['trip']['id']}


def _driver_ids(editor, drivers):
    if not isinstance(drivers, list) or not drivers:
        fail('INVALID_ARGUMENT', 'drivers must be a nonempty list of member handles',
             parameter='drivers')
    result = []
    for index, value in enumerate(drivers):
        ref = editor.ref(value)
        if ref.get('kind') != 'member' or ref.get('owner') != _trip_ref(editor):
            fail('REFERENCE_KIND_MISMATCH',
                 'drivers must identify members of this Trip',
                 reference=value, parameter=f'drivers[{index}]')
        if ref['id'] in result:
            fail('INVALID_ARGUMENT', 'drivers must be distinct member handles',
                 parameter=f'drivers[{index}]')
        result.append(ref['id'])
    return result


def _requirements(value):
    if (not isinstance(value, list) or not value
            or any(not isinstance(entry, str) or not entry.strip() for entry in value)):
        fail('INVALID_ARGUMENT', 'requirements must be nonempty explicit strings',
             parameter='requirements')
    if len(value) != len(set(value)):
        fail('INVALID_ARGUMENT', 'requirements must not contain duplicates',
             parameter='requirements')
    return copy.deepcopy(value)


def vehicle_record_owned(editor, *, category=None, actual_vehicle=None,
                         drivers=None, requirements=None, notes=None):
    require_owned_vehicle_schema(editor)
    fields = {'source_kind': 'owned'}
    for name, value in (('category', category), ('actual_vehicle', actual_vehicle),
                        ('notes', notes)):
        if value is not None:
            nonempty(value, name)
            fields[name] = value
    if drivers is not None:
        fields['driver_member_ids'] = _driver_ids(editor, drivers)
    if requirements is not None:
        fields['requirements'] = _requirements(requirements)
    return editor.add('vehicle_use', fields)


def owned_vehicle_ref(editor, value, parameter):
    require_owned_vehicle_schema(editor, parameter)
    vehicle = editor.record(value, {'vehicle_use'})
    if vehicle.get('source_kind') != 'owned':
        fail('VEHICLE_SOURCE_MISMATCH', 'This action accepts an owned VehicleUse only',
             parameter=parameter)
    return editor.ref(value, {'vehicle_use'})


def bind_owned_vehicle(editor, leg, value, parameter):
    if leg.get('mode') != 'driving' or leg.get('movement', {}).get('kind') != 'independent':
        fail('VEHICLE_MODE_MISMATCH',
             'Owned vehicles bind only independent driving Legs', parameter=parameter)
    proposed = owned_vehicle_ref(editor, value, parameter)
    current = leg.get('vehicle_ref')
    if current == proposed:
        return
    if current is not None and current != proposed:
        fail('VEHICLE_REPLACEMENT_REQUIRED',
             'A different known vehicle requires an execution replacement',
             parameter=parameter, current_vehicle_ref=copy.deepcopy(current),
             proposed_vehicle_ref=copy.deepcopy(proposed))
    if 'id' in leg:
        from .item_times import protect_leg_movement_fact_change
        leg_ref = {'type': 'leg', 'id': leg['id']}
        protect_leg_movement_fact_change(editor, leg_ref, current, proposed, parameter)
    leg['vehicle_ref'] = proposed
