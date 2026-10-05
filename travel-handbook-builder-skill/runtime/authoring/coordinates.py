"""Caller-facing coordinate requirements; no CRS inference or conversion."""
import copy
from .errors import fail

LOCATION_REQUIRED = ['lat', 'lon', 'coordinate_system', 'precision']
REPAIR = {
    'when_known': 'Provide the coordinate system explicitly declared by the source or its documented provider; preserve the named lat/lon order. Do not infer from country, decimals or URL.',
    'when_unknown': 'Omit location (or skip creating the Path); preserve raw values, order, source and the unresolved CRS in notes. Address and other known information can be submitted separately. Retry the entire failed batch after correction.',
}


LOCATION_FIELD_GUIDANCE = {
    'lat': 'Numeric latitude from -90 to 90; name explicitly, do not infer array order.',
    'lon': 'Numeric longitude from -180 to 180; name explicitly, do not infer array order.',
    'coordinate_system': 'Explicit source/provider declaration; no default, verification or conversion.',
    'precision': {
        'entrance': 'The source identifies a specific entrance.',
        'building': 'The source identifies a building, not a specific entrance.',
        'parcel': 'The source identifies a site or parcel.',
        'area': 'The source identifies an area.',
        'approximate': 'Caller explicitly adopts an approximate point; if source precision is unknown, record that limitation in notes. Decimal digits do not establish entrance accuracy.',
    },
}

def _location_contract(guide):
    return {
        'required': LOCATION_REQUIRED,
        'field_guidance': LOCATION_FIELD_GUIDANCE,
        'coordinate_order': 'named lat (latitude), lon (longitude); no positional arrays',
        'default_coordinate_system': None,
        'coordinate_system_rule': 'Explicit source/provider declaration; arbitrary nonempty declaration is stored, not verified. Unknown placeholders are not declarations.',
        'verifies_coordinate_system': False,
        'converts_coordinates': False,
        'replacement': 'whole location object',
        'repair': REPAIR,
        'guide': guide,
    }


COORDINATE_INPUTS = {
    'place.update.set.location': _location_contract('references/LOCATION_GUIDE.md'),
    'access_point.add.location': _location_contract('references/ACCESS_POINT_GUIDE.md'),
    'access_point.update.set.location': _location_contract('references/ACCESS_POINT_GUIDE.md'),
    'path.add_schematic': {
        'required': ['coordinate_system', 'mode', 'parts'],
        'accepted_coordinate_systems': ['WGS84'],
        'default_coordinate_system': None,
        'coordinate_order': 'parts is a list of lines; each vertex uses named lat/lon, not a positional array',
        'verifies_coordinate_system': False,
        'converts_coordinates': False,
        'geometry_kind': 'schematic; not verified routing or a navigation track',
        'repair': REPAIR,
        'guide': 'references/MOVEMENT_GUIDE.md',
    },
    'path.record': {
        'required': ['kind', 'coordinate_system', 'mode', 'parts'],
        'accepted_coordinate_systems': ['WGS84'],
        'accepted_kinds': ['observed_track', 'provider_route', 'authored_route'],
        'source_required_for': ['observed_track', 'provider_route'],
        'default_coordinate_system': None,
        'coordinate_order': 'parts is a list of lines; each vertex uses named lat/lon, not a positional array',
        'verifies_coordinate_system': False,
        'converts_coordinates': False,
        'geometry_kind': 'explicit recorded geometry; kind and source provenance do not prove routability, GPS verification or endpoint reachability',
        'repair': REPAIR,
        'guide': 'references/MOVEMENT_GUIDE.md',
    },
}


UNCONFIRMED = {'unknown', 'unspecified', 'unconfirmed', 'unverified', 'tbd', 'todo', 'n/a',
               '未知', '不详', '待核实', '待确认', '未确认', '未声明'}


def validate_coordinate_inputs(method, args):
    if method == 'place.update' and isinstance(args.get('set'), dict) and 'location' in args['set']:
        location = args['set']['location']
        if not isinstance(location, dict):
            return  # Standard validation reports invalid Location shapes.
        parameter = 'set.location.coordinate_system'
        guide = 'references/LOCATION_GUIDE.md'
        crs = location.get('coordinate_system')
        missing = [key for key in LOCATION_REQUIRED if key not in location]
        location_parameter = 'set.location'
    elif method == 'access_point.add' and 'location' in args:
        location = args['location']
        if not isinstance(location, dict):
            return
        parameter = 'location.coordinate_system'
        guide = 'references/ACCESS_POINT_GUIDE.md'
        crs = location.get('coordinate_system')
        missing = [key for key in LOCATION_REQUIRED if key not in location]
        location_parameter = 'location'
    elif (method == 'access_point.update' and isinstance(args.get('set'), dict)
          and 'location' in args['set']):
        location = args['set']['location']
        if not isinstance(location, dict):
            return
        parameter = 'set.location.coordinate_system'
        guide = 'references/ACCESS_POINT_GUIDE.md'
        crs = location.get('coordinate_system')
        missing = [key for key in LOCATION_REQUIRED if key not in location]
        location_parameter = 'set.location'
    elif method in {'path.add_schematic', 'path.record'}:
        parameter = 'coordinate_system'
        guide = 'references/MOVEMENT_GUIDE.md'
        crs = args.get('coordinate_system')
        missing = ['coordinate_system']
    else:
        return
    if not isinstance(crs, str) or not crs.strip():
        fail('COORDINATE_SYSTEM_REQUIRED', 'Provide an explicitly declared coordinate system; there is no default.',
             parameter=parameter, missing_fields=missing or ['coordinate_system'], repair=copy.deepcopy(REPAIR), guide=guide)
    if crs.strip().casefold() in UNCONFIRMED:
        fail('COORDINATE_SYSTEM_UNCONFIRMED', 'An unknown placeholder is not a coordinate-system declaration.',
             parameter=parameter, repair=copy.deepcopy(REPAIR), guide=guide)
    if method in {'path.add_schematic', 'path.record'} and crs != 'WGS84':
        label = 'Schematic Path' if method == 'path.add_schematic' else 'Recorded Path'
        fail('UNSUPPORTED_VARIANT', f'{label} input accepts explicit WGS84 only; do not relabel another coordinate system.',
             parameter=parameter, accepted_coordinate_systems=['WGS84'], repair=copy.deepcopy(REPAIR), guide=guide)
    if method in {'place.update', 'access_point.add', 'access_point.update'} and missing:
        fail('LOCATION_FIELDS_REQUIRED', 'Provide the complete location object; partial updates are not merged.',
             parameter=location_parameter, missing_fields=missing,
             field_guidance={key: copy.deepcopy(LOCATION_FIELD_GUIDANCE[key]) for key in missing},
             repair={**copy.deepcopy(REPAIR), 'when_known': 'Supply all missing fields using field_guidance, then resend the complete location object. Do not infer entrance precision from decimal digits.'}, guide=guide)
