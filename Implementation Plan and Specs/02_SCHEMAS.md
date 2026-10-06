# 02 — Data Schemas

Every JSON file is written with `jsonio.write` (sorted keys, 2-space indent, UTF-8, LF). JSON Schema files live in `rpggen/schema/` (draft 2020-12). Card T1.02 creates the schema files from this document, and every load validates against them.

Conventions used below:
* `posix_rel` — a POSIX relative path string, with no leading `/` and no `..`.
* `res_path` — a `res://` path string.
* `vec2i` — a JSON array of 2 integers, `[x, y]`.
* `rect` — a JSON array of 4 integers, `[x, y, w, h]`, in pixels.
* `?` after a field name — the field is optional; omit it rather than writing `null`.

---

## 1. `generator_config.json` (config_version 1)

Location: `<project>/rpggen/generator_config.json`. Written by Python and read by both sides.

| Field | Type | Default | Rules |
|-------|------|---------|-------|
| `config_version` | int | 1 | Must be 1. |
| `generator_version` | string | package version | |
| `godot_version` | string | `"4.7.2"` | The version validated during preflight. |
| `project_name` | string | — | 1–64 chars; written to `application/config/name`. |
| `archetype` | enum `turn_based`/`arpg` | `turn_based` | |
| `packs` | array of PackRef | — | At least 1 item. |
| `base_tile_size` | int | detected | One of 8, 12, 16, 24, 32, 48, 64. |
| `resolution` | vec2i | `[640, 360]` | Both values between 160 and 3840. |
| `window_size` | vec2i | `[1280, 720]` | |
| `map_layers` | array of string | see below | Must contain `Ground`. Unique entries. |
| `features` | object of bools | all true except `navigation` | Keys: `tilesets, collision, terrain, animations, demo, editor_tools, save, dialogue, combat, navigation, debug_tools`. |
| `validation` | object | `{"smoke_test": true}` | Strict mode is always on (failures block delivery). |
| `seed` | int | 12345 | Used for every RNG in generation and smoke tests. |
| `input` | object | see §1.1 | Action → bindings. |

Default `map_layers`: `["Ground", "GroundDetails", "Walls", "Props", "Overhead"]`.

**PackRef:** `{ "pack_id": str, "source": str (absolute path as the user gave it; informational only), "source_sha256": str, "kind": "zip"|"7z"|"folder" }`.

### 1.1 `input`

```json
{
  "move_up":    { "keys": ["W", "Up"],     "joy_buttons": [11], "joy_axes": [[1, -1.0]] },
  "move_down":  { "keys": ["S", "Down"],   "joy_buttons": [12], "joy_axes": [[1, 1.0]] },
  "move_left":  { "keys": ["A", "Left"],   "joy_buttons": [13], "joy_axes": [[0, -1.0]] },
  "move_right": { "keys": ["D", "Right"],  "joy_buttons": [14], "joy_axes": [[0, 1.0]] },
  "interact":   { "keys": ["E", "Space"],  "joy_buttons": [0] },
  "confirm":    { "keys": ["Enter", "Space"], "joy_buttons": [0] },
  "cancel":     { "keys": ["Escape", "Backspace"], "joy_buttons": [1] },
  "menu":       { "keys": ["Escape", "Tab"], "joy_buttons": [6] }
}
```

The ARPG archetype adds `attack` (J, mouse button 1, joy 2), `secondary_attack` (K, mouse button 2, joy 3), `dodge` (Shift, joy 1) and `quick_item` (Q, joy 9). Mouse buttons use the key `"mouse_buttons": [1]`.

* Key names are Godot key names as accepted by `OS.find_keycode_from_string`. ⚠ VERIFY.
* Joy button indices are Godot `JoyButton` enum values. Axis entries are `[axis_index, direction]`.
* The project-settings recipe sets **physical** keycodes (`InputEventKey.physical_keycode`).

---

## 2. `inventory.json` (cache, per pack)

Location: `%LOCALAPPDATA%/rpggen/cache/inventories/<source_sha256>.json`. It is immutable.

```json
{
  "inventory_version": 1,
  "pack_id": "forest_pack",
  "source_sha256": "…",
  "files": [
    {
      "path": "Tilesets/grass.png",
      "sha256": "…",
      "size": 4210,
      "ext": ".png",
      "kind": "image",
      "image": { "w": 256, "h": 128, "mode": "RGBA", "has_alpha": true, "frames": 1 }
    },
    { "path": "LICENSE.txt", "sha256": "…", "size": 812, "ext": ".txt", "kind": "license" }
  ],
  "skipped": [ { "path": "__MACOSX/._grass.png", "reason": "os_junk" } ]
}
```

`kind` is one of `image`, `audio`, `font`, `license`, `doc`, `metadata`, `other`. It is decided by extension (T2.02) plus filename rules:
* `license` — the stem, lowercased, starts with `license`, `licence`, `credits`, `readme`, `copying` or `attribution`.
* `metadata` — the extension is `.tsx`, `.tmx`, `.tsj`, `.tmj`, `.json`, `.ldtk`, `.aseprite`, `.ase`, `.xml` or `.rpgproject`.

Files are sorted by path (01_CONVENTIONS §5).

---

## 3. `analysis` cache entry

Location: `%LOCALAPPDATA%/rpggen/cache/analysis/<sha256[0:2]>/<sha256>.json`. The key is the image file hash plus `ANALYZER_VERSION`. Increasing `ANALYZER_VERSION` invalidates the cache.

```json
{
  "analyzer_version": 1,
  "sha256": "…",
  "w": 256, "h": 128,
  "has_alpha": true,
  "opaque_bbox": [0, 0, 256, 128],
  "grid_candidates": [
    { "cell": [16, 16], "margin": [0, 0], "separation": [0, 0], "score": 0.97,
      "nonempty_cells": 96, "total_cells": 128 }
  ],
  "regions": [ [0, 64, 80, 64] ],
  "strip": { "axis": "x", "frames": 6, "frame": [32, 32] },
  "baseline_y": 31,
  "dominant_colors": ["#3a7d2c", "#5aa142", "#2f5e22"],
  "nine_slice": null
}
```

---

## 4. `asset_catalog.json` (catalog_version 2)

Location: `<project>/rpggen/asset_catalog.json`.

### 4.1 Top level

| Field | Type | Notes |
|-------|------|-------|
| `catalog_version` | int | 2 |
| `generator_version` | string | |
| `packs` | array of CatalogPack | Sorted by `pack_id`. |
| `assets` | array of Asset | Sorted by `id`. |
| `objects` | array of SheetObject | Regions cut from sheets (§4.5), sorted by `id`. |
| `tilesets` | array of TileSetDef | §4.6, sorted by `name`. |
| `id_allocations` | object | §4.7 |
| `folder_rules` | array of FolderRule | §4.8, kept in insertion order (order matters). |

### 4.2 CatalogPack

```json
{ "pack_id": "forest_pack", "source_sha256": "…", "root": "assets/packs/forest_pack",
  "license_files": ["assets/packs/forest_pack/LICENSE.txt"],
  "adapters_matched": ["tiled", "generic_grid"], "profile_id": null,
  "warnings": ["rpgmaker_rtp_detected"] }
```

### 4.3 Asset

```json
{
  "id": "forest_pack.tilesets.grass",
  "pack_id": "forest_pack",
  "path": "assets/packs/forest_pack/Tilesets/grass.png",
  "sha256": "…",
  "kind": "image",
  "status": "AUTO_DETECTED",
  "detected": { …Facets… },
  "overrides": { …partial Facets… },
  "detected_by": "generic_grid",
  "confidence": 0.94
}
```

* `status` is one of `CONFIRMED`, `AUTO_DETECTED`, `NEEDS_REVIEW`, `MISSING`, `UNUSED` or `CONFLICT`.
* Status rules, applied by `catalog.recompute_status`:
  * Any override present, or `confidence >= 0.999` from a metadata adapter or profile → `CONFIRMED`, unless conflicted.
  * `confidence >= 0.75` → `AUTO_DETECTED`.
  * Otherwise → `NEEDS_REVIEW`.
  * The file is missing on disk → `MISSING`.
  * The role is `NONE` (the user excluded it) → `UNUSED`.
  * A pack update changed the dimensions of an atlas used by a tileset → `CONFLICT`. Only explicit user resolution clears this.
* **Effective facets** = a deep merge of `detected` with `overrides`, where override keys win. An override value of `null` means "remove this detected key". Implement this once as `catalog.effective(asset) -> dict` and as `catalog_reader.gd: effective(asset)`. Test both on the same fixtures; the results must match (T1.07).

### 4.4 Facets (keys inside `detected`/`overrides`)

| Key | Type | Used when | Meaning |
|-----|------|-----------|---------|
| `role` | enum Role | always | Primary role. `NONE` means excluded. |
| `roles_alt` | array of [Role, float] | detection only | Other candidate roles with confidence. |
| `usage` | enum `tiles`/`sprite`/`object`/`ui`/`portrait`/`background`/`audio`/`font` | always | How the asset is consumed. |
| `grid` | Grid | usage=tiles or sprite sheet | |
| `tileset` | string | usage=tiles | Name of the TileSetDef this sheet belongs to. |
| `collision` | CollisionSpec | usage=tiles/object | Default for the whole sheet. |
| `tile_overrides` | object keyed `"x,y"` | usage=tiles | Per-tile `{collision?, terrain?, custom?, skip?}`. |
| `animations` | object name→AnimSpec | usage=sprite | |
| `frame` | vec2i | usage=sprite | Frame size in px. |
| `origin` | vec2i | usage=sprite/object | Pixel inside a frame/object that becomes the node origin (the feet). |
| `directions` | int 1/4/8 | usage=sprite | |
| `character_index` | int | RPG Maker multi-character sheets | Which 3×4 block (0–7). |
| `ysort` | bool | object/sprite | Default true. |
| `audio` | `{ "type": "music"/"sfx", "loop": bool }` | usage=audio | |
| `nine_slice` | `[left, top, right, bottom]` | usage=ui | Margins in px. |
| `import` | `{ "filter": "nearest"/"linear", "mipmaps": bool }` | images | Defaults: nearest, false. |
| `tags` | array of string | any | Free tags such as `chest` or `door`, used for template selection (T4.03). |

**Role** enum: `GROUND, WALL, CLIFF, WATER, ROAD, AUTOTILE, DECORATION, BUILDING, INTERIOR, PLAYER, NPC, ENEMY, BOSS, WEAPON, ITEM, EFFECT, PROJECTILE, UI, PORTRAIT, BACKGROUND, AUDIO_MUSIC, AUDIO_SFX, FONT, NONE`.

**Grid:** `{ "cell": vec2i, "margin": vec2i, "separation": vec2i }`. Columns are `floor((w - 2*margin.x + separation.x) / (cell.x + separation.x))`; rows are computed the same way with y. The margin applies to the left and top. A right/bottom remainder is allowed and ignored.

**CollisionSpec:** `{ "profile": Profile, "polygon": [[x,y],…]? }`.
* Profile is one of `NONE, FULL, BOTTOM_HALF, BOTTOM_EDGE, TOP_EDGE, LEFT_EDGE, RIGHT_EDGE, ALPHA_POLYGON, CUSTOM`.
* `polygon` is required for `CUSTOM`. Its coordinates are pixels relative to the **top-left** of the cell or object. The builder converts them to Godot's tile-centered space (T1.07).

**AnimSpec:**
```json
{ "frames": [[col, row], …], "fps": 8.0, "loop": true,
  "durations": [1.0, 1.0, …]?, "flip_h": false, "active_frames": [2, 3]? ,
  "source": "assets/packs/…/hero_walk.png"? }
```
* `frames` are grid cells in the asset's own sheet, or in `source` when the animation comes from another file (per-file strips).
* `durations` are relative multipliers. Godot `SpriteFrames` frame duration is relative too.
* `flip_h: true` means "use the referenced frames mirrored". The runtime sets `AnimatedSprite2D.flip_h` while playing this animation; the recipe records it in SpriteFrames metadata (T1.07).
* `active_frames` are the frame indices where an attack hitbox is live (ARPG).

Standard animation names: `idle_down, idle_up, idle_left, idle_right, walk_*, attack_*, hurt_*, death`. No other names are generated automatically. Users may add more through overrides.

### 4.5 SheetObject (object cutter output)

```json
{ "id": "forest_pack.tilesets.town#house_red", "sheet": "forest_pack.tilesets.town",
  "name": "House (red)", "role": "BUILDING", "region": [0, 64, 80, 64],
  "origin": [40, 63], "footprint": [0, 40, 80, 24],
  "collision": { "profile": "CUSTOM", "polygon": [[0,40],[80,40],[80,64],[0,64]] },
  "tags": ["door"], "door": [36, 63]?, "status": "CONFIRMED", "source": "user"|"auto"|"tiled" }
```

* `footprint` is the rectangle (in object pixels) that blocks movement. The default is the bottom 30% of the region at full width.
* `door` is the point where the player exits after leaving an interior and where the entrance trigger sits.

### 4.6 TileSetDef

```json
{ "name": "overworld", "tile_size": [16, 16],
  "sources": [ { "asset": "forest_pack.tilesets.grass", "source_id": 0 } ],
  "terrain_sets": [ { "name": "ground", "mode": "corners_and_sides",
                      "terrains": [ { "name": "grass", "color": "#4caf50" } ] } ],
  "physics_layers": [ { "name": "world", "layer_bits": 1, "mask_bits": 0 } ],
  "custom_data": [ { "name": "asset_id", "type": "string" },
                   { "name": "footstep", "type": "string" },
                   { "name": "move_cost", "type": "float" } ],
  "navigation": false,
  "patterns_from_objects": true }
```

* The `mode` enum is `corners_and_sides`, `corners` or `sides`. These map to `TileSet.TERRAIN_MODE_MATCH_CORNERS_AND_SIDES`, `TileSet.TERRAIN_MODE_MATCH_CORNERS` and `TileSet.TERRAIN_MODE_MATCH_SIDES`. ⚠ VERIFY the enum names.
* TileSet assignment rules (T2.14): one TileSetDef per distinct tile size. A sheet whose role is INTERIOR goes into a separate `interior` set of the same size. Names are `overworld`, `overworld_32`, `interior`, `interior_32` and so on.

### 4.7 id_allocations

```json
{ "tilesets": { "overworld": { "next_source_id": 3, "retired": [1] } },
  "entities": { "starter_map": { "npc": 2, "enemy": 1, "chest": 1 } } }
```

* `source_id` values are **never reused**. `allocate_source_id(tileset)` returns `next_source_id` and increments it.
* Removing a source moves its id into `retired`.
* Python is the only writer of `tilesets`. The editor dock (M8) is the only writer of `entities`.

### 4.8 FolderRule

```json
{ "pack_id": "forest_pack", "glob": "Characters/Enemies/**", "set": { "role": "ENEMY" } }
```

Rules are applied in order after detection and before overrides. They write into a separate `rule` layer, so effective = detected ← rule ← overrides. A matching rule's facet keys replace detected keys. Matching uses `PurePosixPath.full_match` semantics (Python 3.13), or an equivalent helper `paths.glob_match` implemented for 3.12. ⚠ VERIFY your Python version and implement the helper with tests.

---

## 5. `ownership_ledger.json` (ledger_version 1)

```json
{
  "ledger_version": 1,
  "generator_version": "0.1.0",
  "files": {
    "generated/scenes/actors/player.tscn": { "sha256": "…", "written_by": "player_recipe", "owner": "generated" },
    "game/maps/starter_map.tscn": { "sha256": "…", "written_by": "starter_map_recipe", "owner": "user_seed" }
  },
  "deleted_by_user": ["generated/scenes/objects/old_sign.tscn"]
}
```

* `owner` is either `generated` (may be rewritten) or `user_seed` (written once, then never touched).
* Keys are posix_rel paths, sorted.
* Hashes cover the file bytes **after** CRLF→LF normalization for text files (`.gd`, `.tscn`, `.tres`, `.json`, `.cfg`, `.godot`, `.md`, `.import`, `.uid`). Binary files are hashed raw. This avoids false conflicts when git rewrites line endings.

---

## 6. `build_results.json`, `validation_results.json`, `smoke_results.json`

All three files share this shape:

```json
{
  "results_version": 1,
  "phase": "build" | "validate" | "smoke",
  "ok": true,
  "started_ms": 0, "elapsed_ms": 18234,
  "issues": [ { "code": "TILE-003", "severity": "warning", "message": "…", "file": "…" } ],
  "items": [ … phase-specific … ]
}
```

`started_ms` is always 0 to keep the output deterministic. Only `elapsed_ms` varies, and diff checks ignore that field.

* Build `items`: `{ "recipe": "tileset_recipe", "output": "generated/tilesets/overworld.tres", "action": "written"|"skipped"|"merged"|"failed" }`.
* Validate `items`: `{ "check": "resource_load", "target": "…", "ok": bool }`.
* Smoke `items`: `{ "step": 3, "name": "npc_dialogue", "ok": bool, "ms": 412, "detail": "…" }`.

`ok` is false if any issue has `severity == "error"`.

---

## 7. Pack profile (`*.rpgprofile.json`, profile_version 1)

```json
{
  "profile_version": 1,
  "profile_id": "vendor_forest_v2",
  "title": "Forest Pack v2 by Vendor",
  "fingerprint": { "required_files": { "Tilesets/grass.png": "<sha256>", "Characters/hero.png": "<sha256>" },
                   "min_match": 0.8 },
  "assets": { "Tilesets/grass.png": { …partial Facets… } },
  "objects": [ …SheetObject without "id", with "sheet_path" instead of "sheet"… ],
  "folder_rules": [ … ],
  "tilesets": [ …TileSetDef without source_id values… ],
  "author": "github-username", "license": "CC0-1.0"
}
```

* A profile matches when the fraction of `required_files` present with an identical hash is at least `min_match`.
* `required_files` holds up to 20 files, chosen as the largest images.
* Profiles never contain image data.

---

## 8. `build_state.json`

```json
{ "build_state_version": 1, "outputs": { "generated/tilesets/overworld.tres": "<input_hash>" } }
```

---

## 9. Save game (runtime, `user://saves/slot_<n>.json`, save_version 1)

```json
{
  "save_version": 1,
  "checksum": "<sha256 hex of the canonical JSON of everything except 'checksum'>",
  "header": { "slot": 1, "map": "starter_map", "playtime_s": 512, "level": 3, "saved_at_unix": 1760000000 },
  "player": { "actor_id": "hero", "stats": { "level": 3, "experience": 40, "hp": 18, "max_hp": 24 } },
  "party": [],
  "inventory": [ { "item_id": "potion", "qty": 3 } ],
  "gold": 120,
  "world": { "map": "starter_map", "spawn_id": "", "position": [128.0, 96.0], "facing": "down" },
  "flags": { "starter_map_chest_001": { "opened": true } },
  "quests": {},
  "settings_snapshot_version": 1
}
```

* Canonical JSON for the checksum: `JSON.stringify(data_without_checksum, "", true)`, where the third argument sorts keys. ⚠ VERIFY the signature of `JSON.stringify` in 4.7 (`data, indent, sort_keys, full_precision`).
* Vectors are always stored as `[x, y]` arrays.

---

## 10. Fields added by later task cards

Several task cards extend these schemas. Each card that adds a field must update both this document and the JSON Schema file in the same commit. The full list:

| Field | Where | Added by |
|-------|-------|----------|
| `rects`, `offsets` | AnimSpec | T2.10 |
| `region` | Facets (portraits cut from face sheets) | T2.11 |
| `renamed_from` | Asset | T5.05 |
| `remove_source` | Facets (override only) | T5.04 |
| `starter` | generator_config | T3.11 |
| `demo_removed` | ownership_ledger | T8.08 |
| `anim`, `terrain.peering` | `tile_overrides` entries | T2.09, T8.06 |
