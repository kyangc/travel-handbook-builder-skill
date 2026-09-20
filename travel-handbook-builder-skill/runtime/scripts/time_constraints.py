"""Finite timing-constraint checks; no general scheduling or feasibility solver."""
from datetime import datetime, timedelta, timezone
import math
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

KINDS = {'not_before', 'not_after', 'before', 'after'}
FIELDS = {'start', 'end'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _local_parts(value):
    _require(isinstance(value, dict), 'constraint time must be a ZonedDateTime')
    _require({'local', 'timezone'} <= value.keys(), 'constraint time needs local/timezone')
    _require(set(value) <= {'local', 'timezone', 'offset'}, 'unsupported constraint time fields')
    _require(isinstance(value['local'], str) and isinstance(value['timezone'], str), 'invalid local/timezone')
    try:
        local = datetime.fromisoformat(value['local'])
        zone = ZoneInfo(value['timezone'])
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise ValueError('invalid constraint date/timezone') from error
    _require('T' in value['local'] and local.tzinfo is None, 'local must be a timezone-free date-time')
    return local, zone


def validate_constraint(constraint, resolve=None):
    """Raise ValueError on invalid shape/type; optionally resolve the anchor reference."""
    _require(isinstance(constraint, dict), 'constraint must be an object')
    _require(isinstance(constraint.get('kind'), str) and constraint['kind'] in KINDS, 'unsupported constraint kind')
    _require(isinstance(constraint.get('applies_to'), str) and constraint['applies_to'] in FIELDS, 'constraint needs applies_to start/end')
    absolute = 'time' in constraint
    relative = 'relative_to' in constraint
    _require(absolute != relative, 'constraint needs exactly one absolute or relative bound')
    base = {'kind', 'applies_to'}
    if absolute:
        _require(set(constraint) == base | {'time'}, 'invalid absolute constraint fields')
        _local_parts(constraint['time'])
        return
    _require(set(constraint) == base | {'relative_to', 'minutes'}, 'invalid relative constraint fields')
    minutes = constraint['minutes']
    _require(type(minutes) in (int, float) and math.isfinite(minutes), 'minutes must be finite numeric elapsed minutes')
    anchor = constraint['relative_to']
    _require(isinstance(anchor, dict) and set(anchor) == {'ref', 'field'}, 'invalid relative anchor shape')
    _require(isinstance(anchor['field'], str) and anchor['field'] in FIELDS, 'anchor field must be start/end')
    ref = anchor['ref']
    _require(isinstance(ref, dict) and set(ref) == {'type', 'id'}, 'invalid anchor reference shape')
    _require(isinstance(ref['type'], str) and ref['type'] in {'item', 'activity'} and isinstance(ref['id'], str) and bool(ref['id']), 'anchor must reference Item/Activity')
    if resolve is not None:
        resolve(ref)


def _instant(value):
    if not isinstance(value, dict) or not {'local', 'timezone'} <= value.keys():
        return None, 'time_not_explicit'
    local, zone = _local_parts(value)
    if 'offset' in value:
        return None, 'explicit_offset_not_supported'
    first = local.replace(tzinfo=zone, fold=0)
    second = local.replace(tzinfo=zone, fold=1)
    if first.utcoffset() != second.utcoffset():
        return None, 'dst_disambiguation_required'
    instant = first.astimezone(timezone.utc)
    if instant.astimezone(zone).replace(tzinfo=None) != local:
        return None, 'nonexistent_local_time'
    return instant, None


def _endpoint(timing, field):
    if not isinstance(timing, dict):
        return None, 'timing_not_recorded'
    if timing.get('kind') == 'estimated':
        return None, 'estimated_time'
    if timing.get('kind') != 'fixed' or field not in timing:
        return None, 'endpoint_not_explicit_fixed'
    return _instant(timing[field])


def evaluate_constraint(timing, constraint, resolve=None):
    """Return {status: satisfied|violated|unknown, reason?} for explicit fixed times.

    resolve(ref) must return the referenced Item/Activity object. Estimated, derived,
    window, absent endpoints and DST-disambiguation cases conservatively stay unknown.
    """
    validate_constraint(constraint, resolve)
    actual, reason = _endpoint(timing, constraint['applies_to'])
    if actual is None:
        return {'status': 'unknown', 'reason': reason}
    if 'time' in constraint:
        bound, reason = _instant(constraint['time'])
    elif resolve is None:
        return {'status': 'unknown', 'reason': 'anchor_resolver_missing'}
    else:
        anchor = constraint['relative_to']
        bound, reason = _endpoint(resolve(anchor['ref']).get('timing'), anchor['field'])
        if bound is not None:
            try:
                bound += timedelta(minutes=constraint['minutes'])
            except OverflowError:
                return {'status': 'unknown', 'reason': 'relative_bound_out_of_range'}
    if bound is None:
        return {'status': 'unknown', 'reason': reason}
    matches = {'not_before': actual >= bound, 'not_after': actual <= bound,
               'before': actual < bound, 'after': actual > bound}
    return {'status': 'satisfied' if matches[constraint['kind']] else 'violated'}
