@tool
extends EditorPlugin
## Test only (T17.33): makes a short level the way a user makes one, in a running editor, and
## says what came of it. tests/integration/level_probe_run.py copies this folder into a copy of
## a generated project as addons/zz_level_probe, enables it, writes res://rpggen/level_probe_in.json
## and starts `godot --headless --editor`:
##
##   {"template": "res://game/maps/starter_map.tscn", "out": "res://game/maps/probe_level.tscn"}
##
## The template is one of the project's maps (a map of squares or diamonds, or a room of a
## side-view world): its scripts, camera, spawn points and player are kept; its tiles and its
## things are cleared. Then:
##
## * the ground is painted with the Terrain tool's own painting (`set_cells_terrain_connect`, the
##   tool's Connect mode, and `set_cells_terrain_path`, its Path mode): the terrain the template's
##   ground was most painted with over the whole level (a side view: a floor, a gap, a step, a
##   ledge), and up to four other terrains of the tile set as a user picks them (one of each
##   surface, of the sheet nearest the ground's) in blobs with inner corners and a two-cell path;
##   a side view also gets the template's one-way platforms, ladders, hazards and slopes;
## * the project's Assets dock places what a user furnishes a level with (its own placement,
##   `Placement.place_new`): buildings, decorations, people, animals, enemies.
##
## The level is saved under `out`, and res://rpggen/results/level_probe.json says how each terrain
## painted (cells whose piece does not fit its neighbours, holes, how often the middle is the main
## tile) and what each placed thing is (its scale, its filter, whether it collides and moves).

const IN := "res://rpggen/level_probe_in.json"
const OUT := "res://rpggen/results/level_probe.json"
const PLACEMENT := "res://addons/rpg_project_tools/dock/placement.gd"
const INDEX := "res://addons/rpg_project_tools/dock/index.gd"
const CATALOG_EDIT := "res://addons/rpg_project_tools/tools/catalog_edit.gd"

const SIDES := [TileSet.CELL_NEIGHBOR_RIGHT_SIDE, TileSet.CELL_NEIGHBOR_BOTTOM_SIDE, TileSet.CELL_NEIGHBOR_LEFT_SIDE, TileSet.CELL_NEIGHBOR_TOP_SIDE]
const CORNERS := [TileSet.CELL_NEIGHBOR_BOTTOM_RIGHT_CORNER, TileSet.CELL_NEIGHBOR_BOTTOM_LEFT_CORNER, TileSet.CELL_NEIGHBOR_TOP_LEFT_CORNER, TileSet.CELL_NEIGHBOR_TOP_RIGHT_CORNER]
const STEP := {
	TileSet.CELL_NEIGHBOR_RIGHT_SIDE: Vector2i(1, 0), TileSet.CELL_NEIGHBOR_BOTTOM_SIDE: Vector2i(0, 1),
	TileSet.CELL_NEIGHBOR_LEFT_SIDE: Vector2i(-1, 0), TileSet.CELL_NEIGHBOR_TOP_SIDE: Vector2i(0, -1),
	TileSet.CELL_NEIGHBOR_BOTTOM_RIGHT_CORNER: Vector2i(1, 1), TileSet.CELL_NEIGHBOR_BOTTOM_LEFT_CORNER: Vector2i(-1, 1),
	TileSet.CELL_NEIGHBOR_TOP_LEFT_CORNER: Vector2i(-1, -1), TileSet.CELL_NEIGHBOR_TOP_RIGHT_CORNER: Vector2i(1, -1),
}
## The surfaces a user paints a level with, in the order they are taken.
const SURFACES: Array[String] = ["water", "dirt", "path", "sand", "stone", "soil", "snow", "grass", "dark", "rock"]
## What a level is furnished with: role and how many.
const FURNISH := [["BUILDING", 2], ["DECORATION", 8], ["NPC", 2], ["ANIMAL", 2], ["ENEMY", 2], ["CHEST", 1]]

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
	var template := str(wanted["template"])
	var root: Node = null
	for attempt in 20:
		EditorInterface.open_scene_from_path(template)
		await _frames(15)
		root = EditorInterface.get_edited_scene_root()
		if root != null and root.scene_file_path == template:
			break
	if root == null or root.scene_file_path != template:
		report["error"] = "the template did not open"
		_finish(report)
		return
	var ground := root.get_node_or_null("Ground") as TileMapLayer
	if ground == null or ground.tile_set == null:
		report["error"] = "the template has no Ground layer with a tile set"
		_finish(report)
		return
	var side := bool(root.get("side_view")) if root.get("side_view") != null else false
	var iso := RpgIso.footprint_of(root) != Vector2i.ZERO
	report["view"] = "side" if side else ("isometric" if iso else "top_down")
	var ts := ground.tile_set
	var base := _most_painted(ground)
	var specials := _specials(root) if side else []
	report["base"] = _label(ts, base)
	_clear(root)
	var size := Vector2i(40, 26)
	if side:
		var room_size: Variant = root.get("room_size")
		size = room_size if room_size is Vector2i else Vector2i(40, 23)
	elif iso:
		size = Vector2i(14, 14)
	report["size"] = [size.x, size.y]
	var details := root.get_node_or_null("GroundDetails") as TileMapLayer
	if details == null:
		details = ground
	var painted: Array[Dictionary] = []
	if side:
		painted = _paint_side(ground, base, size)
		report["specials"] = _place_specials(root, specials, size)
	else:
		painted = _paint_top(ground, details, base, size, iso)
	for done in painted:
		(report["terrains"] as Array).append(_judge(done["layer"], done["cells"], done["set"], done["terrain"], ts))
	await _frames(2)
	_furnish(root, size, side, report)
	_move_spawn(root, ground, size, side)
	report["saved"] = OK
	EditorInterface.save_scene_as(str(wanted["out"]))
	await _frames(5)
	report["ok"] = true
	_finish(report)

# ------------------------------------------------------------------ what the template had

## The (terrain set, terrain) a layer is most painted with, or [-1, -1].
func _most_painted(layer: TileMapLayer) -> Vector2i:
	var counts := {}
	for cell in layer.get_used_cells():
		var td := layer.get_cell_tile_data(cell)
		if td != null and td.terrain_set >= 0 and td.terrain >= 0:
			var key := Vector2i(td.terrain_set, td.terrain)
			counts[key] = int(counts.get(key, 0)) + 1
	var best := Vector2i(-1, -1)
	var most := 0
	for key: Vector2i in counts.keys():
		if int(counts[key]) > most:
			most = int(counts[key])
			best = key
	return best

func _flag(td: TileData, ts: TileSet, name: String) -> bool:
	if ts.get_custom_data_layer_by_name(name) < 0:
		return false
	return bool(td.get_custom_data(name))

## The tiles of a side-view template that are no terrain and do something: one-way platforms,
## ladders, hazards, slopes, by the layer they were painted on.
func _specials(root: Node) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var seen := {}
	for layer: TileMapLayer in _layers(root):
		var ts := layer.tile_set
		for cell in layer.get_used_cells():
			var td := layer.get_cell_tile_data(cell)
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
			elif td.terrain_set < 0 and ts.get_physics_layers_count() > 0 and td.get_collision_polygons_count(0) > 0 and td.is_collision_polygon_one_way(0, 0):
				kind = "one_way"
			if kind == "" or seen.has(kind):
				continue
			seen[kind] = true
			out.append({"kind": kind, "layer": String(root.get_path_to(layer)), "source": layer.get_cell_source_id(cell), "coords": layer.get_cell_atlas_coords(cell), "alt": layer.get_cell_alternative_tile(cell)})
	return out

func _layers(node: Node) -> Array[TileMapLayer]:
	var out: Array[TileMapLayer] = []
	for child in node.find_children("*", "TileMapLayer", true, false):
		out.append(child as TileMapLayer)
	return out

## Clears the tiles and the things of the template: its player, camera, spawn points and scripts
## stay.
func _clear(root: Node) -> void:
	for layer in _layers(root):
		layer.clear()
	for path: String in ["YSorted/Entities", "Entities"]:
		var holder := root.get_node_or_null(path)
		if holder == null:
			continue
		for child in holder.get_children():
			if not child.is_in_group("player") and String(child.name) != "Player":
				holder.remove_child(child)
				child.free()
	var triggers := root.get_node_or_null("Triggers")
	if triggers != null:
		for child in triggers.get_children():
			triggers.remove_child(child)
			child.free()

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

func _paint_top(ground: TileMapLayer, details: TileMapLayer, base: Vector2i, size: Vector2i, iso: bool) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var all := _rect(0, 0, size.x, size.y)
	if base.x >= 0:
		ground.set_cells_terrain_connect(all, base.x, base.y)
		out.append({"layer": ground, "cells": all, "set": base.x, "terrain": base.y})
	var others := _others(ground.tile_set, base)
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
		if (areas[i] as Array).is_empty():
			# a path two cells wide, painted as the Path mode paints, with a bend
			var line: Array[Vector2i] = []
			for x in range(2, 30):
				line.append(Vector2i(x, 12))
			for y in range(13, 22):
				line.append(Vector2i(29, y))
			details.set_cells_terrain_path(line, key.x, key.y)
			var second: Array[Vector2i] = []
			for x in range(2, 31):
				second.append(Vector2i(x, 13))
			for y in range(14, 22):
				second.append(Vector2i(30, y))
			details.set_cells_terrain_path(second, key.x, key.y)
			cells = line + second
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

func _place_specials(root: Node, specials: Array[Dictionary], size: Vector2i) -> Array:
	var out: Array = []
	var floor_y := size.y - 4
	for special in specials:
		var layer := root.get_node_or_null(str(special["layer"])) as TileMapLayer
		if layer == null:
			continue
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
			layer.set_cell(cell, int(special["source"]), special["coords"], int(special["alt"]))
		out.append({"kind": special["kind"], "layer": special["layer"], "cells": cells.size()})
	return out

## How a terrain painted on `cells`: `wrong` cells whose piece does not fit the cells around
## (a side or, with both its sides, a corner that says the terrain goes on where it does not,
## or the other way round), `holes` cells left without a tile, and of the cells inside (all
## eight neighbours the terrain) how many tiles they use and the share of the most used.
func _judge(layer: TileMapLayer, cells: Array[Vector2i], set_index: int, terrain: int, ts: TileSet) -> Dictionary:
	var inside := {}
	for c in cells:
		inside[c] = true
	var wrong := 0
	var holes := 0
	var examples: Array = []
	var middle := {}
	var middles := 0
	var mode := ts.get_terrain_set_mode(set_index)
	for c in cells:
		var td := layer.get_cell_tile_data(c)
		if td == null:
			holes += 1
			continue
		var bad := td.terrain_set != set_index or td.terrain != terrain
		var bits: Array = []
		if mode != TileSet.TERRAIN_MODE_MATCH_CORNERS:
			bits.append_array(SIDES)
		if mode != TileSet.TERRAIN_MODE_MATCH_SIDES:
			bits.append_array(CORNERS)
		for bit: int in bits:
			if bad or not td.is_valid_terrain_peering_bit(bit):
				continue
			var step: Vector2i = STEP[bit]
			var there := inside.has(c + step)
			if CORNERS.has(bit):
				there = there and inside.has(c + Vector2i(step.x, 0)) and inside.has(c + Vector2i(0, step.y))
			var says := td.get_terrain_peering_bit(bit) == terrain
			if says != there:
				bad = true
		if bad:
			wrong += 1
			if examples.size() < 6:
				examples.append([c.x, c.y])
		var all_in := true
		for step: Vector2i in STEP.values():
			if not inside.has(c + step):
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
		"cells": cells.size(), "wrong": wrong, "holes": holes, "wrong_at": examples,
		"middles": middles, "middle_tiles": middle.size(),
		"main_share": float(most) / float(middles) if middles > 0 else 1.0,
	}

# ------------------------------------------------------------------ furnishing from the dock

func _cell_world(root: Node, cell: Vector2i) -> Vector2:
	var ground := root.get_node("Ground") as TileMapLayer
	return ground.to_global(ground.map_to_local(cell))

func _furnish(root: Node, size: Vector2i, side: bool, report: Dictionary) -> void:
	var placement_script: GDScript = load(PLACEMENT)
	var index_script: GDScript = load(INDEX)
	var catalog_script: GDScript = load(CATALOG_EDIT)
	var entries: Array = index_script.call("build", catalog_script.call("load_catalog"))
	report["entries"] = entries.size()
	var manager := get_undo_redo()
	var spots: Array[Vector2i] = []
	if side:
		var floor_y := size.y - 5
		for x in [3, 7, 11, 19, 21, 33, 35, 37, 9, 27]:
			spots.append(Vector2i(x, floor_y if x < 24 or x > 30 else floor_y - 4))
	else:
		for y in range(2, size.y - 1, 4):
			for x in range(2, size.x - 1, 5):
				spots.append(Vector2i(x, y))
		if size.x <= 14:
			spots = [Vector2i(2, 9), Vector2i(5, 11), Vector2i(10, 2), Vector2i(12, 4), Vector2i(3, 6), Vector2i(7, 1), Vector2i(1, 12), Vector2i(11, 12)]
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
		"scales": scales, "filters": filters, "animated": animated, "frames": frames, "shapes": shapes,
		"script": node.get_script().resource_path if node.get_script() != null else "",
	}

## The default spawn point and the player in the open: the middle of a map, the floor at the
## left of a side-view room.
func _move_spawn(root: Node, ground: TileMapLayer, size: Vector2i, side: bool) -> void:
	var cell := Vector2i(3, size.y - 5) if side else Vector2i(size.x / 2, size.y / 2 - 3)
	if size.x <= 14:
		cell = Vector2i(7, 7)
	var at := ground.to_global(ground.map_to_local(cell))
	var spawn := root.get_node_or_null("SpawnPoints/default") as Node2D
	if spawn != null:
		spawn.global_position = at
	for player in root.find_children("Player", "", true, false):
		if player is Node2D:
			(player as Node2D).global_position = at

func _finish(report: Dictionary) -> void:
	DirAccess.make_dir_recursive_absolute(OUT.get_base_dir())
	var file := FileAccess.open(OUT, FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "  ", true) + "\n")
	file.close()
	get_tree().quit(0)
