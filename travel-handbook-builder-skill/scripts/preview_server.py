#!/usr/bin/env python3
"""Serve one validated canonical handbook export and the bundled web application."""
from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from urllib.parse import unquote, urlsplit


SKILL_DIR = Path(__file__).resolve().parents[1]
ASSET_DIR = SKILL_DIR / "web"
RUNTIME_SCRIPTS = SKILL_DIR / "runtime" / "scripts"
sys.path.insert(0, str(RUNTIME_SCRIPTS))

try:
    from validate_trip import load_json, validate
except ImportError as error:  # pragma: no cover - exercised by the launcher message
    raise SystemExit(
        "travel-handbook preview runtime is not prepared; "
        f"run: python3 \"{SKILL_DIR / 'scripts' / 'setup_runtime.py'}\""
    ) from error


class PreviewInputError(ValueError):
    """The selected export cannot safely back the preview API."""


def port_number(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return port


def validation_summary(result: dict) -> str:
    errors = result.get("errors") if isinstance(result, dict) else None
    if not isinstance(errors, list) or not errors:
        return "canonical export failed validation"
    first = errors[0] if isinstance(errors[0], dict) else {}
    code = first.get("code", "VALIDATION_ERROR")
    pointer = first.get("path") or "/"
    message = first.get("message", "invalid canonical export")
    suffix = f"; {len(errors) - 1} more error(s)" if len(errors) > 1 else ""
    return f"{code} at {pointer}: {message}{suffix}"


def load_validated_export(path: Path) -> tuple[dict, dict]:
    try:
        package = load_json(path)
    except (OSError, UnicodeError, ValueError) as error:
        raise PreviewInputError(f"cannot read canonical export: {error}") from error
    result = validate(package)
    if not result.get("valid"):
        raise PreviewInputError(validation_summary(result))
    return package, result


def api_payload(path: Path) -> bytes:
    package, _ = load_validated_export(path)
    return (json.dumps(
        package, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ) + "\n").encode("utf-8")


def map_config_payload(path: Path | None) -> bytes:
    key = None
    if path is not None:
        try:
            metadata = path.lstat()
            if (stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.getuid()
                    and not metadata.st_mode & 0o077):
                value = json.loads(path.read_text(encoding="utf-8"))
                candidate = value.get("key") if isinstance(value, dict) else None
                if isinstance(candidate, str) and re.fullmatch(r"[A-Za-z0-9_-]{20,256}", candidate):
                    key = candidate
        except (OSError, UnicodeError, ValueError):
            pass
    return (json.dumps({"provider": "google" if key else "osm", "key": key}) + "\n").encode("utf-8")


def safe_asset(path: str) -> Path | None:
    if path.startswith("//") or "\\" in path or "\x00" in path:
        return None
    try:
        decoded = unquote(path, errors="strict")
    except (UnicodeDecodeError, ValueError):
        return None
    if "\\" in decoded or "\x00" in decoded:
        return None
    relative = "index.html" if decoded == "/" else decoded.removeprefix("/")
    parts = PurePosixPath(relative).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        return None
    root = ASSET_DIR.resolve()
    candidate = (root / Path(*parts)).resolve()
    if candidate == root or root not in candidate.parents:
        return None
    if not candidate.is_file():
        return None
    return candidate


IMAGE_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".avif": "image/avif",
}


def image_signature(data: bytes, suffix: str) -> bool:
    return {
        ".png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": data.startswith(b"\xff\xd8\xff"),
        ".jpeg": data.startswith(b"\xff\xd8\xff"),
        ".gif": data.startswith((b"GIF87a", b"GIF89a")),
        ".webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP",
        ".avif": data[4:8] == b"ftyp" and b"avif" in data[8:24],
    }.get(suffix, False)


def media_payload(export_path: Path, media_root: Path | None,
                  media_id: str) -> tuple[bytes, str] | None:
    package, _ = load_validated_export(export_path)
    media = next((entry for entry in package.get("media", [])
                  if entry["id"] == media_id and entry["kind"] == "image"), None)
    if media is None or not media.get("usages"):
        return None
    locator = media["locator"]
    if (not isinstance(locator, str) or not locator or "\x00" in locator
            or "\\" in locator or urlsplit(locator).scheme
            or locator.startswith("//")):
        return None
    original = Path(locator)
    if ".." in original.parts:
        return None
    candidate = original if original.is_absolute() else export_path.parent / original
    resolved = candidate.resolve()
    roots = [export_path.parent.resolve()]
    if media_root is not None:
        roots.append(media_root.resolve())
    if not any(root in resolved.parents for root in roots):
        return None
    suffix = resolved.suffix.lower()
    if suffix not in IMAGE_TYPES or not resolved.is_file() or resolved.stat().st_size > 20_000_000:
        return None
    data = resolved.read_bytes()
    if not image_signature(data, suffix):
        return None
    return data, IMAGE_TYPES[suffix]


def media_id_from_path(path: str) -> str | None:
    if not path.startswith("/api/media/"):
        return None
    raw = path.removeprefix("/api/media/")
    if not raw or "/" in raw or "\\" in raw or "%2f" in raw.lower():
        return None
    try:
        decoded = unquote(raw, errors="strict")
    except (UnicodeDecodeError, ValueError):
        return None
    return decoded if decoded and "/" not in decoded and "\\" not in decoded else None


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], export_path: Path,
                 media_root: Path | None = None,
                 instance_id: str | None = None,
                 map_config: Path | None = None):
        self.export_path = export_path
        self.media_root = media_root
        self.instance_id = instance_id
        self.map_config = map_config
        super().__init__(address, PreviewHandler)
        host, port = self.server_address[:2]
        authority = f"{host}:{port}"
        self.allowed_hosts = {authority}
        self.allowed_origins = {f"http://{authority}"}
        if port == 80:
            self.allowed_hosts.add(host)
            self.allowed_origins.add(f"http://{host}")


class PreviewHandler(BaseHTTPRequestHandler):
    server: PreviewServer
    server_version = "TravelHandbookPreview/1"
    sys_version = ""

    def version_string(self) -> str:
        return self.server_version

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def send_payload(self, status: HTTPStatus, payload: bytes, content_type: str,
                     *, cache_control: str, include_body: bool = True,
                     allow: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", cache_control)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")
        if self.server.instance_id is not None:
            self.send_header("X-Travel-Preview-Instance", self.server.instance_id)
        if allow is not None:
            self.send_header("Allow", allow)
        self.end_headers()
        if include_body:
            self.wfile.write(payload)

    def send_problem(self, status: HTTPStatus, message: str, *, allow: str | None = None,
                     include_body: bool = True) -> None:
        payload = (json.dumps({"error": message}, ensure_ascii=False) + "\n").encode("utf-8")
        self.send_payload(
            status, payload, "application/json; charset=utf-8",
            cache_control="no-store", include_body=include_body, allow=allow,
        )

    def request_path(self) -> str:
        return urlsplit(self.path).path

    def request_origin_is_allowed(self) -> bool:
        hosts = self.headers.get_all("Host") or []
        origins = self.headers.get_all("Origin") or []
        if (len(hosts) != 1
                or hosts[0] not in self.server.allowed_hosts
                or len(origins) > 1
                or (origins and origins[0] not in self.server.allowed_origins)):
            self.send_problem(
                HTTPStatus.FORBIDDEN, "forbidden",
                include_body=self.command != "HEAD",
            )
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        if not self.request_origin_is_allowed():
            return
        path = self.request_path()
        if path == "/api/handbook":
            try:
                payload = api_payload(self.server.export_path)
            except PreviewInputError:
                self.send_problem(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "旅行数据暂时无法读取或验证",
                )
                return
            self.send_payload(
                HTTPStatus.OK, payload, "application/json; charset=utf-8",
                cache_control="no-store",
            )
            return
        if path == "/api/map-config":
            self.send_payload(HTTPStatus.OK, map_config_payload(self.server.map_config),
                              "application/json; charset=utf-8", cache_control="no-store")
            return
        media_id = media_id_from_path(path)
        if media_id is not None:
            try:
                result = media_payload(self.server.export_path, self.server.media_root, media_id)
            except (PreviewInputError, OSError, ValueError):
                result = None
            if result is None:
                self.send_problem(HTTPStatus.NOT_FOUND, "not found")
                return
            payload, content_type = result
            self.send_payload(HTTPStatus.OK, payload, content_type, cache_control="no-store")
            return
        asset = safe_asset(path)
        if asset is None:
            self.send_problem(HTTPStatus.NOT_FOUND, "not found")
            return
        content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
        if asset.suffix == ".js":
            content_type = "text/javascript"
        cache = "no-store" if asset.name == "index.html" else "public, max-age=31536000, immutable"
        self.send_payload(HTTPStatus.OK, asset.read_bytes(), content_type, cache_control=cache)

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib handler contract
        if not self.request_origin_is_allowed():
            return
        path = self.request_path()
        if path in ("/api/handbook", "/api/map-config"):
            self.send_problem(
                HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed",
                allow="GET", include_body=False,
            )
            return
        media_id = media_id_from_path(path)
        if media_id is not None:
            try:
                result = media_payload(self.server.export_path, self.server.media_root, media_id)
            except (PreviewInputError, OSError, ValueError):
                result = None
            if result is None:
                self.send_problem(HTTPStatus.NOT_FOUND, "not found", include_body=False)
                return
            payload, content_type = result
            self.send_payload(HTTPStatus.OK, payload, content_type,
                              cache_control="no-store", include_body=False)
            return
        asset = safe_asset(path)
        if asset is None:
            self.send_problem(HTTPStatus.NOT_FOUND, "not found", include_body=False)
            return
        content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
        if asset.suffix == ".js":
            content_type = "text/javascript"
        cache = "no-store" if asset.name == "index.html" else "public, max-age=31536000, immutable"
        self.send_payload(
            HTTPStatus.OK, b" " * asset.stat().st_size, content_type,
            cache_control=cache, include_body=False,
        )

    def method_not_allowed(self) -> None:
        if not self.request_origin_is_allowed():
            return
        allow = "GET" if self.request_path() == "/api/handbook" else "GET, HEAD"
        self.send_problem(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed", allow=allow)

    do_POST = method_not_allowed
    do_PUT = method_not_allowed
    do_PATCH = method_not_allowed
    do_DELETE = method_not_allowed
    do_OPTIONS = method_not_allowed
    do_TRACE = method_not_allowed
    do_CONNECT = method_not_allowed


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("export", type=Path, help="canonical private export JSON")
    result.add_argument("--port", type=port_number, default=8765,
                        help="loopback port (default: 8765; use 0 for an available port)")
    result.add_argument("--instance-id", help=argparse.SUPPRESS)
    result.add_argument("--media-root", type=Path,
                        help="additional local image directory outside the canonical directory")
    result.add_argument("--map-config", type=Path, help=argparse.SUPPRESS)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    selected_export = args.export.expanduser()
    export_path = selected_export.resolve()
    media_root = args.media_root.expanduser().resolve() if args.media_root else None
    if selected_export.is_symlink() or not export_path.is_file():
        print("preview-handbook: export must be an existing regular file", file=sys.stderr)
        return 2
    if media_root is not None and not media_root.is_dir():
        print("preview-handbook: media root must be an existing directory", file=sys.stderr)
        return 2
    if not (ASSET_DIR / "index.html").is_file():
        print("preview-handbook: bundled web assets are missing", file=sys.stderr)
        return 2
    try:
        _, validation = load_validated_export(export_path)
    except PreviewInputError as error:
        print(f"preview-handbook: {error}", file=sys.stderr)
        return 2
    try:
        server = PreviewServer(("127.0.0.1", args.port), export_path,
                               media_root, args.instance_id, args.map_config)
    except OSError as error:
        print(f"preview-handbook: cannot bind loopback port: {error}", file=sys.stderr)
        return 2
    host, port = server.server_address[:2]
    started = {
        "url": f"http://{host}:{port}/",
        "export": str(export_path),
        "warnings": len(validation.get("warnings", [])),
    }
    print(json.dumps(started, ensure_ascii=False), flush=True)
    print("Press Ctrl-C to stop the preview.", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    print("Preview stopped.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
