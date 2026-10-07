# Contributing to rpggen

Thank you for helping. This file covers setting up, running the tests, how work is organized, and
the three most common contributions: a **pack profile** (no Python needed), an **adapter**, and an
**error code**.

## Development setup

You need Python 3.12 and Git. For the integration tests you also need **Godot 4.7.2** (the
console build on Windows) and its path in `RPGGEN_GODOT`.

```bat
git clone https://github.com/DocDamage/Godot-Project-Maker-4.7.2
cd Godot-Project-Maker-4.7.2
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

On Linux or macOS use `source .venv/bin/activate`. The Qt tests run with
`QT_QPA_PLATFORM=offscreen` (set by `tests/gui/conftest.py`); on Linux install `libegl1 libgl1
libxkbcommon0 libdbus-1-3 libfontconfig1`.

## Running the tests

```bat
python -m pytest -q -m "not integration"      :: unit and GUI tests, no Godot needed
python -m rpggen.dev godot-test               :: the template project's GDScript tests
set RPGGEN_GODOT=C:\Godot\Godot_v4.7.2-stable_win64_console.exe
python -m pytest -q -m integration            :: generation, validation and smoke tests with Godot
python -m pytest -q -m slow tests/perf        :: performance targets on a 1,000-image pack
python -m ruff check .
python -m ruff format --check .
python -m mypy rpggen
```

Integration tests are **skipped, not failed**, when `RPGGEN_GODOT` is unset; CI always sets it.
CI (`.github/workflows/ci.yml`) runs the whole list on Windows and on Ubuntu; the Linux job is what
finds path-case and path-separator bugs, so do not skip it.

## How the project is organized

The project was built from task cards (`docs/spec/M01_...M11`), one milestone at
a time, and the habits carried over:

* **A task card** has *Depends on*, *Files*, *Spec*, *Tests* and *Done when*. Change only the files
  the card lists; if another file must change, say why in `docs/dev/implementation_notes.md`.
* **Tests first or together.** Never delete or weaken a test to make it pass.
* Every finished task adds a line to `docs/dev/implementation_notes.md` (`T1.04 done — summary —
  deviation`) and is committed as `T1.04: <card title>`.
* Judgment calls go under *Decisions* in `docs/dev/implementation_notes.md`. Two documents that contradict
  each other in a way that changes behavior: stop and report it.
* The conventions (layout, naming, logging, determinism, Godot rules) are in
  `docs/spec/01_CONVENTIONS.md`; the file formats in `docs/spec/02_SCHEMAS.md`.

Hard rules (details in `docs/spec/00_START_HERE.md`):

* Never hand-write `.tscn`, `.tres` or `project.godot` content; GDScript *recipes* build them
  headless and save through `ResourceSaver`. The one exception is `export_presets.cfg`, rendered
  from a verified template.
* Never write a `uid://` value; never modify files inside an input pack.
* Never use unseeded randomness or the current time in generated content.
* Verify every Godot API against `docs/godot_api_verified.md` (or a probe script) before using it.
* Generated output must be deterministic: the same inputs give the same bytes.

## Add a pack profile (no Python needed)

If rpggen misdetects a pack you own, you can fix it once for everybody:

1. Generate a project from the pack and correct the **Audit** page until it looks right (roles,
   grids, collision, animations, objects, folder rules).
2. Audit → **Profile → Export pack profile…**; keep the license `CC0-1.0`.
3. Open a pull request against the profile registry (`registry/CONTRIBUTING.md`; the content lives
   in `registry/` here until the separate `rpggen-profiles` repository exists) and add the file
   under `profiles/`. CI validates it and regenerates `index.json`.

A profile contains no images; never commit pack files. See [docs/profiles.md](docs/profiles.md).

## Add an adapter

An adapter teaches rpggen a whole pack *format*. Follow [docs/adapters.md](docs/adapters.md):
implement `match`/`extract`, register it, add a **synthetic pack** (generated, CC0, no real art) to
`tools/make_synthetic_packs.py` with an `expected.json`, write unit tests, update the goldens
(`python -m rpggen.dev update-goldens`) and keep the accuracy corpus above its thresholds.

## Error codes

`docs/spec/03_ERROR_CODES.md` is the single source of truth: one row per code with severity (E, W
or I), a message template with `{placeholders}` and a recommended fix.

1. Add the row to `docs/spec/03_ERROR_CODES.md` **and** copy it to
   `docs/spec/03_ERROR_CODES.md`.
2. Run `python tools/gen_error_codes.py`; it regenerates `rpggen/errors_table.py`,
   `godot_templates/builder/lib/error_codes.gd` and `docs/errors.md`. CI fails when they are stale.
3. Raise it with `issues.add("AREA-NNN", placeholder=value)` or `raise RpgGenError(...)` in Python,
   or the shared helper in GDScript. Never invent a message string outside the table.
4. Test the situation that raises it, and mention a user-facing code in `docs/user_guide.md`.

## Documentation

`docs/architecture.md` is a copy of `docs/spec/ARCHITECTURE.md`; a test fails when they differ.
Screenshots in `docs/images/` are generated: `python tools/make_doc_screenshots.py`.

## Releases

See [docs/release.md](docs/release.md).
