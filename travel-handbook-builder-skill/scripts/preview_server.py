#!/usr/bin/env python3
"""Serve one validated canonical handbook export and the bundled web application."""
from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path, PurePosixPath
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


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], export_path: Path,
                 instance_id: str | None = None):
        self.export_path = export_path
        self.instance_id = instance_id
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
        if path == "/api/handbook":
            self.send_problem(
                HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed",
                allow="GET", include_body=False,
            )
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
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    export_path = args.export.expanduser().resolve()
    if export_path.is_symlink() or not export_path.is_file():
        print("preview-handbook: export must be an existing regular file", file=sys.stderr)
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
        server = PreviewServer(("127.0.0.1", args.port), export_path, args.instance_id)
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
