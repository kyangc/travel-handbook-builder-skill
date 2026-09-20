#!/usr/bin/env python3
"""Verify distributed bytes, local resource links, and package boundaries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import stat


SKILL_DIR = Path(__file__).resolve().parents[1]
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> int:
    manifest = json.loads((SKILL_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != 1:
        raise SystemExit("unsupported MANIFEST.json version")
    expected = {entry["path"]: entry for entry in manifest["files"]}
    actual: dict[str, Path] = {}
    for path in SKILL_DIR.rglob("*"):
        relative = path.relative_to(SKILL_DIR)
        if relative.parts and relative.parts[0] == ".venv":
            continue
        if path.is_symlink():
            raise SystemExit(f"bundle must not contain symlinks: {relative}")
        if path.is_file() and relative.as_posix() != "MANIFEST.json":
            actual[relative.as_posix()] = path
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    if missing or unexpected:
        raise SystemExit(f"bundle file set mismatch: missing={missing}, unexpected={unexpected}")
    for relative, entry in expected.items():
        path = actual[relative]
        if path.stat().st_size != entry["size"] or digest(path) != entry["sha256"]:
            raise SystemExit(f"bundle digest mismatch: {relative}")
        mode = f"{stat.S_IMODE(path.stat().st_mode):04o}"
        if mode != entry["mode"]:
            raise SystemExit(f"bundle mode mismatch: {relative}: {mode} != {entry['mode']}")

    for relative, path in actual.items():
        if path.suffix.lower() != ".md":
            continue
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            target = target.strip().split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (path.parent / target).resolve()
            if SKILL_DIR not in resolved.parents and resolved != SKILL_DIR:
                raise SystemExit(f"resource link escapes bundle: {relative} -> {target}")
            if not resolved.exists():
                raise SystemExit(f"missing resource link: {relative} -> {target}")
    print(json.dumps({"valid": True, "files": len(expected)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
