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
| `archetype` | enum `turn_based`/`arpg`/`metroidvania` | `turn_based` | `metroidvania` since release 1.2 (M14). |
| `packs` | array of PackRef | — | At least 1 item. |
| `base_tile_size` | int | detected | 8 to 256. The wizard and `rpggen generate --pack` set it from the packs (`catalog.dominant_tile_size`); 16 when they have no tile set. |
| `resolution` | vec2i | `[640, 360]` | Both values between 160 and 3840. |
| `window_size` | vec2i | `[1280, 720]` | |
| `map_layers` | array of string | see below | Must contain `Ground`. Unique entries. |
| `features` | object of bools | all true except `navigation` | Keys: `tilesets, collision, terrain, animations, demo, editor_tools, save, dialogue, combat, navigation, debug_tools`. |
| `validation` | object | `{"smoke_test": true}` | Strict mode is always on (failures block delivery). |
| `seed` | int | 12345 | Used for every RNG in generation and smoke tests. |
| `input` | object | see §1.1 | Action → bindings. |
| `sounds` | object | `{}` | Optional (T11.20). Sound slot → audio asset id. Slots: `music_map`, `music_battle`, `music_title`, `sfx_ui_move`, `sfx_ui_confirm`, `sfx_ui_cancel`, `sfx_hit`, `sfx_attack`, `sfx_pickup`, `sfx_chest`, `sfx_door`, `sfx_step`, `sfx_save`, `sfx_levelup`. A slot that is absent is silent. Omitted from the JSON when empty. Beyond the fixed list any key matching `^(music|sfx)_[a-z][a-z0-9_]{1,30}$` is a **custom slot** (T13.16): `sfx_step_<surface>` is the footstep on ground tagged `surface:<surface>`, any other is played by name. A key that does not match is `CAT-006`. |
| `starter_map` | object | defaults | Optional (T11.25). `size` [w, h] tiles (24..96 each), `buildings` 0..4, `npcs` 0..6, `enemies` 0..8, `chests` 0..4, `decorations` 0..40, `ground_patches` 0..20, `ground` asset id or "". Omitted from the JSON when equal to the defaults. `areas` (T13.20, optional): a list of 1 to 12 `{ "name", "biome", "size"?, "enemies"?, "chests"?, "join"?, "reroll"? }` rows that make a **world of connected maps** (§12): `biome` is `village`, `field`, `forest`, `cave` or `shore`; `size` [w, h] is 16..96 tiles (default [32, 20]); `enemies` and `chests` are 0..12 (default 2 and 1); `join` names the area a row added to an existing world hangs on; `reroll` (0 or more) gives another arrangement of that area only. The first `village` row (else the first row) is the starter map, whose size and counts are the options above. Without `areas` the project gets the starter map and the field of 1.0. |
| `repair_world` | bool | `true` | Optional (T13.24). After a build, mend the doors that lead nowhere and the unreachable maps among the maps rpggen made and nobody changed (`rpggen/world_repair.json` lists what was done). Omitted from the JSON when true. |
| `imported_maps` | object | `{}` | Optional (T12.49). `include`: ids of the catalog's `maps` to build into `game/maps/imported/<pack>/`; `starter`: the id of the map that becomes `game/maps/starter_map.tscn` (the layout planner is then skipped, and the map has none of the demo's villager, chest or enemy). The starter is built even when it is not in `include`. Omitted when empty. |
| `git` | object | `{}` | Optional (T12.12). `pack_art`: `"commit"` (default), `"lfs"` (the pack art goes through Git LFS; falls back to `commit` with ENV-013 when git-lfs is missing) or `"ignore"` (`assets/packs/` is added to the generated `.gitignore`). Omitted when it holds the default. |
| `export_targets` | array of strings | `["windows"]` | Optional (T12.52). The platforms that get a preset in `export_presets.cfg` and a test export: `windows`, `web`, `linux`, `macos` (at least one, no repeats; written in that order). Omitted when it is `["windows"]`. |
| `starter` | object | `{}` | Optional (T3.11). Starter selections of the demo recipes: `player`, `npc`, `enemy`, `ground`, `building`, `chest`, `portrait` → an asset id or an object id. Omitted when empty. |

Default `map_layers`: `["Ground", "GroundDetails", "Walls", "Props", "Overhead"]`.

**A metroidvania (release 1.2, M14)** uses the same file with these differences:

* `starter_map` holds the *starter world* instead (T14.06): `rooms` 5..12 (default 6), `room_size`
  `[w, h]` tiles (32..80 by 23..45, default `[40, 23]`), `abilities` (a list from `double_jump`,
  `dash`, `wall_jump`, `high_jump`, `break_blocks`, stored in that order, default the first two),
  `enemies` 0..4 per room (default 2), `pickups` 0..12 in the world (default 4) and `added_rooms`
  (at most 12 rows `{ "name", "join" }`, each a room built beside the room `join` names). `rooms`
  must be at least `len(abilities) + 3`. As for a starter map, only the keys that differ from the
  defaults are written.
* `starter` may have `boss` (the guardian's sprite, role `BOSS`); `building` is not used.
* `sounds` has four more fixed slots: `sfx_jump`, `sfx_land`, `sfx_dash`, `sfx_ability`. In the
  other archetypes a slot of such a name is a custom slot.
* `input` has `jump`, `dash`, `attack` and `down`, and `interact` is E / Up (Space jumps).
* `map_layers` is not used (a room has the layers `Background`, `Ground`, `Platforms`, `Hazards`,
  `Decoration`, `Foreground`), `imported_maps` is not used, and `features.navigation` is off.

**PackRef:** `{ "pack_id": str, "source": str (absolute path as the user gave it; informational only), "source_sha256": str, "kind": "zip"|"7z"|"rar"|"folder" }`.

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
  "skipped": [ { "path": "__MACOSX/._grass.png", "reason": "os_junk" },
               { "path": "Get more packs.html", "reason": "not_an_asset" } ]
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
| `maps` | array of Map | Optional (T12.49), §4.9, sorted by `id`. Omitted when the packs have no Tiled or LDtk maps. |
| `variants` | array of Variant | Optional (T13.18), in the order they were made. A Variant is `{ "id", "source", "name", "op", "params", "stats"? }`: `id` is the id of the variant's effective asset (`<pack>.variants.<slug>`), `source` the asset it recolours, `op` is `hue` (`params`: `shift` 0–359 degrees, `saturation` and `value` multipliers 0–4) or `palette` (`params.map`: a list of `[[r, g, b], [r, g, b]]` pairs, from → to), and `stats` (enemies and bosses only) holds multipliers 0.1–20 for `hp`, `attack`, `xp`, `gold` (1 is not stored). The effective asset is in `assets` like any other: path `generated/variants/<id with _ for .>.png`, the source's effective facets, and `derived_from`. A variant whose source is gone keeps its definition and has no asset (`ASSET-029`). Omitted when empty. |

### 4.2 CatalogPack

```json
{ "pack_id": "forest_pack", "source_sha256": "…", "root": "assets/packs/forest_pack",
  "license_files": ["assets/packs/forest_pack/LICENSE.txt"],
  "adapters_matched": ["tiled", "generic_grid"], "profile_id": null,
  "warnings": ["rpgmaker_rtp_detected"],
  "license": { "license_id": "CC-BY-4.0", "author": "", "url": "https://example.itch.io/forest",
               "attribution_required": true },
  "license_overrides": { "author": "Jane Doe" } }
```

`license` (T12.51) is what `rpggen/core/licenses.py` read from the licence, credits and readme
files: `license_id` is `CC0-1.0`, a Creative Commons BY id (`CC-BY-4.0`, `CC-BY-SA-3.0`,
`CC-BY-NC-4.0`, …), `OGA-BY-3.0`, `MIT`, `commercial` (a vendor's licence that allows commercial
use), `rpgmaker` (the RPG Maker terms) or `""` (unknown). `license_overrides` (optional, omitted
when empty) holds the Audit page's corrections of the same keys and survives a new analysis; the
effective licence is `license` with the overrides on top, and a `license_id` chosen there without
`attribution_required` brings that licence's own rule. A catalog without `license` reads an
unknown licence.

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
* An asset whose file the vendor renamed in a pack update carries `renamed_from`: the pack-relative path of the earlier release (T5.05). Its id, path and tile set source id follow the rename; overrides carry over.
* An override may set `remove_source: true` (T5.04): the user confirmed that the tile set source of this asset, which stays after the file left its pack (REGEN-003), can be removed. It is the only way a tile set source is ever removed.
* Assets may also carry an optional `rule` object (T2.14): the facets written by folder rules (§4.8), so effective = `detected` <- `rule` <- `overrides`.
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
| `audio` | `{ "type": "music"/"sfx", "loop": bool, "duration_s"?: number, "loop_start_ms"?: int, "loop_end_ms"?: int }` | usage=audio | `duration_s` is read from the file (WAV, OGG, MP3, FLAC) when it can be; optional. `loop_start_ms` and `loop_end_ms` (T13.17, optional, set on the Audit page) are where a looping track jumps back to and from; without them it loops as a whole. An override may set a part of `audio` (it merges) and `null` takes a loop point away. |
| `nine_slice` | `[left, top, right, bottom]` | usage=ui | Margins in px. |
| `import` | `{ "filter": "nearest"/"linear", "mipmaps": bool }` | images | Defaults: nearest, false. |
| `tags` | array of string | any | Free tags such as `chest` or `door`, used for template selection (T4.03). Side-view tags detected from folder and file words (T14.02), read by the `metroidvania` archetype only: `platform`, `one_way`, `ladder`, `hazard`, `save_point`, `ability`, and `parallax:<n>` on a background (1 is the farthest layer). |
| `derived_from` | string | a recolour variant | The id of the asset a variant was recoloured from (T13.18); detected facet only. |
| `size` | vec2i | every image asset | Pixel size of the image file (T2.14); a change on a tile sheet used by a tileset raises CONFLICT. |
| `region` | `[x, y, w, h]` | usage=portrait | Pixel rect of one face inside a face sheet (T2.11). |
| `terrain_proposal` | object | usage=tiles | Blob/corner terrain recognized on a sheet (T8.06c): `{layout, confidence, mode, terrain_set, tile_overrides}`. Not applied until the user accepts it in the audit's Terrain tab, which moves `tile_overrides` into the overrides and sets the override `terrain_proposal` to null. |

**Role** enum: `GROUND, WALL, CLIFF, WATER, ROAD, AUTOTILE, DECORATION, BUILDING, INTERIOR, PLAYER, NPC, ENEMY, BOSS, WEAPON, ITEM, EFFECT, PROJECTILE, UI, PORTRAIT, BACKGROUND, AUDIO_MUSIC, AUDIO_SFX, FONT, NONE`.

**Grid:** `{ "cell": vec2i, "margin": vec2i, "separation": vec2i }`. Columns are `floor((w - 2*margin.x + separation.x) / (cell.x + separation.x))`; rows are computed the same way with y. The margin applies to the left and top. A right/bottom remainder is allowed and ignored.

**CollisionSpec:** `{ "profile": Profile, "polygon": [[x,y],…]? }`.
* Profile is one of `NONE, FULL, BOTTOM_HALF, BOTTOM_EDGE, TOP_EDGE, LEFT_EDGE, RIGHT_EDGE, ALPHA_POLYGON, CUSTOM, ONE_WAY, LADDER`.
* `ONE_WAY` and `LADDER` (T14.02, release 1.2) are side-view values for `tiles` assets: a platform the player jumps through from below and drops through with down + jump, and a tile to climb that blocks nothing. Only the `metroidvania` archetype reads them (its TileSet gets a one-way physics layer and the custom data `ladder`); `turn_based` and `arpg` treat both as `NONE`, so a top-down project's TileSet is the same with either.
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
* `rects` (optional, T2.10) are explicit pixel rects `[x, y, w, h]` per frame; they take precedence over `frames` (used for non-grid sheets such as Aseprite exports). `offsets` (optional) are `[ox, oy]` per frame: the trim offset inside the untrimmed frame (`frame` facet), applied as `AtlasTexture.margin`.
* `tile_overrides["x,y"].anim` (T2.09) is `{ "frames": [[x,y],…], "durations_ms": [..] }`; M8 turns it into an animated tile.

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

### 4.9 Map (T12.49)

Python reads `.tmx`/`.tmj` (Tiled) and `.ldtk` (LDtk, one map per level); Godot builds them
(`builder/recipes/imported_maps_recipe.gd`).

```json
{ "id": "tiled_map.maps.town", "pack_id": "tiled_map", "source": "assets/packs/tiled_map/maps/town.tmx",
  "format": "tiled", "tile_size": [16, 16], "size": [6, 4],
  "layers": [
    { "name": "Ground", "kind": "tiles", "tileset": "overworld", "cells": [[8, 0, 0, 0, 0], [2, 0, 1, 2, 0]] },
    { "name": "Collisions", "kind": "intgrid", "cells": [[7, 1], [2, 0]],
      "values": [{ "value": 1, "name": "wall", "solid": true }] },
    { "name": "spawn", "kind": "objects",
      "objects": [{ "name": "start", "type": "spawn", "x": 24, "y": 40, "w": 0, "h": 0, "props": {} }] } ] }
```

* `id` is the pack id and the dotted path of the file (`<pack>.maps.town`); an LDtk level adds its
  identifier (`<pack>.world.level_0`). `size` is in cells. Layers are listed bottom first.
* `tiles` layers: `cells` is run-length encoded over the cells row by row (`width * height` in
  all), each run `[count, source_id, column, row, transform]`. `source_id` -1 is an empty cell.
  `transform` holds the flips: 1 = flip x, 2 = flip y, 4 = transpose (Tiled's diagonal flip). Godot
  keeps them in the alternative-tile bits of the cell, so the TileSet needs no extra tiles.
  `tileset` names the generated TileSet (`generated/tilesets/<tileset>.tres`); a layer with tiles of
  several tile sets becomes one layer per tile set, named `Layer (tileset)`.
* `intgrid` layers (LDtk): runs `[count, value]`. `values` lists the values the layer uses; the
  `solid` ones become collision. `solid` starts as true for a value named wall, solid or collision
  (or for every value of a layer with such a name when no value is named) and is kept across
  regenerations, so a change in the catalog stays.
* `objects` layers: only the objects that are markers. `type` is `spawn`, `door` or `sign`, taken
  from the layer name (Tiled), the object's type or class, or the entity identifier (LDtk).
  `x`/`y`/`w`/`h` are pixels from the top left of the map. `props` are the Tiled properties or LDtk
  fields (`target_map`, `target_spawn` for a door, `text` for a sign).
* Tiled tile data may be CSV, base64, base64 + zlib or base64 + gzip. Zstandard cannot be read: the
  layer is skipped with TILE-009. An infinite map is flattened to the bounds of its tiles. Only
  orthogonal maps are read. A layer whose tile sheet is not part of a tile set is skipped with
  TILE-009 too.

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
* `declined_sha256` (optional, T12.58): the hash of a generated version the user declined with
  *Keep mine*. Promotion skips the conflict while the new content has this hash.
* Keys are posix_rel paths, sorted.
* Covered paths (T5.01): `generated/`, `addons/rpg_runtime/`, `addons/rpg_project_tools/`, `rpggen/` (except `rpggen/logs/`, `rpggen/results/`, the ledger itself and `rpggen/generation_report.json`), `assets/packs/`, `game/` (as `user_seed`), `project.godot`, `.gitignore`, `.gitattributes` and `README.md`. `GENERATION_REPORT.md` is not covered: it is rewritten after promotion.
* `project.godot`, `rpggen/generator_config.json` and `rpggen/asset_catalog.json` are merge-managed: they never produce a conflict.
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
* Three optional keys of a metroidvania (release 1.2), each **written only when it holds
  something**, so the save of a top-down game is byte for byte what 1.1 wrote and `save_version`
  stays 1: `abilities` (array of ability ids, T14.05), `broken_cells`
  (`{ "<room id>": [[x, y], ...] }`: the breakable blocks that were broken, T14.05) and `room_fog`
  (`{ "<room id>": true }`: the rooms that are on the room map, T14.08). A reader ignores entries
  it cannot use. The place a defeated player returns to is kept in `flags` (`respawn.map`,
  `respawn.x`, `respawn.y`), set by resting at a save station.

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
| `declined_sha256` (file entries) | ownership_ledger | T12.58 |
| `anim`, `terrain.peering` | `tile_overrides` entries | T2.09, T8.06 |
| `terrain_proposal` | Facets | T8.06 |
| `terrain: {set, terrain, peering}` replaces `terrain.wangid` | `tile_overrides` entries | T8.06 |
| `maps` | asset_catalog | T12.49 |
| `imported_maps` | generator_config | T12.49 |
| `export_targets` | generator_config | T12.52 |
| `starter_map.rooms`, `room_size`, `abilities`, `pickups`, `added_rooms` | generator_config (metroidvania) | T14.06 |
| `starter.boss` | generator_config | T14.02 |
| `rooms` | world_plan | T14.06 |
| `abilities`, `broken_cells`, `room_fog` | save game | T14.05, T14.08 |
| `summary.map.world`, `summary.map.rooms`; repair kind `exit` | command-line documents | T14.10, T14.06 |

---

## 11. Command-line documents (`--json`, json_version 1)

`rpggen generate|analyze|restore|diagnose|repair-world --json` prints **one** JSON document on stdout; every
human line goes to stderr. The schema is `rpggen/schema/cli.schema.json`. The document is not a
file in a project: it is the answer to one command, so it is written with `json.dumps(indent=2)`
and its keys are in the order below, not sorted. Every document starts with the envelope:

```json
{ "json_version": 1, "command": "generate", "ok": false, "exit_code": 1, … }
```

* `ok` is `exit_code == 0`. The exit codes are the same for every command:

  | Code | Meaning |
  |-----:|---------|
  | 0 | OK |
  | 1 | Generation failed (`BUILD`, `VAL`, `SMOKE`, `REGEN` or `TILE` errors) |
  | 2 | Usage error |
  | 3 | Environment or input (`ENV`, `ARCH`, `CAT`, `ASSET`, `ADAPT` errors) |
  | 4 | Cancelled with Ctrl+C (the work folder is discarded) |
  | 70 | Internal error (`BUILD-005`) |

  For a run that failed, the first error decides between 1 and 3; `BUILD-005` anywhere makes it 70.
* A **usage error** (2), a **cancel** that no running command noticed (4) and an **internal error**
  outside a generation (70) are `{ envelope…, "error": "<one sentence>" }` and nothing else.
  A mistake that `argparse` finds (an unknown option) exits with 2 and prints no document.
* `issue` is `{ "code", "severity", "message", "fix", "file" }`. `file` is always there: a
  `posix_rel` path, or `null`.

### 11.1 `generate`

```json
{
  "json_version": 1, "command": "generate", "ok": true, "exit_code": 0,
  "target": "C:/games/demo",
  "dry_run": false,
  "cancelled": false,
  "run_id": "0123abcd",
  "failed_phase": null,
  "failed_staging": null,
  "skipped": { "export": "ENV-010" },
  "timings": { "preflight": 0.4, "build": 12.5 },
  "issues": [ { "code": "ASSET-010", "severity": "warning", "message": "…", "fix": "…", "file": null } ]
}
```

* `failed_phase` is the phase that stopped the run (`PHASES_M1` names; a dry run uses
  `preflight`, `catalog` and `plan`). `failed_staging` is the kept work folder
  (`.rpggen_failed`) of a failed run. `skipped` maps a check that did not run to the code of
  the note that says why (T12.07). `timings` are seconds per phase; they vary from run to run
  and are never written to a project file. `run_id` is the eight hex characters that mark the
  run's lines in the application log (empty for a dry run).
* `cancelled` is true for exit code 4.
* With `--dry-run`, `dry_run` is true, nothing was made, and the document has a `summary`
  (it is `{}` when preflight already stopped the run):

```json
"summary": {
  "project_name": "forest", "archetype": "turn_based", "regeneration": false,
  "godot": null,
  "packs": ["forest"],
  "tile_size": 16, "tile_size_from": "packs", "resolution": [640, 360],
  "assets": 51, "objects": 2, "tilesets": 1,
  "roles": { "GROUND": { "count": 3, "need": "required" } },
  "placeholders": ["PLAYER"],
  "map": { "size": [40, 24],
           "counts": { "buildings": 1, "npcs": 1, "enemies": 1, "chests": 1, "decorations": 8 },
           "warnings": [] }
}
```

  `tile_size_from` is `packs` when the size was read from the packs (`--pack` without
  `--tile-size`) and `config` otherwise. `roles` lists every required and recommended role and
  every other role that has an asset; `need` is `required`, `recommended` or `optional`.
  `placeholders` are the roles `--placeholder` would fill (those that have no asset).
  `map` is present when the requirement check passed. `godot` is the executable that was found
  (never started), or `null`.

### 11.2 `analyze`

`mode` tells the three shapes apart:

* `"pack"`: `pack`, `assets` (the table as data: `id`, `path`, `usage`, `role`, `grid`,
  `frame`, `confidence`, `status`), `objects` and `tilesets` (counts), `catalog_file` (the `--out`
  file or `null`), `issues` and, with `--expected`, `accuracy` (`groups`, `correct`, `total`,
  `misses`).
* `"corpus"`: `report` (the file written), `passed`, `failures`, `groups`, `thresholds`. The exit
  code is 1 when a threshold is missed.
* `"private_corpus"`: `report` and `summary` (the content of the written report).

An error (`ARCH-*` and so on) is `{ envelope…, "issues": [ … ] }` with exit code 3 (or 1).

### 11.3 `restore`, `diagnose` and `repair-world`

* `repair-world` (T13.24): `target`, `dry_run`, `repairs`, `offered` and `unfixable` (lists of
  `{ "kind": "retarget"/"spawn"/"door"/"exit"/"unfixable", "map", "node", "what" }` (`exit`: the exit of a metroidvania's room): what was written
  or, with `--dry-run`, would be; what a map the run may not write would need; and what cannot be
  mended) and `backup` (the folder name under `.rpggen_backups` the maps went to, or `null`).
  `rpggen/world_repair.json` in the project holds the last run's `repairs`, `skipped` and
  `unfixable`.
* `restore`: `target`, `backup` (the `--backup` name or `null`), `saved_state` (the folder the replaced state
  was saved to; `null` on failure) and `issues` (the error that stopped it, or `[]`).
* `diagnose`: `target` and `bundle` (the zip written).

## 12. `rpggen/world_plan.json` (world_plan_version 1, T13.20)

Written by rpggen (generated-owned) for a config with `starter_map.areas`, and read by the recipes.
It is **stored and reused**: once a map of an area other than the starter map exists, the seed and
the rows of the table no longer change it; a new row is appended and gets a door pair with the
area it joins.

| Key | Type | Notes |
|-----|------|-------|
| `world_plan_version` | int | 1 |
| `seed` | int | The seed the world was planned with. |
| `areas` | array of Area | The village first, then the rows in table order, then the rows added later. |
| `grid` | object | Area id → `[x, y]` on the world's grid. The village is `[0, 0]`, the first area `[1, 0]`. |
| `notes` | array of string | What the planner changed (a biome the packs cannot fill, a cave that is not locked). They are in the report under *World*. |
| `key` | object, optional | `{ "item", "area", "opens", "chest" }`: the key item, the area whose chest holds it, the area it opens. Only when a cave is locked. |
| `maps` | object | Area id → `{ "map_hash" }`: the ledger hash of the map rpggen built, recorded once. A map that was there before the run that would have built it has no entry: a person may have made or changed it (T13.24). |

**Area:** `id` (the slug of the name, unique; the village is `starter_map`), `name`, `biome` (what
it got), `wanted_biome` (only when it differs), `size`, `map` (`game/maps/<id>.tscn`), `ground`
(the ground asset the biome prefers, or ""), `doors`, and for every area but the village
`chests` (`{ id, cell, gold, items: [{item_id, qty}] }`), `enemies` (`{ id, cell }`),
`decorations` (cells), `decor_words`, `water` (`[x, y, w, h]`, a shore), and `gates`
(`{ id, cell, key_item, door }`). The village's inside is laid out by the starter-map planner.

**Door:** `id` (the node name, `<area>_door_<other>`), `edge` (`N`/`E`/`S`/`W`), `cell` (in the
wall), `spawn` (the floor cell in front of it, where a player arrives), `spawn_id`
(`from_<other>`), `facing`, `to` (area id), `to_map`, `to_spawn`, and `key` when it is locked. The
village's east door uses the starter map's own exit; its other doors are moved along the wall to
free floor, so their `cell` is where the plan wanted them.

### 12.1 `rooms` (a metroidvania, T14.06)

A metroidvania's plan has no areas (`areas` is `[]`); its world is the `rooms` object. `grid` and
`maps` are keyed by room id. The plan is stored and reused in the same way: once the scene of one
room exists, the options and the seed no longer change it, and a row of `starter_map.added_rooms`
appends a room.

| Key | Type | Notes |
|-----|------|-------|
| `version` | int | 1 |
| `room_size` | `[w, h]` | Tiles; every room of the first plan has this size. |
| `abilities` | array of string | The abilities of the world, in the order they are found. |
| `start`, `end` | room id | Where the game starts and where the hermit ends it. |
| `guardian` | room id or `""` | The room of the guardian, which gives the first ability. |
| `path` | array of room id | The way from `start` to `end` (the critical path). |
| `list` | array of Room | The rooms, in plan order; added rooms last. |

**Room:** `id` (`room_01`, or `room_<slug>` for an added room), `name`, `kind` (`start`,
`corridor`, `shaft`, `guardian`, `pickup`, `end`), `map` (`game/maps/rooms/<id>.tscn`), `cell`
(`[x, y]` on the world's grid; a room above another has the smaller `y`), `size`, `added` (true
for a room of `added_rooms`), `tiles`, `exits`, and what stands in it, each a **feet cell** (the
cell whose floor the thing stands on): `spawn`, `sign`, `station`, `npc`, `chest`, `enemies`,
`items`, `pickup` (`{ "ability", "cell" }`), `guardian` (`{ "cell", "grants" }`) and `gates`.

* `tiles` is the room as rows of characters, one per cell: `#` ground, `.` air, `=` a one-way
  platform, `H` a ladder, `T` the top of a ladder (a ladder with a platform on it), `^` a hazard
  and `B` a breakable block. The recipe paints exactly this; nothing about a room's shape is
  decided in GDScript.
* **Exit:** `id` (`<room>_exit_<n|e|s|w>`, also the name of its trigger and its spawn point),
  `edge`, `cell`, `to` (room id), `to_exit`, and `needs` (an ability) when the way to it is
  closed by a gate.
* **Gate:** `{ "ability", "kind", "size", "cell" }`: what the room's shape asks for. `kind` is
  `ledge` (double jump, high jump), `gap` (dash), `wall` (break blocks) or `shaft` (wall jump);
  `size` is the height or width in tiles, out of reach without the ability and within reach
  with it (and with the abilities found before it).
