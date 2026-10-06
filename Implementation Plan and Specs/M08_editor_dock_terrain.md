# M8 — Editor Asset Library Dock, Catalog Overrides in Godot, Terrains, Content Tools

**Goal:** inside Godot, the user browses the asset library, drags objects into maps, fixes entity IDs, edits catalog overrides and regenerates affected resources without leaving the editor. Terrains work for Tiled Wang sets, RPG Maker A2 autotiles and recognized blob/Wang layouts.

All editor code lives in `godot_templates/addons/rpg_project_tools/` and every script starts with `@tool`.

---

## T8.01 — Plugin skeleton

**Depends on:** M7 gate
**Files:** `plugin.cfg`, `plugin.gd`, `dock/asset_dock.gd`, `project_settings_recipe.gd` (enable the plugin)

`plugin.cfg`:
```ini
[plugin]

name="RPG Project Tools"
description="Asset library, placement and catalog tools for rpggen projects."
author="rpggen contributors"
version="0.1.0"
script="plugin.gd"
```

`plugin.gd`:
```gdscript
@tool
extends EditorPlugin
var dock: Control
func _enter_tree() -> void:
	dock = preload("res://addons/rpg_project_tools/dock/asset_dock.tscn").instantiate()  # see note
	add_control_to_dock(DOCK_SLOT_RIGHT_UL, dock)    # ⚠ VERIFY: 4.6+ may have a newer dock API; use it if add_control_to_dock is deprecated
	dock.plugin = self
func _exit_tree() -> void:
	remove_control_from_docks(dock)
	dock.queue_free()
```

* The dock **scene** is built by a recipe (`builder/recipes/tools_dock_recipe.gd`), like every other scene, into `addons/rpg_project_tools/dock/asset_dock.tscn`. The `preload` path must therefore exist. Because the builder runs before validation, that's fine.
* Enable the plugin with the project setting `editor_plugins/enabled = PackedStringArray("res://addons/rpg_project_tools/plugin.cfg")`. ⚠ VERIFY.
* The plugin must **never** run game logic and must never write inside `generated/` except through the builder.

---

## T8.02 — Asset Library dock UI

**Depends on:** T8.01
**Files:** `dock/asset_dock.gd`, `dock/asset_item.gd`, `dock/index.gd`

* `index.gd` loads `res://rpggen/object_index.json` (object id → scene path), `res://rpggen/asset_catalog.json` (for roles, tags and names) and `res://rpggen/character_index.json`, a new file written by `actor_recipes` (character asset id → scene path). It builds entries `{id, name, role, category, scene_path, icon_texture}`.
* Categories (tabs or a filter OptionButton): All, Buildings, Decorations, Interior, Characters, Enemies, Items, Interactables.
* UI: a search LineEdit (filters by name, id and tags; case-insensitive), a category filter, and an `ItemList` in icon mode (icon = the scene's sprite texture or first frame, scaled 48 px, nearest filtering) or a `GridContainer` of buttons. Below them:
  * a placement settings panel: snap (Off, 8, 16 = tile, 32, custom), Y-sort parent (auto/selected), flip H, and an auto entity-ID checkbox.
  * a status line.
* Refresh: a "Rescan" button, plus an automatic rescan when `EditorFileSystem.filesystem_changed` fires and the index files changed (compare modified times).

---

## T8.03 — Drag-and-drop and double-click placement

**Depends on:** T8.02
**Files:** `dock/asset_dock.gd`, `placement.gd`

* **Drag:** the item list implements `_get_drag_data(at_position)`, returning `{"type": "files", "files": [scene_path]}`. The Godot 2D editor already instances scenes dropped as file drags. ⚠ VERIFY in 4.7.2 that a `files`-type drag from a plugin dock is accepted by the 2D viewport; if not, fall back to double-click placement only and record it.
* **Post-drop fix-ups:** connect to `get_tree().node_added` while a drag is active (or, more simply, to `EditorInterface.get_selection().selection_changed` after the drop). When a new instance of a library scene appears under the edited scene:
  1. Reparent it to the map's `YSorted/Entities` if Y-sort parent is "auto" and the map has that node. Use `EditorUndoRedoManager` so undo works.
  2. Snap its position to the grid when snapping is on: `pos = (pos / snap).round() * snap`; for objects, the snap aligns the feet origin.
  3. Apply flip_h to its Sprite/Visual if set.
  4. If the scene has `entity_id` (or an RpgPersistent child) and auto-ID is on, assign `<map_id>_<kind>_<nnn>`. `kind` comes from the role, lowercased; `nnn` is the next number from `catalog.id_allocations.entities[map_id][kind]`, computed as 1 + the max existing number for that kind in the map, so it works even if the catalog allocation is stale. Write the allocation back.
* **Double-click:** instances the scene at the center of the current 2D editor viewport (`EditorInterface.get_editor_viewport_2d()` ⚠ VERIFY) and applies the same fix-ups.
* All changes go through `get_undo_redo()` actions named "Place <name>".

---

## T8.04 — Content validator and entity ID tools

**Depends on:** T8.03
**Files:** `dock/validator_panel.gd`, `tools/content_checks.gd` (shared with `builder/validate.gd`, which preloads it)

* The checks run **in the editor**, on demand ("Validate content" button), and also headless in validate.gd:
  * Duplicate or empty entity IDs across all maps (VAL-008, VAL-009)
  * Doors pointing to missing maps → **VAL-016** `"Door {node} in {file} targets missing map {target}."`
  * Doors whose `target_spawn` is not in the target map → **VAL-017** `"Door {node} in {file} targets unknown spawn {spawn} in {target}."`
  * Dialogue conditions that mix `and`/`or` → **VAL-018** (warning) `"Dialogue {file} line {n} mixes and/or; evaluation is left-to-right."`
  * Dialogue events or conditions that reference unknown item ids → **VAL-019** (warning)
  * Debug placeholders in use (VAL-012)
* The results appear in a Tree: severity icon, message and file. Double-clicking opens the scene and selects the node.
* "Fix entity IDs" assigns IDs to all empty ones and renames later duplicates, with undo.
* Add VAL-016…VAL-019 to `03_ERROR_CODES.md` and regenerate the tables.

---

## T8.05 — Catalog overrides and regenerate-in-editor

**Depends on:** T8.02
**Files:** `dock/asset_inspector.gd`, `tools/rebuild.gd`

* Selecting a library item shows an "Asset" panel: role, tags, collision profile, origin (x,y spin boxes), footprint rect and, for characters, an animation FPS table. **Save overrides** writes these into `res://rpggen/asset_catalog.json` `overrides` using `json_util.gd`, recomputes status (port the `recompute_status` rules to GDScript in `tools/catalog_edit.gd`, sharing test fixtures with Python), and marks the asset dirty.
* **Regenerate affected resources:**
  1. Save all open scenes (`EditorInterface.save_all_scenes()`).
  2. Run the builder as a subprocess: `OS.execute(OS.get_executable_path(), ["--headless", "--path", ProjectSettings.globalize_path("res://"), "--script", "res://generated/builder/build.gd"], output, true)`.
  3. Then call `EditorInterface.get_resource_filesystem().scan()`.
  4. Show the build_results issues in the panel.

  ⚠ VERIFY that the editor executable path works headless from within the editor on Windows. The builder only writes generated-owned files whose recipe hash changed. **It does not run promotion or the ledger.** Therefore record "in-editor rebuild" entries: the builder updates `ownership_ledger.json` hashes for the files it wrote. Add a `--update-ledger` builder flag that does this, using the same hashing rules as Python (port `file_hash` to GDScript and share the test vectors).
* **"Open generator"**: if `rpggen_path` is set in Editor Settings (`rpg_tools/rpggen_executable`), this launches the wizard with `--target <project>`. Otherwise, it shows instructions.

---

## T8.06 — Terrains

**Depends on:** T5.04
**Files:** `rpggen/core/terrain/` (`__init__.py`, `tiled_wang.py`, `rpgmaker_a2.py`, `blob.py`), `builder/recipes/tileset_recipe.gd` (terrain application), tests

The Python side produces **terrain assignments** in the catalog. The builder applies them to the TileSet. The data shape is stored in TileSetDef and asset `tile_overrides`:
```json
"tile_overrides": { "3,1": { "terrain": { "set": "ground", "terrain": 0,
                    "peering": { "right_side": 0, "bottom_right_corner": 0, "bottom_side": 0,
                                 "bottom_left_corner": -1, "left_side": -1, "top_left_corner": -1,
                                 "top_side": -1, "top_right_corner": -1 } } } }
```
Peering key names map 1:1 to `TileSet.CELL_NEIGHBOR_*` constants (`right_side` → `CELL_NEIGHBOR_RIGHT_SIDE`, etc.). ⚠ VERIFY the constant names. In the builder: `td.terrain_set = set_index`, `td.terrain = terrain`, then `td.set_terrain_peering_bit(CONST, value)` for each key whose value is ≥ 0.

### 8.06a Tiled Wang sets (from T2.09's recorded wangids)

* The Tiled wangid order is `[top, top_right, right, bottom_right, bottom, bottom_left, left, top_left]`. Values are color indices, where 0 means none and colors start at 1.
* Godot terrain = `color - 1`; none → -1.
* Corner set (mode `corners`): only the corner peering bits are used. Edge set (mode `sides`): only the sides. Mixed: all 8.
* The tile's center `terrain` = the most frequent non-negative value among its peering bits (ties → the lowest index).

### 8.06b RPG Maker A2 autotiles (`rpgmaker_a2.py`)

* A2 sheets hold 8×4 autotile **blocks**. Each block is 2 tiles wide and 3 tiles high (MV/MZ: 96×144 px). Address everything in **quarter-tiles** (half-tile units, 24 px for 48 px tiles): a block is 4 × 6 quarters.
* Quarter source coordinates `(qx, qy)` inside a block, per output quarter position. Each quarter is chosen from its two orthogonal neighbors and the diagonal neighbor:

| Output quarter | Outer corner | Horizontal edge (top/bottom) | Vertical edge (left/right) | Center fill | Inner corner |
|----------------|--------------|------------------------------|----------------------------|-------------|--------------|
| TL | (0,2) | (2,2) | (0,4) | (2,4) | (2,0) |
| TR | (3,2) | (1,2) | (3,4) | (1,4) | (3,0) |
| BL | (0,5) | (2,5) | (0,3) | (2,3) | (2,1) |
| BR | (3,5) | (1,5) | (3,3) | (1,3) | (3,1) |

* Selection for output quarter TL, using neighbors U (up), L (left) and UL (up-left), where each is "same terrain":
  * `U and L and UL` → center
  * `U and L and not UL` → inner corner
  * `U and not L` → vertical edge
  * `not U and L` → horizontal edge
  * `not U and not L` → outer corner
  * Mirror the rule for TR (U, R, UR), BL (D, L, DL) and BR (D, R, DR).
* ⚠ VERIFY this table visually. Implement `tools/debug_a2_sheet.py`, which composes all 47 tiles for one block into a labeled contact sheet PNG. A human must check the result against a real RPG Maker A2 sheet before the gate. If any quarter is wrong, fix the table and record the correction.
* **47 blob tiles:** enumerate all 256 8-neighbor masks. Normalize each by clearing a corner bit unless both adjacent sides are set. This leaves 47 unique masks. Order them by mask value ascending, and compose each tile from 4 quarters.
* Output: a generated composite atlas `generated/terrain_atlases/<asset_slug>_b<i>.png`, 47 tiles in an 8-column grid, written into staging by Python (Pillow). It is a new tiles asset in the catalog (pack `generated`, tags `generated_terrain`) with `tile_overrides` holding terrain peering per tile (mode `corners_and_sides`; side bits from the mask; corner bits only when set after normalization), and a TileSetDef terrain set named after the source sheet and block, e.g. `outside_a2_b3`.
* The source A2 sheet stays in the TileSet as a plain atlas too, so nothing painted earlier breaks.
* A1 (animated water) and A3/A4 (walls and roofs) are **deferred**. They stay plain atlases, and the report notes TILE-006 for them.

### 8.06c Generic blob/Wang sheets (`blob.py`)

* Recognize 47-tile blob sheets laid out in the common "Godot/Tilesetter blob" 12×4 arrangement, and 16-tile corner sets (4×4) by tile count + layout + edge-matching. For each tile in the candidate layout, verify that its expected neighbors' borders match pixel edges (mean absolute difference below a threshold). Accept a layout only if at least 90% of the expected adjacencies match. Otherwise → TILE-006.
* This is best-effort and confidence-scored. Every assignment needs user confirmation in the audit's new "Terrain" tab (GUI): it shows the terrain bitmask over the sheet, with Accept and Reject.

**Tests:** Wang conversion of the `tiled_meta` pack; the A2 composer produces 47 unique tiles with correct peering for a synthetic A2 block whose quarters are color-coded (create it in the test); the blob recognizer on a synthetic 47-tile sheet built by the same composer.

---

## T8.07 — Animated tiles

**Depends on:** T8.06
**Files:** `tileset_recipe.gd`

* For `tile_overrides["x,y"].anim` (from Tiled): if the frames are horizontally consecutive cells in the same row, set `src.set_tile_animation_columns(coords, n)`, `set_tile_animation_frames_count(coords, n)` and per-frame durations (`set_tile_animation_frame_duration`). ⚠ VERIFY the API names.
* Non-consecutive frames are not supported by Godot atlas animation. Skip them with TILE-006-style info using the new code **TILE-008** `"Tile animation at {coords} in {asset} is not a horizontal run and was skipped."`.

---

## T8.08 — Remove demo content

**Depends on:** T8.03
**Files:** `dock/demo_tools.gd`

"Remove demo content" (with a confirmation dialog) does the following:
* Deletes `game/demo/`, if present.
* Removes the demo NPC, chest and enemy instances from `starter_map.tscn` (identified by entity ids in `rpggen/demo_entities.json`, written by recipes) via the undo manager.
* Removes `interior_1.tscn` if the ledger says it is untouched.
* Sets `new_game.tres` items to empty.

The ledger records these as user deletions, so regeneration doesn't recreate them. Make demo content creation conditional on a ledger flag `demo_removed: true` (add it to the ledger schema).

---

## T8.09 — Milestone Gate M8

- [ ] Manual check: drag 10 different assets into the starter map; undo and redo; entity IDs are auto-assigned; regenerate from the wizard; all 10 remain, with their positions intact.
- [ ] Terrain painting works in Godot for the `tiled_meta` pack and for the sample pack (add a small CC0 A2-style block to the sample pack).
- [ ] A human has checked the A2 contact sheet against a real A2 sheet, and the result is noted.
- [ ] Content validator checks run headless in CI and in the editor, with the same results.
