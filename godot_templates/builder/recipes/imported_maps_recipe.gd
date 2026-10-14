extends RefCounted
## Builds the maps read from Tiled and LDtk files (T12.49) as game/maps/imported/<pack>/<map>.tscn
## (user_seed: written once, never touched afterwards). Python read the files; the catalog's `maps`
## hold the cells, run-length encoded, with the tile set and source id of every layer, so this
## recipe only paints them.
##
## * A tile layer goes into the configured map layer (`map_layers`) of the same name, else it
##   becomes a layer of its own in front of the Y-sorted nodes. Its cells use the project's
##   TileSets; flipped tiles keep their flips in the alternative-tile bits.
## * The solid values of an IntGrid layer become invisible collision rectangles.
## * Objects named spawn, door or sign become markers: a spawn point (the first is also "default"),
##   a door to another imported map (`target_map` and `target_spawn` properties) and a marker with
##   the sign's `text`.
##
## The map chosen as the starter map is built by the starter map recipe through `build_map` (the
## layout planner is skipped); this recipe builds the other selected maps.
##
## **An isometric Tiled map** (T17.28, `projection: isometric` in the catalog) is a map of an
## isometric project only, and a map of squares of a project seen from above only: a map of the
## other view is not built (the run says so, TILE-013). Its layers are `iso_tiles`: the pictures
## of the project's isometric tile set by asset id, each painted at its own turn. The first layer
## that Tiled draws in its place is the `Ground`; every other one is a layer of its own in the
## Y-sorted nodes (a wall, a crate or a second floor sorts with who walks behind it), moved as far
## as Tiled moves it. The cells of the pictures the catalog calls walls are blocked, a diamond
## each. Objects stand on the middle of their diamond: Tiled places them on the map's rows and
## columns, each counted in the height of a diamond.

const RECIPE_VERSION := 1
## The version of what the recipe does for an isometric project only (T17.28): it is in the hash
## of such a project and of no other, so a project seen from above rebuilds nothing.
const ISO_VERSION := 1

const Paths := preload("../lib/paths.gd")
const JsonUtil := preload("../lib/json_util.gd")
const SceneUtil := preload("../lib/scene_util.gd")
const MapUtil := preload("../lib/map_util.gd")
const MapBuild := preload("../lib/map_build.gd")
const BuildContext := preload("../lib/build_context.gd")
const MapGeo := preload("../lib/map_geo.gd")
const IsoTileset := preload("../lib/iso_tileset.gd")

const OUT_DIR := "res://game/maps/imported/"
const STARTER_PATH := "res://game/maps/starter_map.tscn"
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
const DEFAULT_TILESET := "overworld"
const PROJECTION_ISOMETRIC := "isometric"
const ISO_LAYER := "iso_tiles"
## The unseen body that blocks the cells of an isometric map's walls.
const ISO_WALLS := "ImportedWalls"

## How an imported map is drawn: "isometric" for a Tiled map of diamonds, else "top_down".
static func map_projection(m: Dictionary) -> String:
	return PROJECTION_ISOMETRIC if JsonUtil.to_str(m.get("projection", "")) == PROJECTION_ISOMETRIC else "top_down"

## True when the map can be a map of this project: an isometric map of an isometric project, a
## map of squares of a project seen from above (catalog.map_fits).
static func fits(ctx: BuildContext, m: Dictionary) -> bool:
	return (map_projection(m) == PROJECTION_ISOMETRIC) == IsoTileset.project_wanted(ctx.config)

# ---------------------------------------------------------------- selection

## `imported_maps` of the config: {include: Array[String], starter: String}.
static func selection(ctx: BuildContext) -> Dictionary:
	var section := ctx.section("imported_maps")
	var include: Array[String] = []
	var raw: Variant = section.get("include", [])
	if raw is Array:
		var items: Array = raw
		for item: Variant in items:
			include.append(JsonUtil.to_str(item))
	return {"include": include, "starter": JsonUtil.to_str(section.get("starter", ""))}

## The catalog maps built as extra maps: selected and not the starter map.
static func extra_maps(ctx: BuildContext) -> Array[Dictionary]:
	var sel := selection(ctx)
	var include: Array = sel["include"]
	var starter := JsonUtil.to_str(sel["starter"])
	var out: Array[Dictionary] = []
	for m in ctx.catalog.map_defs():
		var map_id := JsonUtil.to_str(m["id"])
		if include.has(map_id) and map_id != starter and fits(ctx, m):
			out.append(m)
	return out

## The catalog map that becomes the starter map, or {} (also for a map of the other view: the
## starter map is then planned as without one).
static func starter_map(ctx: BuildContext) -> Dictionary:
	var starter := JsonUtil.to_str(selection(ctx)["starter"])
	if starter == "":
		return {}
	var found := ctx.catalog.map_def(starter)
	if not found.is_empty() and not fits(ctx, found):
		return {}
	return found

## game/maps/imported/<pack>/<map>.tscn; the map name is the id without the pack, dots as "_".
static func map_path(m: Dictionary) -> String:
	var pack := JsonUtil.to_str(m["pack_id"])
	var stem := JsonUtil.to_str(m["id"]).trim_prefix(pack + ".").replace(".", "_")
	return OUT_DIR + pack + "/" + stem + ".tscn"

## The scene a door's `target_map` property names: a res:// path as it is, "starter_map", or the
## id (or its last words) of a selected map. "" when no built map matches.
static func resolve_target(ctx: BuildContext, value: String) -> String:
	if value == "":
		return ""
	if value.begins_with("res://"):
		return value
	if value == "starter_map":
		return STARTER_PATH
	var sel := selection(ctx)
	var include: Array = sel["include"]
	var starter := JsonUtil.to_str(sel["starter"])
	for m in ctx.catalog.map_defs():
		var map_id := JsonUtil.to_str(m["id"])
		if (map_id != starter and not include.has(map_id)) or not fits(ctx, m):
			continue
		var path := STARTER_PATH if map_id == starter else map_path(m)
		var stem := path.get_file().get_basename()
		if value == map_id or map_id.ends_with("." + value) or value == stem or stem.ends_with("_" + value):
			return path
	return ""

# ---------------------------------------------------------------- recipe

func outputs(ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	for m in extra_maps(ctx):
		var path := map_path(m)
		if not FileAccess.file_exists(path):
			out.append(path)
	return out

func input_hash(ctx: BuildContext) -> String:
	var hashed := {
		"v": RECIPE_VERSION,
		"maps": extra_maps(ctx),
		"selection": selection(ctx),
		"layers": ctx.config.get("map_layers", []),
		"tilesets": ctx.catalog.tileset_defs(),
	}
	if IsoTileset.project_wanted(ctx.config):  # nothing more for a project seen from above
		hashed["iso_v"] = ISO_VERSION
	return ctx.stable_hash(hashed)

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	for m in extra_maps(ctx):
		var path := map_path(m)
		if FileAccess.file_exists(path):
			continue
		var stem := path.get_file().get_basename()
		issues.append_array(build_map(ctx, m, path, stem.capitalize().replace(" ", ""), stem))
	return issues

# ---------------------------------------------------------------- one map

## Builds and saves the scene of catalog map `m`. Returns the issues.
static func build_map(ctx: BuildContext, m: Dictionary, out_path: String, root_name: String, map_id: String) -> Array:
	if map_projection(m) == PROJECTION_ISOMETRIC:
		return build_iso_map(ctx, m, out_path, root_name, map_id)
	var issues: Array = []
	var layers: Array = m["layers"]
	var size := Vector2i(JsonUtil.to_int(m["size"][0]), JsonUtil.to_int(m["size"][1]))
	var tile_sets := {}  # tile set name -> TileSet (null when it was not generated)
	var default_name := ""
	for item: Variant in layers:
		var lay: Dictionary = item
		if JsonUtil.to_str(lay["kind"]) != "tiles":
			continue
		var set_name := JsonUtil.to_str(lay["tileset"])
		if not tile_sets.has(set_name):
			tile_sets[set_name] = load(Paths.TILESETS_DIR + set_name + ".tres") as TileSet
			if default_name == "" and tile_sets[set_name] != null:
				default_name = set_name
	if default_name == "":
		default_name = DEFAULT_TILESET
		tile_sets[default_name] = load(Paths.TILESETS_DIR + default_name + ".tres") as TileSet
	var default_set: TileSet = tile_sets[default_name]
	if default_set == null:
		issues.append(ctx.make_issue("VAL-002", {"file": Paths.TILESETS_DIR + default_name + ".tres"}, out_path))
		return issues
	if not ResourceLoader.exists(PLAYER_SCENE):
		issues.append(ctx.make_issue("VAL-002", {"file": PLAYER_SCENE}, PLAYER_SCENE))
		return issues
	var def := ctx.catalog.tileset_def(default_name)
	var tile_px := JsonUtil.to_int(m["tile_size"][0])
	if not def.is_empty():
		tile_px = JsonUtil.to_int(def["tile_size"][0])
	var scale := float(tile_px) / float(maxi(JsonUtil.to_int(m["tile_size"][0]), 1))

	var root := MapUtil.new_map_root(root_name, map_id)
	var layer_names: Array = ctx.config.get("map_layers", MapUtil.DEFAULT_LAYERS)
	var nodes := MapUtil.build_layers(root, layer_names, default_set)
	var claimed := {}
	var solid_cells := {}
	var objects: Array = []
	var missing := 0
	for item: Variant in layers:
		var lay: Dictionary = item
		var kind := JsonUtil.to_str(lay["kind"])
		var layer_name := JsonUtil.to_str(lay["name"])
		if kind == "tiles":
			var set_name := JsonUtil.to_str(lay["tileset"])
			var tile_set: TileSet = tile_sets[set_name]
			if tile_set == null:
				issues.append(ctx.make_issue("TILE-009", {"layer": layer_name, "map": m["id"], "reason": "tile set %s was not generated" % set_name}, out_path))
				continue
			var runs: Array = lay["cells"]
			missing += MapBuild.paint_runs(_layer_for(root, nodes, claimed, layer_name, tile_set), tile_set, size.x, runs)
		elif kind == "intgrid":
			var values: Array = lay["values"]
			var cell_runs: Array = lay["cells"]
			var rects := MapBuild.solid_rects(size.x, cell_runs, MapBuild.solid_values(values))
			for r in rects:
				for y in range(r.position.y, r.end.y):
					for x in range(r.position.x, r.end.x):
						solid_cells[Vector2i(x, y)] = true
			MapBuild.add_solid_body(root, ("Solid_" + layer_name).validate_node_name(), rects, tile_px)
		else:
			var found: Array = lay["objects"]
			objects.append_array(found)
	if missing > 0:
		print("[rpggen] INFO %s: %d cells use tiles that are not in the tile set and stay empty" % [map_id, missing])

	var entities: Node2D = nodes["Entities"]
	var spawns: Node2D = nodes["SpawnPoints"]
	var triggers: Node2D = nodes["Triggers"]
	var default_pos := Vector2.ZERO
	var has_default := false
	var used := {}
	for item: Variant in objects:
		var o: Dictionary = item
		var props: Dictionary = o["props"]
		var pos := Vector2(JsonUtil.to_float(o["x"]) + JsonUtil.to_float(o["w"]) / 2.0, JsonUtil.to_float(o["y"]) + JsonUtil.to_float(o["h"]) / 2.0) * scale
		var object_name := JsonUtil.to_str(o["name"])
		match JsonUtil.to_str(o["type"]):
			"spawn":
				if not has_default:
					has_default = true
					default_pos = pos
					used["default"] = true
					MapUtil.add_marker(spawns, root, "default", pos, true)
				if object_name != "":
					MapUtil.add_marker(spawns, root, _unique(used, object_name), pos, true)
			"door":
				var target := resolve_target(ctx, JsonUtil.to_str(props.get("target_map", "")))
				var door_name := _unique(used, "Door_" + object_name if object_name != "" else "Door")
				if target == "":
					print("[rpggen] INFO %s: door %s has no target map that was built; it is a marker" % [map_id, door_name])
					MapUtil.add_marker(spawns, root, door_name, pos)
				else:
					var cell := Vector2i(floori(pos.x / tile_px), floori(pos.y / tile_px))
					var target_spawn := JsonUtil.to_str(props.get("target_spawn", "default"))
					MapBuild.add_exit_door(triggers, root, door_name, cell, tile_px, target, StringName(target_spawn if target_spawn != "" else "default"))
			"sign":
				var sign_marker := MapUtil.add_marker(spawns, root, _unique(used, "Sign_" + object_name if object_name != "" else "Sign"), pos)
				sign_marker.set_meta("text", JsonUtil.to_str(props.get("text", "")))
	if not has_default:
		var free_cell := MapBuild.free_cell_near_centre(size, solid_cells)
		default_pos = MapUtil.tile_center(free_cell if free_cell.x >= 0 else Vector2i(size.x >> 1, size.y >> 1), tile_px)
		MapUtil.add_marker(spawns, root, "default", default_pos, true)
	MapUtil.place(PLAYER_SCENE, entities, root, default_pos)

	var err := SceneUtil.save_scene(root, out_path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": out_path, "err": err}, out_path))
	return issues

## A node name that is not in `used` yet (`used` records it).
static func _unique(used: Dictionary, wanted: String) -> String:
	var base := wanted.validate_node_name()
	var candidate := base
	var n := 1
	while used.has(candidate):
		n += 1
		candidate = "%s%d" % [base, n]
	used[candidate] = true
	return candidate

## The node a tile layer is painted into: the configured layer of the same name when no other
## layer used it yet (its tile set is the layer's), else a new layer in front of the Y-sorted nodes.
static func _layer_for(root: Node2D, nodes: Dictionary, claimed: Dictionary, layer_name: String, tile_set: TileSet) -> TileMapLayer:
	for key: String in nodes.keys():
		if nodes[key] is TileMapLayer and key.to_lower() == layer_name.to_lower() and not claimed.has(key):
			var existing: TileMapLayer = nodes[key]
			claimed[key] = true
			existing.tile_set = tile_set
			return existing
	var extra := TileMapLayer.new()
	extra.name = layer_name.validate_node_name()
	extra.tile_set = tile_set
	root.add_child(extra)
	var ysorted: Node = nodes["YSorted"]
	root.move_child(extra, ysorted.get_index())
	extra.owner = root
	return extra

# ---------------------------------------------------------------- an isometric map (T17.28)

## Builds and saves the scene of an isometric catalog map `m` in an isometric project. Returns
## the issues.
static func build_iso_map(ctx: BuildContext, m: Dictionary, out_path: String, root_name: String, map_id: String) -> Array:
	var issues: Array = []
	var geo := MapGeo.new(ctx)
	if not geo.isometric:
		issues.append(ctx.make_issue("TILE-001", {"tileset": "iso"}, out_path))
		return issues
	if geo.load_tile_set() == null:
		issues.append(ctx.make_issue("VAL-002", {"file": geo.tileset_path()}, out_path))
		return issues
	if not ResourceLoader.exists(PLAYER_SCENE):
		issues.append(ctx.make_issue("VAL-002", {"file": PLAYER_SCENE}, PLAYER_SCENE))
		return issues
	var built := iso_scene(ctx, geo, m, root_name, map_id)
	var root: Node2D = built["root"]
	var entities: Node2D = root.get_node("YSorted/Entities")
	var default_pos: Vector2 = built["default"]
	MapUtil.place(PLAYER_SCENE, entities, root, default_pos)
	var err := SceneUtil.save_scene(root, out_path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": out_path, "err": err}, out_path))
	return issues

## The scene of an isometric map without its player: `{root, default}`, `default` being where the
## player is put. `geo` has loaded the tile set.
static func iso_scene(ctx: BuildContext, geo: MapGeo, m: Dictionary, root_name: String, map_id: String) -> Dictionary:
	var tile_set := geo.tile_set
	var size := BuildContext.vec2i(m["size"])
	var map_tile := BuildContext.vec2i(m["tile_size"])
	# Tiled's px of this map to the px of the project's diamond
	var scale := Vector2(float(geo.footprint.x) / float(maxi(map_tile.x, 1)), float(geo.footprint.y) / float(maxi(map_tile.y, 1)))
	var root := MapUtil.new_map_root(root_name, map_id)
	var layer_names: Array = ctx.config.get("map_layers", MapUtil.DEFAULT_LAYERS)
	var nodes := MapUtil.build_layers(root, layer_names, tile_set)
	var walls := {}
	for id: Variant in JsonUtil.to_array(m.get("walls", [])):
		walls[JsonUtil.to_str(id)] = true
	var layers: Array = m["layers"]
	var ground_index := ground_layer_index(layers)
	var floor_cells := {}  # the cells of the Ground: where somebody can be put
	var blocked := {}
	var objects: Array = []
	var missing := 0
	var flipped := 0
	for i in layers.size():
		var lay: Dictionary = layers[i]
		var kind := JsonUtil.to_str(lay["kind"])
		if kind == "objects":
			var found: Array = lay["objects"]
			objects.append_array(found)
			continue
		if kind != ISO_LAYER:
			continue
		var layer: TileMapLayer = nodes["Ground"]
		if i != ground_index:
			layer = _iso_layer(root, nodes, JsonUtil.to_str(lay["name"]), tile_set, layer_offset(lay) * scale)
		var pictures := JsonUtil.to_array(lay["pictures"])
		var index := 0
		for run_value: Variant in JsonUtil.to_array(lay["cells"]):
			var run := JsonUtil.to_array(run_value)
			var count := JsonUtil.to_int(run[0])
			var picture := JsonUtil.to_int(run[1])
			var alt := JsonUtil.to_int(run[2])
			for _n in count:
				if picture >= 0 and picture < pictures.size():
					@warning_ignore("integer_division")
					var cell := Vector2i(index % size.x, index / size.x)
					var asset_id := JsonUtil.to_str(pictures[picture])
					# each picture at its own turn: a tile turned four ways is four pictures
					var turn := JsonUtil.to_int(geo.iso.facets(asset_id).get("turn", 0))
					if geo.iso.paint(layer, cell, asset_id, turn):
						if i == ground_index:
							floor_cells[cell] = true
						if walls.has(asset_id):
							blocked[cell] = true
						if alt != 0:
							flipped += 1
					else:
						missing += 1
				index += 1
	if missing > 0:
		print("[rpggen] INFO %s: %d cells use pictures that are not in the tile set and stay empty" % [map_id, missing])
	if flipped > 0:
		print("[rpggen] INFO %s: %d cells are flipped in Tiled and are painted unflipped (an isometric tile has no flipped picture)" % [map_id, flipped])
	var blocked_cells := sorted_cells(blocked)
	if not blocked_cells.is_empty():
		geo.block_cells(root, blocked_cells, ISO_WALLS)

	var spawns: Node2D = nodes["SpawnPoints"]
	var triggers: Node2D = nodes["Triggers"]
	var default_pos := Vector2.ZERO
	var has_default := false
	var used := {}
	for item: Variant in objects:
		var o: Dictionary = item
		var props: Dictionary = o["props"]
		var cell := object_cell(o, map_tile)
		var pos := geo.center(cell)
		var object_name := JsonUtil.to_str(o["name"])
		match JsonUtil.to_str(o["type"]):
			"spawn":
				if not has_default:
					has_default = true
					default_pos = pos
					used["default"] = true
					MapUtil.add_marker(spawns, root, "default", pos, true)
				if object_name != "":
					MapUtil.add_marker(spawns, root, _unique(used, object_name), pos, true)
			"door":
				var target := resolve_target(ctx, JsonUtil.to_str(props.get("target_map", "")))
				var door_name := _unique(used, "Door_" + object_name if object_name != "" else "Door")
				if target == "":
					print("[rpggen] INFO %s: door %s has no target map that was built; it is a marker" % [map_id, door_name])
					MapUtil.add_marker(spawns, root, door_name, pos)
				else:
					var target_spawn := JsonUtil.to_str(props.get("target_spawn", "default"))
					geo.add_exit_door(triggers, root, door_name, cell, target, StringName(target_spawn if target_spawn != "" else "default"))
			"sign":
				var sign_marker := MapUtil.add_marker(spawns, root, _unique(used, "Sign_" + object_name if object_name != "" else "Sign"), pos)
				sign_marker.set_meta("text", JsonUtil.to_str(props.get("text", "")))
	if not has_default:
		default_pos = geo.center(free_floor_cell(floor_cells, blocked, size))
		MapUtil.add_marker(spawns, root, "default", default_pos, true)
	return {"root": root, "default": default_pos}

## The index of the layer that becomes the Ground: the first isometric layer Tiled draws in its
## place (a second floor drawn higher sorts with the rest), else the first one; -1 without one.
static func ground_layer_index(layers: Array) -> int:
	var first := -1
	for i in layers.size():
		var lay: Dictionary = layers[i]
		if JsonUtil.to_str(lay["kind"]) != ISO_LAYER:
			continue
		if first < 0:
			first = i
		if layer_offset(lay) == Vector2.ZERO:
			return i
	return first

## How far Tiled draws a layer from its place, in px of the map.
static func layer_offset(lay: Dictionary) -> Vector2:
	var pair := JsonUtil.to_array(lay.get("offset", []))
	if pair.size() != 2:
		return Vector2.ZERO
	return Vector2(JsonUtil.to_float(pair[0]), JsonUtil.to_float(pair[1]))

## The cell an object of an isometric Tiled map stands on: Tiled places it on the map's columns
## (x) and rows (y), each counted in the height of the map's diamond; its middle decides.
static func object_cell(o: Dictionary, map_tile: Vector2i) -> Vector2i:
	var unit := float(maxi(map_tile.y, 1))
	var x := (JsonUtil.to_float(o["x"]) + JsonUtil.to_float(o["w"]) / 2.0) / unit
	var y := (JsonUtil.to_float(o["y"]) + JsonUtil.to_float(o["h"]) / 2.0) / unit
	return Vector2i(floori(x), floori(y))

## The cell of the Ground nearest the middle of the Ground that nothing blocks (of the nearest,
## the first by row, then column); the middle of the map when there is none.
static func free_floor_cell(floor_cells: Dictionary, blocked: Dictionary, size: Vector2i) -> Vector2i:
	var cells := sorted_cells(floor_cells)
	if cells.is_empty():
		return Vector2i(size.x >> 1, size.y >> 1)
	var low := cells[0]
	var high := cells[0]
	for cell in cells:
		low = Vector2i(mini(low.x, cell.x), mini(low.y, cell.y))
		high = Vector2i(maxi(high.x, cell.x), maxi(high.y, cell.y))
	var middle := Vector2(low + high) / 2.0
	var best := Vector2i(-1, -1)
	var best_distance := INF
	for cell in cells:
		if blocked.has(cell):
			continue
		var apart := Vector2(cell) - middle
		var distance := apart.x * apart.x + apart.y * apart.y
		if distance < best_distance:
			best_distance = distance
			best = cell
	return best if best.x >= 0 else Vector2i(size.x >> 1, size.y >> 1)

## The keys of a dictionary of cells, row by row.
static func sorted_cells(cells: Dictionary) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for key: Variant in cells.keys():
		var cell: Vector2i = key
		out.append(cell)
	out.sort_custom(func(a: Vector2i, b: Vector2i) -> bool: return a.y < b.y or (a.y == b.y and a.x < b.x))
	return out

## A layer of an isometric map that is not its Ground: in the Y-sorted nodes before the
## entities, sorted cell by cell with who walks there, blocking where its tiles block, moved by
## `offset` px.
static func _iso_layer(root: Node2D, nodes: Dictionary, layer_name: String, tile_set: TileSet, offset: Vector2) -> TileMapLayer:
	var ysorted: Node2D = nodes["YSorted"]
	var entities: Node2D = nodes["Entities"]
	var taken := {}
	for child in ysorted.get_children():
		taken[String(child.name)] = true
	var wanted := layer_name.validate_node_name()
	if wanted == "":
		wanted = "Layer"
	var candidate := wanted
	var n := 1
	while taken.has(candidate):
		n += 1
		candidate = "%s%d" % [wanted, n]
	var layer := TileMapLayer.new()
	layer.name = candidate
	layer.tile_set = tile_set
	layer.y_sort_enabled = true
	layer.collision_enabled = true
	layer.position = offset
	ysorted.add_child(layer)
	ysorted.move_child(layer, entities.get_index())
	layer.owner = root
	return layer
