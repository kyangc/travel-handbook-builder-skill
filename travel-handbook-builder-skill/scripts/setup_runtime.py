#!/usr/bin/env python3
"""Create and verify the skill-local Python environment."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import venv


SKILL_DIR = Path(__file__).resolve().parents[1]
VENV_DIR = SKILL_DIR / ".venv"


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    if sys.version_info < (3, 12):
        fail(f"Python 3.12 or newer is required; found {sys.version.split()[0]}")

    subprocess.run(
        [sys.executable, str(SKILL_DIR / "scripts" / "verify_bundle.py")],
        check=True,
    )
    if not (VENV_DIR / "pyvenv.cfg").is_file():
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)

    python = VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        fail(f"virtual environment did not provide an interpreter: {python}")

    subprocess.run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check",
         "-r", str(SKILL_DIR / "requirements.txt")],
        check=True,
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SKILL_DIR / "runtime")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    probe = (
        "import json, jsonschema, tzdata; "
        "from zoneinfo import ZoneInfo; import authoring; "
        "ZoneInfo('Asia/Tokyo'); "
        "print(json.dumps({'python': __import__('platform').python_version(), "
        "'jsonschema': jsonschema.__version__, 'tzdata': tzdata.__version__, "
        "'authoring': authoring.__file__}))"
    )
    checked = subprocess.run(
        [str(python), "-B", "-P", "-c", probe], check=True, capture_output=True, text=True,
        env=environment, cwd=SKILL_DIR,
    )
    subprocess.run(
        [str(python), "-B", "-P", "-m", "authoring", "--help"], check=True,
        stdout=subprocess.DEVNULL, env=environment, cwd=SKILL_DIR,
    )
    result = json.loads(checked.stdout)
    module = Path(result["authoring"]).resolve()
    expected_runtime = (SKILL_DIR / "runtime").resolve()
    if expected_runtime not in module.parents:
        fail(f"authoring resolved outside the bundle runtime: {module}")
    result.update({"ready": True, "environment": str(VENV_DIR)})
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
