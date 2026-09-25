# Travel Handbook Authoring skill

This directory is a self-contained agent skill and local Python runtime for building a private, typed handbook package from supplied travel material and bounded public research. It supports new authoring work, incremental edits, recovery from saved state, bounded reads, previews, checks, and private export. The Agent may research goal-relevant public facts; the runtime itself does not browse, select travel plans, make bookings, verify real-world facts, or publish content.

Start with the [short default CLI workflow](references/DEFAULT_WORKFLOW_GUIDE.md): create from one public request, review `preview`, `apply` and `check`, then `client init` a new managed directory **before the first webpage opening**. Later edits use [managed continuation](references/CLIENT_GUIDE.md) and `client check` for the current full report. Read the [optional Python examples](references/PYTHON_OPTIONAL_GUIDE.md) only if programmatic state handling is needed. This README covers installation and the command inventory; its older self-managed export examples below are not the default continuation path.

## Requirements and isolated setup

- Python 3.12 or newer.
- A POSIX shell for the bundled `scripts/travel-handbook` and `scripts/python` launchers.
- Network access during dependency installation, unless the packages in `requirements.txt` are already available from a configured package index or cache. A preconfigured Python with those dependencies does not need installation.

From any working directory, verify the bundle. If no suitable Python environment
is already available, create the skill-local environment:

```sh
python3 "/path/to/travel-handbook-builder-skill/scripts/verify_bundle.py"
python3 "/path/to/travel-handbook-builder-skill/scripts/setup_runtime.py"
```

Setup creates only `travel-handbook-builder-skill/.venv` and installs the pinned JSON Schema validator plus a `tzdata` fallback there. It does not modify the global Python environment. Re-running setup reuses that environment and rechecks imports, timezone data, and the CLI.

Alternatively, when Python 3.12+ already has `jsonschema` and `tzdata`, use the
existing external interpreter without running setup or installing anything:

```sh
SKILL_DIR="/path/to/travel-handbook-builder-skill"
TRAVEL_HANDBOOK_PYTHON="/absolute/path/to/python3" \
  "$SKILL_DIR/scripts/travel-handbook" --help
TRAVEL_HANDBOOK_PYTHON="/absolute/path/to/python3" \
  "$SKILL_DIR/scripts/python" -c "import authoring, jsonschema, tzdata"
```

Set `TRAVEL_HANDBOOK_PYTHON` on each launcher invocation or export it once in
the shell used for later commands. The launchers prefer an existing
skill-local `.venv`; the external interpreter is selected only when that
`.venv` is absent. The launchers still isolate `PYTHONPATH` to the bundle and
disable bytecode writes. `scripts/setup_runtime.py --help` prints usage without
creating an environment or installing dependencies.

The bundled launchers ignore an inherited `PYTHONPATH`, use only this bundle's `runtime/` for handbook modules, and disable bytecode writes there. This keeps integrity verification valid after normal API and CLI use.

The launchers and setup flow are validated on POSIX. The Python runtime uses portable paths, but this release does not claim a tested native Windows launcher contract.

## Install as an agent skill

Keep the whole `travel-handbook-builder-skill` directory together. Point the agent's skill directory setting at the parent directory, or copy this directory into the agent's normal skills directory. For Kimi CLI, the parent can be supplied with `--skills-dir`; Kimi exposes the selected skill root as `${KIMI_SKILL_DIR}` while the skill is active.

Do not copy only `SKILL.md`: the references, launchers, runtime, Schemas, requirements, and manifest are part of the contract.

## CLI from any directory

Use the launcher by absolute path. State, request, and managed paths may live elsewhere and contain spaces. This is a command outline, not an auto-approval script; build the request from supplied material and review the preview before submitting it. The [default workflow](references/DEFAULT_WORKFLOW_GUIDE.md) has the complete order and recovery rules.

```sh
SKILL_DIR="/path/to/travel-handbook-builder-skill"
"$SKILL_DIR/scripts/travel-handbook" --help
"$SKILL_DIR/scripts/travel-handbook" create "/work/trip state.json" --title "Example trip" --example
"$SKILL_DIR/scripts/travel-handbook" read "/work/trip state.json"
"$SKILL_DIR/scripts/travel-handbook" preview "/work/trip state.json" "/work/request.json"
"$SKILL_DIR/scripts/travel-handbook" apply "/work/trip state.json" "/work/request.json" > "/work/receipt.json"
"$SKILL_DIR/scripts/travel-handbook" check "/work/trip state.json"
"$SKILL_DIR/scripts/travel-handbook" client init "/work/managed handbook" --state "/work/trip state.json"
"$SKILL_DIR/scripts/travel-handbook" client read "/work/managed handbook"
"$SKILL_DIR/scripts/travel-handbook" client check "/work/managed handbook"
```

`--example` is for synthetic demonstrations, not real material. Use `read` to obtain the actual revision and keep the exact first request plus receipt. Initialize only after `check.valid=true`; from then on use `client prepare-place` or `client prepare-request`/`commit` to update the same managed canonical. Read `references/CALLER_GUIDE.md` only when its detailed method contract is needed.

When supplied material is insufficient for the requested handbook, read `references/CONTENT_COLLECTION_GUIDE.md`. It explains which public facts the Agent should research, which decisions remain with the user, and how to preserve source and timeliness context for Place introductions. A concise coverage note may record consequential gaps; no second full managed-state report is required. The runtime does not assess source coverage. Image metadata and explicit Trip/Place uses are supported through the public Media methods; see `references/MEDIA_GUIDE.md`.

The public authoring surface also supports these identity-preserving corrections:

- `stay.action.add` creates an explicit check-in, check-out, breakfast, luggage, departure, or return Item for an existing Stay; `stay.action.bind` converts an existing ordinary Item in place and preserves its ID, schedule position, text, timing, participants, claims, and external references. Read `references/STAY_GUIDE.md` for date, lodging, and confirmation guards.
- `task.amend(..., checklist_edits=[{"op": "rename", ...}])` changes a checklist title without changing its ID, status, or order. A completed Task must be reopened first, and its completion snapshot remains immutable. Read `references/TASK_PREPARATION_GUIDE.md`.
- When the user asks for an overall description of the trip's style, character, or pace, the Agent may summarize confirmed facts and selected arrangements and store that text with `trip.update(set={"summary": ...})`; `clear=["summary"]` removes it. Unselected recommendations and unconfirmed arrangements must not be written as part of the trip. The runtime itself does not generate the summary or change any other Trip fact.

## Python API

Run a caller with the bundled interpreter wrapper so `import authoring` resolves without depending on the current directory:

```sh
"/path/to/travel-handbook-builder-skill/scripts/python" /work/author_trip.py
```

The public imports are `new_workspace`, `import_package`, `read_workspace`, `preview`, `apply`, `check`, `export_package`, and `AuthoringError`; managed access is through `ManagedHandbook`. Programmatic creation and a standalone professional supplement are in [the optional guide](references/PYTHON_OPTIONAL_GUIDE.md). Other method contracts are under `references/`. Runtime implementation and Schemas are execution resources, not calling instructions.

### For older self-managed full state: separate state, package, and report

This manual save example is **only** for a complete state that has not entered managed; it illustrates the three file roles, not a crash-safe replacement procedure. Follow [recovery](references/RECOVERY_READ_PREVIEW_GUIDE.md) for the actual atomic write sequence. Never use it to replace files inside a managed ROOT. The complete authoring state retains handles, receipts, source snapshots, bindings, and decisions. `export_package` returns an export report object; its `package` member is the canonical handbook accepted by `import_package`. The rest contains validation, projection fields when applicable, and a private manifest. Keep an optional report under a distinct name and never pass it to `import_package` or CLI `import`.

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

For old self-managed state, CLI `export` performs extraction and writes only canonical JSON to its output path. Managed publication instead belongs to `client commit`.

## Preview the canonical handbook in a browser

Authoring `preview` is a dry-run for a proposed write request. The separate browser preview renders an already exported canonical private package and never reads or writes authoring state.

For a standalone canonical export, start the bundled foreground loopback server
from any directory (keep `TRAVEL_HANDBOOK_PYTHON` set when using the external route):

```sh
SKILL_DIR="/path/to/travel-handbook-builder-skill"
"$SKILL_DIR/scripts/preview-handbook" "/absolute/path/to/private-handbook.json"
```

Open `http://127.0.0.1:8765/`. To use another loopback port, add `--port 9876`. Press Ctrl-C in the terminal to stop the server.

For an initialized managed `ROOT`, the separate lifecycle launcher keeps the preview available after the caller's command exits:

```sh
"$SKILL_DIR/scripts/preview-service" start "/absolute/path/to/managed-ROOT" --port 0
"$SKILL_DIR/scripts/preview-service" status "/absolute/path/to/managed-ROOT"
"$SKILL_DIR/scripts/preview-service" stop "/absolute/path/to/managed-ROOT"
```

`start` returns JSON only after verifying the loopback server identity and current canonical revision. Save its `url`; another `start` for the same ROOT reuses it, including after a managed commit. The private process record and log live in a 0700 sibling directory named `.travel-handbook-preview-*`, outside managed data and the release. `stop` signals only the recorded instance after checking its process birth and HTTP identity; an unverifiable record requires manual investigation and is never blindly killed. The existing foreground `preview-handbook` remains available for standalone canonical exports.

If the service died, `start` tries its recorded port so the URL stays stable. If another process took that port, it fails explicitly. Only after informing the user that the old URL cannot be kept, use `start ROOT --new-url --port 0`; the result includes `previous_url` and `url_changed=true`.

The extracted release already contains the production-built web application. Node and npm are build-machine dependencies and are not needed by the installed preview. The release intentionally contains no Google Maps key: all four tabs and handbook text remain readable, while map surfaces use the existing retryable unavailable state.

Each browser refresh re-reads and validates the selected canonical file. For managed work, pass `ROOT` to `preview-service` (or `ROOT/private-handbook.json` to the foreground `preview-handbook`), update only through `client commit`, and refresh the same page; restarting a live server is unnecessary. For old self-managed work, pass only the canonical package written by CLI `export` or `export_report["package"]` to the foreground launcher. Complete state files, export-report wrappers, malformed JSON, and schema-invalid packages are rejected.

## Media and compatibility

Use `media.image.add` to record an image locator, alt text, source and explicit representation; use `media.usage.add/remove` to attach or detach a Place introduction or Trip overview while preserving asset identity. Generated overviews record their generator and remain illustrations or schematics, not evidence of a real scene or a precise navigation route. These APIs do not search, generate, download, publish or determine rights.

Version 0.2.0 adds optional Media fields within the current `1.0` schema profile. Existing packages remain readable without rewriting; packages using the new fields require the updated runtime/schema and may be rejected by older strict `1.0` validators. Keep the producing bundle version with the artifact. The current preview does not display new media or serve arbitrary local image paths.

## Integrity, privacy, and licenses

`MANIFEST.json` records the source revision, public entrypoints, environment contract, and SHA-256 digest of every distributed file other than the manifest itself. Run `scripts/verify_bundle.py` after copying or extracting the bundle. The verifier ignores only the local `.venv` created by setup.

State and exports can contain source text, personal details, dates, and travel arrangements. Keep them outside the installed skill directory and treat exports as private unless separately reviewed and authorized for publication.

The bundle includes the project's MIT `LICENSE` and `THIRD_PARTY_NOTICES.md`. The MIT license applies to original project files only. Dependencies installed into `.venv` remain under their upstream licenses and are not vendored into this skill ZIP; retain their installed license files if redistributing that environment.
