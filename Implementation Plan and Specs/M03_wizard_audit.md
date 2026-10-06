# M3 — Wizard, Audit, Object Cutter, Profiles, Sample Pack

**Goal:** a non-developer can map a 500-asset pack in under 15 minutes and generate a project without touching the command line.

**GUI rules (apply to every card):**
* PySide6 only; no QML. Add `pytest-qt>=4.4` to the dev dependencies.
* The GUI never blocks the UI thread for more than 50 ms. Anything slower runs in a worker (T3.02).
* The GUI owns **no business logic**. It edits a `WizardState` and calls core functions.
* Every widget has an `objectName`, so tests can find it with `findChild`.
* All user-visible strings go through `self.tr()`, so the wizard can be translated later.
* Use the default Fusion style plus one stylesheet file, `rpggen/gui/style.qss`. Never hard-code colors in widget code.

---

## T3.01 — App shell and wizard state

**Depends on:** M2 gate
**Files:** `rpggen/gui/app.py`, `rpggen/gui/wizard.py`, `rpggen/gui/state.py`, `rpggen/gui/style.qss`, `rpggen/cli.py` (`gui` subcommand; no subcommand also opens the GUI), `tests/gui/test_shell.py`

```python
@dataclass
class WizardState:
    project_name: str = ""
    target: Path | None = None
    godot_exe: Path | None = None
    pack_sources: list[Path] = field(default_factory=list)
    archetype: str = "turn_based"
    opened_packs: list[OpenedPack] = field(default_factory=list)
    inventories: list[Inventory] = field(default_factory=list)
    catalog: Catalog | None = None          # assembled, with user overrides applied
    config: GeneratorConfig | None = None
    placeholders: set[str] = field(default_factory=set)
    regenerating: bool = False              # target is an existing rpggen project

def draft_path(target: Path) -> Path:
    """local_cache_dir()/drafts/<sha256(str(target.resolve()).casefold())[:16]>.json"""
```

* `MainWindow(QMainWindow)` has a left sidebar (a `QListWidget` of the 7 page names; it shows the current page, and clicking is allowed only for pages already visited), a central `QStackedWidget` and a bottom bar with **Back**, **Next** (or **Generate** on page 5) and **Cancel**.
* Each page subclasses `WizardPage(QWidget)` with:
  * `enter(state)` — called when the page is shown.
  * `validate(state) -> list[Issue]` — Next is disabled while any error-severity issue exists.
  * `leave(state)` — writes the page's widget values into the state.
* **Drafts:** after every `leave()`, save the catalog overrides, folder rules, objects and config to `draft_path(target)` with jsonio. When page 1 is completed for a target that has a draft, ask "Resume previous session?".
* For an existing generated project, the state loads from `<target>/rpggen/*.json` instead, and `regenerating=True`.
* Unhandled exceptions: install `sys.excepthook` to show a dialog with GUI-001, the traceback in a collapsible box, and an "Export diagnostic bundle" button. The button is disabled until M10.

**Tests (pytest-qt):** the window opens; Next is disabled on an empty page 1; the sidebar reflects the current page.

---

## T3.02 — Background workers

**Depends on:** T3.01
**Files:** `rpggen/gui/workers.py`, `tests/gui/test_workers.py`

```python
class WorkerSignals(QObject):
    progress = Signal(str, int, int)   # phase/label, i, n
    log = Signal(str)
    finished = Signal(object)          # result
    failed = Signal(object)            # Issue or exception

class Worker(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args, **kwargs): ...
    # run(): calls fn(*args, callbacks=Callbacks(on_phase=..., on_log=..., is_cancelled=...))
    # emits finished/failed. Never touches widgets.
    def cancel(self) -> None: ...      # sets a threading.Event checked by is_cancelled
```

* Use `QThreadPool.globalInstance()`.
* Analysis uses processes internally (T2.02). That works from a QRunnable on Windows only if `multiprocessing.freeze_support()` is called in `__main__` and the frozen app. Add that call now.
* Long-running worker functions: `analyze_packs(state)` (open, inventory, assemble), `generate(state)` (`orchestrator.run`), `load_thumbnails(...)` (T3.05).

**Tests:** a worker emits finished; cancel stops a looping function within 1 s; an exception emits failed.

---

## T3.03 — Page 1: Project

**Depends on:** T3.02
**Files:** `rpggen/gui/pages/project_page.py`, `tests/gui/test_project_page.py`

The page contains:
* **Asset packs:** a list with Add Zip/7z…, Add Folder… and Remove buttons. Drag-and-drop of files and folders onto the list is accepted.
* **Output folder:** a path field and a Browse button.
* **Godot 4.7.2:** a combo box pre-filled from `auto_find_godot()`, plus Browse. Next to it is a status label that shows the version after detection runs in a worker.
* **Project name:** defaults to the output folder name.

Validation runs live (debounced 300 ms) and shows a red or green line under each field:
* Godot — ENV-001/002/003 from `detect_version`.
* Output — ENV-004/006/007/008/009 from the new function `preflight.check_target(target, packs) -> list[Issue]`. Put `preflight.py` in `rpggen/core/` and move T1.10's preflight checks into it. Free space (ENV-005) is checked once the packs are known: required = 3 × the sum of uncompressed sizes. Read zip sizes from the central directory without extracting.
* At least one pack must be present, and every pack must be readable (it opens without ARCH errors in a quick check: a zip opens and lists entries; a folder exists).
* Name: 1–64 chars.

**Leaving the page** starts `analyze_packs` in a worker and shows a modal progress dialog with Cancel. The results fill `state.opened_packs`, `inventories` and `catalog`. If a draft or existing project exists, overrides are applied through `assemble(..., previous=draft_catalog)`.

**Tests:** fake Godot detection by monkeypatching `detect_version`; check the field validation messages; check that drag-drop adds a pack.

---

## T3.04 — Page 2: Archetype

**Depends on:** T3.03
**Files:** `rpggen/gui/pages/archetype_page.py`

* Two large `QToolButton` cards (checkable, exclusive) with a title, a 2-line description and a small diagram drawn with `QPainter` (boxes and arrows; no images needed): **Turn-based RPG** (Explore → Encounter → Battle → Rewards) and **Action RPG** (Move → Attack → Dodge → Loot).
* The ARPG card shows a warning line if no catalog asset has any `attack_*` animation: "ARPG will use a generic swing effect until you add attack animations."
* Until M9 is done, the ARPG card is disabled with the tooltip "Coming in a later version". Controlled by the constant `ARPG_AVAILABLE = False` in `rpggen/features.py`.

---

## T3.05 — Asset grid (model/view, virtualized)

**Depends on:** T3.03
**Files:** `rpggen/gui/widgets/asset_grid.py`, `rpggen/gui/thumbnails.py`, `tests/gui/test_asset_grid.py`

* `AssetListModel(QAbstractListModel)` exposes one row per **effective** asset (not objects). Roles:
  * `Qt.DisplayRole` → file name
  * `Qt.DecorationRole` → thumbnail QPixmap (or a gray loading placeholder)
  * `AssetIdRole`, `StatusRole`, `RoleRole`, `UsageRole`, `ConfidenceRole`, `PackRole` — custom roles via `Qt.UserRole + n`
* `AssetFilterProxy(QSortFilterProxyModel)` filters by status set, role set, pack and a text search (matching the path, case-insensitive). It sorts by status priority (CONFLICT, NEEDS_REVIEW, MISSING, AUTO_DETECTED, CONFIRMED, UNUSED), then by id.
* The view is a `QListView` in `IconMode` with `uniformItemSizes=True`, grid size 112×132, `setLayoutMode(Batched)` and `ExtendedSelection`.
* `AssetCardDelegate(QStyledItemDelegate)` paints the thumbnail (centered, nearest-neighbor scaled to fit 96×96 at an integer scale where possible), the file name (elided) and a colored status strip on the left edge. The strip colors come from `style.qss` variables mirrored in a Python dict `STATUS_COLORS`.
* `thumbnails.py`:
  * `ThumbnailCache` keeps an LRU of 2,000 QPixmaps.
  * Thumbnails are generated in a worker as PNG bytes. Use Pillow: tiles → the first 4×4 cells; sprites → the first frame; other images → the whole image, fit to 96 px with nearest-neighbor resampling.
  * Bytes are stored on disk in `local_cache_dir()/thumbs/<sha256>_<variant>.png`.
  * QPixmaps are created **only on the UI thread** from those bytes.
* Default filter: "Needs attention" (CONFLICT + NEEDS_REVIEW + MISSING). Toggle chips at the top switch between the status sets.

**Tests:** model row count equals the asset count; the filter changes the visible rows; the delegate paints without exceptions for each status.

---

## T3.06 — Page 3: Audit (detail panel and edits)

**Depends on:** T3.05
**Files:** `rpggen/gui/pages/audit_page.py`, `rpggen/gui/widgets/asset_detail.py`, `rpggen/gui/edits.py`, `tests/gui/test_audit_edits.py`

**Layout:** a filter bar on top; a splitter below with the grid on the left and the detail panel on the right.

**Detail panel**, for a single selection:
* Large preview (`QGraphicsView`, nearest-neighbor, zoom with Ctrl+wheel). A grid overlay is shown when usage is tiles or sprite.
* Fields: path (read-only, with a "Show in folder" button), pack, usage (combo), role (combo, with alternative roles shown as quick buttons and their percentages), confidence bar, status badge, collision profile (combo; only for tiles and objects), tileset (combo of TileSetDef names plus "New…"), tags (comma-separated line edit).
* Buttons: **Confirm** (sets status CONFIRMED without other changes), **Exclude** (sets role NONE), **Edit grid…** (T3.08), **Animations…** (T3.09), **Cut objects…** (T3.10).

**All edits go through `edits.py`**, never by mutating the catalog directly:

```python
def set_override(catalog: Catalog, asset_id: str, key: str, value: Any) -> Catalog
def clear_override(catalog: Catalog, asset_id: str, key: str) -> Catalog
def confirm(catalog: Catalog, asset_ids: list[str]) -> Catalog
```

* Each function returns a new Catalog, using copy-on-write via `dataclasses.replace`.
* Each function pushes onto an **undo stack**: `QUndoStack` with one `QUndoCommand` per edit holding the before and after catalogs. Ctrl+Z and Ctrl+Y work across the page.
* After every edit, call `recompute_status`. If the edit changed grid or usage, also run `assign_tilesets(catalog, previous=catalog)` again, so source ids are kept.

**Tests:** setting the role creates an override and status CONFIRMED; undo restores the previous state; changing the grid keeps existing source ids.

---

## T3.07 — Bulk actions and folder rules

**Depends on:** T3.06
**Files:** `rpggen/gui/widgets/bulk_panel.py`, `rpggen/gui/edits.py` (add bulk functions), `tests/gui/test_bulk.py`

* When more than one asset is selected, the detail panel is replaced by a bulk panel: "N assets selected", combos for role, usage, collision and tileset (each starting at "— unchanged —"), a tags add/remove field, and buttons **Apply**, **Confirm all** and **Exclude all**.
* Bulk edits are one undo command.
* **Folder rules:** right-click a selection → "Make rule for this folder…". This opens a dialog pre-filled with `glob = <common folder>/**`, the pack and the facet values chosen in the bulk panel. Saving appends a FolderRule and re-runs `apply_folder_rules` plus `recompute_status`. Rules are listed in an "Rules" tab, where they can be deleted or reordered (drag); reordering re-applies all rules.
* Keyboard shortcuts on the grid:
  * `C` → confirm the selection
  * `X` → exclude
  * `1`–`9` → set the role to the Nth role in a configurable quick list (default: GROUND, WALL, DECORATION, BUILDING, PLAYER, NPC, ENEMY, ITEM, UI)

**Tests:** a bulk role change on 3 assets is undone in one step; a folder rule applies to matching assets only.

---

## T3.08 — Grid editor

**Depends on:** T3.06
**Files:** `rpggen/gui/widgets/grid_editor.py`, `tests/gui/test_grid_editor.py`

* A modal dialog with a zoomable image view and an overlay that draws the cell boundaries, the margin area (tinted) and the separation gutters.
* Controls: cell w/h spin boxes (with a "square" lock checkbox), margin x/y, separation x/y, and a candidate list showing the top 5 detections with scores (clicking one applies it).
* A live readout shows "cols × rows, N non-empty, remainder r px", plus a warning when the remainder is greater than 0 (ASSET-003).
* **Apply** writes an override for `grid` through `edits.set_override`.

---

## T3.09 — Animation preview and editor

**Depends on:** T3.06
**Files:** `rpggen/gui/widgets/anim_preview.py`, `tests/gui/test_anim_preview.py`

* The left side lists the animation names, with the 4-direction groups shown together.
* The center shows a playback area (QTimer-driven, using the animation's fps and durations; flip_h is honored by mirroring the pixmap) with play/pause, step and a speed slider.
* The bottom shows the sheet with the grid overlay. Clicking cells toggles them in or out of the selected animation's frame list, in click order. "Clear", "Reverse" and "Ping-pong" buttons edit the list.
* Fields: fps, loop, flip_h and active frames (ARPG; hidden for turn-based).
* **Add animation** offers the standard names that don't exist yet. **Mirror from…** creates `<action>_left` from `<action>_right` with flip_h, or vice versa.
* **Origin picker:** click on the frame preview to set `origin`. A crosshair shows the current origin and a horizontal line shows the baseline.
* Apply writes the overrides `animations`, `origin` and `frame`.

---

## T3.10 — Object cutter

**Depends on:** T3.08
**Files:** `rpggen/gui/widgets/object_cutter.py`, `rpggen/gui/edits.py` (object functions), `tests/gui/test_object_cutter.py`

* A dialog showing the sheet with the grid overlay. Existing objects are drawn as labeled rectangles: auto-detected in blue, user-made in green.
* **Tools:**
  * Rectangle — drag, which snaps to the grid by default; hold Alt for pixel precision.
  * Select / move / resize.
  * Footprint — drag inside an object to set its footprint rectangle (drawn in red, semi-transparent).
  * Door point — click to place.
  * Origin — click; the default is the bottom-center of the region.
* Side panel for the selected object: name, role (BUILDING / DECORATION / INTERIOR / NPC…), tags, collision profile (default CUSTOM, generated from the footprint), delete.
* "Accept all suggestions" marks auto objects CONFIRMED. "Reject" deletes the selected suggestion and remembers the rejection: the object goes into the catalog with role NONE so auto-detection doesn't recreate it.
* Object ids: `<sheet_id>#<slug(name)>`, disambiguated.
* `edits.add_object`, `update_object` and `remove_object` are all undoable.

**Tests:** creating an object stores a SheetObject with the correct region, footprint and origin; reject persists across re-assembly.

---

## T3.11 — Page 4: Mapping

**Depends on:** T3.06
**Files:** `rpggen/gui/pages/mapping_page.py`

* A checklist built from `requirements.REQUIRED` and `RECOMMENDED` (T2.15). Each row shows the role, its status (✔ assigned / ⚠ missing / ✖ required missing), the currently selected asset (with a thumbnail) and a **Choose…** button. The button opens a filtered picker (the grid restricted to plausible usage: sprites for characters, tiles for ground, objects and images for buildings).
* Starter selections are stored in `config` under a new key `starter` (add it to the schema):
  `{ "player": asset_id, "npc": asset_id, "enemy": asset_id, "ground": asset_id, "building": object_or_asset_id, "chest": id?, "portrait": id? }`.
  The demo recipes (M4, M6, M7) use these.
* For each missing role, a dropdown offers "Use placeholder" or "Continue without" (recommended roles only). "Assign" is just Choose.
* Required roles that are still missing keep Next disabled.

---

## T3.12 — Page 5: Options

**Depends on:** T3.11
**Files:** `rpggen/gui/pages/options_page.py`

* Feature checkboxes (`config.features`). Dependencies: `demo` requires `dialogue`, `combat` and `save`; `debug_tools` requires nothing. When a required feature is unchecked, the dependent checkbox is unchecked and disabled, and a tooltip says why.
* Resolution presets: 320×180, 384×216, 480×270, 640×360 (default) and Custom. A hint shows "≈ N × M tiles on screen" for the base tile size.
* Window size presets.
* Map layers editor: a reorderable list with add and remove; Ground can't be removed.
* An "Advanced" collapsible section with the seed and the input map table (action → bindings, editable).
* Validation: options come from the config schema; invalid values disable Generate.

---

## T3.13 — Pages 6–7: Generate and Results

**Depends on:** T3.12
**Files:** `rpggen/gui/pages/generate_page.py`, `rpggen/gui/pages/results_page.py`, `rpggen/gui/widgets/log_view.py`

* Generate: on entry, write the final config and catalog to the staging inputs (`orchestrator.run` accepts in-memory `cfg` and `catalog` objects; add an overload) and start the worker.
* The page shows a progress bar (phase index / total), a phase list with ✔/⏳/✖ icons and a log view: `QPlainTextEdit`, read-only, max 10,000 lines, monospace, auto-scrolling unless the user scrolled up.
* Cancel → `worker.cancel()`; the orchestrator discards staging.
* Results — success: counts (assets processed, tilesets, scenes, animation sets, warnings, errors), a warnings list (click → shows the fix text), and buttons **Open in Godot** (runs `godot_exe --path target --editor` detached with `subprocess.Popen`), **Open folder**, **View report** (opens `GENERATION_REPORT.md` in a read-only viewer) and **Restore previous** (M5; disabled until then).
* Results — failure: a red header, the failing phase, the error list with fixes, and buttons **Open failed folder** and **View logs**. **There is no "deliver anyway" button** (decision 6).
* The report itself is written by `report.py` (T5.08 completes it; M3 writes the basic sections: versions, packs, counts, issues).

---

## T3.14 — Pack profiles: export, import and adapter

**Depends on:** T3.10
**Files:** `rpggen/core/profiles.py`, `rpggen/core/adapters/profile.py`, `rpggen/gui/dialogs/profile_dialogs.py`, `tests/unit/test_profiles.py`

* `export_profile(catalog, pack_id, inventory, meta) -> dict`:
  * Includes only assets with overrides or CONFIRMED status; paths relative to the pack; facets = effective facets minus `roles_alt`.
  * Includes objects (`sheet_path`), folder rules and tileset defs (without source ids).
  * Fingerprint: the 20 largest image files by pixel count, ties broken by path.
  * Validates against the profile schema.
* `match_profile(profile, inventory) -> float`: the ratio of fingerprint files present with an equal sha256.
* Profile adapter (priority 0): `match` returns the best ratio among installed profiles in `local_cache_dir()/profiles/*.rpgprofile.json`, or 0. `extract` emits fragments with claim `full` and confidence 0.999 for every profile asset whose file exists with a matching hash; mismatched hashes are skipped and left to normal detection. It emits ADAPT-003.
* GUI: Audit page menu → "Export pack profile…" (asks for title, author and license; the license defaults to CC0-1.0) and "Import profile…" (copies the file into the profiles dir, then re-runs assemble with the existing overrides kept).

**Tests:** round-trip: export from the overridden basic16 → import into a fresh state → the effective facets equal the original's for the exported assets.

---

## T3.15 — Bundled sample pack and "Try it"

**Depends on:** T3.13
**Files:** `sample_pack/` (repo root), `sample_pack/LICENSE.txt`, `sample_pack/SOURCES.md`, `rpggen/gui/pages/project_page.py` (button), `tools/build_sample_pack.py`

* The sample pack must be **CC0**. Either:
  * (a) generate it programmatically with `tools/build_sample_pack.py`: a richer, nicer-looking version of the synthetic generator (16px; 3 ground types, water, walls, a house object in a sheet, 2 trees, a chest, a hero, an NPC, a slime, 4 item icons, simple UI panel and font-free UI); or
  * (b) assemble it from CC0 sources, with every file's origin listed in `SOURCES.md`.

  Option (a) is preferred because it has no provenance risk.
* Include a pre-made `sample.rpgprofile.json`, so the sample pack audit is all-CONFIRMED.
* On page 1, the button **"Try with sample pack"** fills the pack list with the bundled pack (from `templates_root().parent / "sample_pack"`, or the frozen equivalent), sets the target to `Documents/rpggen-sample-<n>` and the name to "Sample RPG", then jumps to page 5.

**Done when:** a fresh user can click Try → Generate → Open in Godot, and the whole flow takes under 2 minutes on a typical machine.

---

## T3.16 — Milestone Gate M3

- [ ] pytest-qt suite green in CI (Windows job; run with `QT_QPA_PLATFORM=offscreen`).
- [ ] The full wizard flow is automated by a GUI integration test on the sample pack: open → Try → Generate → Results success (needs `RPGGEN_GODOT`).
- [ ] Usability check by the human maintainer: map a real 300–500 asset pack and record the time in `IMPLEMENTATION_NOTES.md`. Target: under 15 min.
- [ ] Undo/redo works for every edit type (one test per type).
- [ ] Drafts resume correctly after closing and reopening the app.
