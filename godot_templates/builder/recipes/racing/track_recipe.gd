extends RefCounted
## The tracks of a racing game (generated/scenes/stages/stage_NN.tscn) and the lists of them.
## A track is an arcade stage that does not scroll: a field of grass, the road painted with a
## road tile of the packs (the layer "Ground") or drawn, what every cell is made of
## (RpgTrackSurfaces), dirt, oil and boost arrows shown on the road, the start line, barriers
## at the edges of the field and over the cells the loop does not use (with the scenery of the
## packs on them), tyres at the outside of the corners, markers where pickups lie, the car at
## the start and the race camera. There is a scene for every track of the plan rpggen stored
## (rpggen/world_plan.json, the section `stages`); a project without one gets a flat test
## track, a ring of road.

const RECIPE_VERSION := 2

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const MapUtil := preload("../../lib/map_util.gd")
const Paths := preload("../../lib/paths.gd")
const BuildContext := preload("../../lib/build_context.gd")
const WorldPlan := preload("../../lib/world_plan.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const StageRecipes := preload("../arcade/stage_recipes.gd")
const RaceBuild := preload("racing_build.gd")

const GRASS := Color(0.3, 0.59, 0.27)
const WALL := Color(0.78, 0.16, 0.16)
const HEDGE := Color(0.15, 0.33, 0.17)
const ROAD := Color(0.27, 0.27, 0.31)
const LINE := Color(0.94, 0.94, 0.94)
const TYRE := Color(0.14, 0.14, 0.16)
## What is drawn over the road for a letter of the plan.
const OVERLAYS := {"d": Color(0.59, 0.44, 0.27, 0.9), "o": Color(0.09, 0.09, 0.12, 0.92), "b": Color(0.35, 0.86, 1.0, 0.9)}
## What the game does not need of a planned track: it is painted into the scene.
const PAINTED: Array[String] = ["scene", "rows", "barriers", "tyres", "decoration", "loop", "cells"]

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	for i in maxi(1, stored_plan().size()):
		out.append(ArcadeBuild.stage_path(i))
	out.append(ArcadeBuild.PLANNED_STAGES_PATH)
	if not FileAccess.file_exists(ArcadeBuild.STAGES_PATH):
		out.append(ArcadeBuild.STAGES_PATH)
	return out

func input_hash(ctx: BuildContext) -> String:
	var def := tileset_def(ctx)
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"tracks": stored_plan() if not stored_plan().is_empty() else plan(ctx),
		"tileset": def.get("name", ""),
		"sources": def.get("sources", []),
		"road": RaceBuild.road_asset(ctx).get("id", ""),
		"finish": RaceBuild.tagged(ctx, "GROUND", "finish").get("id", ""),
		"tyre": RaceBuild.tagged(ctx, "HAZARD", "tyre").get("id", ""),
		"scenery": ArcadeBuild.assets(ctx, "DECORATION").map(func(a: Dictionary) -> Variant: return a.get("id", "")),
		"view": ArcadeBuild.view(ctx),
		"fixed": RaceBuild.fixed_camera(ctx),
	})

static func tileset_def(ctx: BuildContext) -> Dictionary:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return def

## The tracks rpggen planned and stored, with their rows; [] for a project without them.
static func stored_plan() -> Array:
	var stages := JsonUtil.to_dict(WorldPlan.read().get("stages", {}))
	if JsonUtil.to_str(stages.get("kind", "")) != "racing":
		return []
	return JsonUtil.to_array(stages.get("list", []))

## The tracks of the game as stages.json has them: those of the stored plan without what is
## painted into their scenes (the start, the checkpoints, the waypoints, the laps and the
## pickups stay: the race reads them). A project without a stored plan gets the test track.
static func plan(ctx: BuildContext) -> Array:
	var stored := stored_plan()
	if stored.is_empty():
		return [test_track(ArcadeBuild.tile(ctx))]
	var out: Array = []
	for raw: Variant in stored:
		var track := JsonUtil.to_dict(raw).duplicate(true)
		for key in PAINTED:
			track.erase(key)
		out.append(track)
	return out

# ---------------------------------------------------------------- the test track

## What every cell of the test track is made of: a ring of road `RaceBuild.ROAD_WIDTH` wide,
## `RaceBuild.TRACK_MARGIN` cells in from the edge of a field of grass.
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
## middle of the ring.
static func test_barriers(cells: Vector2i = RaceBuild.TRACK_CELLS) -> Array[Rect2i]:
	var island := Rect2i(Vector2i.ONE * RaceBuild.TRACK_MARGIN, cells - Vector2i.ONE * RaceBuild.TRACK_MARGIN * 2).grow(-(RaceBuild.ROAD_WIDTH + 3))
	return [
		Rect2i(0, 0, cells.x, 1),
		Rect2i(0, cells.y - 1, cells.x, 1),
		Rect2i(0, 0, 1, cells.y),
		Rect2i(cells.x - 1, 0, 1, cells.y),
		island,
	]

## Where the car starts on the test track (px): in the middle of the left straight.
static func test_start(tile: int, cells: Vector2i = RaceBuild.TRACK_CELLS) -> Vector2:
	return Vector2((RaceBuild.TRACK_MARGIN + RaceBuild.ROAD_WIDTH * 0.5) * tile, cells.y * 0.5 * tile)

## The test track as stages.json has it: the way round its four corners and back to the start.
static func test_track(tile: int, cells: Vector2i = RaceBuild.TRACK_CELLS) -> Dictionary:
	var half := RaceBuild.TRACK_MARGIN + RaceBuild.ROAD_WIDTH * 0.5
	var a := Vector2(half, half) * tile
	var b := (Vector2(cells) - Vector2(half, half)) * tile
	var start := test_start(tile, cells)
	var waypoints: Array = []
	for at: Vector2 in [a, Vector2(b.x, a.y), b, Vector2(a.x, b.y)]:
		waypoints.append({"position": [at.x, at.y], "speed": 6.9})
	waypoints.append({"position": [start.x, start.y], "speed": 12.0})
	return {
		"title": "",
		"axis": "none",
		"speed": 0.0,
		"length": 0.0,
		"exit": "custom",
		"par_time_s": 60.0,
		"waves": [],
		"laps": 3,
		"start": {"position": [start.x, start.y], "heading": -PI * 0.5, "line": [start.x, start.y - tile * 2.0]},
		"checkpoints": [],
		"waypoints": waypoints,
		"pickups": [],
	}

# ---------------------------------------------------------------- the scene

static func _rect(node_name: String, area: Rect2, color: Color) -> Polygon2D:
	var shape := Polygon2D.new()
	shape.name = node_name
	shape.color = color
	shape.polygon = PackedVector2Array([area.position, Vector2(area.end.x, area.position.y), area.end, Vector2(area.position.x, area.end.y)])
	return shape

## The plainest tile of a road sheet to paint a wide road with: grey, dark and of one colour
## (a sheet has tiles with lines, a start, a barrier, and grass); its first tile when none is.
static func plain_tile(tile_set: TileSet, source_id: int) -> Dictionary:
	var src := tile_set.get_source(source_id) as TileSetAtlasSource
	if src == null or src.get_tiles_count() == 0 or src.texture == null:
		return {}
	var image := src.texture.get_image()
	var best := src.get_tile_id(0)
	var best_spread := INF
	if image != null:
		if image.is_compressed():
			image.decompress()
		for i in src.get_tiles_count():
			var coords := src.get_tile_id(i)
			var area := src.get_tile_texture_region(coords)
			var low := Color(1, 1, 1)
			var high := Color(0, 0, 0)
			var clear := false
			# every pixel of a small tile (a centre line is one pixel wide), every nth of a large one
			var step := maxi(1, area.size.x / 24)
			for sy in range(0, area.size.y, step):
				for sx in range(0, area.size.x, step):
					var c := image.get_pixel(area.position.x + sx, area.position.y + sy)
					clear = clear or c.a < 0.9
					low = Color(minf(low.r, c.r), minf(low.g, c.g), minf(low.b, c.b))
					high = Color(maxf(high.r, c.r), maxf(high.g, c.g), maxf(high.b, c.b))
			var spread := (high.r - low.r) + (high.g - low.g) + (high.b - low.b)
			var grey := high.s < 0.25 and high.v < 0.6
			if not clear and grey and spread < best_spread:
				best = coords
				best_spread = spread
	return {"source_id": source_id, "coords": best}

## Adds a layer of drawn shapes to the scene at `at` among its children, or drops an empty one.
static func _keep(root: Node2D, layer: Node2D, layer_name: String, at: int) -> void:
	if layer.get_child_count() == 0:
		layer.free()
		return
	SceneUtil.add(root, layer, root, layer_name)
	root.move_child(layer, mini(at, root.get_child_count() - 1))
	SceneUtil.set_owner_recursive(layer, root)

static func _points(raw: Variant) -> Array[Vector2]:
	var out: Array[Vector2] = []
	for entry: Variant in JsonUtil.to_array(raw):
		var pair := JsonUtil.to_array(entry)
		if entry is Dictionary:
			pair = JsonUtil.to_array(JsonUtil.to_dict(entry).get("position", []))
		if pair.size() >= 2:
			out.append(Vector2(JsonUtil.to_float(pair[0]), JsonUtil.to_float(pair[1])))
	return out

## The scene of a track. `rows` say what every cell is made of, `barriers` are rectangles of
## cells, `start` is where the car stands (px); `road` is the tile the road is painted with
## ({}: the road is drawn). `look` has the rest: `heading` (rad, the way the car points),
## `tyres`, `decoration` and `pickups` (places in px, the pickups with their `kind`),
## `finish` (the tile of the start line), `tyre_texture` and `decoration_textures`.
static func build_track(index: int, stage: Dictionary, view: Vector2i, tile: int, rows: PackedStringArray, barriers: Array[Rect2i],
		start: Vector2, tile_set: TileSet, road: Dictionary, car_scene: PackedScene, fixed_camera: bool = false, look: Dictionary = {}) -> Node2D:
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
	var finish := JsonUtil.to_dict(look.get("finish", {}))
	var drawn := Node2D.new()
	drawn.z_index = -6
	var marks := Node2D.new()  # what lies on the road: over the tiles, under the cars
	marks.z_index = -4
	for y in cells.y:
		var from := -1  # where a run of road began in this row, when the road is drawn
		var mark_from := -1
		var mark := ""
		for x in cells.x + 1:
			var letter := rows[y][x] if x < cells.x else "g"
			var is_road := letter != "g" and letter != "."
			if is_road and painted:
				MapUtil.put(ground, Vector2i(x, y), finish if letter == "s" and not finish.is_empty() else road)
			elif is_road and from < 0:
				from = x
			elif not is_road and from >= 0:
				drawn.add_child(_rect("Road_%d_%d" % [from, y], Rect2(Vector2(from, y) * tile, Vector2((x - from) * tile, tile)), ROAD))
				from = -1
			# a run of one letter that is shown over the road
			var shown := letter if OVERLAYS.has(letter) or (letter == "s" and (finish.is_empty() or not painted)) else ""
			if shown != mark:
				if mark != "":
					var color: Color = LINE if mark == "s" else OVERLAYS[mark]
					marks.add_child(_rect("Mark_%s_%d_%d" % [mark, mark_from, y], Rect2(Vector2(mark_from, y) * tile, Vector2((x - mark_from) * tile, tile)), color))
				mark = shown
				mark_from = x
	_keep(root, drawn, "Road", 1)
	_keep(root, marks, "Marks", 2)
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
		# the edges of the field are a wall, a cell the loop does not use is a hedge
		var edge := barriers[i].size.x == 1 or barriers[i].size.y == 1
		SceneUtil.add(walls, _rect("Wall%d" % i, area, WALL if edge else HEDGE), root, "Wall%d" % i)
	# tyres at the outside of the corners: small, round and in the way
	var tyre_texture: Texture2D = null
	if look.get("tyre_texture") is Texture2D:
		tyre_texture = look.get("tyre_texture")
	var tyres := _points(look.get("tyres", []))
	for i in tyres.size():
		var shape := CollisionShape2D.new()
		var circle := CircleShape2D.new()
		circle.radius = tile * 0.4
		shape.shape = circle
		shape.position = tyres[i]
		SceneUtil.add(walls, shape, root, "Tyre%d" % i)
		if tyre_texture != null:
			var picture := Sprite2D.new()
			picture.texture = tyre_texture
			picture.position = tyres[i]
			SceneUtil.add(walls, picture, root, "TyrePicture%d" % i)
		else:
			var disc := Polygon2D.new()
			disc.color = TYRE
			var ring := PackedVector2Array()
			for k in 8:
				ring.append(Vector2.from_angle(TAU * k / 8.0) * tile * 0.4)
			disc.polygon = ring
			disc.position = tyres[i]
			SceneUtil.add(walls, disc, root, "TyrePicture%d" % i)
	# the scenery of the packs on the hedges
	var scenery_textures: Array = JsonUtil.to_array(look.get("decoration_textures", []))
	var places := _points(look.get("decoration", []))
	if not scenery_textures.is_empty() and not places.is_empty():
		var scenery := Node2D.new()
		scenery.z_index = 1
		SceneUtil.add(root, scenery, root, "Scenery")
		for i in places.size():
			var picture := Sprite2D.new()
			var texture: Texture2D = scenery_textures[i % scenery_textures.size()]
			picture.texture = texture
			picture.position = places[i]
			SceneUtil.add(scenery, picture, root, "Scenery%d" % i)
	# where pickups lie (the race puts them there)
	var pickups := JsonUtil.to_array(look.get("pickups", []))
	if not pickups.is_empty():
		var holder := Node2D.new()
		SceneUtil.add(root, holder, root, "Pickups")
		var at := _points(pickups)
		for i in at.size():
			var marker := Marker2D.new()
			marker.position = at[i]
			marker.set_meta("kind", JsonUtil.to_str(JsonUtil.to_dict(pickups[i]).get("kind", "boost")))
			SceneUtil.add(holder, marker, root, "Pickup%d" % (i + 1))
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
			car.set("heading", JsonUtil.to_float(look.get("heading", -PI * 0.5)))
			SceneUtil.add(root, car, root, "Car")
	return root

static func _barriers_of(track: Dictionary, cells: Vector2i) -> Array[Rect2i]:
	var out: Array[Rect2i] = []
	for raw: Variant in JsonUtil.to_array(track.get("barriers", [])):
		var r := JsonUtil.to_array(raw)
		if r.size() >= 4:
			out.append(Rect2i(JsonUtil.to_int(r[0]), JsonUtil.to_int(r[1]), JsonUtil.to_int(r[2]), JsonUtil.to_int(r[3])))
	if out.is_empty():
		out = test_barriers(cells)
	return out

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var tracks := plan(ctx)
	var stored := stored_plan()
	var tile := ArcadeBuild.tile(ctx)
	var def := tileset_def(ctx)
	var tile_set: TileSet = null
	var road := {}
	var finish := {}
	if not def.is_empty():
		tile_set = load(Paths.TILESETS_DIR + "%s.tres" % def["name"]) as TileSet
		var asset := RaceBuild.road_asset(ctx)
		if tile_set != null and not asset.is_empty():
			var first := MapUtil.tile_of_asset(ctx, def, tile_set, JsonUtil.to_str(asset["id"]))
			if not first.is_empty():
				road = plain_tile(tile_set, JsonUtil.to_int(first["source_id"]))
		var line := RaceBuild.tagged(ctx, "GROUND", "finish")
		if tile_set != null and not line.is_empty():
			finish = MapUtil.tile_of_asset(ctx, def, tile_set, JsonUtil.to_str(line["id"]))
	var car := load(RaceBuild.CAR_PATH) as PackedScene if ResourceLoader.exists(RaceBuild.CAR_PATH) else null
	if car == null:
		issues.append(ctx.make_issue("BUILD-002", {"recipe": "track_recipe", "reason": "the car scene is missing"}, RaceBuild.CAR_PATH))
		return issues
	var look := {"finish": finish, "tyre_texture": ArcadeBuild.first_frame(ctx, RaceBuild.tagged(ctx, "HAZARD", "tyre"))}
	var scenery: Array = []
	for asset in ArcadeBuild.assets(ctx, "DECORATION"):
		var texture := ArcadeBuild.first_frame(ctx, asset)
		if texture != null and scenery.size() < 6:
			scenery.append(texture)
	look["decoration_textures"] = scenery
	for i in tracks.size():
		var path := ArcadeBuild.stage_path(i)
		var entry := JsonUtil.to_dict(tracks[i])
		var rows := test_rows()
		var barriers := test_barriers()
		var start := test_start(tile)
		var own := look.duplicate()
		if i < stored.size():
			var track := JsonUtil.to_dict(stored[i])
			rows = PackedStringArray(JsonUtil.to_array(track.get("rows", [])))
			barriers = _barriers_of(track, Vector2i(rows[0].length(), rows.size()))
			var begin := JsonUtil.to_dict(track.get("start", {}))
			var at := _points([begin.get("position", [])])
			if not at.is_empty():
				start = at[0]
			own["heading"] = JsonUtil.to_float(begin.get("heading", -PI * 0.5))
			for key: String in ["tyres", "decoration", "pickups"]:
				own[key] = JsonUtil.to_array(track.get(key, []))
		var scene := build_track(i, entry, ArcadeBuild.view(ctx), tile, rows, barriers, start, tile_set, road, car, RaceBuild.fixed_camera(ctx), own)
		var err := SceneUtil.save_scene(scene, path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	var listed := StageRecipes.save_list(tracks)
	if listed != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": ArcadeBuild.STAGES_PATH, "err": listed}, ArcadeBuild.STAGES_PATH))
	return issues
