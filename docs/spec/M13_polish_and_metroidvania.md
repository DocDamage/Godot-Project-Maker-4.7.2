# M13 — Polish, Feature Depth and the Metroidvania Archetype

**Goal:** land the twenty improvements of the review of 2026-10-08 and a third archetype,
**Metroidvania** (side-view platforming, abilities that open the world, rooms), before the first
tag. Part A is wizard UX, Part B deepens features that exist, Part C adds three features, Part D is
the archetype, Part E is the documentation and the gate. **Everything in this milestone lands
before `v1.0.0`**: T12.66 now depends on T13.31.

This file follows the format of M01–M12. It was written against commit `99c486a`. File and line
references are to that commit. The appendix maps every item of the review to the card that carries
it.

## Ground rules for this milestone

* The M12 ground rules apply unchanged (`M12_review_followups.md`): core logic stays out of the
  GUI, pages only edit `WizardState`, every edit is undoable, generated output is deterministic,
  `.tscn`, `.tres` and `project.godot` are never written by hand, every Godot API is verified
  before use, config schema changes are additive and optional, `save_version` stays 1 and new save
  data is optional keys with defaults, recipe changes bump `RECIPE_VERSION`, new smoke steps are
  added to the lists the integration tests assert, and T12.16 stays green at the minimum window
  size in both themes.
* **Versions.** Nothing is tagged. The app, the runtime and `config_version` keep 1.0.0, 1.0.0
  and 1. Runtime changes go under the existing `1.0.0` heading of the runtime changelog.
* **New error codes** go into `03_ERROR_CODES.md` first, then `python tools/gen_error_codes.py`.
  Codes reserved by this milestone: `VAL-027`, `VAL-028`, `ASSET-029`, `ASSET-030`, `CAT-006`.
* **Archetypes.** `metroidvania` is the third value of `config.archetype`,
  `staging.ARCHETYPES` and `orchestrator.ARCHETYPE_SMOKE_STEPS`. Its files live in
  `addons/rpg_runtime/archetypes/metroidvania/`, `builder/recipes/metroidvania/` and
  `builder/smoke/smoke_steps_metroidvania.gd`, so the existing install filter
  (`staging._other_archetype`, `staging.py:169`) keeps it out of the other two archetypes'
  projects without change. Until T13.31, the wizard's card is disabled by
  `METROIDVANIA_AVAILABLE = False` in `rpggen/features.py`, exactly as `ARPG_AVAILABLE` was.
* **Shared code moves once.** T13.21 moves the real-time combat primitives out of the ARPG folder
  before any metroidvania card uses them. No card copies a script between archetypes.
* **Dependencies.** The only new Python dependency allowed is `zstandard` (T13.14), optional.
  Record it in `THIRD_PARTY_NOTICES.md`, `packaging/rpggen.spec` and the lock files. Perceptual
  hashes (T13.04) and recolouring (T13.18) are written with Pillow and numpy, which exist.
* **Demo content stays small.** The side-view demo world has six rooms (T13.25); the top-down
  demo gains nothing in this milestone except what T13.12 and T13.20 say.
* After any change to detection or the sample pack, run `python -m rpggen.dev update-goldens` and
  `python tools/build_sample_pack.py`, and review the diff. T13.22 and T13.18 change detection or
  the catalog, so the held-out runs of T10.09 happen after they land.

## Order of work

| Step | Tasks | Why this order |
|------|-------|----------------|
| 1 | T13.21, T13.14, T13.13, T13.11 | Small, independent, and T13.21 must precede Part D |
| 2 | T13.22 → T13.23 → T13.24 → T13.25 → T13.26 → T13.27 → T13.28 → T13.29 | The archetype, in dependency order; the longest chain, so it starts early |
| 3 | T13.01 – T13.10 | Wizard UX; independent of step 2 except T13.08 and T13.10, which touch pages Part D also touches, so they go after T13.28 |
| 4 | T13.12, T13.15, T13.16, T13.17 | Feature improvements |
| 5 | T13.18, T13.19, T13.20 | Feature additions; T13.20 after T13.12 and T13.25 (it reuses the room graph's lock-and-key planner) |
| 6 | T13.30 – T13.31 | Docs, screenshots and the M13 gate, then T12.66 and the tag |

Tasks inside a step are independent unless **Depends on** says otherwise.

## Index

Sizes are rough: **S** under a day, **M** 1–3 days, **L** 3–7 days, **XL** more than a week.

| Card | Title | Size | Depends on | Status |
|------|-------|:----:|------------|--------|
| T13.01 | Audit review mode | M | — | open |
| T13.02 | Audit grid grouped by folder | M | — | open |
| T13.03 | Live preview in the detail panel | M | — | open |
| T13.04 | Select similar assets | M | — | open |
| T13.05 | Mapping: picker gallery and jump to the audit | S | — | open |
| T13.06 | Factory presets and option dependencies | S | — | open |
| T13.07 | Remaining time on the Generate page | S | — | open |
| T13.08 | Project dashboard on the welcome view | M | T13.28 | open |
| T13.09 | First-run tour | S | — | open |
| T13.10 | Accessibility and display scaling | M | T13.28 | open |
| T13.11 | Shops: quantities and sell all | S | — | open |
| T13.12 | One interior per house | M | — | open |
| T13.13 | Validator: every id, inline in the dialogue tab | S | — | open |
| T13.14 | Zstandard for Tiled and LDtk | S | — | open |
| T13.15 | Followers in the action RPG | M | T13.21 | open |
| T13.16 | Custom sound slots | M | — | open |
| T13.17 | Audio audit: waveforms and loop points | M | — | open |
| T13.18 | Recolour variants | L | — | open |
| T13.19 | Quest and cutscene tabs in the dock | L | T13.13 | open |
| T13.20 | A world of connected maps | L | T13.12, T13.25 | open |
| T13.21 | Shared real-time combat primitives | M | — | open |
| T13.22 | Side-view detection: tags, collision values, backgrounds | M | — | open |
| T13.23 | Platform actor | L | T13.21, T13.22 | open |
| T13.24 | Abilities and gates | M | T13.23 | open |
| T13.25 | Rooms, camera and the world graph | XL | T13.24 | open |
| T13.26 | Side-view enemies and the guardian | M | T13.25 | open |
| T13.27 | HUD, room map and save stations | M | T13.26 | open |
| T13.28 | Wizard: the Metroidvania card, roles, options and preview | M | T13.27 | open |
| T13.29 | Metroidvania smoke steps and integration test | M | T13.28 | open |
| T13.30 | Documentation, screenshots and changelogs | M | Parts A–D | open |
| T13.31 | Gate (M13) | M | T13.30 | open |

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
  the file hash, so a cache built before this card is extended, not rebuilt.
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
* The synthetic pack `mixed` (two identical tiles in two folders, if it has them; add them to
  the pack generator otherwise) gets the duplicate tag.

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
  in *Manage…*; *Save as preset…* from a built-in makes a user copy.
* `options.DEPENDENCIES`: `navigation` needs `combat`; `demo` needs `tilesets`; `encounter
  zones`, party and shops (where they are options) need `combat` or `dialogue` as the runtime
  requires. A dependent checkbox is disabled while its requirement is off, with the hint
  "Needs Combat" under it, and `options_model` reports the effective value (off) so the summary
  panel and the config agree.
* The metroidvania archetype's presets (T13.28) reuse this table.

**Tests**
* Built-ins apply the documented values; Manage… refuses to delete them.
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
* The history is capped at ten and survives a settings round trip.

**Done when**
* The tests pass.

---

## T13.08 — Project dashboard on the welcome view

**Depends on:** T13.28 (the card picture per archetype)
**Files:** `rpggen/gui/pages/welcome_page.py`, `rpggen/core/app_settings.py` (recent projects
carry the pack paths and hashes), `rpggen/core/pack_sniff.py` (a cheap "changed since" check),
`tests/gui/test_menus_welcome.py`, `tests/unit/test_pack_sniff.py`

**Spec**
* The recent-projects list becomes cards: the starter map picture (the Results page's picture,
  saved by the orchestrator as `rpggen/preview.png` in the project at promotion), the name, the
  archetype, the date of the last generation and the pack names.
* `pack_sniff.changed_since(pack_path, recorded)` compares a folder's inventory stamp (size and
  mtime of the files, no hashing) or an archive's size and mtime with what the project's config
  recorded. A changed pack gives the card a line `forest.zip changed on 3 Oct` and a
  **Regenerate** button that opens the project at the Generate page with the regeneration
  preview (T12.40).
* A card whose folder is gone says so and offers *Remove from the list* (T12.11's rule: nothing
  is removed by itself).

**Tests**
* Cards show the recorded data; a touched pack file shows the changed line; a missing folder
  shows the removal offer.
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
* The Audit page has the only tour in 1.0: the status colours and glyphs, the queue line, the
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

**Depends on:** T13.28
**Files:** `rpggen/gui/thumbnails.py`, `rpggen/gui/widgets/asset_grid.py`,
`rpggen/gui/widgets/image_view.py`, `rpggen/gui/widgets/map_preview.py`,
`rpggen/gui/pages/generate_page.py`, `rpggen/gui/theme.py`, `rpggen/gui/wizard.py`,
`tests/gui/test_theme_a11y.py`, `tests/gui/test_layout_fit.py`

Two known 1.0 limits (`docs/status.md`): no taskbar progress, and pixmaps that are not
device-pixel-ratio aware.

**Spec**
* Every pixmap the wizard draws (thumbnails, the detail preview, the map preview, archetype
  cards) is rendered at the screen's device pixel ratio and tagged with it, so 150 % and 200 %
  scaling show crisp pixel art at integer scales.
* Taskbar progress on Windows during generation (the `QWinTaskbarProgress` substitute: the
  `ITaskbarList3` COM call through `ctypes`, behind a function that is a no-op elsewhere), and
  the dock badge on macOS through `QApplication.setBadgeNumber` when the window is in the
  background.
* Accessible names and descriptions on every grid cell (`"hero.png, sprite, player, confirmed"`),
  on the status glyphs and on the icon-only buttons; the whole wizard can be driven by keyboard
  (a test tabs through every page and reaches every control).
* **View → Reduce motion** turns off the thumbnail animation, the progress pulse and the tour's
  slide; it defaults to the system's setting where Qt exposes it.

**Tests**
* At DPR 2 a 16-px tile is rendered as a 32-px device image and the overlay lines are 1 device
  pixel.
* The tab order test over all seven pages and the welcome view.
* Accessible names on the grid's cells.

**Done when**
* The tests pass and the two limits are removed from `docs/status.md`.

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
* `ShopDefinition.buys: Array[String]` (categories), optional, default all; the recipe does not
  change the demo shop.
* Gamepad: the quantity is on the row's left/right; the validator's focus chain test covers it.

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
  the starter map still has, and never rewrites a map.
* The map preview legend counts the interiors (`3 interiors`), and the options summary too.

**Tests**
* The plan gives each building its interior id and door column.
* Entering house 2 lands in `interior_2`, leaving returns to house 2's door.
* An existing `interior_1` is untouched by regeneration.

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

**Depends on:** T13.21
**Files:** `godot_templates/addons/rpg_runtime/world/followers.gd`,
`godot_templates/addons/rpg_runtime/archetypes/arpg/components/assist.gd` (new),
`archetypes/arpg/arpg_mode.gd`, `godot_templates/builder/recipes/arpg/arpg_build.gd`,
`builder/recipes/data_recipe.gd`, `godot_templates/tests/unit/test_followers.gd`,
`test_arpg_runtime.gd`, `builder/smoke/smoke_steps_arpg.gd`

**Spec**
* The party (T12.47, T12.69) exists in the ARPG too: `join_party:` works, followers walk behind
  the player as on the top-down maps, and up to two of them carry an `Assist` component: when an
  enemy is within 3 tiles of the player, the follower moves beside it and swings its own hitbox
  (the shared primitives of T13.21) every 1.2 s, with the follower's stats; it never leaves a 6
  tile radius of the player and cannot die (it is "downed" for 5 s at 0 HP, then returns).
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
`tests/unit/test_audio_info.py`, `tests/gui/test_audit_cards.py`

**Spec**
* `audio_info.peaks(path, columns=96)` returns per-column min and max over the decoded samples
  for WAV and OGG (MP3 through the existing frame parser's duration only: no waveform, a flat
  bar). Cached with the other facts.
* The audit card of an audio asset shows the waveform instead of the plain square; the detail
  panel shows it large with a play head, and for music a **Loop** row: start and end in
  milliseconds, draggable markers on the waveform, and **Guess** (`audio_info.guess_loop`: the
  longest pair of 50 ms windows with the smallest RMS difference, start after the first second).
* The loop points are facets (undoable) and the recipe writes them to the `.import` options of
  WAV (`edit/loop_begin`, `edit/loop_end`) and to the OGG stream's `loop_offset`, so the music
  loops at the chosen point in the game.

**Tests**
* Peaks of a synthetic sine; the loop guess on a signal with a repeat.
* The facets round-trip through the catalog; the recipe writes the import options.

**Done when**
* The tests pass.

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
  with a picker from the open map); a graph view (a `GraphEdit`, read-only layout, stages as
  nodes, `next` as edges) beside the form; every change through `EditorUndoRedoManager`; **Test**
  runs the quest against the pretend state (flags, items, gold) and shows the stage it reaches.
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

**Depends on:** T13.12, T13.25 (the lock-and-key planner)
**Files:** `rpggen/core/world_plan.py` (new), `rpggen/core/map_preview.py`,
`rpggen/core/config.py` and `rpggen/schema/config.schema.json` (`starter_map.areas`, optional),
`docs/spec/02_SCHEMAS.md`, `rpggen/gui/widgets/options_sections.py`, `rpggen/gui/widgets/map_preview.py`,
`godot_templates/builder/recipes/starter_map_recipe.gd`, `second_map_recipe.gd` (becomes the
area recipe), `data_recipe.gd`, `godot_templates/tests/unit/test_map_build.gd`,
`tests/unit/test_world_plan.py` (new), `tests/integration/test_m4_sample.py`

The planner makes one starter map, a house and a field.

**Spec**
* `starter_map.areas`: a list of `{name, biome, size, enemies, chests}` with biomes `village`,
  `field`, `forest`, `cave`, `shore`; omitted means today's starter map and field. Each biome
  chooses its ground set by role and tags (`forest` prefers GROUND assets tagged `grass` with
  the most DECORATION trees; `cave` prefers `stone` with WALL cliffs; `shore` adds WATER). A
  biome whose assets are missing falls back to the previous one with a note in the report.
* `world_plan.plan(areas, seed, catalog)` lays the areas on a 2D grid (the village in the
  middle), joins neighbours with door pairs on facing edges, places chests and enemies per area,
  and uses the lock-and-key planner of T13.25 (`lockkey.py`) to put one key (T12.70) in an area
  before the gate that closes the cave. Deterministic from the seed.
* The Options page: the *Starter map* box gains an *Areas* table (add, remove, reorder; name,
  biome, size, enemies, chests) and the preview shows the world as tiles of areas with their
  doors; clicking an area previews it. Reroll works per area.
* The world map (T12.64) is seeded with the areas' placement, so it shows the layout before the
  player has visited every area.
* Regeneration: areas are `user_seed` like the starter map; a project with maps keeps them, and
  an added area is built only when it does not exist.

**Tests**
* The grid placement is deterministic; every area is reachable from the village; the key is
  reachable before the gate.
* The biome fallback and its note.
* The Options table edits are undoable; the preview draws one tile per area.
* Integration: a three-area world generates, validates and passes the smoke test on the sample
  pack.

**Done when**
* The tests pass.

---

# Part D — The Metroidvania archetype

**Files live in** `godot_templates/addons/rpg_runtime/archetypes/metroidvania/`,
`godot_templates/builder/recipes/metroidvania/` and `builder/smoke/smoke_steps_metroidvania.gd`.
The archetype shares the title screen, settings, saving, inventory, equipment, dialogue, shops,
quests, credits, input glyphs, languages and the pause menu with the other two. It does **not**
use the top-down `RpgActor`, the party on the map, encounter zones, followers, Y-sort or the
interior recipe.

## T13.21 — Shared real-time combat primitives

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_runtime/combat/realtime/` (new: `damage_info.gd`,
`hitbox.gd`, `hurtbox.gd`, `health.gd`, `projectile.gd`, `state_machine.gd`, `pickup.gd`,
`screen_feedback.gd`, moved from `archetypes/arpg/`), every script under `archetypes/arpg/` that
preloads them, `godot_templates/builder/recipes/arpg/*.gd`, `rpggen/core/promote.py` (the move is
a ledger rename), `godot_templates/tests/unit/test_arpg_runtime.gd`, `test_ranged_combat.gd`

The ARPG primitives (`class_name` scripts) are needed by T13.23 and T13.15, and an archetype's
folder is filtered out of the other archetypes' projects.

**Spec**
* The eight scripts move to `combat/realtime/`; class names and behaviour are unchanged. Every
  `preload` and `load` path is updated; no copy remains.
* Regeneration of an ARPG project: the ledger sees the old paths as removed and the new ones as
  added, both generated-owned, so promotion deletes and writes them; the runtime changelog says
  so under 1.0.0. A user script that preloaded the old path is the user's to fix: the generated
  README's upgrade note lists the old and new paths.
* `combat_mode.gd` documents which archetypes use the real-time set.

**Tests**
* The existing ARPG and ranged tests pass unchanged except for paths.
* `test_template_project` asserts no script under `archetypes/arpg/` defines the moved classes.
* Regeneration integration: an ARPG project generated before the move regenerates cleanly.

**Done when**
* The tests pass and `godot-test` is green.

---

## T13.22 — Side-view detection: tags, collision values, backgrounds

**Depends on:** nothing
**Files:** `rpggen/core/classifier.py`, `rpggen/core/catalog.py`,
`rpggen/schema/catalog.schema.json` (`CollisionSpec` values), `docs/spec/02_SCHEMAS.md`,
`rpggen/core/adapters/naming.py`, `rpggen/core/requirements.py`, `rpggen/core/mapping.py`,
`tools/make_synthetic_packs.py` (a `platformer` pack), `tests/unit/test_classifier.py`,
`tests/unit/test_requirements.py`, `tests/unit/classifier_cases.json`

**Spec**
* `CollisionSpec` gains the values `one_way` (a platform the player jumps through from below
  and drops through with down + jump) and `ladder` (climbable, no collision). The grid editor
  and bulk panel offer them for `tiles` assets; the TileSet recipe (T13.23) reads them.
* Tags detected from folder and file words: `platform` (platform, ledge), `one_way` (oneway,
  one_way, semi, thin platform), `ladder` (ladder, rope, vine), `hazard` (spike, spikes, lava,
  thorn, saw), `save_point` (save, checkpoint, bench), `ability` (powerup, power_up, upgrade,
  ability, orb), `parallax:<n>` (`bg_far`, `background_1`, `layer2`; `far`, `mid`, `near` give
  1, 2, 3). Tags change nothing in the other archetypes; the top-down goldens do not move.
* `classifier.pack_view(inventory)` guesses `side` or `top` per pack from the words
  (platformer, sidescroller, metroidvania, jump; versus rpg, topdown, overworld) and from
  character sheets whose animations include `jump` or `fall` and no `up` or `down` walk. It is a
  pack warning, shown on the pack card, and the Archetype page's hint (T13.28).
* `requirements.REQUIRED["metroidvania"] = ["PLAYER", "GROUND"]`; `OPTIONAL` adds the roles
  the archetype uses: `BACKGROUND` (parallax layers), `DECORATION`, `ENEMY`, `BOSS` (the
  guardian), `ITEM`, `NPC`, `UI`, `PORTRAIT`; mapping labels say what each is for ("Ground
  tiles: floors and walls of every room").
* Synthetic pack `platformer`: a 16-px tile sheet with ground, one-way platforms, a ladder and
  spikes (folders `tiles/platforms`, `tiles/ladders`, `tiles/hazards`), a hero with idle, run,
  jump, fall, climb, attack and dash (whole strips), a patrol enemy, a flyer, a guardian, a save
  bench, two ability orbs, three parallax backgrounds, a sign and an NPC. Golden added.

**Tests**
* The classifier cases for every new tag and for `pack_view`.
* The collision values validate; the facets round-trip.
* The platformer golden; no other golden moves.

**Done when**
* The tests pass and the corpus is unchanged.

---

## T13.23 — Platform actor

**Depends on:** T13.21, T13.22
**Files:** `archetypes/metroidvania/platform_actor.gd`, `platform_player.gd`, `platform_input.gd`,
`platform_math.gd`, `metroidvania_mode.gd`, `metroidvania_strings.gd` (all under
`godot_templates/addons/rpg_runtime/archetypes/metroidvania/`), `godot_templates/builder/recipes/tileset_recipe.gd`
(physics layers for `one_way`, `ladder` and the `hazard` custom data), `builder/recipes/metroidvania/mode_recipe.gd`,
`builder/recipes/metroidvania/player_recipe.gd`, `builder/recipes/project_settings_recipe.gd`
(input actions `jump`, `dash`, `attack`, `down`; gravity), `godot_templates/tests/unit/test_platform_actor.gd` (new)

```gdscript
class_name RpgPlatformActor extends CharacterBody2D
@export var run_speed := 110.0           # px/s at 16 px tiles; scaled by tile_size / 16
@export var jump_height_tiles := 3.25    # the peak of a full jump
@export var jump_time_to_peak := 0.38    # s; gravity and jump speed derive from these two
@export var fall_gravity_mul := 1.6      # falls faster than it rises
@export var coyote_s := 0.1
@export var jump_buffer_s := 0.12
@export var max_fall_speed := 360.0
var facing := 1                           # -1 left, 1 right; flips the sprite, never the body
var on_ladder := false
signal landed(speed: float)
signal jumped
```

**Spec**
* Movement in `_physics_process` with `move_and_slide`, `floor_snap_length` set, up direction
  `Vector2.UP`. A jump released early cuts the upward velocity in half (variable height).
  Coyote time and a jump buffer as exported above. Wall slide (0.3× fall speed against a wall
  while pushing into it) and wall jump are gated behind the `wall_jump` ability (T13.24); dash
  behind `dash`; a second jump behind `double_jump`.
* One-way platforms: tiles with collision `one_way` are on physics layer 2 with
  `one_way_collision` **⚠ VERIFY** (`TileSet.set_physics_layer_collision_layer`, polygon
  `one_way` flag); down + jump drops through for 0.2 s by disabling the mask bit.
* Ladders: tiles with `ladder` are custom data `ladder = true`; up or down over one enters
  climbing (gravity off, `climb` animation, 70 px/s); jump or leaving the tile exits.
* Hazards: custom data `hazard = true`; touching one costs 1 HP, 0.6 s invulnerability, and a
  return to the last safe ground position (the last cell stood on for 0.25 s) after a 0.3 s
  fade. Death at 0 HP goes through the shared defeat policy (`combat/defeat_policy.gd`): the
  game-over screen, or the last save station (T13.27).
* Animation: `idle`, `run`, `jump`, `fall`, `climb`, `attack`, `dash`, `hurt` through the
  existing `RpgAnimationDriver` with a side-view facing (left is right mirrored unless the pack
  has `left`). A character without `jump` or `fall` uses `idle` in the air, with `ASSET-030`
  (informational) in the report.
* Attack: a hitbox on the facing side on the attack's active frames (T13.21 primitives), damage
  from `get_stat("attack")` so equipment counts. Enemies' hurtboxes as in the ARPG.
* `platform_math` holds the derived gravity and jump speed (`2h/t²`, `2h/t`) and is pure.
* Interaction (`interact`) works with NPCs, signs, doors and save stations that face either
  way: the nearest interactable within a tile ahead.

**Tests**
* `platform_math`: a full jump reaches 3.25 tiles ±2 %; a released jump is lower.
* Coyote: a jump pressed 0.08 s after leaving a ledge succeeds; 0.15 s fails. The buffer: a
  press 0.1 s before landing jumps on landing.
* One-way: the actor lands from above, passes from below, and drops with down + jump.
* Ladder enter and exit; hazard damage, invulnerability and the return to safe ground.
* Attack hits an enemy hurtbox on the facing side only.

**Done when**
* `godot-test` is green and the probe for the one-way tile flag is in `godot_api_verified.md`.

---

## T13.24 — Abilities and gates

**Depends on:** T13.23
**Files:** `godot_templates/addons/rpg_runtime/core/game_state.gd` (`abilities`),
`archetypes/metroidvania/ability_pickup.gd`, `ability_gate.gd`, `abilities.gd` (the table),
`platform_player.gd`, `ui/strings.gd`, `godot_templates/addons/rpg_runtime/world/gate.gd` (a gate
may require an ability), `dialogue/condition.gd` (`ability:<id>` atom), `godot_templates/tests/unit/test_abilities.gd`
(new), `test_game_state.gd`, `test_save_manager.gd`

**Spec**
* `abilities.gd`: `double_jump`, `dash` (a 0.18 s burst at 3× run speed, invulnerable, 0.6 s
  cooldown, one per airtime), `wall_jump`, `high_jump` (+1.25 tiles), `break_blocks` (the attack
  breaks tiles whose custom data `breakable = true`; the cells are remembered in the save under
  `broken_cells`). Each has a name key, a description key and an icon (the ITEM or ability asset
  chosen by the recipe; a generated glyph otherwise).
* `GameState.abilities: Array[String]` (optional key, default empty); `grant(id)` emits
  `ability_granted`; the player reads the set every frame (no caching, so a cutscene can grant
  mid-air).
* `RpgAbilityPickup` (Area2D, persistent by entity id): touching it grants the ability, plays
  `sfx_pickup`, shows a toast with the name and the key hint (`Press [Space] twice`), and
  removes itself (the `persistent` flag of T12.70's objects).
* `RpgAbilityGate`: a wall or a marker the planner uses; the gate itself is only geometry (a
  ledge too high, a gap too wide, a breakable wall). `RpgGate` (T12.70) gains
  `required_ability` beside `required_key`, so a door can also ask for an ability.
* The dialogue condition atom `ability:<id>`; the dialogue tab's checker knows it.

**Tests**
* Grant, save and load round trip; a save without `abilities` loads empty.
* A pickup grants once and is gone after reload.
* Double jump: a second press in the air gives a second jump, once; dash: the distance and the
  cooldown; wall jump only with the ability.
* The condition atom.

**Done when**
* The tests pass.

---

## T13.25 — Rooms, camera and the world graph

**Depends on:** T13.24
**Files:** `rpggen/core/room_plan.py` (new), `rpggen/core/lockkey.py` (new: the lock-and-key
planner, shared with T13.20), `rpggen/core/map_preview.py` (side-view rendering), `rpggen/core/config.py`
and `rpggen/schema/config.schema.json` (`starter_map` for `metroidvania`: `rooms` 3–12,
`room_size` [40, 23] by default, `abilities` a list from the table, `enemies`, `pickups`),
`docs/spec/02_SCHEMAS.md`, `godot_templates/builder/recipes/metroidvania/rooms_recipe.gd` (new),
`builder/recipes/metroidvania/metroidvania_build.gd`, `archetypes/metroidvania/room.gd`,
`room_camera.gd`, `room_exit.gd`, `parallax_recipe.gd`, `godot_templates/addons/rpg_runtime/world/scene_router.gd`
(a transition without a fade for room exits), `godot_templates/tests/unit/test_rooms.gd` (new),
`tests/unit/test_room_plan.py` (new), `tests/unit/test_lockkey.py` (new)

**Spec**
* **Room.** A map scene (`RpgRoom extends RpgMapRoot`) one or more screens large, with layers
  `Background` (parallax, built from BACKGROUND assets by `parallax:<n>`, scrolled by
  `ParallaxBackground` **⚠ VERIFY** the 4.7 `Parallax2D` node), `Ground`, `Platforms`,
  `Hazards`, `Decoration`, `Foreground`, and exits on its edges (`RpgRoomExit`: an Area2D on
  the edge with `target_room`, `target_exit`). Crossing an exit changes the room with the
  player's velocity kept and a 0.25 s camera slide; no fade. `RpgRoomCamera` clamps to the
  room's limits and looks ahead 2 tiles in the facing direction.
* **World graph.** `room_plan.plan(options, seed, catalog)` makes `rooms` rooms on a grid of
  screens: a start room (save station, sign), corridors, a vertical shaft, a guardian room,
  pickup rooms (one per ability in `abilities`) and an end room (an NPC with a line and the
  credits trigger). Rooms connect through exits on shared edges. Every room has a ground floor
  with platforms placed by the biome-less platformer rules: platforms reachable by a full jump
  (≤ 3 tiles up, ≤ 4 across) unless the room is a gate.
* **Lock and key.** `lockkey.plan(graph, keys)` orders the pickups along a critical path so that
  each gate (a 5-tile ledge needs `double_jump` or `high_jump`, a 6-tile gap needs `dash`, a
  breakable wall needs `break_blocks`, a shaft needs `wall_jump`) is reachable only after its
  ability, that every ability is reachable with the ones before it, and that the end room needs
  them all. It is a pure function over an abstract graph, also used by T13.20 with keys instead
  of abilities. An unsolvable layout (too few rooms for the abilities) is `VAL-027` with the
  count needed; a room without a partner exit is `VAL-028`. The planner never emits either on
  its own output (a test proves it over 200 seeds), so they exist for user edits and
  imported rooms.
* **Preview.** The Options page's preview draws the world as a grid of screens with the exits,
  the pickup icons and the gates' letters, in side-view colours; clicking a room shows its
  platforms. `tools/make_map_plan_cases.py` gets side-view cases.
* **Recipe.** `rooms_recipe` writes `game/maps/rooms/<room_id>.tscn` (user_seed), the exits
  with their targets, the save station, the pickups and the enemies (T13.26) from the plan; the
  boot scene's first scene is the start room. `minimap_recipe` renders rooms like any map.

**Tests**
* `room_plan`: deterministic; the room count; every room reachable through exits; the
  critical path order; no VAL-027/028 over 200 seeds; the option bounds.
* `lockkey`: a solvable and an unsolvable graph; the order is stable.
* `test_rooms.gd`: an exit changes the room and keeps velocity; the camera clamps; the parallax
  layers scroll at their factors.
* The preview draws one cell per room.

**Done when**
* The tests pass; VAL-027 and VAL-028 are in `03_ERROR_CODES.md` and `docs/errors.md`.

---

## T13.26 — Side-view enemies and the guardian

**Depends on:** T13.25
**Files:** `archetypes/metroidvania/enemies/patrol.gd`, `flyer.gd`, `shooter.gd`, `guardian.gd`,
`enemy_base.gd` (all new), `builder/recipes/metroidvania/enemy_recipes.gd`, `builder/recipes/data_recipe.gd`
(enemy definitions for the archetype), `godot_templates/tests/unit/test_side_enemies.gd` (new)

**Spec**
* `RpgSideEnemy` (CharacterBody2D with the shared hurtbox and health): takes damage, knockback
  along x, drops loot (the ARPG's loot table), is persistent (dead stays dead per room until a
  save station is used, then respawns, as a metroidvania does).
* **Patrol:** walks on its platform, turns at an edge or a wall (a `RayCast2D` ahead and down),
  hurts on contact. **Flyer:** no gravity; hovers on a sine, chases within 5 tiles, returns to
  its anchor. **Shooter:** stands, fires a projectile (T13.21) at the player every 1.5 s when
  in line of sight within 8 tiles. The kind comes from the enemy asset's tags (`fly`, `bat`,
  `bird` → flyer; `shoot`, `turret`, `archer` → shooter; else patrol), overridable in the
  catalog.
* **Guardian:** the BOSS asset (or the ENEMY with the most HP) in the guardian room: 20 HP at
  tile size 16 scaled by the stats, three phases (walk and lunge; add a jump that shakes the
  room and drops a projectile from the ceiling; faster), telegraphed by a 0.4 s `hurt`-tinted
  pause; the room's exits close (gates) while it lives; its death opens them, grants the first
  ability of the plan and sets `defeated:<id>`.
* `data_recipe` gives each enemy of the archetype a definition with HP, attack, XP and gold from
  its `enemy_definition` defaults.

**Tests**
* The patrol turns at an edge and a wall; the flyer returns; the shooter fires on sight only.
* The guardian's phases change at the HP thresholds; death opens the exits and grants the
  ability.
* Persistence across a room change and respawn after a save.

**Done when**
* The tests pass.

---

## T13.27 — HUD, room map and save stations

**Depends on:** T13.26
**Files:** `archetypes/metroidvania/ui/hud.gd`, `save_station.gd`, `builder/recipes/metroidvania/hud_recipe.gd`,
`godot_templates/addons/rpg_runtime/ui/minimap.gd` and `world_map_menu.gd` (room mode),
`world/minimap_data.gd`, `core/save_manager.gd` (save stations as the save point when the
archetype says so), `combat/defeat_policy.gd`, `ui/strings.gd`, `godot_templates/tests/unit/test_minimap.gd`,
`test_save_manager.gd`, `test_metroidvania_ui.gd` (new)

**Spec**
* **HUD:** HP as pips (one per 4 HP, from the UI asset's frame or a generated pip), the
  abilities as icons that light up when granted, the equipped weapon, gold. Toasts for pickups.
* **Room map:** the minimap and the world map show rooms as cells of the world grid: visited
  rooms filled, the current one outlined, save stations and unused pickups marked, the exits
  as notches. The fog of T12.64 is per room instead of per cell, with the same save key
  (`map_fog` holding `{rooms: [...]}` for this archetype; a top-down save is unaffected).
* **Save stations:** `RpgSaveStation` (interact → the save menu). The archetype's settings
  (`metroidvania_mode`) make the pause menu's *Save* say *Save at a station* and disable it;
  autosave happens on every room change into a slot `auto`. Using a station restores HP,
  respawns the room's enemies and sets the respawn point; the defeat policy returns the player
  to the last station used with the state of the autosave (the metroidvania convention: progress
  since the last save is kept, position is not).

**Tests**
* The HUD reflects HP, abilities and gold.
* The room fog marks the visited rooms and survives a save; a top-down save is unchanged.
* A station saves, restores HP and respawns enemies; the defeat policy returns to it.

**Done when**
* The tests pass.

---

## T13.28 — Wizard: the Metroidvania card, roles, options and preview

**Depends on:** T13.27
**Files:** `rpggen/features.py` (`METROIDVANIA_AVAILABLE`), `rpggen/gui/pages/archetype_page.py`,
`rpggen/gui/pages/mapping_page.py`, `rpggen/core/mapping.py`, `rpggen/core/requirements.py`,
`rpggen/core/options.py`, `rpggen/gui/models/options_model.py`, `rpggen/gui/pages/options_page.py`,
`rpggen/gui/widgets/options_sections.py`, `rpggen/gui/widgets/map_preview.py`, `rpggen/core/config.py`,
`rpggen/core/orchestrator.py` (`ARCHETYPE_SMOKE_STEPS`), `rpggen/core/staging.py` (`ARCHETYPES`),
`rpggen/core/dry_run.py`, `rpggen/core/report.py`, `rpggen/cli.py` (`--archetype metroidvania`),
`godot_templates/project_files/README.metroidvania.md` (new), `tests/gui/test_archetype_page.py`,
`tests/gui/test_options_page.py`, `tests/gui/test_mapping_page.py`, `tests/unit/test_config.py`,
`tests/gui/test_layout_fit.py`

**Spec**
* A third card, **Metroidvania** (Run → Jump → Find an ability → Open the way → Explore), drawn
  with the pack's art like the others (T12.34): the player's `jump` or `run` frame if it has
  one. The page's hint reads `pack_view` (T13.22): a pack that looks side-view suggests this
  card, a top-down pack shows "Your characters have walk-down animations; a metroidvania uses
  side-view sprites" under the card without disabling it. A player without a `jump` animation
  gets the ASSET-030 line as the ARPG's swing warning is shown.
* The card is disabled with the tooltip "Coming in a later version" while
  `METROIDVANIA_AVAILABLE` is false; T13.31 sets it true.
* Mapping: the archetype's role list and labels; the Sound section's slots gain `sfx_jump`,
  `sfx_land`, `sfx_dash`, `sfx_ability` (fixed slots, filled by name as the others).
* Options: the *Starter map* box becomes *Starter world* for this archetype: rooms, room size,
  the abilities (checkboxes in the plan's order), enemies and pickups; the preview is the
  side-view one of T13.25; the layer list is the room layers; *Navigation* is hidden (no
  pathfinding); the summary panel and the dry run describe the world ("6 rooms, 2 abilities,
  a guardian").
* The generated README (`README.metroidvania.md`) explains the controls, the rooms folder, how
  to add a room (copy one, set the exits), the abilities table, the gates, enemies by tag, save
  stations and the map.
* The CLI accepts the archetype; the report names it; `dry_run` plans the world.

**Tests**
* The card's state with the flag on and off; the hint for a side-view and a top-down pack.
* The options model for the archetype; the summary text; the config round trip with the new
  `starter_map` keys; T12.16 for the third archetype in both themes.

**Done when**
* The tests pass with the flag on in the test session (the gate flips the default).

---

## T13.29 — Metroidvania smoke steps and integration test

**Depends on:** T13.28
**Files:** `godot_templates/builder/smoke/smoke_steps_metroidvania.gd` (new),
`tests/integration/test_m13_sample.py` (new), `tests/integration/test_all_synthetic_packs.py`,
`tests/integration/test_determinism.py`, `tools/build_sample_pack.py` (the sample pack gains a
side-view hero strip, a platform tile row and a bench so it can play all three archetypes)

Appended after the M6 sequence (title, new game, dialogue, inventory, save and load):
1. `jump_clears_gap` — in the start room, run right and jump; the player lands on the far side of
   the 3-tile gap.
2. `one_way_platform` — jump through the one-way platform from below and stand on it; press down
   + jump and fall through.
3. `hazard_hurts_and_returns` — walk onto the spikes; HP drops by 1 and the player is back on the
   last safe ground within 1 s.
4. `gate_blocks` — at the double-jump ledge, jump; the player does not reach the ledge within 2 s.
5. `room_transition` — walk through the east exit; the current room changes and the player
   appears at the matching west exit with the same facing.
6. `guardian_dies` — enter the guardian room; the exits close; boost attack to 99 and attack until
   `died`; the exits open and `abilities` contains the first ability.
7. `double_jump_reaches_ledge` — back at the ledge, jump twice; the player stands on it.
8. `pickup_dash` — touch the dash orb; `abilities` contains `dash`; the toast is shown.
9. `dash_crosses_gap` — at the 6-tile gap, dash; the player lands across.
10. `save_station_persist` — use the station; quit to the title; continue; the player is at the
    station with both abilities, and the room's enemies are back.
11. `end_room` — reach the end room and talk to the NPC; the credits flag is set.

**Tests**
* `test_m13_sample.py` generates the sample pack as `metroidvania`, validates, runs the smoke test
  and asserts the step list `M13_STEPS`; the synthetic `platformer` pack passes too, and the
  determinism test covers the archetype.
* The `basic16` pack (no jump animation) generates with ASSET-030 and passes the smoke test
  with the idle frame in the air.

**Done when**
* The integration tests pass locally with `RPGGEN_GODOT` set, and in CI.

---

# Part E — Documentation and the gate

## T13.30 — Documentation, screenshots and changelogs

**Depends on:** Parts A–D
**Files:** `README.md`, `docs/user_guide.md`, `docs/status.md`, `docs/errors.md` (generated),
`docs/spec/02_SCHEMAS.md`, `docs/spec/03_ERROR_CODES.md`, `docs/architecture.md` (§48 deferred
list: remove what this milestone did), `CHANGELOG.md`, `godot_templates/addons/rpg_runtime/CHANGELOG.md`
and `README.md`, `godot_templates/project_files/README.template.md`, `tools/make_doc_screenshots.py`,
`docs/images/*`, `tests/gui/test_doc_screenshots.py`

* The user guide: review mode, folder groups, similar assets, the picker gallery, the presets
  and dependencies, the estimate, the dashboard, the tour, the accessibility options; shops,
  interiors, validator ids, zstd, ARPG followers, custom slots, waveforms and loops; variants,
  the quest and cutscene tabs, areas; and a section **Metroidvania** (choosing it, the roles,
  the world options, playing: controls, abilities, rooms, save stations, the map; editing rooms
  in Godot).
* Screenshots: the Archetype page with three cards, the review mode, the side-view preview, the
  variant dialog, the areas table, the Quests tab. `test_the_screenshots_match_the_files_the_guide_uses`
  passes.
* `docs/status.md`: M13 in the table and the paragraph; the *Known limits* list drops every
  item a card removed; the manual rows for M13 (T13.31) are listed under *Work only a person
  can do*.
* Both changelogs under 1.0.0; the runtime README's archetype section has the metroidvania.

**Done when** the docs test passes and no document mentions "two archetypes".

---

## T13.31 — Gate (M13)

**Depends on:** T13.30

* `METROIDVANIA_AVAILABLE = True`; the wizard's metroidvania path is covered by an automated GUI
  integration test (as T9.08 asked for the ARPG).
* Every suite is green on Windows and Ubuntu, on both PySide6 legs; perf is within its
  ceilings, with a ceiling added for the metroidvania generation of the sample pack.
* T12.16 passes at the minimum size in both themes for all three archetypes, with review mode
  and folder groups on.
* All three archetypes pass the smoke test on the sample pack and every synthetic pack,
  including `platformer`; generated projects contain only their own archetype folder (the
  template test of T13.21).
* The corpus (T12.26) is unchanged on all four measures after T13.04, T13.18 and T13.22.
* Manual rows, added to the T12.66 pass: play the metroidvania demo to the end room with a
  gamepad (jump feel, coyote time, the wall slide, the guardian's telegraphs); buy three of an
  item and sell all; enter two houses; use review mode and folder groups on a 300-asset pack at
  150 % scaling; make a variant enemy and meet it in the game; edit a quest in the graph and a
  cutscene step; generate a three-area world; set a loop point and hear it in the game; add a
  custom slot; check a Tiled map with a zstd layer; a follower assists in the ARPG.
* `docs/status.md` lists nothing from this milestone as open except the manual rows.

**Done when** all of the above is true. Then T12.66 runs (its held-out runs after T13.22 and
T13.18, since both change the catalog), and `v1.0.0` is tagged.

---

# Appendix — Review items to cards

The review of 2026-10-08 listed 10 UI/UX items, 7 feature improvements and 3 feature additions;
the metroidvania archetype was asked for with them. Every item maps to exactly one card.

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
| Addition 3: a world of connected maps | T13.20 |
| Metroidvania archetype | T13.21 – T13.29 |
