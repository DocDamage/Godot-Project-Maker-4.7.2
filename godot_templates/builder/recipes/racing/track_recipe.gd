extends RefCounted
## The first track of a racing game (generated/scenes/stages/stage_01.tscn) and the lists of
## the tracks. A track is an arcade stage that does not scroll: a field of grass, the road
## painted with the road tiles of the packs (the layer "Ground"), what every cell is made of
## (RpgTrackSurfaces), barriers round the field and in its middle, the car at the start and the
## race camera. Until the track plan (T16.13) this is one flat test track: a ring of road.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const MapUtil := preload("../../lib/map_util.gd")
const Paths := preload("../../lib/paths.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const StageRecipes := preload("../arcade/stage_recipes.gd")
const RaceBuild := preload("racing_build.gd")

const GRASS := Color(0.3, 0.59, 0.27)
const BARRIER := Color(0.78, 0.16, 0.16)
const ROAD := Color(0.27, 0.27, 0.31)

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([ArcadeBuild.stage_path(0), ArcadeBuild.PLANNED_STAGES_PATH])
	if not FileAccess.file_exists(ArcadeBuild.STAGES_PATH):
		out.append(ArcadeBuild.STAGES_PATH)
	return out

func input_hash(ctx: BuildContext) -> String:
	var def := tileset_def(ctx)
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"tracks": plan(),
		"tileset": def.get("name", ""),
		"sources": def.get("sources", []),
		"road": RaceBuild.road_asset(ctx).get("id", ""),
		"view": ArcadeBuild.view(ctx),
		"fixed": RaceBuild.fixed_camera(ctx),
	})

static func tileset_def(ctx: BuildContext) -> Dictionary:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return def

## The tracks of the game as stages.json has them: one, which ends when its race says so.
static func plan() -> Array:
	return [{
		"title": "",
		"axis": "none",
		"speed": 0.0,
		"length": 0.0,
		"exit": "custom",
		"par_time_s": 60.0,
		"waves": [],
	}]

## What every cell of the test track is made of: rows of `r` (road) and `g` (grass), a ring of
## road `RaceBuild.ROAD_WIDTH` wide, `RaceBuild.TRACK_MARGIN` cells in from the edge.
static func test_rows(cells: Vector2i = RaceBuild.TRACK_CELLS) -> PackedStringArray:
	var outer := Rect2i(Vector2i.ONE * RaceBuild.TRACK_MARGIN, cells - Vector2i.ONE * RaceBuild.TRACK_MARGIN * 2)
	var inner := outer.grow(-RaceBuild.ROAD_WIDTH)
	var rows := PackedStringArray()
	for y in cells.y:
		var row := ""
		for x in cells.x:
			var at := Vector2i(x, y)
			row += "r" if outer.has_point(at) and not inner.has_point(at) else "g"
		rows.append(row)
	return rows

## The barriers of the test track, in cells: the four edges of the field and a block in the
## middle of the ring (so that the grass inside can be driven on, and not all of it).
static func test_barriers(cells: Vector2i = RaceBuild.TRACK_CELLS) -> Array[Rect2i]:
	var island := Rect2i(Vector2i.ONE * RaceBuild.TRACK_MARGIN, cells - Vector2i.ONE * RaceBuild.TRACK_MARGIN * 2).grow(-(RaceBuild.ROAD_WIDTH + 3))
	return [
		Rect2i(0, 0, cells.x, 1),
		Rect2i(0, cells.y - 1, cells.x, 1),
		Rect2i(0, 0, 1, cells.y),
		Rect2i(cells.x - 1, 0, 1, cells.y),
		island,
	]

## Where the car starts on the test track (px) and the way it points: in the middle of the
## left straight, heading up.
static func test_start(tile: int, cells: Vector2i = RaceBuild.TRACK_CELLS) -> Vector2:
	return Vector2((RaceBuild.TRACK_MARGIN + RaceBuild.ROAD_WIDTH * 0.5) * tile, cells.y * 0.5 * tile)

static func _rect(node_name: String, area: Rect2, color: Color) -> Polygon2D:
	var shape := Polygon2D.new()
	shape.name = node_name
	shape.color = color
	shape.polygon = PackedVector2Array([area.position, Vector2(area.end.x, area.position.y), area.end, Vector2(area.position.x, area.end.y)])
	return shape

## The scene of a track. `rows` say what every cell is made of, `barriers` are rectangles of
## cells, `start` is where the car stands (px); `road` is the tile the road is painted with
## ({}: the road is drawn).
static func build_track(index: int, stage: Dictionary, view: Vector2i, tile: int, rows: PackedStringArray, barriers: Array[Rect2i],
		start: Vector2, tile_set: TileSet, road: Dictionary, car_scene: PackedScene, fixed_camera: bool = false) -> Node2D:
	var root := StageRecipes.build_stage(index, stage, view, start)
	var cells := Vector2i(rows[0].length() if not rows.is_empty() else 0, rows.size())
	var field := Rect2(Vector2.ZERO, Vector2(cells) * tile)
	var grass := _rect("Field", field, GRASS)
	grass.z_index = -10
	SceneUtil.add(root, grass, root, "Field")
	root.move_child(grass, 0)
	var ground := TileMapLayer.new()
	ground.tile_set = tile_set
	ground.collision_enabled = false
	ground.z_index = -5
	SceneUtil.add(root, ground, root, "Ground")
	root.move_child(ground, 1)
	var painted := not road.is_empty() and tile_set != null
	var drawn := Node2D.new()
	drawn.z_index = -6
	for y in cells.y:
		var from := -1  # where a run of road began in this row, when the road is drawn
		for x in cells.x + 1:
			var is_road := x < cells.x and rows[y][x] != "g" and rows[y][x] != "."
			if is_road and painted:
				MapUtil.put(ground, Vector2i(x, y), road)
			elif is_road and from < 0:
				from = x
			elif not is_road and from >= 0:
				drawn.add_child(_rect("Road_%d_%d" % [from, y], Rect2(Vector2(from, y) * tile, Vector2((x - from) * tile, tile)), ROAD))
				from = -1
	if drawn.get_child_count() > 0:
		SceneUtil.add(root, drawn, root, "Road")
		root.move_child(drawn, 1)
		SceneUtil.set_owner_recursive(drawn, root)
	else:
		drawn.free()
	var surfaces := Node2D.new()
	SceneUtil.attach_script(surfaces, RaceBuild.SURFACES_SCRIPT)
	surfaces.set("cell", float(tile))
	surfaces.set("rows", rows)
	SceneUtil.add(root, surfaces, root, "Surfaces")
	var walls := StaticBody2D.new()
	walls.collision_layer = 1 << (RaceBuild.WORLD_LAYER - 1)
	walls.collision_mask = 0
	SceneUtil.add(root, walls, root, "Barriers")
	for i in barriers.size():
		var area := Rect2(Vector2(barriers[i].position) * tile, Vector2(barriers[i].size) * tile)
		var shape := CollisionShape2D.new()
		var box := RectangleShape2D.new()
		box.size = area.size
		shape.shape = box
		shape.position = area.get_center()
		SceneUtil.add(walls, shape, root, "Shape%d" % i)
		SceneUtil.add(walls, _rect("Wall%d" % i, area, BARRIER), root, "Wall%d" % i)
	# the stage's camera is the race camera, and the scroller leaves it alone
	var camera := root.get_node("Camera") as Camera2D
	SceneUtil.attach_script(camera, RaceBuild.CAMERA_SCRIPT)
	camera.set("target_path", NodePath("../Car"))
	camera.set("view", Vector2(view))
	camera.set("track", field)
	camera.set("fixed", fixed_camera)
	camera.position = field.get_center() if fixed_camera else start
	root.get_node("Scroller").set("camera_path", NodePath(""))
	if car_scene != null:
		var car := car_scene.instantiate() as Node2D
		if car != null:
			car.position = start
			SceneUtil.add(root, car, root, "Car")
	return root

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var tracks := plan()
	var path := ArcadeBuild.stage_path(0)
	var tile := ArcadeBuild.tile(ctx)
	var def := tileset_def(ctx)
	var tile_set: TileSet = null
	var road := {}
	if not def.is_empty():
		tile_set = load(Paths.TILESETS_DIR + "%s.tres" % def["name"]) as TileSet
		var asset := RaceBuild.road_asset(ctx)
		if tile_set != null and not asset.is_empty():
			road = MapUtil.tile_of_asset(ctx, def, tile_set, JsonUtil.to_str(asset["id"]))
	var car := load(RaceBuild.CAR_PATH) as PackedScene if ResourceLoader.exists(RaceBuild.CAR_PATH) else null
	if car == null:
		issues.append(ctx.make_issue("BUILD-002", {"recipe": "track_recipe", "reason": "the car scene is missing"}, RaceBuild.CAR_PATH))
		return issues
	var scene := build_track(0, JsonUtil.to_dict(tracks[0]), ArcadeBuild.view(ctx), tile, test_rows(), test_barriers(),
		test_start(tile), tile_set, road, car, RaceBuild.fixed_camera(ctx))
	var err := SceneUtil.save_scene(scene, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	var listed := StageRecipes.save_list(tracks)
	if listed != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": ArcadeBuild.STAGES_PATH, "err": listed}, ArcadeBuild.STAGES_PATH))
	return issues
