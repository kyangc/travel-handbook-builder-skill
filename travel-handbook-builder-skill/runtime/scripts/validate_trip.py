#!/usr/bin/env python3
"""Offline structural validation plus explicitly bounded domain checks."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
from model_checks import check_package, coverage_plan_issues
from time_constraints import evaluate_constraint
from time_checks import time_diagnostics
from domain_checks import (cross_field_errors, shopping_place_warnings,
                           task_dependency_warnings, trip_range_warnings)

FORMATS = FormatChecker()

@FORMATS.checks('iana-timezone')
def valid_zone(value):
    if not isinstance(value, str):
        return True
    try:
        ZoneInfo(value)
        return True
    except (ValueError, ZoneInfoNotFoundError):
        return False

@FORMATS.checks('local-date-time')
def valid_local(value):
    if not isinstance(value, str):
        return True
    try:
        return 'T' in value and datetime.fromisoformat(value).tzinfo is None
    except ValueError:
        return False


def pointer(path):
    return '/' + '/'.join(str(p).replace('~', '~0').replace('/', '~1') for p in path) if path else ''


def validator(version='1.0'):
    # Unknown versions use the stable schema and receive an ordinary
    # schema_version diagnostic instead of an unchecked dispatch error.
    schema_dir = ROOT / 'schemas' / 'v1'
    schema_uri = 'https://travel-handbook.invalid/schema/v1/'
    resources = []
    for file in sorted(schema_dir.glob('*.schema.json')):
        schema = json.loads(file.read_text())
        Draft202012Validator.check_schema(schema)
        resources.append((schema_uri + file.name, Resource.from_contents(schema)))
    registry = Registry().with_resources(resources)
    schema = json.loads((schema_dir / 'trip.schema.json').read_text())
    return Draft202012Validator(schema, registry=registry, format_checker=FORMATS)


def validate(package):
    errors = []
    warnings = []
    for error in sorted(validator(package.get('schema_version') if isinstance(package, dict) else None).iter_errors(package), key=lambda e: str(list(e.absolute_path))):
        errors.append({'code': 'SCHEMA_' + str(error.validator).upper(), 'path': pointer(error.absolute_path), 'message': error.message})
    if errors:
        return {'valid': False, 'errors': errors, 'warnings': warnings, 'scope': 'structure; semantics not run'}
    try:
        resolve = check_package(package, require_example=False)
    except (ValueError, KeyError, TypeError, IndexError) as error:
        errors.append({'code': 'DOMAIN_INVARIANT', 'path': '', 'message': str(error)})
        return {'valid': False, 'errors': errors, 'warnings': warnings, 'scope': 'structure and bounded semantics (first domain error)'}
    if package.get('schema_version') in ('1.0',):
        time_errors, time_warnings, time_assessments = time_diagnostics(package)
        errors.extend(time_errors)
        warnings.extend(time_warnings)
        from transport_checks import transport_diagnostics
        transport_errors, transport_warnings, transport_assessments = transport_diagnostics(package)
        errors.extend(transport_errors)
        warnings.extend(transport_warnings)
    errors.extend(cross_field_errors(package))
    projection = None
    if package.get('schema_version') in ('1.0',):
        from coverage_checks import coverage_revision_errors, coverage_projection
        errors.extend(coverage_revision_errors(package))
        if not errors:
            projection = coverage_projection(package)
            current = set(projection['current_coverage_ids'])
            effective = {(entry['coverage_ref']['id'], entry['scope_ref']['id']) for entry in projection['effective_scopes']}
            projected = {**package, 'coverages': [
                {**coverage, 'scopes': [scope for scope in coverage['scopes'] if (coverage['id'], scope['id']) in effective]}
                for coverage in package.get('coverages', []) if coverage['id'] in current]}
            warnings.extend(coverage_plan_issues(projected, resolve))
    else:
        warnings.extend(coverage_plan_issues(package, resolve))
    warnings.extend(shopping_place_warnings(package))
    warnings.extend(task_dependency_warnings(package))
    if package.get('schema_version') in ('1.0',):
        warnings.extend(trip_range_warnings(package))
    if package.get('schema_version') not in ('1.0',):
        for collection in ('items', 'activities'):
            for index, obj in enumerate(package.get(collection, [])):
                if obj.get('lifecycle', 'current') != 'current':
                    continue
                for number, constraint in enumerate(obj.get('timing', {}).get('constraints', [])):
                    result = evaluate_constraint(obj['timing'], constraint, resolve)
                    if result['status'] != 'satisfied':
                        warnings.append({'code': 'TIME_CONSTRAINT_' + result['status'].upper(), 'path': f'/{collection}/{index}/timing/constraints/{number}', **result})
    result = {'valid': not errors, 'errors': errors, 'warnings': warnings,
              'scope': 'structure and bounded semantics; not travel feasibility, factual verification, rendering or generation quality'}
    if package.get('schema_version') in ('1.0',):
        result['time_assessments'] = time_assessments
        result['transport_assessments'] = transport_assessments
    if projection is not None:
        result['coverage_projection'] = projection
    return result


def load_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid_number(value):
        raise ValueError('non-JSON numeric constant: ' + value)
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_object, parse_constant=invalid_number)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path)
    args = parser.parse_args()
    failed = False
    for path in args.files:
        try:
            result = validate(load_json(path))
        except (OSError, ValueError) as error:
            result = {'valid': False, 'errors': [{'code': 'INPUT_ERROR', 'path': '', 'message': str(error)}], 'warnings': []}
        print(json.dumps({'file': str(path), **result}, ensure_ascii=False))
        failed |= not result['valid']
    return int(failed)

if __name__ == '__main__':
    raise SystemExit(main())
