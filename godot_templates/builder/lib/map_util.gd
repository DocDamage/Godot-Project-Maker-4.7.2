extends RefCounted
## Helpers shared by the map recipes (starter map and interior).

const SceneUtil := preload("scene_util.gd")

const DEFAULT_LAYERS := ["Ground", "GroundDetails", "Walls", "Props", "Overhead"]
const COLLIDING_LAYERS := ["Walls", "Props"]
const SPAWN_SCRIPT := "res://addons/rpg_runtime/world/spawn_point.gd"
const MAP_ROOT_SCRIPT := "res://addons/rpg_runtime/world/map_root.gd"
const DOOR_SCRIPT := "res://addons/rpg_runtime/world/door.gd"

static func _layer(layer_name: String, tile_set: TileSet) -> TileMapLayer:
	var layer := TileMapLayer.new()
	layer.name = layer_name
	layer.tile_set = tile_set
	layer.collision_enabled = COLLIDING_LAYERS.has(layer_name)
	return layer

## Creates the map skeleton under `root` (T4.05) and returns the important nodes by name:
## every TileMapLayer, plus "YSorted", "Entities", "Triggers" and "SpawnPoints".
##   Ground, GroundDetails, Walls, <other configured layers>, YSorted(Props, Entities),
##   Overhead, Triggers, SpawnPoints
static func build_layers(root: Node2D, layer_names: Array, tile_set: TileSet) -> Dictionary:
	var nodes := {}
	var wanted: Array = layer_names.duplicate()
	if not wanted.has("Ground"):
		wanted.push_front("Ground")
	for structural in ["Ground", "GroundDetails", "Walls"]:
		if wanted.has(structural):
			nodes[structural] = _layer(structural, tile_set)
			root.add_child(nodes[structural])
	for extra in wanted:
		if not DEFAULT_LAYERS.has(extra):
			nodes[extra] = _layer(extra, tile_set)
			root.add_child(nodes[extra])
	var ysorted := Node2D.new()
	ysorted.name = "YSorted"
	ysorted.y_sort_enabled = true
	root.add_child(ysorted)
	nodes["YSorted"] = ysorted
	if wanted.has("Props"):
		var props := _layer("Props", tile_set)
		props.y_sort_enabled = true
		ysorted.add_child(props)
		nodes["Props"] = props
	var entities := Node2D.new()
	entities.name = "Entities"
	entities.y_sort_enabled = true
	ysorted.add_child(entities)
	nodes["Entities"] = entities
	if wanted.has("Overhead"):
		var overhead := _layer("Overhead", tile_set)
		overhead.z_index = 10
		root.add_child(overhead)
		nodes["Overhead"] = overhead
	var triggers := Node2D.new()
	triggers.name = "Triggers"
	root.add_child(triggers)
	nodes["Triggers"] = triggers
	var spawns := Node2D.new()
	spawns.name = "SpawnPoints"
	root.add_child(spawns)
	nodes["SpawnPoints"] = spawns
	return nodes

## A map root: Node2D with map_root.gd and its map id.
static func new_map_root(root_name: String, map_id: String) -> Node2D:
	var root := Node2D.new()
	root.name = root_name
	SceneUtil.attach_script(root, MAP_ROOT_SCRIPT)
	root.set("map_id", StringName(map_id))
	return root

# ---------------------------------------------------------------- painting

static func fill(layer: TileMapLayer, rect: Rect2i, tile: Dictionary) -> void:
	if tile.is_empty():
		return
	for y in range(rect.position.y, rect.end.y):
		for x in range(rect.position.x, rect.end.x):
			layer.set_cell(Vector2i(x, y), tile["source_id"], tile["coords"], 0)

## One-tile border of `rect`; cells listed in `skip` stay empty (e.g. a doorway).
static func border(layer: TileMapLayer, rect: Rect2i, tile: Dictionary, skip: Array = []) -> void:
	if tile.is_empty():
		return
	for y in range(rect.position.y, rect.end.y):
		for x in range(rect.position.x, rect.end.x):
			var on_edge := x == rect.position.x or y == rect.position.y or x == rect.end.x - 1 or y == rect.end.y - 1
			if on_edge and not skip.has(Vector2i(x, y)):
				layer.set_cell(Vector2i(x, y), tile["source_id"], tile["coords"], 0)

## Four invisible collision rectangles along the edge of a `size`-tile map, for maps without a
## WALL tile. Cells in `skip` are left open.
static func border_collision(root: Node2D, size: Vector2i, tile_px: int, skip: Array = []) -> StaticBody2D:
	var body := StaticBody2D.new()
	body.name = "BorderCollision"
	body.collision_layer = 0
	body.collision_mask = 0
	body.set_collision_layer_value(1, true)
	root.add_child(body)
	body.owner = root
	var rects: Array = []
	for x in size.x:
		for y in [0, size.y - 1]:
			rects.append(Vector2i(x, y))
	for y in range(1, size.y - 1):
		for x in [0, size.x - 1]:
			rects.append(Vector2i(x, y))
	for cell in rects:
		if skip.has(cell):
			continue
		var shape := CollisionShape2D.new()
		shape.name = "Wall_%d_%d" % [cell.x, cell.y]
		var rect := RectangleShape2D.new()
		rect.size = Vector2(tile_px, tile_px)
		shape.shape = rect
		shape.position = Vector2(cell) * tile_px + Vector2(tile_px, tile_px) / 2.0
		body.add_child(shape)
		shape.owner = root
	return body

# ---------------------------------------------------------------- finding tiles

static func _sorted_sources(def: Dictionary) -> Array:
	var sources: Array = def.get("sources", []).duplicate()
	sources.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a["source_id"]) < int(b["source_id"]))
	return sources

## {source_id, coords} of the first tile of the first asset with `role` in the tile set, or {}.
static func find_tile(ctx, def: Dictionary, tile_set: TileSet, role: String) -> Dictionary:
	for s in _sorted_sources(def):
		var asset: Dictionary = ctx.catalog.asset(s["asset"])
		if asset.is_empty() or ctx.catalog.effective(asset).get("role", "") != role:
			continue
		var tile := first_tile(tile_set, int(s["source_id"]))
		if not tile.is_empty():
			return tile
	return {}

## {source_id, coords} of the first tile of the tile sheet `asset_id`, or {}.
static func tile_of_asset(ctx, def: Dictionary, tile_set: TileSet, asset_id: String) -> Dictionary:
	for s in _sorted_sources(def):
		if s["asset"] == asset_id:
			return first_tile(tile_set, int(s["source_id"]))
	return {}

static func first_tile(tile_set: TileSet, source_id: int) -> Dictionary:
	var src := tile_set.get_source(source_id) as TileSetAtlasSource
	if src != null and src.get_tiles_count() > 0:
		return {"source_id": source_id, "coords": src.get_tile_id(0)}
	return {}

## Up to `count` other tiles of the same source (not `base`), in tile order.
static func other_tiles(tile_set: TileSet, base: Dictionary, count: int) -> Array:
	var out: Array = []
	var src := tile_set.get_source(int(base["source_id"])) as TileSetAtlasSource
	if src == null:
		return out
	for i in src.get_tiles_count():
		var coords := src.get_tile_id(i)
		if coords != base["coords"]:
			out.append({"source_id": base["source_id"], "coords": coords})
			if out.size() >= count:
				break
	return out

## The first tile (row-major) a catalog override marks as WALL (`custom.role == "WALL"`): the way
## hand-annotated packs mark wall tiles inside a ground sheet.
static func override_wall_tile(ctx, def: Dictionary) -> Dictionary:
	for s in _sorted_sources(def):
		var eff: Dictionary = ctx.catalog.effective(ctx.catalog.asset(s["asset"]))
		var best := {}
		for key in eff.get("tile_overrides", {}).keys():
			var ov: Dictionary = eff["tile_overrides"][key]
			if ov.get("custom", {}).get("role", "") != "WALL":
				continue
			var parts := String(key).split(",")
			var coords := Vector2i(int(parts[0]), int(parts[1]))
			if best.is_empty() or coords.y < best["coords"].y or (coords.y == best["coords"].y and coords.x < best["coords"].x):
				best = {"source_id": int(s["source_id"]), "coords": coords}
		if not best.is_empty():
			return best
	return {}

static func wall_tile(ctx, def: Dictionary, tile_set: TileSet) -> Dictionary:
	var tile := find_tile(ctx, def, tile_set, "WALL")
	return tile if not tile.is_empty() else override_wall_tile(ctx, def)

# ---------------------------------------------------------------- placing

## Instances `scene_path` under `parent` at `pos` (map-local pixels) and returns it, or null.
## The instance keeps the base-scene state, so only real overrides (position) are saved.
static func place(scene_path: String, parent: Node, root: Node, pos: Vector2, node_name: String = "") -> Node2D:
	var inst := SceneUtil.instance(scene_path) as Node2D
	if inst == null:
		return null
	if node_name != "":
		inst.name = node_name
	inst.position = pos
	parent.add_child(inst)
	inst.owner = root
	return inst

static func add_marker(parent: Node, root: Node, marker_name: String, pos: Vector2, spawn: bool = false, facing: String = "down") -> Marker2D:
	var marker := Marker2D.new()
	marker.name = marker_name
	if spawn:
		SceneUtil.attach_script(marker, SPAWN_SCRIPT)
		marker.set("spawn_id", StringName(marker_name))
		marker.set("facing", facing)
	marker.position = pos
	parent.add_child(marker)
	marker.owner = root
	return marker

## Tile -> map-local pixel position of the tile's center.
static func tile_center(tile_pos: Vector2i, tile_px: int) -> Vector2:
	return Vector2(tile_pos) * tile_px + Vector2(tile_px, tile_px) / 2.0
