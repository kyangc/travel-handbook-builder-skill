# 行迹 · Travel Handbook Builder Skill

Build and revise a private travel handbook with a local Python runtime and browser preview. The Agent interprets supplied material and may research relevant public facts; the runtime records facts, unknowns and revisions. It does not choose plans, make bookings or payments, verify real-world facts, or publish content.

## Requirements and isolated setup

Use Python 3.12+ and a POSIX shell (macOS or Linux). Keep the entire extracted `travel-handbook-builder-skill` directory together, including `SKILL.md`, references, runtime, launchers and manifest.

From any directory, verify the bundle and create its isolated environment:

```sh
python3 "/path/to/travel-handbook-builder-skill/scripts/verify_bundle.py"
python3 "/path/to/travel-handbook-builder-skill/scripts/setup_runtime.py"
```

Setup installs the pinned dependencies into the Skill's `.venv`, without changing global Python. It needs package-index or cache access. If an existing Python already has the dependencies, use `TRAVEL_HANDBOOK_PYTHON` instead; interpreter selection, diagnostics and integrity checks are in the [runtime setup guide](references/RUNTIME_SETUP_GUIDE.md). Native Windows launchers are not a tested contract.

## Load and start

Point your agent's Skill setting at the directory's parent, or copy the whole directory into its normal skills folder. Kimi CLI accepts the parent with `--skills-dir`. Keep travel files and managed workspaces **outside** the installation directory.

Ask the agent, for example:

> Use travel-handbook-builder-skill to turn these notes into a private handbook and open its local preview. Preserve confirmed arrangements, keep recommendations separate, and leave missing times, bookings and costs unknown.

The [default CLI workflow](references/DEFAULT_WORKFLOW_GUIDE.md) covers the complete sequence: create a public request, review `preview`, `apply`, `check`, then `client init` a new managed directory **before the first webpage opening**. Initialize only after `check.valid=true`. Later edits go through [managed continuation](references/CLIENT_GUIDE.md), with `client check` for the current full report; do not directly rewrite managed files.

For command help from any working directory:

```sh
"/path/to/travel-handbook-builder-skill/scripts/travel-handbook" --help
```

## Open the local preview

For an initialized managed workspace:

```sh
SKILL_DIR="/path/to/travel-handbook-builder-skill"
"$SKILL_DIR/scripts/preview-service" start "/absolute/path/to/managed-ROOT" --port 0
```

Open the returned `url`. Later `client commit` updates the same canonical handbook; refresh the page. Authoring `preview` is a request dry-run, distinct from this browser view. See [browser preview operations](references/BROWSER_PREVIEW_GUIDE.md) for status/stop, standalone exports, image roots and recovery.

Google Maps requires your own restricted browser key; the bundle contains none. Configure it through the private local preview service, never in requests or canonical data. Without a key, after a Google failure, or offline, the view uses a labeled point/line schematic with **no basemap**. It does not fetch public OSM tiles or provide an offline street map.

## Find the relevant guide

| Need | Guide |
| --- | --- |
| Public methods and live capabilities | [API inventory](references/README.md) · [detailed calling contract](references/CALLER_GUIDE.md) |
| Supplement missing material or images | [content collection](references/CONTENT_COLLECTION_GUIDE.md) · [Media](references/MEDIA_GUIDE.md) |
| Edit daily arrangements or summaries | [arrangement edits](references/ARRANGEMENT_EDIT_GUIDE.md) |
| Correct lodging actions or preparation Tasks | [Stay](references/STAY_GUIDE.md) · [Task preparation](references/TASK_PREPARATION_GUIDE.md) |
| Recover older state or inspect bounded reads | [recovery and export](references/RECOVERY_READ_PREVIEW_GUIDE.md) |
| Use the Python API | [optional Python examples](references/PYTHON_OPTIONAL_GUIDE.md) |

For a complete state that has not entered managed, keep full state, canonical package and export report separate. `export_report["package"]` is the canonical import input; an export report wrapper is not. CLI `export` writes only canonical JSON. Follow the recovery guide for safe saves; managed publication belongs to `client commit`.

## Privacy and validation

State and exports may contain personal details and source text. Treat them as private unless separately reviewed and authorized for sharing. Local preview is not public hosting or cross-device sync; a cloud Agent's data handling remains governed by that tool.

Checks validate structure and bounded rules, not source completeness, travel feasibility, external services or autonomous Agent success. Review the rendered result and verify important facts separately. Existing `1.0` packages remain readable; newer optional fields may be rejected by older strict validators, so retain the producing bundle version. Release changes and their evidence boundaries are in the [public changelog](https://github.com/kyangc/travel-handbook-builder-skill/blob/main/CHANGELOG.md).

Run `scripts/verify_bundle.py` after extraction, copying or setup. Licensing: [MIT](LICENSE) for original files, with [third-party notices](THIRD_PARTY_NOTICES.md); installed dependencies retain their upstream licenses.

Daily weather is optional: [weather guide](references/WEATHER_GUIDE.md). The browser queries Open-Meteo directly with coordinates and the declared day/timezone (no key, credentials or private handbook headers). The free API is for non-commercial use; weather data attribution is Open-Meteo / CC BY 4.0, preserved in THIRD_PARTY_NOTICES.md and provided through one information popover beside the overview weather heading and after the daily weather location title (hover, keyboard focus or tap). The popover links the provider and licence and notes rounding; there is no page-bottom source section. Lucide icons use ISC. Forecasts persist only with a manual offline save in the authenticated site; portable preview keeps session data only. New `Day.weather_location_ref` packages require a weather-capable runtime/frontend (0.3.7 or later); existing packages remain compatible.
