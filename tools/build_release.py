#!/usr/bin/env python3
"""Build a deterministic ZIP from the verified public skill bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "travel-handbook-builder-skill"
MANIFEST = SKILL_DIR / "MANIFEST.json"
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    subprocess.run(
        [sys.executable, str(SKILL_DIR / "scripts" / "verify_bundle.py")], check=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    name = manifest["package"]["name"]
    version = manifest["package"]["version"]
    output = args.output or ROOT / "dist" / f"{name}-{version}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    entries = [MANIFEST]
    entries.extend(SKILL_DIR / entry["path"] for entry in manifest["files"])
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path in sorted(entries, key=lambda value: value.relative_to(SKILL_DIR).as_posix()):
            relative = path.relative_to(SKILL_DIR).as_posix()
            info = zipfile.ZipInfo(f"{name}/{relative}", FIXED_TIMESTAMP)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            unix_mode = stat.S_IFREG | stat.S_IMODE(path.stat().st_mode)
            info.external_attr = (unix_mode & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)

    print(json.dumps({
        "archive": str(output),
        "files": len(entries),
        "sha256": sha256(output),
        "size": output.stat().st_size,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
