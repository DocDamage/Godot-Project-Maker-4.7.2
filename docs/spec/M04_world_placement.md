# M4 — World Foundation and Placement Scenes

**Goal:** the starter map has all configured layers. Buildings, trees and props exist as reusable scenes with correct origins, footprints and Y-sorting. A building door leads to an interior map and back. The SceneRouter's core exists (M6 extends it).

---

## T4.01 — Shared recipe helpers

**Depends on:** M3 gate
**Files:** `godot_templates/builder/lib/scene_util.gd`, `godot_templates/builder/lib/texture_util.gd`, `godot_templates/tests/unit/test_scene_util.gd`

* `scene_util.gd`:
  * `save_scene(root: Node, path: String) -> int` (the pattern from `01_CONVENTIONS.md` §6.2, plus UID preservation: before saving, `var old_uid := ResourceLoader.get_resource_uid(path)` if the file exists; after saving, if `old_uid != ResourceUID.INVALID_ID`, call `ResourceSaver.set_uid(path, old_uid)` ⚠ VERIFY).
  * `instance(path: String) -> Node`.
  * `add(parent: Node, child: Node, root: Node, name: String) -> Node` (sets the name and owner, returns the child).
  * `attach_script(node, path)`.
* `texture_util.gd`:
  * `region_texture(atlas_path: String, region: Rect2i) -> AtlasTexture`, cached per `(path, region)` within one build. **Embed the AtlasTexture as a sub-resource of the scene. Do not save separate `.tres` files per region.**
  * `asset_texture(asset: Dictionary) -> Texture2D`.
* Update every existing recipe (M1) to use `scene_util.save_scene`.

**Tests:** saving a scene with nested children and one instanced child, then reloading it, keeps the structure; the instanced child's internals are not duplicated into the parent scene; the UID is preserved across two saves of the same path.

---

## T4.02 — Runtime world-object scripts

**Depends on:** T4.01
**Files:** under `godot_templates/addons/rpg_runtime/world/`: `world_object.gd`, `door.gd`, `spawn_point.gd`, `map_root.gd`, `scene_router.gd` (core part), plus tests.

```gdscript
# world_object.gd
class_name RpgWorldObject
extends Node2D
@export var asset_id: String = ""
@export var entity_id: String = ""      # empty for non-persistent props
@export var blocks_movement: bool = true
```

```gdscript
# spawn_point.gd
class_name RpgSpawnPoint
extends Marker2D
@export var spawn_id: StringName = &"default"
@export var facing: String = "down"
func _ready() -> void: add_to_group("spawn_points")
```

```gdscript
# door.gd — an Area2D trigger
class_name RpgDoor
extends Area2D
@export_file("*.tscn") var target_map: String = ""
@export var target_spawn: StringName = &"default"
@export var require_interact: bool = false   # false: walk-in; true: press interact
signal used
# On body_entered (player group) or interact: SceneRouter.go_to(target_map, target_spawn)
```

```gdscript
# map_root.gd — attached to every map's root
class_name RpgMapRoot
extends Node2D
@export var map_id: StringName = &""
@export var music_asset_id: String = ""
func get_spawn(spawn_id: StringName) -> RpgSpawnPoint  # searches group within this map
func get_player() -> Node2D                              # first node in group "player" in this map
func used_rect_px() -> Rect2                             # union of all TileMapLayer used rects × tile size
```

**SceneRouter (core, autoload `SceneRouter`)**, in `scene_router.gd`:
```gdscript
extends Node
signal map_changed(map_id: StringName)
var current_map: RpgMapRoot
func go_to(map_path: String, spawn_id: StringName = &"default") -> void
```

Behavior of `go_to`:
1. Set a `_busy` flag; ignore calls while busy.
2. Fade out over 0.2 s, using a CanvasLayer (layer 100) with a ColorRect (black) whose alpha is tweened. Create both in `_ready`.
3. `get_tree().change_scene_to_file(map_path)`, then `await get_tree().scene_changed` ⚠ VERIFY that the signal exists in 4.7; fallback: await two process frames and then read `current_scene`.
4. Find the spawn. Spawn priority: the spawn with this id; else `"default"`; else the first spawn; else (0,0) with `push_error("[RPG-WORLD] no spawn")`. Move the player there and set its facing.
5. Fade in, clear `_busy`, emit `map_changed`.

* The camera: each player has its own Camera2D. After placing the player, set the camera limits from `current_map.used_rect_px()` (`limit_left`, etc.) and call `reset_smoothing()`.
* Register the autoload `SceneRouter` in `project_settings_recipe` (add `autoload/SceneRouter = "*res://addons/rpg_runtime/world/scene_router.gd"`). ⚠ VERIFY the autoload value format with the `*` prefix.
* Change the boot scene to call `SceneRouter.go_to(first_scene)`.

**Tests:** spawn resolution order (unit test with a fake map); the busy flag ignores a second call.

---

## T4.03 — Object scene recipe

**Depends on:** T4.02
**Files:** `godot_templates/builder/recipes/object_scenes_recipe.gd`, `godot_templates/tests/unit/test_object_recipe.gd`

**Inputs:**
* Every catalog **SheetObject** with status ≠ UNUSED and role ≠ NONE.
* Every image asset with usage `sprite`, a single frame (no animations) and role in {DECORATION, BUILDING, INTERIOR, ITEM}.

**Outputs:** `res://generated/scenes/objects/<slug(id)>.tscn`. Replace `#` and `.` in ids with `__` for file names. The mapping `object_id → scene path` is written to `res://rpggen/object_index.json` (`{id: path}`, sorted), which the dock uses in M8.

**Template selection** (`_template_for(obj) -> String`), applied in order:
1. Tag `door` or role BUILDING → `building`
2. Tag `chest` → `chest` (M6 adds the chest script; M4 builds it as `interactable` with tag kept)
3. Tag `sign` → `sign` (same as above)
4. The collision profile is not NONE, or the role is DECORATION with a footprint area of at least 50% of a tile → `obstacle`
5. Otherwise → `prop`

**Scene structure per template:**

```text
prop:
<Name> (Node2D, script world_object.gd, asset_id, blocks_movement=false)
└── Sprite (Sprite2D, texture = region texture, centered = false, offset = -origin)

obstacle:
<Name> (StaticBody2D, script world_object.gd, collision_layer = world(1), collision_mask = 0)
├── Sprite (Sprite2D as above)
└── Footprint (CollisionPolygon2D, polygon = footprint polygon − origin)

building:
obstacle +
├── Entrance (Area2D, script door.gd, require_interact=false, collision_layer = triggers(6),
│             collision_mask = player(2))
│   └── Shape (CollisionShape2D, RectangleShape2D 0.75 tile × 0.5 tile)
│   positioned at (door point − origin) + (0, +4)   # just in front of the door
└── ExitSpawn (Marker2D + spawn_point.gd, spawn_id = "<object slug>_exit", facing="down")
    positioned at (door point − origin) + (0, +tile_size)
```

**Footprint polygon:**
* CUSTOM polygon if present.
* Otherwise the `footprint` rect.
* Otherwise a default: the bottom 30% of the region at full width, inset by 1 px on each side.

All coordinates are in object pixels, and they are converted with `p - origin` so the node origin is the feet/base.

**Origin default:** `(region.w / 2, region.h - 1)`.

**Building without a door point:** the door defaults to the bottom-center and gets the tag `door_assumed`; the report lists it.

**Tests:** for a known object (from `objects_in_sheet`), the built scene's Sprite offset, footprint polygon points and entrance position match the hand-computed values.

---

## T4.04 — Interior map recipe

**Depends on:** T4.03
**Files:** `godot_templates/builder/recipes/interior_recipe.gd`

* For the starter building (config `starter.building`), create **one** interior map, `res://game/maps/interior_1.tscn`. It is user_seed: created only if it doesn't exist.
* Size: 12×9 tiles. Floor: the first tile of the first GROUND sheet in the `interior` tileset if one exists, otherwise the overworld ground. Walls: the WALL tile if one exists, otherwise the border is left empty, with a StaticBody2D rectangle border (4 thin rectangles) so the room is enclosed either way.
* Root: `Interior1` (Node2D + `map_root.gd`, map_id `interior_1`). It has the same layer set as the overworld (T4.05).
* Contents:
  * `SpawnPoints/default` at the bottom-center, one tile above the exit.
  * `Triggers/Exit` (`door.gd`): `target_map = res://game/maps/starter_map.tscn`, `target_spawn = "<building slug>_exit"`, a 1×1 tile area at the bottom-center.
* In the starter map, the placed building instance's `Entrance` gets `target_map = interior_1.tscn` and `target_spawn = "default"`. These are **overrides on the instance**, set by `inst.get_node("Entrance").set("target_map", …)`. ⚠ VERIFY that property changes on nodes inside an instanced child are saved as instance overrides (they should be). Use a probe.

---

## T4.05 — Full starter map composition

**Depends on:** T4.04
**Files:** `godot_templates/builder/recipes/starter_map_recipe.gd` (rewrite), `godot_templates/builder/lib/map_util.gd`

**Map structure** (layers from `config.map_layers`; the defaults are shown):

```text
StarterMap (Node2D, map_root.gd, map_id="starter_map")
├── Ground          (TileMapLayer, tile_set = overworld)
├── GroundDetails   (TileMapLayer)
├── Walls           (TileMapLayer, collision enabled)
├── YSorted         (Node2D, y_sort_enabled = true)
│   ├── Props       (TileMapLayer, y_sort_enabled = true)
│   └── Entities    (Node2D, y_sort_enabled = true)   ← player, NPCs, enemies, objects
├── Overhead        (TileMapLayer, z_index = 10)
├── Triggers        (Node2D)
└── SpawnPoints     (Node2D)
    └── default     (RpgSpawnPoint)
```

* Layer names from config that are not in the default set are added as TileMapLayers between `Walls` and `YSorted`, in config order. `Props` is always placed under YSorted when present.
* TileMapLayer `collision_enabled` is true for Walls and Props only. ⚠ VERIFY the property name.

**Layout** (deterministic, using `config.seed` and Godot's `RandomNumberGenerator`, seeded):
* Size 40×24 tiles.
* Ground: fill with the starter ground tile. Then scatter up to 3 other GROUND-role tiles from the same sheet in 2×2 to 4×4 patches: 6 patches, positions from the RNG, kept away from the house area.
* Walls: a 1-tile border using the WALL tile (or invisible collision rectangles if there is no WALL tile).
* Building: place the starter building instance under `Entities`, at tile (8, 6) measured from the top-left of its region. Its Entrance links to the interior (T4.04).
* Decorations: up to 8 `obstacle`/`prop` instances chosen from DECORATION objects (sorted by id, cycled), placed on a fixed list of positions: (20,4) (24,5) (30,8) (33,14) (6,17) (14,19) (26,18) (35,20).
* Spawn `default` at (12, 12). The Player instance is placed at the spawn.
* Path to the house: if a ROAD tile exists, paint a path from the spawn to the house door on GroundDetails.
* **Reserved spots for later milestones** (empty Marker2D nodes under `SpawnPoints`, named `npc_spot`, `enemy_spot` and `chest_spot`) at (16,12), (28,12) and (18,8). M6 and M7 recipes place content there.

* `map_util.gd` helpers: `fill(layer, rect, source_id, coords)`, `border(layer, rect, …)`, `find_tile(tileset, role) -> {source_id, coords}`, which uses the catalog to find the first non-empty tile of an asset with that role in that tileset, `place(scene_path, parent, root, tile_pos, tile_size)`.

**Tests:** after build, the starter map has every config layer; the building instance's Entrance has `target_map` set; a second build with the map already existing doesn't modify it (user_seed).

---

## T4.06 — TileSet patterns from objects

**Depends on:** T4.03
**Files:** `godot_templates/builder/recipes/tileset_recipe.gd` (extension)

* For each SheetObject whose sheet belongs to a TileSetDef with `patterns_from_objects: true`, build a `TileMapPattern`: for each cell inside the object's region (in cell units of the sheet), `pattern.set_cell(cell - region_origin_cell, source_id, cell, 0)`, then `ts.add_pattern(pattern)`. ⚠ VERIFY the API.
* Pattern order follows object id order. On rebuild, **remove all existing patterns first** (`while ts.get_patterns_count() > 0: ts.remove_pattern(0)`), then re-add. Patterns don't affect painted maps, so a rebuild is safe.

---

## T4.07 — Y-sort correctness and smoke steps

**Depends on:** T4.05
**Files:** `godot_templates/builder/smoke/smoke_steps_m4.gd`, `godot_templates/builder/validate.gd` (add a check), `godot_templates/tests/unit/test_ysort.gd`

* Headless mode renders nothing, so Y-sort is verified **logically**:
  * Validator check `ysort_origins`: for every scene under `generated/scenes/objects/` and `generated/scenes/actors/`, the visual's bottom edge must be within ±2 px of node y = 0. Compute it from the Sprite2D or AnimatedSprite2D offset and region size, plus `centered` and the first frame size. Otherwise → VAL-011-style warning, using the new code **VAL-014** `"Visual of {file} is not aligned to its origin (bottom at {y})."`. Add the code to the table.
  * The parent of every placed entity in maps must be y_sort_enabled. Otherwise → VAL-015 warning `"Entity {node} in {file} is not under a Y-sorted parent."`. Add the code.
* Smoke steps M4 (they extend the M1 steps; the runner takes a list of step scripts via `--rpg-smoke-steps=a.gd,b.gd`):
  1. `enter_building`: teleport the player 1 tile below the building entrance, press up until `SceneRouter.map_changed` fires with `interior_1` (timeout 5 s).
  2. `exit_building`: walk to the exit and expect `starter_map`, with the player within 1 tile of `<building>_exit`.
  3. `decor_blocks`: walk into the first obstacle's footprint and expect to be blocked.

**Gate checks are in T4.08.**

---

## T4.08 — Milestone Gate M4

- [ ] The sample pack and all synthetic packs with objects generate and pass the M1 and M4 smoke steps.
- [ ] Opening the generated project (manual check): the map shows all layers in the Scene dock; painting on each layer works; the building is enterable in play mode; the player walks behind tree tops and in front of tree trunks correctly.
- [ ] Regenerating without changes leaves `game/maps/*.tscn` byte-identical (an early check before M5 formalizes it).
- [ ] VAL-014 and VAL-015 report no warnings on the sample pack.
