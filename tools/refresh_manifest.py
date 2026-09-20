#!/usr/bin/env python3
"""Regenerate the public skill manifest from the release directory."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "travel-handbook-builder-skill"
MANIFEST = SKILL_DIR / "MANIFEST.json"
REPOSITORY = "https://github.com/kyangc/travel-handbook-builder-skill"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def packaged_files() -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    for path in sorted(SKILL_DIR.rglob("*")):
        relative = path.relative_to(SKILL_DIR)
        if (relative.parts and relative.parts[0] == ".venv"
                or "__pycache__" in relative.parts
                or path.suffix in {".pyc", ".pyo"}):
            continue
        if path.is_symlink():
            raise SystemExit(f"release bundle must not contain symlinks: {relative}")
        if not path.is_file() or relative.as_posix() == "MANIFEST.json":
            continue
        files.append({
            "path": relative.as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256(path),
            "mode": f"{stat.S_IMODE(path.stat().st_mode):04o}",
        })
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--release-tag", required=True)
    args = parser.parse_args()

    previous = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = packaged_files()
    manifest = {
        "manifest_version": 1,
        "package": {
            "name": "travel-handbook-builder-skill",
            "version": args.version,
        },
        "source": {
            "repository": REPOSITORY,
            "release_tag": args.release_tag,
            "distribution": "public-skill-release",
        },
        "requirements": previous["requirements"],
        "integrity": {
            "algorithm": "sha256",
            "file_count": len(files),
            "scope": "all skill files except MANIFEST.json and generated .venv",
        },
        "entrypoints": previous["entrypoints"],
        "files": files,
    }
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(MANIFEST), "files": len(files)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
