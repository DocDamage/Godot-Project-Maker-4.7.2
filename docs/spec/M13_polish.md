# M13 — Polish and Feature Depth (release 1.1.0)

**Goal:** land the twenty improvements of the review of 2026-10-08 as the first release after
1.0. Part A is wizard UX, Part B deepens features that exist, Part C adds three features and the
lock-and-key planner that the connected-maps feature and M14 share, Part D is the documentation
and the gate. **This milestone starts after `v1.0.0` is tagged** (T12.66) and ends with
`v1.1.0`. The Metroidvania archetype is M14 (release 1.2.0).

This file follows the format of M01–M12. It was written against commit `9726d0e` and revised the
same day to move it after the 1.0 tag. The appendix maps every item of the review to the card
that carries it.

## Ground rules for this milestone

* The M12 ground rules apply unchanged (`M12_review_followups.md`): core logic stays out of the
  GUI, pages only edit `WizardState`, every edit is undoable, generated output is deterministic,
  `.tscn`, `.tres` and `project.godot` are never written by hand, every Godot API is verified
  before use, recipe changes bump `RECIPE_VERSION`, new smoke steps are added to the lists the
  integration tests assert, and T12.16 stays green at the minimum window size in both themes.
* **This is the first milestone after a release, so compatibility is now a contract.**
  * The app and the runtime become **1.1.0**. `REGEN-006` asks for confirmation only on a major
    runtime change, so a 1.0 project regenerates into 1.1 without a prompt; everything in this
    milestone must therefore be safe for a project made by 1.0: no generated-owned script is
    moved, renamed or removed, and no `class_name` changes.
  * `config_version` stays 1. Config changes are additive and optional with defaults, `to_json`
    omits a key at its default, and a 1.0 config file loads unchanged.
  * `save_version` stays 1 as long as every new save key is optional with a default that
    `GameState.from_dict` applies, so a 1.0 save loads in a 1.1 game. A key whose **meaning**
    changes bumps `save_version` and ships a migration with a test over a 1.0 save fixture
    (`godot_templates/tests/fixtures/saves/v1_0.json`, added by the first card that needs it).
  * The runtime changelog gets a `1.1.0` heading; T12.08's text keys follow the "older projects
    get the English default" rule.
* **New error codes** go into `03_ERROR_CODES.md` first, then `python tools/gen_error_codes.py`.
  Codes reserved by this milestone: `ASSET-029`, `CAT-006`, `VAL-027`, `VAL-028` (the last two
  are **warnings**: a world a person has edited may be intentionally unreachable).
* **Dependencies.** Two new Python dependencies are allowed: `zstandard` (T13.14, optional
  extra that the packages always include) and `soundfile` (T13.17: libsndfile, decodes WAV,
  OGG Vorbis, FLAC and MP3; BSD wrapper over an LGPL library, which `THIRD_PARTY_NOTICES.md`
  must say). Record both in `pyproject.toml`, the lock files, `THIRD_PARTY_NOTICES.md` and
  `packaging/rpggen.spec`, and check that the frozen build on all three systems carries the
  libsndfile binary (`tools/package.py --smoke` plays a WAV and an OGG through it).
* **Demo content stays small.** The top-down demo gains only what T13.12 and T13.20 say, and only
  in new projects.
* After any change to detection or the sample pack, run `python -m rpggen.dev update-goldens` and
  `python tools/build_sample_pack.py`, and review the diff. T13.04 and T13.18 touch the catalog;
  the corpus (T12.26) must be unchanged on all four measures after each.

## Order of work

| Step | Tasks | Why this order |
|------|-------|----------------|
| 1 | T13.14, T13.13, T13.11, T13.21 | Small and independent; the planner first so T13.20 can use it |
| 2 | T13.01 – T13.10 | Wizard UX |
| 3 | T13.12, T13.15, T13.16, T13.17 | Feature improvements |
| 4 | T13.18, T13.19, T13.20, T13.24 | Feature additions; T13.20 after T13.12 and T13.21, T13.24 after T13.20 |
| 5 | T13.22 – T13.23 | Docs, screenshots and the gate, then tag `v1.1.0` |

Tasks inside a step are independent unless **Depends on** says otherwise.

## Index

Sizes are rough: **S** under a day, **M** 1–3 days, **L** 3–7 days, **XL** more than a week.

| Card | Title | Size | Depends on | Status |
|------|-------|:----:|------------|--------|
| T13.01 | Audit review mode | M | — | done |
| T13.02 | Audit grid grouped by folder | M | — | done |
| T13.03 | Live preview in the detail panel | M | — | done |
| T13.04 | Select similar assets | M | — | done |
| T13.05 | Mapping: picker gallery and jump to the audit | S | — | done |
| T13.06 | Factory presets and option dependencies | S | — | done |
| T13.07 | Remaining time on the Generate page | S | — | done |
| T13.08 | Project dashboard on the welcome view | M | — | done |
| T13.09 | First-run tour | S | — | done |
| T13.10 | Accessibility and display scaling | M | — | done |
| T13.11 | Shops: quantities and sell all | S | — | done |
| T13.12 | One interior per house | M | — | done |
| T13.13 | Validator: every id, inline in the dialogue tab | S | — | done |
| T13.14 | Zstandard for Tiled and LDtk | S | — | done |
| T13.15 | Followers in the action RPG | M | — | done |
| T13.16 | Custom sound slots | M | — | done |
| T13.17 | Audio audit: waveforms and loop points | M | — | done |
| T13.18 | Recolour variants | L | — | done |
| T13.19 | Quest and cutscene tabs in the dock | L | T13.13 | done |
| T13.20 | A world of connected maps | L | T13.12, T13.21 | done |
| T13.21 | Lock-and-key planner | S | — | done |
| T13.22 | Documentation, screenshots and changelogs | M | Parts A–C | done |
| T13.23 | Gate (1.1.0) | M | T13.22 | open |
| T13.24 | World repair: unpaired doors and unreachable maps fix themselves (added 2026-10-08) | M | T13.20 | done |

---

# Part A — Wizard UX

## T13.01 — Audit review mode

**Depends on:** nothing
**Files:** `rpggen/gui/widgets/review_mode.py` (new), `rpggen/gui/pages/audit_page.py`,
`rpggen/gui/widgets/asset_detail.py`, `rpggen/gui/window_menus.py`, `tests/gui/test_review_mode.py`
(new)

The queue (`N`, `Shift+N`) walks the assets that need attention, but every one is still reviewed
in the detail panel beside a grid, with the preview at thumbnail size. A 300-asset audit is a
long series of small looks.

**Spec**
* **View → Review mode** (`F7`, and a button beside the queue line) replaces the page's body with
  one asset at a time: a preview that fills the left two thirds (nearest-neighbour, integer
  scale, the tile or frame grid drawn over it according to usage, see T13.03), and on the right
  the same `AssetDetail` widget the page uses, so no edit code is duplicated.
* The keys of the page work unchanged (`C`, `X`, `1`–`9`, `N`, `Shift+N`, `Ctrl+Z`), and are
  shown as a key line under the preview (`C Confirm · X Exclude · 1–9 Role · N Next`). `Esc` and
  `F7` leave the mode; the grid's selection follows the asset shown.
* The order is the queue's order; when the queue is empty the mode walks the current filter.
  A counter says `12 of 37 need attention`.
* Review mode is a widget over the same `EditSession`: nothing is edited twice, and leaving the
  mode changes no state.

**Tests**
* Entering shows the queue's first asset; `N` advances; `C` confirms and advances; `Esc` returns
  to the grid with that asset selected.
* An edit in review mode is one undo step, undoable after leaving the mode.
* T12.16 at the minimum window size in both themes.

**Done when**
* The tests pass and the keyboard shortcuts dialog lists `F7`.

---

## T13.02 — Audit grid grouped by folder

**Depends on:** nothing
**Files:** `rpggen/gui/widgets/asset_grid.py`, `rpggen/gui/pages/audit_page.py`,
`rpggen/gui/widgets/bulk_panel.py`, `rpggen/core/catalog.py` (a `folder_of` helper),
`tests/gui/test_asset_grid.py`, `tests/gui/test_audit_edits.py`

Packs are organised by folder, and most audit decisions are per folder, but the grid is flat.

**Spec**
* A **Group by folder** toggle on the filter bar (off by default; remembered in the settings).
  When on, the grid shows a header row per folder (the pack id and the folder relative to the
  pack, with the counts `4 need attention · 12 confirmed`), collapsible, and the assets of that
  folder under it. Headers are rows of the same model with a `HeaderRole`, so the proxy filter and
  the virtualised view are unchanged; a header is hidden when none of its assets pass the filter.
* A header has three buttons: **Confirm all** (the folder's assets that pass the filter, one undo
  step), **Select all** (so the bulk panel applies), and **Make rule…** (the existing folder-rule
  dialog, pre-filled with `<folder>/**`).
* The queue and `N` ignore headers.

**Tests**
* Headers appear once per folder, in path order, with correct counts; a filter hides empty ones.
* Confirm all is one undo step that confirms exactly the visible assets of the folder.
* Make rule… opens with the folder glob.

**Done when**
* The tests pass and T12.16 is green with the toggle on.

---

## T13.03 — Live preview in the detail panel

**Depends on:** nothing
**Files:** `rpggen/gui/widgets/asset_detail.py`, `rpggen/gui/widgets/image_view.py`,
`rpggen/gui/widgets/anim_preview.py` (its player becomes reusable), `tests/gui/test_anim_preview.py`,
`tests/gui/test_audit_cards.py`

The detail panel shows a still picture. Animations play only in the *Animations…* dialog, and the
grid, footprint and hit frames are each in their own dialog.

**Spec**
* The preview area draws an overlay according to usage: the tile grid (cell, margin, separation)
  for `tiles`, the frame boxes for `sprite`, the footprint and origin for `object`, nothing for
  the others. The overlay follows every edit at once (it reads the effective facets).
* For `sprite` assets with animations, a small transport under the picture: an animation combo
  (direction-grouped names as in the dialog), play/pause, and the frame number. Playback uses
  the dialog's `AnimPlayer` moved into `anim_preview.py` as a reusable widget; the dialog uses
  the same class.
* Active frames (ARPG hit frames) are tinted in the overlay.
* Playback stops when the asset changes or the page is left, and never runs in review mode and
  the panel at once.

**Tests**
* The overlay reflects a grid edit without reopening the asset.
* Play advances frames with a fake clock; leaving the page stops the timer.
* The dialog still works with the shared player.

**Done when**
* The tests pass.

---

## T13.04 — Select similar assets

**Depends on:** nothing
**Files:** `rpggen/core/analyzer/similarity.py` (new), `rpggen/core/analyzer/image_facts.py`
(the hash is one more cached fact), `rpggen/core/catalog.py`, `rpggen/gui/pages/audit_page.py`,
`rpggen/gui/widgets/asset_grid.py`, `tests/unit/test_similarity.py` (new),
`tests/gui/test_audit_edits.py`

**Spec**
* `image_facts` computes a 64-bit difference hash (`dhash`, 9×8 greyscale, Pillow and numpy) of
  every image and of every sheet object's region; it is cached with the other facts, keyed by
  the file hash. A cache entry from 1.0 lacks the hash and is extended in place, not rebuilt.
* `similarity.near(catalog, asset_id, max_distance=10)` returns the assets whose Hamming
  distance is at most `max_distance`, nearest first, with the distance.
* Audit page: right-click → **Select similar** (and `Ctrl+Shift+S`) selects them in the grid so
  the bulk panel applies. The status line says `9 similar assets selected`.
* Two assets from different packs at distance ≤ 2 with the same size get the informational tag
  `duplicate_of:<id>` on the later one, shown in the *Why* line (`looks like forest/tree.png
  from pack_a`). No role or usage changes, and goldens that have no such pair do not move.
* Audio and fonts have no hash; the command is disabled for them.

**Tests**
* A copy, a 1-pixel edit and a recolour of the same sprite are near; a different sprite is not.
* The distance is symmetric and deterministic.
* The command selects the right set and the bulk panel applies to it.
* A 1.0 cache entry is extended without re-reading the other facts.
* The synthetic pack `mixed` gets the duplicate tag (add an identical tile in two folders to
  the pack generator if it has none).

**Done when**
* The tests pass and the corpus (T12.26) is unchanged on all four measures.

---

## T13.05 — Mapping: picker gallery and jump to the audit

**Depends on:** nothing
**Files:** `rpggen/gui/pages/mapping_page.py`, `rpggen/gui/dialogs/asset_picker.py` (the dialog
`AssetPickerDialog` moves here from the page if it still lives there), `tests/gui/test_mapping_page.py`

T12.36 put the top five candidates in each row's combo; "More…" opens a plain list.

**Spec**
* "More…" opens a gallery: thumbnails at the grid's size, grouped by pack, with the filter bar's
  search and a confidence badge, and only the assets `mapping.candidates` allows for the role.
  Double-click chooses.
* Each row gains **Show in audit** (an icon button), which goes to the Audit page with that asset
  selected and the grid scrolled to it; `Back` returns to Mapping with the row focused. The
  sidebar's forward jumps (T12.35) make this a normal page change.

**Tests**
* The gallery lists the candidates in rank order and grouped by pack; choosing is the same
  undoable edit as the combo.
* Show in audit selects the asset on the Audit page.

**Done when**
* The tests pass.

---

## T13.06 — Factory presets and option dependencies

**Depends on:** nothing
**Files:** `rpggen/core/options.py`, `rpggen/gui/models/options_model.py`,
`rpggen/gui/pages/options_page.py`, `rpggen/gui/widgets/options_sections.py`,
`tests/unit/test_options_model.py`, `tests/gui/test_options_page.py`

**Spec**
* Three built-in presets head the preset combo, separated from the user's: **Everything** (the
  defaults), **Minimal** (tilesets, collision, animations, save, dialogue; no combat, no demo, no
  editor tools, no debug tools, no navigation, Windows export only) and **Just the tilesets**
  (tilesets, collision, terrain; nothing else, no demo). Built-ins cannot be renamed or deleted
  in *Manage…*; *Save as preset…* from a built-in makes a user copy. A 1.0 settings file whose
  user preset has a built-in's name keeps it, shown with a "(yours)" suffix.
* `options.DEPENDENCIES`: `navigation` needs `combat`; `demo` needs `tilesets`; encounter
  zones, party and shops (where they are options) need `combat` or `dialogue` as the runtime
  requires. A dependent checkbox is disabled while its requirement is off, with the hint
  "Needs Combat" under it, and `options_model` reports the effective value (off) so the summary
  panel and the config agree.

**Tests**
* Built-ins apply the documented values; Manage… refuses to delete them; a same-named user
  preset survives.
* Turning off `combat` disables and clears `navigation`; the summary says so.

**Done when**
* The tests pass.

---

## T13.07 — Remaining time on the Generate page

**Depends on:** nothing
**Files:** `rpggen/core/app_settings.py` (phase timing history), `rpggen/core/orchestrator.py`
(records timings per phase after every run; it already reports them), `rpggen/gui/pages/generate_page.py`,
`tests/unit/test_app_settings.py`, `tests/gui/test_generate_page.py`

**Spec**
* `AppSettings.phase_history`: for each phase, the last ten `(assets, seconds)` pairs on this
  computer. The orchestrator appends after every run, failed runs included for the phases that
  finished.
* `estimate(phase, assets)`: the median seconds per asset of the history times the current
  count, or the median seconds when the phase does not scale with assets (preflight, promote,
  report). Without history, no estimate.
* The Generate page shows `about 40 s left` beside the running phase and a total at the top,
  updated per phase, never counting down by the clock (an estimate that runs past zero says
  `taking longer than usual`). Hidden on the first run.
* The CLI prints the same estimate on stderr after each phase line when history exists.

**Tests**
* The estimate from a known history; no estimate without one; the overrun text.
* The history is capped at ten and survives a settings round trip; a 1.0 settings file without
  it loads.

**Done when**
* The tests pass.

---

## T13.08 — Project dashboard on the welcome view

**Depends on:** nothing
**Files:** `rpggen/gui/pages/welcome_page.py`, `rpggen/core/app_settings.py` (recent projects
carry the pack paths and stamps), `rpggen/core/pack_sniff.py` (a cheap "changed since" check),
`rpggen/core/orchestrator.py` (saves the preview picture at promotion), `tests/gui/test_menus_welcome.py`,
`tests/unit/test_pack_sniff.py`

**Spec**
* The recent-projects list becomes cards: the starter map picture (the Results page's picture,
  saved by the orchestrator as `rpggen/preview.png` in the project at promotion; a 1.0 project
  without one shows the archetype's card drawing), the name, the archetype, the date of the
  last generation and the pack names.
* `pack_sniff.changed_since(pack_path, recorded)` compares a folder's inventory stamp (size and
  mtime of the files, no hashing) or an archive's size and mtime with what the project's config
  recorded. A changed pack gives the card a line `forest.zip changed on 3 Oct` and a
  **Regenerate** button that opens the project at the Generate page with the regeneration
  preview (T12.40).
* A card whose folder is gone says so and offers *Remove from the list* (T12.11's rule: nothing
  is removed by itself).

**Tests**
* Cards show the recorded data; a touched pack file shows the changed line; a missing folder
  shows the removal offer; a 1.0 project without a preview picture shows the drawing.
* T12.16 with six cards at the minimum size.

**Done when**
* The tests pass.

---

## T13.09 — First-run tour

**Depends on:** nothing
**Files:** `rpggen/gui/widgets/tour.py` (new), `rpggen/gui/pages/audit_page.py`,
`rpggen/gui/wizard.py`, `rpggen/core/app_settings.py` (`tours_seen`), `tests/gui/test_tour.py` (new)

**Spec**
* A tour is a list of `(widget, title, text)` steps shown as a callout anchored to the widget,
  with *Next*, *Back* and *Skip*, dimming nothing (the page stays usable). It is keyboard
  navigable and closes on `Esc`.
* The Audit page has the only tour in 1.1: the status colours and glyphs, the queue line, the
  detail panel, the keys, and the Profile menu. It starts the first time the page is shown with a
  real pack (not the sample's "Try the sample" path, which ends on the Options page) and never
  again once finished or skipped. **Help → Show the tour again** restarts it.
* The texts go through `tr()`.

**Tests**
* The tour starts once, is marked seen when skipped, and restarts from the menu.
* Every anchor widget exists at the minimum window size.

**Done when**
* The tests pass.

---

## T13.10 — Accessibility and display scaling

**Depends on:** nothing
**Files:** `rpggen/gui/thumbnails.py`, `rpggen/gui/widgets/asset_grid.py`,
`rpggen/gui/widgets/image_view.py`, `rpggen/gui/widgets/map_preview.py`,
`rpggen/gui/pages/generate_page.py`, `rpggen/gui/theme.py`, `rpggen/gui/wizard.py`,
`rpggen/gui/taskbar.py` (new, optional part), `tests/gui/test_theme_a11y.py`, `tests/gui/test_layout_fit.py`

Two known 1.0 limits (`docs/status.md`): no taskbar progress, and pixmaps that are not
device-pixel-ratio aware.

**Spec**
* Every pixmap the wizard draws (thumbnails, the detail preview, the map preview, archetype
  cards) is rendered at the screen's device pixel ratio and tagged with it, so 150 % and 200 %
  scaling show crisp pixel art at integer scales. The thumbnail cache key includes the ratio.
* Accessible names and descriptions on every grid cell (`"hero.png, sprite, player, confirmed"`),
  on the status glyphs and on the icon-only buttons; the whole wizard can be driven by keyboard
  (a test tabs through every page and reaches every control).
* **View → Reduce motion** turns off the thumbnail animation, the progress pulse and the tour's
  slide; it defaults to the system's setting where Qt exposes it.
* **Optional, last:** taskbar progress on Windows during generation through `ITaskbarList3`
  (a COM vtable call through `ctypes` in `taskbar.py`; no new dependency), and the dock badge
  on macOS through `QApplication.setBadgeNumber`. Both are no-ops elsewhere and on any error.
  If the Windows call is not working within a day, ship without it and leave the limit in
  `docs/status.md`; the rest of the card does not wait for it.

**Tests**
* At DPR 2 a 16-px tile is rendered as a 32-px device image and the overlay lines are 1 device
  pixel.
* The tab order test over all seven pages and the welcome view.
* Accessible names on the grid's cells.
* `taskbar.py` is a no-op on Linux and when the COM call fails (monkeypatched).

**Done when**
* The tests pass and the limits the card removed are gone from `docs/status.md`.

---

# Part B — Feature improvements

## T13.11 — Shops: quantities and sell all

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_runtime/ui/shop_menu.gd`, `data/shop_definition.gd`,
`ui/strings.gd`, `godot_templates/builder/recipes/ui_recipes.gd`,
`godot_templates/tests/unit/test_shops.gd`, smoke steps (the shop step buys two)

**Spec**
* The buy and sell rows get a quantity (left/right or a spinner, 1 to the stack limit or what
  gold allows), with the total shown before confirming.
* **Sell all** on the sell tab sells every item of the categories the shop's `buys` lists
  (default: everything but QUEST and equipped gear), after a confirmation that names the gold.
* `ShopDefinition.buys: Array[String]` (categories), optional, default all; a 1.0 shop resource
  without it loads. The recipe does not change the demo shop.
* Gamepad: the quantity is on the row's left/right; the validator's focus chain test covers it.
  A 1.0 project's shop scene (older `ui_recipes` version) gets the rows on regeneration; the
  script tolerates the older scene.

**Tests**
* Buying three takes three times the price and respects the stack limit.
* Sell all skips equipped gear and quest items.

**Done when**
* The tests and the smoke step pass; `docs/status.md` drops the limit.

---

## T13.12 — One interior per house

**Depends on:** nothing
**Files:** `godot_templates/builder/recipes/interior_recipe.gd`,
`godot_templates/builder/recipes/starter_map_recipe.gd`, `rpggen/core/map_preview.py`,
`godot_templates/tests/unit/test_map_build.gd`, `tests/unit/test_map_plan.py`,
`tests/integration/test_m4_sample.py`

Every house leads to `interior_1`, which leads back to the first house.

**Spec**
* The planner numbers the buildings; each gets `interior_<n>` sized from its footprint (the
  width in tiles of the building, at least 10, by 8), with the door on the bottom wall at the
  building's door column, a bed, a table and a chest for the first only (the demo chest stays
  where it is).
* `interior_recipe` (version 3) builds one scene per building and the door pairs point back to
  the right house (`target_map`, `target_spawn`). Existing projects keep their `interior_1`; the
  new scenes are `user_seed`, so a regeneration adds the missing interiors only for buildings
  the starter map still has, and never rewrites a map. The doors of an existing starter map are
  not retargeted (the map is user-owned); the generated README says how to point a house at
  its new interior.
* The map preview legend counts the interiors (`3 interiors`), and the options summary too.

**Tests**
* The plan gives each building its interior id and door column.
* Entering house 2 lands in `interior_2`, leaving returns to house 2's door.
* An existing `interior_1` and the starter map are untouched by regeneration.

**Done when**
* The tests pass; `docs/status.md` drops the limit.

---

## T13.13 — Validator: every id, inline in the dialogue tab

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_project_tools/tools/content_checks.gd`,
`godot_templates/addons/rpg_runtime/dialogue/dialogue_runner.gd` (`event_problem` takes an id
resolver), `godot_templates/addons/rpg_project_tools/dock/dialogue_tab.gd`,
`godot_templates/tests/unit/test_content_checks.gd`, `test_tools_dock.gd`

**Spec**
* `content_checks` resolves `open_shop:<id>`, `quest_start:`, `quest_advance:`, `quest_complete:`
  and `join_party:<id>` against the shop, quest and actor definitions under `game/data/`, and
  reports each unknown id as a validator row with the dialogue file and line.
* `RpgDialogueRunner.event_problem(event, ids)` accepts an optional `ids` dictionary
  (`{"shop": [...], "quest": [...], "actor": [...]}`); with it, an unknown id is a problem. The
  dialogue tab passes the ids it loads from `game/data/`, so a typo is marked while typing.
* The headless validator (`validate.gd`) runs the same check and fails the build on an unknown id
  in the demo content only (user dialogue gives VAL warnings, not failures, as today).

**Tests**
* Each event kind with a known and an unknown id.
* The tab marks the line with the unknown id.

**Done when**
* The tests pass; `docs/status.md` drops the limit.

---

## T13.14 — Zstandard for Tiled and LDtk

**Depends on:** nothing
**Files:** `rpggen/core/adapters/tiled.py`, `rpggen/core/adapters/ldtk.py` (if it reads
compressed layers), `pyproject.toml`, `requirements/*.txt`, `THIRD_PARTY_NOTICES.md`,
`packaging/rpggen.spec`, `tools/make_synthetic_packs.py`, `tests/unit/test_adapter_tiled.py`

**Spec**
* `zstandard` is an optional dependency (`[project.optional-dependencies] maps`) that the
  packages always include. `_decode_layer` decompresses `zstd` through it when it is importable;
  without the module the layer gives TILE-009 with the text "install the zstandard package", so
  a source checkout without extras behaves as before.
* The `tiled_map` synthetic pack gains a zstd layer; the golden is updated.
* TILE-009's text changes from "Zstandard" to "an unsupported compression (`{compression}`)".

**Tests**
* A zstd layer decodes to the same cells as its zlib twin; the module missing (monkeypatched)
  gives TILE-009 with the install text.

**Done when**
* The tests pass; `docs/status.md` and `docs/errors.md` are updated.

---

## T13.15 — Followers in the action RPG

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_runtime/world/followers.gd`,
`godot_templates/addons/rpg_runtime/archetypes/arpg/components/assist.gd` (new),
`archetypes/arpg/arpg_mode.gd`, `godot_templates/builder/recipes/arpg/arpg_build.gd`,
`builder/recipes/data_recipe.gd`, `godot_templates/tests/unit/test_followers.gd`,
`test_arpg_runtime.gd`, `builder/smoke/smoke_steps_arpg.gd`

**Spec**
* The party (T12.47, T12.69) exists in the ARPG too: `join_party:` works, followers walk behind
  the player as on the top-down maps, and up to two of them carry an `Assist` component: when an
  enemy is within 3 tiles of the player, the follower moves beside it and swings its own hitbox
  (`RpgHitbox` from the ARPG folder, where it stays in 1.x) every 1.2 s, with the follower's
  stats; it never leaves a 6 tile radius of the player and cannot die (it is "downed" for 5 s at
  0 HP, then returns).
* The HUD shows followers' HP bars under the player's.
* Demo: the villager's companion offer (turn-based) is the same dialogue in the ARPG.

**Tests**
* A follower hits an enemy near the player; it returns when the player walks away; it cannot
  die.
* Smoke: `follower_assists`.

**Done when**
* The tests pass; `docs/status.md` drops the limit.

---

## T13.16 — Custom sound slots

**Depends on:** nothing
**Files:** `rpggen/core/sound_slots.py`, `rpggen/core/config.py`,
`rpggen/schema/config.schema.json`, `docs/spec/02_SCHEMAS.md`, `rpggen/gui/widgets/sound_section.py`,
`godot_templates/builder/recipes/audio_bus_recipe.gd`,
`godot_templates/addons/rpg_runtime/audio/*.gd`, `godot_templates/addons/rpg_runtime/actors/actor.gd`
(footsteps by surface), `tests/unit/test_sound_slots.py`, `tests/gui/test_options_m11.py`

**Spec**
* `config.sounds` accepts any key matching `^(music|sfx)_[a-z][a-z0-9_]{1,30}$` beyond the fixed
  list (`additionalProperties` with that pattern). The fixed slots keep their meaning.
* `sound_slots.SURFACES = ["grass", "stone", "wood", "water", "sand"]`: a ground tile asset's
  tag `surface:<name>` (detected from folder and file words: grass, stone, wood, sand, water,
  snow) makes the actor play `sfx_step_<name>` when it exists, else `sfx_step`. `default_sounds`
  fills these from audio file names (`step_grass.wav`, `footstep-stone.ogg`).
* The Sound dialog has **Add slot…** (name, validated by the pattern; a duplicate is refused) and
  a remove button on custom rows; a custom slot is played by `RpgAudio.play("sfx_<name>")` from
  dialogue events (`play_sound:<slot>`) and custom recipes. The generated README lists them.
* An invalid slot name in a config file is `CAT-006`.

**Tests**
* The pattern; `default_sounds` fills surface slots; an actor on a `surface:stone` cell plays
  the stone step; the dialogue event.
* The dialog adds and removes a slot as one undo step.

**Done when**
* The tests pass; `docs/status.md` drops the limit.

---

## T13.17 — Audio audit: waveforms and loop points

**Depends on:** nothing
**Files:** `rpggen/core/audio_info.py` (peaks and loop guess), `rpggen/gui/widgets/audio_preview.py`,
`rpggen/gui/widgets/asset_detail.py`, `rpggen/gui/thumbnails.py` (waveform thumbnails),
`rpggen/schema/catalog.schema.json` (`audio.loop_start_ms`, `audio.loop_end_ms`, optional),
`godot_templates/builder/recipes/audio_bus_recipe.gd` (loop points into the import options),
`pyproject.toml`, `requirements/*.txt`, `THIRD_PARTY_NOTICES.md`, `packaging/rpggen.spec`,
`tools/package.py` (the smoke plays through libsndfile), `tests/unit/test_audio_info.py`,
`tests/gui/test_audit_cards.py`

**Spec**
* Decoding goes through `soundfile` (libsndfile), the dependency the ground rules allow: WAV,
  OGG Vorbis, FLAC and MP3. `audio_info.peaks(path, columns=96)` returns per-column min and max
  over the decoded samples, reading in blocks so a ten-minute track never sits in memory at
  once, and it runs in the analysis worker with the other facts (cached by file hash). A file
  libsndfile cannot open keeps the duration-only facts and a flat bar; it is never an error.
* The audit card of an audio asset shows the waveform instead of the plain square; the detail
  panel shows it large with a play head, and for music a **Loop** row: start and end in
  milliseconds, draggable markers on the waveform, and **Guess** (`audio_info.guess_loop`: the
  longest pair of 50 ms windows with the smallest RMS difference, start after the first second).
* The loop points are facets (undoable) and the recipe writes them to the `.import` options of
  WAV (`edit/loop_mode`, `edit/loop_begin`, `edit/loop_end`) and to the OGG stream's
  `loop_offset` **⚠ VERIFY** both against the 4.7 class reference, so the music loops at the
  chosen point in the game. MP3 streams get `loop_offset` too.
* Perf: the analysis of the sample pack and of the perf corpus stays within the T12.27 ceilings;
  if decoding every track breaks a ceiling, peaks are computed lazily when the asset is first
  shown and the ceiling stays.

**Tests**
* Peaks of a synthetic sine written as WAV and as OGG; the loop guess on a signal with a
  repeat; an unreadable file gives the flat bar.
* The facets round-trip through the catalog; the recipe writes the import options.
* The frozen smoke (`tools/package.py --smoke`) decodes an OGG on all three systems.

**Done when**
* The tests pass and `THIRD_PARTY_NOTICES.md` lists libsndfile with its licence.

---

# Part C — Feature additions

## T13.18 — Recolour variants

**Depends on:** nothing
**Files:** `rpggen/core/variants.py` (new), `rpggen/core/catalog.py`,
`rpggen/schema/catalog.schema.json` (`variants`), `docs/spec/02_SCHEMAS.md`,
`rpggen/gui/dialogs/variant_dialog.py` (new), `rpggen/gui/pages/audit_page.py`,
`rpggen/core/staging.py` (variant images are written into the staging copy),
`godot_templates/builder/recipes/data_recipe.gd` (enemy definitions per variant),
`tests/unit/test_variants.py` (new), `tests/gui/test_variant_dialog.py` (new)

Most packs ship one slime.

**Spec**
* `catalog.variants: [{id, source, name, op, params}]`, optional. `op` is `hue` (`shift`
  degrees, `saturation`, `value` multipliers) or `palette` (`map`: a list of `[from, to]` RGB
  pairs). A variant is an effective asset with the source's facets (grid, frames, animations,
  collision), usage and role, path `generated/variants/<id>.png`, and `derived_from: source`.
* `variants.render(source_image, op, params)` is deterministic (integer arithmetic, no dithering)
  and keeps alpha. A variant whose source left the pack is `ASSET-029` (the variant is dropped
  from the effective list with the warning).
* Audit: right-click a sprite → **Make variant…**: the dialog shows the source and the result
  side by side, the hue wheel or a palette table with eyedroppers from the source, a name
  (`Fire slime`), and for ENEMY or BOSS sources a stats multiplier (HP, attack, XP, gold). Saving
  adds the variant as one undo step; the variant appears in the grid with a ⧉ glyph.
* Regeneration re-renders variants from the current source (the ledger owns the PNG).
* `data_recipe` makes an enemy definition per ENEMY variant (name, multiplied stats, the
  variant's SpriteFrames); the dock lists them like other enemies. Nothing is placed on the demo
  map.

**Tests**
* A hue shift of 120° turns pure red to pure green and keeps alpha; a palette map changes only
  the listed colours; the render is byte-identical across runs.
* A variant's effective facets equal its source's; a removed source gives ASSET-029.
* The dialog's undo.
* Integration: a variant enemy definition exists in the sample project after adding one through
  a config.

**Done when**
* The tests pass.

---

## T13.19 — Quest and cutscene tabs in the dock

**Depends on:** T13.13
**Files:** `godot_templates/addons/rpg_project_tools/dock/quest_tab.gd` (new),
`dock/sequence_tab.gd` (new), `dock/asset_dock.gd`, `godot_templates/addons/rpg_runtime/data/quest_definition.gd`
(`problems`), `events/sequence.gd` (`problems`, `STEP_KINDS`), `godot_templates/tests/unit/test_tools_dock.gd`,
`test_quests.gd`

**Spec**
* **Quests tab:** the `.tres` under `game/data/quests/`; a stage list with the stage's title,
  description, condition (with the inline checker of T12.61), rewards and `target` (an entity id
  with a picker from the open map); a graph view (a `GraphEdit` **⚠ VERIFY** the 4.7 node and
  slot API, read-only layout, stages as nodes, `next` as edges) beside the form; every change
  through `EditorUndoRedoManager`; **Test** runs the quest against the pretend state (flags,
  items, gold) and shows the stage it reaches.
* **Cutscenes tab:** the sequences under `game/data/sequences/`; a step list (kind from
  `STEP_KINDS`: move, face, say, wait, camera, flag, give, play sound, fade), a form per step,
  entity ids checked against the open map, and **Test** that plays the sequence in the editor's
  running scene when one is playing, otherwise checks it only.
* Both tabs export and import JSON like the Dialogue tab.

**Tests**
* Stage edit round trip and undo; the graph lists one node per stage and an edge per `next`.
* A step with an unknown entity is marked; the JSON round trips.

**Done when**
* The tests pass.

---

## T13.20 — A world of connected maps

**Depends on:** T13.12, T13.21
**Files:** `rpggen/core/world_plan.py` (new), `rpggen/core/map_preview.py`,
`rpggen/core/config.py` and `rpggen/schema/config.schema.json` (`starter_map.areas`, optional),
`rpggen/schema/world_plan.schema.json` (new), `docs/spec/02_SCHEMAS.md`,
`rpggen/gui/widgets/options_sections.py`, `rpggen/gui/widgets/map_preview.py`,
`rpggen/core/orchestrator.py` and `rpggen/core/preflight.py` (the stored plan),
`godot_templates/builder/recipes/starter_map_recipe.gd`, `second_map_recipe.gd` (becomes the
area recipe), `data_recipe.gd`, `godot_templates/builder/validate.gd` (VAL-027, VAL-028),
`godot_templates/tests/unit/test_map_build.gd`, `tests/unit/test_world_plan.py` (new),
`tests/integration/test_m4_sample.py`, `tests/integration/test_regeneration.py`

The planner makes one starter map, a house and a field.

**Spec**
* `starter_map.areas`: a list of `{name, biome, size, enemies, chests}` with biomes `village`,
  `field`, `forest`, `cave`, `shore`; omitted means today's starter map and field. Each biome
  chooses its ground set by role and tags (`forest` prefers GROUND assets tagged `grass` with
  the most DECORATION trees; `cave` prefers `stone` with WALL cliffs; `shore` adds WATER). A
  biome whose assets are missing falls back to the previous one with a note in the report.
* `world_plan.plan(areas, seed, catalog)` lays the areas on a 2D grid (the village in the
  middle), joins neighbours with door pairs on facing edges, places chests and enemies per area,
  and uses the lock-and-key planner (T13.21) to put one key (T12.70) in an area before the gate
  that closes the cave. Deterministic from the seed.
* **The plan is stored and reused.** The orchestrator writes the plan to
  `rpggen/world_plan.json` in the project (generated-owned, schema-checked) at promotion. On
  regeneration the recipes read the stored plan and build only the areas whose map does not
  exist; the seed and the areas table are **not** re-planned once any area map exists. The
  Options page then shows the *Areas* table disabled with the text "This project has its world
  already; add areas in Godot or delete `game/maps/<area>.tscn` to rebuild it", the same rule
  the starter map follows (T12.33's "a project that already has a starter map keeps it").
  Adding a row to the table is allowed and appends an area to the stored plan, joined to the
  area the user picks in the row; nothing else moves.
* **Validation.** `validate.gd` walks the doors of every map under `game/maps/` and warns:
  `VAL-027` when a map cannot be reached from the starter map through door pairs (with the
  map's name), `VAL-028` when a door's `target_map` or `target_spawn` has no partner. Both are
  **warnings**, listed under *Notes* on the Results page and in the report: a person may want
  an island. The planner never emits either on its own output (a test proves it over 200 seeds).
  T13.24 repairs both. The stored plan records a `map_hash` per map rpggen built, so T13.24 can
  tell a map nobody edited from one a person changed.
* The Options page: the *Starter map* box gains an *Areas* table (add, remove, reorder; name,
  biome, size, enemies, chests) and the preview shows the world as tiles of areas with their
  doors; clicking an area previews it. Reroll works per area, before the first generation only.
* The world map (T12.64) is seeded with the areas' placement, so it shows the layout before the
  player has visited every area.

**Tests**
* The grid placement is deterministic; every area is reachable from the village; the key is
  reachable before the gate; no VAL-027/028 over 200 seeds.
* The biome fallback and its note.
* The stored plan: a regeneration with a different seed and a bigger table builds only the new
  area, and the existing maps are byte-identical; the table is disabled once a map exists.
* A hand-broken door gives VAL-028 as a warning and the build still succeeds.
* The Options table edits are undoable; the preview draws one tile per area.
* Integration: a three-area world generates, validates and passes the smoke test on the sample
  pack.

**Done when**
* The tests pass; VAL-027 and VAL-028 are in `03_ERROR_CODES.md` as warnings and in `docs/errors.md`.

---

## T13.21 — Lock-and-key planner

**Depends on:** nothing
**Files:** `rpggen/core/lockkey.py` (new), `tests/unit/test_lockkey.py` (new)

A pure function shared by T13.20 (keys and gates on a top-down world) and M14 (abilities and
gates in a side-view room graph).

**Spec**
* `lockkey.plan(graph, keys, start, goal, rng)`: `graph` is `{node: [neighbour, ...]}` with
  edges optionally tagged by the key they need (`(neighbour, key)`); `keys` is the ordered list
  of keys to place. The result assigns each key to a node reachable with the keys placed before
  it, so that the goal needs them all, and returns the critical path. Deterministic from `rng`.
* `lockkey.check(graph, placements, start, goal)` says whether every node is reachable in some
  order and which are not, so a validator can report them.
* An unsolvable input (fewer free nodes than keys, or a goal cut off) raises `LockKeyError`
  with the count needed; callers turn it into their own code.

**Tests**
* A solvable and an unsolvable graph; the order is stable; `check` names the unreachable nodes;
  200 random graphs with 2 to 6 keys all verify with `check`.

**Done when**
* The tests pass.

---

## T13.24 — World repair: unpaired doors and unreachable maps fix themselves

**Depends on:** T13.20
**Files:** `godot_templates/builder/tools/world_repair.gd` (new; the builder's `tools/` folder),
`godot_templates/builder/lib/map_graph.gd` (new: doors, spawns and reachability over the maps
under `game/maps`, shared with `validate.gd`), `godot_templates/builder/validate.gd`,
`godot_templates/addons/rpg_project_tools/dock/validator_panel.gd` (Fix buttons),
`godot_templates/addons/rpg_project_tools/tools/content_checks.gd`, `rpggen/core/world_repair.py`
(new: runs the tool headless, backs up, reads its result), `rpggen/core/orchestrator.py` (after
promotion), `rpggen/core/report.py` (*World repairs*), `rpggen/core/config.py` and
`rpggen/schema/config.schema.json` (`repair_world`, optional, default true), `rpggen/schema/world_plan.schema.json`
(`map_hash` per map), `rpggen/gui/fixes.py` (the one-click fix), `rpggen/gui/pages/results_page.py`,
`rpggen/gui/widgets/options_sections.py` (*Advanced*), `rpggen/cli.py` (`repair-world`, and
`--no-repair-world` on `generate`), `godot_templates/tests/unit/test_world_repair.gd` (new),
`tests/unit/test_world_repair.py` (new), `tests/integration/test_regeneration.py`

Added 2026-10-08. T13.20 makes a broken world a warning. This card makes it mend itself where
that is safe, and offers the mend where it is not.

**Spec**
* **The graph.** `map_graph.gd` reads every map under `game/maps/` (and `game/maps/rooms/`
  in M14): its doors (`target_map`, `target_spawn`), its spawn points, its size and the solid
  cells of its layers. It gives the unreachable maps from the starter map and the doors without
  a partner. `validate.gd` and `content_checks.gd` use it instead of their own walk, so the
  warning and the repair agree on what is broken.
* **Repairs**, in this order, each deterministic and additive (nothing the user placed is
  moved or deleted):
  1. A door whose `target_map` does not exist: retarget it to the map the stored plan paired it
     with, if that map exists; else to the nearest map on the plan's grid; else leave it and
     report it as unfixable.
  2. A door whose `target_spawn` does not exist on an existing target: add a spawn point on the
     target map at the matching position (the opposite edge, the same offset, moved to the
     nearest walkable cell within 3 tiles), named after the source door, and a door back beside
     it when the target has no door to the source. From the stored plan when the pair is
     planned; by geometry otherwise.
  3. An unreachable map: pick the nearest reachable map that shares an edge on the plan's grid
     (the starter map when the map is not in the plan); add a door pair on the shared edge at a
     cell that is walkable on both sides (scanned from the middle outwards); when no such cell
     exists, report it as unfixable with the edge it tried.
  Every repair is a line `{kind, map, node, what}`; the tool writes them to
  `rpggen/world_repair.json` in the project and prints them.
* **By itself, where safe.** The stored plan (T13.20) records `map_hash` for every map rpggen
  built. After a successful promotion the orchestrator runs the tool on the maps whose hash is
  unchanged (rpggen made them, nobody edited them), with `config.repair_world` on (the default;
  *Options → Advanced → Repair generated maps after a build*; `--no-repair-world`). The maps
  are backed up to `.rpggen_backups` first, as the conflict resolver does, so **Restore
  previous** undoes a repair, and the report lists each line under *World repairs*. A map
  whose hash changed is never touched by itself.
* **Offered, where not.** For an edited map, the Results page's *Notes* show the VAL-027 and
  VAL-028 warnings with a one-click fix (T12.41) **Repair the world…** that previews the lines
  before writing (the same backup and report). `rpggen-cli repair-world --target X [--dry-run]
  [--json]` does the same for scripts.
* **In the editor.** The dock's validator panel lists the same warnings with **Fix** per row
  and **Fix all**, each through `EditorUndoRedoManager` so `Ctrl+Z` takes it back, and marks
  the map scene modified rather than saving it. The panel never runs a fix by itself.
* **Never.** The repair never writes a map it reports as unfixable, never changes a door that
  already has a partner, never removes a spawn or a door, and does nothing while the editor has
  the project open (`REGEN-005` applies).

**Tests**
* `test_world_repair.gd`: each of the three repairs on a fixture world; a door with a partner
  is untouched; an unreachable map with no walkable shared edge is reported, not written; the
  result file; the dock's Fix is undoable.
* `test_world_repair.py`: the hash rule (an edited map is skipped), the backup and *Restore
  previous*, the report section, the config default and the CLI flags, `--dry-run` writes
  nothing.
* Integration: delete a generated spawn point from an area's map, regenerate; the spawn is
  back, the report says so, and Restore previous removes it again.

**Done when**
* The tests pass and the user guide's regeneration page explains the rule in one paragraph:
  rpggen mends the maps it made; yours it mends when you ask.

---

# Part D — Documentation and the gate

## T13.22 — Documentation, screenshots and changelogs

**Depends on:** Parts A–C (T13.24 included)
**Files:** `README.md`, `docs/user_guide.md`, `docs/status.md`, `docs/regeneration.md` (the stored
world plan and the repair rule), `docs/errors.md` (generated), `docs/spec/02_SCHEMAS.md`, `docs/spec/03_ERROR_CODES.md`,
`docs/architecture.md` (§48 deferred list: remove what this milestone did), `CHANGELOG.md`,
`godot_templates/addons/rpg_runtime/CHANGELOG.md` and `README.md`,
`godot_templates/project_files/README.template.md`, `tools/make_doc_screenshots.py`,
`docs/images/*`, `tests/gui/test_doc_screenshots.py`

* The user guide: review mode, folder groups, similar assets, the picker gallery, the presets
  and dependencies, the estimate, the dashboard, the tour, the accessibility options; shops,
  interiors, validator ids, zstd, ARPG followers, custom slots, waveforms and loops; variants,
  the quest and cutscene tabs, areas and the stored world plan.
* Screenshots: the review mode, the variant dialog, the areas table, the Quests tab.
  `test_the_screenshots_match_the_files_the_guide_uses` passes.
* `docs/status.md`: M13 done; the *Known limits* list drops every item a card removed; the
  manual rows for M13 (T13.23) are listed.
* `CHANGELOG.md` gets `1.1.0`; the runtime changelog too, with the compatibility notes
  (optional save keys, the older-scene tolerance).

**Done when** the docs test passes.

---

## T13.23 — Gate (1.1.0)

**Depends on:** T13.22

* Every suite is green on Windows and Ubuntu, on both PySide6 legs; perf is within its
  ceilings.
* The frozen smoke test passes on Windows, Linux and macOS, including the libsndfile decode.
* T12.16 passes at the minimum size in both themes for both archetypes, with review mode and
  folder groups on.
* **Upgrade test:** a project generated by the `v1.0.0` build (kept as a fixture produced by
  `tools/held_out_run.py --keep`) regenerates with 1.1 without a prompt, its maps and `game/`
  byte-identical, and its 1.0 save loads in the regenerated game.
* The corpus (T12.26) is unchanged on all four measures.
* Manual rows: buy three of an item and sell all; enter two houses; use review mode and folder
  groups on a 300-asset pack at 150 % scaling; make a variant enemy and meet it in the game;
  edit a quest in the graph and a cutscene step; generate a three-area world and regenerate it
  with a changed seed; delete a door from a generated area and regenerate, then from an edited
  one and use the one-click fix, then undo a Fix in the dock; set a loop point and hear it in
  the game; add a custom slot; check a Tiled map with a zstd layer; a follower assists in the
  ARPG.
* `docs/status.md` lists nothing from this milestone as open.

**Done when** all of the above is true; then tag `v1.1.0`.

---

# Appendix — Review items to cards

The review of 2026-10-08 listed 10 UI/UX items, 7 feature improvements and 3 feature additions.
Every item maps to exactly one card. The Metroidvania archetype asked for with them is
`M14_metroidvania.md`.

| Review item | Card |
|-------------|------|
| UX 1: focused review mode | T13.01 |
| UX 2: group the grid by folder | T13.02 |
| UX 3: live preview in the detail panel | T13.03 |
| UX 4: select visually similar assets | T13.04 |
| UX 5: Mapping thumbnail picker | T13.05 (T12.36 already has the inline candidates) |
| UX 6: factory presets and dependencies | T13.06 |
| UX 7: time estimate | T13.07 |
| UX 8: project dashboard | T13.08 |
| UX 9: first-run tour | T13.09 |
| UX 10: accessibility and scaling | T13.10 |
| Improvement 1: shop quantities | T13.11 |
| Improvement 2: one interior per house | T13.12 |
| Improvement 3: validator ids | T13.13 |
| Improvement 4: Zstandard | T13.14 |
| Improvement 5: ARPG followers | T13.15 |
| Improvement 6: custom sound slots | T13.16 |
| Improvement 7: audio waveforms and loop points | T13.17 |
| Addition 1: recolour variants | T13.18 |
| Addition 2: quest and cutscene tabs | T13.19 |
| Addition 3: a world of connected maps | T13.20 (planner in T13.21, repair in T13.24) |
