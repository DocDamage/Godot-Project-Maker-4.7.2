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

const RECIPE_VERSION := 1

const Paths := preload("../lib/paths.gd")
const JsonUtil := preload("../lib/json_util.gd")
const SceneUtil := preload("../lib/scene_util.gd")
const MapUtil := preload("../lib/map_util.gd")
const MapBuild := preload("../lib/map_build.gd")
const BuildContext := preload("../lib/build_context.gd")

const OUT_DIR := "res://game/maps/imported/"
const STARTER_PATH := "res://game/maps/starter_map.tscn"
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
const DEFAULT_TILESET := "overworld"

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
		if include.has(map_id) and map_id != starter:
			out.append(m)
	return out

## The catalog map that becomes the starter map, or {}.
static func starter_map(ctx: BuildContext) -> Dictionary:
	var starter := JsonUtil.to_str(selection(ctx)["starter"])
	if starter == "":
		return {}
	return ctx.catalog.map_def(starter)

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
		if map_id != starter and not include.has(map_id):
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
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"maps": extra_maps(ctx),
		"selection": selection(ctx),
		"layers": ctx.config.get("map_layers", []),
		"tilesets": ctx.catalog.tileset_defs(),
	})

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
