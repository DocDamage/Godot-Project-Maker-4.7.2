@tool
extends EditorPlugin
## Test only (T17.33): makes a short level the way a user makes one, in a running editor, in an
## assets-only project (the kind `assets`: the packs' tile sets and the dock's scenes, no game),
## and says what came of it. tests/integration/level_probe_run.py copies this folder into a copy
## of the project as addons/zz_level_probe, enables it, writes res://rpggen/level_probe_in.json
## and starts `godot --headless --editor`:
##
##   {"out": "res://game/levels/probe_level.tscn"}
##
## As a user does: a new 2D scene with a TileMapLayer `Ground` and one above it,
## `GroundDetails`, both with the project's tile set (of generated/tilesets/, the one with the
## most terrains), and a y-sorted `YSorted/Entities` for what is placed. It is saved and opened
## in the editor. Then:
##
## * the ground is painted with the Terrain tool's own painting (`set_cells_terrain_connect`, the
##   tool's Connect mode, and `set_cells_terrain_path`, its Path mode): the terrain with the most
##   tiles over the whole level (seen from the side: a floor, a gap, a step, a ledge and walls),
##   and up to four other terrains of the tile set as a user picks them (one of each surface, of
##   the sheet nearest the ground's) in blobs with inner corners and a two-cell path; a terrain
##   of strips alone (paths one tile wide) is painted as straight paths. Seen from the side, the
##   tile set's one-way platforms, ladders, hazards and slopes are put where they belong;
## * the project's Assets dock places what a user furnishes a level with (its own placement,
##   `Placement.place_new`): buildings, decorations, people, animals, enemies, a chest.
##
## The level is saved under `out`, and res://rpggen/results/level_probe.json says how each terrain
## painted (cells whose piece does not fit its neighbours, holes, how often the middle is the main
## tile) and what each placed thing is (its scale, its filter, whether it collides and moves).

const IN := "res://rpggen/level_probe_in.json"
const OUT := "res://rpggen/results/level_probe.json"
const CONFIG := "res://rpggen/generator_config.json"
const TILESETS := "res://generated/tilesets/"
const TEMPLATE := "res://rpggen/level_probe_template.tscn"
const PLACEMENT := "res://addons/rpg_project_tools/dock/placement.gd"
const INDEX := "res://addons/rpg_project_tools/dock/index.gd"
const CATALOG_EDIT := "res://addons/rpg_project_tools/tools/catalog_edit.gd"
const HEIGHT_LAYERS := "res://addons/rpg_project_tools/tools/height_layers.gd"

## The sides and corners of a cell, in turn round it, on squares and on diamonds; each corner
## lies between the side before it and the side after it.
const SQUARE_SIDES := [TileSet.CELL_NEIGHBOR_RIGHT_SIDE, TileSet.CELL_NEIGHBOR_BOTTOM_SIDE, TileSet.CELL_NEIGHBOR_LEFT_SIDE, TileSet.CELL_NEIGHBOR_TOP_SIDE]
const SQUARE_CORNERS := [TileSet.CELL_NEIGHBOR_BOTTOM_RIGHT_CORNER, TileSet.CELL_NEIGHBOR_BOTTOM_LEFT_CORNER, TileSet.CELL_NEIGHBOR_TOP_LEFT_CORNER, TileSet.CELL_NEIGHBOR_TOP_RIGHT_CORNER]
const DIAMOND_SIDES := [TileSet.CELL_NEIGHBOR_BOTTOM_RIGHT_SIDE, TileSet.CELL_NEIGHBOR_BOTTOM_LEFT_SIDE, TileSet.CELL_NEIGHBOR_TOP_LEFT_SIDE, TileSet.CELL_NEIGHBOR_TOP_RIGHT_SIDE]
const DIAMOND_CORNERS := [TileSet.CELL_NEIGHBOR_BOTTOM_CORNER, TileSet.CELL_NEIGHBOR_LEFT_CORNER, TileSet.CELL_NEIGHBOR_TOP_CORNER, TileSet.CELL_NEIGHBOR_RIGHT_CORNER]

static func _sides(ts: TileSet) -> Array:
	return DIAMOND_SIDES if ts.tile_shape == TileSet.TILE_SHAPE_ISOMETRIC else SQUARE_SIDES

static func _corners(ts: TileSet) -> Array:
	return DIAMOND_CORNERS if ts.tile_shape == TileSet.TILE_SHAPE_ISOMETRIC else SQUARE_CORNERS
## The surfaces a user paints a level with, in the order they are taken.
const SURFACES: Array[String] = ["water", "dirt", "path", "road", "sand", "stone", "soil", "snow", "grass", "dark", "rock"]
## What a level is furnished with: role and how many.
const FURNISH := [["BUILDING", 2], ["DECORATION", 10], ["NPC", 2], ["ANIMAL", 2], ["ENEMY", 2], ["CHEST", 1]]
## The Terrain tool lays a terrain's variants by their probability with Godot's global random
## numbers; seeded, a level paints the same on every run and system (an unseeded one laid the
## middle of a terrain of the sample 67 % its main tile once on CI, 2026-10-27).
const PAINT_SEED := 1733

func _enter_tree() -> void:
	if FileAccess.file_exists(IN):
		_run.call_deferred()

func _frames(count: int) -> void:
	for i in count:
		await get_tree().process_frame

func _run() -> void:
	var report := {"ok": false, "error": "", "terrains": [], "places": [], "specials": []}
	var wanted: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(IN))
	await _frames(20)
	var waited := 0
	while EditorInterface.get_resource_filesystem().is_scanning() and waited < 3000:
		await _frames(1)
		waited += 1
	var config: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(CONFIG))
	var side := str(config.get("archetype", "")) == "assets" and str(config.get("view", "")) == "side"
	var iso := str(config.get("projection", "")) == "isometric"
	report["view"] = "side" if side else ("isometric" if iso else "top_down")
	var ts := _tileset()
	if ts == null:
		# A character/prop pack is a valid assets-only project without ground art.
		# Keep its empty layers and exercise the dock, without inventing terrain.
		ts = TileSet.new()
		var tile_size := maxi(8, int(config.get("base_tile_size", 16)))
		ts.tile_size = Vector2i(tile_size, tile_size)
	report["tileset"] = ts.resource_path
	var err := _make_template(ts)
	if err != OK:
		report["error"] = "the new scene was not saved: %d" % err
		_finish(report)
		return
	var root: Node = null
	for attempt in 20:
		EditorInterface.open_scene_from_path(TEMPLATE)
		await _frames(15)
		root = EditorInterface.get_edited_scene_root()
		if root != null and root.scene_file_path == TEMPLATE:
			break
	if root == null or root.scene_file_path != TEMPLATE:
		report["error"] = "the new scene did not open"
		_finish(report)
		return
	var ground := root.get_node("Ground") as TileMapLayer
	var details := root.get_node("GroundDetails") as TileMapLayer
	var base := _ground_terrain(ts, side)
	report["base"] = _label(ts, base)
	var size := Vector2i(40, 23) if side else (Vector2i(14, 14) if iso else Vector2i(40, 26))
	report["size"] = [size.x, size.y]
	var painted: Array[Dictionary] = []
	seed(PAINT_SEED)
	if side:
		painted = _paint_side(ground, base, size)
		report["specials"] = _place_specials(ground, _specials(ts), size)
	else:
		painted = _paint_top(ground, details, base, size, iso)
	for done in painted:
		(report["terrains"] as Array).append(_judge(done["layer"], done["cells"], done["set"], done["terrain"], ts, bool(done.get("strip", false))))
	if iso:
		report["stack"] = _stack(root, ts)
	await _frames(2)
	_furnish(root, size, side, report)
	EditorInterface.save_scene_as(str(wanted["out"]))
	await _frames(5)
	report["saved"] = str(wanted["out"])
	report["ok"] = true
	_finish(report)

# ------------------------------------------------------------------ the new scene

## The tile set of generated/tilesets/ with the most terrains (the first by name when as many).
func _tileset() -> TileSet:
	var best: TileSet = null
	var most := -1
	var files := DirAccess.get_files_at(TILESETS)
	files.sort()
	for file in files:
		if not file.ends_with(".tres"):
			continue
		var ts := load(TILESETS + file) as TileSet
		if ts == null:
			continue
		var count := 0
		for s in ts.get_terrain_sets_count():
			count += ts.get_terrains_count(s)
		if count > most:
			most = count
			best = ts
	return best

## A new scene as a user starts a level: the root, two tile layers with the tile set, and a
## y-sorted holder for what is placed. Saved as TEMPLATE.
func _make_template(ts: TileSet) -> Error:
	var root := Node2D.new()
	root.name = "Level"
	for layer_name in ["Ground", "GroundDetails"]:
		var layer := TileMapLayer.new()
		layer.name = layer_name
		layer.tile_set = ts
		root.add_child(layer)
		layer.owner = root
	var ysorted := Node2D.new()
	ysorted.name = "YSorted"
	ysorted.y_sort_enabled = true
	root.add_child(ysorted)
	ysorted.owner = root
	var entities := Node2D.new()
	entities.name = "Entities"
	entities.y_sort_enabled = true
	ysorted.add_child(entities)
	entities.owner = root
	var packed := PackedScene.new()
	var err := packed.pack(root)
	root.free()
	if err != OK:
		return err
	return ResourceSaver.save(packed, TEMPLATE)

# ------------------------------------------------------------------ what the tile set has

## The terrain a user lays first: seen from above a grass if the tile set has one (the one with
## the most tiles), else the terrain with the most tiles; [-1, -1] without terrains.
func _ground_terrain(ts: TileSet, side: bool) -> Vector2i:
	var counts := _terrain_tiles(ts)
	var best := Vector2i(-1, -1)
	var most := 0
	var keys: Array = counts.keys()
	keys.sort()
	for grass_first in ([false] if side else [true, false]):
		for key: Vector2i in keys:
			var words := _words(ts.get_terrain_name(key.x, key.y))
			if grass_first and (words.is_empty() or words[0] != "grass"):
				continue
			if (counts[key] as Array).size() > most:
				most = (counts[key] as Array).size()
				best = key
		if best.x >= 0:
			return best
	return best

## {Vector2i(set, terrain): [TileData, ...]} of the tiles the packs draw (each atlas tile as it
## is, not its alternatives: those stand in for pieces a pack does not draw).
func _terrain_tiles(ts: TileSet) -> Dictionary:
	var out := {}
	for i in ts.get_source_count():
		var source := ts.get_source(ts.get_source_id(i)) as TileSetAtlasSource
		if source == null:
			continue
		for t in source.get_tiles_count():
			var td := source.get_tile_data(source.get_tile_id(t), 0)
			if td == null or td.terrain_set < 0 or td.terrain < 0:
				continue
			var key := Vector2i(td.terrain_set, td.terrain)
			if not out.has(key):
				out[key] = []
			(out[key] as Array).append(td)
	return out

## True for a terrain of strips alone (paths one tile wide): none of its tiles says the terrain
## goes on on all four sides.
func _strip_terrain(ts: TileSet, key: Vector2i) -> bool:
	if ts.get_terrain_set_mode(key.x) == TileSet.TERRAIN_MODE_MATCH_CORNERS:
		return false  # a set joined at the corners (Medieval Town's plates) is an area: no side bits
	for td: TileData in _terrain_tiles(ts).get(key, []):
		var all_sides := true
		for bit: int in _sides(ts):
			if not td.is_valid_terrain_peering_bit(bit) or td.get_terrain_peering_bit(bit) != key.y:
				all_sides = false
		if all_sides:
			return false
	return true

## [source id, atlas coords] of the plain ground drawn for a sheet without one
## (farm_ground: the asset rpggen_farm_kit.ground), or [].
func _plain_tile(ts: TileSet) -> Array:
	if ts.get_custom_data_layer_by_name("asset_id") < 0:
		return []
	for i in ts.get_source_count():
		var source_id := ts.get_source_id(i)
		var source := ts.get_source(source_id) as TileSetAtlasSource
		if source == null:
			continue
		for t in source.get_tiles_count():
			var coords := source.get_tile_id(t)
			var td := source.get_tile_data(coords, 0)
			if td != null and str(td.get_custom_data("asset_id")) == "rpggen_farm_kit.ground":
				return [source_id, coords]
	return []

func _flag(td: TileData, ts: TileSet, name: String) -> bool:
	if ts.get_custom_data_layer_by_name(name) < 0:
		return false
	return bool(td.get_custom_data(name))

## The tiles of a side-view tile set that are no terrain and do something: one-way platforms,
## ladders, hazards, slopes; the first of each.
func _specials(ts: TileSet) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var seen := {}
	for i in ts.get_source_count():
		var source_id := ts.get_source_id(i)
		var source := ts.get_source(source_id) as TileSetAtlasSource
		if source == null:
			continue
		for t in source.get_tiles_count():
			var coords := source.get_tile_id(t)
			var td := source.get_tile_data(coords, 0)
			if td == null:
				continue
			var kind := ""
			if _flag(td, ts, "ladder"):
				kind = "ladder"
			elif _flag(td, ts, "hazard"):
				kind = "hazard"
			elif _flag(td, ts, "slope_up"):
				kind = "slope_up"
			elif _flag(td, ts, "slope_down"):
				kind = "slope_down"
			elif td.terrain_set < 0 and ts.get_physics_layers_count() > 1 and td.get_collision_polygons_count(1) > 0:
				kind = "one_way"  # the one-way physics layer (SideTileset.ONE_WAY_PHYSICS)
			if kind == "" or seen.has(kind):
				continue
			seen[kind] = true
			out.append({"kind": kind, "source": source_id, "coords": coords})
	return out

# ------------------------------------------------------------------ painting

func _label(ts: TileSet, key: Vector2i) -> String:
	if key.x < 0 or key.x >= ts.get_terrain_sets_count() or key.y >= ts.get_terrains_count(key.x):
		return ""
	return ts.get_terrain_name(key.x, key.y)

func _words(text: String) -> PackedStringArray:
	return text.to_lower().replace("·", " ").replace("_", " ").replace("-", " ").split(" ", false)

## The other terrains a user paints with: one of each surface (the first word of the terrain's
## name), of the set whose name shares most words with the ground's.
func _others(ts: TileSet, base: Vector2i) -> Array[Vector2i]:
	var base_words := _words(_label(ts, base))
	var base_surface := base_words[0] if base_words.size() > 0 else ""
	var best := {}
	var score := {}
	for s in ts.get_terrain_sets_count():
		for t in ts.get_terrains_count(s):
			if Vector2i(s, t) == base:
				continue
			var words := _words(ts.get_terrain_name(s, t))
			if words.is_empty() or words[0] == base_surface or not SURFACES.has(words[0]):
				continue
			var shared := 0
			for w in words:
				if base_words.has(w):
					shared += 1
			if not best.has(words[0]) or shared > int(score[words[0]]):
				best[words[0]] = Vector2i(s, t)
				score[words[0]] = shared
	var out: Array[Vector2i] = []
	for surface in SURFACES:
		if best.has(surface) and out.size() < 4:
			out.append(best[surface])
	return out

func _rect(x0: int, y0: int, w: int, h: int) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for y in range(y0, y0 + h):
		for x in range(x0, x0 + w):
			out.append(Vector2i(x, y))
	return out

## A blob with inner corners: a rectangle with a bite out of one side and a bay added to another.
func _blob(x0: int, y0: int, w: int, h: int) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for cell in _rect(x0, y0, w, h):
		if cell.x >= x0 + w - 3 and cell.y < y0 + 2:
			continue  # the bite: two inner corners
		out.append(cell)
	for cell in _rect(x0 + 2, y0 + h, 3, 2):
		out.append(cell)  # the bay
	return out

## Straight paths one tile wide (a terrain of strips): a row and a column, painted as the Path
## mode paints, apart from each other.
func _strips(layer: TileMapLayer, key: Vector2i, x0: int, y0: int, length: int) -> Array[Vector2i]:
	var row: Array[Vector2i] = []
	for x in range(x0, x0 + length):
		row.append(Vector2i(x, y0))
	layer.set_cells_terrain_path(row, key.x, key.y)
	var column: Array[Vector2i] = []
	for y in range(y0 + 2, y0 + 2 + length / 2):
		column.append(Vector2i(x0, y))
	layer.set_cells_terrain_path(column, key.x, key.y)
	return row + column

func _paint_top(ground: TileMapLayer, details: TileMapLayer, base: Vector2i, size: Vector2i, iso: bool) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var all := _rect(0, 0, size.x, size.y)
	var ts := ground.tile_set
	if base.x >= 0:
		if _strip_terrain(ts, base):
			# beds or paths alone: the plain ground under them (a tile of its own: the one drawn
			# in the pack's grass colour, or the pack's), and the strips on the layer above
			var plain := _plain_tile(ts)
			if not plain.is_empty():
				for cell in all:
					ground.set_cell(cell, int(plain[0]), plain[1])
			out.append({"layer": details, "cells": _strips(details, base, 2, 2, 12), "set": base.x, "terrain": base.y, "strip": true})
		else:
			ground.set_cells_terrain_connect(all, base.x, base.y)
			out.append({"layer": ground, "cells": all, "set": base.x, "terrain": base.y})
	var others := _others(ts, base)
	var areas: Array = []
	if iso:
		areas = [_blob(1, 1, 5, 4), _blob(8, 7, 5, 3)]
	else:
		areas = [_blob(3, 3, 9, 6), _blob(15, 15, 9, 5), [], _blob(29, 3, 8, 5)]
	for i in others.size():
		if i >= areas.size():
			break
		var key: Vector2i = others[i]
		var cells: Array[Vector2i] = []
		if _strip_terrain(ts, key):
			var at: Vector2i = (areas[i] as Array)[0] if not (areas[i] as Array).is_empty() else Vector2i(2, 20)
			out.append({"layer": details, "cells": _strips(details, key, at.x, at.y, 8), "set": key.x, "terrain": key.y, "strip": true})
			continue
		if (areas[i] as Array).is_empty():
			# a path two cells wide with a bend, painted as a user paints a wide path: Connect
			for x in range(2, 31):
				cells.append(Vector2i(x, 12))
				cells.append(Vector2i(x, 13))
			for y in range(14, 22):
				cells.append(Vector2i(29, y))
				cells.append(Vector2i(30, y))
			details.set_cells_terrain_connect(cells, key.x, key.y)
		else:
			for c: Vector2i in areas[i]:
				cells.append(c)
			details.set_cells_terrain_connect(cells, key.x, key.y)
		out.append({"layer": details, "cells": cells, "set": key.x, "terrain": key.y})
	return out

func _paint_side(ground: TileMapLayer, base: Vector2i, size: Vector2i) -> Array[Dictionary]:
	if base.x < 0:
		return []
	var cells: Array[Vector2i] = []
	var floor_y := size.y - 4
	for cell in _rect(0, floor_y, size.x, 4):
		if cell.x >= 14 and cell.x <= 16 and cell.y < size.y - 1:
			continue  # a gap with a pit
		cells.append(cell)
	for cell in _rect(24, floor_y - 4, 7, 4):
		cells.append(cell)  # a step up
	for cell in _rect(5, floor_y - 7, 6, 2):
		cells.append(cell)  # a ledge in the air
	for cell in _rect(0, 0, 1, floor_y):
		cells.append(cell)  # walls at the ends
	for cell in _rect(size.x - 1, 0, 1, floor_y):
		cells.append(cell)
	ground.set_cells_terrain_connect(cells, base.x, base.y)
	return [{"layer": ground, "cells": cells, "set": base.x, "terrain": base.y}]

func _place_specials(layer: TileMapLayer, specials: Array[Dictionary], size: Vector2i) -> Array:
	var out: Array = []
	var floor_y := size.y - 4
	for special in specials:
		var cells: Array[Vector2i] = []
		match str(special["kind"]):
			"one_way":
				cells = _rect(17, floor_y - 5, 4, 1)
			"ladder":
				cells = _rect(31, floor_y - 8, 1, 8)
			"hazard":
				cells = _rect(14, size.y - 2, 3, 1)
			"slope_up":
				cells = [Vector2i(23, floor_y - 1)]
			"slope_down":
				cells = [Vector2i(31, floor_y - 1)]
		for cell in cells:
			layer.set_cell(cell, int(special["source"]), special["coords"])
		out.append({"kind": special["kind"], "cells": cells.size()})
	return out

## How a terrain painted on `cells`: `wrong` cells whose piece does not fit the cells around
## (a side or, with both its sides, a corner that says the terrain goes on where it does not,
## or the other way round), `holes` cells left without a tile, and of the cells inside (all
## eight neighbours the terrain; for strips, both along the strip) how many tiles they use and
## the share of the most used.
func _judge(layer: TileMapLayer, cells: Array[Vector2i], set_index: int, terrain: int, ts: TileSet, strip: bool = false) -> Dictionary:
	var inside := {}
	for c in cells:
		inside[c] = true
	var wrong := 0
	var holes := 0
	var examples: Array = []
	var middle := {}
	var middles := 0
	var mode := ts.get_terrain_set_mode(set_index)
	var sides := _sides(ts)
	var corners := _corners(ts)
	var stand_ins := 0
	for c in cells:
		var td := layer.get_cell_tile_data(c)
		if td == null:
			holes += 1
			continue
		if layer.get_cell_alternative_tile(c) > 0:
			stand_ins += 1  # the nearest piece the pack draws, for one it does not (complete_terrains)
		var bad := td.terrain_set != set_index or td.terrain != terrain
		var drawn := td
		if mode == TileSet.TERRAIN_MODE_MATCH_CORNERS and layer.get_cell_alternative_tile(c) > 0:
			# a stand-in on the edge of a set joined at the corners says nothing of the corners on
			# empty cells; what it shows there is the piece it was made of (complete_corner_sets)
			var source := ts.get_source(layer.get_cell_source_id(c)) as TileSetAtlasSource
			drawn = source.get_tile_data(layer.get_cell_atlas_coords(c), 0)
		var bits: Array = []
		if mode != TileSet.TERRAIN_MODE_MATCH_CORNERS:
			bits.append_array(sides)
		if mode != TileSet.TERRAIN_MODE_MATCH_SIDES:
			bits.append_array(corners)
		for bit: int in bits:
			if bad or not td.is_valid_terrain_peering_bit(bit):
				continue
			var there := inside.has(layer.get_neighbor_cell(c, bit))
			var at := corners.find(bit)
			if at >= 0:
				# a corner is the terrain's when the cell there and the two sides beside it are
				there = there and inside.has(layer.get_neighbor_cell(c, sides[at])) and inside.has(layer.get_neighbor_cell(c, sides[(at + 1) % 4]))
			if mode == TileSet.TERRAIN_MODE_MATCH_CORNERS:
				# Painting uses ignore_empty_terrains=true. A corner touching unpainted
				# space is unconstrained, not a request for this terrain at that corner.
				# Check the joins inside the painted region; valid outer edges may be empty.
				if not there:
					continue
				there = true
			var says := drawn.get_terrain_peering_bit(bit) == terrain
			if says != there:
				bad = true
		if bad:
			wrong += 1
			if examples.size() < 6:
				examples.append([c.x, c.y])
		var all_in := true
		if strip:
			# along the strip: the sides across from each other both its own
			all_in = false
			for k in 2:
				if inside.has(layer.get_neighbor_cell(c, sides[k])) and inside.has(layer.get_neighbor_cell(c, sides[k + 2])):
					all_in = true
		else:
			for bit: int in sides + corners:
				if not inside.has(layer.get_neighbor_cell(c, bit)):
					all_in = false
		if all_in:
			middles += 1
			var key := "%d:%d,%d:%d" % [layer.get_cell_source_id(c), layer.get_cell_atlas_coords(c).x, layer.get_cell_atlas_coords(c).y, layer.get_cell_alternative_tile(c)]
			middle[key] = int(middle.get(key, 0)) + 1
	var most := 0
	for key: String in middle.keys():
		most = maxi(most, int(middle[key]))
	return {
		"name": ts.get_terrain_name(set_index, terrain), "set": set_index, "layer": String(layer.name),
		"cells": cells.size(), "wrong": wrong, "holes": holes, "wrong_at": examples, "strip": strip,
		"stand_ins": stand_ins,
		"middles": middles, "middle_tiles": middle.size(),
		"main_share": float(most) / float(middles) if middles > 0 else 1.0,
	}

# ------------------------------------------------------------------ furnishing from the dock

# ------------------------------------------------------------------ what is stacked (2026-10-26)

## The cells of the tiles of the tile set by their asset id: {asset_id: [source, coords]}.
func _tiles_by_id(ts: TileSet) -> Dictionary:
	var out := {}
	if ts.get_custom_data_layer_by_name("asset_id") == -1:
		return out
	for i in ts.get_source_count():
		var source_id := ts.get_source_id(i)
		var src := ts.get_source(source_id) as TileSetAtlasSource
		if src == null:
			continue
		for t in src.get_tiles_count():
			var coords := src.get_tile_id(t)
			out[str(src.get_tile_data(coords, 0).get_custom_data("asset_id"))] = [source_id, coords]
	return out

## The tiles of `stack` (the custom data) whose asset id has every word of `words`, by id.
func _stack_tiles(ts: TileSet, by_id: Dictionary, stack: String, words: Array = []) -> Array[String]:
	var out: Array[String] = []
	if ts.get_custom_data_layer_by_name("stack") == -1:
		return out
	for id: String in by_id:
		var at: Array = by_id[id]
		var src := ts.get_source(int(at[0])) as TileSetAtlasSource
		if str(src.get_tile_data(at[1], 0).get_custom_data("stack")) != stack:
			continue
		var fits := true
		for word: String in words:
			if not id.contains(word):
				fits = false
		if fits:
			out.append(id)
	out.sort()
	return out

## Paints `id` on `cell` of `layer`; false when the tile set has no such tile.
func _put(layer: TileMapLayer, by_id: Dictionary, id: String, cell: Vector2i) -> bool:
	if id == "" or not by_id.has(id):
		return false
	var at: Array = by_id[id]
	layer.set_cell(cell, int(at[0]), at[1])
	return true

## What a user stacks, as the dock's height layers make it (tools/height_layers.gd): a hill of
## blocks with a ramp up to it, and a house of storeys on blocks under a roof whose pieces join,
## with an awning on its front and a thing on its roof, each layer at the height the dock
## suggests. {layers: [{name, height, cells}], tiles: {what: asset id}, top_of_house,
## top_of_hill} for what the tile set has.
func _stack(root: Node, ts: TileSet) -> Dictionary:
	var heights: GDScript = load(HEIGHT_LAYERS)
	var by_id := _tiles_by_id(ts)
	var blocks := _stack_tiles(ts, by_id, "block")
	var storeys := _stack_tiles(ts, by_id, "storey")
	var out := {"layers": [], "tiles": {}}
	if blocks.is_empty():
		return out
	var manager := get_undo_redo()
	var hill: Array[Vector2i] = [Vector2i(9, 8), Vector2i(10, 8), Vector2i(9, 9), Vector2i(10, 9)]
	var house: Array[Vector2i] = [Vector2i(3, 3), Vector2i(4, 3), Vector2i(3, 4), Vector2i(4, 4)]
	var block := blocks[0]
	for id in blocks:  # a block of the ground's own kind first, a pavement under a house
		if id.contains("grass") or id.contains("pavement"):
			block = id
			break
	out["tiles"]["block"] = block
	var base: int = heights.call("suggested", root)
	var first: TileMapLayer = heights.call("add_layer", root, base, manager)
	for cell in hill:
		_put(first, by_id, block, cell)
	if not storeys.is_empty():
		var pavement := _stack_tiles(ts, by_id, "block", ["sidewalk"]) + _stack_tiles(ts, by_id, "block", ["pavement"])
		var footing: String = pavement[0] if not pavement.is_empty() else block
		out["tiles"]["footing"] = footing
		for cell in house:  # a house stands on a block of pavement (Gridwright City's README)
			_put(first, by_id, footing, cell)
	# up to the hill towards row - 1: a low ramp and a high one (Gridwright Tiles' README), else
	# stairs, else any ramp
	var low := _stack_tiles(ts, by_id, "ramp", ["grass", "up_ne_low"])
	var high := _stack_tiles(ts, by_id, "ramp", ["grass", "up_ne_high"])
	var stairs := _stack_tiles(ts, by_id, "ramp", ["stairs", "up_ne"])
	var ramps := _stack_tiles(ts, by_id, "ramp")
	if not low.is_empty() and not high.is_empty():
		_put(first, by_id, low[0], Vector2i(9, 11))
		_put(first, by_id, high[0], Vector2i(9, 10))
		out["tiles"]["ramp"] = high[0]
	elif not stairs.is_empty():
		_put(first, by_id, stairs[0], Vector2i(9, 10))
		out["tiles"]["ramp"] = stairs[0]
	elif not ramps.is_empty():
		_put(first, by_id, ramps[0], Vector2i(9, 10))
		out["tiles"]["ramp"] = ramps[0]
	(out["layers"] as Array).append({"name": String(first.name), "height": base, "cells": first.get_used_cells().size()})
	out["top_of_hill"] = heights.call("top_at", root, Vector2i(9, 9))
	if storeys.is_empty():
		return out
	var ground_floor := _stack_tiles(ts, by_id, "storey", ["ground", "windows"])
	var door := _stack_tiles(ts, by_id, "storey", ["ground", "door_sw"])
	var upper := _stack_tiles(ts, by_id, "storey", ["upper", "windows"])
	var wall: String = ground_floor[0] if not ground_floor.is_empty() else storeys[0]
	out["tiles"]["storey"] = wall
	for k in 3:
		var height: int = heights.call("suggested", root)
		var layer: TileMapLayer = heights.call("add_layer", root, height, manager)
		for cell in house:
			var id := wall if k == 0 else (upper[0] if not upper.is_empty() else wall)
			if k == 0 and cell == Vector2i(3, 4) and not door.is_empty():
				id = door[0]  # the face towards row + 1
			_put(layer, by_id, id, cell)
		(out["layers"] as Array).append({"name": String(layer.name), "height": height, "cells": layer.get_used_cells().size()})
		if k == 0:
			var awnings := _stack_tiles(ts, by_id, "on_storey", ["_sw"])
			if not awnings.is_empty():
				var front: TileMapLayer = heights.call("add_layer", root, height, manager)
				_put(front, by_id, awnings[0], Vector2i(4, 4))
				out["tiles"]["awning"] = awnings[0]
	var roofs := _stack_tiles(ts, by_id, "roof")
	if not roofs.is_empty():
		var height: int = heights.call("suggested", root)
		var roof_layer: TileMapLayer = heights.call("add_layer", root, height, manager)
		for cell in house:
			# NE = 1 (row - 1), SE = 2 (col + 1), SW = 4 (row + 1), NW = 8 (col - 1)
			var mask := 0
			for pair: Array in [[Vector2i(0, -1), 1], [Vector2i(1, 0), 2], [Vector2i(0, 1), 4], [Vector2i(-1, 0), 8]]:
				if house.has(cell + (pair[0] as Vector2i)):
					mask += int(pair[1])
			var named := _stack_tiles(ts, by_id, "roof", ["roof_%02d" % mask])
			_put(roof_layer, by_id, named[0] if not named.is_empty() else roofs[0], cell)
		out["tiles"]["roof"] = roofs[0]
		(out["layers"] as Array).append({"name": String(roof_layer.name), "height": height, "cells": roof_layer.get_used_cells().size()})
		var tops := _stack_tiles(ts, by_id, "on_roof")
		if not tops.is_empty():
			var top_height: int = heights.call("top_at", root, Vector2i(3, 3))
			var on_roof: TileMapLayer = heights.call("add_layer", root, top_height, manager)
			_put(on_roof, by_id, tops[0], Vector2i(3, 3))
			out["tiles"]["on_roof"] = tops[0]
			(out["layers"] as Array).append({"name": String(on_roof.name), "height": top_height, "cells": 1})
	out["top_of_house"] = heights.call("top_at", root, Vector2i(4, 4))
	# a plateau of the ground's floor two blocks up, given its sides by the dock (T18.20): blocks
	# of its surface under the edges that face the camera
	var floors: Array[String] = []
	for id: String in by_id:
		if id.contains("floor_grass"):
			floors.push_front(id)  # the ground's own kind first
		elif id.contains("floor_"):
			floors.append(id)
	if not floors.is_empty():
		var plateau: TileMapLayer = heights.call("add_layer", root, 32, manager)
		for cell: Vector2i in [Vector2i(11, 2), Vector2i(12, 2), Vector2i(11, 3), Vector2i(12, 3)]:
			_put(plateau, by_id, floors[0], cell)
		var catalog: Dictionary = (load(CATALOG_EDIT) as GDScript).call("load_catalog")
		var sides: int = heights.call("face_sides", root, plateau, manager, catalog)
		out["plateau"] = {"floor": floors[0], "height": 32, "sides": sides, "top": heights.call("top_at", root, Vector2i(12, 3))}
	return out

func _cell_world(root: Node, cell: Vector2i) -> Vector2:
	var ground := root.get_node("Ground") as TileMapLayer
	return ground.to_global(ground.map_to_local(cell))

func _furnish(root: Node, size: Vector2i, side: bool, report: Dictionary) -> void:
	var placement_script: GDScript = load(PLACEMENT)
	var index_script: GDScript = load(INDEX)
	var catalog_script: GDScript = load(CATALOG_EDIT)
	var entries: Array = index_script.call("build", catalog_script.call("load_catalog"))
	report["entries"] = entries.size()
	var roles := {}
	for entry: Dictionary in entries:
		var role := str(entry.get("role", ""))
		roles[role] = int(roles.get(role, 0)) + 1
	report["entry_roles"] = roles
	var manager := get_undo_redo()
	var spots: Array[Vector2i] = []
	if side:
		var floor_y := size.y - 5
		for x in [3, 7, 11, 19, 21, 33, 35, 37, 9, 27, 2, 12, 18, 22, 36, 38]:
			spots.append(Vector2i(x, floor_y if x < 24 or x > 30 else floor_y - 4))
	elif size.x <= 14:
		spots = [Vector2i(2, 9), Vector2i(5, 11), Vector2i(10, 2), Vector2i(12, 4), Vector2i(3, 6), Vector2i(7, 1), Vector2i(1, 12), Vector2i(11, 12), Vector2i(9, 9), Vector2i(6, 4)]
	else:
		for y in range(2, size.y - 1, 4):
			for x in range(2, size.x - 1, 5):
				spots.append(Vector2i(x, y))
	var used := 0
	for pair: Array in FURNISH:
		var role := str(pair[0])
		if side and role in ["BUILDING", "ANIMAL"]:
			continue
		var chosen: Array = []
		for entry: Dictionary in entries:
			if str(entry.get("role", "")) == role and chosen.size() < int(pair[1]):
				chosen.append(entry)
		for entry: Dictionary in chosen:
			if used >= spots.size():
				break
			var at := _cell_world(root, spots[used])
			used += 1
			var placement: RefCounted = placement_script.new()
			placement.set("snap", int((root.get_node("Ground") as TileMapLayer).tile_set.tile_size.x))
			var node: Node2D = placement.call("place_new", entry, root, manager, at)
			var seen := {"role": role, "name": str(entry.get("name", "")), "scene": str(entry.get("scene_path", ""))}
			if node == null:
				seen["error"] = "nothing was placed"
			else:
				seen.merge(_looks(node))
			(report["places"] as Array).append(seen)

## What a placed thing is: its parent, its pictures' scales (whole numbers), filters, whether it
## is animated and collides.
func _looks(node: Node2D) -> Dictionary:
	var scales: Array = []
	var filters: Array = []
	var animated := false
	var frames := 0
	for child in [node] + node.find_children("*", "", true, false):
		if child is Sprite2D:
			var s := child as Sprite2D
			scales.append([s.global_scale.x, s.global_scale.y])
			filters.append(int(s.texture_filter))
		elif child is AnimatedSprite2D:
			var a := child as AnimatedSprite2D
			scales.append([a.global_scale.x, a.global_scale.y])
			filters.append(int(a.texture_filter))
			animated = true
			if a.sprite_frames != null:
				for anim in a.sprite_frames.get_animation_names():
					frames = maxi(frames, a.sprite_frames.get_frame_count(anim))
	var shapes := node.find_children("*", "CollisionShape2D", true, false).size() + node.find_children("*", "CollisionPolygon2D", true, false).size()
	return {
		"node": String(node.name), "parent": String(node.get_parent().name), "x": node.global_position.x, "y": node.global_position.y,
		"raised": int(node.get_parent().get_meta("rpg_height", 0)),
		"scales": scales, "filters": filters, "animated": animated, "frames": frames, "shapes": shapes,
		"script": node.get_script().resource_path if node.get_script() != null else "",
	}

func _finish(report: Dictionary) -> void:
	DirAccess.make_dir_recursive_absolute(OUT.get_base_dir())
	var file := FileAccess.open(OUT, FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "  ", true) + "\n")
	file.close()
	get_tree().quit(0)
