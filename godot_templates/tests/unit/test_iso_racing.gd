extends RefCounted
## T17.15: a race seen at an angle. The arithmetic of the view (RpgRaceView) on RpgIso's grid,
## the frame of a car's picture for its heading on the screen, the camera that leads the car on
## the screen, the stick of absolute steering, a track painted on diamonds with its race still
## in the plan, the road laid from the pieces of a pack along the loop, and a lap of a planned
## track by the smoke's driver that is, step for step, the lap of the same track seen from above.

const Fixtures := preload("../lib/fixtures.gd")
const TilesetRecipe := preload("res://builder/recipes/tileset_recipe.gd")
const CarRecipe := preload("res://builder/recipes/racing/car_recipe.gd")
const RivalRecipes := preload("res://builder/recipes/racing/rival_recipes.gd")
const TrackRecipe := preload("res://builder/recipes/racing/track_recipe.gd")
const IsoTrack := preload("res://builder/recipes/racing/iso_track.gd")
const RaceBuild := preload("res://builder/recipes/racing/racing_build.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")
const MapGeo := preload("res://builder/lib/map_geo.gd")
const MapUtil := preload("res://builder/lib/map_util.gd")
const JsonUtil := preload("res://builder/lib/json_util.gd")

## The tracks of track_plan.plan({}, 12345): tests/unit/test_track_plan.py keeps the file.
const TRACKS := "res://tests/unit/track_plan_cases.json"
const CASES := "res://tests/unit/car_math_cases.json"
const FIXTURE := "res://tests/fixtures/iso_tiles/catalog.json"
const TS_PATH := "res://generated/tilesets/iso.tres"
const STATE_PATH := "res://rpggen/tileset_apply_state.json"
const FOOT := Vector2i(60, 34)
const TILE := 16
const VIEW := Vector2i(640, 360)
const DT := 1.0 / 60.0
const ROAD_STRAIGHT := "iso_tiles.png.isotile_010_"
const ROAD_CORNER := "iso_tiles.png.isotile_011_"
## The smoke's driver (smoke_steps_racing.gd): how near a waypoint it turns to the next one.
const REACH := 4.0

# ---------------------------------------------------------------- helpers

func _view(tiles: int = RaceBuild.DRAWN_TILES, footprint: Vector2i = FOOT) -> RpgRaceView:
	var seen := RpgRaceView.new()
	seen.name = RpgRaceView.NODE
	seen.footprint = footprint
	seen.cell_px = float(tiles * TILE)
	seen.origin = Vector2(TILE, TILE)
	return seen

func _sheet(headings: int, cell: int) -> ImageTexture:
	var image := Image.create(cell * headings, cell, false, Image.FORMAT_RGBA8)
	image.fill(Color.RED)
	return ImageTexture.create_from_image(image)

func _catalog() -> Dictionary:
	return JsonUtil.to_dict(JsonUtil.read(FIXTURE)).duplicate(true)

## The catalog with a road in two pieces that name their sides (a straight and a corner, each
## one tile turned four ways of which the first is annotated, as the audit would).
func _with_road() -> Dictionary:
	var cat := _catalog()
	for raw: Variant in JsonUtil.to_array(cat["assets"]):
		var asset: Dictionary = raw
		var id := str(asset["id"])
		if id.begins_with(ROAD_STRAIGHT):
			asset["overrides"] = {"role": "ROAD", "joins": ["n", "s"]} if id.ends_with("_0") else {"role": "ROAD"}
		elif id.begins_with(ROAD_CORNER):
			asset["overrides"] = {"role": "ROAD", "joins": ["e", "s"]} if id.ends_with("_0") else {"role": "ROAD"}
	return cat

func _cleanup() -> void:
	for p: String in [TS_PATH, STATE_PATH]:
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(p)

## The geometry of an isometric project with the tiles of `cat`, its tile set built and loaded.
func _geo(t, cat: Dictionary) -> MapGeo:
	_cleanup()
	var ctx := BuildContext.new("res://builder")
	ctx.config = {"projection": "isometric", "features": {}, "seed": 7, "map_layers": MapUtil.DEFAULT_LAYERS.duplicate()}
	ctx.catalog = CatalogReader.new(cat, "isometric")
	t.eq(TilesetRecipe.new().build(ctx), [])
	var geo := MapGeo.new(ctx)
	t.ok(geo.isometric and geo.load_tile_set() != null, "the tile set of diamonds is built")
	return geo

func _planned() -> Array:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(TRACKS))
	if parsed is Dictionary:
		var plan: Dictionary = parsed
		return JsonUtil.to_array(plan.get("list", []))
	return []

## The scene of a planned track with `rivals` rivals, in the tree, its race set up; nothing
## moves by itself. Seen from above without `geo`; with it on its diamonds, the road laid from
## the pieces of the packs when `pieces` (the diamonds then enlarged `scale` times).
func _stage(track: Dictionary, rivals: int, geo: MapGeo = null, pieces: bool = false, fixed: bool = false, scale: int = 1) -> RpgArcadeStage:
	var car_scene := PackedScene.new()
	var made := CarRecipe.build_car(_sheet(8, 24), Vector2i(24, 24), 8, TILE)
	car_scene.pack(made)
	made.free()
	var rival_scenes: Array = []
	for i in rivals:
		var packed := PackedScene.new()
		var rival := RivalRecipes.build_rival(i + 1, _sheet(8, 24), Vector2i(24, 24), 8, TILE)
		packed.pack(rival)
		rival.free()
		rival_scenes.append(packed)
	var pickup_scene := PackedScene.new()
	var pickup := RivalRecipes.build_pickup(TILE)
	pickup_scene.pack(pickup)
	pickup.free()
	var rows := PackedStringArray(JsonUtil.to_array(track["rows"]))
	var barriers: Array[Rect2i] = []
	for raw: Variant in JsonUtil.to_array(track["barriers"]):
		var r := JsonUtil.to_array(raw)
		barriers.append(Rect2i(int(r[0]), int(r[1]), int(r[2]), int(r[3])))
	var begin := JsonUtil.to_dict(track["start"])
	var at := JsonUtil.to_array(begin["position"])
	var start := Vector2(float(at[0]), float(at[1]))
	var look := {
		"heading": float(begin["heading"]),
		"tyres": track["tyres"],
		"pickups": track["pickups"],
		"decoration": track["decoration"],
		"rival_scenes": rival_scenes,
		"pickup_scene": pickup_scene,
	}
	var stage: RpgArcadeStage = null
	if geo == null:
		stage = TrackRecipe.build_track(0, track, VIEW, TILE, rows, barriers, start, null, {}, car_scene, fixed, look) as RpgArcadeStage
	else:
		look["loop"] = track["loop"]
		look["pieces"] = pieces
		look["tiles"] = 3
		look["scale"] = scale
		look["zoom"] = 2.0
		look["decoration_textures"] = [_sheet(1, 20)]
		look["decoration_origins"] = [Vector2(10, 18)]
		stage = IsoTrack.build_track(0, track, VIEW, TILE, rows, barriers, start, geo, car_scene, fixed, look) as RpgArcadeStage
	Fixtures.tree().root.add_child(stage)
	var race := stage.get_node("Race") as RpgRace
	race.auto_advance = false
	race.countdown_s = 0.1
	var all: Array[RpgCar] = []
	for node in stage.find_children("*", "CharacterBody2D", true, false):
		var car := node as RpgCar
		car.set_physics_process(false)
		car.input_node_enabled = not car.is_player
		all.append(car)
	(stage.get_node("Camera") as RpgRaceCamera).auto_advance = false
	race.setup(track, all)
	race.begin()
	return stage

func _drop(stage: Node) -> void:
	stage.get_parent().remove_child(stage)
	stage.free()

func _points(track: Dictionary, key: String) -> Array[Vector2]:
	var out: Array[Vector2] = []
	for raw: Variant in JsonUtil.to_array(track[key]):
		var at := JsonUtil.to_array(JsonUtil.to_dict(raw)["position"])
		out.append(Vector2(float(at[0]), float(at[1])))
	return out

## One step of the smoke's driver (smoke_steps_racing.gd, `_drive_toward`), telling the car
## what the driver's buttons would: toward `goal` (px of the plan), down to `limit` (tiles a
## second) in time. With absolute steering the stick is the way to the goal as it is seen.
func _drive_toward(car: RpgCar, goal: Vector2, limit: float, stuck: int) -> int:
	var tile := car.tile_size
	var to := goal - car.position
	var speed := car.speed_tiles()
	if stuck > 90:
		car.throttle = -1.0
		car.steer = 0.0
		car.stick = Vector2.ZERO
		return stuck + 1 if stuck < 130 else 0
	var wheel := RpgCarPhysics.steer_toward(car.heading, to.angle())
	var room := (speed * speed - limit * limit) / (2.0 * RpgCarPhysics.BRAKE) + 2.5
	var slow := speed > limit and to.length() < room * tile
	var turning := absf(RpgCarPhysics.angle_difference(car.heading, to.angle())) > 0.45 and speed > 6.0
	if car.absolute_steering:
		var seen := car.view()
		car.stick = seen.screen_vector(to).normalized() if seen != null else to.normalized()
	else:
		car.steer = 1.0 if wheel > 0.15 else (-1.0 if wheel < -0.15 else 0.0)
	car.throttle = -1.0 if slow else (0.0 if turning else 1.0)
	return stuck + 1 if absf(speed) < 0.6 and not car.is_spinning() else 0

## Drives the player's car of `stage` along the waypoints of `track` until it has driven
## `laps` laps (or `most` steps). Returns what happened: `steps`, `laps`, `path` (where the
## car was after every step), `gates` (how many checkpoints were counted one after the other,
## each with the car near it), `out_of_order`, `grass` and `shown` (how many steps the
## picture was not where the view puts the car, or not the frame of its heading there).
func _lap(stage: RpgArcadeStage, track: Dictionary, laps: int = 1, most: int = 60 * 90) -> Dictionary:
	var race := stage.get_node("Race") as RpgRace
	var car := stage.get_node("Car") as RpgCar
	var visual := car.get_node("Visual") as RpgHeadingSprite
	var seen := car.view()
	var waypoints := _points(track, "waypoints")
	var speeds: Array[float] = []
	for raw: Variant in JsonUtil.to_array(track["waypoints"]):
		speeds.append(float(JsonUtil.to_dict(raw)["speed"]))
	var out := {"steps": 0, "gates": 0, "out_of_order": 0, "grass": 0, "shown": 0}
	var path := PackedVector2Array()
	var target := 0
	var stuck := 0
	var passed := 0
	var steps := 0
	while race.lap_of(car) <= laps and steps < most:
		if race.is_running():
			if (waypoints[target] - car.position).length() < car.tile_size * REACH:
				target = (target + 1) % waypoints.size()
			stuck = _drive_toward(car, waypoints[target], speeds[target], stuck)
		car.step(DT)
		race.advance(DT)
		steps += 1
		path.append(car.position)
		if car.surface == "grass":
			out["grass"] += 1
		var counted := race.checkpoints_of(car)
		if race.lap_of(car) == 1 and counted != passed:
			var gate := race.gates[counted - 1]
			if counted != passed + 1 or car.position.distance_to(gate.position) > gate.width:
				out["out_of_order"] += 1
			passed = counted
		if seen != null:
			var at := seen.to_screen(car.position) - car.position
			if not visual.position.is_equal_approx(at) or visual.frame != visual.frame_for(seen.screen_heading(car.heading)):
				out["shown"] += 1
	out["steps"] = steps
	out["laps"] = race.lap_of(car) - 1
	out["gates"] = passed
	out["path"] = path
	return out

# ---------------------------------------------------------------- the view

func test_the_view_is_rpgisos_grid_at_another_scale(t) -> void:
	# a diamond is three tiles of the plan wide, the first behind the wall of one tile
	var seen := _view()
	t.eq(seen.to_screen(Vector2(TILE, TILE)), Vector2(30, 0), "the corner of the field's first cell is the top corner of the cell (0, 0)")
	for cell: Vector2i in [Vector2i(0, 0), Vector2i(3, 0), Vector2i(0, 4), Vector2i(7, 5), Vector2i(-1, 2)]:
		var middle := Vector2(TILE, TILE) + (Vector2(cell) + Vector2(0.5, 0.5)) * 3.0 * TILE
		t.ok(seen.to_screen(middle).is_equal_approx(RpgIso.cell_to_screen(cell, FOOT)), "the middle of the cell %s is RpgIso's" % cell)
		t.eq(RpgIso.screen_to_cell(seen.to_screen(middle + Vector2(5, -7)), FOOT), cell, "a point of its square is in its diamond")
		t.eq(seen.depth(middle), cell.x + cell.y + 1, "its row of diamonds")
	for plan: Vector2 in [Vector2(0, 0), Vector2(100, 37), Vector2(612.5, 480.25), Vector2(-40, 900)]:
		t.ok(seen.to_plan(seen.to_screen(plan)).is_equal_approx(plan), "to the screen and back: %s" % plan)
	# a step east runs down and to the right, a step south down and to the left
	t.ok(seen.screen_vector(Vector2(48, 0)).is_equal_approx(Vector2(30, 17)))
	t.ok(seen.screen_vector(Vector2(0, 48)).is_equal_approx(Vector2(-30, 17)))
	t.ok(seen.plan_vector(Vector2(30, 17)).is_equal_approx(Vector2(48, 0)), "and back")
	t.ok(seen.plan_vector(Vector2(0, 34)).is_equal_approx(Vector2(48, 48)), "down on the screen is south-east in the plan")
	t.near(seen.scale_px(), Vector2(30, 17).length() / 48.0, 0.0001)
	# a rectangle of the plan is a diamond-shaped piece of the screen
	var corners := seen.screen_corners(Rect2(TILE, TILE, 96, 48))
	t.ok(corners[0].is_equal_approx(Vector2(30, 0)) and corners[1].is_equal_approx(Vector2(90, 34)) and corners[2].is_equal_approx(Vector2(60, 51)) and corners[3].is_equal_approx(Vector2(0, 17)), str(corners))
	t.ok(seen.screen_rect(Rect2(TILE, TILE, 96, 48)).is_equal_approx(Rect2(0, 0, 90, 51)))
	# it is found from anything of its track, and a track seen from above has none
	var root := Node2D.new()
	var holder := Node2D.new()
	var leaf := Node2D.new()
	root.add_child(holder)
	holder.add_child(leaf)
	t.ok(RpgRaceView.of(leaf) == null, "a track seen from above")
	root.add_child(seen)
	t.ok(RpgRaceView.of(leaf) == seen and RpgRaceView.of(holder) == seen and RpgRaceView.of(root) == seen)
	root.free()

func test_a_heading_of_the_plan_is_another_on_the_screen(t) -> void:
	for footprint: Vector2i in [FOOT, Vector2i(64, 32), Vector2i(180, 104), Vector2i(100, 65)]:
		var seen := _view(3, footprint)
		# the eight headings of a car drawn for the view: N is up on the screen, then clockwise
		var names := ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
		var want := {0.0: "SE", PI * 0.5: "SW", PI: "NW", -PI * 0.5: "NE", PI * 0.25: "S", -PI * 0.25: "E", PI * 0.75: "W", -PI * 0.75: "N"}
		for heading: float in want.keys():
			var frame := RpgCarPhysics.heading_frame(seen.screen_heading(heading), 8)
			t.eq(names[frame], want[heading], "%s: the plan's heading %.2f" % [footprint, heading])
			t.near(RpgCarPhysics.angle_difference(seen.plan_heading(seen.screen_heading(heading)), heading), 0.0, 0.0001, "and back")
		# east in the plan points along the lower right side of the diamond
		t.near(seen.screen_heading(0.0), Vector2(footprint).angle(), 0.0001)
		seen.free()

func test_the_frame_of_the_picture_is_for_the_heading_on_the_screen(t) -> void:
	var root := Node2D.new()
	var seen := _view()
	root.add_child(seen)
	var car := CarRecipe.build_car(_sheet(8, 24), Vector2i(24, 24), 8, TILE) as RpgCar
	car.input_node_enabled = false
	root.add_child(car)
	Fixtures.tree().root.add_child(root)
	var visual := car.get_node("Visual") as RpgHeadingSprite
	t.ok(car.view() == seen, "the car knows how its track is seen")
	var at := Vector2(400, 250)
	car.place(at, 0.0)
	t.eq(visual.frame, 3, "east in the plan: the picture that points down and to the right (SE)")
	t.eq(car.position, at, "the car is where the plan has it")
	t.ok((car.position + visual.position).is_equal_approx(seen.to_screen(at)), "and its picture where the view has that place")
	t.ok(car.shown_position().is_equal_approx(seen.to_screen(at)))
	t.near(car.shown_heading(), Vector2(30, 17).angle(), 0.0001)
	t.eq(visual.z_index, seen.depth(at), "it is drawn by its row of diamonds")
	t.eq(visual.rotation, 0.0, "a sheet of headings is not turned")
	car.place(at, -PI * 0.5)
	t.eq(visual.frame, 1, "north in the plan: up and to the right (NE)")
	car.place(at, PI * 0.5)
	t.eq(visual.frame, 5, "south: down and to the left (SW)")
	car.place(at, PI)
	t.eq(visual.frame, 7, "west: up and to the left (NW)")
	# the car steers smoothly underneath; its picture turns in steps of 45 degrees
	car.place(at, 0.0)
	car.surface_override = "road"
	car.velocity = Vector2(6.0 * TILE, 0.0)
	car.throttle = 0.6
	car.steer = 1.0
	var frames: Array[int] = []
	var most := 0.0
	var before := car.heading
	for i in 240:
		car.step(DT)
		most = maxf(most, absf(RpgCarPhysics.angle_difference(before, car.heading)))
		before = car.heading
		t.eq(visual.frame, visual.frame_for(seen.screen_heading(car.heading)))
		if frames.is_empty() or frames[-1] != visual.frame:
			frames.append(visual.frame)
	t.ok(most > 0.0 and most < 0.1, "the heading turns a little a step (%.3f rad at most)" % most)
	t.ok(frames.size() >= 8, "and the picture went through its headings: %s" % [frames])
	for i in range(1, frames.size()):
		t.eq(posmod(frames[i] - frames[i - 1], 8), 1, "one step clockwise at a time")
	# a sheet drawn from straight above (sixteen headings) is used too: by the screen's heading
	var flat := CarRecipe.build_car(_sheet(16, 24), Vector2i(24, 24), 16, TILE, false) as RpgCar
	root.add_child(flat)
	flat.place(at, 0.0)
	var flat_visual := flat.get_node("Visual") as RpgHeadingSprite
	t.eq(flat_visual.frame, RpgCarPhysics.heading_frame(Vector2(30, 17).angle(), 16))
	t.eq(flat_visual.frame, 5, "between right (4) and down and to the right (6)")
	# one picture is turned to it, and a car without a picture is a drawn one that is turned
	var single := CarRecipe.build_car(_sheet(1, 24), Vector2i(24, 24), 1, TILE, false) as RpgCar
	root.add_child(single)
	single.place(at, 0.0)
	t.near((single.get_node("Visual") as Node2D).rotation, Vector2(30, 17).angle() + PI * 0.5, 0.0001)
	var drawn := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE, false) as RpgCar
	root.add_child(drawn)
	drawn.place(at, PI)
	t.near((drawn.get_node("Visual") as Node2D).rotation, Vector2(-30, -17).angle() + PI * 0.5, 0.0001)
	t.ok((drawn.position + (drawn.get_node("Visual") as Node2D).position).is_equal_approx(seen.to_screen(at)))
	root.get_parent().remove_child(root)
	root.free()
	# seen from above nothing of this happens: the picture is the car's own heading, on the car
	var above := CarRecipe.build_car(_sheet(8, 24), Vector2i(24, 24), 8, TILE) as RpgCar
	Fixtures.tree().root.add_child(above)
	above.place(at, 0.0)
	var above_visual := above.get_node("Visual") as RpgHeadingSprite
	t.eq([above_visual.frame, above_visual.position, above_visual.z_index], [2, Vector2.ZERO, 0])
	t.eq([above.shown_position(), above.shown_heading()], [at, 0.0])
	above.get_parent().remove_child(above)
	above.free()

func test_the_camera_leads_the_car_on_the_screen(t) -> void:
	await Fixtures.tree().process_frame
	var root := Node2D.new()
	var seen := _view()
	root.add_child(seen)
	var car := CarRecipe.build_car(_sheet(8, 24), Vector2i(24, 24), 8, TILE) as RpgCar
	car.input_node_enabled = false
	car.set_physics_process(false)
	root.add_child(car)
	var camera := RpgRaceCamera.new()
	camera.auto_advance = false
	camera.view = Vector2(VIEW)
	root.add_child(camera)
	Fixtures.tree().root.add_child(root)
	camera.target_path = camera.get_path_to(car)
	car.place(Vector2(500, 300), 0.0)
	camera.snap()
	t.ok(camera.position.is_equal_approx(seen.to_screen(car.position)), "over where a car that stands is drawn (%s)" % camera.position)
	t.ok(not camera.position.is_equal_approx(car.position), "which is not where the plan has it")
	t.eq(camera.zoom, Vector2.ONE)
	# east in the plan at the top speed: a quarter of the screen ahead, down and to the right
	car.velocity = Vector2(RpgCarPhysics.TOP * TILE, 0.0)
	var lead := camera.wanted() - seen.to_screen(car.position)
	t.near(lead.length(), 360.0 * RpgCarPhysics.LEAD, 0.01, "as far ahead as seen from above")
	t.near(lead.angle(), Vector2(30, 17).angle(), 0.0001, "the way the car moves on the screen")
	t.near(camera.wanted_zoom(), RpgCarPhysics.ZOOM_FAR, 0.0001)
	# north at half the speed: up and to the right, half as far
	car.velocity = Vector2(0.0, -RpgCarPhysics.TOP * TILE * 0.5)
	lead = camera.wanted() - seen.to_screen(car.position)
	t.near(lead.length(), 360.0 * RpgCarPhysics.LEAD * 0.5, 0.01)
	t.near(lead.angle(), Vector2(30, -17).angle(), 0.0001)
	for i in 120:
		camera.advance(DT)
	t.ok(camera.position.distance_to(camera.wanted()) < 0.5, "the camera gets there")
	# a camera that is nearer (large diamonds, a small car): the same part of the screen
	camera.base_zoom = 2.0
	car.velocity = Vector2(RpgCarPhysics.TOP * TILE, 0.0)
	t.near((camera.wanted() - seen.to_screen(car.position)).length(), 360.0 * RpgCarPhysics.LEAD / 2.0, 0.01)
	t.near(camera.wanted_zoom(), RpgCarPhysics.ZOOM_FAR * 2.0, 0.0001)
	car.velocity = Vector2.ZERO
	camera.snap()
	t.eq(camera.zoom, Vector2.ONE * 2.0, "over a car that stands")
	# fixed: the whole diamond of the track, never nearer than a car that stands is seen
	camera.fixed = true
	camera.track = seen.screen_rect(Rect2(0, 0, 38 * TILE, 29 * TILE))
	camera.look_at_track()
	t.ok(camera.position.is_equal_approx(camera.track.get_center()))
	t.near(camera.zoom.x, minf(640.0 / camera.track.size.x, 360.0 / camera.track.size.y), 0.0001)
	t.ok(camera.zoom.x < 2.0 and camera.track.size.x * camera.zoom.x <= 640.01 and camera.track.size.y * camera.zoom.y <= 360.01, "the whole track is on the screen")
	camera.track = Rect2(0, 0, 64, 36)
	camera.look_at_track()
	t.eq(camera.zoom, Vector2.ONE * 2.0, "a track smaller than the screen is not blown up further")
	root.get_parent().remove_child(root)
	root.free()

func test_the_stick_of_absolute_steering_is_a_direction_of_the_screen(t) -> void:
	await Fixtures.tree().process_frame
	var root := Node2D.new()
	var seen := _view()
	root.add_child(seen)
	var car := CarRecipe.build_car(_sheet(8, 24), Vector2i(24, 24), 8, TILE) as RpgCar
	car.input_node_enabled = false
	car.set_physics_process(false)
	car.absolute_steering = true
	car.surface_override = "road"
	root.add_child(car)
	Fixtures.tree().root.add_child(root)
	# the stick held down on the screen: the car ends up heading south-east in the plan, which
	# is what points down there
	for stick: Vector2 in [Vector2.DOWN, Vector2.RIGHT, Vector2.UP, Vector2(-1, -1).normalized()]:
		car.place(Vector2(2000, 2000), 0.3)
		car.velocity = car.forward() * 5.0 * TILE
		car.stick = stick
		car.throttle = 0.5
		for i in 240:
			car.step(DT)
		t.near(RpgCarPhysics.angle_difference(car.shown_heading(), stick.angle()), 0.0, 0.05, "the car points along the stick on the screen (%s)" % stick)
		t.near(RpgCarPhysics.angle_difference(car.heading, seen.plan_heading(stick.angle())), 0.0, 0.05)
	t.near(seen.plan_heading(Vector2.DOWN.angle()), PI * 0.25, 0.0001, "down on the screen is south-east")
	root.get_parent().remove_child(root)
	root.free()

# ---------------------------------------------------------------- the track

func test_a_track_on_diamonds_keeps_its_race_in_the_plan(t) -> void:
	var track: Dictionary = _planned()[1]
	var geo := _geo(t, _catalog())
	t.ok(not RaceBuild.road_pieces(geo), "the pack names no road piece: the road is drawn")
	# the scale is chosen for the car: its picture is to be about 1.6 tiles long on the road.
	# One step on a diamond of 60 x 34 is 34 px
	t.eq(geo.tile_px, 34)
	var small := RaceBuild.scale_for(geo, 21.0, false)
	t.eq([small["pieces"], small["tiles"], small["scale"], small["zoom"]], [false, 3, 1, 1.0], "a car of 21 px: three tiles a diamond")
	t.near(float(small["shown"]), 34.0 / 3.0, 0.0001, "a tile of the plan is 11 px on the screen")
	t.eq(RaceBuild.scale_for(geo, 24.0, false)["tiles"], 2, "a car of 24 px (the drawn one): two")
	t.eq(RaceBuild.scale_for(geo, 0.0, false)["tiles"], 3, "no picture of a car: three")
	t.eq(RaceBuild.scale_for(geo, 200.0, false)["tiles"], 2, "never fewer than two")
	var tiny := RaceBuild.scale_for(geo, 6.0, false)
	t.eq(tiny["tiles"], 9, "a tiny car on large diamonds: a block a diamond")
	t.near(float(tiny["zoom"]), 3.45, 0.0001, "and the camera comes nearer")
	# with road pieces a cell of the loop is one diamond, and the diamonds are enlarged
	var laid := RaceBuild.scale_for(geo, 21.0, true)
	t.eq([laid["pieces"], laid["tiles"], laid["scale"], laid["zoom"]], [true, 9, 3, 1.0])
	t.near(float(laid["shown"]), 34.0 * 3.0 / 9.0, 0.0001)
	t.eq(RaceBuild.scale_for(geo, 300.0, true)["scale"], 4, "four times at most")
	# the diamonds are not enlarged past what the camera shows without zooming out: a tile of
	# 22 px at most (a diamond whose step is 104 px is not enlarged at all for a large car)
	t.near(float(RaceBuild.scale_for(geo, 300.0, true)["shown"]), 34.0 * 4.0 / 9.0, 0.0001)
	t.eq(RaceBuild.scale_for(geo, 300.0, true)["zoom"], 1.0)
	t.eq(RaceBuild.scale_for(geo, 5.0, true)["scale"], 1, "and never made smaller")
	t.eq([RaceBuild.zoom_for(9.0), RaceBuild.zoom_for(22.0)], [1.0, 1.0])
	t.near(RaceBuild.zoom_for(26.0), 0.5, 0.0001)
	t.near(RaceBuild.zoom_for(1.0), 4.0, 0.0001)
	t.near(RaceBuild.body_radius(34.0 / 3.0, Vector2(21, 18), TILE), 18 * 0.36 / (34.0 / 3.0) * TILE, 0.001, "the body of a car of 21 x 18 px, in px of the plan")
	t.near(RaceBuild.body_radius(34.0 / 3.0, Vector2(64, 64), TILE), 0.65 * TILE, 0.001, "never so large that two do not fit side by side on the grid")
	t.near(RaceBuild.body_radius(34.0 / 3.0, Vector2(4, 4), TILE), 0.4 * TILE, 0.001, "nor so small that it cannot be seen to touch")
	var above := _stage(track, 3)
	var plan := {}
	for node in above.find_children("*", "", true, false):
		if node is CharacterBody2D or node is CollisionShape2D or node is RpgRacePickup:
			plan[str(above.get_path_to(node))] = (node as Node2D).position
	var roads := above.get_node("Road").get_child_count()
	var marks := above.get_node("Marks").get_child_count()
	var rows: PackedStringArray = above.get_node("Surfaces").get("rows")
	_drop(above)
	var stage := _stage(track, 3, geo)
	var seen := stage.get_node("View") as RpgRaceView
	t.ok(seen != null, "the track says how it is seen")
	t.eq([seen.footprint, seen.cell_px, seen.origin], [FOOT, 48.0, Vector2(TILE, TILE)])
	# everything a car can touch or drive over is where the track seen from above has it
	var same := 0
	for node in stage.find_children("*", "", true, false):
		if node is CharacterBody2D or node is CollisionShape2D or node is RpgRacePickup:
			var key := str(stage.get_path_to(node))
			t.ok(plan.has(key) and plan[key] == (node as Node2D).position, "%s is where the plan has it" % key)
			same += 1
	t.eq(same, plan.size(), "and nothing is missing (%d cars, shapes and pickups)" % same)
	t.eq(stage.get_node("Surfaces").get("rows"), rows, "what every cell is made of")
	t.ok(stage.get_node("Barriers").find_children("*", "Polygon2D", true, false).is_empty(), "the barriers of the plan are not drawn where they are")
	# what is seen: the ground on diamonds under the whole field, the road drawn over it
	var ground := stage.get_node("Ground") as TileMapLayer
	t.ok(RpgIso.is_iso(ground.tile_set) and not ground.collision_enabled)
	var cells := Vector2i(rows[0].length(), rows.size())
	var covered := IsoTrack.ground_cells(seen, Rect2(Vector2.ZERO, Vector2(cells) * TILE))
	t.eq(ground.get_used_cells().size(), covered.size.x * covered.size.y, "one ground tile a diamond")
	for corner: Vector2 in [Vector2.ZERO, Vector2(cells.x, 0) * TILE, Vector2(cells) * TILE, Vector2(0, cells.y) * TILE]:
		t.ok(ground.get_cell_source_id(RpgIso.screen_to_cell(seen.to_screen(corner), FOOT)) >= 0, "the corner %s of the field lies on ground" % corner)
	t.eq(stage.get_node("Road").get_child_count(), roads, "the road, run for run")
	t.eq(stage.get_node("Marks").get_child_count(), marks, "and what lies on it")
	var run := stage.get_node("Road").get_child(0) as Polygon2D
	var named := run.name.split("_")
	var from := Vector2(int(named[1]), int(named[2])) * TILE
	t.ok(run.polygon[0].is_equal_approx(seen.to_screen(from - Vector2(IsoTrack.SEAM, IsoTrack.SEAM))), "a run of road begins where the view has its first cell (and a hair before it)")
	t.near((run.polygon[3] - run.polygon[0]).angle(), Vector2(-30, 17).angle(), 0.0001, "and is one row of the plan high: down and to the left")
	t.eq(stage.get_node("Walls").get_child_count(), JsonUtil.to_array(track["barriers"]).size() + JsonUtil.to_array(track["tyres"]).size(), "a wall or a hedge drawn for every barrier, a disc for every tyre")
	# the scenery stands on the middles of diamonds, sorted with the cars
	var scenery := stage.get_node("Scenery")
	t.ok(scenery.get_child_count() > 0)
	for node in scenery.get_children():
		var picture := node as Sprite2D
		var cell := RpgIso.screen_to_cell(picture.position, FOOT)
		t.ok(picture.position.is_equal_approx(RpgIso.cell_to_screen(cell, FOOT)), "%s stands on the middle of %s" % [picture.name, cell])
		t.eq([picture.z_index, picture.offset], [IsoTrack.STANDING_Z + cell.x + cell.y + 1, Vector2(-10, -18)])
	# the cars and what lies on the track are drawn where the view has them
	var car := stage.get_node("Car") as RpgCar
	t.eq(car.z_index, IsoTrack.STANDING_Z)
	t.ok((car.position + (car.get_node("Visual") as Node2D).position).is_equal_approx(seen.to_screen(car.position)))
	var lying := stage.get_node("Pickups").get_child(0) as RpgRacePickup
	t.ok(lying.shown_position().is_equal_approx(seen.to_screen(lying.position)))
	var race := stage.get_node("Race") as RpgRace
	var shot := RpgRaceWeapon.fired(car, RpgRaceWeapon.MISSILE, TILE)
	stage.add_child(shot)
	t.ok(shot.shown_position().is_equal_approx(seen.to_screen(shot.position)), "a missile too")
	t.ok(race.line.along(car.position) < 0.0 and race.cars.size() == 4, "the race has its cars behind the line of the plan")
	# the camera is on the car as it is seen, and its track is the diamond of the field
	var camera := stage.get_node("Camera") as RpgRaceCamera
	t.ok(camera.position.is_equal_approx(seen.to_screen(car.position)))
	t.eq(camera.base_zoom, 2.0)
	t.ok(camera.track.is_equal_approx(seen.screen_rect(Rect2(Vector2.ZERO, Vector2(cells) * TILE)).grow(17.0)))
	_drop(stage)
	var fixed := _stage(track, 0, geo, false, true)
	var still := fixed.get_node("Camera") as RpgRaceCamera
	still.look_at_track()
	t.ok(still.fixed and still.position.is_equal_approx(still.track.get_center()), "a fixed camera is over the middle of the diamond")
	t.ok(still.track.size.x * still.zoom.x <= 640.01 and still.track.size.y * still.zoom.y <= 360.01, "all of which is on the screen")
	_drop(fixed)
	_cleanup()

func test_the_road_is_laid_from_the_pieces_along_the_loop(t) -> void:
	var geo := _geo(t, _with_road())
	t.eq(geo.iso.laid_pieces("ROAD").size(), 8, "a straight in two ways (each said twice), a corner in four")
	var stood := 0
	for raw: Variant in _planned():
		var track: Dictionary = raw
		var stage := _stage(track, 0, geo, true, false, 2)
		var seen := stage.get_node("View") as RpgRaceView
		t.eq(seen.cell_px, float(RaceBuild.BLOCK * TILE), "%s: a cell of the loop is a diamond" % track["id"])
		t.ok(stage.get_node_or_null("Road") == null, "no road is drawn")
		var ground := stage.get_node("Ground") as TileMapLayer
		t.eq([ground.scale, seen.footprint], [Vector2(2, 2), FOOT * 2], "the diamonds are enlarged, and the view counts with what is seen")
		var scenery := stage.get_node_or_null("Scenery")  # none on a track that fills its field
		for node in (scenery.get_children() if scenery != null else []):
			var picture := node as Sprite2D
			stood += 1
			t.eq(picture.scale, Vector2(2, 2), "what stands on them too")
			t.ok(picture.position.is_equal_approx(RpgIso.cell_to_screen(RpgIso.screen_to_cell(picture.position, FOOT * 2), FOOT * 2)), "on the middle of an enlarged diamond")
		var loop := JsonUtil.to_array(track["loop"])
		var corners := 0
		for i in loop.size():
			var cell := Vector2i(int(loop[i][0]), int(loop[i][1]))
			var before := Vector2i(int(loop[i - 1][0]), int(loop[i - 1][1]))
			var after := Vector2i(int(loop[(i + 1) % loop.size()][0]), int(loop[(i + 1) % loop.size()][1]))
			var sides: Array[String] = [IsoTrack.SIDE_OF[before - cell], IsoTrack.SIDE_OF[after - cell]]
			var piece := geo.iso.piece_for("ROAD", sides)
			t.ok(not piece.is_empty(), "the pack has the piece for %s" % [sides])
			var data := ground.get_cell_tile_data(cell)
			t.eq(data.get_custom_data("asset_id") if data != null else "", piece["asset_id"], "%s: the piece at %s joins %s" % [track["id"], cell, sides])
			var straight := before - cell == cell - after
			t.eq(str(piece["asset_id"]).begins_with(ROAD_STRAIGHT), straight, "a straight on a straight, the corner piece at a corner of the plan")
			corners += 0 if straight else 1
			# the middle of the block of the cell in the plan is the middle of its diamond as it is drawn
			var middle := (Vector2(cell) + Vector2(0.5, 0.5)) * RaceBuild.BLOCK * TILE + Vector2(TILE, TILE)
			t.ok(seen.to_screen(middle).is_equal_approx(ground.to_global(ground.map_to_local(cell))))
		t.ok(corners >= 4, "%s: %d corners" % [track["id"], corners])
		t.eq(geo.take_notes(), [] as Array[String], "every cell got the piece for exactly its sides")
		# a cell the loop does not use is plain ground, and so is the ring round the field
		var size := JsonUtil.to_array(track["cells"])
		var plain := 0
		for y in range(-1, int(size[1]) + 1):
			for x in range(-1, int(size[0]) + 1):
				if not loop.has([float(x), float(y)]) and not loop.has([x, y]):
					var data := ground.get_cell_tile_data(Vector2i(x, y))
					t.ok(data != null and not str(data.get_custom_data("asset_id")).begins_with("iso_tiles.png.isotile_01"), "ground at (%d, %d)" % [x, y])
					plain += 1
		t.ok(plain > 0)
		t.ok(stage.get_node("Marks").get_child_count() > 0, "the start line and what lies on the road are drawn over the pieces")
		_drop(stage)
	t.ok(stood > 0, "scenery stood on the unused cells of some track (%d)" % stood)
	_cleanup()

# ---------------------------------------------------------------- driving it

func test_a_lap_by_the_smokes_driver_is_the_lap_of_the_track_seen_from_above(t) -> void:
	var geo := _geo(t, _catalog())
	var tracks := _planned()
	t.eq(tracks.size(), 4, "the four tracks rpggen plans for seed 12345")
	for raw: Variant in tracks:
		var track: Dictionary = raw
		var gates := JsonUtil.to_array(track["checkpoints"]).size()
		var above := _stage(track, 0)
		var flat: Dictionary = _lap(above, track)
		_drop(above)
		var stage := _stage(track, 0, geo)
		var seen: Dictionary = _lap(stage, track)
		_drop(stage)
		t.eq(seen["laps"], 1, "%s: a lap in the isometric view (%d steps)" % [track["id"], seen["steps"]])
		t.eq([seen["gates"], seen["out_of_order"]], [gates, 0], "%s: through every checkpoint, in its order, where it lies" % track["id"])
		t.ok(int(seen["grass"]) * 10 < int(seen["steps"]), "%s: on the road (%d of %d steps on grass)" % [track["id"], seen["grass"], seen["steps"]])
		t.eq(seen["shown"], 0, "%s: the picture was where the view has the car, pointing its way, at every step" % track["id"])
		# the physics does not know the view: the same lap, step for step
		t.eq(seen["steps"], flat["steps"], "%s: in as many steps as seen from above" % track["id"])
		var a: PackedVector2Array = flat["path"]
		var b: PackedVector2Array = seen["path"]
		var apart := 0.0
		for i in mini(a.size(), b.size()):
			apart = maxf(apart, a[i].distance_to(b[i]))
		t.ok(apart < 0.001, "%s: and at the same places of the plan (%.6f px apart at most)" % [track["id"], apart])
	# with the stick as the heading, held the way the waypoint is seen
	var track: Dictionary = tracks[0]
	var stage := _stage(track, 0, geo)
	(stage.get_node("Car") as RpgCar).absolute_steering = true
	var stick: Dictionary = _lap(stage, track)
	_drop(stage)
	t.eq([stick["laps"], stick["gates"], stick["out_of_order"]], [1, JsonUtil.to_array(track["checkpoints"]).size(), 0], "absolute steering: a lap through every checkpoint (%d steps)" % stick["steps"])
	t.ok(int(stick["grass"]) * 10 < int(stick["steps"]), "on the road (%d of %d)" % [stick["grass"], stick["steps"]])
	_cleanup()

func test_a_rival_drives_the_same_lap_in_both_views(t) -> void:
	var geo := _geo(t, _catalog())
	var track: Dictionary = _planned()[2]
	var paths: Array[PackedVector2Array] = []
	for view: MapGeo in [null, geo]:
		var stage := _stage(track, 1, view)
		var race := stage.get_node("Race") as RpgRace
		var rival := stage.get_node("Rival1") as RpgCar
		var path := PackedVector2Array()
		var steps := 0
		while race.lap_of(rival) < 2 and steps < 60 * 90:
			rival.poll_input()
			rival.step(DT)
			race.advance(DT)
			steps += 1
			path.append(rival.position)
		t.eq(race.lap_of(rival), 2, "a lap in %d steps" % steps)
		paths.append(path)
		_drop(stage)
	t.eq(paths[0].size(), paths[1].size(), "the rival needs as many steps on diamonds as from above")
	var apart := 0.0
	for i in mini(paths[0].size(), paths[1].size()):
		apart = maxf(apart, paths[0][i].distance_to(paths[1][i]))
	t.ok(apart < 0.001, "and is at the same places of the plan (%.6f px apart at most)" % apart)
	_cleanup()

func test_the_table_of_the_physics_is_driven_under_the_view(t) -> void:
	# the drive of rpggen's table of cases (car_math.py: a start, a hard turn with a boost,
	# grass, oil, the brake), by a car on a track seen at an angle: it ends where the table says
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(CASES))
	t.ok(parsed is Array, "the table of cases is there")
	if not (parsed is Array):
		return
	var cases: Array = parsed
	t.eq([cases[-2]["fn"], cases[-1]["fn"]], ["drive", "drive_tuned"])
	await Fixtures.tree().process_frame
	var root := Node2D.new()
	var seen := _view()
	root.add_child(seen)
	var car := CarRecipe.build_car(_sheet(8, 24), Vector2i(24, 24), 8, TILE) as RpgCar
	car.input_node_enabled = false
	car.set_physics_process(false)
	root.add_child(car)
	Fixtures.tree().root.add_child(root)
	var from := Vector2(5000, 5000)
	car.place(from, -PI * 0.5)
	var legs: Array = cases[-2]["result"]
	for leg: Array in legs:
		car.surface_override = str(leg[3])
		car.surface = RpgCarPhysics.surface(str(leg[3]))  # on it already: no boost arrow is driven over
		if bool(leg[4]):
			car.boost_left = RpgCarPhysics.BOOST_S
		car.throttle = float(leg[1])
		car.steer = float(leg[2])
		for i in int(leg[0]):
			car.step(DT)
		var at := (car.position - from) / TILE
		t.near(at.x, float(leg[5]), 0.01, "x after the leg on %s" % leg[3])
		t.near(at.y, float(leg[6]), 0.01, "y after the leg on %s" % leg[3])
		t.near(RpgCarPhysics.angle_difference(car.heading, float(leg[7])), 0.0, 0.001, "the heading")
		t.near(car.velocity.x / TILE, float(leg[8]), 0.001)
		t.near(car.velocity.y / TILE, float(leg[9]), 0.001)
		t.ok((car.position + (car.get_node("Visual") as Node2D).position).is_equal_approx(seen.to_screen(car.position)), "and its picture is where the view has it")
	root.get_parent().remove_child(root)
	root.free()
