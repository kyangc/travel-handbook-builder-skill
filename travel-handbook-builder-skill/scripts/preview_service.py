#!/usr/bin/env python3
"""Own one detached loopback preview for an initialized managed handbook."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "runtime"))

from authoring.client import ClientError, ManagedHandbook  # noqa: E402


class ServiceError(Exception):
    pass


def port_number(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return port


def root_path(raw: str) -> Path:
    path = Path(raw).expanduser().absolute()
    if path.is_symlink() or not path.is_dir():
        raise ServiceError("ROOT must be an existing non-symlink managed directory")
    return path.resolve()


def control_path(root: Path) -> Path:
    key = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:20]
    return root.parent / f".travel-handbook-preview-{key}"


def checked_directory(path: Path, *, create: bool) -> bool:
    try:
        if create:
            path.mkdir(mode=0o700)
    except FileExistsError:
        pass
    except OSError as error:
        raise ServiceError(f"cannot create private control directory: {error}") from error
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid()
            or metadata.st_mode & 0o077):
        raise ServiceError("control directory is not a private, owned directory")
    return True


@contextmanager
def locked_control(path: Path, *, create: bool):
    flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    if create:
        flags |= os.O_CREAT
    descriptor = os.open(path / "lock", flags, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                or metadata.st_mode & 0o077):
            raise ServiceError("control lock is not an owned regular file")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def read_record(path: Path) -> dict | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
            or metadata.st_mode & 0o077):
        raise ServiceError("service record is not a private, owned regular file")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ServiceError(f"service record is invalid: {error}") from error
    required = {"root": str, "export": str, "pid": int, "birth": str,
                "instance": str, "port": int, "url": str}
    if (not isinstance(record, dict)
            or any(type(record.get(key)) is not kind for key, kind in required.items())
            or record["pid"] <= 0 or not 1 <= record["port"] <= 65535
            or not re.fullmatch(r"[0-9a-f]{32}", record["instance"])
            or record["url"] != f'http://127.0.0.1:{record["port"]}/'):
        raise ServiceError("service record has an invalid shape")
    return record


def write_record(path: Path, record: dict) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".instance-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def birth_identity(pid: int) -> str | None:
    """Return an OS birth signature; never fall back to PID alone."""
    if sys.platform.startswith("linux"):
        try:
            line = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
            fields = line.rsplit(")", 1)[1].split()
            if fields[0].startswith("Z"):
                return None
            boot = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
            return f"linux:{boot}:{fields[19]}"
        except (OSError, IndexError, ValueError):
            return None
    if sys.platform == "darwin":
        result = subprocess.run(
            ["/bin/ps", "-o", "lstart=", "-o", "stat=", "-p", str(pid)],
            text=True, capture_output=True, check=False,
        )
        parts = result.stdout.strip().rsplit(None, 1)
        if result.returncode != 0 or len(parts) != 2 or parts[1].startswith("Z"):
            return None
        return f"darwin:{parts[0]}"
    return None


def process_gone(pid: int) -> bool:
    """Recognize a dead or zombie recorded process, not an unknown live PID."""
    if sys.platform.startswith("linux"):
        try:
            line = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
            return line.rsplit(")", 1)[1].split()[0].startswith("Z")
        except FileNotFoundError:
            return True
        except (OSError, IndexError, ValueError):
            return False
    if sys.platform == "darwin":
        result = subprocess.run(
            ["/bin/ps", "-o", "stat=", "-p", str(pid)],
            text=True, capture_output=True, check=False,
        )
        if result.returncode != 0:
            return not result.stdout.strip() and not result.stderr.strip()
        return result.stdout.strip().startswith("Z")
    return False


def api_probe(port: int) -> tuple[int, str | None, int | None] | None:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.5)
    try:
        connection.request("GET", "/api/handbook")
        response = connection.getresponse()
        instance = response.getheader("X-Travel-Preview-Instance")
        body = response.read()
        revision = None
        if response.status == 200:
            try:
                package = json.loads(body)
            except (ValueError, UnicodeError):
                package = None
            if isinstance(package, dict):
                revision = package.get("revision")
        return response.status, instance, revision
    except (OSError, TimeoutError, ValueError, http.client.HTTPException):
        return None
    finally:
        connection.close()


def managed_status(root: Path) -> tuple[dict | None, str | None]:
    try:
        status = ManagedHandbook.open(root).status()
        if status["canonical_path"] != str(root / "private-handbook.json"):
            raise ServiceError("managed canonical path differs from selected ROOT")
        return status, None
    except ClientError as error:
        return None, f"{error.code}: {error}"


def service_status(root: Path, control: Path, record: dict | None) -> dict:
    managed, data_error = managed_status(root)
    result = {"state": "stopped", "ready": False, "owned": False,
              "url": record["url"] if record else None,
              "pid": record["pid"] if record else None,
              "instance": record["instance"] if record else None,
              "export": str(root / "private-handbook.json"),
              "revision": None, "publish_status": managed["publish_status"] if managed else None,
              "data_error": data_error, "control_dir": str(control)}
    if record is None:
        return result
    if record["root"] != str(root) or record["export"] != result["export"]:
        result["state"] = "identity_mismatch"
        return result
    birth = birth_identity(record["pid"])
    probe = api_probe(record["port"])
    if birth is None:
        if probe is not None:
            if process_gone(record["pid"]):
                result["port_conflict"] = True
            else:
                result["state"] = "identity_mismatch"
        result["stale_process"] = True
        return result
    if birth != record["birth"] or probe is None or probe[1] != record["instance"]:
        result["state"] = "identity_mismatch"
        return result
    result["owned"] = True
    result["revision"] = probe[2]
    if (data_error is not None or managed["publish_status"] != "current"
            or probe[0] != 200 or probe[2] != managed["canonical_revision"]):
        result["state"] = "stale_data"
    else:
        result["state"] = "ready"
        result["ready"] = True
    return result


def ready_line(log: Path) -> dict | None:
    try:
        with log.open(encoding="utf-8") as stream:
            line = stream.readline()
        return json.loads(line) if line else None
    except (OSError, UnicodeError, ValueError):
        return None


def start(root: Path, control: Path, record_path: Path, requested_port: int | None,
          allow_new_url: bool) -> dict:
    existing = read_record(record_path)
    current = service_status(root, control, existing)
    if existing is not None:
        if current["state"] == "ready":
            if requested_port not in (None, 0, existing["port"]):
                raise ServiceError("requested port differs from the existing service URL")
            current["reused"] = True
            return current
        if current["owned"]:
            raise ServiceError("owned service is running but managed data is not ready")
        if current["state"] == "identity_mismatch":
            raise ServiceError("service identity mismatch; refusing takeover")
    managed, data_error = managed_status(root)
    if data_error is not None:
        raise ServiceError(f"managed data is not ready: {data_error}")
    if managed["publish_status"] != "current":
        raise ServiceError("managed canonical is not currently published")
    export = root / "private-handbook.json"
    if export.is_symlink() or not export.is_file():
        raise ServiceError("managed canonical must be a regular non-symlink file")
    port = existing["port"] if existing else (8765 if requested_port is None else requested_port)
    if existing and allow_new_url:
        if requested_port is None:
            raise ServiceError("--new-url requires an explicit --port")
        port = requested_port
    elif existing and requested_port not in (None, 0, port):
        raise ServiceError("requested port differs from the previous URL; use --new-url to change it")
    instance = uuid.uuid4().hex
    log = control / f"{instance}.log"
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    command = [str(SKILL_DIR / "scripts" / "python"),
               str(SKILL_DIR / "scripts" / "preview_server.py"), str(export),
               "--port", str(port), "--instance-id", instance]
    child = None
    try:
        with os.fdopen(fd, "wb") as output:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                     stdout=output, stderr=output,
                                     close_fds=True, start_new_session=True)
        deadline = time.monotonic() + 12
        selected_port = None
        birth = None
        birth_seen = False
        while time.monotonic() < deadline:
            if child.poll() is not None:
                if "cannot bind loopback port" in log.read_text(encoding="utf-8"):
                    raise ServiceError(
                        f"loopback port {port} is occupied; the previous URL cannot be preserved"
                    )
                raise ServiceError("preview process exited before readiness; see private log")
            started = ready_line(log)
            if isinstance(started, dict):
                match = re.fullmatch(r"http://127\.0\.0\.1:(\d+)/", str(started.get("url")))
                if match and started.get("export") == str(export):
                    selected_port = int(match.group(1))
            birth = birth_identity(child.pid)
            birth_seen = birth_seen or birth is not None
            probe = api_probe(selected_port) if selected_port else None
            if (birth and probe and probe[0] == 200 and probe[1] == instance
                    and probe[2] == managed["canonical_revision"]):
                break
            time.sleep(0.05)
        else:
            if not birth_seen:
                raise ServiceError("process birth identity unavailable; lifecycle service unsupported")
            raise ServiceError("preview did not become identity-verified and data-ready")
        record = {"root": str(root), "export": str(export), "pid": child.pid,
                  "birth": birth, "instance": instance, "port": selected_port,
                  "url": f"http://127.0.0.1:{selected_port}/", "started_at": time.time(),
                  "log": str(log)}
        manifest = SKILL_DIR / "MANIFEST.json"
        if manifest.is_file():
            record["bundle_version"] = json.loads(manifest.read_text(encoding="utf-8"))["package"]["version"]
        write_record(record_path, record)
        result = service_status(root, control, record)
        if not result["ready"]:
            raise ServiceError("managed data changed during startup; check status")
        result["reused"] = False
        result["url_changed"] = bool(existing and existing["url"] != result["url"])
        if result["url_changed"]:
            result["previous_url"] = existing["url"]
        return result
    except Exception:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=3)
        if child is not None and record_path.exists():
            candidate = read_record(record_path)
            if candidate and candidate.get("instance") == instance:
                record_path.unlink()
        raise


def stop(root: Path, control: Path, record_path: Path) -> dict:
    record = read_record(record_path)
    if record is None:
        return service_status(root, control, None)
    current = service_status(root, control, record)
    if not current["owned"]:
        probe = api_probe(record["port"]) if current.get("stale_process") else None
        if probe is not None and probe[1] == record["instance"]:
            raise ServiceError("process birth identity unavailable; refusing to signal a process")
        raise ServiceError("service identity cannot be verified; refusing to signal a process")
    # Recheck immediately before signalling: PID alone is never sufficient.
    if birth_identity(record["pid"]) != record["birth"]:
        raise ServiceError("process birth identity changed; refusing to signal")
    os.kill(record["pid"], signal.SIGTERM)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        probe = api_probe(record["port"])
        if probe is None or probe[1] != record["instance"]:
            record_path.unlink()
            return service_status(root, control, None)
        time.sleep(0.05)
    raise ServiceError("service did not release its port after SIGTERM")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("action", choices=("start", "status", "stop"))
    result.add_argument("root", help="initialized managed ROOT")
    result.add_argument("--port", type=port_number, default=None,
                        help="start port (default 8765; 0 chooses an available port)")
    result.add_argument("--new-url", action="store_true",
                        help="explicitly choose a new URL after the previous process has died")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        root = root_path(args.root)
        control = control_path(root)
        if args.action == "start":
            checked_directory(control, create=True)
        elif not checked_directory(control, create=False):
            result = service_status(root, control, None)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.action != "start" and not (control / "lock").exists():
            if (control / "instance.json").exists():
                raise ServiceError("service record exists without its control lock")
            print(json.dumps(service_status(root, control, None), ensure_ascii=False))
            return 0
        with locked_control(control, create=args.action == "start"):
            record = control / "instance.json"
            if args.action == "start":
                result = start(root, control, record, args.port, args.new_url)
            elif args.action == "stop":
                result = stop(root, control, record)
            else:
                result = service_status(root, control, read_record(record))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ServiceError, OSError) as error:
        print(f"preview-service: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
