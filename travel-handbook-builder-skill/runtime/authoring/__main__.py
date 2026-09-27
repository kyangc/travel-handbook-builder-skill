"""Single-writer local CLI; state and successful receipts share one file."""
import argparse
import json
import os
import sys
from pathlib import Path
import tempfile

from . import core
from .client import ManagedHandbook
from scripts.validate_trip import load_json


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise core.AuthoringError('INVALID_CLI', message)


def read_json(path):
    try:
        return load_json(path)
    except (OSError, UnicodeError, ValueError) as error:
        raise core.AuthoringError('INPUT_ERROR', str(error), path=str(path)) from error


def write_json(path, value, *, replace):
    """Commit one local file, without claiming concurrent-writer protection."""
    path = Path(path)
    if not replace and os.path.lexists(path):
        raise core.AuthoringError('TARGET_EXISTS', 'Output already exists', path=str(path))
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         dir=path.parent, prefix='.' + path.name + '.',
                                         suffix='.tmp', delete=False) as output:
            temporary = Path(output.name)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        if not replace and os.path.lexists(path):
            raise core.AuthoringError('TARGET_EXISTS', 'Output already exists', path=str(path))
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def add_read_options(command):
    command.add_argument('--report', choices=['map-coverage'],
                         help='Read-only Day/Place/Stop/Recommendation/AccessPoint/Path coverage; paginate rows with --cursor')
    command.add_argument('--day', metavar='DAY_HANDLE',
                         help='Current Day handle, not a date/name; first read --type day and follow pagination')
    command.add_argument('--type', dest='types', action='append', metavar='OBJECT_TYPE',
                         help='Model object type such as day, place, task, media, transport_service; repeatable')
    command.add_argument('--handle', dest='handles', action='append', metavar='OBJECT_HANDLE',
                         help='Current handle of any object; repeatable')
    command.add_argument('--limit', type=int)
    command.add_argument('--cursor')
    command.add_argument('--include-source-text', action='store_true')
    command.add_argument('--omit-capabilities', action='store_false', dest='include_capabilities',
                         help='Omit only repeated capability metadata; keep full objects, related handles, revision and pagination. Default includes capabilities.')


def read_options(args):
    selection = {}
    for name in ('day', 'types', 'handles'):
        value = getattr(args, name)
        if value is not None:
            selection[name] = value
    local = bool(selection or args.limit is not None or args.cursor is not None
                 or args.include_source_text)
    return {'selection': selection if local else None, 'limit': args.limit,
            'cursor': args.cursor, 'include_source_text': args.include_source_text,
            **({'include_capabilities': False} if not args.include_capabilities else {}),
            **({'report': args.report} if args.report is not None else {})}


def parser():
    result = Parser(description='Local travel authoring prototype. Use one writer per state file.')
    commands = result.add_subparsers(dest='command', required=True, parser_class=Parser)
    create = commands.add_parser('create')
    create.add_argument('state', type=Path)
    create.add_argument('--title', required=True)
    create.add_argument('--example', action='store_true')
    import_command = commands.add_parser('import')
    import_command.add_argument('package', type=Path)
    import_command.add_argument('state', type=Path)
    read = commands.add_parser('read')
    read.add_argument('state', type=Path)
    add_read_options(read)
    check = commands.add_parser('check')
    check.add_argument('state', type=Path)
    apply = commands.add_parser('apply')
    apply.add_argument('state', type=Path)
    apply.add_argument('request', type=Path)
    preview = commands.add_parser('preview')
    preview.add_argument('state', type=Path)
    preview.add_argument('request', type=Path)
    export = commands.add_parser('export')
    export.add_argument('state', type=Path)
    export.add_argument('output', type=Path)
    export.add_argument('--revision', type=int, required=True)
    client = commands.add_parser('client')
    client_commands = client.add_subparsers(
        dest='client_command', required=True, parser_class=Parser)
    client_init = client_commands.add_parser('init')
    client_init.add_argument('root', type=Path)
    client_source = client_init.add_mutually_exclusive_group(required=True)
    client_source.add_argument('--state', type=Path)
    client_source.add_argument('--package', type=Path)
    client_context = client_commands.add_parser('context',
        description='Place-only context. Use --handle PLACE_HANDLE or --name PLACE_NAME; --target is not supported. For other objects use client read ROOT --handle OBJECT_HANDLE.')
    client_context.add_argument('root', type=Path)
    client_target = client_context.add_mutually_exclusive_group(required=True)
    client_target.add_argument('--handle', metavar='PLACE_HANDLE', help='Current Place handle only')
    client_target.add_argument('--name', metavar='PLACE_NAME', help='Exact Place name; ambiguity is reported, never guessed')
    client_context.add_argument('--source-text', dest='source_text_handles', action='append')
    client_read = client_commands.add_parser('read')
    client_read.add_argument('root', type=Path)
    add_read_options(client_read)
    client_check = client_commands.add_parser('check')
    client_check.add_argument('root', type=Path)
    client_prepare = client_commands.add_parser('prepare-place')
    client_prepare.add_argument('root', type=Path)
    client_prepare.add_argument('edit', type=Path)
    client_prepare_request = client_commands.add_parser('prepare-request')
    client_prepare_request.add_argument('root', type=Path)
    client_prepare_request.add_argument('request', type=Path)
    client_commit = client_commands.add_parser('commit')
    client_commit.add_argument('root', type=Path)
    client_commit.add_argument('operation_id')
    client_status = client_commands.add_parser('status')
    client_status.add_argument('root', type=Path)
    return result


def execute(args):
    if args.command == 'create':
        state = core.new_workspace(args.title, example=args.example)
        write_json(args.state, state, replace=False)
        return {'created': True, 'state': str(args.state),
                'workspace_id': state['workspace_id'], 'revision': state['revision']}, 0
    if args.command == 'import':
        state = core.import_package(read_json(args.package))
        write_json(args.state, state, replace=False)
        return {'imported': True, 'state': str(args.state),
                'workspace_id': state['workspace_id'], 'revision': state['revision'],
                'import_report': state['import_report']}, 0
    if args.command == 'client':
        if args.client_command == 'init':
            if args.state is not None:
                book = ManagedHandbook.initialize(args.root, state=read_json(args.state))
            else:
                book = ManagedHandbook.initialize(args.root, package=read_json(args.package))
            return book.status(), 0
        book = ManagedHandbook.open(args.root)
        if args.client_command == 'read':
            return book.read(**read_options(args)), 0
        if args.client_command == 'check':
            result = book.check()
            return result, 0 if result['report']['valid'] else 1
        if args.client_command == 'context':
            target = {'handle': args.handle} if args.handle is not None else {'name': args.name}
            return book.place_context(
                target=target, source_text_handles=args.source_text_handles), 0
        if args.client_command == 'prepare-place':
            result = book.prepare_place_enrichment(read_json(args.edit))
            return result, 0 if result.get('status') in {'prepared', 'no_change'} else 2
        if args.client_command == 'prepare-request':
            return book.prepare_request(read_json(args.request)), 0
        if args.client_command == 'commit':
            result = book.commit(args.operation_id)
            return result, 0 if result.get('publish_status') == 'current' else 3
        return book.status(), 0

    # Resolve an existing state symlink consistently for reading and replacement.
    state_path = args.state.resolve()
    state = read_json(state_path)
    if args.command == 'read':
        return core.read_workspace(state, **read_options(args)), 0
    if args.command == 'check':
        report = core.check(state)
        return report, 0 if report['valid'] else 1
    if args.command == 'apply':
        candidate, receipt = core.apply(state, read_json(args.request))
        if not receipt['replayed']:
            write_json(state_path, candidate, replace=True)
        return receipt, 0
    if args.command == 'preview':
        return core.preview(state, read_json(args.request)), 0
    artifact = core.export_package(state, revision=args.revision)
    write_json(args.output, artifact['package'], replace=False)
    return {'exported': True, 'output': str(args.output),
            'manifest': artifact['manifest'], 'validation': artifact['validation']}, 0


def _read_recovery(result, args, argv):
    """Attach executable argument lists without resolving dates/names or guessing intent."""
    if args is not None and result.get('parameter') == 'selection.day':
        prefix = ['client', 'read', str(args.root)] if args.command == 'client' else ['read', str(args.state)]
        result['recovery'] = {'argv': [*prefix, '--type', 'day', '--limit', '50'],
                              'then': 'Follow pagination, choose the returned handle by record.date, and retry --day DAY_HANDLE.'}
    if (result.get('code') == 'INVALID_CLI' and argv[:2] == ['client', 'context']
            and any(value == '--target' or value.startswith('--target=') for value in argv[2:])):
        result['message'] = '--target is not supported; client context accepts --handle PLACE_HANDLE or --name PLACE_NAME'
        result['parameter'] = '--target'
        result['recovery_hint'] = 'context is Place-only. For other objects use client read ROOT --handle OBJECT_HANDLE. No target was inferred.'
        if len(argv) > 2 and not argv[2].startswith('-'):
            result['recovery'] = {'argv': ['client', 'context', argv[2], '--help']}
    return result


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = None
    try:
        args = parser().parse_args(argv)
        result, status = execute(args)
    except core.AuthoringError as error:
        result, status = _read_recovery(error.as_dict(), args, argv), 1
    except OSError as error:
        result, status = {'committed': False, 'code': 'IO_ERROR', 'message': str(error)}, 1
    except Exception as error:
        result, status = {'committed': False, 'code': 'INTERNAL_ERROR',
                          'message': f'{type(error).__name__}: {error}'}, 1
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
