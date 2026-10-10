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

## Things that have bitten CI

* **Formatting covers `tests/` and `tools/`** as well as `rpggen/`: run `python -m ruff format .`
  before you push, not only `ruff check`.
* **PNG and zip bytes depend on the platform's zlib.** The synthetic packs under
  `test_packs/synthetic/` are compared byte for byte only on Windows in CI;
  `tests/unit/test_synthetic_packs.py` compares decoded pixels and zip contents everywhere. After
  changing `tools/make_synthetic_packs.py`, regenerate on Windows and run
  `python -m rpggen.dev update-goldens`. Godot cannot load the header-only audio stubs the tool
  writes, so the two `.ogg` files of `audio_basic` are real encoded files that the tool keeps.
* **Git repacks in the background**, so integration tests that snapshot a generated project leave
  `.git/` out and check the repository with `vcs.is_clean`.
* **Kill the whole process tree.** `rpggen/core/godot.py` starts Godot in its own session on
  POSIX and kills the group, because Godot starts children of its own.
* **A late worker callback can reach a closed page.** Callbacks that touch widgets guard with a
  `try: widget.objectName() except RuntimeError: return`.
* **Smoke steps that depend on saves** must clear the autosave slot (`AUTOSAVE_SLOT`, 0) as well
  as slots 1 to 3.
* **Smoke-test lists** are asserted by the integration tests (`M6_STEPS`, `M7_STEPS`, `M9_STEPS`
  and the list in `test_generate_basic16.py`); adding a step means updating them.
* **A local Godot** can sit in the project folder (`Godot_v*` is git-ignored); point
  `RPGGEN_GODOT` at its console executable.

To change the Godot version the app targets, use `python tools/bump_godot.py <version>`
([docs/release.md](docs/release.md)). To refresh the pictures in the user guide, run
`python tools/make_doc_screenshots.py --godot <exe>` (a test checks that the guide and the images
agree).

## How the project is organized

The project was built from task cards (`docs/spec/M01_...M14`), one milestone at
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

1. Add the row to `docs/spec/03_ERROR_CODES.md`.
2. Run `python tools/gen_error_codes.py`; it regenerates `rpggen/errors_table.py`,
   `godot_templates/builder/lib/error_codes.gd` and `docs/errors.md`. CI fails when they are stale.
3. Raise it with `issues.add("AREA-NNN", placeholder=value)` or `raise RpgGenError(...)` in Python,
   or the shared helper in GDScript. Never invent a message string outside the table.
4. Test the situation that raises it, and mention a user-facing code in `docs/user_guide.md`.

## Translating the wizard

The wizard's texts go through `tr()`; Qt's tools turn them into translations (T12.56).

1. Start a language, or bring an existing one up to date with new texts:
   `python tools/update_translations.py extract --lang fr` (`--lang` only for a new language;
   without it every `rpggen/gui/i18n/rpggen_<lang>.ts` is updated). Commit the `.ts` file.
2. Translate with Qt Linguist (`pyside6-linguist rpggen/gui/i18n/rpggen_fr.ts`) or any editor
   that knows the format. Keep `{0}`-style placeholders, `&` mnemonics and `\t` shortcuts.
   A text left unfinished is shown in English.
3. `python tools/update_translations.py release` builds the `.qm` files (not committed; the
   release build runs this step). Pick the language under *View > Language* and restart.

Texts are only found when `tr()` is given a string literal: write `self.tr("A") if x else
self.tr("B")`, not `self.tr("A" if x else "B")`, and mark lists of texts with
`QT_TRANSLATE_NOOP("Context", "Text")` (see `PAGE_NAMES` in `rpggen/gui/wizard.py`). Error messages
stay English: they are documented by code in `docs/errors.md`. French (`rpggen_fr.ts`) is the
pilot: the step names, the menus, the navigation and the welcome view are translated; a native
speaker's review and the remaining texts are welcome.

The generated game is translated separately, by adding columns to its `game/i18n/strings.tsv`
(see the project's README).

## Look and feel

The wizard has one design system (M15). Keep to it, so that a new widget looks like the rest in
both themes.

* **Tokens.** Every colour, radius and size has a name in `rpggen/gui/theme.py` (`TOKENS`, one
  table per theme, and `SIZES`). `rpggen/gui/style.qss.in` is the only stylesheet: it is a
  template, `@token` becomes the value of the theme in use, and a name that is not a token is
  an error. In code ask `theme.token("accent")` or `theme.px("pad_control")`; never write a
  colour code. A new token needs a value in both themes and has to pass the contrast tests
  (`tests/gui/test_theme_a11y.py`, `tests/gui/test_design_system.py`).
* **No inline styles.** A widget is styled by a rule on its object name or on a property
  (`widget.setProperty("role", "section")`, then `theme.repolish(widget)`), not by
  `setStyleSheet`. A test lists the two exceptions, which carry a colour of the data.
* **Buttons.** `widgets.buttons.set_kind(button, PRIMARY | SECONDARY | QUIET | DANGER)`. A view
  has **one** primary button: what the user most likely does next.
* **Icons.** The icons are rpggen's own SVG files in `rpggen/gui/icons` (24 px view box, 2 px
  stroke, `currentColor`), written by `tools/make_ui_icons.py`. To add one, add its drawing to
  that tool and run it (a test runs it with `--check`); use it with `icons.set_icon(button,
  "name")` or `icons.pixmap("name", "accent", 24)`, which follow the theme. No bitmap icons:
  they blur at 150 %.
* **Pages** start with `page_layout()` (the margins and the header); cards are
  `widgets.card.Card`, messages `Banner`.
* **Pictures of every page.** `tests/gui/test_visual_goldens.py` renders the welcome view and
  the seven pages, in both themes and at both window sizes, and compares them with the pictures
  in `tests/gui/goldens`. When a change to the look is meant, run
  `python -m rpggen.dev update-ui-goldens`, look at what changed (`git diff --stat` names the
  pages) and commit the new pictures with the change, with a before and after of each page in
  the pull request. A failure leaves the page as it is now and a picture of the difference in
  `tests/gui/goldens/_failed`; CI uploads them. The goldens are rendered with the test font
  in `tests/gui/fonts` (DejaVu 2.37: regular, bold and mono), not with a font of the machine,
  so they can be made and compared on any system.

## Documentation

`docs/architecture.md` is a copy of `docs/spec/ARCHITECTURE.md`; a test fails when they differ.
Screenshots in `docs/images/` are generated: `python tools/make_doc_screenshots.py --godot <exe>`
(without Godot the Generate and Results pages are left out). They are 1100 x 720 pictures of
a display at 100 %: on a display that is scaled, set `QT_ENABLE_HIGHDPI_SCALING=0` and
`QT_FONT_DPI=96` for the run.

## Releases

See [docs/release.md](docs/release.md).
