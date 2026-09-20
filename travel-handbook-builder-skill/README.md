# Travel Handbook Authoring skill

This directory is a self-contained agent skill and local Python runtime for converting supplied travel material into a private, typed handbook package. It supports new authoring work, incremental edits, recovery from saved state, bounded reads, previews, checks, and private export. It does not select travel plans, make bookings, verify real-world facts, or publish content.

## Requirements and isolated setup

- Python 3.12 or newer.
- A POSIX shell for the bundled `scripts/travel-handbook` and `scripts/python` launchers.
- Network access during dependency installation, unless the packages in `requirements.txt` are already available from a configured package index or cache.

From any working directory, verify the bundle and create its local environment:

```sh
python3 "/path/to/travel-handbook-builder-skill/scripts/verify_bundle.py"
python3 "/path/to/travel-handbook-builder-skill/scripts/setup_runtime.py"
```

Setup creates only `travel-handbook-builder-skill/.venv` and installs the pinned JSON Schema validator plus a `tzdata` fallback there. It does not modify the global Python environment. Re-running setup reuses that environment and rechecks imports, timezone data, and the CLI.

The bundled launchers ignore an inherited `PYTHONPATH`, use only this bundle's `runtime/` for handbook modules, and disable bytecode writes there. This keeps integrity verification valid after normal API and CLI use.

The launchers and setup flow are validated on POSIX. The Python runtime uses portable paths, but this release does not claim a tested native Windows launcher contract.

## Install as an agent skill

Keep the whole `travel-handbook-builder-skill` directory together. Point the agent's skill directory setting at the parent directory, or copy this directory into the agent's normal skills directory. For Kimi CLI, the parent can be supplied with `--skills-dir`; Kimi exposes the selected skill root as `${KIMI_SKILL_DIR}` while the skill is active.

Do not copy only `SKILL.md`: the references, launchers, runtime, Schemas, requirements, and manifest are part of the contract.

## CLI from any directory

Use the launcher by absolute path. State, request, and export paths may live elsewhere and may contain spaces.

```sh
SKILL_DIR="/path/to/travel-handbook-builder-skill"
"$SKILL_DIR/scripts/travel-handbook" --help
"$SKILL_DIR/scripts/travel-handbook" create "/work/trip state.json" --title "Example trip" --example
"$SKILL_DIR/scripts/travel-handbook" apply "/work/trip state.json" "/work/request.json"
"$SKILL_DIR/scripts/travel-handbook" read "/work/trip state.json"
"$SKILL_DIR/scripts/travel-handbook" check "/work/trip state.json"
"$SKILL_DIR/scripts/travel-handbook" export "/work/trip state.json" "/work/trip.json" --revision 1
```

Read `references/CALLER_GUIDE.md` before creating request JSON. Use `read` to obtain the actual revision for export; `1` above is illustrative.

## Python API

Run a caller with the bundled interpreter wrapper so `import authoring` resolves without depending on the current directory:

```sh
"/path/to/travel-handbook-builder-skill/scripts/python" /work/author_trip.py
```

The public imports are `new_workspace`, `import_package`, `read_workspace`, `preview`, `apply`, `check`, `export_package`, and `AuthoringError`. The full calling contract and topic guides are under `references/`. Runtime implementation and Schemas are execution resources, not calling instructions.

### Save state, canonical package, and export report separately

The complete authoring state is the file used to resume work without losing handles, receipts, source snapshots, bindings, or decisions. `export_package` returns an export report object; its `package` member is the canonical handbook accepted by `import_package`. The rest of the report contains validation, projection fields when applicable, and a private manifest. Keep an optional report under a distinct name and never pass it to `import_package` or CLI `import`.

```python
from pathlib import Path
import json
from authoring import export_package, read_workspace

def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

save_json("trip-state.json", state)  # Complete state for resuming edits.
export_report = export_package(state, revision=read_workspace(state)["revision"])
save_json("private-handbook.json", export_report["package"])  # Canonical import input.
save_json("export-report.json", export_report)  # Optional diagnostics; never import this file.
```

CLI `export` performs the extraction itself and writes only the canonical handbook JSON to its output path.

## Integrity, privacy, and licenses

`MANIFEST.json` records the source revision, public entrypoints, environment contract, and SHA-256 digest of every distributed file other than the manifest itself. Run `scripts/verify_bundle.py` after copying or extracting the bundle. The verifier ignores only the local `.venv` created by setup.

State and exports can contain source text, personal details, dates, and travel arrangements. Keep them outside the installed skill directory and treat exports as private unless separately reviewed and authorized for publication.

The bundle includes the project's MIT `LICENSE` and `THIRD_PARTY_NOTICES.md`. The MIT license applies to original project files only. Dependencies installed into `.venv` remain under their upstream licenses and are not vendored into this skill ZIP; retain their installed license files if redistributing that environment.
