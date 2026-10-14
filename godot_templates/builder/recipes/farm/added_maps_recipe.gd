extends RefCounted
## The maps added to a farm (T17.23): a forest and a beach, each a map of its own, built from
## the stored plan (`rpggen/world_plan.json`, the list `farm.map.added`, planned by
## rpggen/core/added_map_plan.py), and the farm's side of the doors to them.
##
## * game/maps/<id>.tscn for every entry of the plan (`farm_map_1`, `farm_map_2`, ...), **once**
##   (user_seed ownership): a map that exists is never built again, and a row that is added
##   later builds one more map and touches no other. On it, whatever its kind: the layers of a
##   top-down map with the `Soil` layer and the `Field` (so the tools work there: the axe and the
##   sickle clear what the plan lays down, and the rod is cast at cells whose tile says `water`),
##   the edge with the one gap that is the way back to the farm (the door `to_farm`, the spawn
##   `from_farm`), trees, scenery and things to clear as the farm has them
##   (farm_map_recipe.gd's own: the packs' pictures by their words, else drawn), and the places
##   where things to forage lie (`Forage/Spot1` ...). Its root says what it is with the metadata
##   `farm_kind` (RpgForage.KIND_META: a beach has things of its own), and the map is no
##   interior: the weather, the seasons and the light of the day are the farm's.
##   - a **forest** (`kind`): the ground of the farm under a shade (`Shade`), a path to its
##     clearing;
##   - a **beach**: sand (the packs' ground tile the plan names, else drawn: `Sand`), the sea
##     along one side (the packs' water tile, else the drawn water of the `Soil` layer; its
##     cells carry the `water` data, and the root says `farm_water`: `sea`, RpgFishing.WATER_META,
##     so the fish of the sea bite there), `Markers/FishFrom` where the rod is cast from.
## * generated/scenes/farm/trails.tscn, **on every build**: the farm's side of every door pair.
##   The farm's map instances this scene once, when it is built (`Trails`, farm_map_recipe.gd),
##   and is never written again; what the scene holds grows with the plan: for every added map
##   the door `to_<id>` on the cell of the trail the plan gave it (`farm.map.trails`: beside the
##   edge of the farm, set aside when the farm was planned), the spawn `from_<id>` one cell
##   further in, and a worn patch of ground with an arrow (`Mark_<id>`) so that the door can be
##   seen. A farm without added maps has the scene with nothing in it.
##
## **Squares or diamonds.** Everything goes through the seam of the map recipes
## (builder/lib/map_geo.gd), as the farm's map does: the same plan is painted with square tiles
## or with the project's diamonds.
##
## **What T17.24 finds here.** `build_map` is one function for every kind; what a kind has of
## its own is in `_add_ground` (the `match` on the kind) and nowhere else. A cave adds its
## branch there (and its enemies after `_add_common`); nothing of the trails changes.

const RECIPE_VERSION := 1
## The version of what the recipe does for an isometric project only: in the hash of such a
## project and of no other.
const ISO_VERSION := 1

const JsonUtil := preload("../../lib/json_util.gd")
const SceneUtil := preload("../../lib/scene_util.gd")
const MapUtil := preload("../../lib/map_util.gd")
const MapBuild := preload("../../lib/map_build.gd")
const MapGeo := preload("../../lib/map_geo.gd")
const ObjectEntries := preload("../../lib/object_entries.gd")
const BuildContext := preload("../../lib/build_context.gd")
const FarmBuild := preload("farm_build.gd")
const FieldRecipe := preload("field_recipe.gd")
const FarmMapRecipe := preload("farm_map_recipe.gd")

const TRAILS_SCENE := FarmBuild.TRAILS_SCENE
const TRAILS_NODE := FarmBuild.TRAILS_NODE
const FARM_PATH := "res://game/maps/farm.tscn"
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
## The door pair of an added map: its way back is the door `to_farm` and leads to the farm's
## spawn `from_<id>`; the farm's door `to_<id>` leads to its spawn `from_farm`.
const BACK_DOOR := "to_farm"
const FROM_FARM := "from_farm"
const KIND_META := &"farm_kind"
const WATER_META := &"farm_water"
const FOREST := "forest"
const BEACH := "beach"

const SAND := Color(0.89, 0.82, 0.59)
const SAND_DARK := Color(0.86, 0.79, 0.56)
const SHADE := Color(0.05, 0.2, 0.08, 0.3)
const TRAIL := Color(0.62, 0.5, 0.33)
const TRAIL_ARROW := Color(0.93, 0.87, 0.7)

# ---------------------------------------------------------------- the plan

## The added maps of the stored plan (`farm.map.added`), in its order.
static func entries() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in JsonUtil.to_array(FarmMapRecipe.plan().get("added", [])):
		out.append(JsonUtil.to_dict(raw))
	return out

## The trails of the stored plan (`farm.map.trails`), in its order.
static func trails() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in JsonUtil.to_array(FarmMapRecipe.plan().get("trails", [])):
		out.append(JsonUtil.to_dict(raw))
	return out

static func map_id(entry: Dictionary) -> String:
	return JsonUtil.to_str(entry.get("id", ""))

static func map_path(entry: Dictionary) -> String:
	return "res://" + JsonUtil.to_str(entry.get("map", ""))

## The door of the farm that leads to an added map, and the spawn the farmer comes back to.
static func door_name(entry: Dictionary) -> String:
	return "to_" + map_id(entry)

static func spawn_name(entry: Dictionary) -> String:
	return "from_" + map_id(entry)

## The trail of the farm an added map uses, or {} when the plan gave it none.
static func trail_of(entry: Dictionary, found: Array[Dictionary]) -> Dictionary:
	var at := JsonUtil.to_int(entry.get("trail", -1), -1)
	return found[at] if at >= 0 and at < found.size() else {}

## The cells of the sea of an entry that touch the land (to the four sides): what keeps the
## farmer out of the water. The rest of the sea is behind them.
static func shore_cells(water: Array[Vector2i], size: Vector2i) -> Array[Vector2i]:
	var wet := {}
	for cell in water:
		wet[cell] = true
	var out: Array[Vector2i] = []
	for cell in water:
		for step: Vector2i in [Vector2i.UP, Vector2i.LEFT, Vector2i.RIGHT, Vector2i.DOWN]:
			var beside := cell + step
			var inside := beside.x >= 0 and beside.y >= 0 and beside.x < size.x and beside.y < size.y
			if inside and not wet.has(beside):
				out.append(cell)
				break
	return out

## The cells of the inside of a map of `size` cells that are not in `without`, as runs along a
## row: [Rect2i] one row high, row by row. What a drawn ground is laid as.
static func row_runs(size: Vector2i, without: Array[Vector2i]) -> Array[Rect2i]:
	var skip := {}
	for cell in without:
		skip[cell] = true
	var out: Array[Rect2i] = []
	for y in range(1, size.y - 1):
		var start := -1
		for x in range(1, size.x):
			var open := x < size.x - 1 and not skip.has(Vector2i(x, y))
			if open and start < 0:
				start = x
			elif not open and start >= 0:
				out.append(Rect2i(start, y, x - start, 1))
				start = -1
	return out

# ---------------------------------------------------------------- the recipe

## The trails' scene on every build, and only the maps that do not exist yet.
func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([TRAILS_SCENE])
	for entry in entries():
		if not FileAccess.file_exists(map_path(entry)):
			out.append(map_path(entry))
	return out

func input_hash(ctx: BuildContext) -> String:
	var hashed := {
		"v": RECIPE_VERSION,
		"added": entries(),
		"trails": trails(),
		"overworld": ctx.catalog.tileset_def("overworld"),
		"layers": ctx.config.get("map_layers", []),
		"ground": JsonUtil.to_str(ctx.section("starter_map").get("ground", "")),
		"music": JsonUtil.to_str(ctx.section("sounds").get("music_map", "")),
		"entries": ObjectEntries.entries(ctx),
		"field": FieldRecipe.RECIPE_VERSION,
	}
	if MapGeo.is_isometric(ctx):
		hashed["iso"] = MapGeo.new(ctx).def
		hashed["iso_v"] = ISO_VERSION
	return ctx.stable_hash(hashed)

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var geo := MapGeo.new(ctx)
	var err := SceneUtil.save_scene(trails_root(geo), TRAILS_SCENE)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": TRAILS_SCENE, "err": err}, TRAILS_SCENE))
	for entry in entries():
		var path := map_path(entry)
		if FileAccess.file_exists(path):
			continue
		var root := build_map(ctx, entry, issues)
		if root == null:
			continue
		err = SceneUtil.save_scene(root, path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	return issues

# ---------------------------------------------------------------- the farm's side

## The scene the farm's map instances: for every added map of the plan its door, the spawn the
## farmer comes back to, and the mark on the ground. Not yet saved.
static func trails_root(geo: MapGeo) -> Node2D:
	var root := Node2D.new()
	root.name = TRAILS_NODE
	var found := trails()
	for entry in entries():
		var trail := trail_of(entry, found)
		if trail.is_empty():
			continue
		var cell := FarmMapRecipe.cell_of(trail.get("cell"))
		var arrive := FarmMapRecipe.cell_of(trail.get("spawn"))
		var mark := trail_mark(geo, cell - arrive)
		mark.position = geo.center(cell)
		SceneUtil.add(root, mark, root, "Mark_" + map_id(entry))
		geo.add_exit_door(root, root, door_name(entry), cell, map_path(entry), StringName(FROM_FARM))
		MapUtil.add_marker(root, root, spawn_name(entry), geo.center(arrive), true, JsonUtil.to_str(trail.get("facing", "down")))
	return root

## The mark of a trail, the middle of its cell at the origin: a worn patch of the shape of the
## cell, and an arrow that points the way out (`outward`: one step in cells). It lies flat on
## the ground, under whoever walks over it.
static func trail_mark(geo: MapGeo, outward: Vector2i) -> Node2D:
	var mark := Node2D.new()
	var patch := Polygon2D.new()
	patch.name = "Patch"
	patch.color = TRAIL
	var corners := geo.cells_outline(Rect2i(0, 0, 1, 1))
	var middle := geo.center(Vector2i.ZERO)
	var shape := PackedVector2Array()
	for corner in corners:
		shape.append((corner - middle) * 0.9)
	patch.polygon = shape
	mark.add_child(patch)
	var ahead := geo.step(Vector2(outward))
	var across := geo.step(Vector2(-outward.y, outward.x))
	var arrow := Polygon2D.new()
	arrow.name = "Arrow"
	arrow.color = TRAIL_ARROW
	arrow.polygon = PackedVector2Array([ahead * 0.34, ahead * -0.12 + across * 0.26, ahead * -0.12 - across * 0.26])
	mark.add_child(arrow)
	return mark

# ---------------------------------------------------------------- an added map

## One added map of the plan as the nodes of its scene, not yet saved; null, with an issue, when
## the project lacks what it is built from.
func build_map(ctx: BuildContext, entry: Dictionary, issues: Array) -> Node2D:
	var path := map_path(entry)
	var geo := MapGeo.new(ctx)
	if geo.def.is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": "overworld"}, path))
		return null
	var tile_set := geo.load_tile_set()
	if tile_set == null:
		issues.append(ctx.make_issue("VAL-002", {"file": geo.tileset_path()}, geo.tileset_path()))
		return null
	if not ResourceLoader.exists(PLAYER_SCENE):
		issues.append(ctx.make_issue("VAL-002", {"file": PLAYER_SCENE}, PLAYER_SCENE))
		return null
	var id := map_id(entry)
	var kind := JsonUtil.to_str(entry.get("kind", FOREST))
	var size := FarmMapRecipe.cell_of(entry.get("size"))
	var root := MapUtil.new_map_root(id.capitalize().replace(" ", ""), id)
	root.set("display_name", JsonUtil.to_str(entry.get("name", id)))
	root.set("music_asset_id", JsonUtil.to_str(ctx.section("sounds").get("music_map", "")))
	root.set_meta(KIND_META, kind)
	var layer_names: Array = ctx.config.get("map_layers", MapUtil.DEFAULT_LAYERS)
	var nodes := MapUtil.build_layers(root, layer_names, tile_set)
	var entities: Node2D = nodes["Entities"]
	var spawns: Node2D = nodes["SpawnPoints"]
	var triggers: Node2D = nodes["Triggers"]
	var door := JsonUtil.to_dict(entry.get("door", {}))
	var gap := FarmMapRecipe.cell_of(door.get("cell"))
	var arrive := FarmMapRecipe.cell_of(door.get("spawn"))
	var water := FarmMapRecipe.cells_of(JsonUtil.to_dict(entry.get("water", {})).get("cells"))

	var water_tile := _add_ground(ctx, entry, kind, root, nodes, geo, water)
	# the edge, open at the way in and where the sea is
	var skip: Array[Vector2i] = [gap]
	skip.append_array(water)
	geo.paint_walls(root, nodes, size, skip)
	for note in geo.take_notes():
		print("[rpggen] INFO added_maps (%s): %s" % [id, note])

	# the field: nothing can be tilled here, and the cells of the sea say `water`
	var soil := FieldRecipe.add_field(root, nodes)
	if soil == null:
		issues.append(ctx.make_issue("VAL-002", {"file": FarmBuild.SOIL_TILESET}, FarmBuild.SOIL_TILESET))
		root.free()
		return null
	# a sea without a water tile of the packs is drawn; the packs' own shows through
	var water_mark := FieldRecipe.WATER_MARK if not water_tile.is_empty() else FieldRecipe.WATER_TILE
	for cell in water:
		soil.set_cell(cell, FieldRecipe.SOURCE_ID, water_mark)
	_add_common(ctx, entry, id, root, nodes, geo, water, size)

	MapUtil.add_marker(spawns, root, FROM_FARM, geo.center(arrive), true, JsonUtil.to_str(door.get("facing", "down")))
	MapUtil.add_marker(spawns, root, "default", geo.center(arrive), true, JsonUtil.to_str(door.get("facing", "down")))
	geo.add_exit_door(triggers, root, BACK_DOOR, gap, FARM_PATH, StringName(spawn_name(entry)))
	MapUtil.place(PLAYER_SCENE, entities, root, geo.center(arrive))
	return root

## The ground of a kind, the path on it and the water. Returns the packs' water tile the sea
## was painted with, or {} (no sea, or a sea that the `Soil` layer draws).
func _add_ground(ctx: BuildContext, entry: Dictionary, kind: String, root: Node2D, nodes: Dictionary, geo: MapGeo, water: Array[Vector2i]) -> Dictionary:
	var size := FarmMapRecipe.cell_of(entry.get("size"))
	var ground: TileMapLayer = nodes["Ground"]
	var base := _farm_ground(ctx, geo)
	var own := geo.tile_of_asset(JsonUtil.to_str(entry.get("ground", ""))) if JsonUtil.to_str(entry.get("ground", "")) != "" else {}
	MapBuild.fill_ground(ground, size, own if not own.is_empty() else base)
	var details := geo.road_layer(nodes)
	if details != null:
		geo.paint_joined(details, FarmMapRecipe.cells_of(entry.get("paths")), "ROAD", geo.find_tile("ROAD"))
	var water_tile := {}
	match kind:
		BEACH:
			root.set_meta(WATER_META, "sea")
			water_tile = geo.find_tile("WATER")
			if not water_tile.is_empty():
				geo.paint_joined(ground, water, "WATER", water_tile)
			if own.is_empty():
				# no sand of the packs: drawn over the ground, row by row, wherever the sea is not
				_add_cover(root, ground, geo, "Sand", row_runs(size, water), SAND, SAND_DARK)
		FOREST:
			if own.is_empty():
				# the floor of a wood is the farm's ground in the shade of its trees
				_add_cover(root, ground, geo, "Shade", row_runs(size, []), SHADE, SHADE)
	return water_tile

## The ground tile of the farm (farm_map_recipe.gd chooses the same).
func _farm_ground(ctx: BuildContext, geo: MapGeo) -> Dictionary:
	var wanted := JsonUtil.to_str(ctx.section("starter_map").get("ground", ""))
	if wanted == "":
		wanted = JsonUtil.to_str(ctx.section("starter").get("ground", ""))
	if wanted != "":
		var tile := geo.tile_of_asset(wanted)
		if not tile.is_empty():
			return tile
	return geo.find_tile("GROUND")

## A drawn ground over the tiles of the ground and under everything else: one polygon a run of
## cells (`runs`, a row high each), every second row in the second colour so that it does not
## lie there as one flat sheet.
static func _add_cover(root: Node2D, ground: TileMapLayer, geo: MapGeo, node_name: String, runs: Array[Rect2i], first: Color, second: Color) -> void:
	var cover := Node2D.new()
	cover.name = node_name
	root.add_child(cover)
	root.move_child(cover, ground.get_index() + 1)
	for i in runs.size():
		var run := runs[i]
		var strip := Polygon2D.new()
		strip.name = "Row_%d_%d" % [run.position.y, run.position.x]
		strip.polygon = geo.cells_outline(run)
		strip.color = first if run.position.y % 2 == 0 else second
		cover.add_child(strip)

## What every kind has: what blocks the way into the sea, the trees, the scenery and the things
## to clear, the places to forage, the markers.
func _add_common(ctx: BuildContext, entry: Dictionary, id: String, root: Node2D, nodes: Dictionary, geo: MapGeo, water: Array[Vector2i], size: Vector2i) -> void:
	var entities: Node2D = nodes["Entities"]
	if not water.is_empty():
		var sea := StaticBody2D.new()
		sea.collision_layer = 0
		sea.collision_mask = 0
		sea.set_collision_layer_value(1, true)  # world
		SceneUtil.add(root, sea, root, "Sea")
		var shape_of_cell := geo.cell_shape()  # one shape for every cell
		for cell in shore_cells(water, size):
			var shape := CollisionShape2D.new()
			shape.name = "Cell_%d_%d" % [cell.x, cell.y]
			shape.shape = shape_of_cell
			shape.position = geo.center(cell)
			sea.add_child(shape)
	FarmMapRecipe.new().add_things(entry, root, entities, geo, ObjectEntries.entries(ctx), id)
	var spots := FarmMapRecipe.cells_of(entry.get("spots"))
	if not spots.is_empty():
		var holder := Node2D.new()
		SceneUtil.add(root, holder, root, "Forage")
		for i in spots.size():
			MapUtil.add_marker(holder, root, "Spot%d" % (i + 1), geo.center(spots[i]))
	var markers := Node2D.new()
	SceneUtil.add(root, markers, root, "Markers")
	var fish := JsonUtil.to_dict(entry.get("fish", {}))
	if not fish.is_empty():
		MapUtil.add_marker(markers, root, "FishFrom", geo.center(FarmMapRecipe.cell_of(fish.get("from"))))
		MapUtil.add_marker(markers, root, "FishAt", geo.center(FarmMapRecipe.cell_of(fish.get("at"))))
	var clearing := FarmMapRecipe.rect_of(entry.get("clearing"))
	if clearing.size != Vector2i.ZERO:
		var middle := clearing.position + clearing.size / 2
		MapUtil.add_marker(markers, root, "Clearing", geo.center(middle))
