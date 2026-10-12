extends RefCounted
## T16.15: the championship of a racing game (points, the table, elimination, the save), the
## screen of results after a race, and the race HUD with its sign and its map of the track.

const Fixtures := preload("../lib/fixtures.gd")
const CarRecipe := preload("res://builder/recipes/racing/car_recipe.gd")
const RivalRecipes := preload("res://builder/recipes/racing/rival_recipes.gd")
const TrackRecipe := preload("res://builder/recipes/racing/track_recipe.gd")
const HudRecipe := preload("res://builder/recipes/racing/hud_recipe.gd")
const ArcadeHud := preload("res://builder/recipes/arcade/hud_recipe.gd")
const JsonUtil := preload("res://builder/lib/json_util.gd")

## The tracks of track_plan.plan({}, 12345): tests/unit/test_track_plan.py keeps the file.
const TRACKS := "res://tests/unit/track_plan_cases.json"
const SAVE_DIR := "user://test_championship"
const TILE := 16
const VIEW := Vector2i(640, 360)
const ME := RpgChampionship.PLAYER

## A race as a championship is told of it: the drivers in the order they came in.
static func _race(order: Array[String]) -> Array:
	var out: Array = []
	for driver in order:
		out.append({"driver": driver, "finished": driver == order[0] or driver == ME, "time_s": 60.0 + out.size()})
	return out

static func _points(table: Array[Dictionary]) -> Array:
	var out: Array = []
	for row in table:
		out.append([row["driver"], row["points"]])
	return out

func _drop(node: Node) -> void:
	if node.get_parent() != null:
		node.get_parent().remove_child(node)
	node.free()

# ---------------------------------------------------------------- the championship

func test_a_place_is_worth_points_and_the_table_is_by_points(t) -> void:
	t.eq([RpgChampionship.points_for(1), RpgChampionship.points_for(2), RpgChampionship.points_for(6)], [10, 6, 1])
	t.eq([RpgChampionship.points_for(7), RpgChampionship.points_for(0)], [0, 0], "no points behind the sixth")
	var cup := RpgChampionship.new()
	t.eq([cup.table().size(), cup.leader(), cup.place_of(ME)], [0, "", 0], "nothing before the first race")
	var rows := cup.record(_race([ME, "rival_1", "rival_2", "rival_3"]))
	t.eq(rows.size(), 4)
	t.eq([rows[0]["driver"], rows[0]["place"], rows[0]["player"], rows[0]["points"], rows[0]["total"]], [ME, 1, true, 10, 10])
	t.eq([rows[3]["driver"], rows[3]["place"], rows[3]["player"], rows[3]["points"], rows[3]["finished"]], ["rival_3", 4, false, 3, false])
	t.eq(_points(cup.table()), [[ME, 10], ["rival_1", 6], ["rival_2", 4], ["rival_3", 3]])
	# the same points: the one who was better in the last race is ahead
	cup.record(_race(["rival_1", ME, "rival_3", "rival_2"]))
	t.eq(_points(cup.table()), [["rival_1", 16], [ME, 16], ["rival_3", 7], ["rival_2", 7]])
	t.eq([cup.place_of(ME), cup.leader()], [2, "rival_1"])
	rows = cup.record(_race(["rival_2", "rival_3", "rival_1", ME]))
	t.eq([rows[3]["points"], rows[3]["total"]], [3, 19])
	cup.record(_race([ME, "rival_2", "rival_1", "rival_3"]))
	t.eq(_points(cup.table()), [[ME, 29], ["rival_1", 24], ["rival_2", 23], ["rival_3", 16]])
	t.eq([cup.races, cup.last_count, cup.leader()], [4, 1, ME])
	var places: Array = []
	for row in cup.table():
		places.append(row["place"])
	t.eq(places, [1, 2, 3, 4])
	# what is saved is the same championship again
	var data := cup.to_data()
	var parsed: Variant = JSON.parse_string(JSON.stringify(data))
	var again := RpgChampionship.new()
	again.from_data(parsed as Dictionary)
	t.eq(_points(again.table()), _points(cup.table()), "through a save file and back")
	t.eq([again.races, again.last_count], [4, 1])
	again.record(_race(["rival_3", "rival_1", "rival_2", ME]))
	t.eq(again.points_of("rival_3"), 26)
	again.from_data({})
	t.eq([again.races, again.table().size()], [0, 0], "a new run")
	# a row that names nobody, and a driver that is in a race twice
	var odd := RpgChampionship.new()
	t.eq(odd.record([{"place": 1}, "x"]).size(), 0)
	t.eq(odd.races, 0, "a race without drivers is none")
	t.eq(odd.record(_race([ME, "rival_1", ME])).size(), 2)

func test_last_twice_is_out_when_the_game_says_so(t) -> void:
	var cup := RpgChampionship.new()
	cup.elimination = true
	cup.record(_race(["rival_1", "rival_2", ME]))
	t.ok(not cup.is_eliminated(), "once is not twice")
	cup.record(_race([ME, "rival_1", "rival_2"]))
	cup.record(_race(["rival_2", ME, "rival_1"]))
	t.eq(cup.last_count, 1)
	cup.record(_race(["rival_2", "rival_1", ME]))
	t.ok(cup.is_eliminated(), "twice, not in a row")
	var soft := RpgChampionship.new()
	for i in 3:
		soft.record(_race(["rival_1", ME]))
	t.eq(soft.last_count, 3)
	t.ok(not soft.is_eliminated(), "not without the option")
	var alone := RpgChampionship.new()
	alone.elimination = true
	for i in 3:
		alone.record(_race([ME]))
	t.eq([alone.last_count, alone.points_of(ME)], [0, 30], "a car that races alone is the first, not the last")

func test_a_driver_is_the_player_or_a_rival_by_its_number(t) -> void:
	var mine := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE) as RpgCar
	var other := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE, false) as RpgCar
	other.name = "Rival3"
	t.eq([RpgChampionship.driver_of(mine), RpgChampionship.driver_of(other)], [ME, "rival_3"])
	t.eq([RpgChampionship.driver_name(ME), RpgChampionship.driver_name("rival_3")], ["You", "Rival 3"])
	# the standings of a race name the cars
	var cup := RpgChampionship.new()
	var rows := cup.record([{"car": other, "place": 1, "finished": true, "time_s": 50.0}, {"car": mine, "place": 2, "finished": true, "time_s": 51.5}])
	t.eq([rows[0]["driver"], rows[1]["driver"], rows[1]["time_s"]], ["rival_3", ME, 51.5])
	mine.free()
	other.free()

# ---------------------------------------------------------------- the results

func test_the_results_list_the_race_the_parts_and_the_table(t) -> void:
	t.eq([RpgRaceResults.time_text(83.456), RpgRaceResults.time_text(5.0), RpgRaceResults.time_text(600.0)], ["1:23.46", "0:05.00", "10:00.00"])
	var cup := RpgChampionship.new()
	cup.record(_race([ME, "rival_1", "rival_2"]))
	var rows := cup.record(_race(["rival_2", ME, "rival_1"]))
	t.eq(RpgRaceResults.race_lines(rows), [
		PackedStringArray(["1.", "Rival 2", "1:00.00", "+10"]),
		PackedStringArray(["2.", "You", "1:01.00", "+6"]),
		PackedStringArray(["3.", "Rival 1", "-", "+4"]),
	] as Array[PackedStringArray], "a car that had not finished has no time")
	t.eq(RpgRaceResults.table_lines(cup.table()), [
		PackedStringArray(["1.", "You", "16"]),
		PackedStringArray(["2.", "Rival 2", "14"]),
		PackedStringArray(["3.", "Rival 1", "10"]),
	] as Array[PackedStringArray])
	t.eq(RpgRaceResults.parts_text([] as Array[String]), "")
	t.eq(RpgRaceResults.parts_text(["speed", "tyres"] as Array[String]), "Parts won: Speed, Tyres")
	t.eq(RpgRaceResults.heading_text("Track 2", cup.table(), false, false), "Track 2: results")
	t.eq(RpgRaceResults.heading_text("Track 4", cup.table(), true, false), "Champion: You")
	t.eq(RpgRaceResults.heading_text("Track 2", cup.table(), false, true), "Last twice: you are out")
	var screen := RpgRaceResults.new()
	Fixtures.tree().root.add_child(screen)
	screen.set_process(false)
	screen.show_results("Track 2", rows, ["acceleration"] as Array[String], cup.table())
	t.eq(screen.heading_shown(), "Track 2: results")
	t.eq(screen.grid_texts("Race"), RpgRaceResults.race_lines(rows))
	t.eq(screen.grid_texts("Table"), RpgRaceResults.table_lines(cup.table()))
	t.eq((screen.get_node("Center/Box/Parts") as Label).text, "Parts won: Acceleration")
	t.eq((screen.get_node("Center/Box/Halves/Table/Title") as Label).text, "Championship")
	var closed := [0]
	screen.finished.connect(func() -> void: closed[0] += 1)
	screen._process(RpgRaceResults.HOLD_S - 0.1)
	t.eq(closed[0], 0)
	screen._process(0.2)
	screen.close()
	t.eq(closed[0], 1, "it closes by itself, once")
	_drop(screen)

# ---------------------------------------------------------------- the run

func _planned() -> Array:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(TRACKS))
	if parsed is Dictionary:
		var plan: Dictionary = parsed
		return JsonUtil.to_array(plan.get("list", []))
	return []

## The scene of planned track `index` with three rivals, in the tree; nothing in it moves.
func _track(index: int, track: Dictionary) -> RpgArcadeStage:
	var car_scene := PackedScene.new()
	var made := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE)
	car_scene.pack(made)
	made.free()
	var rival_scenes: Array = []
	for i in 3:
		var packed := PackedScene.new()
		var rival := RivalRecipes.build_rival(i + 1, null, Vector2i(24, 24), 1, TILE)
		packed.pack(rival)
		rival.free()
		rival_scenes.append(packed)
	var rows := PackedStringArray(JsonUtil.to_array(track["rows"]))
	var begin := JsonUtil.to_dict(track["start"])
	var at := JsonUtil.to_array(begin["position"])
	var look := {"heading": float(begin["heading"]), "tyres": [], "pickups": [], "rival_scenes": rival_scenes}
	var stage := TrackRecipe.build_track(index, track, VIEW, TILE, rows, [] as Array[Rect2i], Vector2(float(at[0]), float(at[1])), null, {}, car_scene, false, look) as RpgArcadeStage
	stage.auto_advance = false
	Fixtures.tree().root.add_child(stage)
	(stage.get_node("Race") as RpgRace).auto_advance = false
	for node in stage.find_children("*", "CharacterBody2D", true, false):
		(node as RpgCar).set_physics_process(false)
	(stage.get_node("Camera") as RpgRaceCamera).auto_advance = false
	return stage

func _saves() -> void:
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER)
	save.dir = SAVE_DIR
	if DirAccess.dir_exists_absolute(SAVE_DIR):
		for file: String in DirAccess.get_files_at(SAVE_DIR):
			DirAccess.remove_absolute(SAVE_DIR.path_join(file))

func _mode(tracks: Array) -> RpgRacingMode:
	var mode := RpgRacingMode.new()
	mode.auto_screens = true
	Fixtures.tree().root.add_child(mode)
	mode.sequence = RpgArcadeStageSequence.from_array(tracks)
	return mode

## Ends the race of the track `mode` is on with the cars in `order` ("player", "rival_2", ...).
func _finish(mode: RpgRacingMode, order: Array[String]) -> void:
	var standings: Array = []
	for driver in order:
		for car in mode.race.cars:
			if RpgChampionship.driver_of(car) == driver:
				standings.append({"car": car, "place": standings.size() + 1, "player": car.is_player, "finished": true, "time_s": 70.0 + standings.size()})
	mode.race.finished.emit(standings)
	mode.stage.advance(1.0 / 60.0)  # the stage ends on its next step

func test_a_championship_of_four_races_is_counted_and_saved(t) -> void:
	await Fixtures.tree().process_frame
	var state := Fixtures.install_state() as RpgGameState
	_saves()
	var tracks := _planned()
	t.eq(tracks.size(), 4)
	var mode := _mode(tracks)
	var log: Array = []
	mode.stage_wanted.connect(func(i: int) -> void: log.append("want %d" % i))
	mode.run_finished.connect(func(_points: int, _rank: int) -> void: log.append("done"))
	mode.eliminated.connect(func() -> void: log.append("out"))
	var orders: Array = [
		[ME, "rival_1", "rival_2", "rival_3"],
		["rival_1", ME, "rival_3", "rival_2"],
		["rival_2", "rival_3", "rival_1", ME],
		[ME, "rival_2", "rival_1", "rival_3"],
	]
	var stages: Array[RpgArcadeStage] = []
	for i in 4:
		var stage := _track(i, tracks[i] as Dictionary)
		stages.append(stage)
		mode.bind_stage(stage)
		t.eq([mode.race.cars.size(), mode.race.phase], [4, RpgRace.Phase.COUNTDOWN], "track %d: its race is counted down" % (i + 1))
		t.eq(mode.championship.races, i)
		if i == 1:
			# between the races the table is in the save of the run, and a loaded game has it
			var extra: Dictionary = mode.saved_run().get("extra", {})
			t.eq(extra, mode.championship.to_data())
			t.eq(extra.get("races"), 1)
			var loaded := RpgRacingMode.new()
			loaded.restore_run_data(JSON.parse_string(JSON.stringify(extra)) as Dictionary)
			t.eq(_points(loaded.championship.table()), [[ME, 10], ["rival_1", 6], ["rival_2", 4], ["rival_3", 3]])
			loaded.free()
		var before := mode.score.points
		var order: Array[String] = []
		order.assign(orders[i] as Array)
		_finish(mode, order)
		t.eq(mode.last_place, order.find(ME) + 1)
		t.eq(mode.last_results.size(), 4)
		t.eq(mode.last_results[0]["driver"], order[0])
		t.ok(mode.score.points >= before + RpgRacingMode.PLACE_POINTS[mode.last_place - 1], "the place pays into the score too")
	t.eq(log, ["want 1", "want 2", "want 3", "done"], "no race put the player out: the option is off")
	t.eq(_points(mode.championship.table()), [[ME, 29], ["rival_1", 24], ["rival_2", 23], ["rival_3", 16]])
	t.eq([mode.championship.leader(), mode.championship.last_count, mode.phase], [ME, 1, RpgArcadeMode.Phase.FINISHED])
	t.eq(state.flags.has(RpgArcadeMode.SAVE_ENTITY), false, "a finished run is not in the saved game")
	# the next run begins with an empty table
	var again := _track(0, tracks[0] as Dictionary)
	mode.bind_stage(again)
	t.eq([mode.championship.races, mode.championship.table().size()], [0, 0])
	t.eq(mode.saved_run().get("extra"), {"races": 0, "last": 0, "points": []}, "and that is what is saved")
	for stage in stages:
		_drop(stage)
	_drop(again)
	_drop(mode)
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()

func test_a_player_who_is_last_twice_is_out_and_may_drive_the_race_again(t) -> void:
	await Fixtures.tree().process_frame
	Fixtures.install_state()
	_saves()
	var tracks := _planned()
	var mode := _mode(tracks)
	mode.elimination = true
	var log: Array = []
	mode.stage_wanted.connect(func(i: int) -> void: log.append("want %d" % i))
	mode.eliminated.connect(func() -> void: log.append("out"))
	mode.game_over.connect(func() -> void: log.append("over"))
	mode.continued.connect(func() -> void: log.append("continue"))
	var last: Array[String] = ["rival_1", "rival_2", "rival_3", ME]
	var first := _track(0, tracks[0] as Dictionary)
	mode.bind_stage(first)
	t.ok(mode.championship.elimination, "the mode's championship has the rule of the game")
	_finish(mode, last)
	t.eq(log, ["want 1"], "last once: on to the next race")
	var second := _track(1, tracks[1] as Dictionary)
	mode.bind_stage(second)
	t.eq(mode.saved_run().get("extra", {}).get("last"), 1, "the save knows of the first time")
	_finish(mode, last)
	t.eq(log, ["want 1", "out", "over", "continue", "want 1"], "last twice: out, and Continue is the same race again")
	t.eq([mode.championship.races, mode.championship.last_count, mode.championship.points_of(ME)], [1, 1, 3], "the race counts for nothing")
	t.ok(not mode.championship.is_eliminated())
	# the race again, and won
	var retry := _track(1, tracks[1] as Dictionary)
	mode.bind_stage(retry)
	var won: Array[String] = [ME, "rival_1", "rival_2", "rival_3"]
	_finish(mode, won)
	t.eq(log.slice(5), ["want 2"])
	t.eq([mode.championship.races, mode.championship.points_of(ME)], [2, 13])
	# out again, and no: the run is over
	var third := _track(2, tracks[2] as Dictionary)
	mode.bind_stage(third)
	mode.auto_continue = false
	_finish(mode, last)
	t.eq(log.slice(6), ["out", "over"])
	t.eq([mode.in_run, mode.saved_run()], [false, {}], "quit: the run is gone")
	for stage: RpgArcadeStage in [first, second, retry, third]:
		_drop(stage)
	_drop(mode)
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- the HUD

func _surfaces(parent: Node) -> RpgTrackSurfaces:
	var surfaces := RpgTrackSurfaces.new()
	surfaces.name = "Surfaces"
	surfaces.cell = 16.0
	surfaces.rows = PackedStringArray(["ggggg", "grrsg", "grgrg", "grrrg", "ggggg"])
	parent.add_child(surfaces)
	return surfaces

func test_the_map_of_the_track_shows_the_road_and_every_car(t) -> void:
	var image := RpgRaceMinimap.picture(PackedStringArray(["ggggg", "grrsg", "gdobg", "g.r"]))
	t.eq(Vector2i(image.get_width(), image.get_height()), Vector2i(5, 4), "a pixel a cell")
	var road := RpgRaceMinimap.ROAD.to_rgba32()
	t.eq(image.get_pixel(1, 1).to_rgba32(), road)
	t.eq(image.get_pixel(3, 1), RpgRaceMinimap.LINE, "the start line")
	t.eq([image.get_pixel(1, 2).to_rgba32(), image.get_pixel(2, 2).to_rgba32(), image.get_pixel(3, 2).to_rgba32()], [road, road, road], "dirt, oil and arrows are road")
	t.eq([image.get_pixel(0, 0).a, image.get_pixel(1, 3).a, image.get_pixel(4, 3).a], [0.0, 0.0, 0.0], "grass and what is beside the track are clear")
	# as large as fits, in the middle, its shape kept
	var view := RpgMinimap.VIEW
	t.eq(RpgRaceMinimap.fit(Vector2i(5, 5), view), Rect2(18, 4, 76, 76))
	var wide := RpgRaceMinimap.fit(Vector2i(54, 27), view)
	t.near(wide.size.x, 104.0, 0.001)
	t.near(wide.size.y, 52.0, 0.001)
	t.near(wide.position.y, 16.0, 0.001)
	t.eq(RpgRaceMinimap.fit(Vector2i.ZERO, view).size, Vector2.ZERO)
	t.eq(RpgRaceMinimap.spot(Vector2(40, 40), Vector2(80, 80), Rect2(18, 4, 76, 76)), Vector2(56, 42))
	t.eq(RpgRaceMinimap.spot(Vector2(80, 0), Vector2(80, 80), Rect2(18, 4, 76, 76)), Vector2(94, 4))
	# the cars of a track
	var root := Node2D.new()
	root.position = Vector2(300, 100)  # the map is of the track, wherever that is
	Fixtures.tree().root.add_child(root)
	var surfaces := _surfaces(root)
	var cars: Array[RpgCar] = []
	for at: Vector2 in [Vector2(40, 40), Vector2(20, 60), Vector2(-10000, -10000), Vector2(72, 24)]:
		var car := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE, cars.is_empty()) as RpgCar
		car.set_physics_process(false)
		car.position = at
		root.add_child(car)
		cars.append(car)
	cars[3].visible = false
	var layer := CanvasLayer.new()
	Fixtures.tree().root.add_child(layer)
	var map := RpgRaceMinimap.new()
	layer.add_child(map)
	map.set_process(false)
	t.ok(not map.visible, "nothing to show yet")
	var screen := map.get_viewport_rect().size
	t.eq(map.position + map.size + Vector2(RpgMinimap.MARGIN, RpgMinimap.MARGIN), screen, "in the bottom-right corner")
	t.eq(map.size, RpgMinimap.VIEW)
	map.show_track(surfaces, cars, cars[0])
	t.ok(map.visible)
	t.eq(Vector2i(map.track_texture().get_size()), Vector2i(5, 5))
	t.eq(map.dots(), [
		{"position": Vector2(56, 42), "player": true},
		{"position": Vector2(37, 61), "player": false},
	] as Array[Dictionary], "a car off the track and one that is not shown have no dot")
	var texture := map.track_texture()
	cars[1].position = Vector2(40, 20)
	map.show_track(surfaces, cars, cars[0])
	t.eq(map.dots()[1]["position"], Vector2(56, 23), "the dot follows its car")
	t.ok(map.track_texture() == texture, "the picture of the track is made once")
	map.show_track(null, cars, cars[0])
	t.ok(not map.visible)
	_drop(layer)
	_drop(root)

func test_the_hud_has_a_sign_a_map_and_the_championship_and_no_lives(t) -> void:
	await Fixtures.tree().process_frame
	var hud := HudRecipe.build_hud() as RpgRacingHud
	t.ok(hud != null, "the recipe's HUD is the race HUD")
	Fixtures.tree().root.add_child(hud)
	hud.set_process(false)
	t.ok(hud.track_minimap() != null and hud.track_minimap().get_parent() == hud)
	hud.track_minimap().set_process(false)
	hud.refresh()
	t.ok(not (hud.get_node("Left/Lives") as Label).visible, "a car has no lives")
	t.eq(hud.sign_text(), "")
	# the sign: a race that is counted down, started, driven the wrong way
	var root := Node2D.new()
	Fixtures.tree().root.add_child(root)
	var me := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE) as RpgCar
	me.set_physics_process(false)
	me.input_node_enabled = false
	root.add_child(me)
	var race := RpgRace.new()
	race.auto_advance = false
	root.add_child(race)
	var cars: Array[RpgCar] = [me]
	race.setup({"laps": 2, "start": {"position": [60.0, 0.0], "heading": 0.0, "line": [100.0, 0.0]}, "checkpoints": [{"id": "c01", "position": [300.0, 0.0], "heading": 0.0, "width": 100.0}], "waypoints": [{"position": [200.0, 0.0], "speed": 12.0}, {"position": [400.0, 100.0], "speed": 6.0}, {"position": [200.0, 200.0], "speed": 12.0}, {"position": [0.0, 100.0], "speed": 6.0}]}, cars)
	race.begin()
	hud.show_race(race, me)
	var sign_label := hud.get_node("Sign") as Label
	t.eq([hud.sign_text(), sign_label.visible], ["3", true], "the countdown")
	t.eq(sign_label.get_theme_font_size(&"font_size"), RpgRacingHud.SIGN_SIZE, "large")
	t.eq(hud.row_text("notice"), "", "the sign is not a row of the corner any more")
	for i in 200:
		race.advance(1.0 / 60.0)
	hud.show_race(race, me)
	t.eq([hud.sign_text(), hud.row_text("lap"), hud.row_text("place")], ["Go!", "Lap 1/2", "Place 1/1"])
	for i in 60:
		race.advance(1.0 / 60.0)
	hud.show_race(race, me)
	t.eq([hud.sign_text(), sign_label.visible], ["", false])
	me.position = Vector2(250, 0)
	me.velocity = Vector2(-100, 0)
	for i in 70:
		race.advance(1.0 / 60.0)
	hud.show_race(race, me)
	t.eq(hud.sign_text(), "Wrong way!")
	t.eq(sign_label.get_theme_color(&"font_color"), RpgRacingHud.WARNING_COLOR)
	hud.show_race(null, me)
	t.eq([hud.sign_text(), hud.row_text("lap")], ["", ""])
	# the championship: the points once a race was driven, the last places when they count
	var cup := RpgChampionship.new()
	hud.show_championship(cup)
	t.eq([hud.row_text("points"), hud.row_text("last")], ["", ""])
	cup.record(_race(["rival_1", ME]))
	hud.show_championship(cup)
	t.eq([hud.row_text("points"), hud.row_text("last")], ["Points: 6", ""], "last, in a game that puts nobody out")
	cup.elimination = true
	hud.show_championship(cup)
	t.eq(hud.row_text("last"), "Last place: 1/2")
	hud.show_championship(null)
	t.eq([hud.row_text("points"), hud.row_text("last")], ["", ""])
	_drop(hud)
	_drop(root)
	# a HUD without the map, and the HUD of the other arcade kinds has neither
	var bare := HudRecipe.build_hud(false) as RpgRacingHud
	Fixtures.tree().root.add_child(bare)
	bare.set_process(false)
	t.ok(bare.track_minimap() == null and bare.get_node_or_null("Minimap") == null)
	_drop(bare)
	t.eq(ArcadeHud.script_for("racing"), "res://addons/rpg_runtime/archetypes/racing/ui/racing_hud.gd")

# ---------------------------------------------------------------- the screens over the game

func test_a_screen_over_the_game_covers_the_whole_screen(t) -> void:
	await Fixtures.tree().process_frame
	var layer := CanvasLayer.new()
	Fixtures.tree().root.add_child(layer)
	var whole := layer.get_viewport().get_visible_rect().size
	var screens: Array[Control] = [RpgRaceResults.new(), RpgArcadeStageClear.new(), RpgArcadeContinueScreen.new(), RpgArcadeHighScoreTable.new(), RpgMemberPicker.new(), RpgEquipPicker.new()]
	for screen in screens:
		layer.add_child(screen)
		screen.set_process(false)
	var results := screens[0] as RpgRaceResults
	var cup := RpgChampionship.new()
	var rows := cup.record(_race([ME, "rival_1"]))
	results.show_results("Track 1", rows, [] as Array[String], cup.table())
	(screens[1] as RpgArcadeStageClear).show_tally("Stage 1", RpgArcadeStageClear.tally(10.0, 30.0, 3), 100)
	await Fixtures.tree().process_frame
	await Fixtures.tree().process_frame
	for screen in screens:
		t.eq(screen.size, whole, "%s is as large as the screen" % (screen.get_script() as Script).resource_path.get_file())
	# and what it shows is in its middle, over a shade as large as the screen
	var center := results.get_node("Center") as Control
	t.eq(center.position, Vector2.ZERO)
	t.ok(center.size.x >= whole.x and center.size.y >= whole.y, "what centres the results is as large (%s)" % center.size)
	for child in results.get_children():
		if child is ColorRect:
			t.eq((child as ColorRect).size, whole, "the shade")
	_drop(layer)
