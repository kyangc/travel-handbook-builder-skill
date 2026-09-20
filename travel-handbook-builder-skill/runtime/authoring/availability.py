"""Read-only coverage of fixed meal intervals by recorded venue opening hours."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class Unassessed(Exception):
    pass


def instant(value):
    if 'offset' in value:
        raise Unassessed('explicit_offset_not_supported')
    local = datetime.fromisoformat(value['local'])
    zone = ZoneInfo(value['timezone'])
    candidates = set()
    for fold in (0, 1):
        moment = local.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if moment.astimezone(zone).replace(tzinfo=None) == local:
            candidates.add(moment)
    if len(candidates) != 1:
        raise Unassessed('local_time_not_unique')
    return candidates.pop()


def gaps(start, end, intervals):
    cursor, result = start, []
    for left, right in sorted(intervals):
        if right <= cursor or left >= end:
            continue
        if left > cursor:
            result.append((cursor, left))
        cursor = max(cursor, min(right, end))
    if cursor < end:
        result.append((cursor, end))
    return result


def ranges(intervals):
    return [{'start':a.isoformat(), 'end':b.isoformat()} for a,b in intervals]


def evaluate(item, schedules):
    timing = item['timing']
    if timing['kind'] != 'fixed' or not {'start','end'} <= timing.keys():
        raise Unassessed('fixed_start_and_end_required')
    start, end = instant(timing['start']), instant(timing['end'])
    if end <= start:
        raise Unassessed('positive_interval_required')
    if len(schedules) != 1:
        raise Unassessed('venue_schedule_missing' if not schedules else 'multiple_venue_schedules')
    schedule = schedules[0]
    if schedule.get('date_overrides') or 'valid_from' in schedule or 'valid_to' in schedule:
        raise Unassessed('date_or_season_rules_not_supported')
    if any(rule.get('cutoffs') for rule in schedule['weekly_rules']):
        raise Unassessed('cutoffs_not_supported')
    result = {'interval':ranges([(start,end)])[0], 'schedule_id':schedule['id']}
    overlaps, closure_indices = [], []
    for index,closure in enumerate(schedule.get('closures',[])):
        left,right = instant(closure['start']),instant(closure['end'])
        if max(start,left) < min(end,right):
            overlaps.append((max(start,left),min(end,right)))
            closure_indices.append(index)
    if overlaps:
        return {**result,'status':'conflict','reason':'absolute_closure_overlap',
                'closure_indices':closure_indices,'uncovered_intervals':ranges(overlaps)}
    zone = ZoneInfo(schedule['timezone'])
    first = start.astimezone(zone).date() - timedelta(days=1)
    last = (end - timedelta(microseconds=1)).astimezone(zone).date()
    if (last-first).days > 7:
        raise Unassessed('interval_too_long')
    def at(day, clock='00:00'):
        return instant({'local':day.isoformat()+'T'+clock+':00','timezone':schedule['timezone']})
    opened, possible, rule_ids = [], [], []
    day = first
    while day <= last:
        matching = [r for r in schedule['weekly_rules'] if day.isoweekday() in r['weekdays']]
        if len(matching) > 1:
            raise Unassessed('multiple_weekday_rules')
        if not matching or matching[0]['state'] == 'unknown':
            # An unspecified opening start-day could extend into the following day.
            possible.append((at(day),at(day+timedelta(days=2))))
        else:
            rule=matching[0]
            rule_ids.append(rule['id'])
            if rule['state'] == 'open':
                periods = [{'start':'00:00','end':'00:00','end_day_offset':1}] if rule.get('all_day') else rule['intervals']
                for period in periods:
                    opened.append((at(day,period['start']),at(day+timedelta(days=period['end_day_offset']),period['end'])))
        day += timedelta(days=1)
    result['rule_ids'] = list(dict.fromkeys(rule_ids))
    if not gaps(start,end,opened):
        return {**result,'status':'covered','reason':'recorded_hours_cover_interval'}
    definite = gaps(start,end,opened+possible)
    if definite:
        return {**result,'status':'conflict','reason':'outside_recorded_hours','uncovered_intervals':ranges(definite)}
    return {**result,'status':'unknown','reason':'opening_start_day_unspecified',
            'unverified_intervals':ranges(gaps(start,end,opened))}


def meal_availability(package):
    assessments, warnings = [], []
    places = {p['id']:p for p in package.get('places',[])}
    for index,item in enumerate(package.get('items',[])):
        if item['kind'] != 'meal' or item.get('lifecycle','current') != 'current':
            continue
        result = {'item_ref':{'type':'item','id':item['id']}, 'scope':'venue',
                  'limits':['recorded_hours_only','meal_service_and_booking_not_assessed']}
        place_ref = item.get('place_ref')
        if place_ref:
            result['place_ref'] = dict(place_ref)
        try:
            if place_ref is None:
                raise Unassessed('place_not_recorded')
            schedules = [s for s in places[place_ref['id']].get('availability',[]) if s['scope'] == 'venue']
            result.update(evaluate(item,schedules))
        except Unassessed as error:
            result.update(status='unknown',reason=str(error))
        except ZoneInfoNotFoundError:
            result.update(status='unknown',reason='timezone_not_supported')
        except (OverflowError,ValueError):
            result.update(status='unknown',reason='calendar_out_of_supported_range')
        assessments.append(result)
        if result['status'] == 'conflict':
            warnings.append({'code':'MEAL_OUTSIDE_VENUE_HOURS','path':f'/items/{index}/timing',
                'message':'Recorded venue hours do not cover this meal interval; the arrangement is unchanged.',**result})
    return assessments,warnings
