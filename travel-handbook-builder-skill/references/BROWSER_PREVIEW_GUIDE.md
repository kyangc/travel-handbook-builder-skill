# Local browser preview

The installed Skill includes a built frontend; Node and npm are not required. This guide covers its loopback server, managed lifecycle, map configuration and local images. For creation and edits, follow the [default workflow](DEFAULT_WORKFLOW_GUIDE.md) and [managed continuation](CLIENT_GUIDE.md). The separately hosted multi-trip site is not part of this bundle.

## Start and stop

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

`stop` does not validate managed data: its response has `publish_status: null` and `data_error: "not_checked"`. `status` or `client check` reports current data separately. If `start` times out, the error names the last readiness stage and HTTP probe result plus the private log path; inspect that log locally before retrying. These diagnostics do not establish the cause of an earlier timeout.

## Google Maps and the schematic fallback

First run `preview-service maps-status ROOT`; it returns only `asked`, `configured` and `skipped`. If `asked=false`, ask the user once whether they want Google Maps. Record a decline or unanswered optional prompt with `preview-service maps-skip ROOT`. The same preview URL then shows the handbook's own point/line schematic without a basemap.

To configure later, put your Google Maps JavaScript API key in a private local file and run `preview-service maps-configure ROOT < /private/path/to/key-file`; refresh the existing URL. The bundle supplies no key. The key is read from standard input, stored only in the 0700 preview control directory as a 0600 file, never returned by status, and never written to canonical data, requests, logs, URL fragments, or the release. Do not place a key directly in a shell argument or repository `.env` file.

The browser must receive the key to load Google's JavaScript API, so it is visible in browser network requests. Restrict it to the Maps JavaScript API and the intended HTTP referrers in Google Cloud Console; a browser key cannot be kept secret from someone who can inspect that browser. See [Google's key setup](https://developers.google.com/maps/documentation/javascript/get-api-key) and [key security guidance](https://developers.google.com/maps/api-security-best-practices).

When Google Maps cannot load, is not configured, or the browser is offline, the preview labels the fallback as a point/line schematic with no basemap. It does not request public OpenStreetMap tiles, substitute another tile provider, prefetch map data, or generate routes. A decoded image can itself be a provider denial image, so image loading is not treated as proof of valid map content. The fallback retains recorded coordinates and paths and distinguishes endpoint-only schematic lines; points without coordinates are not plotted. It offers a Google retry when online and an external Google Maps link. This is not an offline street map. Coordinate collection and precision gaps remain Agent-side checks in [LOCATION_GUIDE.md](LOCATION_GUIDE.md).

## Local image directories

For local images outside the canonical directory, include `--media-root "/absolute/path/to/image-directory"` on the first `start`. The successful start saves this setting in private `media.json` (0600) inside the sibling control directory, separately from the PID/birth/instance record. Repeated `start`, crash recovery, and `stop` followed by `start` can omit the option. `stop` removes the instance record but retains media and map settings. After an explicit stop, choose the next port again with `--port` if the default 8765 is unsuitable.

To replace the additional directory, stop the owned service and run `start ROOT --media-root DIRECTORY`. To clear it, stop and run `start ROOT --clear-media-root`; this persists the choice to serve only canonical-directory images. These two flags are mutually exclusive and apply only to `start`.

Missing or changed saved directories fail with recovery instructions. If configuration was lost, a verified running instance can restore it; after that instance record is gone, supply the directory explicitly (or explicitly clear access). A failed startup preserves the previously saved setting. Only image IDs explicitly referenced by the validated canonical package and contained in an allowed directory are served; changing or clearing a root does not relocate images or rewrite their locators.

## Runtime identity and restart recovery

`GET /api/preview-status` exposes read-only package metadata, manifest SHA-256, running server source SHA-256, current frontend asset SHA-256/count, and whether frontend assets match the manifest. It shares the exact loopback Host/Origin checks and `no-store` policy. It returns no local roots, credentials or travel data. Managed `start`/`status` include this response as `runtime` only after process and HTTP instance verification; older servers without the endpoint return `runtime: null`.

Package version, schema version and canonical revision alone do not identify frontend bytes. The frontend fingerprint describes files available at request time, not an already-open tab's cache; the server fingerprint is captured at module load. Treat installed bundles as immutable and refresh the page when comparing builds. This is not a complete runtime-dependency integrity check, and custom development servers may not implement the endpoint.

If the service died, `start` tries its recorded port so the URL stays stable. If another process took that port, it fails explicitly. Only after informing the user that the old URL cannot be kept, use `start ROOT --new-url --port 0`; the result includes `previous_url` and `url_changed=true`.

## Updating the same handbook

Each browser refresh re-reads and validates the selected canonical file. For managed work, pass `ROOT` to `preview-service` (or `ROOT/private-handbook.json` to the foreground `preview-handbook`), update only through `client commit`, and refresh the same page; restarting a live server is unnecessary. For old self-managed work, pass only the canonical package written by CLI `export` or `export_report["package"]` to the foreground launcher. Complete state files, export-report wrappers, malformed JSON, and schema-invalid packages are rejected.
