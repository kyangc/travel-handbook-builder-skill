# Runtime setup and installation

This guide covers the installed Skill's Python environment and launcher behavior. Start with the bundle README for the shortest installation path; this page is for environment choices and diagnostics. It does not change the [default authoring workflow](DEFAULT_WORKFLOW_GUIDE.md).

## Choose a Python environment

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

An inherited `PYTHONPATH` is ignored; handbook modules resolve only from this bundle’s `runtime/`. Normal API and CLI use therefore leaves the verified runtime unchanged.

The launchers and setup flow are validated on POSIX. The Python runtime uses portable paths, but this release does not claim a tested native Windows launcher contract.

## Load the complete Skill

Keep the whole `travel-handbook-builder-skill` directory together. Point the agent's skill directory setting at its parent, or copy this directory into the agent's normal skills directory. For Kimi CLI, supply the parent with `--skills-dir`; Kimi exposes the active skill root as `${KIMI_SKILL_DIR}`.

Do not copy only `SKILL.md`: references, launchers, runtime, Schemas, requirements and manifest are all required. Keep travel state, requests, exports and managed directories outside the installed Skill.

## Verify after normal use

`MANIFEST.json` records the source revision, entrypoints, environment contract and SHA-256 of every distributed file except itself. Run `scripts/verify_bundle.py` after extraction or copying, and again after setup or normal use. It ignores only the local `.venv` created by setup. Treat an installed bundle as immutable; upgrade by installing a verified bundle rather than editing its runtime files.

The bundle contains the project's MIT `LICENSE` and `THIRD_PARTY_NOTICES.md`. Dependencies installed into `.venv` retain their upstream licenses and are not vendored in the ZIP; retain their installed license files if redistributing that environment.
