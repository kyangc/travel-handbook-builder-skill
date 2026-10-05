# 行迹 · Travel Handbook Builder Skill

Create and revise a private travel handbook from supplied choices and sourced facts. The Agent interprets material; the local runtime stores typed requests and serves a browser preview. Booking, payment, and public publishing require separate user action.

## Install

Use Python 3.12+ on macOS or Linux. Keep the extracted directory together and place travel data outside it. Verify the bundle, then prepare its isolated runtime:

```sh
python3 "/path/to/travel-handbook-builder-skill/scripts/verify_bundle.py"
python3 "/path/to/travel-handbook-builder-skill/scripts/setup_runtime.py"
```

An existing interpreter with the required dependencies can be selected with `TRAVEL_HANDBOOK_PYTHON`; see [runtime setup](references/RUNTIME_SETUP_GUIDE.md). Point the Agent's Skill setting at this directory's parent. Kimi CLI accepts that parent with `--skills-dir`. Run `scripts/travel-handbook --help` for CLI commands.

## Create and continue

Follow the [default CLI workflow](references/DEFAULT_WORKFLOW_GUIDE.md): create a full state, review `preview`, apply the same request, check it, and initialize a new managed ROOT **before opening the browser**. Later changes use `client read` or `context`, `prepare-*`, and `commit` in that ROOT; see [managed continuation](references/CLIENT_GUIDE.md). Load [Python examples](references/PYTHON_OPTIONAL_GUIDE.md) only for programmatic state handling. The [public method index](references/README.md) routes to topic guides, including [content collection](references/CONTENT_COLLECTION_GUIDE.md).

For an initialized ROOT, start the persistent local preview and open its returned URL:

```sh
"/path/to/travel-handbook-builder-skill/scripts/preview-service" start "/absolute/path/to/managed-ROOT" --port 0
```

Refresh that URL after `client commit`. The authoring `preview` is a write dry-run, separate from this browser view. [Browser preview operations](references/BROWSER_PREVIEW_GUIDE.md) covers status, stop, media paths, map-key configuration, and recovery. Google Maps needs your own restricted browser key; without one the fallback displays handbook points and lines without a basemap.

For a complete state that has not entered managed, keep the full state and canonical package separate. `export_report["package"]` is the canonical import input; an export report wrapper is not. CLI `export` writes only the canonical package. See [recovery and export](references/RECOVERY_READ_PREVIEW_GUIDE.md).

Treat source text, state, and exports as private. `check.valid` tests structure, not factual accuracy, current opening hours, feasibility, bookings, or publication. Inspect the rendered page before claiming visible content. Run `scripts/verify_bundle.py` again after copying or setup. Original files use [MIT](LICENSE); bundled third-party materials are listed in [notices](THIRD_PARTY_NOTICES.md).
