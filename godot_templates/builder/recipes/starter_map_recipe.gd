extends RefCounted
## Seeds game/maps/starter_map.tscn once (user_seed ownership: never rewritten afterwards).

const RECIPE_VERSION := 1

const Paths := preload("../lib/paths.gd")
const SceneUtil := preload("../lib/scene_util.gd")

const OUT_PATH := "res://game/maps/starter_map.tscn"
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
const TILESET_PATH := "res://generated/tilesets/overworld.tres"
const MAP_SIZE := Vector2i(30, 20)

## Only listed while the file does not exist yet, so an existing (possibly edited) map is kept.
func outputs(_ctx) -> PackedStringArray:
	if FileAccess.file_exists(OUT_PATH):
		return PackedStringArray()
	return PackedStringArray([OUT_PATH])

func input_hash(ctx) -> String:
	var overworld := {}
	for def in ctx.catalog.tileset_defs():
		if def["name"] == "overworld":
			overworld = def
	return ctx.stable_hash({"v": RECIPE_VERSION, "overworld": overworld})

func build(ctx) -> Array:
	var issues: Array = []
	if FileAccess.file_exists(OUT_PATH):
		return issues
	var def := _overworld_def(ctx)
	if def.is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": "overworld"}, OUT_PATH))
		return issues
	var tile_set := load(TILESET_PATH) as TileSet
	var player_scene := load(PLAYER_SCENE) as PackedScene
	if tile_set == null:
		issues.append(ctx.make_issue("VAL-002", {"file": TILESET_PATH}, TILESET_PATH))
		return issues
	if player_scene == null:
		issues.append(ctx.make_issue("VAL-002", {"file": PLAYER_SCENE}, PLAYER_SCENE))
		return issues

	var ground_cell := _first_ground_tile(ctx, def, tile_set)
	var wall_cell := _first_wall_tile(ctx, def)
	var tile_size: Vector2i = ctx.vec2i(def["tile_size"])

	var root := Node2D.new()
	root.name = "StarterMap"
	var ground := TileMapLayer.new()
	ground.name = "Ground"
	ground.tile_set = tile_set
	root.add_child(ground)
	var ysorted := Node2D.new()
	ysorted.name = "YSorted"
	ysorted.y_sort_enabled = true
	root.add_child(ysorted)

	if not ground_cell.is_empty():
		for y in MAP_SIZE.y:
			for x in MAP_SIZE.x:
				var border := x == 0 or y == 0 or x == MAP_SIZE.x - 1 or y == MAP_SIZE.y - 1
				var cell: Dictionary = wall_cell if (border and not wall_cell.is_empty()) else ground_cell
				ground.set_cell(Vector2i(x, y), cell["source_id"], cell["coords"], 0)

	# GEN_EDIT_STATE_INSTANCE keeps the base scene state, so only real overrides (position) are saved.
	var player := player_scene.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE) as Node2D
	player.position = Vector2(15, 10) * Vector2(tile_size) + Vector2(tile_size) / 2.0
	ysorted.add_child(player)
	# Instanced scene: owner is the map root; its own children stay untouched.
	var err := SceneUtil.save_scene(root, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	return issues

func _overworld_def(ctx) -> Dictionary:
	for def in ctx.catalog.tileset_defs():
		if def["name"] == "overworld":
			return def
	return {}

func _sorted_sources(def: Dictionary) -> Array:
	var sources: Array = def.get("sources", []).duplicate()
	sources.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a["source_id"]) < int(b["source_id"]))
	return sources

## {source_id, coords} of the first tile of the first GROUND sheet, or {}.
func _first_ground_tile(ctx, def: Dictionary, tile_set: TileSet) -> Dictionary:
	for s in _sorted_sources(def):
		var asset: Dictionary = ctx.catalog.asset(s["asset"])
		if ctx.catalog.effective(asset).get("role", "") != "GROUND":
			continue
		var src := tile_set.get_source(int(s["source_id"])) as TileSetAtlasSource
		if src != null and src.get_tiles_count() > 0:
			return {"source_id": int(s["source_id"]), "coords": src.get_tile_id(0)}
	return {}

## {source_id, coords} of the first tile (row-major) whose override marks it as WALL
## (tile_overrides["x,y"].custom.role == "WALL"), or {} when no wall tile exists.
func _first_wall_tile(ctx, def: Dictionary) -> Dictionary:
	for s in _sorted_sources(def):
		var eff: Dictionary = ctx.catalog.effective(ctx.catalog.asset(s["asset"]))
		var best := {}
		for key in eff.get("tile_overrides", {}).keys():
			var ov: Dictionary = eff["tile_overrides"][key]
			if ov.get("custom", {}).get("role", "") != "WALL":
				continue
			var parts := String(key).split(",")
			var coords := Vector2i(int(parts[0]), int(parts[1]))
			if best.is_empty() or (coords.y < best["coords"].y) or (coords.y == best["coords"].y and coords.x < best["coords"].x):
				best = {"source_id": int(s["source_id"]), "coords": coords}
		if not best.is_empty():
			return best
	return {}
