"""Private persistence primitives for the managed authoring client."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import uuid

from .errors import AuthoringError


CLIENT_FORMAT = "travel-handbook-managed-client-1"
MARKER_NAME = ".travel-handbook-client.json"
LOCK_NAME = ".travel-handbook-client.lock"
STATE_NAME = "trip-state.json"
CANONICAL_NAME = "private-handbook.json"
REPORT_NAME = "export-report.json"
OPERATIONS_NAME = "operations"


class ClientError(AuthoringError):
    """Structured failure raised by the managed client."""


def json_bytes(value):
    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                           allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ClientError("CLIENT_INPUT_ERROR", f"Value must be finite JSON: {error}") from error


def read_json(path):
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ClientError("CLIENT_UNSAFE_PATH", "Managed JSON must be a regular file",
                              path=str(path))

        def object_pairs(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError(f"duplicate JSON key: {key}")
                value[key] = item
            return value

        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=object_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number: {value}")),
        )
    except ClientError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ClientError("CLIENT_STORAGE_INVALID", f"Cannot read managed JSON: {path.name}",
                          path=str(path), reason=str(error)) from error
    except ValueError as error:
        raise ClientError("CLIENT_STORAGE_INVALID", f"Cannot read managed JSON: {path.name}",
                          path=str(path), reason=str(error)) from error


def _fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_json(path, value):
    payload = json_bytes(value)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp",
                                                   dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        json.loads(temporary.read_text(encoding="utf-8"))
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def file_sha256(path):
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ClientError("CLIENT_UNSAFE_PATH", "Managed file must be a regular file",
                              path=str(path))
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except ClientError:
        raise
    except OSError as error:
        raise ClientError("CLIENT_STORAGE_INVALID", "Cannot hash managed file",
                          path=str(path), reason=str(error)) from error


def value_sha256(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def _write_new(path, payload):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    open_descriptor = descriptor
    try:
        with os.fdopen(descriptor, "wb") as stream:
            open_descriptor = None
            split = len(payload) // 2
            stream.write(payload[:split])
            stream.flush()
            _fault(f"after_partial_new_file:{path.name}")
            stream.write(payload[split:])
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if open_descriptor is not None:
            os.close(open_descriptor)
        path.unlink(missing_ok=True)
        raise


def initialize_layout(root, *, marker, state, canonical, report):
    root = Path(root).expanduser().absolute()
    if root.is_symlink():
        raise ClientError("CLIENT_UNSAFE_PATH", "Managed root cannot be a symlink", path=str(root))
    created_root = False
    if root.exists():
        if not root.is_dir():
            raise ClientError("CLIENT_UNSAFE_PATH", "Managed root must be a directory", path=str(root))
        if any(root.iterdir()):
            raise ClientError("CLIENT_TARGET_NOT_EMPTY", "Managed root must be absent or empty",
                              path=str(root))
    else:
        root.mkdir(parents=False)
        created_root = True

    created = []
    try:
        operations = root / OPERATIONS_NAME
        operations.mkdir()
        created.append(operations)
        for name, payload in (
            (LOCK_NAME, b""),
            (STATE_NAME, json_bytes(state)),
            (CANONICAL_NAME, json_bytes(canonical)),
            (REPORT_NAME, json_bytes(report)),
            (MARKER_NAME, json_bytes(marker)),
        ):
            path = root / name
            _write_new(path, payload)
            created.append(path)
        _fsync_directory(root)
        return root
    except Exception:
        for path in reversed(created):
            try:
                path.rmdir() if path.is_dir() else path.unlink()
            except FileNotFoundError:
                pass
        if created_root:
            try:
                root.rmdir()
            except OSError:
                pass
        raise


def _require_regular(path):
    try:
        metadata = path.lstat()
    except FileNotFoundError as error:
        raise ClientError("CLIENT_STORAGE_INVALID", "Managed path is missing", path=str(path)) from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ClientError("CLIENT_UNSAFE_PATH", "Managed path must be a regular file", path=str(path))


def validate_layout(root):
    root = Path(root).expanduser().absolute()
    if root.is_symlink() or not root.is_dir():
        raise ClientError("CLIENT_UNSAFE_PATH", "Managed root must be a real directory", path=str(root))
    marker_path = root / MARKER_NAME
    _require_regular(marker_path)
    marker = read_json(marker_path)
    if not isinstance(marker, dict) or marker.get("format") != CLIENT_FORMAT:
        raise ClientError("CLIENT_MARKER_INVALID", "Directory is not initialized by this client",
                          path=str(marker_path))
    if marker.get("recovery_mode") not in {"full_state", "package_only"}:
        raise ClientError("CLIENT_MARKER_INVALID", "Managed marker has an invalid recovery mode",
                          path=str(marker_path))
    if not isinstance(marker.get("workspace_id"), str) or not marker["workspace_id"]:
        raise ClientError("CLIENT_MARKER_INVALID", "Managed marker has no workspace identity",
                          path=str(marker_path))
    expected_paths = {
        "state": STATE_NAME,
        "canonical": CANONICAL_NAME,
        "report": REPORT_NAME,
        "operations": OPERATIONS_NAME,
        "lock": LOCK_NAME,
    }
    if marker.get("paths") != expected_paths:
        raise ClientError("CLIENT_MARKER_INVALID", "Managed marker paths do not match the fixed layout",
                          path=str(marker_path))
    for name in (STATE_NAME, CANONICAL_NAME, REPORT_NAME, LOCK_NAME):
        _require_regular(root / name)
    operations = root / OPERATIONS_NAME
    if operations.is_symlink() or not operations.is_dir():
        raise ClientError("CLIENT_UNSAFE_PATH", "Operations path must be a real directory",
                          path=str(operations))
    return root, marker


def create_operation(root, *, intent, request_id, intent_sha256, kind=None):
    operations = root / OPERATIONS_NAME
    operation_id = "op-" + uuid.uuid4().hex
    temporary = operations / ("." + operation_id + ".tmp")
    final = operations / operation_id
    temporary.mkdir()
    try:
        _write_new(temporary / "intent.json", json_bytes(intent))
        initial_status = {
            "phase": "intent_saved",
            "request_id": request_id,
            "intent_sha256": intent_sha256,
        }
        if kind is not None:
            initial_status["kind"] = kind
        _write_new(temporary / "status.json", json_bytes(initial_status))
        _fsync_directory(temporary)
        os.replace(temporary, final)
        _fsync_directory(operations)
        return operation_id, final
    finally:
        if temporary.exists():
            for child in temporary.iterdir():
                child.unlink()
            temporary.rmdir()


def operation_path(root, operation_id):
    if (not isinstance(operation_id, str) or len(operation_id) != 35
            or not operation_id.startswith("op-")
            or any(character not in "0123456789abcdef" for character in operation_id[3:])):
        raise ClientError("CLIENT_OPERATION_NOT_FOUND", "Operation ID is not valid")
    path = root / OPERATIONS_NAME / operation_id
    if path.is_symlink() or not path.is_dir():
        raise ClientError("CLIENT_OPERATION_NOT_FOUND", "Operation does not exist",
                          operation_id=operation_id)
    return path


def operation_directories(root):
    result = []
    for path in (root / OPERATIONS_NAME).iterdir():
        if path.name.startswith("."):
            continue
        if path.is_symlink() or not path.is_dir():
            raise ClientError("CLIENT_UNSAFE_PATH", "Operation entry must be a real directory",
                              path=str(path))
        result.append(path)
    return sorted(result, key=lambda path: path.name)


def _fault(point):
    """Internal no-op seam used by isolated crash tests."""


@contextmanager
def locked(root):
    lock_path = root / LOCK_NAME
    _require_regular(lock_path)
    descriptor = os.open(lock_path, os.O_RDWR)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
