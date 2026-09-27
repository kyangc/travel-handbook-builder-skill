# Travel Handbook Authoring skill

This directory is a self-contained agent skill and local Python runtime for building a private, typed handbook package from supplied travel material and bounded public research. It supports new authoring work, incremental edits, recovery from saved state, bounded reads, previews, checks, and private export. The Agent may research goal-relevant public facts; the runtime itself does not browse, select travel plans, make bookings, verify real-world facts, or publish content.

This v0.3.5 bundle fixes detail sheets that briefly appear above their final bottom position while opening. The outer dialog no longer auto-scrolls to its animated focused child; scrolling long content inside the panel remains available. Installing or upgrading an existing local copy remains a separate action.

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

- `stay.action.add` creates an explicit lodging action Item for an existing Stay. Use one `check_in` for the first arrival of each Stay and `return` for later returns; do not split luggage storage, registration, or key collection into separate arrival actions. The underlying `action` field still accepts nonempty custom strings. `stay.action.bind` converts an existing ordinary Item in place and preserves its ID, schedule position, text, timing, participants, claims, and external references. Read `references/STAY_GUIDE.md` for date, lodging, and confirmation guards.
- `task.amend(set={"action": "purchase"})` corrects a mistaken action in place within the model's Task action enum; `set={"targets": [current_item_handle]}` can explicitly retarget an existing Task from a retired ordinary Item to the current Item that owns a formal Journey. It does not infer the replacement or accept a Journey handle directly. `checklist_edits=[{"op": "rename", ...}]` changes a checklist title without changing its ID, status, or order. A completed Task must be reopened first, and its old action and completion snapshot remain immutable. Read `references/TASK_PREPARATION_GUIDE.md`.
- `trip.update(set={"title": ...})` changes the current Trip title in place while retaining its identity and dates. When the user asks for an overall description of the trip's style, character, or pace, the Agent may summarize confirmed facts and selected arrangements and store that text with `trip.update(set={"summary": ...})`; `clear=["summary"]` removes only the summary. Unselected recommendations and unconfirmed arrangements must not be written as part of the trip. The runtime itself does not generate either value.
- A concise account of one Day can be supplied with `day.add(summary=...)` or revised in place with `day.update(target=..., set={"summary": ...})`; use `clear=["summary"]` to remove it. The summary is optional prose for the day card and does not change its Item references, times, or route.

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

For a new managed map preview, first run `preview-service maps-status ROOT`. Its output contains only `asked`, `configured`, and `skipped`. If `asked=false`, ask the user once whether they want to configure Google Maps. A decline or unanswered optional prompt is recorded with `preview-service maps-skip ROOT`, and the same preview URL shows an interactive schematic of the handbook's own points and lines without a basemap. To configure later, put a Google Maps JavaScript API key in a private local file and run `preview-service maps-configure ROOT < /private/path/to/key-file`; refresh the existing URL. The key is read from standard input, stored only in the 0700 preview control directory as a 0600 file, never returned by status, and never written to canonical data, requests, logs, URL fragments, or the release. Do not place a key directly in a shell argument or repository `.env` file. The browser must receive the key to load Google's JavaScript API, so it is visible in browser network requests. Restrict it to the Maps JavaScript API and the intended HTTP referrers in Google Cloud Console; a browser key cannot be kept secret from someone who can inspect that browser. See [Google's key setup](https://developers.google.com/maps/documentation/javascript/get-api-key) and [key security guidance](https://developers.google.com/maps/api-security-best-practices).

When Google Maps cannot load, is not configured, or the browser is offline, the preview labels the fallback as a point/line schematic with no basemap. It does not request public OpenStreetMap tiles, substitute another tile provider, prefetch map data, or generate routes. A decoded image can itself be a provider denial image, so image loading is not treated as proof of valid map content. The fallback retains recorded coordinates and paths and distinguishes endpoint-only schematic lines; points without coordinates are not plotted. It offers a Google retry when online and an external Google Maps link. This is not an offline street map. Coordinate collection and precision gaps remain Agent-side checks in references/LOCATION_GUIDE.md.

For local images outside the canonical directory, include `--media-root "/absolute/path/to/image-directory"` on the first `start`. The successful start saves this setting in private `media.json` (0600) inside the sibling control directory, separately from the PID/birth/instance record. Repeated `start`, crash recovery, and `stop` followed by `start` can omit the option. `stop` removes the instance record but retains media and map settings. After an explicit stop, choose the next port again with `--port` if the default 8765 is unsuitable.

To replace the additional directory, stop the owned service and run `start ROOT --media-root DIRECTORY`. To clear it, stop and run `start ROOT --clear-media-root`; this persists the choice to serve only canonical-directory images. These two flags are mutually exclusive and apply only to `start`. Missing or changed saved directories fail with recovery instructions. If configuration was lost, a verified running instance can restore it; after that instance record is gone, supply the directory explicitly (or explicitly clear access). A failed startup preserves the previously saved setting. Only image IDs explicitly referenced by the validated canonical package and contained in an allowed directory are served; changing or clearing a root does not relocate images or rewrite their locators.

`GET /api/preview-status` exposes read-only package metadata, manifest SHA-256, running server source SHA-256, current frontend asset SHA-256/count, and whether frontend assets match the manifest. It shares the exact loopback Host/Origin checks and `no-store` policy. It returns no local roots, credentials or travel data. Managed `start`/`status` include this response as `runtime` only after process and HTTP instance verification; older servers without the endpoint return `runtime: null`. Package version, schema version and canonical revision alone do not identify frontend bytes. The frontend fingerprint describes files available at request time, not an already-open tab's cache; the server fingerprint is captured at module load. Treat installed bundles as immutable and refresh the page when comparing builds. This is not a complete runtime-dependency integrity check, and custom development servers may not implement the endpoint.

If the service died, `start` tries its recorded port so the URL stays stable. If another process took that port, it fails explicitly. Only after informing the user that the old URL cannot be kept, use `start ROOT --new-url --port 0`; the result includes `previous_url` and `url_changed=true`.

The extracted bundle already contains the production-built web application. Node and npm are build-machine dependencies and are not needed by the installed preview. The bundle intentionally contains no Google Maps key; the managed preview shows its own point/line schematic until a private local key is configured.

Each browser refresh re-reads and validates the selected canonical file. For managed work, pass `ROOT` to `preview-service` (or `ROOT/private-handbook.json` to the foreground `preview-handbook`), update only through `client commit`, and refresh the same page; restarting a live server is unnecessary. For old self-managed work, pass only the canonical package written by CLI `export` or `export_report["package"]` to the foreground launcher. Complete state files, export-report wrappers, malformed JSON, and schema-invalid packages are rejected.

## Media and compatibility

Use `media.image.add` to record an image locator, alt text, source and explicit representation; use `media.usage.add/remove` to attach or detach a Place introduction or Trip overview while preserving asset identity. Generated overviews record their generator and remain illustrations or schematics, not evidence of a real scene or a precise navigation route. These APIs do not search, generate, download, publish or determine rights.

Version 0.2.0 introduced optional Media fields within the current `1.0` schema profile. Existing packages remain readable without rewriting; packages using the new fields require the updated runtime/schema and may be rejected by older strict `1.0` validators. Keep the producing bundle version with the artifact.

The bundle displays explicit Trip and Place image usages. Local images must be inside the canonical directory or an additional directory supplied with `--media-root`; the server only reads images referenced by the validated canonical package.

## Validation boundary

Since 0.3.0, the bundle also includes reason-required Task retirement, explicit optional Route Stop encounter kinds, and optional hotel-local `role_details.lodging.check_in_time` in strict `HH:mm` form. Public Place creation and update support whole role-details objects with existing role and evidence protections. The first arrival remains `check_in`; the page adds the luggage-storage suffix only for an explicitly timed arrival safely known to precede the hotel check-in start. Equal, later, unknown or conflicting times keep the ordinary check-in label; subsequent returns and itinerary order remain unchanged. This does not establish early room access. Existing independent caller runs still had partial failures in duplicate GuideNotes and placement of trip-specific dates. Deterministic repairs on a separate synthetic copy and static guide checks do not demonstrate autonomous success with the final guidance. Engineering checks, rendered-page checks, real-world facts and local installation remain separate acceptance layers; publication does not demonstrate real-world completeness or autonomous caller success.

For 0.3.5, 84 browser cases covering six detail entrypoints, WebKit/Chromium, multiple viewport sizes, reopen and reduced motion passed; 84 affected unit tests and both frontend builds also passed. The original symptom was reproduced in desktop WebKit, not naturally reproduced in local Chromium; this does not establish that a user's mobile Chrome, installed PWA, or real address-bar animation is fixed on-device. Long panel scrolling and focus/scroll restoration were checked separately. The original in-app browser was unavailable to inspect and still needs a user refresh and recheck. Release-asset verification is recorded in the public changelog. The separately hosted multi-trip site, its branding assets and authentication/offline storage are not included in this Skill bundle. Earlier runtime and public-entrypoint evidence remains scoped to its original checks; missing historical frozen evaluation ZIPs remain an unchanged gate. No new natural-caller effectiveness claim is made. Other installations' Google key permissions, external image availability/licensing, and real travel facts still need separate validation.

## Integrity, privacy, and licenses

`MANIFEST.json` records the source revision, public entrypoints, environment contract, and SHA-256 digest of every distributed file other than the manifest itself. Run `scripts/verify_bundle.py` after copying or extracting the bundle. The verifier ignores only the local `.venv` created by setup.

State and exports can contain source text, personal details, dates, and travel arrangements. Keep them outside the installed skill directory and treat exports as private unless separately reviewed and authorized for publication.

The bundle includes the project's MIT `LICENSE` and `THIRD_PARTY_NOTICES.md`. The MIT license applies to original project files only. Dependencies installed into `.venv` remain under their upstream licenses and are not vendored into this skill ZIP; retain their installed license files if redistributing that environment.
