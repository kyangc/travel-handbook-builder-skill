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
    if "media_root" in record and type(record["media_root"]) is not str:
        raise ServiceError("service record has an invalid media root")
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


def read_media_config(path: Path, root: Path) -> dict | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
            or metadata.st_mode & 0o077):
        raise ServiceError("media configuration is not a private, owned regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ServiceError("media configuration is invalid; use start --media-root or --clear-media-root to replace it") from error
    if (not isinstance(value, dict) or value.get("root") != str(root)
            or "media_root" not in value
            or (value["media_root"] is not None
                and (type(value["media_root"]) is not str or not Path(value["media_root"]).is_absolute()))):
        raise ServiceError("media configuration has an invalid shape or ROOT; use start --media-root or --clear-media-root")
    return value


def save_media_config(path: Path, root: Path, media_root: Path | None) -> None:
    write_record(path, {"root": str(root), "media_root": str(media_root) if media_root else None})


def runtime_probe(port: int, instance: str) -> dict | None:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", "/api/preview-status")
        response = connection.getresponse()
        body = response.read()
        if response.status == 200 and response.getheader("X-Travel-Preview-Instance") == instance:
            value = json.loads(body)
            if isinstance(value, dict):
                return value
    except (OSError, ValueError, http.client.HTTPException):
        pass
    finally:
        connection.close()
    return None


def read_map_config(path: Path) -> dict:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {"asked": False}
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
            or metadata.st_mode & 0o077):
        raise ServiceError("map configuration is not a private, owned regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ServiceError("map configuration is invalid") from error
    if (not isinstance(value, dict) or type(value.get("asked")) is not bool
            or ("key" in value and (type(value["key"]) is not str
                                    or not re.fullmatch(r"[A-Za-z0-9_-]{20,256}", value["key"])))):
        raise ServiceError("map configuration has an invalid shape")
    return value


def write_map_config(path: Path, value: dict) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".maps-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
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
        status = ManagedHandbook.current_publication(root)
        if status["canonical_path"] != str(root / "private-handbook.json"):
            raise ServiceError("managed canonical path differs from selected ROOT")
        return status, None
    except ClientError as error:
        return None, f"{error.code}: {error}"


def service_status(root: Path, control: Path, record: dict | None,
                   *, check_data: bool = True) -> dict:
    managed, data_error = managed_status(root) if check_data else (None, "not_checked")
    result = {"state": "stopped", "ready": False, "owned": False,
              "url": record["url"] if record else None,
              "pid": record["pid"] if record else None,
              "instance": record["instance"] if record else None,
              "export": str(root / "private-handbook.json"),
              "revision": None, "canonical_revision": managed["canonical_revision"] if managed else None,
              "publish_status": managed["publish_status"] if managed else None,
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
    if check_data:
        result["runtime"] = runtime_probe(record["port"], record["instance"])
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
          allow_new_url: bool, media_root: Path | None, clear_media_root: bool = False) -> dict:
    existing = read_record(record_path)
    current = service_status(root, control, existing)
    if current["state"] == "identity_mismatch":
        raise ServiceError("service identity mismatch; refusing takeover")
    config_path = control / "media.json"
    explicit_media = media_root is not None or clear_media_root
    config = None if explicit_media else read_media_config(config_path, root)
    if not explicit_media:
        saved = config["media_root"] if config is not None else existing.get("media_root") if existing else None
        media_root = Path(saved) if saved else None
    if media_root is not None and (not media_root.is_dir() or media_root.resolve() != media_root):
        raise ServiceError("saved media root is missing or changed; stop any running service, then start --media-root DIRECTORY or --clear-media-root")
    if existing is not None:
        if current["state"] == "ready":
            if (str(media_root) if media_root else None) != existing.get("media_root"):
                raise ServiceError("media root differs from the existing service; stop it before changing the root")
            if requested_port not in (None, 0, existing["port"]):
                raise ServiceError("requested port differs from the existing service URL")
            save_media_config(config_path, root, media_root)
            current["reused"] = True
            return current
        if current["owned"]:
            raise ServiceError("owned service is running but managed data is not ready")
        if current["state"] == "identity_mismatch":
            raise ServiceError("service identity mismatch; refusing takeover")
    if current["data_error"] is not None:
        raise ServiceError(f"managed data is not ready: {current['data_error']}")
    if current["publish_status"] != "current":
        raise ServiceError("managed canonical is not currently published")
    export = root / "private-handbook.json"
    if export.is_symlink() or not export.is_file():
        raise ServiceError("managed canonical must be a regular non-symlink file")
    if not explicit_media and config is None and media_root is None:
        package = json.loads(export.read_text(encoding="utf-8"))
        if any(item.get("kind") == "image" and item.get("usages")
               and isinstance(item.get("locator"), str)
               and not item["locator"].startswith("//")
               and Path(item["locator"]).is_absolute()
               and not Path(item["locator"]).is_relative_to(root)
               for item in package.get("media", [])):
            raise ServiceError("external media has no saved configuration; start --media-root DIRECTORY to restore access, or --clear-media-root to disable it")
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
               "--port", str(port), "--instance-id", instance,
               "--map-config", str(control / "maps.json")]
    if media_root is not None:
        command.extend(["--media-root", str(media_root)])
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
        stage = "waiting_for_ready_line"
        last_probe = "not_attempted"
        while time.monotonic() < deadline:
            if child.poll() is not None:
                if "cannot bind loopback port" in log.read_text(encoding="utf-8"):
                    raise ServiceError(
                        f"loopback port {port} is occupied; the previous URL cannot be preserved; private log: {log}"
                    )
                raise ServiceError(f"preview process exited before readiness; private log: {log}")
            started = ready_line(log)
            if isinstance(started, dict):
                match = re.fullmatch(r"http://127\.0\.0\.1:(\d+)/", str(started.get("url")))
                if match and started.get("export") == str(export):
                    selected_port = int(match.group(1))
            birth = birth_identity(child.pid)
            birth_seen = birth_seen or birth is not None
            probe = api_probe(selected_port) if selected_port else None
            if not selected_port:
                stage = "waiting_for_ready_line"
                last_probe = "not_attempted"
            elif not birth:
                stage = "waiting_for_process_birth"
                last_probe = "no_http_response" if probe is None else f"http_{probe[0]}"
            elif probe is None:
                stage = "waiting_for_http_response"
                last_probe = "no_http_response"
            elif probe[1] != instance:
                stage = "waiting_for_instance"
                last_probe = f"http_{probe[0]},instance_mismatch"
            elif probe[0] != 200:
                stage = "waiting_for_http_200"
                last_probe = f"http_{probe[0]},instance_match"
            elif probe[2] != current["canonical_revision"]:
                stage = "waiting_for_revision"
                last_probe = "http_200,instance_match,revision_mismatch"
            else:
                stage = "ready"
                last_probe = "http_200,instance_match,revision_match"
            if (birth and probe and probe[0] == 200 and probe[1] == instance
                    and probe[2] == current["canonical_revision"]):
                break
            time.sleep(0.05)
        else:
            if not birth_seen:
                raise ServiceError(f"process birth identity unavailable; lifecycle service unsupported; stage={stage}; last_probe={last_probe}; private log: {log}")
            raise ServiceError(f"preview did not become identity-verified and data-ready; stage={stage}; last_probe={last_probe}; private log: {log}")
        record = {"root": str(root), "export": str(export), "pid": child.pid,
                  "birth": birth, "instance": instance, "port": selected_port,
                  "url": f"http://127.0.0.1:{selected_port}/", "started_at": time.time(),
                  "log": str(log)}
        if media_root is not None:
            record["media_root"] = str(media_root)
        manifest = SKILL_DIR / "MANIFEST.json"
        if manifest.is_file():
            record["bundle_version"] = json.loads(manifest.read_text(encoding="utf-8"))["package"]["version"]
        write_record(record_path, record)
        result = service_status(root, control, record)
        if not result["ready"]:
            raise ServiceError("managed data changed during startup; check status")
        save_media_config(config_path, root, media_root)
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
        return service_status(root, control, None, check_data=False)
    current = service_status(root, control, record, check_data=False)
    if not current["owned"]:
        probe = api_probe(record["port"]) if current.get("stale_process") else None
        if probe is not None and probe[1] == record["instance"]:
            raise ServiceError("process birth identity unavailable; refusing to signal a process")
        raise ServiceError("service identity cannot be verified; refusing to signal a process")
    # Recheck immediately before signalling: PID alone is never sufficient.
    if birth_identity(record["pid"]) != record["birth"]:
        raise ServiceError("process birth identity changed; refusing to signal")
    # Migrate an older live instance before deleting its process record. Existing
    # configuration (even damaged configuration) must not prevent an owned stop.
    config_path = control / "media.json"
    if not os.path.lexists(config_path):
        save_media_config(config_path, root, Path(record["media_root"]) if record.get("media_root") else None)
    os.kill(record["pid"], signal.SIGTERM)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        probe = api_probe(record["port"])
        if probe is None or probe[1] != record["instance"]:
            record_path.unlink()
            return service_status(root, control, None, check_data=False)
        time.sleep(0.05)
    raise ServiceError("service did not release its port after SIGTERM")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("action", choices=("start", "status", "stop", "maps-status", "maps-skip", "maps-configure"))
    result.add_argument("root", help="initialized managed ROOT")
    result.add_argument("--port", type=port_number, default=None,
                        help="start port (default 8765; 0 chooses an available port)")
    result.add_argument("--new-url", action="store_true",
                        help="explicitly choose a new URL after the previous process has died")
    media = result.add_mutually_exclusive_group()
    media.add_argument("--media-root", type=Path,
                        help="additional local image directory outside the canonical directory")
    media.add_argument("--clear-media-root", action="store_true",
                       help="start without an additional image directory and persist that choice")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.action != "start" and (args.media_root is not None or args.clear_media_root):
            raise ServiceError("--media-root and --clear-media-root apply only to start")
        root = root_path(args.root)
        media_root = args.media_root.expanduser().resolve() if args.media_root else None
        if media_root is not None and not media_root.is_dir():
            raise ServiceError("media root must be an existing directory")
        control = control_path(root)
        if args.action in ("start", "maps-skip", "maps-configure"):
            checked_directory(control, create=True)
        elif not checked_directory(control, create=False):
            result = ({"asked": False, "configured": False, "skipped": False}
                      if args.action == "maps-status" else service_status(
                          root, control, None, check_data=args.action != "stop"))
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.action not in ("start", "maps-skip", "maps-configure") and not (control / "lock").exists():
            if (control / "instance.json").exists():
                raise ServiceError("service record exists without its control lock")
            result = ({"asked": False, "configured": False, "skipped": False}
                      if args.action == "maps-status" else service_status(
                          root, control, None, check_data=args.action != "stop"))
            print(json.dumps(result, ensure_ascii=False))
            return 0
        with locked_control(control, create=args.action in ("start", "maps-skip", "maps-configure")):
            record = control / "instance.json"
            map_path = control / "maps.json"
            if args.action in ("maps-status", "maps-skip", "maps-configure"):
                config = read_map_config(map_path)
                if args.action == "maps-skip":
                    write_map_config(map_path, {**config, "asked": True})
                    config = read_map_config(map_path)
                elif args.action == "maps-configure":
                    key = sys.stdin.readline().strip()
                    if not re.fullmatch(r"[A-Za-z0-9_-]{20,256}", key):
                        raise ServiceError("expected a Google Maps JavaScript API key on stdin")
                    write_map_config(map_path, {"asked": True, "key": key})
                    config = read_map_config(map_path)
                result = {"asked": config["asked"], "configured": bool(config.get("key")),
                          "skipped": config["asked"] and not bool(config.get("key"))}
            elif args.action == "start":
                result = start(root, control, record, args.port, args.new_url, media_root, args.clear_media_root)
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
