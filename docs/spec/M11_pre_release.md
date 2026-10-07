# M11 — Pre-release Fixes, Wizard UX and Game Polish

**Goal:** close the gaps found in the pre-release review before the manual test pass starts, so
that testing is done once, on the thing that ships. Three groups of work: (A) things that are
broken or misleading as built, (B) wizard usability and features, (C) what a player notices in the
first five minutes of a generated game. A fourth group (D) is the manual test pass itself, and (E)
lists what is deliberately left for 1.1.

This file follows the format of M01–M10. It was written against commit `5d985ba` (M10). File and
line references are to that commit.

## Ground rules for this milestone

* The conventions in `01_CONVENTIONS.md` apply unchanged: core logic stays out of the GUI, pages
  only edit `WizardState`, every edit is undoable, generated output is deterministic.
* **Versions stay at 1.0.0.** Nothing has been released, so the runtime, the app and the config
  keep their numbers. Add the runtime changes to the existing `1.0.0` heading in
  `godot_templates/addons/rpg_runtime/CHANGELOG.md`.
* **Config schema changes are additive and optional.** `config_version` stays 1; every new key
  has a default so a config written before M11 still loads and still validates. `to_json` omits
  a new key when it holds its default (as `starter` does today), so existing golden files and the
  determinism test do not move.
* **New error codes** go into `03_ERROR_CODES.md` first, then run `python tools/gen_error_codes.py`
  to regenerate `rpggen/errors_table.py`, `godot_templates/builder/lib/error_codes.gd` and
  `docs/errors.md`. Codes reserved by this milestone: `ENV-011`, `ENV-012`, `ASSET-026`,
  `ASSET-027`, `VAL-020`.
* **Recipe changes bump `RECIPE_VERSION`** of the recipe so existing projects rebuild the output.
* **The starter map is `user_seed`.** Anything in group C that changes `starter_map_recipe`
  affects new projects only; an existing map is never rewritten. Say so in the generated README
  where it matters.
* After any change to detection or the sample pack: `python -m rpggen.dev update-goldens` and
  `python tools/build_sample_pack.py`, and review the diff.

## Order of work

| Step | Tasks | Why this order |
|------|-------|----------------|
| 1 | T11.01 – T11.08 | Small, independent, and they change what the test pass exercises |
| 2 | T11.09 – T11.11 | App settings and the menu bar are used by most of the UX tasks |
| 3 | T11.20 – T11.24 | Audio and game polish: the largest user-visible gain |
| 4 | T11.12 – T11.19 | Wizard page polish |
| 5 | T11.25 – T11.27 | Starter map options and preview (depends on T11.20 for schema layout) |
| 6 | T11.28 | Docs and screenshots, once the pages have stopped moving |
| 7 | T11.29 – T11.30 | Manual test pass and gate |

Tasks inside a step are independent unless **Depends on** says otherwise.

---

# Part A — Fix before release

## T11.01 — Correct the repository URLs

**Depends on:** nothing
**Files:** `rpggen/__init__.py`, `README.md`, `packaging/installer.iss`, `rpggen/core/profile_registry.py`, `registry/README.md`, `registry/CONTRIBUTING.md`, `docs/profiles.md`, `docs/release.md`, `tests/unit/test_release.py`

The project lives at `https://github.com/DocDamage/Godot-Project-Maker-4.7.2`. Three places point
at `github.com/rpggen/rpggen`, which is not this project: `README.md:17`,
`packaging/installer.iss:12` and (for the registry) `rpggen/core/profile_registry.py:28`.

* Add one constant, `REPO_URL = "https://github.com/DocDamage/Godot-Project-Maker-4.7.2"`, to
  `rpggen/__init__.py`, plus `RELEASES_URL`, `ISSUES_URL` and `DOCS_URL` (the `docs/` tree on
  `main`) derived from it. Every Python use reads these.
* Replace the literal URLs in the README and `installer.iss` (`AppPublisherURL`; also add
  `AppSupportURL` and `AppUpdatesURL`).
* Test in `test_release.py`: no tracked text file outside `docs/spec/` and
  `Implementation Plan and Specs/` contains `github.com/rpggen/`; the URL in `installer.iss`
  equals `REPO_URL`.

If the repository is renamed before release, this is then a one-line change.

---

## T11.02 — Make "Find profile online" work, off the GUI thread

**Depends on:** T11.01
**Files:** `rpggen/core/profile_registry.py`, `rpggen/gui/pages/audit_page.py`, `rpggen/gui/dialogs/profile_dialogs.py`, `registry/`, `tests/unit/test_profile_registry.py`, `tests/gui/` (audit profile tests)

**Problem 1: the registry does not exist.** `REGISTRY_BASE` is
`https://raw.githubusercontent.com/rpggen/rpggen-profiles/main/`; that repository was never
created, so the menu item always ends in "Could not reach the profile registry".

Decision: serve the registry from this repository's `registry/` folder for 1.0. It is already
there, already validated by tests, and needs no second repository to maintain.

* `REGISTRY_BASE = "https://raw.githubusercontent.com/DocDamage/Godot-Project-Maker-4.7.2/main/registry/"`.
* Move `registry/.github/workflows/validate.yml` into the real `.github/workflows/` as
  `registry.yml`, with `paths: ["registry/**"]`, running `python registry/scripts/build_index.py
  --check`. A workflow file under `registry/.github/` never runs.
* Rewrite `registry/README.md` and `registry/CONTRIBUTING.md` for "a folder in the main repo";
  update `docs/profiles.md`.
* An environment variable `RPGGEN_REGISTRY_BASE` overrides the base (https only, same checks) so
  a fork or a test server can be used.

**Problem 2: the lookup blocks the window.** `AuditPage.find_profile_online`
(`audit_page.py:349`) calls `fetch_registry` and `download_registry_profile` directly; each can
take the 15 s timeout.

* Run both through `workers.Worker`. `Worker` passes `callbacks=` to its function, so add two
  thin functions in `workers.py`: `fetch_registry(inventories, *, callbacks)` and
  `download_profile(profile_id, *, callbacks)`.
* While either runs, show a modal `QProgressDialog` (indeterminate, with Cancel) in the style of
  `widgets/analysis_progress.py`. Cancel abandons the result: the worker cannot interrupt
  `urlopen`, so the dialog closes at once and the late result is ignored (compare a request
  token, as `ProjectPage._key` does).
* Keep the two overridable methods (`fetch_registry`, `download_registry_profile`) as the seams
  the tests replace; the tests now wait with `qtbot.waitSignal`.
* Messages: distinguish "no connection" (`RegistryError` from `OSError`), "the registry returned
  something unusable", and "no profile matches your packs" (already handled).

Tests: the GUI thread processes events while a slow fake fetcher sleeps (a `QTimer` fires during
the call); cancel during the fetch leaves the catalog untouched; a registry index served from
`registry/` on disk through a fake fetcher still matches the sample pack.

---

## T11.03 — Remove the GPL dependency (mutagen)

**Depends on:** nothing
**Files:** `rpggen/core/audio_info.py` (new), `rpggen/core/classifier.py`, `pyproject.toml`, `THIRD_PARTY_NOTICES.md`, `docs/release.md`, `packaging/rpggen.spec`, `tests/unit/test_audio_info.py`, `tests/unit/test_release.py`, `tools/make_synthetic_packs.py`

mutagen is GPL-2.0-or-later and is bundled, which puts the whole Windows build under GPL terms.
It is used in one function, `classifier.audio_duration` (`classifier.py:83`), to read the length
of OGG and MP3 files so that tracks of 20 s or more are classified as music.

Replace it with a small parser of our own. No third-party code.

`rpggen/core/audio_info.py`:

```python
def duration_seconds(path: Path) -> float | None: ...
```

* **WAV:** the existing `wave` code, moved here.
* **OGG Vorbis / Opus:** read the first page (`OggS`); the identification header gives the sample
  rate (Vorbis: bytes 12–15 of the `\x01vorbis` packet; Opus: always 48000, with pre-skip at
  bytes 10–11 of `OpusHead`). Then read the last 64 KiB of the file, find the last `OggS` page
  and take its 64-bit granule position (bytes 6–13). Duration = granule / rate (Opus: (granule −
  pre-skip) / 48000).
* **MP3:** skip an ID3v2 tag (`ID3`, 10-byte header, synchsafe size). Parse the first frame
  header for version, layer, bitrate and sample rate. If a `Xing`/`Info` header with a frame
  count is present, duration = frames × samples-per-frame / rate. Otherwise estimate from the
  file size and the first frame's bitrate (CBR assumption). The estimate only needs to be right
  about "longer than 20 s".
* **FLAC** (cheap to add): `fLaC`, STREAMINFO block: sample rate and total samples.
* Anything unreadable returns `None`; never raises. Cap reads at 256 KiB per file.

Then:

* `classifier.audio_duration` calls `audio_info.duration_seconds`; delete the mutagen import.
* Remove `mutagen` from `pyproject.toml`, from `THIRD_PARTY_NOTICES.md` (table row and the GPL
  paragraph), from the note in `docs/release.md`, and from any hidden import in `rpggen.spec`.
* `test_release.py`: assert that no dependency in `pyproject.toml` is on a deny-list
  (`mutagen`), and that `THIRD_PARTY_NOTICES.md` no longer says "GPL-2.0-or-later" outside the
  PyInstaller-bootloader row.
* Bump `ANALYZER_VERSION` (durations may differ by a few milliseconds, and the cache stores
  them).

Tests: generate fixtures in the test itself. WAV with `wave`; a minimal valid Ogg Vorbis stream
and a CBR MP3 built from hand-written headers plus padding frames (`tools/make_synthetic_packs.py`
gains helpers so the synthetic packs can also carry a 1 s SFX and a 30 s music file; see T11.20).
Assert durations within 0.1 s, `None` for truncated and garbage files, and that a 30 s file is
`AUDIO_MUSIC` while a 1 s file is `AUDIO_SFX`.

---

## T11.04 — Getting the right Godot: download button and clearer gate

**Depends on:** T11.09 (settings store) for remembering the path; can be built first and wired later
**Files:** `rpggen/core/godot_fetch.py` (new, from `tools/fetch_godot.py`), `tools/fetch_godot.py` (becomes a thin CLI over it), `rpggen/core/godot.py`, `rpggen/gui/pages/project_page.py`, `rpggen/gui/workers.py`, `03_ERROR_CODES.md`, `docs/user_guide.md`, tests

Today `godot.check_version` (`godot.py:48`) accepts only 4.7.x; anything else raises `ENV-002`.
A user who installs the current Godot from the website is stopped on the first page with no way
forward inside the app.

Keep the gate (the generated project and the builder are verified against 4.7 APIs), but give the
user the fix in one click.

1. **Move the downloader into the package.** `rpggen/core/godot_fetch.py` holds `zip_name`,
   `console_name`, `release_url`, `parse_sums`, `fetch` from `tools/fetch_godot.py`, plus:
   * `managed_dir() -> Path`: `paths.local_cache_dir() / "godot" / "<version>"`.
   * `fetch(version, out, platform, *, progress=None, is_cancelled=None)`: stream the download in
     1 MiB chunks to `<name>.part`, call `progress(done, total)`, verify the SHA-512 from the
     release's `SHA512-SUMS.txt` **before** extracting, extract only the expected executable
     names (reject any other member and any path with `..` or a drive), then rename into place.
   * Errors raise `RpgGenError("ENV-011", reason=...)`.
   * `tools/fetch_godot.py` imports from it, so CI keeps working unchanged.
2. **Find the managed copy.** `godot.auto_find_godot` also returns the console executable in
   `managed_dir()` and lists it first.
3. **Project page.** When no Godot is selected, or the selected one fails `ENV-002`, show a
   button under the field: **Download Godot 4.7.2 (about 60 MB)**. Clicking it shows a
   confirmation that names the source (`github.com/godotengine/godot/releases`), the size and the
   destination, then runs `fetch` in a `Worker` behind a progress dialog with Cancel. On success
   the path is put into the combo and the checks re-run.
4. **Messages.** `ENV-002` text becomes: "Godot {found} is not supported: rpggen 1.0 builds
   projects for Godot 4.7." Fix: "Press Download Godot 4.7.2, or select a 4.7.x executable. Your
   other Godot versions are not touched." Rename the field label from "Godot 4.7.2" to "Godot
   executable".
5. **Privacy text.** This is the app's second network action; like the first it only happens on
   a click. Update `README.md` (Privacy) and `docs/user_guide.md` §8.

New codes: `ENV-011` (E) "Could not download Godot: {reason}." / "Check your connection, or
install Godot 4.7.2 from godotengine.org and select it."

Tests (no network): `fetch` against a local fake opener: good archive; wrong checksum (nothing
extracted, `.part` removed); cancel mid-download; an archive containing `..\evil.exe` (rejected).
GUI: the button appears for no-Godot and for a fake 4.8 version string, not for 4.7.1.

---

## T11.05 — Cancel must stop a running Godot

**Depends on:** nothing
**Files:** `rpggen/core/godot.py`, `rpggen/core/orchestrator.py`, `rpggen/core/export_check.py`, `rpggen/gui/pages/generate_page.py`, tests

`orchestrator._execute` checks `cb.is_cancelled()` only between phases (`orchestrator.py:511`),
and `godot._run` blocks in `proc.communicate(timeout=...)` (`godot.py:92`). A cancel during
import, build, validate, smoke or export waits for that phase, up to its timeout.

* `godot._run` gains `is_cancelled: Callable[[], bool] | None`. Read stdout and stderr on two
  daemon threads into lists (so the pipes cannot fill), and wait with
  `proc.wait(timeout=0.2)` in a loop that checks the deadline and `is_cancelled()`. On cancel:
  `_kill_tree(proc)`, join the readers, return with a new flag.
* `GodotRun` gains `cancelled: bool = False`. `run_godot`, `import_project` and the export check
  pass `is_cancelled` through.
* `orchestrator._run_godot` (`orchestrator.py:139`) passes `state.cb.is_cancelled` and raises
  `_Stop` when the run was cancelled, without adding `BUILD-003`. `_execute` treats a cancelled
  stop exactly like a cancel between phases: staging is discarded, nothing is delivered, no
  `.rpggen_failed` folder is kept.
* Python-side long phases (`install`, `catalog`) check `is_cancelled` between packs and between
  assets.
* `GeneratePage`: "Cancelling…" becomes "Stopping Godot…" while a Godot phase is active. Closing
  the window while a run is active asks "Generation is running. Stop it and close?" and cancels
  first (today `leave` only vetoes page changes).

Tests: unit: a fake long-running process (`python -c "import time; time.sleep(60)"`) is killed
within 2 s of the cancel flag and its children are gone. Integration (needs Godot): cancel during
`import` returns within 5 s, the target folder does not exist afterwards and no `godot*`
process whose command line contains the staging path survives.

---

## T11.06 — Update check (opt-in, on click)

**Depends on:** T11.01, T11.10 (Help menu)
**Files:** `rpggen/core/update_check.py` (new), `rpggen/gui/dialogs/about_dialog.py`, `README.md`, `docs/user_guide.md`, tests

The README's Privacy section mentions update checks; none exist. Build the smallest honest
version rather than deleting the sentence.

* `update_check.latest_release(fetcher=...) -> Release | None`: GET
  `https://api.github.com/repos/DocDamage/Godot-Project-Maker-4.7.2/releases/latest` (https only,
  10 s timeout, 256 KiB limit, reuse the fetcher shape of `profile_registry.default_fetcher`),
  read `tag_name` and `html_url`. `is_newer(tag, current)` compares numeric tuples and ignores
  pre-releases.
* Help → **Check for updates…** runs it in a `Worker` and shows one of: "You have the latest
  version (1.0.0)", "Version X is available" with an **Open download page** button (opens the
  browser; the app never downloads or installs an update), or "Could not check".
* **Never automatic.** No check at start-up, no background timer, no setting to enable one.
* README Privacy and user guide §8 list exactly three network actions, each behind a click:
  find profile, download Godot, check for updates.

Tests: version comparison table; a fake fetcher for each of the three outcomes.

---

## T11.07 — Finish the loose ends in the generated game

**Depends on:** nothing (the HUD part touches the same recipe as nothing else here)
**Files:** see each item

**(a) `secondary_attack` does nothing.** `config.default_input` binds it (`config.py:64`) and
`README.arpg.md:12` admits it has no behavior. Give it one: a **charged heavy attack**.

* `archetypes/arpg/player_combat.gd`: in `_update_free`, `secondary_attack` enters `ATTACK` with
  `heavy = true`: damage × 1.75, knockback × 1.5, duration `GENERIC_ATTACK_S × 1.6`, active
  window shifted later by the same factor, and the player cannot buffer another attack out of
  it. Uses the `attack_*` animation at 0.7 speed (no new animation role).
* `arpg_math.gd`: `heavy_damage(base)`; unit-tested.
* `smoke_steps_arpg.gd`: one step `heavy_attack_hits` (more damage than the light attack on the
  same frozen enemy).
* `README.arpg.md`: document it; remove the "bound but" sentence.

**(b) Chests have no open frame.** `chest.gd:50` supports an `open_texture` meta, and the header
comment promises "2+ frames = frame 0 closed, frame 1 open", but `object_scenes_recipe` never
sets the meta, so every chest is only darkened.

* `object_scenes_recipe.gd` (chest template): when the chest asset is a strip or sheet with at
  least 2 frames (catalog `frame`/`grid` facets, or an animation named `open`), build two
  `AtlasTexture`s through `texture_util` and set frame 0 as the texture and frame 1 (or the last
  frame of `open`) as the `open_texture` meta.
* Keep the darkened fallback for single-frame chests, and keep `ASSET-023`.
* Add a 2-frame chest to the sample pack (`tools/build_sample_pack.py`) so the sample shows it.
* Test (GDScript): a built chest scene from a 2-frame asset has the meta; `apply_opened_state`
  swaps the texture and leaves `modulate` white.

**(c) The ARPG HUD ignores the pack's UI art.** `arpg/hud_recipe.gd` builds flat `ProgressBar`s.

* When the catalog has a UI asset with tag `bar` (or a name token `bar`, `gauge`, `health`,
  `hp`) and a nine-slice facet, style the bars with `StyleBoxTexture` (background from the
  frame, fill tinted). Otherwise keep the flat styles. The node stays a `ProgressBar`, so
  `hud.gd` is unchanged.
* The HUD panel uses the project theme's panel style (from `theme_recipe`) instead of no
  background.

Bump `RECIPE_VERSION` in `object_scenes_recipe`, `hud_recipe`; add CHANGELOG lines.

---

## T11.08 — Repository tidy-up

**Depends on:** nothing; do it in its own commit
**Files:** `Implementation Plan and Specs/` (delete), `IMPLEMENTATION_NOTES.md` (move), `README.md`, `CONTRIBUTING.md`, `tools/gen_error_codes.py`, `tests/unit/test_release.py`, `pyproject.toml`

* The spec exists twice. Keep `docs/spec/` as the only copy and delete
  `Implementation Plan and Specs/`. First grep for the folder name: `tools/gen_error_codes.py`,
  `test_release.py:82-86` (which asserts the two copies are equal), `pyproject.toml`
  (`extend-exclude`), README and CONTRIBUTING all mention it.
* Move `IMPLEMENTATION_NOTES.md` to `docs/dev/implementation_notes.md`. Append an "M11" section
  as tasks are done, in the existing one-line-per-task style.
* Add to `.gitignore`: `.mypy_cache/`, `validation_runs/`.
* PyInstaller: confirm `docs/spec/` and `docs/dev/` are **not** bundled (only the user docs).

---

# Part B — Wizard UX and features

## T11.09 — App settings that survive a restart

**Depends on:** nothing
**Files:** `rpggen/core/app_settings.py` (new), `rpggen/gui/wizard.py`, `rpggen/gui/pages/project_page.py`, `rpggen/gui/pages/audit_page.py`, tests

There is no application-level settings store. The Godot path returns only through auto-detection
or a per-target draft; the window always opens at 1100 × 720.

`app_settings.py`, plain JSON at `paths.local_cache_dir() / "settings.json"` (not `QSettings`:
core must be usable without Qt, and the file is easy to put into a diagnostic bundle):

```python
@dataclass
class AppSettings:
    godot_exe: str = ""
    last_pack_dir: str = ""
    last_target_dir: str = ""
    recent_projects: list[RecentProject] = field(default_factory=list)   # newest first, max 10
    window: dict[str, int] = field(default_factory=dict)                 # x, y, w, h, maximized
    splitters: dict[str, list[int]] = field(default_factory=dict)        # e.g. "audit"
    theme: str = "dark"                                                  # T11.19
    thumb_size: int = 96                                                 # T11.14
    option_presets: dict[str, dict] = field(default_factory=dict)        # T11.17
    quick_roles: list[str] = field(default_factory=list)                 # the 1-9 keys

def load() -> AppSettings      # missing or corrupt file -> defaults, never raises
def save(s: AppSettings) -> None   # atomic: write .tmp, replace
```

`RecentProject` = `{target, name, archetype, last_opened}`; entries whose folder no longer exists
are dropped on load.

Wiring:

* `MainWindow`: restore geometry on start (clamped to an existing screen), save on close.
* `ProjectPage`: the Godot combo's initial value is the saved path when it still exists; file
  dialogs start in `last_pack_dir` / `last_target_dir`; a successful generation adds the project
  to `recent_projects`.
* `AuditPage`: the splitter position.
* The diagnostic bundle includes `settings.json`, redacted like the other files.

Tests: round trip; corrupt JSON falls back to defaults; unknown keys are ignored (forward
compatible); geometry off-screen is clamped.

---

## T11.10 — Menu bar, About, Help

**Depends on:** T11.01, T11.09
**Files:** `rpggen/gui/wizard.py`, `rpggen/gui/dialogs/about_dialog.py` (new), `rpggen/gui/dialogs/error_lookup.py` (new), tests

The window has no menu bar, no version anywhere, and no route to the documentation.

* **File:** New project, Open project… (a folder picker that calls `open_target`), Recent
  projects ▸ (from T11.09), Exit.
* **Edit:** Undo / Redo (enabled on the Audit page; they forward to its `EditSession`).
* **View:** Theme ▸ Dark / Light (T11.19), Thumbnail size ▸ (T11.14).
* **Help:** User guide (opens the bundled `docs/user_guide.md` rendered in the existing
  `TextViewer`; images resolve against the bundled `docs/images`), Error codes… (a searchable
  list built from `errors_table`, showing message and fix), Keyboard shortcuts, Report a
  problem… (opens `ISSUES_URL` and offers **Export diagnostic bundle** first), Check for
  updates… (T11.06), About.
* **About:** name, version, runtime version, the Godot version it targets, license, a link to
  `REPO_URL`, and a **Third-party notices** button that shows `THIRD_PARTY_NOTICES.md`.
* **F1** opens the user guide at the section of the current page (each `WizardPage` gets a
  `help_anchor` class attribute).
* Window title: `rpggen — <project name>` once a name exists, with `[regenerating]` when the
  target is an existing project.

Tests: every action exists and is reachable; About shows `rpggen.__version__`; F1 on each page
resolves to an anchor that exists in the guide.

---

## T11.11 — Welcome screen and first-run flow

**Depends on:** T11.09
**Files:** `rpggen/gui/pages/welcome_page.py` (new), `rpggen/gui/wizard.py`, `rpggen/gui/pages/project_page.py`, tests

"Try with sample pack" is the best first experience and is a small button in the bottom-left
corner of an otherwise empty, error-covered page.

* A **Welcome** view shown before page 1 (not a numbered wizard step; the sidebar is hidden
  while it shows). Three large cards:
  1. **Try the sample**: "See a finished project in about a minute. Nothing to configure."
     Calls the existing `ProjectPage.try_sample`.
  2. **Start with my asset pack**: goes to the Project page.
  3. **Open an existing project**: folder picker, then `open_target`.
* Under the cards: **Recent projects** (name, archetype, folder, last opened); click opens it.
* A one-line Godot status at the bottom: "Godot 4.7.2 found at …" in green, or "Godot 4.7 not
  found" with the download button from T11.04.
* `rpggen gui --target X` skips the welcome view.
* Keep the small sample button on the Project page (the user guide and tests refer to it).

Tests: the sample card drives the same path as `tests/gui/test_wizard_flow.py`; a recent project
whose folder was deleted is not listed.

---

## T11.12 — Project page: errors only when earned

**Depends on:** nothing
**Files:** `rpggen/gui/pages/project_page.py`, `rpggen/gui/wizard.py`, `rpggen/gui/style.qss`, tests

A fresh page shows three red lines ("Add at least one asset pack", "Choose an output folder",
"The name needs 1 to 64 characters") and the window repeats all three above the Cancel button.

* Each field tracks **touched** (edited, or lost focus after an edit). An untouched empty field
  shows a neutral grey hint ("Drag a folder or archive here", "Where the Godot project will be
  created") instead of an error. Pressing Next with missing fields marks all of them touched
  and focuses the first invalid one.
* `Next` stays enabled on this page while fields are merely empty; it is the press that reveals
  what is missing. It stays disabled for real errors (bad Godot, unwritable folder).
* Remove the duplicate: `MainWindow.problem_label` is hidden for issues with code `GUI-INPUT`
  when the page shows its own inline message (add `WizardPage.shows_inline_errors = True` for
  pages that do).
* The pack list gets an empty-state drawing: a dashed border and "Drop asset packs here: folders,
  .zip, .7z or .rar".
* The project name is prefilled from the first pack's name (title-cased, sanitized) until the
  user edits it; the output folder is suggested as `Documents/rpggen/<name>` until edited.
* Each pack row shows its kind, file count and size once known, and a warning icon with the
  issue text for `ARCH-*` problems.

Tests: a fresh page has no `state="error"` label; Next on an empty page produces the three
errors and focus lands in the pack list; the prefill stops once the user types a name.

---

## T11.13 — Friendly names and descriptions for roles and usages

**Depends on:** nothing
**Files:** `rpggen/core/labels.py` (new), `rpggen/gui/widgets/asset_detail.py`, `rpggen/gui/widgets/bulk_panel.py`, `rpggen/gui/widgets/asset_grid.py`, `rpggen/gui/pages/mapping_page.py`, `rpggen/core/report.py`, tests

The combos show internal names: `DECORATION`, `GROUND`, `tiles`.

`labels.py` holds one table for every role and usage:

```python
ROLE_INFO = {
  "GROUND":     ("Ground tiles",   "Painted as the floor of the starter map. Walkable."),
  "WALL":       ("Wall tiles",     "Used for the map border. Blocks movement."),
  "DECORATION": ("Decoration",     "Placed as scenery. Available in the editor dock."),
  "PLAYER":     ("Player",         "The character you control."),
  ...
}
USAGE_INFO = {"tiles": ("Tile sheet", "Cut into a grid and added to a TileSet."), ...}
def role_label(role) -> str; def role_help(role) -> str   # unknown -> the raw name
```

* Combos display `label` and keep the raw value as item data (they already use
  `addItem(text, data)`), with the description as the item tooltip and as a grey line under the
  combo for the current value.
* The role filter on the Audit page, the Mapping page row titles ("Player *" with the raw name
  in the tooltip), the bulk panel and `GENERATION_REPORT.md` use the labels.
* A test asserts that every role in `classifier.ROLE_ORDER`, `asset_detail.ROLES` and
  `requirements` has an entry, and every usage in `asset_detail.USAGES`.
* Profiles, the catalog and the CLI keep the raw names.

---

## T11.14 — Audit page: layout, progress and review queue

**Depends on:** T11.13
**Files:** `rpggen/gui/widgets/asset_grid.py`, `rpggen/gui/widgets/asset_detail.py`, `rpggen/gui/pages/audit_page.py`, `rpggen/gui/style.qss`, tests

At the default width the pack filter reads "All pacl", the search box reads "Se…" and the
Profile button is clipped. There is no sense of how much work is left.

**Layout**

* Two rows above the grid. Row 1: the status chips, each with its **count** ("Needs attention
  12"). Row 2: role filter, pack filter, search (stretching, placeholder "Search by name or
  folder"), and a thumbnail-size slider (64 / 96 / 128 / 192; saved in app settings; the cache
  key in `thumbnails.py` already includes a variant hash, add the size to it).
* Move **Profile** into the tab bar's corner widget (`QTabWidget.setCornerWidget`) so it cannot
  be clipped.
* Minimum window width 1000; the splitter position is restored (T11.09).

**Progress**

* A header line above the chips: a progress bar and "**328 of 340 reviewed** — 12 need
  attention". Reviewed = `CONFIRMED` or `UNUSED`; needs attention = the existing
  `NEEDS_ATTENTION` set. Lives in core as `catalog.review_progress(catalog) -> (done, attention,
  total)`.
* When attention reaches 0: "Everything that needed attention is done. Auto-detected assets can
  be left as they are." and the Next button gets the default focus.

**Queue**

* `N` / `Shift+N`: select the next / previous asset that needs attention (wraps; uses the proxy
  order). After `C` (confirm) or `X` (exclude) on a single selected asset the selection advances
  to the next one that needs attention, so review is "look, press C, look, press C".
* **Confirm all auto-detected** button (visible on the Auto-detected chip): one undo step,
  through `EditSession.bulk_edit`.
* A **`?`** button opens a shortcut sheet (C, X, N, 1–9 with their current roles, Ctrl+Z/Y,
  Ctrl+wheel zoom).

**Detail panel**

* A "Why" line under Role: the top three reasons the classifier already returns in `roles_alt`
  and the matched keywords ("folder *characters*, 4 rows of 3 frames").
* The empty-selection state says "Select an asset to see and correct what rpggen detected."
  instead of an empty form.
* Multi-selection shows "5 assets selected" and points at the bulk panel.

Tests: chip counts follow edits and undo; `N` cycles only through attention assets; confirm
advances; at 1000 px width no toolbar widget is narrower than its size hint (the regression test
for the clipping).

---

## T11.15 — Mapping page: clearer rows and audio

**Depends on:** T11.13, T11.20 (audio rows)
**Files:** `rpggen/gui/pages/mapping_page.py`, `rpggen/core/mapping.py`, tests

* **The unlabeled combo.** Required rows show an empty, disabled-looking combo; optional rows
  show "Continue without". Replace the combo with a labelled control that appears only when the
  row has no asset: "No asset: ○ Use a placeholder ○ Continue without" (required rows offer only
  the placeholder). Assigned rows show nothing there.
* **Thumbnails** at 48 px with a checkerboard behind transparency. For tile sheets show the
  first 3 × 3 non-empty cells instead of a scaled-down whole sheet (the GROUND thumbnail is
  blank today because the generated A2 atlas is mostly transparent at that scale).
* **Names.** Show the file name and pack ("meadow_a2.png · sample_pack") with the asset id in
  the tooltip, not `generated.sample_pack_tilesets_meadow_a2_b0`.
* **Grouping** with headers: *World* (ground, wall, building), *Characters* (player, NPC,
  enemy, portrait), *Things* (item/chest), *Interface* (UI), *Sound* (T11.20).
* Each row gets a one-line "used for" text from `requirements.REQUIRED_BY` and a **Clear**
  action beside **Choose…**.
* A summary line at the top: "2 required roles assigned, 6 of 9 optional roles assigned".

---

## T11.16 — Options page: grouped, explained features

**Depends on:** nothing
**Files:** `rpggen/core/options.py`, `rpggen/gui/pages/options_page.py`, tests

Eleven checkboxes in one column, no explanations; "Navigation" shows as a half-filled box.

* `options.FEATURE_INFO`: for each key in `config.FEATURE_KEYS` a group, a label and one
  sentence. Groups: **World** (tilesets, collision, terrain, animations, navigation),
  **Game systems** (save, dialogue, combat, demo), **Tools** (editor_tools, debug_tools). A test
  asserts every feature key has an entry.
* Each feature is a row: checkbox, label, grey description. Example: "Navigation: adds a
  navigation layer to the TileSet so enemies can path around walls. Off by default: enemies
  walk straight at the player."
* The checkboxes are plain two-state boxes (fix whatever makes Navigation render as partially
  checked; no feature is tri-state).
* A feature disabled by a dependency shows "Needs: Dialogue, Combat, Save" inline, not only in a
  tooltip.
* Two-column layout at widths ≥ 1100 so the page fits without scrolling: features left, screen
  and layers right.
* **Advanced** becomes a real collapsible section with a ▸/▾ arrow. The binding table's cells
  get key-capture: double-click, "Press a key…", instead of typing `W, Up`; typing still works.
* **Reset to defaults** per section.

---

## T11.17 — Option presets

**Depends on:** T11.09, T11.16
**Files:** `rpggen/core/options.py`, `rpggen/gui/pages/options_page.py`, tests

* A preset is the option part of a config: `features`, `resolution`, `window_size`,
  `map_layers`, `input`, `validation`, `starter_map` (T11.25). Never packs, name, seed or
  `starter`.
* `options.to_preset(cfg) -> dict` and `options.apply_preset(cfg, preset) -> GeneratorConfig`
  (pure; unknown keys ignored; the result is checked with `config_errors`).
* Options page header: **Preset ▾** (Defaults, the saved presets), **Save as preset…**,
  **Manage…** (rename, delete). Stored in `AppSettings.option_presets`.
* Applying a preset whose `input` belongs to the other archetype keeps the current archetype's
  bindings (same rule the Archetype page uses when it switches the input map).
* CLI: `rpggen-cli generate --preset NAME`.

---

## T11.18 — Generate and Results pages

**Depends on:** T11.09 (timings), T11.27 (preview image)
**Files:** `rpggen/gui/pages/generate_page.py`, `rpggen/gui/pages/results_page.py`, `rpggen/core/orchestrator.py`, tests

**Generate**

* Elapsed time, ticking each second, and a duration beside each finished phase.
* An estimate: `orchestrator` records per-phase seconds in `RunResult.timings` (not in any file
  that must be deterministic). The page keeps the last run's timings in app settings and shows
  "about 40 s left" from them; with no history it shows nothing rather than a guess.
* The phase names get plain labels ("Importing assets into Godot", "Playing the game to test
  it") with the internal name in the tooltip.
* The log is collapsed by default behind **Show details**; it opens by itself on failure.
* Windows taskbar progress when available; a system notification when the run ends while the
  window is not active.

**Results (success)**

* The counts become a compact strip; the page leads with the **map preview** (T11.27) and a
  primary **Open in Godot** button.
* A **What next** checklist with the real paths: "Press F5 to play", "Paint on
  `game/maps/starter_map.tscn`", "Drag objects from the RPG Project Tools dock", "Edit items in
  `game/data/items/`", "Read `README.md` in the project". Each line that names a file has a
  "Show" link.
* The warnings list groups by severity and shows the fix text inline (today it needs a click on
  each row).
* **Generate another** (back to Welcome) and **Change options and regenerate** (to Options,
  with `regenerating` set).

**Results (failure)**

* Lead with one sentence in plain words for the failing phase, then the issue list, then the
  buttons. For `ENV-*` failures, a button that goes back to the Project page.

---

## T11.19 — Archetype cards, light theme, tooltips, accessibility

**Depends on:** T11.09
**Files:** `rpggen/gui/pages/archetype_page.py`, `rpggen/gui/style.qss`, `rpggen/gui/style_light.qss` (new), `rpggen/gui/app.py`, `rpggen/gui/widgets/asset_grid.py`, `tools/make_doc_screenshots.py`, tests

* **Archetype cards.** The cards fill a quarter of the page and their lower half is empty. Make
  them fill the page side by side; under the flow diagram add a mock screen drawn with
  `QPainter` (turn-based: two battlers, a command box, HP rows; action: a room, a swing arc, a
  HUD bar), a bullet list of what is generated, and the controls. Below both: "You can generate
  the other kind later into a new project; saving, dialogue, inventory and menus are the same."
  The selected card gets a clear border and a check mark.
* **Light theme.** `style_light.qss` mirrors `style.qss`; `app.create_app` loads the one named
  in app settings; View → Theme switches at once. The status colours stay the same in both and
  stay checked by the existing test; add a contrast test (each status colour against both
  backgrounds meets 3:1).
* **Tooltips.** Only 9 `setToolTip` calls exist. Every button, combo and check box that is not
  self-explanatory gets one. A test walks each page's widgets and fails for an interactive
  widget without a tooltip, an accessible name or a visible label buddy.
* **Keyboard.** Tab order is set explicitly on every page; every button has a mnemonic where
  the platform shows them; Alt+N / Alt+B for Next / Back.
* **Status is not colour-only.** The grid's coloured edge is paired with a small corner glyph
  (✔ confirmed, ? needs review, ! conflict, ∅ missing), so the audit is usable with a colour
  vision deficiency.
* **High DPI.** Check the pages at 150% and 200% scale (`QT_SCALE_FACTOR`); thumbnails and the
  flow diagrams must use device-pixel-ratio-aware pixmaps.

---

# Part C — The generated game

## T11.20 — Audio: map music and sound effects

**Depends on:** T11.03
**Files:**
*Python:* `rpggen/core/requirements.py`, `rpggen/core/mapping.py`, `rpggen/core/classifier.py`, `rpggen/core/config.py`, `rpggen/schema/config.schema.json`, `docs/spec/02_SCHEMAS.md`, `rpggen/gui/pages/mapping_page.py`, `rpggen/gui/widgets/audio_preview.py` (new), `tools/build_sample_pack.py`, `tools/make_synthetic_packs.py`, `03_ERROR_CODES.md`
*Godot:* `addons/rpg_runtime/audio/audio_service.gd`, `addons/rpg_runtime/audio/sound_bank.gd` (new), `addons/rpg_runtime/world/scene_router.gd`, `addons/rpg_runtime/world/map_root.gd`, `addons/rpg_runtime/ui/menu_util.gd`, `builder/recipes/audio_bus_recipe.gd`, `builder/recipes/starter_map_recipe.gd`, `builder/recipes/interior_recipe.gd`, `builder/recipes/turn_based/battle_scene_recipe.gd`, `builder/smoke/smoke_steps_m6.gd`, tests

This is the largest gap in the result. The pieces exist and are not connected: audio files are
classified (`AUDIO_MUSIC` / `AUDIO_SFX`), `audio_bus_recipe` writes `rpggen/audio_index.json`,
`RpgAudio` can crossfade music and play effects, `RpgMapRoot` and `RpgBattleScene` both have a
`music_asset_id` property. But no recipe sets either property, nothing calls `play_sfx` or
`play_ui`, and the Mapping page has no audio rows (`mapping._usable` requires `kind == "image"`).

### 1. Sound slots (core)

A fixed list of slots, each filled by one audio asset or left empty:

| Slot key | Kind | Default match (file-name tokens, first hit wins) |
|----------|------|---------------------------------------------------|
| `music_map` | music | town, village, overworld, field, map, theme; else the longest music track |
| `music_battle` | music | battle, fight, combat, boss |
| `music_title` | music | title, menu, intro; else same as `music_map` |
| `sfx_ui_move` | sfx | cursor, move, select, tick, hover |
| `sfx_ui_confirm` | sfx | confirm, accept, ok, click |
| `sfx_ui_cancel` | sfx | cancel, back, close |
| `sfx_hit` | sfx | hit, hurt, damage, impact, slash |
| `sfx_attack` | sfx | attack, swing, sword, whoosh |
| `sfx_pickup` | sfx | pickup, coin, item, collect |
| `sfx_chest` | sfx | chest, open, unlock |
| `sfx_door` | sfx | door, enter, stairs |
| `sfx_step` | sfx | step, footstep, walk |
| `sfx_save` | sfx | save |
| `sfx_levelup` | sfx | levelup, level, fanfare, victory |

* `rpggen/core/sound_slots.py`: the table, `default_sounds(catalog) -> dict[str, str]`,
  `resolve_sounds(catalog, current)` (drop stale ids, fill gaps), the same shape as
  `mapping.default_starter` / `resolve_starter`.
* Config: a new optional top-level key `sounds: {slot: asset_id}`; schema entry with the slot
  names as properties and `additionalProperties: false`; omitted from `to_json` when empty.
  Document in `02_SCHEMAS.md`.
* `requirements.check`: `ASSET-026` (I) "No music was found in the packs: the game will be
  silent." and `ASSET-027` (I) "No sound effects were found in the packs." Info only; audio is
  never required, and there are no audio placeholders.
* `classifier`: add the slot tokens to the music/SFX decision only where they are unambiguous
  (`bgm`, `theme`, `song` already are); do not change roles of non-audio assets.

### 2. Mapping page

* A **Sound** group (T11.15) with one row per slot, collapsed to "3 music tracks, 14 sound
  effects assigned" with an **Edit…** expander, because 14 rows would drown the page.
* The picker lists audio assets of the right kind with name, pack and duration. A **▶** button
  previews: `widgets/audio_preview.py` uses `QtMultimedia` (`QMediaPlayer` + `QAudioOutput`),
  created lazily, and the button is hidden when the module or an output device is missing.
  PyInstaller currently excludes unused Qt modules: **add QtMultimedia back** to
  `packaging/rpggen.spec` and note the size change in the task log.
* Assigning sets `config.sounds[slot]`; it does not change the asset's role.

### 3. Builder

* `audio_bus_recipe` (v2) also writes `res://rpggen/sound_bank.json`: `{slot: res-path}` for the
  configured slots whose asset is still active. `input_hash` includes `config.sounds`.
* `starter_map_recipe` sets `music_asset_id` on the map root from `music_map`;
  `interior_recipe` leaves it empty (the router keeps the current track when the next map has
  none); `battle_scene_recipe` sets `music_battle`. The starter map is `user_seed`, so this
  applies to new projects; for an existing map the README says "set **Music Asset Id** on the
  map root".
* The title screen's music is set by `ui_recipes` on the title scene (a `music_asset_id` meta
  read by `title_screen.gd`).

### 4. Runtime

* `sound_bank.gd` (`RpgSoundBank`, a `RefCounted` owned by `RpgAudio`): loads
  `sound_bank.json` once; `stream(slot) -> AudioStream` (cached; `null` when unset).
* `RpgAudio` gains `play(slot: StringName)` (SFX bus), `play_ui_slot(slot)` (UI bus) and
  `play_music_slot(slot)`. All are silent no-ops for an unset slot: no warning, so a pack
  without audio produces a clean log.
* `RpgAudio._ready` connects to `Events` (through `RpgUtil`, as other services do):
  `item_added` → `sfx_pickup`; `player_damaged` → `sfx_hit`; `level_up` → `sfx_levelup`;
  `game_saved` → `sfx_save`. Add two events, `chest_opened(entity_id)` and
  `door_used(entity_id)`, emitted by `chest.gd` and `door.gd`, mapped to `sfx_chest` /
  `sfx_door`. Add `attack_started(actor)` from `player_combat.gd` and from
  `battle_scene.gd`'s hit feedback → `sfx_attack`.
* **Map music:** `scene_router.gd`, after a map is entered (where it emits `map_entered`),
  reads the map root's `music_asset_id`; non-empty and different from
  `audio.current_music_id` → `audio.play_music(id)`.
* **UI sounds:** `menu_util.wire_vertical` / `wire_grid` (already called for every menu)
  connect each control's `focus_entered` → `sfx_ui_move` and `pressed` → `sfx_ui_confirm`,
  once per control (guard with a meta flag). The `cancel` action in `ui_controller.gd` →
  `sfx_ui_cancel`. The first focus after a menu opens is muted so opening a menu does not tick.
* **Footsteps:** `RpgMovement` emits nothing today. Add a `step_interval_px` (default one tile)
  counter on the player only; each interval → `sfx_step` at −6 dB with ±5% pitch variation. If a
  tile has `footstep` custom data (the Tiled adapter already carries it) and a slot
  `sfx_step_<value>` exists in the bank, prefer it.
* Music keeps playing through the pause menu; the Settings sliders already drive the buses.

### 5. Sample pack and tests

* `tools/build_sample_pack.py` synthesizes CC0 audio with numpy and `wave`: a 24 s looping
  two-voice tune (`music/town_theme.wav`), a 16 s battle loop, and eight short effects (blip,
  confirm, cancel, hit, swing, coin, chest, step). WAV only, so no encoder is needed and the
  bytes are deterministic. Record them in `sample_pack/SOURCES.md` and the sample profile. Keep
  the pack under 3 MB (mono, 22050 Hz, 16-bit).
* Synthetic pack `audio_basic` with `expected.json` (roles and slot defaults).
* Unit (Python): slot defaults for name patterns; stale ids dropped; schema round trip.
* Unit (GDScript): the sound bank; `play` on an unset slot is silent and logs nothing; event →
  slot wiring with a fake audio node; the router switches music only when the id changes.
* Smoke (`smoke_steps_m6.gd`): after `title_new_game`, when `music_map` is configured,
  `audio.current_music_id` equals it; after `chest_open`, when `sfx_chest` is configured,
  `sfx_busy_count()` rose during the step. Both steps pass with a note when the slot is unset.
* `validate.gd`: `VAL-020` (E) "Sound slot {slot} points at {path}, which does not load."

---

## T11.21 — Game-over screen

**Depends on:** nothing
**Files:** `addons/rpg_runtime/ui/game_over.gd` (new), `builder/recipes/ui_recipes.gd`, `addons/rpg_runtime/combat/defeat_policy.gd` (new), `addons/rpg_runtime/archetypes/arpg/arpg_mode.gd`, `addons/rpg_runtime/archetypes/turn_based/turn_based_mode.gd`, `addons/rpg_runtime/ui/strings.gd`, smoke steps, tests

On defeat the game silently loads the newest save or respawns the player. There is no moment
that says "you lost".

* **Share the policy.** `apply_defeat` and `latest_save_slot` are duplicated in the two mode
  scripts (noted in M9 decision 8). Move them to `combat/defeat_policy.gd` (`RpgDefeatPolicy`,
  static functions), which is shared runtime and may be used by both archetypes. Behavior is
  unchanged: HP at least 1; newest save when one exists, else default spawn with full HP.
* `ui_recipes` builds `game_over.tscn`: a dimmed full-screen panel, the title "You were
  defeated", and buttons **Continue from last save** (hidden when there is none), **Try again
  from the start of the map**, **Quit to title**. Focus wiring through `menu_util`; it is walked
  by VAL-011 like every menu.
* The modes call `RpgDefeatPolicy.show_game_over(router)`, which pauses the tree, shows the
  scene and applies the chosen option. `auto_choose` / smoke mode skips the screen and applies
  the default option at once, so existing smoke steps keep their timing.
* Strings: `UI_GAME_OVER_TITLE`, `UI_GAME_OVER_CONTINUE`, `UI_GAME_OVER_RETRY`,
  `UI_GAME_OVER_QUIT` in `strings.gd` and the seeded CSV (new keys are appended for existing
  projects by `translations_recipe`; check that it merges and does not overwrite).
* Smoke: `defeat_policy` steps in both archetypes additionally assert, in one non-auto run, that
  the screen appears and that confirming the focused button resumes play.

---

## T11.22 — Autosave

**Depends on:** nothing
**Files:** `addons/rpg_runtime/core/save_manager.gd`, `addons/rpg_runtime/ui/save_load_menu.gd`, `addons/rpg_runtime/core/settings.gd`, `addons/rpg_runtime/ui/settings_menu.gd`, `builder/recipes/ui_recipes.gd`, `addons/rpg_runtime/world/scene_router.gd`, tests

* `SaveManager`: an extra slot `AUTOSAVE_SLOT := 0` beside the manual slots 1–3 (check
  `_slot_path` and `SLOTS` loops; the manual numbering must not shift, so existing saves stay
  valid; `SAVE_VERSION` stays 1). `autosave() -> bool` uses the normal `save` path (tmp, verify,
  backup, rename) and emits `game_saved` with the slot.
* When: after `map_entered` (deferred by one frame so the map's persistent entities are in
  place), and after a battle ends in victory. Never while the router is busy, during combat, in
  a dialogue, or within 10 s of the previous autosave.
* The save/load menu lists **Autosave** first, load-only (it cannot be chosen as a save target),
  with the same header line (map, level, play time).
* `latest_save_slot` already picks the newest by time, so Continue and the game-over screen pick
  up an autosave naturally; verify with a test.
* Settings menu: **Autosave: On / Off** (default on), stored by `RpgSettings`.
* A small "Saved" toast through `Events.notify`, at most once per autosave.
* Smoke: entering the house and returning leaves an autosave whose header names the starter map;
  with the setting off none is written. Smoke saves already go to `user://smoke_saves`.

---

## T11.23 — A second outdoor map

**Depends on:** T11.20 (music id), T11.25 (shares the map-building helpers)
**Files:** `builder/recipes/starter_map_recipe.gd`, `builder/lib/map_build.gd` (new, extracted), `builder/recipes/second_map_recipe.gd` (new), `builder/build.gd`, `addons/rpg_project_tools/dock/demo_tools.gd`, `builder/smoke/smoke_steps_m4.gd`, `project_files/README.template.md`, tests

The starter project shows a map and an interior. A second outdoor area shows that the game is
more than one screen, and gives the user a worked example of connecting maps.

* Extract the painting helpers of `starter_map_recipe.gd` (`_paint_ground`, `_paint_walls`,
  `_paint_path`, `_place_decorations`, layer creation) into `builder/lib/map_build.gd` so both
  recipes use one implementation.
* `second_map_recipe` → `game/maps/field_1.tscn` (`user_seed`, demo content): 32 × 20, the same
  TileSet, a different seed stream (`SeedUtil` with the label `field_1`), a second ground
  variant when the catalog has one, 2 enemies, 1 chest with a different item, no building.
* **Connection:** a gap in the starter map's east wall with an `RpgDoor`-style edge trigger
  (`starter_map_east_exit`) targeting `field_1` spawn `west_entry`, and the reverse. The path
  (ROAD tiles) is extended to the gap.
* Listed in `rpggen/demo_entities.json`; **Remove demo content** in the dock deletes the map
  when untouched (same ledger rule as `interior_1.tscn`) and closes the gap's door target.
* Behind `features.demo`; registered in `build.gd` `RECIPE_ORDER` after `starter_map_recipe`.
* Validation: `VAL-016` (door targets) already covers the new doors.
* Smoke (`smoke_steps_m4.gd`): `walk_to_field` and `return_from_field`; position and
  `GameState.current_map` are asserted.
* README: a short "How the maps are connected" section naming the two door nodes.

---

## T11.24 — Small runtime polish

**Depends on:** T11.20
**Files:** as named

Each is small; group them in one commit.

* **Interaction prompt.** When the player's interaction area overlaps an interactable, show a
  small "E" (the first key bound to `interact`, or the gamepad glyph name) above it.
  `actors/interaction.gd` + a scene built by `ui_recipes`.
* **Screen feedback.** ARPG: a 2-frame hit-stop and a brief camera shake on a landed heavy
  attack; a setting **Screen shake: On / Off**.
* **Title screen.** Shows the project name from `ProjectSettings` and the game version; Continue
  is focused when a save exists.
* **Pause menu.** Shows the current map name and play time.

---

## T11.25 — Starter map options

**Depends on:** nothing in Python; shares `map_build.gd` with T11.23
**Files:** `rpggen/core/config.py`, `rpggen/schema/config.schema.json`, `docs/spec/02_SCHEMAS.md`, `rpggen/core/options.py`, `rpggen/gui/pages/options_page.py`, `builder/recipes/starter_map_recipe.gd`, tests

The map is fixed: `MAP_SIZE := Vector2i(40, 24)`, one house at (8, 6), eight decorations, one
NPC, one chest, one enemy (two for ARPG), six ground patches (`starter_map_recipe.gd:28-37`).

New optional config key:

```json
"starter_map": {
  "size": [40, 24],          // tiles; each 24..96
  "buildings": 1,            // 0..4
  "npcs": 1,                 // 0..6
  "enemies": 1,              // 0..8   (arpg default 2)
  "chests": 1,               // 0..4
  "decorations": 8,          // 0..40
  "ground_patches": 6,       // 0..20
  "ground": ""               // asset id of the ground set; "" = starter.ground
}
```

* `GeneratorConfig.starter_map` with these defaults; omitted from JSON when equal to the
  defaults (the archetype's default enemy count included).
* **Recipe (v7).** Replace the constants with a layout function in `map_build.gd`:
  `plan(size, counts, seed) -> {buildings: [...], spawn, npcs, enemies, chests, decorations,
  path}`. Rules, in order: buildings on a coarse grid with 3 tiles of clearance and their door
  side free; the spawn in front of the first building's door (or the centre); a ROAD path from
  the spawn to each door; NPCs beside the path; chests against buildings or the border; enemies
  at least 8 tiles from the spawn; decorations anywhere left, never on a path, a door approach or
  within 1 tile of an entity. Everything comes from the seeded stream, so the same config gives
  the same map.
* **The defaults must reproduce today's map exactly** (same tiles, same positions, same entity
  ids), so existing goldens, smoke steps and the determinism test do not change. Achieve it by
  making the planner return the current constants when the options equal the defaults, and
  assert it with a test that compares `dump_map_cells.gd` output before and after.
* Extra entities get ids `starter_map_npc_002`, … and are added to `demo_entities.json`. Extra
  buildings share `interior_1` unless there are several interior-capable buildings; each door
  gets its own exit spawn.
* When a count cannot be placed (map too small), place what fits and report a warning with the
  number placed (reuse `ASSET-010`'s neighbour or add a build warning; do not fail).
* **Options page:** a "Starter map" group: size presets (Small 32×20, Medium 40×24, Large
  64×40, Custom), the counts as spin boxes, the ground set as a combo when the catalog has more
  than one GROUND asset. Disabled with an explanation when regenerating a project whose starter
  map exists ("The starter map already exists and is yours; these options apply to new
  projects").
* Smoke steps find entities by id and by the demo list, not by fixed tiles; check
  `smoke_steps_m1/m4/m6` for hard-coded positions and move them to `demo_entities.json` lookups.

Tests: property test over 200 random option sets: every entity is inside the map, nothing
overlaps, every door is reachable from the spawn (flood fill over non-blocked tiles); the
defaults equal the old map; integration: a Large map with 4 buildings generates, validates and
passes smoke.

---

## T11.26 — Map preview before generating

**Depends on:** T11.25
**Files:** `rpggen/core/map_preview.py` (new), `rpggen/gui/widgets/map_preview.py` (new), `rpggen/gui/pages/options_page.py`, tests

A picture of what the options will produce, with a **Reroll** button, before a minute is spent
generating.

* The layout must come from **one** implementation. The planner of T11.25 lives in GDScript, so
  port it to Python as `map_preview.plan(...)` and keep the two equal with a shared fixture, the
  way `status_cases.json` and `hash_vectors.json` already keep Python and GDScript in step:
  `godot_templates/tests/fixtures/map_plan_cases.json` holds 20 option sets with the expected
  plan, checked by a Python test and a GDScript test. That requires the planner to use only the
  shared deterministic RNG (`SeedUtil` / its Python twin) and integer arithmetic.
* `map_preview.render(plan, catalog, resolver, scale) -> PIL.Image`: ground tile repeated,
  patches, the wall border, buildings and decorations drawn from their sheet regions, and
  coloured markers with a legend for spawn, NPCs, enemies and chests. It is a preview, not a
  pixel-exact render: autotile terrain is drawn with the set's centre tile.
* Options page: the preview beside the Starter-map group, re-rendered (debounced 200 ms, in a
  `Worker`) when an option or the seed changes. **Reroll** picks a new seed and writes it to the
  Advanced seed field. Disabled, with the same explanation, when the starter map already exists.
* The preview states "Preview: the generated map can differ in tile details."

Tests: the fixture equality on both sides; rendering the sample pack's plan produces an image of
the expected size with non-background pixels at the building and marker positions.

---

## T11.27 — Picture of the generated map on the Results page

**Depends on:** T11.26 (renderer)
**Files:** `rpggen/core/orchestrator.py`, `rpggen/core/map_preview.py`, `rpggen/gui/pages/results_page.py`, `builder/tools/dump_map_cells.gd`, tests

The builds run with `--headless`, which has no renderer, so a viewport screenshot is not
available. Render the picture in Python from what was actually built:

* After the smoke phase, run the existing `builder/tools/dump_map_cells.gd` on
  `game/maps/starter_map.tscn` (extend its output with entity positions and scene paths) into
  `rpggen/results/starter_map_cells.json`.
* `map_preview.render_cells(cells, catalog, resolver)` draws the real cells (atlas coordinates
  → sheet regions) and the entities; saved to `rpggen/results/starter_map.png` (the folder is
  already git-ignored and outside the ledger, so determinism is unaffected).
* A failure here is a warning in the log, never a failed generation.
* Results page shows it (T11.18). Clicking opens it at full size.
* On regeneration the picture shows the user's current map, which is a pleasant confirmation
  that their work was kept.

---

# Part D — Documentation, test pass and gate

## T11.28 — Documentation and screenshots

**Depends on:** all of Parts A–C
**Files:** `docs/user_guide.md`, `README.md`, `docs/profiles.md`, `docs/release.md`, `tools/make_doc_screenshots.py`, `docs/images/`, `project_files/README*.md`, `addons/rpg_runtime/README.md`, `CHANGELOG`s, `tests/unit/test_release.py`

* Regenerate every screenshot with `tools/make_doc_screenshots.py`; add the welcome view, the
  map preview, the About dialog and the game-over screen.
* User guide: welcome view; Download Godot; audit queue and shortcuts; sound mapping; starter
  map options and preview; presets; Help menu; the three network actions.
* Generated README: audio slots and how to change them, the heavy attack, autosave, the second
  map, game over.
* `test_release.py`: the screenshot list matches the files referenced by the guide.
* Add a root `CHANGELOG.md` for the application (1.0.0).

---

## T11.29 — Manual test pass (human)

**Depends on:** T11.28
**Files:** `docs/coverage.md`, `docs/dev/implementation_notes.md`, `validation_runs/results.md`

Every item below was recorded as never exercised by a person. Do them on Godot **4.7.2**, on a
frozen build made with `python tools/package.py --smoke --godot <exe> --installer`. Record each
result in the notes file as pass/fail with the date; a failure becomes a fix or a ticket.

| # | Check | How |
|---|-------|-----|
| 1 | Editor dock placement | Open a generated project in the editor. Drag a building, a prop and an enemy from **RPG Project Tools** into the map: each lands on the right layer, snapped, Y-sorted, with an entity id where needed. Ctrl+Z removes it in one step. Double-click placement does the same. |
| 2 | Dock rebuild | Change an asset's collision in the dock inspector, press **Rebuild**: the subprocess runs, the dock rescans, the TileSet shows the change, and nothing in `game/` changed. |
| 3 | RPG Maker A2 | Run `python tools/debug_a2_sheet.py` on a real A2 sheet you own, then generate and paint with the terrain in the editor: corners and edges join correctly. If not, the quarter table in `terrain/rpgmaker_a2.py` is wrong; fix it against the sheet. |
| 4 | Installer | Run `rpggen-1.0.0-setup.exe` on a clean Windows account: installs without admin, Start-menu shortcut works, *Try the sample* succeeds, the uninstaller removes everything except the cache folder (decide and document whether it should). |
| 5 | Regeneration with the editor open | With the project open in Godot, regenerate: the REGEN-005 dialog appears. Close the editor, Retry, reopen: the painted map is intact. |
| 6 | Gamepad | Play both archetypes with a controller: menus, a full battle (attack, item, run), ARPG attack, heavy attack, dodge, quick item, pause. |
| 7 | Layers and Y-sort | Paint on every layer; the player walks behind tree tops and in front of trunks; the house is enterable. |
| 8 | Audio | With the sample pack: title music, map music, battle music and back, UI ticks, chest, footsteps; the volume sliders work; a pack without audio is silent and logs no warnings. |
| 9 | Cancel | Cancel during import and during the smoke test: the page returns within a few seconds and no Godot process is left. |
| 10 | Download Godot | On a machine without Godot: the welcome view offers the download, it completes, and generation works with the downloaded copy. |
| 11 | Find profile online | With the registry served from the repository: the sample pack finds its profile; with the network off, the message is clear and the window stays responsive. |
| 12 | Display scaling | 100%, 150% and 200%; dark and light themes; window at 1000 × 700. |
| 13 | Held-out packs | The five unseen packs of `docs/coverage.md` with `tools/held_out_run.py`, both archetypes; fill in time to first paint and audit edits. All 10 runs pass; median time to first paint under 10 minutes. |
| 14 | Large audit | Audit a real 300–500 asset pack with the new queue; record the time (target under 15 minutes). |
| 15 | SmartScreen | Take the screenshot the README promises, from the unsigned installer. |

---

## T11.30 — Gate (M11)

The milestone is done when:

1. CI is green on `main` for Windows and Ubuntu, including the perf job, on Godot 4.7.2.
2. `tests/unit/test_release.py` passes: one version everywhere, no dead repository URLs, no
   GPL dependency, every doc link resolves.
3. No network call happens without a click. A test runs the whole wizard flow on the sample
   pack with `socket.socket` patched to raise, and it passes.
4. A no-op regeneration of a project generated after M11 still changes no file, and a rebuild
   leaves `game/` and `generated/` byte-identical (existing tests, re-run on the new recipes).
5. A project generated **before** M11 regenerates without error and keeps its starter map; the
   new demo content (second map, music id) is not forced into the user's map.
6. Every row of T11.29 is recorded as passed, or has a linked ticket that is agreed not to block.
7. `docs/coverage.md` has its two tables filled.

Then follow `docs/release.md`: tag `v1.0.0`.

---

# Part E — Deferred to 1.1

Recorded so they are not lost; none is needed for 1.0, and each is a milestone-sized piece of
work with its own save-format implications.

| Feature | What exists already | What it needs |
|---------|---------------------|---------------|
| **Equipment** | `RpgItemDefinition.modifiers` (`[{stat, add, mul}]`) and the `WEAPON` / `ARMOR` / `ACCESSORY` categories | Equipment slots on the actor, stat recomputation in `RpgStatsComponent`, an Equip screen, save format v2 with a migration, starting equipment in `new_game.tres`, weapon-driven attack values in both archetypes |
| **Shops** | `RpgItemDefinition.value`, gold in `GameState` | A shop resource (stock, price factors), a buy/sell menu, an NPC interaction that opens it, a demo shopkeeper |
| **Quests** | The `QUEST` item category, flags in `GameState`, `dialogue_event` | Quest resources (stages, conditions through `RpgCondition`), a quest log menu, dialogue actions to start and advance, a demo quest ("bring the villager a potion") |
| **Skills and status effects** | A `skill` battle command script | Skill resources with costs, an MP stat, status effects with durations in both combat modes |
| **Party members** | `RpgBattleActor` already handles a list per side | Party storage, followers on the map, a party menu |
| **More archetypes** | The archetype folder structure and the filtered install | Tactics grid or platformer; each is its own milestone |
| **In-app audit of audio** | T11.20's preview widget | Waveform thumbnails, loop-point editing |
| **Localization of the wizard** | Every string already goes through `self.tr` | `.ts` files, a language menu |
| **macOS and Linux builds** | CI already runs on Ubuntu | Packaging, signing/notarization, the Godot download for each platform |
