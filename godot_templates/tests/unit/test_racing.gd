extends RefCounted
## T16.12: the car of a racing game and its camera: the arithmetic rpggen shares, a car that
## reaches its top speed, turns more slowly at speed, is slower on grass, bumps off a barrier
## and drifts, the picture for sixteen headings, the camera that looks ahead, and the scenes
## the recipes build.

const Fixtures := preload("../lib/fixtures.gd")
const CarRecipe := preload("res://builder/recipes/racing/car_recipe.gd")
const TrackRecipe := preload("res://builder/recipes/racing/track_recipe.gd")
const RaceBuild := preload("res://builder/recipes/racing/racing_build.gd")
const HudRecipe := preload("res://builder/recipes/arcade/hud_recipe.gd")
const JsonUtil := preload("res://builder/lib/json_util.gd")

const CASES := "res://tests/unit/car_math_cases.json"
const TILE := 16
const VIEW := Vector2i(640, 360)
const DT := 1.0 / 60.0

class Field:
	var root: Node2D
	var car: RpgCar

	func frames(count: int) -> void:
		for i in count:
			await Engine.get_main_loop().physics_frame

	func drop() -> void:
		if root.get_parent() != null:
			root.get_parent().remove_child(root)
		root.free()

## An open field with one wall (a barrier across x = 400) and a car on it, pointing right.
func _field(surface: String = "road") -> Field:
	await Fixtures.tree().process_frame
	var field := Field.new()
	field.root = Node2D.new()
	var wall := StaticBody2D.new()
	wall.collision_layer = 1
	var shape := CollisionShape2D.new()
	var box := RectangleShape2D.new()
	box.size = Vector2(32, 2000)
	shape.shape = box
	wall.add_child(shape)
	wall.position = Vector2(416, 0)  # its face is at x = 400
	field.root.add_child(wall)
	field.car = CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE) as RpgCar
	field.car.input_node_enabled = false
	field.car.surface_override = surface
	field.car.heading = 0.0
	field.root.add_child(field.car)
	Fixtures.tree().root.add_child(field.root)
	await field.frames(2)
	return field

func _sheet(headings: int, cell: int) -> ImageTexture:
	var image := Image.create(cell * headings, cell, false, Image.FORMAT_RGBA8)
	image.fill(Color.RED)
	return ImageTexture.create_from_image(image)

# ---------------------------------------------------------------- the arithmetic

func _call(fn: String, args: Array) -> Variant:
	match fn:
		"surface":
			return RpgCarPhysics.surface(args[0])
		"grip":
			return RpgCarPhysics.grip(args[0])
		"top_speed":
			return RpgCarPhysics.top_speed(args[0], args[1])
		"accelerate":
			return RpgCarPhysics.accelerate(args[0], args[1], args[2], args[3], args[4])
		"turn_rate":
			return RpgCarPhysics.turn_rate(args[0])
		"turn":
			return RpgCarPhysics.turn(args[0], args[1], args[2], args[3], args[4])
		"slide":
			return RpgCarPhysics.slide(args[0], args[1], args[2])
		"is_drifting":
			return RpgCarPhysics.is_drifting(args[0])
		"split":
			return RpgCarPhysics.split(Vector2(args[0], args[1]), args[2])
		"join":
			return RpgCarPhysics.join(args[0], args[1], args[2])
		"bump":
			return RpgCarPhysics.bump(Vector2(args[0], args[1]), Vector2(args[2], args[3]))
		"heading_frame":
			return RpgCarPhysics.heading_frame(args[0], int(args[1]))
		"angle_difference":
			return RpgCarPhysics.angle_difference(args[0], args[1])
		"steer_toward":
			return RpgCarPhysics.steer_toward(args[0], args[1])
		"look_ahead":
			return RpgCarPhysics.look_ahead(Vector2(args[0], args[1]), args[2])
		"zoom_for":
			return RpgCarPhysics.zoom_for(args[0])
		"curve_speed":
			return RpgCarPhysics.curve_speed(args[0], args[1])
	return null

static func _same(got: Variant, expected: Variant) -> bool:
	if got is Vector2 and expected is Array:
		var pair: Array = expected
		var vector: Vector2 = got
		return pair.size() == 2 and absf(vector.x - float(pair[0])) <= 0.0001 and absf(vector.y - float(pair[1])) <= 0.0001
	if got is bool or got is String:
		return got == expected
	if (got is float or got is int) and (expected is float or expected is int):
		return absf(float(got) - float(expected)) <= 0.0001
	return false

func test_the_arithmetic_is_rpggens_over_a_table_of_cases(t) -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(CASES))
	t.ok(parsed is Array, "the table of cases is there")
	if not (parsed is Array):
		return
	var cases: Array = parsed
	t.ok(cases.size() > 300, "%d cases" % cases.size())
	var wrong: Array[String] = []
	var seen := {}
	for raw: Variant in cases:
		var case: Dictionary = raw
		var fn: String = case["fn"]
		seen[fn] = true
		if fn == "drive":
			continue
		var args: Array = case["args"]
		var got: Variant = _call(fn, args)
		if not _same(got, case["result"]) and wrong.size() < 5:
			wrong.append("%s%s gave %s, rpggen has %s" % [fn, args, got, case["result"]])
	t.eq(wrong, [] as Array[String])
	t.eq(seen.size(), 18, "every function of the model, and the drive")
	# the drive: a car that starts, turns hard with a boost, crosses grass and oil, brakes
	var state := {"x": 0.0, "y": 0.0, "heading": -PI * 0.5, "vx": 0.0, "vy": 0.0, "boost": 0.0}
	var legs: Array = cases[-1]["result"]
	t.eq(legs.size(), 6)
	for leg: Array in legs:
		if bool(leg[4]):
			state["boost"] = RpgCarPhysics.BOOST_S
		for i in int(leg[0]):
			state = RpgCarPhysics.step(state, leg[1], leg[2], leg[3], DT)
		var keys := ["x", "y", "heading", "vx", "vy", "lateral"]
		for k in keys.size():
			var got: float = state[keys[k]]
			t.near(got, float(leg[5 + k]), 0.001, "%s after the leg on %s" % [keys[k], leg[3]])

func test_what_the_ground_does_to_a_car(t) -> void:
	t.ok(RpgCarPhysics.grip("road") > RpgCarPhysics.grip("dirt"))
	t.ok(RpgCarPhysics.grip("dirt") > RpgCarPhysics.grip("grass"))
	t.ok(RpgCarPhysics.grip("grass") > RpgCarPhysics.grip("oil"))
	t.ok(RpgCarPhysics.top_speed("grass") < RpgCarPhysics.top_speed("road"))
	t.eq(RpgCarPhysics.top_speed("oil"), RpgCarPhysics.TOP, "oil is fast, and slippery")
	t.eq(RpgCarPhysics.surface("Asphalt "), "road", "the names a pack has for its ground")
	t.eq(RpgCarPhysics.surface("sand"), "dirt")
	t.eq(RpgCarPhysics.surface("nothing known"), "road")
	t.ok(RpgCarPhysics.turn_rate(1.0) > RpgCarPhysics.turn_rate(RpgCarPhysics.TOP), "a slow car turns faster")
	t.eq(RpgCarPhysics.turn_rate(0.0), 0.0, "a car that stands does not turn")
	t.ok(RpgCarPhysics.turn_rate(-2.0) < 0.0, "in reverse the wheel turns it the other way")
	t.ok(RpgCarPhysics.curve_speed(2.0) < RpgCarPhysics.curve_speed(6.0), "a tight curve is taken slowly")

# ---------------------------------------------------------------- the car

func test_the_car_reaches_its_top_speed_and_brakes(t) -> void:
	var field := await _field()
	var car := field.car
	car.position = Vector2(-2000, 0)
	car.throttle = 1.0
	await field.frames(60)
	t.near(car.speed_tiles(), RpgCarPhysics.ACCEL, 0.3, "a second of the pedal")
	t.ok(car.velocity.x > 0.0 and absf(car.velocity.y) < 0.01, "it goes the way it points")
	await field.frames(60)
	t.near(car.speed_tiles(), RpgCarPhysics.TOP, 0.01, "the top speed, and no more")
	car.throttle = 0.0
	await field.frames(30)
	t.ok(car.speed_tiles() < RpgCarPhysics.TOP and car.speed_tiles() > 0.0, "it rolls out")
	car.throttle = -1.0
	await field.frames(40)
	t.ok(car.speed_tiles() <= 0.0, "the brake stops it")
	await field.frames(60)
	t.near(car.speed_tiles(), -RpgCarPhysics.TOP * RpgCarPhysics.REVERSE, 0.01, "and then reverses it, slowly")
	# a boost
	car.place(Vector2(-2000, 0), 0.0)
	t.eq(car.boosts, 3)
	var boosted := [0]
	car.boosted.connect(func() -> void: boosted[0] += 1)
	car.throttle = 1.0
	car.press_boost()
	await field.frames(50)
	t.ok(car.speed_tiles() > RpgCarPhysics.TOP, "a boost is faster than the top speed (%f)" % car.speed_tiles())
	t.eq([car.boosts, boosted[0]], [2, 1])
	car.press_boost()
	await field.frames(2)
	t.eq(car.boosts, 2, "no second boost while one lasts")
	await field.frames(150)
	t.ok(not car.is_boosting())
	t.near(car.speed_tiles(), RpgCarPhysics.TOP, 0.01, "after it the car is back at its top speed")
	t.ok(car.add_boost() and car.boosts == 3, "a boost can be picked up")
	field.drop()

func test_the_car_turns_more_slowly_at_speed(t) -> void:
	var field := await _field()
	var car := field.car
	car.position = Vector2(-3000, 0)
	car.steer = 1.0
	await field.frames(20)
	t.near(car.heading, 0.0, 0.0001, "a car that stands does not turn")
	# slow: a little of the pedal
	car.throttle = 0.3
	await field.frames(40)
	var slow_speed := car.speed_tiles()
	var from := car.heading
	await field.frames(10)
	var slow := RpgCarPhysics.angle_difference(from, car.heading)
	t.ok(slow > 0.0, "the wheel to the right turns the car clockwise")
	# fast
	car.place(Vector2(-3000, 0), 0.0)
	car.steer = 0.0
	car.throttle = 1.0
	await field.frames(120)
	car.steer = 1.0
	from = car.heading
	await field.frames(10)
	var fast := RpgCarPhysics.angle_difference(from, car.heading)
	t.ok(slow_speed < 4.0 and fast < slow, "ten steps turn %f rad at %f tiles a second and %f at the top speed" % [slow, slow_speed, fast])
	# absolute steering: the stick is the heading
	car.place(Vector2(-3000, 0), 0.0)
	car.absolute_steering = true
	car.steer = 0.0
	car.stick = Vector2.DOWN
	car.throttle = 0.6
	await field.frames(150)
	t.near(car.heading, PI * 0.5, 0.05, "the car heads where the stick points")
	car.stick = Vector2.ZERO
	from = car.heading
	await field.frames(20)
	t.near(car.heading, from, 0.0001, "and goes straight on when it is let go")
	field.drop()

func test_the_car_is_slower_on_grass_and_drifts(t) -> void:
	var field := await _field("grass")
	var car := field.car
	car.position = Vector2(-3000, 0)
	car.throttle = 1.0
	await field.frames(120)
	t.near(car.speed_tiles(), RpgCarPhysics.top_speed("grass"), 0.01, "the top speed of grass")
	t.eq(car.surface, "grass")
	var seen: Array[String] = []
	car.surface_changed.connect(func(surface: String) -> void: seen.append(surface))
	car.surface_override = "road"
	await field.frames(120)
	t.eq(seen, ["road"] as Array[String])
	t.near(car.speed_tiles(), RpgCarPhysics.TOP, 0.01, "back on the road it is fast again")
	# a hard turn at the top speed: the car slides
	t.ok(not car.drifting, "straight ahead nothing slides")
	var drifts := [0]
	car.drift_started.connect(func() -> void: drifts[0] += 1)
	car.surface_override = "grass"
	car.steer = 1.0
	await field.frames(30)
	t.ok(car.drifting and drifts[0] == 1, "a hard turn at speed on grass is a drift (%f sideways)" % car.lateral_tiles())
	t.ok(absf(car.lateral_tiles()) > RpgCarPhysics.DRIFT_FROM * RpgCarPhysics.TOP)
	t.ok(car.velocity.normalized().dot(car.forward()) < 0.97, "it does not go where it points")
	car.steer = 0.0
	car.surface_override = "road"
	await field.frames(40)
	t.ok(not car.drifting and absf(car.lateral_tiles()) < 0.01, "on the road, straight, the slide ends")
	# a boost arrow of the track
	car.surface_override = "boost"
	await field.frames(2)
	t.ok(car.is_boosting() and car.boosts == 3, "a boost arrow boosts, and costs none of the car's own")
	field.drop()

func test_the_car_bumps_off_a_barrier(t) -> void:
	var field := await _field()
	var car := field.car
	car.position = Vector2(200, 0)
	car.throttle = 1.0
	var lost: Array[float] = []
	car.bumped.connect(func(tiles: float) -> void: lost.append(tiles))
	var fastest := [0.0]
	for i in 240:
		fastest[0] = maxf(fastest[0], car.speed_tiles())
		if not lost.is_empty():
			break
		await Engine.get_main_loop().physics_frame
	t.eq(lost.size(), 1, "the car meets the wall")
	t.ok(fastest[0] > 5.0 and lost[0] > fastest[0] * 0.5, "a bump straight on costs most of the speed (%f of %f)" % [lost[0] if not lost.is_empty() else 0.0, fastest[0]])
	t.ok(car.velocity.x < 0.0, "it comes back off the wall")
	t.ok(car.position.x < 400.0, "and is not in it")
	# along the wall the car scrapes on
	car.place(Vector2(380, 0), PI * 0.5 - 0.15)
	car.throttle = 1.0
	lost.clear()
	await field.frames(90)
	t.ok(car.position.y > 100.0, "at a flat angle the car goes on along the wall (%s)" % car.position)
	t.ok(car.position.x < 400.0)
	field.drop()

# ---------------------------------------------------------------- the picture and the camera

func test_the_picture_has_a_frame_for_each_of_sixteen_headings(t) -> void:
	var car := CarRecipe.build_car(_sheet(16, 24), Vector2i(24, 24), 16, TILE) as RpgCar
	var visual := car.get_node("Visual") as RpgHeadingSprite
	t.eq([visual.hframes, visual.vframes, visual.headings], [16, 1, 16])
	var frames := {}
	for k in 16:
		var heading := -PI * 0.5 + k * TAU / 16.0
		visual.show_heading(heading)
		t.eq(visual.frame, k, "heading %d of 16" % k)
		t.eq(visual.rotation, 0.0)
		frames[visual.frame] = true
		# a little off a heading is still its frame
		t.eq(visual.frame_for(heading + 0.15), k)
		t.eq(visual.frame_for(heading - 0.15), k)
	t.eq(frames.size(), 16)
	t.eq(visual.frame_for(0.0), 4, "to the right is a quarter of the way round")
	t.eq(visual.frame_for(PI * 0.5), 8, "down is half")
	# the car shows its heading
	Fixtures.tree().root.add_child(car)
	car.place(Vector2.ZERO, PI)
	t.eq(visual.frame, 12, "to the left")
	car.get_parent().remove_child(car)
	car.free()
	# one picture is rotated
	var single := CarRecipe.build_car(_sheet(1, 24), Vector2i(24, 24), 1, TILE) as RpgCar
	var one := single.get_node("Visual") as RpgHeadingSprite
	one.show_heading(0.0)
	t.eq(one.frame, 0)
	t.near(one.rotation, PI * 0.5, 0.0001, "a picture drawn pointing up, turned to the right")
	one.show_heading(-PI * 0.5)
	t.near(one.rotation, 0.0, 0.0001)
	single.free()
	# and a game without a picture has a drawn car
	var drawn := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE)
	t.ok(drawn.get_node("Visual") is Polygon2D)
	t.ok(drawn.get_node("Body") is CollisionShape2D and drawn.get_node("Input") != null)
	drawn.free()
	var rival := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE, false) as RpgCar
	t.ok(not rival.is_player and rival.get_node_or_null("Input") == null, "a car that is not the player's reads no input")
	rival.free()

func test_the_camera_leads_the_velocity(t) -> void:
	var field := await _field()
	var car := field.car
	car.position = Vector2(-3000, 0)
	var camera := RpgRaceCamera.new()
	camera.auto_advance = false
	camera.view = Vector2(VIEW)
	field.root.add_child(camera)
	camera.target_path = camera.get_path_to(car)
	camera.snap()
	t.eq(camera.position, car.position, "over a car that stands")
	t.eq(camera.zoom, Vector2.ONE)
	car.velocity = Vector2(RpgCarPhysics.TOP * TILE, 0.0)
	t.near(camera.wanted().x - car.position.x, 360.0 * RpgCarPhysics.LEAD, 0.01, "a quarter of the screen ahead at the top speed")
	t.near(camera.wanted().y, car.position.y, 0.01)
	t.near(camera.wanted_zoom(), RpgCarPhysics.ZOOM_FAR, 0.0001)
	car.velocity = Vector2(0.0, -RpgCarPhysics.TOP * TILE * 0.5)
	t.near(car.position.y - camera.wanted().y, 360.0 * RpgCarPhysics.LEAD * 0.5, 0.01, "half as far at half the speed, the way the car moves")
	for i in 120:
		camera.advance(DT)
	t.near(camera.position.y, camera.wanted().y, 0.5, "the camera gets there")
	t.ok(camera.zoom.x < 1.0 and camera.zoom.x > RpgCarPhysics.ZOOM_FAR)
	# a fixed camera shows the whole track and stays
	camera.fixed = true
	camera.track = Rect2(0, 0, 1280, 480)
	camera.look_at_track()
	t.eq(camera.position, Vector2(640, 240))
	t.near(camera.zoom.x, 0.5, 0.0001, "the whole track on the screen")
	camera.advance(1.0)
	t.eq(camera.position, Vector2(640, 240))
	field.drop()

# ---------------------------------------------------------------- the track

func test_the_test_track_is_a_ring_of_road_with_barriers(t) -> void:
	var rows := TrackRecipe.test_rows()
	var cells := RaceBuild.TRACK_CELLS
	t.eq([rows.size(), rows[0].length()], [cells.y, cells.x])
	t.eq(rows[0], "g".repeat(cells.x), "grass round the ring")
	var m := RaceBuild.TRACK_MARGIN
	var w := RaceBuild.ROAD_WIDTH
	t.eq(rows[m].count("r"), cells.x - 2 * m, "the top straight")
	t.eq(rows[cells.y / 2].count("r"), 2 * w, "two straights at the sides")
	t.eq(rows[cells.y / 2][m + w], "g", "grass in the middle")
	var car_scene := PackedScene.new()
	var made := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE)
	car_scene.pack(made)
	made.free()
	var start := TrackRecipe.test_start(TILE)
	var track := TrackRecipe.build_track(0, TrackRecipe.test_track(TILE), VIEW, TILE, rows, TrackRecipe.test_barriers(), start, null, {}, car_scene) as RpgArcadeStage
	t.ok(track != null, "a track is an arcade stage")
	var surfaces := track.get_node("Surfaces") as RpgTrackSurfaces
	t.eq(surfaces.size_cells(), cells)
	t.eq(surfaces.at_cell(Vector2i(m, m)), "road")
	t.eq(surfaces.at_cell(Vector2i(0, 0)), "grass")
	t.eq(surfaces.at_cell(Vector2i(-5, 2)), "grass", "outside the track is grass")
	t.eq(surfaces.bounds(), Rect2(Vector2.ZERO, Vector2(cells) * TILE))
	var car := track.get_node("Car") as RpgCar
	t.eq(car.position, start)
	Fixtures.tree().root.add_child(track)
	t.eq(surfaces.at(start), "road", "the car starts on the road")
	t.eq(car.surface_here(), "road", "and knows it")
	car.position = Vector2(TILE * 2.5, TILE * 10.0)
	t.eq(car.surface_here(), "grass")
	var camera := track.get_node("Camera") as RpgRaceCamera
	t.ok(camera != null and camera.target() == car, "the camera of the stage is the race camera, on the car")
	t.ok(track.scroller().camera() == null, "the scroller leaves it alone")
	t.eq(track.get_node("Barriers").get_child_count(), 10, "five barriers, each a shape and a picture")
	t.eq([track.exit_condition, track.scroller().axis], ["custom", "none"])
	track.get_parent().remove_child(track)
	track.free()
	# a fixed camera
	var still := TrackRecipe.build_track(0, TrackRecipe.test_track(TILE), VIEW, TILE, rows, TrackRecipe.test_barriers(), start, null, {}, car_scene, true)
	var fixed := still.get_node("Camera") as RpgRaceCamera
	t.ok(fixed.fixed)
	t.eq(fixed.position, Vector2(cells) * TILE * 0.5)
	still.free()

func test_the_hud_shows_the_speed_and_the_boosts(t) -> void:
	t.eq(HudRecipe.script_for("racing"), "res://addons/rpg_runtime/archetypes/racing/ui/racing_hud.gd")
	var hud := HudRecipe.build_hud(HudRecipe.script_for("racing")) as RpgRacingHud
	Fixtures.tree().root.add_child(hud)
	var car := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE) as RpgCar
	car.heading = 0.0
	car.velocity = Vector2(8.0 * TILE, 0.0)
	hud.show_car(car)
	t.eq(hud.row_text("speed"), "Speed: 120")
	t.eq(hud.row_text("boosts"), "Boosts: 3")
	hud.show_car(null)
	t.eq(hud.row_text("speed"), "")
	car.free()
	hud.get_parent().remove_child(hud)
	hud.free()

# ---------------------------------------------------------------- a planned track (T16.13)

## A tile set of four tiles: a road with a white line down its middle, grass, plain asphalt
## and a red barrier on asphalt.
func _road_tiles() -> TileSet:
	var image := Image.create(TILE * 4, TILE, false, Image.FORMAT_RGBA8)
	var asphalt := Color8(70, 70, 78)
	image.fill(asphalt)
	for y in TILE:
		image.set_pixel(8, y, Color.WHITE)
		for x in TILE:
			image.set_pixel(TILE + x, y, Color8(76, 150, 70))
	for x in TILE:
		image.set_pixel(TILE * 3 + x, 7, Color8(200, 40, 40))
	var tiles := TileSet.new()
	tiles.tile_size = Vector2i(TILE, TILE)
	var src := TileSetAtlasSource.new()
	src.texture = ImageTexture.create_from_image(image)
	src.texture_region_size = Vector2i(TILE, TILE)
	tiles.add_source(src, 0)
	for x in 4:
		src.create_tile(Vector2i(x, 0))
	return tiles

func test_the_road_is_painted_with_the_plainest_tile_of_its_sheet(t) -> void:
	var tiles := _road_tiles()
	var plain := TrackRecipe.plain_tile(tiles, 0)
	t.eq(plain, {"source_id": 0, "coords": Vector2i(2, 0)}, "plain asphalt: not the line, not the grass, not the barrier")
	t.eq(TrackRecipe.plain_tile(tiles, 5), {}, "no such sheet")
	# a sheet without a grey tile: its first
	var image := Image.create(TILE * 2, TILE, false, Image.FORMAT_RGBA8)
	image.fill(Color8(76, 150, 70))
	var green := TileSet.new()
	green.tile_size = Vector2i(TILE, TILE)
	var src := TileSetAtlasSource.new()
	src.texture = ImageTexture.create_from_image(image)
	src.texture_region_size = Vector2i(TILE, TILE)
	green.add_source(src, 0)
	src.create_tile(Vector2i(0, 0))
	src.create_tile(Vector2i(1, 0))
	t.eq(TrackRecipe.plain_tile(green, 0), {"source_id": 0, "coords": Vector2i(0, 0)})

func test_a_planned_track_has_its_start_its_marks_its_tyres_and_its_pickups(t) -> void:
	# a field of 12 by 7 cells: a road along it with a start line, dirt, oil and a boost arrow
	var rows := PackedStringArray([
		"gggggggggggg",
		"gggggggggggg",
		"grsrddrorbrg",
		"grsrddrrrbrg",
		"grsrrrrrrbrg",
		"gggggggggggg",
		"gggggggggggg",
	])
	var barriers: Array[Rect2i] = [Rect2i(0, 0, 12, 1), Rect2i(4, 5, 6, 2)]
	var car_scene := PackedScene.new()
	var made := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE)
	car_scene.pack(made)
	made.free()
	var tiles := _road_tiles()
	var start := Vector2(24, 56)
	var look := {
		"heading": 0.0,
		"tyres": [[24.0, 24.0], [168.0, 24.0]],
		"decoration": [[100.0, 100.0]],
		"pickups": [{"position": [120.0, 56.0], "kind": "missile"}],
	}
	var track := TrackRecipe.build_track(1, TrackRecipe.test_track(TILE), VIEW, TILE, rows, barriers, start, tiles,
		TrackRecipe.plain_tile(tiles, 0), car_scene, false, look) as RpgArcadeStage
	t.eq(track.stage_index, 1)
	var ground := track.get_node("Ground") as TileMapLayer
	t.eq(ground.get_used_cells().size(), 30, "every cell of the road has a tile")
	t.eq(ground.get_cell_atlas_coords(Vector2i(1, 2)), Vector2i(2, 0), "the plain one")
	t.eq(ground.get_cell_source_id(Vector2i(0, 0)), -1, "none on the grass")
	t.ok(track.get_node_or_null("Road") == null, "a painted road is not drawn")
	# over the road: the line, the dirt, the oil and the arrow, a rectangle a run of cells
	var marks := track.get_node("Marks")
	var names: Array[String] = []
	for mark in marks.get_children():
		names.append(String(mark.name))
	names.sort()
	t.eq(names, ["Mark_b_9_2", "Mark_b_9_3", "Mark_b_9_4", "Mark_d_4_2", "Mark_d_4_3", "Mark_o_7_2", "Mark_s_2_2", "Mark_s_2_3", "Mark_s_2_4"] as Array[String])
	var dirt := marks.get_node("Mark_d_4_2") as Polygon2D
	t.eq(dirt.polygon[0], Vector2(64, 32))
	t.eq(dirt.polygon[2], Vector2(96, 48), "two cells of dirt, one rectangle")
	var surfaces := track.get_node("Surfaces") as RpgTrackSurfaces
	t.eq([surfaces.at_cell(Vector2i(2, 2)), surfaces.at_cell(Vector2i(4, 2)), surfaces.at_cell(Vector2i(7, 2)), surfaces.at_cell(Vector2i(9, 2))],
		["road", "dirt", "oil", "boost"], "the start line is road")
	# barriers: a wall at the edge, a hedge over a cell the loop does not use; and the tyres
	var walls := track.get_node("Barriers")
	t.eq((walls.get_node("Wall0") as Polygon2D).color, TrackRecipe.WALL)
	t.eq((walls.get_node("Wall1") as Polygon2D).color, TrackRecipe.HEDGE)
	t.ok((walls.get_node("Tyre1") as CollisionShape2D).shape is CircleShape2D)
	t.eq((walls.get_node("Tyre1") as CollisionShape2D).position, Vector2(168, 24))
	t.ok(walls.get_node("TyrePicture0") is Polygon2D, "a drawn tyre without a picture of one")
	t.ok(track.get_node_or_null("Scenery") == null, "no scenery without pictures for it")
	var pickup := track.get_node("Pickups/Pickup1") as Marker2D
	t.eq(pickup.position, Vector2(120, 56))
	t.eq(pickup.get_meta("kind"), "missile")
	var car := track.get_node("Car") as RpgCar
	t.eq(car.position, start)
	t.eq(car.heading, 0.0, "the car points the way the race goes")
	# the car drives over what the plan put on the road
	Fixtures.tree().root.add_child(track)
	car.input_node_enabled = false
	var seen: Array[String] = []
	car.surface_changed.connect(func(surface: String) -> void: seen.append(surface))
	car.throttle = 1.0
	for i in 200:
		await Engine.get_main_loop().physics_frame
		if car.position.x > 170.0:
			break
	t.eq(seen, ["dirt", "road", "boost", "road"] as Array[String], "dirt, the road again, the arrow (it passes below the oil)")
	t.ok(car.is_boosting() and car.boosts == 3, "the arrow boosted it")
	track.get_parent().remove_child(track)
	track.free()
	# with pictures: the tyre of the pack, and scenery on the hedges; a drawn road and line
	look["tyre_texture"] = _sheet(1, 16)
	look["decoration_textures"] = [_sheet(1, 16)]
	var drawn := TrackRecipe.build_track(0, TrackRecipe.test_track(TILE), VIEW, TILE, rows, barriers, start, null, {}, car_scene, false, look)
	t.ok(drawn.get_node("Barriers/TyrePicture0") is Sprite2D)
	t.eq(drawn.get_node("Scenery").get_child_count(), 1)
	t.eq(drawn.get_node("Road").get_child_count(), 3, "a drawn road: a rectangle a row")
	t.eq((drawn.get_node("Ground") as TileMapLayer).get_used_cells().size(), 0)
	t.ok(drawn.get_node("Marks/Mark_s_2_2") != null)
	drawn.free()
	# the test track knows its way round too
	var ring := TrackRecipe.test_track(TILE)
	t.eq(JsonUtil.to_array(ring["waypoints"]).size(), 5, "four corners and the start")
	t.eq(JsonUtil.to_dict(ring["start"])["heading"], -PI * 0.5)
