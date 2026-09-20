"""Bounded Cost recording, direct budget rates, and read-only projection."""
import copy
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
import math
import re

from .errors import fail, nonempty


MONEY_VERSIONS = {'1.0'}
COST_TARGET_TYPES = {
    'item', 'leg', 'journey', 'stay', 'activity', 'service_use',
    'vehicle_use', 'service_bundle', 'route', 'reservation',
}
CURRENCIES = re.compile(r'^[A-Z]{3}$')
DECIMALS = re.compile(r'^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$')
CLAIM_BASES = (
    'user_statement', 'confirmation', 'official', 'observation',
    'estimate', 'synthetic_fixture', 'other',
)


def require_money_version(editor):
    if editor.package.get('schema_version') not in MONEY_VERSIONS:
        fail('SCHEMA_VERSION_UNSUPPORTED', 'Cost and budget methods require 1.0 or later',
             supported_version='1.0')


def require_cost_origin(origin, *, example):
    if not isinstance(origin, dict) or set(origin) != {'basis', 'statement'}:
        fail('MISSING_FACTS',
             'Confirmed Cost facts require operation.origin with basis and statement',
             parameter='origin')
    nonempty(origin['statement'], 'origin.statement')
    basis = origin['basis']
    if not isinstance(basis, str) or basis not in CLAIM_BASES:
        fail('INVALID_ARGUMENT', 'Unknown origin basis', parameter='origin.basis')
    if basis == 'estimate' or (basis == 'synthetic_fixture' and not example):
        fail('INVALID_EVIDENCE',
             'An estimate or invented real-trip fixture cannot establish a confirmed Cost',
             parameter='origin.basis')


def currency(value, parameter):
    if not isinstance(value, str) or CURRENCIES.fullmatch(value) is None:
        fail('INVALID_ARGUMENT', 'currency must be a three-letter uppercase code',
             parameter=parameter)
    return value


def decimal_string(value, parameter, *, positive=False):
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or DECIMALS.fullmatch(value) is None:
        qualifier = 'positive' if positive else 'nonnegative'
        fail('INVALID_ARGUMENT',
             f'{parameter} must be a {qualifier} decimal string or integer; floats and booleans are not accepted',
             parameter=parameter)
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        fail('INVALID_ARGUMENT', f'{parameter} must be a finite decimal', parameter=parameter)
    if parsed < 0 or (positive and parsed <= 0):
        fail('INVALID_ARGUMENT', f'{parameter} must be ' + ('positive' if positive else 'nonnegative'),
             parameter=parameter)
    return value


def money(value, parameter):
    if not isinstance(value, dict) or set(value) != {'amount', 'currency'}:
        fail('INVALID_ARGUMENT', 'Money requires exactly amount and currency', parameter=parameter)
    return {
        'amount': decimal_string(value['amount'], parameter + '.amount'),
        'currency': currency(value['currency'], parameter + '.currency'),
    }


def price_value(*, amount=None, currency_value=None, value=None, parameter='value',
                allow_unknown=True):
    simplified = amount is not None or currency_value is not None
    if simplified == (value is not None):
        fail('INVALID_ARGUMENT', 'Choose amount with currency or one complete value',
             parameter=parameter)
    if simplified:
        if amount is None or currency_value is None:
            fail('INVALID_ARGUMENT', 'amount and currency must be supplied together',
                 parameter=parameter)
        return {'kind': 'exact', 'money': {
            'amount': decimal_string(amount, 'amount'),
            'currency': currency(currency_value, 'currency'),
        }}
    if not isinstance(value, dict) or not isinstance(value.get('kind'), str):
        fail('INVALID_ARGUMENT', 'value must use exact, range, from, or unknown',
             parameter=parameter)
    kind = value['kind']
    if kind == 'exact' and set(value) == {'kind', 'money'}:
        return {'kind': 'exact', 'money': money(value['money'], parameter + '.money')}
    if kind == 'range' and set(value) == {'kind', 'min', 'max'}:
        low = money(value['min'], parameter + '.min')
        high = money(value['max'], parameter + '.max')
        if low['currency'] != high['currency']:
            fail('INVALID_ARGUMENT', 'range bounds must use one currency', parameter=parameter)
        if Decimal(low['amount']) > Decimal(high['amount']):
            fail('INVALID_ARGUMENT', 'range min must not exceed max', parameter=parameter)
        return {'kind': 'range', 'min': low, 'max': high}
    if kind == 'from' and set(value) == {'kind', 'min'}:
        return {'kind': 'from', 'min': money(value['min'], parameter + '.min')}
    if kind == 'unknown' and set(value) in ({'kind'}, {'kind', 'currency'}):
        if not allow_unknown:
            fail('INVALID_ARGUMENT', 'confirmed Cost cannot use an unknown amount',
                 parameter=parameter)
        result = {'kind': 'unknown'}
        if 'currency' in value:
            result['currency'] = currency(value['currency'], parameter + '.currency')
        return result
    fail('INVALID_ARGUMENT', 'value must be a closed exact, range, from, or unknown object',
         parameter=parameter)


def completeness_value(value, parameter='completeness'):
    if not isinstance(value, str) or value not in {'complete', 'partial', 'unknown'}:
        fail('INVALID_ARGUMENT', 'completeness must be complete, partial, or unknown',
             parameter=parameter)
    return value


def target_refs(editor, targets):
    if not isinstance(targets, list) or not targets:
        fail('INVALID_ARGUMENT', 'targets must be a nonempty list of Cost target handles',
             parameter='targets')
    result = []
    for index, target in enumerate(targets):
        ref = editor.ref(target)
        owner_type = ref.get('owner', {}).get('type') if 'owner' in ref else ref.get('type')
        if owner_type not in COST_TARGET_TYPES:
            fail('REFERENCE_KIND_MISMATCH', 'Handle is not a legal Cost target',
                 parameter=f'targets[{index}]', reference=target)
        if ref in result:
            fail('INVALID_ARGUMENT', 'Do not repeat a Cost target', parameter='targets')
        result.append(ref)
    return result


def quantity_basis_value(editor, value):
    if not isinstance(value, dict) or not {'unit', 'quantity'} <= set(value) or set(value) - {
            'unit', 'quantity', 'rate', 'chargeable_nights', 'notes', 'eligible_members'}:
        fail('INVALID_ARGUMENT',
             'quantity_basis needs unit and quantity; optional rate, chargeable_nights, notes, eligible_members',
             parameter='quantity_basis')
    nonempty(value['unit'], 'quantity_basis.unit')
    quantity = value['quantity']
    if (type(quantity) is int and quantity > 0):
        pass
    elif type(quantity) is float and math.isfinite(quantity) and quantity > 0:
        pass
    else:
        fail('INVALID_ARGUMENT', 'quantity_basis.quantity must be a positive finite number',
             parameter='quantity_basis.quantity')
    result = {'unit': value['unit'], 'quantity': quantity}
    if 'rate' in value:
        result['rate'] = money(value['rate'], 'quantity_basis.rate')
    if 'chargeable_nights' in value:
        nights = value['chargeable_nights']
        if (type(nights) is int and nights > 0):
            pass
        elif type(nights) is float and math.isfinite(nights) and nights > 0:
            pass
        else:
            fail('INVALID_ARGUMENT', 'chargeable_nights must be a positive finite number',
                 parameter='quantity_basis.chargeable_nights')
        result['chargeable_nights'] = nights
    if 'notes' in value:
        nonempty(value['notes'], 'quantity_basis.notes')
        result['notes'] = value['notes']
    if 'eligible_members' in value:
        entries = value['eligible_members']
        if not isinstance(entries, list) or not entries:
            fail('INVALID_ARGUMENT', 'eligible_members must be a nonempty list of member handles',
                 parameter='quantity_basis.eligible_members')
        ids = []
        for index, entry in enumerate(entries):
            ref = editor.ref(entry)
            if (ref.get('kind') != 'member'
                    or ref.get('owner') != {'type': 'trip', 'id': editor.package['trip']['id']}):
                fail('REFERENCE_KIND_MISMATCH', 'eligible_members accepts Trip member handles',
                     parameter=f'quantity_basis.eligible_members[{index}]')
            if ref['id'] in ids:
                fail('INVALID_ARGUMENT', 'Do not repeat an eligible member',
                     parameter='quantity_basis.eligible_members')
            ids.append(ref['id'])
        result['eligible_member_ids'] = ids
    return result


def breakdown_value(values):
    if not isinstance(values, list) or not values:
        fail('INVALID_ARGUMENT', 'breakdown must be a nonempty list when supplied',
             parameter='breakdown')
    result = []
    for index, value in enumerate(values):
        parameter = f'breakdown[{index}]'
        if (not isinstance(value, dict) or not {'label', 'money'} <= set(value)
                or set(value) - {'label', 'money', 'notes'}):
            fail('INVALID_ARGUMENT', 'breakdown entry needs label, money, and optional notes',
                 parameter=parameter)
        nonempty(value['label'], parameter + '.label')
        entry = {'label': value['label'], 'money': money(value['money'], parameter + '.money')}
        if 'notes' in value:
            nonempty(value['notes'], parameter + '.notes')
            entry['notes'] = value['notes']
        result.append(entry)
    return result


def cost_record(editor, *, title, targets, price_status, amount=None, currency=None,
                value=None, completeness=None, quantity_basis=None, quote=None,
                breakdown=None, notes=None):
    require_money_version(editor)
    nonempty(title, 'title')
    if not isinstance(price_status, str) or price_status not in {'estimate', 'confirmed'}:
        fail('INVALID_ARGUMENT', 'price_status must be estimate or confirmed',
             parameter='price_status')
    normalized = price_value(amount=amount, currency_value=currency, value=value,
                             allow_unknown=price_status == 'estimate')
    fields = {
        'title': title,
        'status': 'active',
        'target_refs': target_refs(editor, targets),
        'completeness': completeness_value(
            'unknown' if completeness is None else completeness),
        price_status: normalized,
    }
    if quantity_basis is not None:
        fields['quantity_basis'] = quantity_basis_value(editor, quantity_basis)
    if quote is not None:
        fields['price_quote_ref'] = editor.ref(quote, {'price_quote'})
    if breakdown is not None:
        fields['breakdown'] = breakdown_value(breakdown)
    if notes is not None:
        nonempty(notes, 'notes')
        fields['notes'] = notes
    return editor.add('cost', fields)


def cost_confirm(editor, *, target, amount=None, currency=None, value=None,
                 completeness=None):
    require_money_version(editor)
    cost = editor.record(target, {'cost'})
    if cost['status'] != 'active':
        fail('UNSUPPORTED_VARIANT', 'Only an active Cost can be confirmed', parameter='target')
    normalized = price_value(amount=amount, currency_value=currency, value=value,
                             allow_unknown=False)
    if 'confirmed' in cost:
        if not _price_values_equal(cost['confirmed'], normalized):
            fail('COST_CONFIRMATION_REPLACEMENT_REQUIRED',
                 'A different known confirmation needs a controlled replacement method',
                 parameter='value')
        if completeness is not None and completeness_value(completeness) != cost['completeness']:
            fail('COST_COMPLETENESS_REPLACEMENT_REQUIRED',
                 'A different confirmed completeness needs a controlled replacement method',
                 parameter='completeness')
        editor.parts['_skip_origin_claim'] = True
        return editor.handle(target)
    previous = cost['completeness']
    current = completeness_value('unknown' if completeness is None else completeness)
    cost['confirmed'] = normalized
    cost['completeness'] = current
    editor.parts['completeness_change'] = {'from': previous, 'to': current}
    return editor.handle(target)


def _money_values_equal(left, right):
    return (left.get('currency') == right.get('currency')
            and Decimal(left.get('amount', '-1')) == Decimal(right.get('amount', '-2')))


def _price_values_equal(left, right):
    if left.get('kind') != right.get('kind'):
        return False
    if left['kind'] == 'exact':
        return _money_values_equal(left['money'], right['money'])
    if left['kind'] == 'range':
        return (_money_values_equal(left['min'], right['min'])
                and _money_values_equal(left['max'], right['max']))
    if left['kind'] == 'from':
        return _money_values_equal(left['min'], right['min'])
    return left == right


def exchange_rate_record(editor, *, base_currency, quote_currency, rate, as_of,
                         source, notes=None):
    require_money_version(editor)
    base = currency(base_currency, 'base_currency')
    quote = currency(quote_currency, 'quote_currency')
    if base == quote:
        fail('INVALID_ARGUMENT', 'Exchange-rate currencies must differ',
             parameter='quote_currency')
    normalized_rate = decimal_string(rate, 'rate', positive=True)
    if not isinstance(as_of, str):
        fail('INVALID_ARGUMENT', 'as_of must be an explicit calendar date', parameter='as_of')
    try:
        if date.fromisoformat(as_of).isoformat() != as_of:
            raise ValueError
    except ValueError:
        fail('INVALID_ARGUMENT', 'as_of must use YYYY-MM-DD', parameter='as_of')
    fields = {
        'base_currency': base,
        'quote_currency': quote,
        'rate': normalized_rate,
        'as_of': as_of,
        'source_ref': editor.ref(source, {'source'}),
    }
    if notes is not None:
        nonempty(notes, 'notes')
        fields['notes'] = notes
    return editor.add('exchange_rate', fields)


def _usable_rate(package, rate, reporting_currency):
    if (not isinstance(rate, dict) or rate.get('quote_currency') != reporting_currency
            or rate.get('base_currency') == reporting_currency):
        return False, 'not_direct_to_reporting_currency'
    try:
        if Decimal(rate.get('rate', '0')) <= 0:
            return False, 'rate_not_positive'
    except (InvalidOperation, TypeError):
        return False, 'rate_not_positive'
    try:
        if date.fromisoformat(rate.get('as_of', '')).isoformat() != rate.get('as_of'):
            return False, 'as_of_invalid'
    except (TypeError, ValueError):
        return False, 'as_of_invalid'
    source = rate.get('source_ref')
    if (not isinstance(source, dict) or source.get('type') != 'source'
            or not any(value.get('id') == source.get('id')
                       for value in package.get('sources', []))):
        return False, 'source_missing'
    return True, None


def budget_scope_value(value):
    if (not isinstance(value, dict) or 'status' not in value
            or set(value) - {'status', 'notes', 'categories'}):
        fail('INVALID_ARGUMENT', 'scope needs status and optional notes/categories',
             parameter='scope')
    result = {'status': completeness_value(value['status'], 'scope.status')}
    if 'notes' in value:
        nonempty(value['notes'], 'scope.notes')
        result['notes'] = value['notes']
    if 'categories' in value:
        categories = value['categories']
        if (not isinstance(categories, list)
                or any(not isinstance(entry, str) or not entry.strip() for entry in categories)):
            fail('INVALID_ARGUMENT', 'scope.categories must be a list of nonempty labels',
                 parameter='scope.categories')
        if len(categories) != len(set(categories)):
            fail('INVALID_ARGUMENT', 'scope.categories must not repeat labels',
                 parameter='scope.categories')
        result['categories'] = copy.deepcopy(categories)
    return result


def budget_configure(editor, *, reporting_currency, rates, scope=None):
    require_money_version(editor)
    reporting = currency(reporting_currency, 'reporting_currency')
    if not isinstance(rates, list):
        fail('INVALID_ARGUMENT', 'rates must be a list of ExchangeRate handles', parameter='rates')
    refs, bases = [], set()
    for index, value in enumerate(rates):
        ref = editor.ref(value, {'exchange_rate'})
        if ref in refs:
            fail('INVALID_ARGUMENT', 'Do not select the same ExchangeRate twice', parameter='rates')
        record = editor.record(value, {'exchange_rate'})
        usable, reason = _usable_rate(editor.package, record, reporting)
        if not usable:
            fail('INVALID_ARGUMENT', 'Selected ExchangeRate is not usable for this reporting currency',
                 parameter=f'rates[{index}]', reason=reason)
        if record['base_currency'] in bases:
            fail('INVALID_ARGUMENT', 'Select at most one direct rate for each base currency',
                 parameter='rates', base_currency=record['base_currency'])
        bases.add(record['base_currency'])
        refs.append(ref)
    trip = editor.package['trip']
    trip['reporting_currency'] = reporting
    trip['budget_rate_refs'] = refs
    if scope is not None:
        trip['budget_scope'] = budget_scope_value(scope)
    trip_ref = {'type': 'trip', 'id': trip['id']}
    handle = next((name for name, ref in editor.state['handles'].items() if ref == trip_ref), None)
    if handle is None:
        fail('STATE_FORMAT', 'Workspace trip handle is missing')
    return {'handle': handle}


def _precision(values):
    decimals = [Decimal(value) for value in values]
    return max(28, sum(len(value.as_tuple().digits) + abs(value.as_tuple().exponent)
                       for value in decimals) + len(decimals) + 10)


def _format_decimal(value):
    result = format(value, 'f')
    if '.' in result:
        result = result.rstrip('0').rstrip('.')
    return result or '0'


def _sum_amounts(values):
    if not values:
        return None
    with localcontext() as context:
        context.prec = _precision(values)
        return _format_decimal(sum((Decimal(value) for value in values), Decimal(0)))


def _multiply_amount(amount, rate):
    with localcontext() as context:
        context.prec = _precision([amount, rate])
        return _format_decimal(Decimal(amount) * Decimal(rate))


def _value_currency(value):
    if value['kind'] == 'exact':
        return value['money']['currency']
    if value['kind'] in {'range', 'from'}:
        return value['min']['currency']
    return value.get('currency')


def _bounds(value):
    if value['kind'] == 'exact':
        amount = value['money']['amount']
        return amount, amount
    if value['kind'] == 'range':
        return value['min']['amount'], value['max']['amount']
    if value['kind'] == 'from':
        return value['min']['amount'], None
    return None, None


def _value_from_bounds(lowers, uppers, currency_code):
    if not lowers:
        return None
    low = _sum_amounts(lowers)
    if any(value is None for value in uppers):
        return {'kind': 'from', 'min': {'amount': low, 'currency': currency_code}}
    high = _sum_amounts(uppers)
    if low == high:
        return {'kind': 'exact', 'money': {'amount': low, 'currency': currency_code}}
    return {'kind': 'range', 'min': {'amount': low, 'currency': currency_code},
            'max': {'amount': high, 'currency': currency_code}}


def _convert_value(value, rate, currency_code):
    if value['kind'] == 'unknown':
        return None
    if value['kind'] == 'exact':
        return {'kind': 'exact', 'money': {
            'amount': _multiply_amount(value['money']['amount'], rate),
            'currency': currency_code}}
    result = {'kind': value['kind'], 'min': {
        'amount': _multiply_amount(value['min']['amount'], rate),
        'currency': currency_code}}
    if value['kind'] == 'range':
        result['max'] = {'amount': _multiply_amount(value['max']['amount'], rate),
                         'currency': currency_code}
    return result


def budget_projection(package):
    active = [value for value in package.get('costs', [])
              if value.get('status') == 'active']
    trip = package.get('trip', {})
    projection = {
        'status': 'recorded_costs' if active else 'no_recorded_costs',
        'costs': [],
        'original_currency_groups': [],
    }
    if 'budget_scope' in trip:
        projection['budget_scope'] = copy.deepcopy(trip['budget_scope'])
    reporting_currency = trip.get('reporting_currency')
    if reporting_currency is not None:
        projection['reporting_currency'] = reporting_currency

    rates_by_id = {value.get('id'): value for value in package.get('exchange_rates', [])}
    selected = []
    bases = {}
    duplicate_bases = set()
    for ref in trip.get('budget_rate_refs', []):
        record = rates_by_id.get(ref.get('id'))
        if record is None:
            selected.append({'rate_ref': copy.deepcopy(ref), 'usable': False,
                             'reason': 'rate_missing'})
            continue
        usable, reason = _usable_rate(package, record, reporting_currency)
        entry = {'rate_ref': copy.deepcopy(ref), 'base_currency': record.get('base_currency'),
                 'quote_currency': record.get('quote_currency'), 'rate': record.get('rate'),
                 'as_of': record.get('as_of'), 'usable': usable}
        if reason is not None:
            entry['reason'] = reason
        selected.append(entry)
        base = record.get('base_currency')
        if base in bases:
            duplicate_bases.add(base)
        else:
            bases[base] = record
    for entry in selected:
        if entry.get('base_currency') in duplicate_bases:
            entry['usable'] = False
            entry['reason'] = 'duplicate_base_currency'
    usable_rates = {base: record for base, record in bases.items()
                    if base not in duplicate_bases
                    and _usable_rate(package, record, reporting_currency)[0]}
    projection['selected_rates'] = selected

    groups = {}
    reporting_values = []
    reporting = ({'currency': reporting_currency, 'included_cost_refs': [],
                  'missing_conversion_cost_refs': [], 'unknown_amount_cost_refs': [],
                  'unknown_currency_cost_refs': []}
                 if reporting_currency is not None else None)
    for cost in active:
        slot = 'confirmed' if 'confirmed' in cost else 'estimate'
        value = copy.deepcopy(cost[slot])
        ref = {'type': 'cost', 'id': cost['id']}
        entry = {'cost_ref': ref, 'slot': slot, 'value': value,
                 'completeness': cost['completeness'],
                 'target_refs': copy.deepcopy(cost['target_refs'])}
        projection['costs'].append(entry)
        code = _value_currency(value)
        group = groups.setdefault(code, {'currency': code, 'cost_refs': [], 'lowers': [],
                                         'uppers': [], 'unknown_cost_refs': []})
        group['cost_refs'].append(ref)
        low, high = _bounds(value)
        if low is None:
            group['unknown_cost_refs'].append(ref)
        else:
            group['lowers'].append(low)
            group['uppers'].append(high)

        if reporting is None:
            continue
        if value['kind'] == 'unknown':
            entry['reporting'] = {'status': 'amount_unknown',
                                  'reporting_currency': reporting_currency}
            reporting['unknown_amount_cost_refs'].append(ref)
            if code is None:
                reporting['unknown_currency_cost_refs'].append(ref)
            continue
        if code is None:
            entry['reporting'] = {'status': 'currency_unknown',
                                  'reporting_currency': reporting_currency}
            reporting['unknown_currency_cost_refs'].append(ref)
            continue
        if code == reporting_currency:
            converted = copy.deepcopy(value)
            entry['reporting'] = {'status': 'same_currency', 'value': converted}
        elif code in usable_rates:
            rate = usable_rates[code]
            converted = _convert_value(value, rate['rate'], reporting_currency)
            entry['reporting'] = {
                'status': 'converted', 'value': converted,
                'rate_ref': {'type': 'exchange_rate', 'id': rate['id']},
                'rate': rate['rate'], 'as_of': rate['as_of'],
            }
        else:
            entry['reporting'] = {'status': 'missing_rate',
                                  'reporting_currency': reporting_currency}
            reporting['missing_conversion_cost_refs'].append(ref)
            continue
        reporting['included_cost_refs'].append(ref)
        reporting_values.append(converted)

    for group in groups.values():
        result = {'currency': group['currency'], 'cost_refs': group['cost_refs']}
        if group['currency'] is not None:
            known = _value_from_bounds(group['lowers'], group['uppers'], group['currency'])
            if known is not None:
                result['known_part'] = known
        result['unknown_cost_refs'] = group['unknown_cost_refs']
        projection['original_currency_groups'].append(result)

    if reporting is not None:
        lowers, uppers = [], []
        for value in reporting_values:
            low, high = _bounds(value)
            if low is not None:
                lowers.append(low)
                uppers.append(high)
        known = _value_from_bounds(lowers, uppers, reporting_currency)
        if known is not None:
            reporting['known_part'] = known
        projection['reporting'] = reporting

    reasons = []
    scope = trip.get('budget_scope')
    if not active:
        reasons.append('no_recorded_costs')
    if scope is None or scope.get('status') != 'complete':
        reasons.append('budget_scope_not_declared_complete')
    if scope and scope.get('categories'):
        reasons.append('category_scope_not_global')
    if any(cost.get('completeness') != 'complete' for cost in active):
        reasons.append('cost_completeness_not_complete')
    if any(cost['confirmed' if 'confirmed' in cost else 'estimate']['kind'] in {'unknown', 'from'}
           for cost in active):
        reasons.append('amount_not_fully_bounded')
    if active and reporting_currency is None:
        reasons.append('reporting_currency_not_configured')
    if reporting is not None:
        if reporting['missing_conversion_cost_refs']:
            reasons.append('missing_conversion')
        if reporting['unknown_currency_cost_refs']:
            reasons.append('currency_unknown')
    projection['completeness'] = ({'status': 'caller_declared_complete',
                                   'basis': 'caller_declaration'}
                                  if not reasons else {'status': 'not_established',
                                                       'reasons': reasons})
    return projection
