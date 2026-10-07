# M12 — Review Follow-ups: Fixes, Engineering, UX and Features for 1.0

**Goal:** act on the code review of 2026-10-07 and finish 1.0. Part A fixes what is broken or
misleading as built (15 findings, most of them reproduced). Part B makes the generator faster,
safer to release and easier to test. Part C improves the wizard and the generated game where a user
notices it. Part D adds the twenty features from the review. Part E updates the documentation and
holds the 1.0 gate. **Everything in this milestone lands before the first tag.**

This file follows the format of M01–M11. It was written against commit `e8bab6d`. File and line
references are to that commit. The appendix maps every item of the review to the card that carries
it, and lists where this plan corrects the review.

## Ground rules for this milestone

* The conventions in `01_CONVENTIONS.md` apply unchanged: core logic stays out of the GUI, pages
  only edit `WizardState`, every edit is undoable, generated output is deterministic, `.tscn`,
  `.tres` and `project.godot` are never written by hand, and every Godot API is verified
  (`docs/godot_api_verified.md` or a probe) before it is used.
* **Versions.** Nothing has been tagged yet (`git tag` is empty at `e8bab6d`), and every card here
  lands before the first tag. The app, the runtime and `config_version` keep their numbers (1.0.0,
  1.0.0, 1). Runtime changes go under the existing `1.0.0` heading of
  `godot_templates/addons/rpg_runtime/CHANGELOG.md`.
* **Config schema changes are additive and optional** (the M11 rule). Every new key has a default,
  `to_json` omits a key that holds its default, and existing goldens and the determinism test do
  not move.
* **Save format.** `save_version` stays 1. No save has been released, so new save data is added as
  optional keys that `GameState.from_dict` defaults when they are missing, as `party` and `quests`
  already are (`game_state.gd:142-153`). Header additions follow the same rule.
* **New error codes** go into `03_ERROR_CODES.md` first, then run
  `python tools/gen_error_codes.py`. Codes reserved by this milestone: `ARCH-009`, `BUILD-005`,
  `VAL-021`, `REGEN-007`, `REGEN-008`, `TILE-009`, `ADAPT-004` and `ASSET-028`.
* **Recipe changes bump `RECIPE_VERSION`.** The starter map and everything under `game/` are
  `user_seed`: they affect new projects only. Say so in the generated README where it matters.
* **Smoke steps.** Every new smoke step is added to the lists the integration tests assert
  (`M6_STEPS`, `M7_STEPS`, `M9_STEPS` and the list in `test_generate_basic16.py`).
* **Demo content stays small.** A feature appears in the demo only when its card says so, and only
  in new projects.
* **Layout.** Once T12.16 exists, every card that changes a wizard page must keep it green at the
  minimum window size in both themes.
* **Dependencies.** The only new runtime dependency allowed is `psutil` (T12.05). Record it in
  `THIRD_PARTY_NOTICES.md` and `packaging/rpggen.spec`. Any other new dependency needs a decision
  note in `docs/dev/implementation_notes.md`.
* After any change to detection or the sample pack, run `python -m rpggen.dev update-goldens` and
  `python tools/build_sample_pack.py`, and review the diff.

## Order of work

| Step | Tasks | Why this order |
|------|-------|----------------|
| 1 | T12.16, T12.01, T12.14 | The test that catches squeezed layouts first, then the two pages it catches |
| 2 | T12.02 – T12.13, T12.15 | The remaining fixes; independent except T12.11 after T12.10 |
| 3 | T12.17 – T12.24, T12.26 – T12.29 | Engineering; T12.17 after T12.06, T12.18/T12.21/T12.24 after T12.10 |
| 4 | T12.25 | Before the Project and Options cards of steps 5 and 6, so those pages are rewritten once |
| 5 | T12.30 – T12.44 | Wizard and game UX |
| 6 | T12.45 – T12.64 | The features (suggested order below) |
| 7 | T12.65 – T12.66 | Docs, screenshots and the 1.0 gate, then tag `v1.0.0` |

Tasks inside a step are independent unless **Depends on** says otherwise.

**Suggested order inside step 6**, most value per risk first:

1. T12.51 (credits: licence compliance).
2. T12.50 and T12.49 (frame sequences and imported maps). They change detection, so they must land
   before the gate's held-out coverage runs.
3. T12.45 → T12.46 → T12.48 → T12.47 (equipment, shops, quests, party: they share the inventory,
   status and save code).
4. T12.52 (export presets) and T12.63 (Linux and macOS packages), which both need CI runners.
5. T12.58 (conflict resolver).
6. Then the rest.

## Index

Sizes are rough: **S** under a day, **M** 1–3 days, **L** 3–7 days, **XL** more than a week.

| Card | Title | Size | Depends on |
|------|-------|:----:|------------|
| T12.01 | Mapping page scrolls | S | — |
| T12.02 | Hash each pack once, never on the GUI thread | M | — |
| T12.03 | Derive the base tile size from the packs | M | — |
| T12.04 | The CLI rejects unknown arguments | S | — |
| T12.05 | Editor-open detection: exact paths, no PowerShell | S | — |
| T12.06 | Analysis: real progress and a Cancel that cancels | M | — |
| T12.07 | Report skipped checks as skipped | M | — |
| T12.08 | Generated game: safe backup rotation, translated messages | S | — |
| T12.09 | Archive extraction: links, collisions, one size budget | M | — |
| T12.10 | Config, data and cache folders; bounded caches | L | — |
| T12.11 | One settings store; recent projects survive unplugged drives | M | T12.10 |
| T12.12 | Git: commit only what rpggen wrote; pack-art choice | M | — |
| T12.13 | No shared mutable network timeouts | S | — |
| T12.14 | Audit page layout | S | T12.16 |
| T12.15 | Release hygiene and the 1.0 gate | M | — |
| T12.16 | Layout regression test | M | — |
| T12.17 | Parallel image analysis | M | T12.06 |
| T12.18 | Folder-pack inventory cache | S | T12.10 |
| T12.19 | Live Godot output and build progress | M | — |
| T12.20 | Lean failed-run folders | S | — |
| T12.21 | Godot download: pinned checksum, resume, retry | M | T12.10 |
| T12.22 | PySide6 version matrix | S | — |
| T12.23 | A report for unexpected errors | S | — |
| T12.24 | One log location, rotated, with run ids | S | T12.10 |
| T12.25 | View-models for the Project and Options pages | L | T12.02, T12.03 |
| T12.26 | A real-pack accuracy corpus without art | M | — |
| T12.27 | Performance trends | S | — |
| T12.28 | Scriptable CLI: `--json`, exit codes, `--dry-run` | M | T12.04, T12.07, T12.23 |
| T12.29 | Strict GDScript in the template project | M | — |
| T12.30 | Quit is not Cancel; fit laptop screens | S | T12.16 |
| T12.31 | Audit cards: audio, fonts, role badges, playback | M | T12.16 |
| T12.32 | Audit filter bar that fits | S | T12.14 |
| T12.33 | Project page: pack cards | M | T12.25 |
| T12.34 | Archetype cards drawn with the pack's art | M | — |
| T12.35 | Sidebar: step status and forward jumps | M | — |
| T12.36 | Mapping: inline candidates | S | T12.01 |
| T12.37 | Options: summary panel | S | T12.25 |
| T12.38 | Map preview legend as widgets | S | — |
| T12.39 | Results: Play, Open starter map, grouped warnings | M | T12.07 |
| T12.40 | Regeneration preview before promotion | M | — |
| T12.41 | One-click fixes for common failures | M | T12.39 |
| T12.42 | Follow the system theme; theme-aware canvases | S | — |
| T12.43 | Audit change history | M | — |
| T12.44 | Generated game: save and load screens | M | T12.08 |
| T12.45 | Equipment | L | — |
| T12.46 | Shops | M | T12.45 |
| T12.47 | Party members (turn-based) | L | T12.45 |
| T12.48 | Quest journal | M | — |
| T12.49 | Import Tiled and LDtk maps | XL | T12.25 |
| T12.50 | Frame sequences and more actions | L | — |
| T12.51 | Credits screen from pack licences | M | — |
| T12.52 | Web, Linux and macOS export presets | M | T12.07, T12.25 |
| T12.53 | Random-encounter zones | M | — |
| T12.54 | Event sequencer | L | — |
| T12.55 | Input glyphs | M | — |
| T12.56 | Languages: in-game picker, wizard translations | L | — |
| T12.57 | Contact sheet export | S | — |
| T12.58 | Conflict resolver for `.rpggen-new` files | L | T12.40 |
| T12.59 | Learn from my corrections | L | — |
| T12.60 | Custom recipe hook | M | — |
| T12.61 | Dialogue authoring dock | L | — |
| T12.62 | Lighting and day/night | M | — |
| T12.63 | Linux and macOS app packages | L | T12.10, T12.21 |
| T12.64 | Minimap and world map | L | — |
| T12.65 | Documentation, screenshots and changelogs | M | Parts A–D |
| T12.66 | Gate (1.0.0) | M | T12.65, T10.10 |

---

# Part A — Fix before release

## T12.01 — Mapping page scrolls

**Depends on:** nothing
**Files:** `rpggen/gui/pages/mapping_page.py`, `tests/gui/test_mapping_page.py`

The role rows sit in a plain `QVBoxLayout` with no scroll area (`mapping_page.py:217-229`). This
was measured offscreen with the sample pack at the default window size of 1100×720:

* The page's minimum size hint is 876 px, but it is given 653 px.
* Every `RoleRowWidget` is squeezed to 47 px of its 72 px minimum.
* The Choose… and Clear buttons end up 11 px tall.

The user guide shows the defect (`docs/images/wizard_mapping.png`). The action-RPG archetype has
more roles, so it is worse there.

* Keep the intro line and `summary_label` at the top. Put `rows_box` and `sound_section` into a
  frameless `QScrollArea` with `setWidgetResizable(True)`, as `options_page.py:225` does.
* Rows get a vertical size policy of `Minimum`, so they never shrink below their size hint.
* When the wizard asks the page to reveal what is missing (`reveal_missing`), scroll the first
  incomplete required row into view.

**Tests**
* At the window minimum (1000×640, or the T12.30 value once that card is done), every visible
  `RoleRowWidget.height()` is at least its `minimumSizeHint().height()`. Every Choose… button is at
  least its `sizeHint().height()`.
* `reveal_missing` makes the first missing row visible in the viewport.

**Done when**
* Both tests pass for both archetypes, and T12.16 passes on Mapping.

---

## T12.02 — Hash each pack once, never on the GUI thread

**Depends on:** nothing
**Files:** `rpggen/core/config.py`, `rpggen/core/staging.py`, `rpggen/gui/pages/project_page.py`, `tests/unit/test_config.py`, `tests/unit/test_staging_regen.py`, `tests/gui/test_project_page.py`

* `pack_ref_from_source` hashes an archive with `hashlib.sha256(source.read_bytes())`
  (`config.py:233`). That loads the whole archive into memory: a 3 GB zip means 3 GB of RAM.
* `folder_sha256` (`config.py:212`) reads every file of a folder pack again.
* Both are called on the GUI thread from `project_page.py:937` and `:945`, right after the
  analysis worker computed the same values:
  * `OpenedPack.source_sha256` for archives.
  * `Inventory.source_sha256` for folders.
* `staging._place` (`staging.py:149`) hashes both source and destination of every pack file again.
* `folder_sha256` counts `Thumbs.db` and `.DS_Store`, while the inventory excludes them, so one
  folder has two identities.

**Spec**
* `pack_ref_from_source(source, pack_id, known_sha256: str | None = None)` uses the known hash
  when given. Otherwise it streams archives with `archive.sha256_file`.
* The folder identity becomes `inventory.hash_file_list` over non-junk files, the same as
  `inventory.py:207`, so the config and the catalog agree.
* `ProjectPage._default_config` and `_config_with_packs` pass the hash from `state.opened_packs`
  or `state.inventories`. No pack file is read on the GUI thread.
* `install_pack` passes `InventoryFile.sha256` to `_place(src, dst, src_hash)`. Only an existing
  `dst` is hashed.
* Nothing compares `PackRef.source_sha256` today, so the folder-identity change needs no migration.
  Note it in `implementation_notes.md`.

**Tests**
* With a known hash, `pack_ref_from_source` never opens the file (patch `open` to raise).
* A 50 MB generated zip is hashed with a `tracemalloc` peak under 8 MB.
* Folder identity ignores `Thumbs.db`.
* Building the default config after analysis computes no SHA-256 on the GUI thread (patch
  `hashlib.sha256` to record its thread).
* `_place` hashes the source zero times when given its hash.

**Done when**
* All tests pass, and generating a 1 GB folder pack hashes each file at most once per run.

---

## T12.03 — Derive the base tile size from the packs

**Depends on:** nothing
**Files:** `rpggen/core/catalog.py`, `rpggen/core/orchestrator.py`, `rpggen/cli.py`, `rpggen/gui/pages/project_page.py`, `rpggen/gui/pages/options_page.py`, `rpggen/core/options.py`, `tests/unit/test_assemble.py`, `tests/unit/test_cli.py` (new), `tests/gui/test_options_page.py`

`base_tile_size` is always 16. Nothing sets it from the packs:

* `config.py:104` sets the default, and `project_page.py:948` uses it.
* `orchestrator.default_config_for_pack` passes `tile_size=16` (`orchestrator.py:651`).
* The CLI has no flag for it.

Effects:

* The Options hint (`options_page.py:599`) says "≈ 40 × 22.5 tiles on screen" for a 48 px pack at
  640×360. The truth is ≈ 13.3 × 7.5.
* Placeholders are sized for 16 px tiles (`placeholders.py:23`).
* The builder's fallbacks use 16 when a project has no tile set (`actor_recipes.gd:60` and five
  other recipes).

**Spec**
* `catalog.dominant_tile_size(catalog) -> int | None` returns:
  * the cell size of the `overworld` tile set definition;
  * else the definition with the most tiles, with ties going to the smaller size;
  * `None` when there are no tile sets.
* Wizard: when `ProjectPage` creates a default config, set `base_tile_size` from it (16 when
  `None`). A regeneration keeps the stored value.
* CLI: add `--tile-size N` (8–256). Without it, a `--pack` run derives the size in
  `phase_catalog`, before placeholders are created. The new `_State.derive_tile_size` is set only
  by the `--pack` path. The written `generator_config.json` records the derived value.
* Options page: the hint uses the draft's value. The resolution combo marks the preset closest to
  20 tiles across as "(suggested)".

**Tests**
* Dominant size: `basic16` gives 16, `gutter32` 32, `gutterless48` and `rpgmaker_like` 48 (as in
  their goldens).
* `rpggen generate --pack <rpgmaker_like>` writes `base_tile_size: 48`.
* The hint for 48 at 640×360 reads "≈ 13.3 × 7.5".
* A `PLAYER` placeholder on a 48 px pack is 48×72.

**Done when**
* The tests pass, catalog goldens are unchanged, and only `--pack` configs of non-16 px packs
  change.

---

## T12.04 — The CLI rejects unknown arguments

**Depends on:** nothing
**Files:** `rpggen/cli.py`, `tests/unit/test_cli.py` (new)

`main` uses `parse_known_args` (`cli.py:177`). Verified: `rpggen generate --pack X --target Y
--placeholdr PLAYER --godott Z` drops both mistyped flags without a word. Generation then fails on
a missing role, or picks another Godot.

* Use `parse_args` for every command except `gui` and the default. Only that path forwards unknown
  arguments to `QApplication`, for Qt options such as `-platform` and `-style`.
* `ArgumentParser(allow_abbrev=False)`, so `--targ` is an error instead of a silent expansion.
* The frozen multiprocessing child never reaches `main`, because `freeze_support()` runs first in
  `rpggen/__main__.py:8`, `packaging/entry_cli.py:16` and `packaging/entry_gui.py:22`. Keep it so.

**Tests**
* An unknown flag exits with code 2 and "unrecognized arguments".
* `gui -platform offscreen` still starts.
* `python tools/package.py --smoke` passes.

**Done when**
* The tests pass and the README's command lines still work.

---

## T12.05 — Editor-open detection: exact paths, no PowerShell

**Depends on:** nothing
**Files:** `rpggen/core/promote.py`, `pyproject.toml`, `packaging/rpggen.spec`, `THIRD_PARTY_NOTICES.md`, `tests/unit/test_promote.py`

* `editor_open` does a substring match (`promote.py:349-352`). Verified: an editor on
  `D:\Games\forest_v2` makes `D:\Games\forest` look open, and regeneration stops with `REGEN-005`.
* Every preflight starts PowerShell for a CIM query (`promote.py:330-341`). That takes 1–3 s, and
  under a constrained-language policy it fails and silently answers "not open".

**Spec**
* Use `psutil.process_iter(["name", "cmdline", "cwd"])` filtered to names starting with `godot`
  (case-insensitive). Skip `AccessDenied` and `NoSuchProcess`.
* Parse each command line for these project paths:
  * `--path P` and `--path=P`;
  * a positional `…/project.godot`;
  * a positional folder after `-e` or `--editor`.
* Normalize with `Path(p).resolve(strict=False)`, case-folded on Windows. Resolve relative paths
  against the process `cwd()` when available; otherwise ignore them.
* The project is open when a normalized path equals the target or `target/project.godot`.
* The signature and the "cannot ask the system means not open" rule stay. Log the reason at debug.

**Tests**
* A table of command lines:
  * `forest` vs `forest_v2` is not open.
  * A trailing slash or backslash is open.
  * `D:/games/FOREST` is open on Windows.
  * A positional `project.godot` is open.
  * A non-Godot process with the path is not open.
  * A process that denies access is skipped.

**Done when**
* The tests pass, preflight takes under 200 ms for this check, and no PowerShell is started.

---

## T12.06 — Analysis: real progress and a Cancel that cancels

**Depends on:** nothing
**Files:** `rpggen/gui/workers.py`, `rpggen/gui/widgets/analysis_progress.py`, `rpggen/core/catalog.py`, `rpggen/core/analyzer/__init__.py`, `rpggen/core/archive.py`, `rpggen/core/inventory.py`, `tests/gui/test_workers.py`, `tests/unit/test_assemble.py`, `tests/unit/test_archive.py`

* `analyze_packs` calls `assemble` without `is_cancelled` (`workers.py:126`). `assemble` only
  checks between packs (`catalog.py:613`), so Cancel on one large pack waits for the whole
  analysis.
* `on_phase("Analyzing images", total, total)` (`workers.py:125`) sets the bar to 100% for the
  slowest step.
* Extraction and hashing report nothing.

**Spec**
* Thread a callback `Progress = Callable[[str, int, int], None]` (label, done, total; 0 means
  unknown) through:
  * `open_pack`: bytes extracted of the declared total.
  * `build_inventory`: files hashed. Use `as_completed` so progress arrives with the results.
  * `analyzer_for`: images analyzed of the pack's image count.
* The same layers check `is_cancelled`:
  * Extraction stops between chunks and removes `.partial`, as `archive.py:369` already does for
    exceptions.
  * The inventory pool shuts down with `cancel_futures=True`.
  * The analyze callback raises `AssemblyCancelled`.
* `workers.analyze_packs` passes both callbacks into `assemble` and maps `AssemblyCancelled` to
  `Cancelled`.
* The dialog shows a determinate bar per stage, for example:
  * "Extracting forest.zip — 1.2 of 3.4 GB"
  * "Reading files — 412 of 1,048"
  * "Analyzing images — 312 of 1,048"
* On Cancel the label says "Stopping…" and the button is disabled.
* Throttle progress signals to at most 10 per second.

**Tests**
* Cancel during analysis of a 200-image synthetic pack returns within 2 s and leaves no
  `.partial` folder.
* Progress values are monotonic, and the bar reaches its maximum only at the end of a stage.
* The zipped synthetic pack reports extraction progress.

**Done when**
* The tests pass, and Cancel answers within one second of the next file on the perf pack.

---

## T12.07 — Report skipped checks as skipped

**Depends on:** nothing
**Files:** `rpggen/core/orchestrator.py`, `rpggen/core/report.py`, `rpggen/gui/workers.py`, `rpggen/gui/pages/generate_page.py`, `rpggen/gui/pages/results_page.py`, `docs/spec/03_ERROR_CODES.md`, `tests/unit/test_report.py`, `tests/gui/test_generate_page.py`, `tests/gui/test_results_m11.py`

Without export templates, `run_check` returns `ENV-010` (info) and `ran=False`, but the
orchestrator discards `ran` (`orchestrator.py:435`). The Generate page then shows "✔
Test-exporting the game · 0 s". The success view lists only warnings (`results_page.py:340`), so
the user believes the export was verified.

A config with `validation.smoke_test: false` is skipped just as silently (`orchestrator.py:402`).
The GUI has no such toggle, so this concerns hand-written or CLI configs.

**Spec**
* `RunResult.skipped: dict[str, str]` maps a phase to an issue code:
  * export without templates gives `ENV-010`;
  * smoke off gives the new `VAL-021` (I): "The smoke test is turned off in the config; the game
    was not played." Fix: "Set validation.smoke_test to true."
* `Callbacks.on_skip(name, code)` (default no-op), emitted by the worker as a new `skipped` signal.
* Generate page: a "–" icon and "skipped: <short reason>" instead of a duration, with the fix in
  the tooltip.
* Results success view: a collapsible "Notes (n)" section with the INFO issues, skipped checks
  first.
* `GENERATION_REPORT.md` gets a "Checks not run" section.

**Tests**
* With templates absent (patch `templates_installed`), the result has `skipped == {"export":
  "ENV-010"}`, the phase row shows "skipped", and Notes lists `ENV-010`.
* `smoke_test: false` gives `VAL-021`.
* The report has the section.

**Done when**
* No skipped phase is ever shown with ✔.

---

## T12.08 — Generated game: safe backup rotation and translated messages

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_runtime/core/save_manager.gd`, `godot_templates/addons/rpg_runtime/ui/inventory_menu.gd`, `godot_templates/addons/rpg_runtime/world/chest.gd`, `godot_templates/addons/rpg_runtime/ui/strings.gd`, `godot_templates/builder/recipes/translations_recipe.gd`, `godot_templates/tests/unit/test_save_manager.gd`, `godot_templates/tests/probes/probe_rename_replace.gd` (new), `docs/godot_api_verified.md`, `godot_templates/addons/rpg_runtime/CHANGELOG.md`

* `save()` copies the main slot file over its backup without verifying it
  (`save_manager.gd:137-139`). If the main file is damaged, the next save replaces the last good
  backup with it.
* Four player-facing strings bypass `tr()`, although the project ships a translation pipeline:
  * `save_manager.gd:204`
  * `save_manager.gd:208`
  * `inventory_menu.gd:117`
  * `chest.gd:38`

**Spec**
* Back up the main file only when `_read_verified(main)` is not empty. Otherwise keep the existing
  backup and log `[RPG-SAVE] skipped backing up a damaged save`.
* Probe whether `DirAccess.rename_absolute` replaces an existing file on Windows, Linux and macOS
  (`probe_rename_replace.gd`), and record the result.
  * If it replaces: rename the temp file directly onto the main file, with no remove first.
  * If not: keep remove-then-rename (the backup covers the gap).
* New keys:
  * `UI_SAVE_DAMAGED_LOADED_BACKUP`
  * `UI_SAVE_FROM_NEWER_VERSION`
  * `UI_CANNOT_USE_NOW`
  * `UI_CHEST_FOUND` (with `%s`)
  * `UI_CHEST_EMPTY`

  Add them to the English defaults in `strings.gd`, which existing projects fall back to because
  their `user_seed` `strings.tsv` lacks them, and to the seeded TSV for new projects. The chest
  lists translated item names.
* A GDScript test scans the runtime for `notify("` followed by a literal and fails on any new one.

**Tests**
* A damaged main file plus a good backup, then `save()`: the backup still verifies.
* The probe result is recorded in `godot_api_verified.md`.
* The literal-notify scan passes.

**Done when**
* The tests pass and the runtime CHANGELOG mentions both fixes.

---

## T12.09 — Archive extraction: links, collisions and one size budget

**Depends on:** nothing
**Files:** `rpggen/core/archive.py`, `rpggen/core/inventory.py`, `docs/spec/03_ERROR_CODES.md`, `tests/unit/test_archive.py`

* **RAR.** The listing is validated (`archive.py:264-265`), then `7z x -y` extracts *everything*
  (`archive.py:266`):
  * Case collisions are settled by 7-Zip's order, not by the file `ARCH-005` reports as kept.
  * Junk is extracted, then deleted.
  * Size limits are checked only afterwards (`archive.py:275`).
* **Links.** py7zr and 7-Zip can create symbolic links, and nothing rejects links or junctions
  after extraction. `inventory._list_files` follows them (`is_file()`), so a link can pull a file
  from outside the pack into the generated project.
* **Nested archives.** `_extract_nested` (`archive.py:284`) gives each nested archive a fresh
  4 GB budget.

**Spec**
* RAR: write the selected entries (raw names) to a UTF-8 list file, then run
  `7z x -o<dest> -y -scsUTF-8 @<list>`. Nothing outside the list is extracted.
* 7z: drop entries that py7zr reports as symbolic links from `targets`, and record `ARCH-009`.
* After any extraction, and while listing a folder pack, walk with `os.scandir` without following
  links:
  * A symbolic link or junction (`Path.is_junction`, Python 3.12) is removed for archives or
    skipped for folders.
  * Both give `ARCH-009` (W): "{entry} is a link and was skipped."
  * Every remaining file must be `_inside(dest)`.
* A `Budget` (files, bytes) is shared by an archive and all of its nested archives. When it runs
  out, raise `ARCH-004`.

**Tests**
* Nested zips that together exceed the budget give `ARCH-004`.
* RAR with `Tree.png` and `tree.png`: the file `ARCH-005` reports is the one on disk. Skip when 7z
  is absent.
* A folder pack with a link pointing outside: skipped with `ARCH-009`. Skip on Windows without the
  symlink privilege.
* A 7z archive with a symlink entry: the link is not extracted.

**Done when**
* The tests pass and the synthetic corpus is unchanged.

---

## T12.10 — Separate config, data and cache folders; bounded caches

**Depends on:** nothing
**Files:** `rpggen/paths.py`, `rpggen/core/app_settings.py`, `rpggen/gui/state.py`, `rpggen/core/profiles.py`, `rpggen/core/godot_fetch.py`, `rpggen/core/cache.py`, `rpggen/core/archive.py`, `rpggen/core/inventory.py`, `rpggen/gui/thumbnails.py`, `rpggen/gui/dialogs/diagnostic_export.py`, `rpggen/gui/window_menus.py`, `rpggen/core/cache_policy.py` (new), `rpggen/gui/dialogs/storage_dialog.py` (new), `tests/unit/test_paths.py`, `tests/unit/test_cache.py`, `tests/gui/test_menus_welcome.py`, `docs/user_guide.md`

`paths.local_cache_dir()` (`paths.py:79`) is the single root for every one of these:

* settings and option presets;
* installed profiles (`profiles.py:27`);
* drafts of unfinished audits (`state.py:44`);
* the downloaded Godot (`godot_fetch.py:75`);
* logs;
* the real caches.

Disk-cleanup tools empty folders called "cache", so users lose real work. Meanwhile the real
caches are never pruned:

* extracted archives, up to 4 GB each (`archive.py:322`);
* thumbnails, inventories and analysis;
* GIF strips and terrain atlases when no work dir is given.

Only `analyze --no-cache` clears anything, and only the analysis.

**Spec**
* Add `paths.config_dir()`, `data_dir()` and `cache_dir()`. `local_cache_dir()` stays an alias of
  `cache_dir()` for one release. `paths.py` stays the only platform check.

  | Platform | Config | Data | Cache |
  |----------|--------|------|-------|
  | Windows | `%LOCALAPPDATA%\rpggen\config` | `%LOCALAPPDATA%\rpggen\data` | `%LOCALAPPDATA%\rpggen\cache` |
  | Linux | `$XDG_CONFIG_HOME/rpggen` (`~/.config`) | `$XDG_DATA_HOME/rpggen` (`~/.local/share`) | `$XDG_CACHE_HOME/rpggen` (`~/.cache`) |
  | macOS | `~/Library/Application Support/rpggen` | same | `~/Library/Caches/rpggen` |

* `RPGGEN_CACHE_DIR` keeps isolating tests: when it is set, the three folders are `config/`,
  `data/` and `cache/` under it.
* What goes where:
  * config: `settings.json`;
  * data: `drafts/`, `profiles/`, `godot/`, `logs/`;
  * cache: `extracted/`, `analysis/`, `inventories/`, `thumbs/`, `gif_strips/`,
    `terrain_atlases/`.
* One-time migration at startup moves the old items when the new location lacks them. It never
  overwrites, and it logs what moved.
* `cache_policy`:
  * Each `extracted/<sha>` gets a `.last_used` stamp, touched by `open_pack`.
  * Least-recently-used entries beyond `cache_limit_gb` (setting, default 10) are pruned in a
    worker at startup and after analysis. The entry in use is never pruned.
  * Analysis, inventories and thumbnails share a 1 GB cap.
  * `.part` downloads older than 7 days are pruned (T12.21).
* Edit → **Storage…** shows:
  * the size per category, with Clear for cache categories;
  * the limit and "Open folder";
  * the data items, cleared only after a confirmation that lists what is lost.

**Tests**
* Paths per platform (patch `sys.platform` and the environment).
* Migration moves settings and keeps files that already exist at the new location.
* The prune removes the oldest entries beyond the limit and never the one in use.
* The dialog reports sizes.
* The whole suite still runs isolated under `RPGGEN_CACHE_DIR`.

**Done when**
* The tests pass and the user guide has a "Where rpggen keeps its files" section.

---

## T12.11 — One settings store; recent projects survive unplugged drives

**Depends on:** T12.10
**Files:** `rpggen/core/app_settings.py`, the callers of `app_settings.load()` / `save()` (`rpggen/gui/pages/audit_page.py`, `generate_page.py`, `options_page.py`, `project_page.py`, `welcome_page.py`, `rpggen/gui/theme.py`, `window_menus.py`, `wizard.py`, `workers.py`), `tests/unit/test_app_settings.py`, `tests/gui/test_menus_welcome.py`

* `_recent` drops every recent project whose folder is missing (`app_settings.py:79-80`). The next
  save makes it permanent, so a project on an unplugged USB drive is forgotten.
* `load()` parses the JSON and checks up to 10 folders. It is called from 24 places, including
  every second by `GeneratePage._tick` (`generate_page.py:145`), so an unreachable network share
  stalls the window.
* Two windows read, modify and write the same file, so the last writer wins.

**Spec**
* `app_settings.store()` holds one cached `AppSettings` per process:
  * `get()` returns it with no I/O.
  * `update(fn)` applies a change, re-reads the file and merges, then writes atomically with
    `jsonio.write`.
  * Merge rules: recent lists merge by target, newest first. For scalar keys, this process's
    changes win.
  * GUI writes are debounced by 300 ms and flushed on exit.
* Loading no longer touches project folders. `RecentProject.available` is computed lazily by the
  welcome view in a worker, with a 2 s timeout per path.
* Unavailable rows are greyed out with **Locate…** and **Remove**. Nothing is removed
  automatically.
* `GeneratePage` reads `phase_timings` once, in `start()`.

**Tests**
* A missing folder is kept across load and save.
* Two stores that change different keys both keep their changes.
* `get()` does no file I/O (patch `open`).
* The welcome view marks a slow, unavailable folder without blocking (fake `is_dir` that sleeps).

**Done when**
* The tests pass and `grep "app_settings.load()" rpggen/gui` finds nothing.

---

## T12.12 — Git: commit only what rpggen wrote, say when it fails, choose how pack art is handled

**Depends on:** nothing
**Files:** `rpggen/core/vcs.py`, `rpggen/core/orchestrator.py`, `rpggen/core/config.py`, `rpggen/schema/config.schema.json`, `docs/spec/02_SCHEMAS.md`, `rpggen/core/staging.py`, `godot_templates/project_files/README.template.md`, `rpggen/gui/pages/options_page.py`, `docs/spec/03_ERROR_CODES.md`, `tests/unit/test_vcs.py`, `tests/integration/test_regeneration.py`

* `init_and_commit` runs `git add -A` (`vcs.py:57`). A regeneration commit therefore includes the
  user's own uncommitted edits under the message "rpggen: regenerate project".
* A failed commit is only logged; its result is ignored (`orchestrator.py:479`).
* New projects commit `assets/packs/`, the purchased art, by default. Pushed to a public
  repository, that breaks most pack licences.

**Spec**
* A repository rpggen creates keeps the current behaviour (`add -A`, then commit).
* An existing repository:
  * Stage exactly the files promotion wrote or deleted, the `.rpggen-new` conflict files, the
    ledger and the reports, with `git add -- <paths>`.
  * Commit with `git commit -m <msg> -- <paths>`, so other staged or unstaged changes stay out.
  * If the user had uncommitted changes, add `REGEN-008` (I): "Your own uncommitted changes were
    left out of rpggen's commit."
* A failure gives `REGEN-007` (W): "The project was generated but the git commit failed:
  {reason}". It is shown on Results.
* Optional config key `git.pack_art`: `"commit"` (default), `"lfs"` or `"ignore"`.
  * `"ignore"` appends `assets/packs/` to the generated `.gitignore`.
  * `"lfs"` enables the LFS lines of `.gitattributes` for the pack's image and audio extensions.
    Without git-lfs it falls back to `"commit"` with a warning.
* Options page: three radio buttons under "Version control", with one sentence about licences. The
  generated README explains the choice.

**Tests**
* A regeneration in a dirty repository commits only promoted paths (`git log --name-only`).
* A failing pre-commit hook gives `REGEN-007`.
* `"ignore"` puts the line in `.gitignore`.
* The config round-trips and the default is omitted.

**Done when**
* The tests pass and `docs/regeneration.md` describes the commit rules.

---

## T12.13 — No shared mutable network timeouts

**Depends on:** nothing
**Files:** `rpggen/core/profile_registry.py`, `rpggen/core/update_check.py`, `tests/unit/test_update_check.py`, `tests/unit/test_profile_registry.py`

`update_check._fetch` overwrites `profile_registry.TIMEOUT_S` for the duration of a request
(`update_check.py:51-57`). Both run on the `QThreadPool`, so a registry fetch on another thread can
use, or restore, the wrong value.

* `default_fetcher(url, limit, *, timeout=TIMEOUT_S)`. `update_check` passes its own timeout, and
  the swap is deleted.
* Grep for other assignments to another module's constants outside tests; there must be none.

**Tests**
* The update check uses 10 s, the registry 15 s.
* Two threads calling at once each see their own timeout.

**Done when**
* The tests pass.

---

## T12.14 — Audit page layout

**Depends on:** T12.16
**Files:** `rpggen/gui/pages/audit_page.py`, `rpggen/gui/widgets/asset_grid.py`, `rpggen/gui/style.qss`, `rpggen/gui/style_light.qss`, `tests/gui/test_audit_queue.py`

* The splitter is added without a stretch factor (`audit_page.py:146`). The word-wrapped "done"
  label takes the spare height, which leaves an empty band above the grid
  (`docs/images/wizard_audit.png`).
* In the light theme, the "Size" label overlaps the search field
  (`docs/images/wizard_audit_light.png`).

**Spec**
* Use `layout.addWidget(self.splitter, 1)`, and give `done_label` the vertical policy `Maximum`.
* Filter row: the search field gets the stretch and a minimum width. The Size label and slider get
  a fixed width.
* The full redesign of the filter bar is T12.32.

**Tests**
* The splitter's height is at least the page height minus the progress row, the done label and
  the margins.
* T12.16 passes on Audit in both themes.

**Done when**
* Both tests pass.

---

## T12.15 — Release hygiene and the 1.0 gate

**Depends on:** nothing
**Files:** `.github/workflows/release.yml`, `.github/workflows/ci.yml`, `.github/dependabot.yml` (new), `requirements/release.txt` (new, generated), `CONTRIBUTING.md`, `docs/release.md`, `tests/unit/test_release.py`

* `CHANGELOG.md` calls 1.0.0 "the first release", but its own gate T10.10 is still open:
  * The held-out and pack-coverage tables in `docs/coverage.md` are empty.
  * The 1.000 accuracy is measured on the synthetic packs the heuristics were tuned on.

  No tag exists yet, so this is a gate to keep, not a mistake to undo.
* `release.yml` has three problems:
  * It installs unpinned dependencies (`pip install -e .[dev]`).
  * It runs only `tests/unit/test_release.py` and the frozen smoke test.
  * It pins third-party actions by tag in a job that has `contents: write`, `id-token: write` and
    the SignPath secret.
* `CONTRIBUTING.md:119-120` tells contributors to copy `03_ERROR_CODES.md` onto itself.

**Spec**
* `requirements/release.txt` with hashes, from
  `pip-compile --generate-hashes --extra dev pyproject.toml` (Python 3.12, Windows). The release
  job runs `pip install --require-hashes -r requirements/release.txt`, then
  `pip install --no-deps -e .`. A CI step fails when the lock is out of date.
* `ci.yml` also runs `on: workflow_call`. `release.yml` calls it first (`needs: ci`), so the tagged
  commit passes the whole suite, integration included.
* Every third-party `uses:` is pinned to a full commit SHA, with the tag as a comment. Dependabot
  updates `github-actions` weekly.
* On tag builds, a step fails while `docs/coverage.md` contains `*(pending)*`.
* `CONTRIBUTING.md` step 1 becomes: "Add the row to `docs/spec/03_ERROR_CODES.md`."

**Tests** (`test_release.py`)
* Every `uses:` in `.github/workflows/` has a 40-hex SHA.
* The lock file names every `pyproject.toml` dependency.
* CONTRIBUTING contains no self-copy instruction.

**Done when**
* A dry run of the release workflow (`workflow_dispatch`) goes through CI, installs from the lock
  and stops at the gate step while `coverage.md` is pending.

---

# Part B — Engineering

## T12.16 — Layout regression test

**Depends on:** nothing (do it together with T12.01)
**Files:** `tests/gui/test_layout_fit.py` (new), `tests/gui/conftest.py`, `rpggen/dev.py`

Neither the Mapping page defect nor the truncated Audit combos are caught by any test.

**Spec**
* Build a `WizardState` by running `workers.analyze_packs` on the sample pack directly; no Godot is
  needed.
* Check every wizard page, for both archetypes, both themes and two window sizes (the minimum and
  1100×720). The test fails on any visible widget whose geometry is below its
  `minimumSizeHint()`:
  * in height or width;
  * except widgets inside a `QScrollArea` viewport, which may scroll.

  The failure names the page and the `objectName`.
* Every visible `QComboBox` (current text), `QPushButton` and `QToolButton` text fits:
  `fontMetrics().horizontalAdvance(text)` plus the style's padding is at most the width. This
  catches "All pacl".
* `python -m rpggen.dev layout-shots` writes a PNG of every page, theme and size to a temp folder
  for review.

**Tests**
* This card is the test. At `e8bab6d` it must fail on Mapping and Audit; record that in
  `implementation_notes.md`. T12.01 and T12.14 then make it pass.

**Done when**
* It runs in both CI jobs (offscreen) and is green.

---

## T12.17 — Parallel image analysis

**Depends on:** T12.06
**Files:** `rpggen/core/analyzer/__init__.py`, `rpggen/core/catalog.py`, `tests/unit/test_assemble.py`, `tests/integration/test_determinism.py`, `tests/perf/test_perf.py`

Hashing already uses a process pool (`inventory.py:195`). `analyze_array` (grid detection,
regions, character sheets) runs one image at a time through `analyzer_for`
(`analyzer/__init__.py:104`), from inside the adapters. ARCHITECTURE §45 says analysis is
parallelized across processes.

**Spec**
* `analyzer.prewarm(inv, root, *, use_cache, is_cancelled, on_progress)`:
  * Images whose `(sha256, ANALYZER_VERSION)` is not cached are analyzed in a
    `ProcessPoolExecutor` (workers `min(8, cpu)`, chunk size 4, only above `POOL_THRESHOLD`).
  * Each worker writes the cache entry, and the results seed the `analyzer_for` memo.
  * With `use_cache=False`, results stay in memory.
* `assemble` calls `prewarm` per pack before `run_adapters`.
* Images over 64 megapixels are analyzed in the parent, one at a time, to bound memory.
* `freeze_support()` is already called by both frozen entry points. Keep it so.

**Tests**
* The catalog is identical with and without prewarm on every synthetic pack.
* Cancel stops the pool.
* The perf test prints the speed-up. It asserts cold analysis of the 1,000-image pack at least 2×
  faster only when `os.cpu_count() >= 4`.

**Done when**
* The tests pass and `docs/coverage.md` has the new timings.

---

## T12.18 — Folder-pack inventory cache

**Depends on:** T12.10
**Files:** `rpggen/core/inventory.py`, `tests/unit/test_inventory.py`

`build_inventory` uses the cache only for packs with a source hash, which means archives
(`inventory.py:177`). Folder packs are hashed in full on every analysis and every generation.

**Spec**
* For folders, the cache is `inventories/folder_<sha256(resolved path, case-folded)[:16]>.json`.
  It holds per file: path, size, `mtime_ns`, sha256 and the image facts.
* When building:
  * List the files.
  * Reuse an entry when size and `mtime_ns` match; scan the rest.
  * Write the cache back.
* `use_cache=False` (`--no-cache`) bypasses it.
* Document the one blind spot: a tool that rewrites a file keeping both its size and its modified
  time. `--no-cache` fixes it.

**Tests**
* A second build of an unchanged folder reads no file contents (patch `open` in `_scan_file`).
* Touching one file rescans only that file.
* Added and deleted files are handled.

**Done when**
* The tests pass and warm analysis of a folder pack does no hashing.

---

## T12.19 — Live Godot output and build progress

**Depends on:** nothing
**Files:** `rpggen/core/godot.py`, `rpggen/core/orchestrator.py`, `godot_templates/builder/build.gd`, `godot_templates/builder/validate.gd`, `godot_templates/builder/lib/log.gd`, `rpggen/gui/workers.py`, `rpggen/gui/pages/generate_page.py`, `rpggen/gui/widgets/log_view.py`, `tests/unit/test_godot_cancel.py`, `tests/gui/test_generate_page.py`

`godot._run` collects stdout and stderr in lists (`godot.py:119-131`) and writes the log file after
Godot exits. "Show details" therefore shows nothing new during an import of up to 600 s, or during
the build.

**Spec**
* `_run(..., on_line=None)`: the drain threads split the output into lines and call `on_line`. The
  log file is opened before the start and written as lines arrive, so a crash still leaves a log.
* The orchestrator forwards Godot lines prefixed `[godot] `, batched every 100 ms, at most 200 lines
  per batch.
* Progress protocol:
  * The builder and the validator print `@rpggen step <phase> <i>/<n> <label>` once per recipe or
    check, through a `log.gd` helper.
  * The orchestrator parses these lines (they are not forwarded) and calls the new
    `Callbacks.on_step(phase, i, n, label)`.
* Generate page: a muted sub-line under the running phase, for example "Building tile sets (7 of
  31)". During import, which has no protocol, it shows the last line Godot printed, elided.
* `LogView`:
  * Appends in batches and keeps 5,000 lines; older lines give way to a note pointing to
    `rpggen/logs`.
  * Auto-scrolls unless the user has scrolled up.

**Tests**
* A fake Godot that prints with pauses: `on_line` receives lines before it exits.
* Protocol parsing.
* The `LogView` cap and auto-scroll.
* Cancel still kills the process tree within 0.2 s.

**Done when**
* The tests pass, and the sample generation shows a moving sub-line in every Godot phase.

---

## T12.20 — Lean failed-run folders

**Depends on:** nothing
**Files:** `rpggen/core/staging.py`, `rpggen/core/app_settings.py`, `tests/unit/test_staging_regen.py`

`staging.discard` (`staging.py:358`) moves the whole staging folder into
`.rpggen_failed/<stamp>/` and keeps three of them. Each holds copied pack art (full copies for new
projects) and the `.godot/` import cache. A 2 GB pack can leave 6 GB or more hidden in the output
folder.

**Spec**
* After the move, delete `assets/packs/` and `.godot/imported/` from the failed copy, unless the
  setting `keep_full_failed_runs` is on (default off).
* Write `FAILED_RUN.md`: what was removed, and how to keep everything next time.
* Keep `rpggen/`, the logs and results, `generated/`, `game/` and `project.godot`.
* Diagnostic bundles are unchanged; they never contain art.

**Tests**
* A failed run (the existing sabotage hook) leaves no PNG under `.rpggen_failed`.
* With the setting on, the art is kept.
* `FAILED_RUN.md` lists the removed folders.

**Done when**
* The tests pass.

---

## T12.21 — Godot download: pinned checksum, resume, retry

**Depends on:** T12.10
**Files:** `rpggen/godot_target.py`, `rpggen/core/godot_fetch.py`, `tools/bump_godot.py`, `tools/fetch_godot.py`, `tests/unit/test_godot_fetch.py`, `tests/unit/test_fetch_godot.py`

* The SHA-512 comes from the same GitHub release as the zip (`godot_fetch.py:159`). It detects
  corruption, not tampering.
* Any failure or cancel deletes the `.part` file (`godot_fetch.py:193`), so the next attempt starts
  from zero.

**Spec**
* `godot_target.SHA512 = {"windows": "<hex>", "linux": "<hex>"}` for `VERSION`:
  * `fetch()` requires a match with the pinned value.
  * The release's `SHA512-SUMS.txt` is still read and must agree; a mismatch is `ENV-011`.
  * Other versions (`tools/fetch_godot.py --version`) fall back to the SUMS file alone.
* `bump_godot.py` downloads the SUMS file of the new version and writes both hashes. Its printed
  checklist gains "compare the hashes with the release page".
* Resume:
  * Keep `<name>.part` and `<name>.part.json` (url, bytes, etag).
  * A retry sends `Range: bytes=<n>-` and `If-Range: <etag>`. A 206 appends (the hash re-reads the
    kept bytes once); a 200 restarts.
  * Three retries on network errors, with backoff of 2, 5 and 10 s.
  * Cancel keeps the `.part` file; T12.10 prunes it after 7 days.

**Tests**
* A file that matches the SUMS file but not the pinned hash fails.
* Resume with a fake opener: the 206 path and the 200 fallback.
* The retry count.
* Cancel keeps `.part`.

**Done when**
* The tests pass, and `godot_target.py` holds real hashes for 4.7.2.

---

## T12.22 — PySide6 version matrix

**Depends on:** nothing
**Files:** `pyproject.toml`, `.github/workflows/ci.yml`

`PySide6>=6.7` has no upper bound, and Qt minor releases change style and layout behaviour.

* Change the dependency to `PySide6>=6.7,<7`.
* The Ubuntu job gets a matrix `pyside: ["6.7.*", "latest"]` that runs
  `pytest -m "not integration" tests/gui`. The 6.7 leg installs `"PySide6==6.7.*"` first.
* Windows stays on the lock (T12.15). `fail-fast: false`.
* Comment any version-specific workaround with the version.

**Done when**
* Both legs are green.

---

## T12.23 — A report for unexpected errors

**Depends on:** nothing
**Files:** `rpggen/core/orchestrator.py`, `rpggen/core/diagnostics.py`, `docs/spec/03_ERROR_CODES.md`, `tests/unit/test_orchestrator_crash.py` (new)

On any unexpected exception, `_execute` moves staging to `.rpggen_failed` and re-raises
(`orchestrator.py:633-636`):

* The failed folder has no report and no issue.
* The GUI shows `GUI-001` from the worker.
* The CLI prints a traceback.

**Spec**
* Catch `Exception` (`KeyboardInterrupt` and `SystemExit` keep today's path):
  * Write the traceback to `rpggen/logs/crash.log` in staging.
  * Add `BUILD-005` (E): "Unexpected error in phase {phase}: {reason}", with the fix "Export a
    diagnostic bundle and report it."
  * Return `_fail(state)`.
* The failed folder then has both reports, and the GUI shows Results with "Export diagnostic
  bundle".
* Diagnostic bundles include `crash.log`.

**Tests**
* A phase patched to raise gives a result with `ok` False and `failed_phase` set.
* The reports and `crash.log` exist, and the issue is `BUILD-005`.

**Done when**
* The tests pass.

---

## T12.24 — One log location, rotated, with run ids

**Depends on:** T12.10
**Files:** `rpggen/logging_setup.py`, `rpggen/cli.py`, `rpggen/gui/app.py`, `rpggen/core/orchestrator.py`, `rpggen/core/report.py`, `rpggen/core/diagnostics.py`, `rpggen/gui/dialogs/diagnostic_export.py`, `rpggen/gui/pages/results_page.py`, `tests/unit/test_diagnostics.py`

The CLI logs to `%TEMP%\rpggen_cli_logs` (`cli.py:98`); the GUI logs to the cache folder
(`diagnostic_export.py:14`). Nothing ties app log lines to a run.

**Spec**
* `paths.log_dir()` is under data. Both CLI and GUI use a `RotatingFileHandler` of 5 × 2 MB.
* Each generation gets a run id of 8 hex characters:
  * A `logging.Filter` attaches it to every record during the run.
  * It is stored in `generation_report.json`.
  * Results shows it ("Run 3f9a1c2e").
* A diagnostic bundle includes the app log lines of its run id.

**Tests**
* CLI and GUI write to the same folder.
* Rotation happens.
* A bundle contains only the matching run's lines.

**Done when**
* The tests pass.

---

## T12.25 — View-models for the Project and Options pages

**Depends on:** T12.02, T12.03
**Files:** `rpggen/gui/models/__init__.py` (new), `rpggen/gui/models/project_model.py` (new), `rpggen/gui/models/options_model.py` (new), `rpggen/gui/pages/project_page.py`, `rpggen/gui/pages/options_page.py`, `tests/unit/test_project_model.py` (new), `tests/unit/test_options_model.py` (new)

`project_page.py` (965 lines) and `options_page.py` (944 lines) keep validation, suggestions,
config building, presets and feature dependencies inside widget classes. Most of that can only be
tested through Qt.

**Spec**
* Move the non-widget logic into plain classes that import nothing from PySide6. The pages keep the
  widgets, the signals and the wiring.
* No behaviour change: the existing GUI tests stay unchanged and green.
* Target: each page under 500 lines, and the models covered by Qt-free unit tests.

**Done when**
* Both targets are met and the full suite is green.

---

## T12.26 — A real-pack accuracy corpus without art

**Depends on:** nothing
**Files:** `tools/corpus_fingerprint.py` (new), `rpggen/analyze_cmd.py`, `rpggen/core/accuracy.py`, `docs/coverage.md`, `.github/workflows/ci.yml`, `tests/unit/test_accuracy.py`

The 1.000 accuracy comes from the synthetic corpus the heuristics were tuned on, as
`docs/coverage.md` itself says. Purchased packs cannot be committed.

**Spec**
* A corpus entry is one JSON file:
  * the pack fingerprint (paths, sha256 and sizes, as in the registry index);
  * the expected decisions in the exported-profile format (roles, grids, animations, objects).

  It holds no pixels.
* `tools/corpus_fingerprint.py --pack X --profile confirmed.rpgprofile.json --out corpus/x.json`
  creates an entry.
* `rpggen analyze --private-corpus DIR --packs ROOT`:
  * Finds each pack under `ROOT` by fingerprint and analyzes it.
  * Reports per-role precision and recall, a confusion matrix, and grid and animation accuracy, as
    JSON and Markdown.
* An optional CI job runs on a self-hosted runner when `vars.PRIVATE_CORPUS` is set.
* Use it to fill the held-out table of `docs/coverage.md` (T10.09).

**Tests**
* A fingerprint round-trip.
* A confusion matrix for a synthetic pack treated as private.

**Done when**
* The tests pass, and the maintainer has run it on at least the five held-out packs.

---

## T12.27 — Performance trends

**Depends on:** nothing (benefits from T12.17)
**Files:** `tests/perf/test_perf.py`, `tests/perf/conftest.py`, `.github/workflows/ci.yml`

The perf tests allow twice the §45 targets (`test_perf.py:22`) and run only on pushes to main, so
slow drift goes unnoticed until a hard ceiling breaks.

**Spec**
* The tests write `perf.json` with:
  * cold and warm analysis;
  * full generation;
  * a new case: regeneration with no changes (§45 target under 1 minute).
* CI publishes the file with `benchmark-action/github-action-benchmark` (pinned SHA) and comments
  when a value exceeds 130% of the previous main run. This is not a failure.
* The hard ceilings stay. Pull requests labelled `perf` run the job.

**Done when**
* Two consecutive main runs produce a trend entry.

---

## T12.28 — Scriptable CLI: `--json`, exit codes, `--dry-run`

**Depends on:** T12.04, T12.07, T12.23
**Files:** `rpggen/cli.py`, `rpggen/analyze_cmd.py`, `rpggen/core/orchestrator.py`, `docs/spec/02_SCHEMAS.md`, `README.md`, `docs/user_guide.md`, `tests/unit/test_cli.py`

**Spec**
* `--json` on `generate`, `analyze`, `restore` and `diagnose` prints one JSON document on stdout;
  human lines go to stderr. For `generate` it holds `ok`, `target`, `failed_phase`,
  `failed_staging`, `skipped`, `timings` and `issues[{code, severity, message, fix, file}]`. Add
  the schema to `02_SCHEMAS.md`.
* Exit codes:

  | Code | Meaning |
  |-----:|---------|
  | 0 | OK |
  | 1 | Generation failed (`BUILD`, `VAL`, `SMOKE` or `REGEN` errors) |
  | 2 | Usage error |
  | 3 | Environment or input (`ENV`, `ARCH`, `CAT`) |
  | 4 | Cancelled with Ctrl+C (a SIGINT handler sets `is_cancelled`; staging is discarded) |
  | 70 | Internal error (`BUILD-005`) |

* `--dry-run` runs preflight, analysis, the requirement check and the starter-map plan, then prints
  a summary (roles, tile size, map size and counts). It creates no staging, runs no Godot and leaves
  the target untouched.

**Tests**
* The JSON parses and matches the schema.
* Each exit code.
* A dry run leaves a missing target missing.

**Done when**
* The tests pass and the README's command-line section documents all three.

---

## T12.29 — Strict GDScript in the template project

**Depends on:** nothing
**Files:** `godot_templates/project.godot`, `godot_templates/addons/**`, `godot_templates/builder/**`, `docs/godot_api_verified.md`

The template project sets no `debug/gdscript/warnings/*`. Untyped declarations and unsafe property
or method access go unnoticed in the runtime that every generated project ships.

**Spec**
* This applies to the template project only. Generated projects get their settings from the
  builder and do not change.
* Verify the setting names with a probe. Then:
  * Set `untyped_declaration` and the `unsafe_*` group to warn (1) and count the hits.
  * Fix them.
  * Raise them to error (2).
* `python -m rpggen.dev godot-test` fails on any warning that is set to error.

**Done when**
* `godot-test` and the integration suite are green with the stricter settings.
* The determinism test shows generated projects unchanged.

---

# Part C — Wizard and game UX

## T12.30 — Quit is not Cancel; fit laptop screens

**Depends on:** T12.16
**Files:** `rpggen/gui/wizard.py`, `rpggen/gui/window_menus.py`, `rpggen/gui/style.qss`, `rpggen/gui/style_light.qss`, `tests/gui/test_shell.py`

* The bottom-left "Cancel" closes rpggen (`wizard.py:147-161`; tooltip "Close rpggen"). The
  Generate page has its own "Cancel" that stops generation, so one screen shows two Cancel buttons
  with different meanings (`docs/images/wizard_generate.png`).
* The minimum window size of 1000×640 (`wizard.py:88`) does not fit a 1366×768 laptop at 125%
  scaling, which leaves about 1093×576 usable.

**Spec**
* Rename the button to **Quit** (Ctrl+Q, also in the File menu), and hide it while generation
  runs.
* Minimum size 880×540. Below 1000 px wide, the sidebar shows numbers and icons only, with the
  names in tooltips.
* T12.16 runs at the new minimum.

**Tests**
* The button's text and visibility while running.
* The layout check at 880×540.

**Done when**
* The tests pass.

---

## T12.31 — Audit cards: audio, fonts, role badges, playback

**Depends on:** T12.16
**Files:** `rpggen/gui/widgets/asset_grid.py`, `rpggen/gui/thumbnails.py`, `rpggen/gui/widgets/asset_detail.py`, `rpggen/gui/widgets/audio_preview.py`, `rpggen/core/audio_info.py`, `tests/gui/test_asset_grid.py`

* Thumbnails skip everything that is not an image (`asset_grid.py:215`), so audio and font cards
  are blank grey squares.
* For those assets the detail panel shows an empty dark box.
* Playback exists only in the Mapping sound dialog (`sound_section.py`).
* Cards show the file name and a status corner, so seeing a role takes a click.

**Spec**
* Audio card:
  * a music or speaker glyph;
  * the duration (from `audio_info`);
  * a waveform strip for WAV, read with the standard `wave` module. Other formats get the glyph and
    duration only.
* Font card: "Aa Bb 123" rendered from the file with `QFontDatabase.addApplicationFont`, removed
  again after rendering. If that fails, an "Aa" glyph.
* Every card gets a role chip (the friendly name from `labels.role_label`), plus a thin confidence
  bar for `AUTO_DETECTED` and `NEEDS_REVIEW`. The status corner glyph stays, so colour is never the
  only cue.
* Detail panel for audio: Play/Stop (Space), duration and type, through `audio_preview`. The empty
  image box is hidden for audio and fonts.

**Tests**
* The delegate paints a role chip.
* An audio card shows a duration.
* Play is hidden when `audio_preview.available()` is False.

**Done when**
* The tests pass and the regenerated audit screenshot shows no blank cards.

---

## T12.32 — Audit filter bar that fits

**Depends on:** T12.14
**Files:** `rpggen/gui/widgets/asset_grid.py`, `rpggen/gui/pages/audit_page.py`, `rpggen/gui/window_menus.py`, `tests/gui/test_asset_grid.py`

The screenshot shows four problems: truncated combos ("All role", "All pacl"), a clipped "Profile"
corner button, an unlabelled "?" button, and chips crammed into one row.

**Spec**
* Row 1: the status chips, in a `FlowLayout` so they wrap.
* Row 2: role and pack combos (`AdjustToContents`, minimum width from the longest item, elided with
  a tooltip) and the search field, which stretches.
* The thumbnail-size slider moves to View → Thumbnail size, which already exists
  (`window_menus.py:94`), with Ctrl+= and Ctrl+-.
* "?" becomes "Shortcuts".
* The tab corner gives the Profile button its full width.

**Tests**
* T12.16's text-fit check passes on Audit in both themes.
* Ctrl+= changes the thumbnail size.

**Done when**
* The tests pass.

---

## T12.33 — Project page: pack cards

**Depends on:** T12.25
**Files:** `rpggen/gui/pages/project_page.py`, `rpggen/gui/models/project_model.py`, `rpggen/core/pack_sniff.py` (new), `tests/unit/test_pack_sniff.py` (new), `tests/gui/test_project_page.py`

**Spec**
* Each added pack becomes a card with:
  * name, kind (folder, zip, 7z, rar), size and file count;
  * a remove button.
* The card also shows the format, sniffed without extracting (zip or 7z name list, or a folder
  listing):
  * **RPG Maker:** `img/tilesets`, A1–A5 and B–E names, `$` and `!` prefixes. 48 or 32 px is read
    from one sheet's header.
  * **LPC.**
  * **Tiled:** `.tsx` or `.tmx` files.
  * **LDtk:** `.ldtk` files.
  * **Aseprite:** `.json` files with `frames` and `meta`.
  * **Generic** otherwise.
* It also shows whether a licence file was found, with the same names as
  `catalog._license_files`.
* Errors appear inline: unsupported type, missing path, password protected (`ARCH-002`).
* Sniffing runs in a worker and takes at most 1 s for a listing.

**Tests**
* Every synthetic pack sniffs to its expected format.
* Licence detection.
* A missing path shows its error on the card.

**Done when**
* The tests pass.

---

## T12.34 — Archetype cards drawn with the pack's art

**Depends on:** nothing
**Files:** `rpggen/gui/pages/archetype_page.py`, `rpggen/gui/thumbnails.py`, `tests/gui/test_archetype_page.py`

The cards are drawn with coloured rectangles (`docs/images/wizard_archetype.png`), although the
packs have already been analyzed when the Project page is left (`project_page.py:889-918`).

**Spec**
* When `state.catalog` has a `PLAYER`, draw each card's scene with:
  * the ground tiles;
  * the player's first idle or walk frame;
  * the enemy's first frame (turn-based: in the battle layout; action RPG: next to the swing arc).
* Scale with nearest-neighbour to an integer factor. Any missing piece falls back to today's
  drawing.
* Cache the result per catalog.

**Tests**
* With the sample pack, the card contains pixels of the hero sprite (sample a known colour).
* Without a catalog, the card uses today's drawing.

**Done when**
* The tests pass.

---

## T12.35 — Sidebar: step status and forward jumps

**Depends on:** nothing
**Files:** `rpggen/gui/wizard.py`, `rpggen/gui/pages/base.py`, `rpggen/gui/pages/*.py` (a `status()` each), `tests/gui/test_wizard_flow.py`

The sidebar only shows enabled or disabled, and only visited pages are clickable
(`wizard.py:236`).

**Spec**
* `WizardPage.status(state) -> (kind, count)`, with kind in `none`, `ok`, `attention` or `error`.
* Items read like "3. Audit · 12", with ✓, ⚠ or ✖ and an accessible description.
* A forward click is allowed to any page up to the first page with blocking errors. The pages in
  between are entered and left in order, exactly as with Next.
* Generate and Results stay reachable only as today.

**Tests**
* The status counts for Audit (attention) and Mapping (missing required).
* A jump from Project to Options after analysis passes through the enter and leave of each page in
  between.

**Done when**
* The tests pass.

---

## T12.36 — Mapping: inline candidates

**Depends on:** T12.01
**Files:** `rpggen/gui/pages/mapping_page.py`, `rpggen/core/mapping.py`, `tests/gui/test_mapping_page.py`

**Spec**
* Each row's asset label becomes a combo with:
  * the top five of `mapping.candidates(catalog, role)`, each with a thumbnail, name and
    confidence;
  * "None";
  * "More…", which opens `AssetPickerDialog` as today.
* Choosing is the same undoable edit as Choose…, and the combo is reachable by keyboard.

**Tests**
* The candidates appear in rank order.
* Choosing updates the starter assignment and can be undone.

**Done when**
* The tests pass.

---

## T12.37 — Options: summary panel

**Depends on:** T12.25
**Files:** `rpggen/gui/pages/options_page.py`, `rpggen/gui/models/options_model.py`, `tests/gui/test_options_page.py`

The page already has a collapsed Advanced section (`options_page.py:404`), so the review's
suggestion to add one is withdrawn.

**Spec**
* A summary card at the top, or in a right-hand column at 1200 px and wider. It shows:
  * the archetype;
  * the maps (starter, second area, interiors);
  * the systems that are on, as chips;
  * the tile size and how many tiles fit on screen.
* Two estimates:
  * **Generation time:** the saved `phase_timings`, scaled by the asset-count ratio. Hidden without
    history.
  * **Project size:** pack bytes × an import-overhead factor measured on the sample pack.
* It updates live.

**Tests**
* The summary follows feature toggles.
* The time estimate is hidden without saved timings.

**Done when**
* The tests pass.

---

## T12.38 — Map preview legend as widgets

**Depends on:** nothing
**Files:** `rpggen/gui/widgets/map_preview.py`, `rpggen/core/map_preview.py`, `tests/unit/test_map_render.py`, `tests/gui/test_options_m11.py`

`core/map_preview.py:592-605` paints the legend and the note into the image with PIL's default
bitmap font. The widget then scales the image down:

* The text becomes illegible (`docs/images/map_preview.png`).
* It is English only.
* The note duplicates the label at `widgets/map_preview.py:136`.

**Spec**
* The widget calls `render(..., legend=False)` and builds the legend as Qt widgets: a coloured dot
  and a `tr()` name for each marker, with one caption.
* Remove the `legend` parameter and its drawing if no other caller remains.

**Tests**
* The widget has five legend labels with translated text.
* The rendered image is exactly the map's height.

**Done when**
* The tests pass.

---

## T12.39 — Results: Play, Open starter map, grouped warnings

**Depends on:** T12.07
**Files:** `rpggen/gui/pages/results_page.py`, `rpggen/core/godot.py`, `rpggen/gui/wizard.py`, `rpggen/gui/pages/audit_page.py`, `rpggen/gui/dialogs/error_lookup.py`, `docs/godot_api_verified.md`, `tests/gui/test_results_m11.py`

Results offers "Open in Godot" plus links that open the file explorer. Warnings are one flat list
(`results_page.py:272-282`).

**Spec**
* `godot.find_gui_exe(exe)` returns the non-console sibling (the inverse of `find_console_exe`,
  `godot.py:70`). Launches use it.
* **Play** launches `<gui exe> --path <target>`.
* **Open starter map** launches `<gui exe> --editor --path <target>
  res://game/maps/starter_map.tscn`. Verify that 4.7.2 opens the scene this way, and record it.
  Fallback: open the editor only.
* Warnings are grouped by code: "<code> × 37", expandable, with the shared fix shown once.
* "Show these assets" switches to Audit, filtered to the assets named by the issues.
* Double-clicking a code opens `error_lookup` at that code.

**Tests**
* The launch arguments, through the existing `launch` hook.
* The group counts.
* The jump to Audit applies the filter.

**Done when**
* The tests pass.

---

## T12.40 — Regeneration preview before promotion

**Depends on:** nothing
**Files:** `rpggen/core/orchestrator.py`, `rpggen/core/promote.py`, `rpggen/gui/workers.py`, `rpggen/gui/pages/generate_page.py`, `rpggen/gui/dialogs/promotion_dialog.py` (new), `rpggen/cli.py`, `rpggen/core/app_settings.py`, `tests/unit/test_promote.py`, `tests/gui/test_regeneration_ui.py`

On a regeneration, the user learns about overwritten files and conflicts only afterwards, as
`REGEN-001` and `REGEN-002` warnings.

**Spec**
* Split `promote.promote` so the `PromotionPlan` (computed at `promote.py:306`) is available before
  `execute`.
* `Callbacks.confirm_promotion(summary) -> bool` (default True). The summary holds the counts and
  lists for write, delete, conflicts and skipped deletions, plus the backup folder name.
* GUI:
  * The worker waits on a `threading.Event`, and the page shows a dialog:
    * files to update, grouped by folder;
    * conflicts, with "a `.rpggen-new` copy will be written beside";
    * deletions that are respected;
    * where the backup goes.
  * Cancel means the run is cancelled and staging discarded.
  * The setting "Show the changes before regenerating" is on by default and applies only to
    regenerations that write something.
  * Closing the window while the dialog is open cancels.
* CLI: no prompt by default, so scripts are unaffected. `--confirm` prints the summary and asks
  y/N on a TTY.

**Tests**
* When the callback returns False, the target stays byte-identical.
* The dialog lists the conflict files.
* `--confirm` answered with `n` cancels.

**Done when**
* The tests pass.

---

## T12.41 — One-click fixes for common failures

**Depends on:** T12.39
**Files:** `rpggen/gui/fixes.py` (new), `rpggen/gui/pages/results_page.py`, `rpggen/gui/pages/project_page.py`, `rpggen/gui/pages/welcome_page.py`, `tests/gui/test_results_m11.py`

**Spec**
* A registry maps codes to buttons shown on their issue row:

  | Code | Button |
  |------|--------|
  | `ENV-001`, `ENV-002` | "Download Godot 4.7.2" (the existing download flow) and "Choose Godot…" |
  | `ENV-009` | "Choose another output folder" |
  | `ENV-010` | "How to install export templates" (help anchor) |
  | `ASSET-010` (a required role is missing) | "Use a placeholder and generate again" |
  | `REGEN-006` | "Accept the runtime upgrade and generate again" |
  | `REGEN-001` | "Resolve conflicts" (opens the resolver of T12.58; until it lands, the folder) |

* Actions only change `WizardState` and navigate. Nothing runs without the user's click.

**Tests**
* Each action leaves the expected state.
* Only registered codes get a button.

**Done when**
* The tests pass.

---

## T12.42 — Follow the system theme; theme-aware canvases

**Depends on:** nothing
**Files:** `rpggen/core/app_settings.py`, `rpggen/gui/theme.py`, `rpggen/gui/window_menus.py`, `rpggen/gui/widgets/image_view.py`, `rpggen/gui/widgets/anim_preview.py`, `rpggen/gui/widgets/map_preview.py`, `tests/gui/test_theme_a11y.py`

* The only themes are `"dark"` and `"light"` (`app_settings.py:24`).
* The preview canvases hard-code dark backgrounds: `image_view.py:27` uses `QColor(60, 60, 60)` and
  `anim_preview.py:75` uses `QColor(70, 70, 70)`. The light theme therefore shows dark boxes
  (`docs/images/wizard_audit_light.png`).

**Spec**
* Add a `"system"` theme, the default for first runs; existing settings keep their choice. It
  follows `QGuiApplication.styleHints().colorScheme()` and its `colorSchemeChanged` signal.
* Canvases read theme tokens (canvas background, grid lines) from `theme.py`. The transparency
  checkerboard is unchanged.

**Tests**
* The system theme follows a faked scheme change.
* The canvas colour differs between themes.
* The existing contrast test still passes.

**Done when**
* The tests pass.

---

## T12.43 — Audit change history

**Depends on:** nothing
**Files:** `rpggen/gui/edits.py`, `rpggen/gui/pages/audit_page.py`, `rpggen/gui/widgets/changes_panel.py` (new), `tests/gui/test_audit_edits.py`

Edits can be undone (a `QUndoStack`, `edits.py:242`), but the user cannot see what they changed
since the analysis.

**Spec**
* A "Changes (n)" tab next to Rules and Terrain lists:
  * every asset whose overrides differ from what was detected (role, grid, collision, animations,
    excluded, objects);
  * the folder rules added;
  * each as before → after.
* Each row has a Revert button, which is an undoable command.
* A filter by kind. Double-click selects the asset in the grid. The count updates on every edit.

**Tests**
* An edit adds a row.
* Revert restores the detected value and can itself be undone.
* The count is correct.

**Done when**
* The tests pass.

---

## T12.44 — Generated game: save and load screens

**Depends on:** T12.08
**Files:** `godot_templates/addons/rpg_runtime/ui/save_load_menu.gd`, `godot_templates/addons/rpg_runtime/core/save_manager.gd`, `godot_templates/addons/rpg_runtime/world/map_root.gd`, `godot_templates/addons/rpg_runtime/ui/strings.gd`, `godot_templates/builder/recipes/ui_recipes.gd`, `godot_templates/builder/smoke/smoke_steps_m6.gd`, `godot_templates/tests/unit/test_save_manager.gd`

* A slot shows the map's file id and the playtime (`save_load_menu.gd:18-22`).
* `saved_at` is stored, in UTC, but never shown (`save_manager.gd:59`).
* Saving over a used slot asks nothing.
* The slot loops are hard-coded as `range(0, 4)` (`save_load_menu.gd:10`, `27`, `43`) instead of
  using `SaveManager.SLOTS`.

**Spec**
* The header gains `saved_unix` and `map_name`, a translation key from a new
  `RpgMapRoot.display_name` export (default `MAP_<ID>`). These are optional fields, so
  `save_version` stays 1.
* A slot reads, for example, "Slot 2 — Village · Lv 3 · 1:12 played · 12 Oct 14:05", in local
  time.
* Saving over a used slot asks for confirmation, with the focus on "No".
* A 160×90 thumbnail is saved next to the slot (skipped headless) and shown on the button.
* The loops use `SaveManager.SLOTS`. Bump `RECIPE_VERSION` in `ui_recipes.gd`.

**Tests**
* The header fields.
* The slot text with a fixed time.
* The confirmation path in the smoke test, through an auto-confirm hook.

**Done when**
* The tests pass and the integration smoke lists are updated.

---

# Part D — Features

The twenty additions from the review. All of them land before 1.0, and the ground rules on save
data, smoke steps and demo content apply to each.

## T12.45 — Equipment

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_runtime/core/game_state.gd`, `data/item_definition.gd`, `data/stats.gd`, `data/inventory.gd`, `ui/inventory_menu.gd`, `ui/status_menu.gd`, `ui/strings.gd`, `archetypes/arpg/player_combat.gd`, `archetypes/turn_based/battle_math.gd` (all under `godot_templates/addons/rpg_runtime/`), `godot_templates/builder/recipes/data_recipe.gd`, `godot_templates/builder/recipes/ui_recipes.gd`, `godot_templates/builder/smoke/smoke_steps_m6.gd`, `godot_templates/tests/unit/test_inventory.gd`, `test_stats.gd`, `test_save_manager.gd`, `tests/integration/test_m6_sample.py`

The pieces exist but are not connected:

* Items have the categories WEAPON, ARMOR and ACCESSORY, and `modifiers`
  (`item_definition.gd:13`).
* `RpgStats.get_stat(name, modifiers)` applies modifiers (`stats.gd:24`).

There is no equipped state and no way to equip anything, so weapons and armour do nothing.

**Spec**
* `GameState.equipment: {actor_id: {"weapon": id, "armor": id, "accessory": id}}`. It is keyed by
  actor from the start, for T12.47.
* Equipping moves an item between the inventory and the slot. `equipped_modifiers(actor_id)` feeds
  every `get_stat` call.
* Inventory menu: "Equip" on equipable items. Status menu: the slots, and the stat changes (green
  or red) before confirming.
* Both combat systems read attack and defence through `get_stat`; fix any direct field read.
* `data_recipe` seeds a starter weapon and armour (user_seed) from ITEM assets whose names suggest
  them: sword, axe and bow for weapons; armor, shield and helmet for armour.
* Save: `equipment` is an optional key that `GameState.from_dict` defaults to empty slots, so
  `save_version` stays 1 (ground rules).
* Smoke: equip the sword, and the attack stat rises.

**Tests**
* Modifier sums.
* Equip and unequip swaps.
* A save without `equipment` loads with empty slots, and equipment survives a save round trip.
* The integration smoke lists.

**Done when**
* The tests pass on both archetypes.

---

## T12.46 — Shops

**Depends on:** T12.45
**Files:** `godot_templates/addons/rpg_runtime/data/shop_definition.gd` (new), `ui/shop_menu.gd` (new), `dialogue/dialogue_runner.gd`, `ui/strings.gd`, `godot_templates/builder/recipes/ui_recipes.gd`, `godot_templates/builder/recipes/starter_map_recipe.gd`, smoke steps, GDScript tests

Items have a `value` (`item_definition.gd:12`) and gold is earned in both archetypes, but there is
nothing to spend it on.

**Spec**
* `ShopDefinition` holds items, optional prices, and a sell ratio (default 0.5).
* A dialogue event `open_shop:<id>` opens the shop. Events are strings, like `set_flag:`.
* Buying and selling respect gold and stack limits.
* The menu is fully navigable by gamepad; the validator checks the focus chain.
* Demo (new projects): the villager offers a shop after the first talk.

**Tests**
* Buying takes gold and adds the item.
* Buying is refused without enough gold.
* Selling works.
* The focus chain is valid.

**Done when**
* The tests and the smoke step pass.

---

## T12.47 — Party members (turn-based)

**Depends on:** T12.45
**Files:** `godot_templates/addons/rpg_runtime/core/game_state.gd`, `data/actor_definition.gd`, `dialogue/dialogue_runner.gd`, `archetypes/turn_based/battle_controller.gd`, `archetypes/turn_based/ui/battle_ui.gd`, `ui/status_menu.gd`, builder recipes, smoke steps, GDScript tests

`GameState.party` is marked "reserved" (`game_state.gd:10`). The battle controller already works
with a party array (`battle_controller.gd:40`, `66`), but builds it from the player alone.

**Spec**
* Events `join_party:<actor_id>` and `leave_party:<actor_id>`, with at most 4 members.
* In battle, every member acts and the target cursor covers the party.
* Experience is shared.
* The status menu pages through the members, and each has their own equipment (T12.45).
* The action RPG gets no followers in 1.0; document that.

**Tests**
* Joining and leaving.
* Turn order with two members.
* The party survives save and load.

**Done when**
* The tests pass.

---

## T12.48 — Quest journal

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_runtime/data/quest_definition.gd` (new), `core/game_state.gd`, `dialogue/condition.gd`, `dialogue/dialogue_runner.gd`, `ui/journal_menu.gd` (new), `ui/pause_menu.gd`, `godot_templates/builder/recipes/ui_recipes.gd`, `godot_templates/builder/recipes/data_recipe.gd`, smoke steps, GDScript tests

`GameState.quests` exists (`game_state.gd:19`) and dialogue conditions use it, but there is no
quest definition and no screen.

**Spec**
* `QuestDefinition` has:
  * an id and a title key;
  * stages, each `{id, description key, complete_when: condition}`;
  * rewards (gold, experience, items).
* Events: `quest_start:`, `quest_stage:<id>:<stage>` and `quest_complete:`. Conditions:
  `quest_active:`, `quest_stage:` and `quest_done:`.
* A Journal in the pause menu, with Active and Completed tabs, and a notification on every stage
  change.
* Demo (new projects): "Talk to the elder → open the chest → return".

**Tests**
* Condition evaluation.
* Rewards are given on completion.
* The journal lists the quests.
* Quests survive a save round trip.

**Done when**
* The tests pass.

---

## T12.49 — Import Tiled and LDtk maps

**Depends on:** T12.25 (the Options page)
**Files:** `rpggen/core/adapters/tiled.py`, `rpggen/core/adapters/ldtk.py`, `rpggen/core/catalog.py`, `rpggen/schema/catalog.schema.json`, `docs/spec/02_SCHEMAS.md`, `godot_templates/builder/recipes/imported_maps_recipe.gd` (new), `godot_templates/builder/lib/map_build.gd`, `rpggen/gui/pages/options_page.py`, `docs/spec/03_ERROR_CODES.md`, `tools/make_synthetic_packs.py`, new synthetic packs and goldens, tests

* `.tmx` files are read only for their tilesets (`tiled.py:193-197`).
* LDtk levels are ignored, and IntGrid collision only raises the pack warning
  `ldtk_intgrid_collision_available` (`ldtk.py:78`).

Packs that ship sample maps lose them.

**Spec**
* The catalog gets an optional `maps` list:
  * `{id, source, tile_size, layers: [{name, kind: tiles|intgrid|objects, tileset, cells}]}`;
  * cells are run-length encoded.

  Python parses; Godot builds.
* **Tiled:**
  * Tile layers in CSV, base64, zlib or gzip. Zstd is reported as `TILE-009` and the layer is
    skipped.
  * Flip flags become TileSet alternative tiles.
  * Object layers named spawn, door or sign become markers.
  * Infinite maps are flattened to their bounds.
* **LDtk:**
  * Tile and auto-layer `gridTiles`.
  * IntGrid becomes a collision layer. The audit chooses which IntGrid values are solid.
* The builder writes `game/maps/imported/<pack>/<map>.tscn` (user_seed) with the project's TileSets
  and the catalog's source ids.
  * Layers map to `map_layers` by name, or are appended.
  * A layer with an unknown tileset gives `TILE-009` (W) and is skipped.
* Options lists the imported maps with a checkbox each, and can make one the starter map. The
  planner is then skipped.

**Tests**
* New synthetic packs `tiled_map` and `ldtk_level`.
* A cell round trip, checked by the validator as the starter map is.
* Flipped tiles.
* IntGrid collision.

**Done when**
* The tests pass and both packs generate and pass the smoke test.

---

## T12.50 — Frame sequences and more actions

**Depends on:** nothing
**Files:** `rpggen/core/adapters/sequences.py` (new), `rpggen/core/adapters/__init__.py`, `rpggen/core/adapters/strips.py`, `rpggen/core/adapters/naming.py`, `godot_templates/builder/recipes/sprite_frames_recipe.gd`, `godot_templates/addons/rpg_runtime/actors/animation_driver.gd`, `docs/spec/03_ERROR_CODES.md`, `tools/make_synthetic_packs.py`, `tests/golden/sequences.catalog.json` (new), `docs/adapters.md`

* `STRIP_NAME` (`strips.py:18-22`) matches only whole strips named `<name>_<action>[_<dir>]`, plus
  GIFs. Numbered single frames such as `hero_walk_down_01.png`, `hero/walk/0001.png` or
  `Walk (3).png` each become a separate asset.
* The actions are limited to idle, walk, run, attack, hurt, death, die, hit and move. The
  directions are limited to four, plus s, n, e and w.

**Spec**
* A `SequencesAdapter` runs before strips. It groups files by folder and by stem without the
  trailing number; the separators are `_`, `-`, a space, or `(n)`.
  * A group needs at least two frames of identical size.
  * Frames are sorted numerically, so 10 comes after 9.
  * A gap in the numbers gives `ADAPT-004` (W).
* Frames are composited into `generated/frame_strips/<sha>.png`, as GIF strips are
  (`strips.py:39`), so each animation uses one atlas. The originals stay in `assets/packs`.
* New actions: jump, fall, cast, shoot, slash, thrust, block, roll, dash, climb, swim and interact.
* New directions: down_left, down_right, up_left, up_right, and sw, se, nw, ne.
  * 8-direction sets map to names such as `idle_down_left`.
  * The `AnimationDriver` picks the nearest direction that exists.

**Tests**
* A synthetic `sequences` pack: numbered frames, `(n)` frames, folder-per-animation, and one with a
  gap.
* The golden catalog.
* Numeric sorting.
* 8-direction selection in the driver.

**Done when**
* The tests pass and accuracy thresholds still hold.

---

## T12.51 — Credits screen from pack licences

**Depends on:** nothing
**Files:** `rpggen/core/licenses.py` (new), `rpggen/core/catalog.py`, `rpggen/schema/catalog.schema.json`, `rpggen/gui/pages/audit_page.py`, `godot_templates/addons/rpg_runtime/ui/credits_menu.gd` (new), `godot_templates/addons/rpg_runtime/ui/title_screen.gd`, `godot_templates/addons/rpg_runtime/ui/pause_menu.gd`, builder recipes, `docs/spec/03_ERROR_CODES.md`, tests

CC-BY packs require attribution in the game. Today the licences appear only in
`GENERATION_REPORT.md`.

**Spec**
* Detect each licence from the licence files: CC0, CC-BY x.y, CC-BY-SA, OGA-BY, MIT, "commercial
  use" wording, and RPG Maker terms. Also detect author and URL lines.
* Each catalog pack gets `{license_id, author, url, attribution_required}`. When attribution is
  required but no author is found, raise `ASSET-028` (W).
* The Audit page gets editable pack information: author, URL and licence.
* The game gets Credits on the title screen and in the pause menu.
  * The data is generated, so a regeneration updates it.
  * `game/data/credits_extra.tsv` (user_seed) adds the user's own lines.

**Tests**
* Detection on fixture licence texts.
* The generated credits data.
* `ASSET-028`.

**Done when**
* The tests pass, and the sample project shows a credits screen.

---

## T12.52 — Web, Linux and macOS export presets

**Depends on:** T12.07, T12.25 (the Options page)
**Files:** `godot_templates/project_files/export_presets.template.cfg`, `rpggen/core/export_check.py`, `rpggen/core/config.py`, `rpggen/schema/config.schema.json`, `rpggen/gui/pages/options_page.py`, `docs/godot_api_verified.md`, `docs/user_guide.md`, tests

The only preset is Windows Desktop (`export_presets.template.cfg:4`). Web builds for itch.io and
Linux builds are common requests.

**Spec**
* Add Web, Linux and macOS presets, rendered from verified templates like the Windows one.
  * Web: thread support off, for itch.io compatibility.
  * macOS: unsigned.
  * Verify every preset key and the renderer requirement for Web against 4.7.2 with a probe.
* Options gets "Export targets" checkboxes; Windows is on by default. The optional config key is
  `export_targets`.
* The export check runs per selected target whose templates are installed. Skips are reported as in
  T12.07.

**Tests**
* The presets render deterministically.
* The export check runs per platform (integration; skipped when templates are absent).

**Done when**
* The tests pass.

---

## T12.53 — Random-encounter zones

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_runtime/world/encounter_zone.gd` (new), `data/encounter_table.gd` (new), `archetypes/turn_based/turn_based_mode.gd`, `godot_templates/addons/rpg_project_tools/dock/placement.gd`, `godot_templates/addons/rpg_project_tools/tools/content_checks.gd`, `godot_templates/builder/recipes/second_map_recipe.gd`, smoke steps, GDScript tests

Today the turn-based archetype only has visible overworld enemies.

**Spec**
* An `EncounterZone` is an Area2D polygon, or a cell painted on an "Encounters" layer.
* An `EncounterTable` lists enemy groups with weights.
* The encounter rate counts steps in tiles moved, with grace steps after a battle. The RNG is the
  seeded one from `GameState`.
* A zone can be switched off by a flag.
* A dock tool creates a zone over the current selection.
* Demo (new projects): one zone on the second map.
* Turn-based only. Action-RPG spawners are out of scope; document that.

**Tests**
* A deterministic encounter after N steps with a fixed seed.
* The grace period.
* Disabling by flag.

**Done when**
* The tests and the smoke step pass.

---

## T12.54 — Event sequencer

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_runtime/events/sequence.gd` (new), `events/sequence_runner.gd` (new), `world/trigger_area.gd` (new), `dialogue/dialogue_runner.gd`, `core/save_manager.gd`, `godot_templates/addons/rpg_project_tools/dock/asset_inspector.gd`, GDScript tests

**Spec**
* A `Sequence` resource holds a list of commands:
  * `move_actor(entity_id, tiles)` and `face`;
  * `wait`;
  * `fade_out` and `fade_in`;
  * `play_sound(slot)`;
  * `show_dialogue`;
  * `give_item` and `take_item`;
  * `set_flag`;
  * `start_battle(group)`;
  * `change_map(map, spawn)`;
  * `camera_pan`.
* While a sequence runs, player input is blocked. It can be skipped with cancel when it is marked
  skippable.
* Sequences are deterministic.
* Autosave is blocked while one runs, the same guard as for dialogue in `can_autosave`.
* Triggers:
  * entering an area, once per flag;
  * interacting with something;
  * the dialogue event `run_sequence:<id>`.

**Tests**
* A unit test per command.
* A sequence runs in order headless.
* Autosave is blocked while it runs.

**Done when**
* The tests pass.

---

## T12.55 — Input glyphs

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_runtime/ui/input_glyphs.gd` (new), the prompt users (interaction prompt, battle hints, title, settings remap), `godot_templates/addons/rpg_runtime/LICENSE`, `THIRD_PARTY_NOTICES.md`, GDScript tests

ARCHITECTURE §26 promises an `InputGlyphs` helper, but no code exists, and prompts show fixed text.

**Spec**
* Track the last input device: keyboard and mouse, or a joypad. For joypads, detect the
  Xbox / PlayStation / Nintendo layout from the joy name.
* `glyph(action)` returns a texture, or a text label, for the first binding of that device class.
  It respects remapped keys.
* Prompts update when the device changes.
* Any bundled glyph art must be CC0 and recorded. Otherwise use text glyphs only, such as "[E]".

**Tests**
* Switching devices.
* A remapped key is shown.
* An unknown pad falls back to text.

**Done when**
* The tests pass.

---

## T12.56 — Languages: in-game picker and wizard translations

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_runtime/core/settings.gd`, `ui/settings_menu.gd`, `ui/strings.gd`, `rpggen/gui/app.py`, `rpggen/gui/i18n/*.ts` (new), `tools/update_translations.py` (new), `packaging/rpggen.spec`, `rpggen/core/app_settings.py`, `rpggen/gui/window_menus.py`, `CONTRIBUTING.md`, tests

* The game builds one Translation per locale column of `game/i18n/strings.tsv`, but its settings
  have no language option.
* The wizard calls `tr()` everywhere, but no `QTranslator` is ever installed, and there are no
  `.ts` or `.qm` files in the repository.

**Spec**
* Game:
  * A language option lists the locales in `generated/i18n` plus "System".
  * It is stored in `settings.cfg` and applied with `TranslationServer.set_locale`.
  * Menus rebuild their text on `changed`.
* Wizard:
  * `pyside6-lupdate` extracts the strings to `rpggen/gui/i18n/rpggen_<lang>.ts`.
  * `lrelease` runs at build time.
  * The `QTranslator` follows the setting, or the OS.
* Start with one community language as a pilot, and document the process in CONTRIBUTING.
* Error messages stay English for now; they are documented by code.

**Tests**
* Switching the game's locale changes a label.
* The wizard loads a test `.qm` and a page title changes.
* A missing translation falls back to English.

**Done when**
* The tests pass.

---

## T12.57 — Contact sheet export

**Depends on:** nothing
**Files:** `rpggen/core/contact_sheet.py` (new), `rpggen/gui/pages/audit_page.py`, `rpggen/gui/window_menus.py`, tests

ARCHITECTURE §13 promises a PNG or PDF contact sheet for offline review, but it does not exist.

**Spec**
* Each page shows the current filtered set, or all assets. For each asset:
  * the thumbnail (optionally with the grid overlay);
  * the file name, role and status;
  * the confidence;
  * the tile or frame size.
* Output as PNG, or as PDF through `QPdfWriter`, so no new dependency. A4 or Letter.
* It runs in a worker.

**Tests**
* The page count for N assets.
* The PDF header bytes.
* A deterministic PNG for a fixed input.

**Done when**
* The tests pass.

---

## T12.58 — Conflict resolver for `.rpggen-new` files

**Depends on:** T12.40
**Files:** `rpggen/core/conflicts.py` (new), `rpggen/core/ledger.py`, `rpggen/schema/ledger.schema.json`, `rpggen/core/promote.py`, `rpggen/gui/dialogs/conflict_dialog.py` (new), `rpggen/gui/pages/results_page.py`, `rpggen/gui/window_menus.py`, `rpggen/cli.py`, tests

A conflict writes `<file>.rpggen-new` beside the user's file (`promote.py:231`) and raises
`REGEN-001`. Merging is manual, and the conflict comes back on every regeneration while the
generated content differs.

**Spec**
* List the files of a project that have a `.rpggen-new` sibling.
* Show three versions: the base (the version rpggen last wrote, from the newest backup that holds
  it), the user's, and the new one. Without a base, show two.
* Actions, each backed up first:

  | Action | What it does |
  |--------|--------------|
  | Keep mine | Deletes `.rpggen-new` and records the declined content as the ledger entry's new optional `declined_sha256`. Promotion then skips the conflict while the generated content still has that hash. |
  | Take new | Replaces the file and updates the ledger hash. |
  | Merge | Line-based three-way merge with conflict markers, for text files. `.tscn` and `.tres` files get a warning to validate in Godot afterwards. |

* CLI: `rpggen conflicts --target X [--keep-mine|--take-new] <file>`.

**Tests**
* After Take new, the next regeneration overwrites freely.
* Keep mine suppresses the conflict until the generated content changes.
* A merge produces markers.

**Done when**
* The tests pass, and `docs/regeneration.md` documents the resolver.

---

## T12.59 — Learn from my corrections

**Depends on:** nothing
**Files:** `rpggen/core/learned_rules.py` (new), `rpggen/core/adapters/learned.py` (new), `rpggen/core/adapters/__init__.py`, `rpggen/gui/edits.py`, `rpggen/gui/dialogs/learned_rules_dialog.py` (new), `docs/profiles.md`, tests

**Spec**
* When the user changes a role, usage or collision on assets whose folder or name tokens share a
  pattern, record a rule `{pattern → facet values, hits, misses}` in the data folder. It is never
  uploaded.
* A learned adapter runs after the profile adapters and before the heuristics.
  * Its confidence comes from the hit rate, capped at 0.85, so assets stay "Auto-detected".
  * The audit says "Why: learned from your earlier fixes (n times)".
* Settings → Learned rules lets the user list, disable and delete rules, and export them as
  folder rules.

**Tests**
* Rules are created from edits.
* They apply on a new synthetic pack.
* The confidence cap holds.
* Disabling a rule works.

**Done when**
* The tests pass, and the privacy section of the user guide mentions the rules file.

---

## T12.60 — Custom recipe hook

**Depends on:** nothing
**Files:** `godot_templates/builder/build.gd`, `godot_templates/builder/lib/build_context.gd`, `godot_templates/builder/validate.gd`, `godot_templates/project_files/README.template.md`, `docs/recipes.md` (new), GDScript tests

**Spec**
* After the standard recipes, `build.gd` runs every `res://game/builder_recipes/*.gd` in name order.
  Each must extend `RefCounted` with `func build(ctx) -> void`.
  * The `ctx` API is documented as stable for 1.x, and `RECIPE_API_VERSION` marks it.
  * Outputs go under `game/` (user-owned) or `generated/custom/` (ledger-managed, rewritten each
    run).
* A failing recipe is `BUILD-002`, naming the recipe, and fails the build.
* New projects get a commented sample recipe (user_seed).

**Tests**
* A custom recipe creates a scene.
* A failing recipe is reported by name.
* Recipes run in name order.

**Done when**
* The tests pass.

---

## T12.61 — Dialogue authoring dock

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_project_tools/dock/dialogue_tab.gd` (new), `godot_templates/addons/rpg_project_tools/plugin.gd`, `godot_templates/addons/rpg_runtime/dialogue/json_import.gd`, `godot_templates/tests/unit/test_tools_dock.gd`

**Spec**
* A dock tab lists the resources in `game/data/dialogue`. Each line can be edited:
  * speaker;
  * portrait, from the PORTRAIT assets;
  * text, with a BBCode preview;
  * choices, condition and event.
* Undo goes through `EditorUndoRedoManager`.
* **Test** plays the dialogue against a mock `GameState` whose flags and items can be toggled.
* JSON export is added (import already exists).
* Unknown events and conditions are flagged inline.

**Tests**
* An edit round trip saves the resource.
* The condition preview.
* JSON export and import round-trip.

**Done when**
* The tests pass.

---

## T12.62 — Lighting and day/night

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_runtime/world/light_source.gd` (new), `godot_templates/addons/rpg_runtime/world/map_root.gd`, `godot_templates/addons/rpg_runtime/core/settings.gd`, `godot_templates/builder/recipes/object_scenes_recipe.gd`, `godot_templates/builder/recipes/interior_recipe.gd`, `rpggen/core/classifier.py`, `docs/godot_api_verified.md`, GDScript tests

**Spec**
* Each map gets an ambient colour through `CanvasModulate`: day outdoors, dimmer in interiors.
* Objects tagged `light` get a `PointLight2D`, with an optional flicker. The tag is suggested from
  names: torch, lamp, lantern, candle, campfire.
  * The light texture is generated by the builder, never written by hand.
  * Lights outside the camera are culled.
* An optional time-of-day cycle, off by default, drives the outdoor ambient.
* Verify support under the compatibility renderer with a probe.

**Tests**
* A tagged object's scene has a light.
* The interior ambient.
* The cycle is deterministic at a fixed time.

**Done when**
* The tests pass.

---

## T12.63 — Linux and macOS app packages

**Depends on:** T12.10, T12.21
**Files:** `tools/package.py`, `packaging/rpggen.spec`, `packaging/linux/` (new: `.desktop` file, AppImage recipe), `.github/workflows/release.yml`, `rpggen/core/godot_fetch.py`, `rpggen/godot_target.py`, `rpggen/core/godot.py`, `docs/release.md`, `README.md`

The code and CI already run on Linux, and `godot_fetch` already supports Linux. Only Windows builds
are packaged.

**Spec**
* Linux: a PyInstaller one-folder build on `ubuntu-22.04` (for the glibc floor), shipped as an
  AppImage and a tar.gz.
* macOS: an arm64 or universal2 `.app` in a zip, unsigned at first; notarization is documented as
  a later step.
* The frozen smoke test runs on each runner.
* Godot download for macOS (the `macos.universal` zip, with the executable inside the `.app`) has a
  pinned hash (T12.21).
* `auto_find_godot` searches each OS's usual places: `~/.local/bin` and `/Applications/Godot.app`.
* The README stops saying "only Windows builds are packaged for 1.0" and lists the three
  platforms, with the SmartScreen section kept for Windows and a Gatekeeper note for unsigned macOS
  builds.

**Tests**
* The frozen smoke test on each runner.
* `godot_fetch` file names per platform.
* The auto-find paths.

**Done when**
* The release workflow attaches all three platforms with SHA-256 sums.

---

## T12.64 — Minimap and world map

**Depends on:** nothing (the quest markers need T12.48)
**Files:** `godot_templates/builder/recipes/minimap_recipe.gd` (new), `godot_templates/builder/tools/dump_map_view.gd`, `godot_templates/addons/rpg_runtime/ui/minimap.gd` (new), `godot_templates/addons/rpg_runtime/ui/world_map_menu.gd` (new), `godot_templates/addons/rpg_runtime/ui/pause_menu.gd`, `godot_templates/addons/rpg_runtime/core/settings.gd`, `godot_templates/addons/rpg_runtime/core/game_state.gd`, GDScript tests

**Spec**
* The builder renders one minimap per map from the TileMapLayer cells. Each cell gets the average
  colour of its tile, computed at build time. The image is saved with `ResourceSaver` as an
  `ImageTexture` resource, so there is no second import pass.
* "Regenerate affected resources" updates the minimaps of user maps.
* A HUD minimap corner, with a settings toggle:
  * a player dot;
  * markers for doors, unopened chests and quest targets (T12.48).
* A world map in the pause menu shows visited maps, with fog of war over unvisited cells. Visited
  cells are saved as compact bitsets under an optional save key (ground rules).

**Tests**
* The minimap size equals the map's used rect.
* The markers.
* Fog survives a save.

**Done when**
* The tests pass.

---

# Part E — Ship 1.0.0

## T12.65 — Documentation, screenshots and changelogs

**Depends on:** every Part A–D card
**Files:** `docs/user_guide.md`, `docs/images/*`, `README.md`, `CHANGELOG.md`, `godot_templates/addons/rpg_runtime/CHANGELOG.md`, `godot_templates/addons/rpg_runtime/README.md`, `godot_templates/project_files/README.template.md`, `godot_templates/project_files/README.turn_based.md`, `godot_templates/project_files/README.arpg.md`, `docs/regeneration.md`, `docs/adapters.md`, `docs/profiles.md`, `docs/recipes.md`, `docs/errors.md` (generated), `docs/spec/00_START_HERE.md`, `docs/dev/implementation_notes.md`

* Regenerate the screenshots with `python tools/make_doc_screenshots.py --godot <exe>`. Mapping must
  show full rows, and Audit no empty band. Add pictures for the new wizard surfaces (pack cards,
  regeneration preview, conflict resolver, Storage dialog).
* The user guide covers:
  * the storage folders and the Storage dialog;
  * the git pack-art choice;
  * the regeneration preview and the conflict resolver;
  * skipped checks;
  * the CLI's `--json`, exit codes, `--tile-size`, `--dry-run`, `--confirm` and `conflicts`;
  * imported Tiled and LDtk maps, frame sequences, export targets, learned rules and the contact
    sheet;
  * the wizard's language setting.
* The generated READMEs (template plus the archetype parts) explain the game features a user will
  edit: equipment, shops, party, quests, encounter zones, sequences, credits, lighting, minimap,
  custom recipes and the dialogue dock.
* `docs/adapters.md` describes the sequences adapter; `docs/recipes.md` (new in T12.60) is linked
  from the README's documentation table.
* Add both changelogs' entries under 1.0.0.
* Add M11 and M12 to the reading list in `00_START_HERE.md`.

**Done when**
* `test_the_screenshots_match_the_files_the_guide_uses` passes, every new code is in
  `docs/errors.md`, and every Part D card has a section in the user guide or a generated README.

---

## T12.66 — Gate (1.0.0)

**Depends on:** T12.65, T10.10

* Every suite is green on Windows and Ubuntu, on both PySide6 legs. Perf is within its ceilings.
* The frozen smoke test passes on Windows, Linux and macOS (T12.63).
* T12.16 passes at the minimum size in both themes for both archetypes.
* Every smoke list asserted by the integration tests includes the new steps, and both archetypes
  pass the smoke test on the sample pack and every synthetic pack, including the new `sequences`,
  `tiled_map` and `ldtk_level` packs.
* `docs/coverage.md` has the held-out table filled (T10.09 and T10.10, ideally with T12.26), with no
  `*(pending)*`. These runs happen **after** T12.49 and T12.50 land, because both change detection.
  The release workflow enforces this (T12.15).
* The M11 manual pass (T11.29) is repeated in full, extended with one row per Part D feature:
  * Equip, buy and sell, recruit, and finish the demo quest.
  * Walk an encounter zone and run a sequence.
  * Switch the game's language and open the credits.
  * Use the minimap, world map and lighting.
  * Use the dialogue dock and a custom recipe in the editor.
  * Import a Tiled and an LDtk map, and export to Web, Linux and macOS.
  * Resolve a conflict, and check learned rules on a second pack.
* The lock file is current, and the actions are pinned.

**Done when** all of the above is true; then tag `v1.0.0`.

---

# Appendix — Review items to cards

The review of 2026-10-07 listed 15 findings, 20 improvements, 20 additions and 20 UI/UX
improvements. Every item maps to exactly one card; several cards carry more than one item.

| Review item | Card |
|-------------|------|
| Finding 1: Mapping rows squeezed | T12.01 |
| Finding 2: hashing on the GUI thread, whole archive in RAM | T12.02 |
| Finding 3: `base_tile_size` always 16 | T12.03 |
| Finding 4: CLI ignores mistyped flags | T12.04 |
| Finding 5: editor-open false positive | T12.05 |
| Finding 6: analysis Cancel and progress | T12.06 |
| Finding 7: skipped checks look like passes | T12.07 |
| Finding 8: save backup and untranslated messages | T12.08 |
| Finding 9: RAR/7z trust, links, nested budget | T12.09 |
| Finding 10: user data in a cache folder; unbounded caches | T12.10 |
| Finding 11: recent projects erased; settings read every second | T12.11 |
| Finding 12: git commits | T12.12 |
| Finding 13: thread race on the timeout | T12.13 |
| Finding 14: Audit layout | T12.14 |
| Finding 15: release process, gate, CONTRIBUTING | T12.15 |
| Improvement 1: parallel analysis | T12.17 |
| Improvement 2: folder inventory cache | T12.18 |
| Improvement 3: hash once | T12.02 |
| Improvement 4: live Godot output | T12.19 |
| Improvement 5: lean failed runs | T12.20 |
| Improvement 6: size-capped caches | T12.10 |
| Improvement 7: pinned Godot hash | T12.21 |
| Improvement 8: reproducible, gated releases | T12.15 |
| Improvement 9: PySide6 matrix | T12.22 |
| Improvement 10: faster editor detection | T12.05 |
| Improvement 11: settings service | T12.11 |
| Improvement 12: crash report | T12.23 |
| Improvement 13: unified logs | T12.24 |
| Improvement 14: page view-models | T12.25 |
| Improvement 15: layout regression test | T12.16 |
| Improvement 16: real-pack corpus | T12.26 |
| Improvement 17: performance trends | T12.27 |
| Improvement 18: scriptable CLI | T12.28 (`--tile-size` in T12.03) |
| Improvement 19: strict GDScript | T12.29 |
| Improvement 20: resumable download | T12.21 |
| Additions 1–20 | T12.45 – T12.64, in the same order |
| UX 1: Quit vs Cancel | T12.30 |
| UX 2: laptop minimum size | T12.30 |
| UX 3: audio and font cards | T12.31 |
| UX 4: role badges | T12.31 |
| UX 5: filter bar | T12.32 |
| UX 6: pack cards | T12.33 |
| UX 7: archetype art | T12.34 |
| UX 8: sidebar status | T12.35 |
| UX 9: inline candidates | T12.36 |
| UX 10: Options summary | T12.37 |
| UX 11: map legend | T12.38 |
| UX 12: phase states | T12.07 |
| UX 13: live sub-step and log | T12.19 |
| UX 14: Play and Open starter map | T12.39 |
| UX 15: grouped warnings | T12.39 |
| UX 16: regeneration preview | T12.40 |
| UX 17: one-click fixes | T12.41 |
| UX 18: system theme | T12.42 |
| UX 19: change history | T12.43 |
| UX 20: save and load screens | T12.44 |

**Where this plan corrects the review**

* **UX 10.** The Options page already has a collapsed Advanced section (`options_page.py:404`), so
  T12.37 adds only the summary.
* **Finding 15.** No tag exists, so 1.0.0 is not released. The open gate is something to enforce
  (T12.15, T12.66), not a published mistake.
* **Finding 7.** Turning the smoke test off is only possible through a config file; the GUI has no
  toggle.
