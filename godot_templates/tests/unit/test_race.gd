extends RefCounted
## T16.14: a race: the countdown, checkpoints and laps, who is where, the wrong way, pickups
## and weapons, rivals that drive the planned tracks, the finish, and the parts a player keeps.

const Fixtures := preload("../lib/fixtures.gd")
const CarRecipe := preload("res://builder/recipes/racing/car_recipe.gd")
const RivalRecipes := preload("res://builder/recipes/racing/rival_recipes.gd")
const TrackRecipe := preload("res://builder/recipes/racing/track_recipe.gd")
const RaceBuild := preload("res://builder/recipes/racing/racing_build.gd")
const HudRecipe := preload("res://builder/recipes/arcade/hud_recipe.gd")
const JsonUtil := preload("res://builder/lib/json_util.gd")

## The tracks of track_plan.plan({}, 12345): tests/unit/test_track_plan.py keeps the file.
const TRACKS := "res://tests/unit/track_plan_cases.json"
const TILE := 16
const VIEW := Vector2i(640, 360)
const DT := 1.0 / 60.0

## A loop to count laps on: east along y = 0 over the start line (at x = 100) and the first
## checkpoint (x = 300), back west along y = 200 over the second (x = 300).
const LOOP := {
	"laps": 2,
	"start": {"position": [60.0, 0.0], "heading": 0.0, "line": [100.0, 0.0]},
	"checkpoints": [
		{"id": "c01", "position": [300.0, 0.0], "heading": 0.0, "width": 100.0},
		{"id": "c02", "position": [300.0, 200.0], "heading": PI, "width": 100.0},
	],
	"waypoints": [
		{"position": [200.0, 0.0], "speed": 12.0},
		{"position": [400.0, 100.0], "speed": 6.0},
		{"position": [200.0, 200.0], "speed": 12.0},
		{"position": [0.0, 100.0], "speed": 6.0},
	],
}
## Just over the start line, and the way round from there to there.
const OVER := Vector2(200, 0)
const ROUND: Array[Vector2] = [Vector2(380, 0), Vector2(380, 200), Vector2(200, 200), Vector2(0, 200), Vector2(0, 0), Vector2(200, 0)]

class Field:
	var root: Node2D
	var race: RpgRace
	var player: RpgCar
	var rivals: Array[RpgCar] = []

	## Moves `car` to `to` in small steps, the race watching.
	func move(car: RpgCar, to: Vector2) -> void:
		while car.position.distance_to(to) > 0.01:
			car.position = car.position.move_toward(to, 15.0)
			race.advance(1.0 / 60.0)

	## Once round, for a car that is just over the line: through both checkpoints and over
	## the line again.
	func lap(car: RpgCar) -> void:
		for point in ROUND:
			move(car, point)

	func run(steps: int) -> void:
		for i in steps:
			race.advance(1.0 / 60.0)

	func drop() -> void:
		if root.get_parent() != null:
			root.get_parent().remove_child(root)
		root.free()

## A race on LOOP with the player and `rivals` other cars, which nothing drives: the test moves
## them. The countdown is over.
func _field(rivals: int = 1, started: bool = true) -> Field:
	await Fixtures.tree().process_frame
	var field := Field.new()
	field.root = Node2D.new()
	field.player = CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE) as RpgCar
	field.player.input_node_enabled = false
	field.player.position = Vector2(60, 0)
	field.player.heading = 0.0
	field.root.add_child(field.player)
	var all: Array[RpgCar] = [field.player]
	for i in rivals:
		var rival := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE, false) as RpgCar
		rival.position = Vector2(60, 20.0 * (i + 1))
		rival.heading = 0.0
		field.root.add_child(rival)
		field.rivals.append(rival)
		all.append(rival)
	field.race = RpgRace.new()
	field.race.name = "Race"
	field.race.auto_advance = false
	field.race.countdown_s = 0.5
	field.root.add_child(field.race)
	Fixtures.tree().root.add_child(field.root)
	for car in all:
		car.set_physics_process(false)  # the test moves the cars
	field.race.setup(LOOP, all)
	field.race.begin()
	if started:
		field.run(40)
	return field

# ---------------------------------------------------------------- the line

func test_a_line_is_crossed_the_right_way_within_its_width(t) -> void:
	var gate := RpgRaceCheckpoint.make(Vector2(100, 50), 0.0, 80.0, "c01")
	t.ok(gate.crossed(Vector2(95, 50), Vector2(105, 50)), "over it, the way of the race")
	t.ok(gate.crossed(Vector2(95, 20), Vector2(100, 15)), "at its edge, and on to it counts")
	t.ok(not gate.crossed(Vector2(105, 50), Vector2(95, 50)), "not backwards")
	t.ok(not gate.crossed(Vector2(95, 120), Vector2(105, 120)), "not beside it")
	t.ok(not gate.crossed(Vector2(80, 50), Vector2(90, 50)), "not before it")
	t.ok(not gate.crossed(Vector2(110, 50), Vector2(120, 50)), "not after it")
	t.ok(not gate.crossed(Vector2(-500, 50), Vector2(500, 50)), "a car that is put somewhere else did not drive over it")
	t.near(gate.along(Vector2(130, 0)), 30.0, 0.001)
	t.near(gate.across(Vector2(130, 20)), 30.0, 0.001)
	var down := RpgRaceCheckpoint.from_data({"id": "c07", "position": [10, 10], "heading": PI * 0.5, "width": 40})
	t.eq([down.id, down.position, down.width], ["c07", Vector2(10, 10), 40.0])
	t.ok(down.crossed(Vector2(10, 5), Vector2(10, 15)), "a line across a road that goes down")
	t.ok(not down.crossed(Vector2(5, 10), Vector2(15, 10)))
	var line := RpgRaceCheckpoint.from_data({"line": [5, 6]}, 99.0)
	t.eq([line.position, line.width], [Vector2(5, 6), 99.0], "the start line of a track")

# ---------------------------------------------------------------- the race

func test_the_race_counts_down_and_the_cars_stand_until_the_start(t) -> void:
	var field := await _field(1, false)
	var race := field.race
	var counts: Array[int] = []
	var started := [0]
	race.counted.connect(func(left: int) -> void: counts.append(left))
	race.started.connect(func() -> void: started[0] += 1)
	t.eq(race.phase, RpgRace.Phase.COUNTDOWN)
	race.countdown_s = 3.0
	t.ok(not field.player.engine_on and not field.rivals[0].engine_on, "nobody can go yet")
	field.player.throttle = 1.0
	field.player.step(DT)
	t.eq(field.player.velocity, Vector2.ZERO, "the pedal does nothing before the start")
	field.run(30)
	t.near(race.countdown_left(), 2.5, 0.02)
	field.run(140)
	t.eq(counts, [3, 2, 1] as Array[int], "three, two, one")
	t.eq(started[0], 0)
	field.run(20)
	t.eq([started[0], race.phase], [1, RpgRace.Phase.RUNNING])
	t.ok(field.player.engine_on and field.rivals[0].engine_on, "and off they go")
	t.eq(race.countdown_left(), 0.0)
	t.ok(race.time_s < 0.5, "the clock of the race starts with it")
	t.eq([race.laps, race.gates.size(), race.route.size()], [2, 2, 4], "the laps, the checkpoints and the waypoints of the track")
	t.eq(race.line.position, Vector2(100, 0))
	field.drop()

func test_a_lap_counts_only_after_every_checkpoint(t) -> void:
	var field := await _field(0)
	var race := field.race
	var car := field.player
	var laps: Array[int] = []
	race.lap_done.connect(func(_car: RpgCar, lap: int) -> void: laps.append(lap))
	t.eq([race.lap_of(car), race.checkpoints_of(car)], [0, 0], "behind the line the race has not begun for it")
	field.move(car, Vector2(200, 0))
	t.eq(race.lap_of(car), 1, "over the line: the first lap")
	t.eq(laps, [] as Array[int], "no lap is done yet")
	# a lap that leaves a checkpoint out is none
	field.move(car, Vector2(380, 0))
	t.eq(race.checkpoints_of(car), 1)
	field.move(car, Vector2(380, 100))
	field.move(car, Vector2(0, 100))  # across the middle: not over the second checkpoint
	field.move(car, Vector2(0, 0))
	field.move(car, Vector2(200, 0))
	t.eq([race.lap_of(car), race.checkpoints_of(car)], [1, 1], "the line does not count without the second checkpoint")
	t.eq(laps, [] as Array[int])
	# nor do the checkpoints count out of their order, or backwards
	field.move(car, Vector2(250, 0))
	field.move(car, Vector2(350, 0))
	t.eq(race.checkpoints_of(car), 1, "the first one again is nothing")
	field.move(car, Vector2(350, 200))
	field.move(car, Vector2(250, 200))
	t.eq(race.checkpoints_of(car), 2, "the second, the way of the race")
	field.move(car, Vector2(0, 200))
	field.move(car, Vector2(0, 0))
	field.move(car, Vector2(200, 0))
	t.eq([race.lap_of(car), race.checkpoints_of(car)], [2, 0], "now the lap counts")
	t.eq(laps, [1] as Array[int])
	t.ok(not race.has_finished(car) and race.is_running())
	# the last lap ends the race for the player
	var over: Array = []
	race.finished.connect(func(standings: Array) -> void: over.append(standings))
	field.lap(car)
	t.eq(laps, [1, 2] as Array[int])
	t.ok(race.has_finished(car) and race.is_finished(), "two laps: the race is over")
	t.eq(over.size(), 1)
	t.ok(not car.engine_on, "the cars stop")
	var first: Dictionary = over[0][0]
	t.eq([first["place"], first["player"], first["finished"]], [1, true, true])
	t.ok(float(first["time_s"]) > 0.0)
	field.drop()

func test_the_places_follow_the_cars_and_change_when_one_overtakes(t) -> void:
	var field := await _field(2)
	var race := field.race
	var me := field.player
	var a := field.rivals[0]
	var b := field.rivals[1]
	var changes := [0]
	race.positions_changed.connect(func() -> void: changes[0] += 1)
	# the rivals go ahead: over the line, one of them further
	field.move(a, Vector2(380, 20))
	field.move(b, Vector2(200, 40))
	t.eq([race.place_of(a), race.place_of(b), race.place_of(me)], [1, 2, 3], "more checkpoints, then nearer the next one")
	t.eq(race.order(), [a, b, me] as Array[RpgCar])
	var before: int = changes[0]
	t.ok(before >= 1)
	# the player overtakes the second
	field.move(me, Vector2(250, 0))
	t.eq([race.place_of(a), race.place_of(me), race.place_of(b)], [1, 2, 3], "the player is second now")
	t.eq(changes[0], before + 1, "and that is told once")
	t.ok(race.progress(a) > race.progress(me) and race.progress(me) > race.progress(b))
	# a lap more is ahead of everything
	field.move(me, OVER)
	field.lap(me)
	t.eq(race.place_of(me), 1)
	t.ok(race.lap_of(me) == 2 and race.lap_of(a) == 1)
	# the standings when the player finishes: the others by how far they got
	field.lap(me)
	t.ok(race.is_finished())
	var table := race.standings()
	t.eq(table.size(), 3)
	t.eq([table[0]["car"], table[1]["car"], table[2]["car"]], [me, a, b])
	t.eq([table[0]["finished"], table[1]["finished"], table[2]["place"]], [true, false, 3])
	field.drop()
	# and a race that is lost: a rival finishes first
	var lost := await _field(1)
	var rival := lost.rivals[0]
	lost.move(rival, OVER)
	for i in 2:
		lost.lap(rival)
	t.ok(lost.race.has_finished(rival) and not lost.race.is_finished(), "the race goes on for the player")
	t.ok(rival.engine_on, "a rival that has finished drives on: it does not stand in the way")
	lost.move(lost.player, OVER)
	for i in 2:
		lost.lap(lost.player)
	t.ok(lost.race.is_finished())
	t.eq([lost.race.place_of(rival), lost.race.place_of(lost.player)], [1, 2], "who finished first is first")
	var both := lost.race.standings()
	t.ok(float(both[0]["time_s"]) < float(both[1]["time_s"]))
	lost.drop()

func test_a_player_who_drives_the_wrong_way_is_told(t) -> void:
	var field := await _field(0)
	var race := field.race
	var car := field.player
	var told: Array[bool] = []
	race.wrong_way_changed.connect(func(wrong: bool) -> void: told.append(wrong))
	t.near(race.way_at(Vector2(200, 5)).angle(), 0.0, 0.8, "the track goes east along its top")
	t.ok(race.way_at(Vector2(200, 195)).x < 0.0, "and west along its bottom")
	car.position = Vector2(250, 0)
	car.velocity = Vector2(100, 0)
	field.run(90)
	t.eq(told, [] as Array[bool], "the right way: nothing")
	car.velocity = Vector2(-100, 0)
	field.run(30)
	t.ok(not race.wrong_way, "not at once")
	field.run(40)
	t.ok(race.wrong_way, "after a second against the track")
	car.velocity = Vector2(-10, 0)
	field.run(2)
	t.ok(not race.wrong_way, "a car that hardly moves is not driving the wrong way")
	car.velocity = Vector2(100, 0)
	field.run(2)
	t.eq(told, [true, false] as Array[bool])
	field.drop()

# ---------------------------------------------------------------- pickups and weapons

func _pickup(field: Field, kind: String, at: Vector2) -> RpgRacePickup:
	var holder := field.root.get_node_or_null("Pickups")
	if holder == null:
		holder = Node2D.new()
		holder.name = "Pickups"
		field.root.add_child(holder)
	var made := RivalRecipes.build_pickup(TILE) as RpgRacePickup
	made.kind = kind
	made.position = at
	holder.add_child(made)
	field.race.pickups.append(made)
	return made

func test_what_lies_on_the_track_is_taken_by_driving_over_it(t) -> void:
	var field := await _field(1)
	var race := field.race
	var me := field.player
	var rival := field.rivals[0]
	var taken: Array[String] = []
	race.pickup_taken.connect(func(car: RpgCar, kind: String) -> void: taken.append(("me:" if car == me else "rival:") + kind))
	var parts: Array[String] = []
	race.part_taken.connect(func(kind: String) -> void: parts.append(kind))
	me.boosts = 1
	var boost := _pickup(field, "boost", Vector2(150, 0))
	var missile := _pickup(field, "missile", Vector2(200, 0))
	var shield := _pickup(field, "shield", Vector2(250, 0))
	var part := _pickup(field, "tyres", Vector2(300, 0))
	t.ok(part.is_part() and not boost.is_part())
	t.ok(not boost.reaches(Vector2(150, 30)) and boost.reaches(Vector2(150, 10)))
	field.move(me, Vector2(150, 0))
	t.eq(me.boosts, 2, "a boost more")
	t.ok(not boost.active and not boost.visible, "it is gone")
	field.move(me, Vector2(200, 0))
	t.eq(me.weapon, "missile", "a missile to carry")
	field.move(me, Vector2(250, 0))
	t.ok(me.shielded)
	field.move(me, Vector2(300, 0))
	t.eq(parts, ["tyres"] as Array[String], "a part: the mode keeps it")
	t.eq(taken, ["me:boost", "me:missile", "me:shield", "me:tyres"] as Array[String])
	# they come back, but for a part
	field.run(int(boost.respawn_s * 60.0) + 5)
	t.ok(boost.active and boost.visible and missile.active and shield.active, "after six seconds they lie there again")
	t.ok(not part.active, "a part is taken once")
	# a rival takes them too, but no part; and a car full of boosts leaves a boost lying
	var second := _pickup(field, "speed", Vector2(150, 40))
	field.move(rival, Vector2(150, 40))
	t.ok(second.active and parts.size() == 1, "a part is the player's only")
	me.boosts = me.max_boosts
	me.position = Vector2(140, 0)  # put there, not driven over the others on the way
	field.run(1)
	field.move(me, Vector2(150, 0))
	t.ok(boost.active, "a car that has all its boosts does not take another")
	field.move(rival, Vector2(200, 0))
	t.eq(rival.weapon, "missile", "a rival carries a missile too")
	t.ok(not race.give(me, "nothing known"))
	field.drop()

func test_a_missile_spins_the_car_ahead_and_a_bomb_the_car_behind(t) -> void:
	var field := await _field(1)
	var race := field.race
	var me := field.player
	var rival := field.rivals[0]
	for car: RpgCar in [me, rival]:
		car.set_physics_process(false)
	# a missile, fired at a car ahead
	me.place(Vector2(200, 0), 0.0)
	rival.place(Vector2(400, 0), 0.0)
	me.engine_on = true
	rival.engine_on = true
	me.weapon = "missile"
	var fired: Array[String] = []
	me.weapon_fired.connect(func(kind: String) -> void: fired.append(kind))
	me.press_fire()
	me.step(DT)
	t.eq(fired, ["missile"] as Array[String])
	t.eq(me.weapon, "", "it is used up")
	t.eq(race.weapons.size(), 1)
	var missile := race.weapons[0]
	t.ok(missile.position.x > me.position.x and missile.velocity.x > 0.0, "it flies the way the car points")
	var spun := [0]
	rival.spun_out.connect(func() -> void: spun[0] += 1)
	field.run(40)
	t.eq(spun[0], 1, "it hits the car ahead")
	t.ok(rival.is_spinning())
	t.eq(race.weapons.size(), 0, "and is gone")
	# a car that spins does not steer, turns round and loses its speed
	rival.velocity = Vector2(160, 0)
	rival.throttle = 1.0
	var heading := rival.heading
	for i in 30:
		rival.step(DT)
	t.ok(rival.velocity.length() < 160.0 and absf(RpgCarPhysics.angle_difference(heading, rival.heading)) > 0.5, "it spins and slows")
	for i in 60:
		rival.step(DT)
	t.ok(not rival.is_spinning(), "for a moment only")
	# a missile that meets nothing ends
	me.weapon = "missile"
	rival.place(Vector2(200, 300), 0.0)
	me.press_fire()
	me.step(DT)
	field.run(120)
	t.eq([race.weapons.size(), spun[0]], [0, 1])
	# a shield takes one hit
	rival.place(Vector2(400, 0), 0.0)
	rival.shielded = true
	var broken := [0]
	rival.shield_broken.connect(func() -> void: broken[0] += 1)
	me.weapon = "missile"
	me.press_fire()
	me.step(DT)
	field.run(40)
	t.eq([spun[0], broken[0], rival.shielded], [1, 1, false], "the shield is gone, the car drives on")
	# a bomb is dropped behind and waits for who comes
	me.weapon = "bomb"
	me.press_fire()
	me.step(DT)
	t.eq(race.weapons.size(), 1)
	var bomb := race.weapons[0]
	t.ok(bomb.position.x < me.position.x and bomb.velocity == Vector2.ZERO, "behind the car, lying still")
	field.run(60)
	t.ok(not me.is_spinning(), "it does not go off under the car that dropped it")
	rival.place(bomb.position + Vector2(-100, 0), 0.0)
	field.move(rival, bomb.position)
	t.eq(spun[0], 2, "the car behind drives over it")
	t.eq(race.weapons.size(), 0)
	# a car without a weapon fires nothing
	var shots := fired.size()
	me.press_fire()
	me.step(DT)
	t.eq([fired.size(), race.weapons.size()], [shots, 0])
	field.drop()

# ---------------------------------------------------------------- the rivals

func _planned() -> Array:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(TRACKS))
	if parsed is Dictionary:
		var plan: Dictionary = parsed
		return JsonUtil.to_array(plan.get("list", []))
	return []

## The scene of a planned track with `rivals` rivals, in the tree, its race set up; nothing
## moves by itself: the test steps the cars and the race.
func _track(track: Dictionary, rivals: int) -> RpgArcadeStage:
	var car_scene := PackedScene.new()
	var made := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE)
	car_scene.pack(made)
	made.free()
	var rival_scenes: Array = []
	for i in rivals:
		var packed := PackedScene.new()
		var rival := RivalRecipes.build_rival(i + 1, null, Vector2i(24, 24), 1, TILE)
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
	var look := {
		"heading": float(begin["heading"]),
		"tyres": track["tyres"],
		"pickups": track["pickups"],
		"rival_scenes": rival_scenes,
		"pickup_scene": pickup_scene,
	}
	var stage := TrackRecipe.build_track(0, track, VIEW, TILE, rows, barriers, Vector2(float(at[0]), float(at[1])), null, {}, car_scene, false, look) as RpgArcadeStage
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

func test_a_rival_drives_a_lap_of_every_planned_track(t) -> void:
	var tracks := _planned()
	t.eq(tracks.size(), 4, "the four tracks rpggen plans for seed 12345")
	for raw: Variant in tracks:
		var track: Dictionary = raw
		var stage := _track(track, 1)
		var race := stage.get_node("Race") as RpgRace
		var rival := stage.get_node("Rival1") as RpgCar
		var driver := rival.get_node("Input") as RpgRival
		t.ok(driver != null and driver.route.size() == JsonUtil.to_array(track["waypoints"]).size(), "%s: the rival knows the way" % track["id"])
		var grass := 0
		var steps := 0
		var bumps := [0]
		rival.bumped.connect(func(_lost: float) -> void: bumps[0] += 1)
		while race.lap_of(rival) < 2 and steps < 60 * 90:
			rival.poll_input()
			rival.step(DT)
			race.advance(DT)
			steps += 1
			if race.is_running() and rival.surface == "grass":
				grass += 1
		t.eq(race.lap_of(rival), 2, "%s: a lap in %d steps" % [track["id"], steps])
		t.ok(steps < 60 * 60, "%s: in under a minute (%d steps)" % [track["id"], steps])
		t.eq(race.checkpoints_of(rival), 0, "%s: through every checkpoint, and on to the next lap" % track["id"])
		t.ok(grass * 20 < steps, "%s: on the road (%d of %d steps on grass)" % [track["id"], grass, steps])
		t.eq(bumps[0], 0, "%s: without hitting a barrier or a tyre" % track["id"])
		stage.get_parent().remove_child(stage)
		stage.free()

func test_a_weaker_rival_is_slower_and_a_rubber_band_only_holds_back(t) -> void:
	var track: Dictionary = _planned()[0]
	var times: Array[int] = []
	for skill: float in [0.95, 0.4]:
		var stage := _track(track, 1)
		var race := stage.get_node("Race") as RpgRace
		var rival := stage.get_node("Rival1") as RpgCar
		(rival.get_node("Input") as RpgRival).skill = skill
		var steps := 0
		while race.lap_of(rival) < 2 and steps < 60 * 120:
			rival.poll_input()
			rival.step(DT)
			race.advance(DT)
			steps += 1
		t.eq(race.lap_of(rival), 2, "a rival of skill %.2f finishes its lap" % skill)
		times.append(steps)
		stage.get_parent().remove_child(stage)
		stage.free()
	t.ok(times[0] < times[1], "the better driver is faster (%d against %d steps)" % [times[0], times[1]])
	# where a weak driver aims is off the middle of the road, a good one's hardly
	var driver := RpgRival.new()
	driver.set_route(PackedVector2Array([Vector2(0, 0), Vector2(100, 0), Vector2(200, 0), Vector2(300, 0)]), PackedFloat32Array([12, 12, 12, 12]))
	driver.skill = 1.0
	t.eq(driver.aim(1, TILE), Vector2(100, 0), "the best holds the line")
	driver.skill = 0.3
	var off := driver.aim(1, TILE)
	t.ok(off.x == 100.0 and absf(off.y) > 0.5 and absf(off.y) <= 0.7 * 1.2 * TILE, "a weak one drifts off it (%s)" % off)
	t.eq(driver.aim(1, TILE), off, "the same way every lap")
	driver.free()
	# the rubber band: a rival far ahead gets less pedal, one behind never more than its own
	var field := await _field(1)
	var rival_car := field.rivals[0]
	var brain := RpgRival.new()
	brain.name = "Input"
	rival_car.add_child(brain)
	field.race.setup(LOOP, [field.player, rival_car] as Array[RpgCar])
	field.race.begin()
	field.run(40)
	t.eq(brain.pace, 1.0)
	field.move(rival_car, OVER)
	field.lap(rival_car)
	t.ok(brain.pace < 1.0 and brain.pace >= 1.0 - RpgRace.BAND_MOST, "far ahead it eases off (%f)" % brain.pace)
	field.move(field.player, OVER)
	field.lap(field.player)
	field.lap(field.player)
	t.eq(brain.pace, 1.0, "behind the player it drives as it can, and no faster")
	field.race.rubber_band = false
	field.drop()

func test_a_race_against_three_rivals_is_driven_to_its_end(t) -> void:
	var track: Dictionary = _planned()[0].duplicate(true)
	track["laps"] = 1
	var stage := _track(track, 3)
	var race := stage.get_node("Race") as RpgRace
	var me := stage.get_node("Car") as RpgCar
	t.eq(race.cars.size(), 4)
	t.eq(race.player, me)
	t.eq(race.pickups.size(), JsonUtil.to_array(track["pickups"]).size(), "what the plan put on the track lies there")
	# the grid: the rivals ahead, the player last, all behind the line and on the road
	var surfaces := stage.get_node("Surfaces") as RpgTrackSurfaces
	for car in race.cars:
		t.ok(race.line.along(car.position) < 0.0, "%s stands behind the line" % car.name)
		t.eq(surfaces.at(car.position), "road")
		t.ok(race.line.along(car.position) >= race.line.along(me.position), "nobody stands behind the player")
	# the player is driven by a rival's driver: it is a race of four that can drive
	var driver := RpgRival.new()
	driver.skill = 1.0
	driver.name = "Driver"
	me.add_child(driver)
	driver.set_route(race.route, race.route_speeds)
	var over: Array = []
	race.finished.connect(func(standings: Array) -> void: over.append(standings))
	var steps := 0
	var taken := [0]
	race.pickup_taken.connect(func(_car: RpgCar, _kind: String) -> void: taken[0] += 1)
	while over.is_empty() and steps < 60 * 120:
		for car in race.cars:
			if car == me:
				driver.poll(me)
			else:
				car.poll_input()
			car.step(DT)
		race.advance(DT)
		steps += 1
	t.eq(over.size(), 1, "the race ends when the player has driven its lap (%d steps)" % steps)
	var table: Array = over[0]
	t.eq(table.size(), 4)
	var places: Array[int] = []
	for row: Dictionary in table:
		places.append(int(row["place"]))
	t.eq(places, [1, 2, 3, 4] as Array[int])
	t.ok(race.place_of(me) >= 1 and race.place_of(me) <= 4)
	t.ok(taken[0] > 0, "pickups were driven over on the way (%d)" % taken[0])
	for car in race.cars:
		t.ok(race.lap_of(car) >= 1, "%s got over the line" % car.name)
	stage.get_parent().remove_child(stage)
	stage.free()

# ---------------------------------------------------------------- the scenes and the mode

func test_the_recipes_put_the_rivals_on_the_grid_ahead_of_the_player(t) -> void:
	var start := Vector2(200, 100)
	t.eq(RaceBuild.grid_slot(start, 0.0, 0, TILE), start + Vector2(0.7, 1.2) * TILE, "the first: ahead, to one side of the road")
	t.eq(RaceBuild.grid_slot(start, 0.0, 1, TILE), start + Vector2(0.7, -1.2) * TILE, "beside it")
	t.eq(RaceBuild.grid_slot(start, 0.0, 2, TILE), start + Vector2(-0.7, 1.2) * TILE, "a row behind")
	var down := RaceBuild.grid_slot(start, PI * 0.5, 1, TILE)
	t.near(down.x, start.x + 1.2 * TILE, 0.001, "turned with the way of the race")
	t.near(down.y, start.y + 0.7 * TILE, 0.001)
	var rival := RivalRecipes.build_rival(2, null, Vector2i(24, 24), 1, TILE, Color(0.5, 1, 0.5)) as RpgCar
	t.eq(String(rival.name), "Rival2")
	t.ok(not rival.is_player and rival.boosts == 0)
	var driver := rival.get_node("Input") as RpgRival
	t.ok(driver != null, "a rival is driven by RpgRival")
	t.eq(driver.skill, RaceBuild.SKILLS[1])
	t.eq((rival.get_node("Visual") as CanvasItem).modulate, Color(0.5, 1, 0.5), "the player's car in another colour")
	rival.free()
	var pickup := RivalRecipes.build_pickup(TILE) as RpgRacePickup
	t.ok(pickup != null and pickup.tile == 16.0)
	pickup.free()
	var track: Dictionary = _planned()[1]
	var stage := _track(track, 3)
	var begin := JsonUtil.to_dict(track["start"])
	var at := JsonUtil.to_array(begin["position"])
	var middle := Vector2(float(at[0]), float(at[1]))
	var heading := float(begin["heading"])
	for i in 3:
		var car := stage.get_node("Rival%d" % (i + 1)) as RpgCar
		t.eq(car.position, RaceBuild.grid_slot(middle, heading, i, TILE))
		t.eq(car.heading, heading)
	t.eq((stage.get_node("Car") as RpgCar).position, RaceBuild.grid_slot(middle, heading, 3, TILE), "the player starts last")
	t.ok(stage.get_node("Pickups/Pickup1") is RpgRacePickup)
	var kinds := {}
	for node in stage.get_node("Pickups").get_children():
		kinds[(node as RpgRacePickup).kind] = true
	var parts := 0
	for kind: String in kinds:
		t.ok(RpgRacePickup.KINDS.has(kind) or RpgRacePickup.PARTS.has(kind), kind)
		parts += 1 if RpgRacePickup.PARTS.has(kind) else 0
	t.eq(parts, 1, "one part lies on the track")
	stage.get_parent().remove_child(stage)
	stage.free()
	# without rivals the car is alone in the middle of the road, and there is a race all the same
	var alone := _track(track, 0)
	t.eq((alone.get_node("Car") as RpgCar).position, middle)
	t.eq((alone.get_node("Race") as RpgRace).cars.size(), 1)
	alone.get_parent().remove_child(alone)
	alone.free()

func test_the_mode_keeps_the_parts_and_gives_points_for_the_place(t) -> void:
	var mode := RpgRacingMode.new()
	Fixtures.tree().root.add_child(mode)
	var car := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE) as RpgCar
	mode.car = car
	t.eq([mode.part_level("speed"), mode.part_level("tyres"), mode.part_level("acceleration")], [0, 0, 0])
	t.ok(mode.add_part("speed"))
	t.ok(mode.add_part("tyres") and mode.add_part("tyres"))
	t.eq(mode.weapon, "speed=1;tyres=2;acceleration=0", "kept as text in what the run saves")
	t.near(car.top_mul, 1.04, 0.0001)
	t.near(car.grip_mul, 1.16, 0.0001)
	t.eq(car.accel_mul, 1.0)
	t.near(car.top_tiles(), RpgCarPhysics.TOP * 1.04, 0.0001)
	t.ok(mode.add_part("speed") and mode.add_part("speed"))
	t.ok(not mode.add_part("speed"), "three levels and no more")
	t.eq(mode.part_level("speed"), 3)
	t.ok(not mode.add_part("paint"), "no such part")
	# a loaded run: the text is read again
	var other := RpgRacingMode.new()
	other.weapon = "speed=2;tyres=9;acceleration=x"
	t.eq([other.part_level("speed"), other.part_level("tyres"), other.part_level("acceleration")], [2, 3, 0])
	other.free()
	# a faster car: the same pedal for the same time
	var plain := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE) as RpgCar
	for one: RpgCar in [car, plain]:
		Fixtures.tree().root.add_child(one)
		one.set_physics_process(false)
		one.input_node_enabled = false
		one.surface_override = "road"
		one.heading = 0.0
		one.throttle = 1.0
		for i in 240:
			one.step(DT)
	t.near(plain.speed_tiles(), RpgCarPhysics.TOP, 0.01)
	t.near(car.speed_tiles(), RpgCarPhysics.TOP * RpgCarPhysics.part_factor("speed", 3), 0.01, "the part makes the car faster")
	t.eq(RpgRacingMode.PLACE_POINTS[0], 3000)
	t.ok(RpgRacingMode.PLACE_POINTS[0] > RpgRacingMode.PLACE_POINTS[1] and RpgRacingMode.PLACE_POINTS[1] > RpgRacingMode.PLACE_POINTS[3])
	for one: RpgCar in [car, plain]:
		one.get_parent().remove_child(one)
		one.free()
	mode.get_parent().remove_child(mode)
	mode.free()

func test_the_hud_shows_the_lap_the_place_and_what_the_car_carries(t) -> void:
	var field := await _field(1, false)
	var hud := HudRecipe.build_hud(HudRecipe.script_for("racing")) as RpgRacingHud
	Fixtures.tree().root.add_child(hud)
	hud.set_process(false)
	hud.track_minimap().set_process(false)
	var me := field.player
	field.race.countdown_s = 3.0
	hud.show_race(field.race, me)
	t.eq(hud.sign_text(), "3", "the countdown")
	t.eq(hud.row_text("lap"), "Lap 1/2")
	t.eq(hud.row_text("place"), "Place 1/2")
	field.run(200)
	hud.show_race(field.race, me)
	t.eq(hud.sign_text(), "Go!")
	field.move(field.rivals[0], Vector2(380, 20))
	field.run(60)
	hud.show_race(field.race, me)
	t.eq(hud.row_text("place"), "Place 2/2")
	t.eq(hud.sign_text(), "")
	me.weapon = "bomb"
	me.shielded = true
	hud.show_car(me)
	t.eq(hud.row_text("weapon"), "Weapon: Bomb")
	t.eq(hud.row_text("shield"), "Shield")
	me.weapon = ""
	me.shielded = false
	hud.show_car(me)
	t.eq([hud.row_text("weapon"), hud.row_text("shield")], ["", ""])
	me.position = Vector2(250, 0)
	me.velocity = Vector2(-100, 0)
	field.run(70)
	hud.show_race(field.race, me)
	t.eq(hud.sign_text(), "Wrong way!")
	hud.show_race(null, me)
	t.eq([hud.row_text("lap"), hud.row_text("place"), hud.sign_text()], ["", "", ""])
	hud.get_parent().remove_child(hud)
	hud.free()
	field.drop()
