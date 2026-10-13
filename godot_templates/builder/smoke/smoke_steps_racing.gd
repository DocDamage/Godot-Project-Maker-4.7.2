extends RefCounted
## The smoke steps of a racing game (T16.12 to T16.15): the title and a new game, the race of
## the first track counting down with every car standing on its grid, and the start. Then the
## rivals are taken off the track and the car is driven alone with the real input actions: it
## speeds up and brakes, steers, the camera looks ahead of it, it boosts, is slower on the
## grass and bumps off a barrier; it drives over what lies on the track and uses the weapon it
## has picked up. Then the race is run again with the rivals, one lap: a simple driver (head
## for the next waypoint, brake down to its speed, back off what it is stuck on) holds the
## buttons for the player, the rivals drive themselves, and the race ends with its standings.
## In that lap every checkpoint is counted for the player where it lies, in its order, and the
## player, who starts last and has the debug speed of a smoke run, passes a rival.
## Its results are put on the screen as the game shows them, the championship has the points
## of the race and is in the save of the run, and the HUD of the next track has its sign, its
## rows and its map with a dot for every car. The other tracks are each seen counting down and
## starting, and ended by hand, to the credits.
##
## The steps ask the plan of the track, not the screen: where a car is, what it drives on, the
## checkpoints and the waypoints are the plan's in both views, since a race is driven on the
## flat plan whatever it looks like (T17.15). The three things that are about the picture ask
## the car where it is drawn (`shown_position`, `shown_heading`): that it is on the screen,
## which frame of its picture shows, and where the camera is. With *absolute* steering the
## arrows the driver holds are the way to the waypoint as it is seen on the screen.

const SAVE_DIR := "user://smoke_saves"
const ACTIONS: Array[StringName] = [&"accelerate", &"brake", &"boost", &"fire", &"move_left", &"move_right", &"move_up", &"move_down"]
## What a failed step of this sequence is reported as (docs/spec/03_ERROR_CODES.md).
const CODE := "SMOKE-012"
## The debug speed: what the player's car has more than a rival's in the race that is driven
## (its top speed, its acceleration and its grip), and how much faster than the track says it
## is taken through a corner with that, so that it passes a rival in a lap whatever the track.
const DEBUG_SPEED := 1.5
const DEBUG_CORNER := 1.15
## Passing: a rival this near ahead (tiles), and this near the line the car drives (tiles), is
## in the way; the driver then heads this far (tiles) beside the waypoint, for this many steps.
const PASS_AHEAD := 6.0
const PASS_BESIDE := 1.5
const PASS_ASIDE := 2.5
const PASS_STEPS := 45

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	return [
		_step("title_new_game", _title_new_game, 40.0),
		_step("car_speeds_up_and_brakes", _car_speeds_up_and_brakes, 30.0),
		_step("car_steers", _car_steers, 30.0),
		_step("camera_looks_ahead", _camera_looks_ahead, 30.0),
		_step("car_boosts", _car_boosts, 30.0),
		_step("grass_is_slower", _grass_is_slower, 40.0),
		_step("car_bumps_off_a_barrier", _car_bumps_off_a_barrier, 40.0),
		_step("pickup_is_taken_and_used", _pickup_is_taken_and_used, 40.0),
		_step("race_is_driven_to_the_finish", _race_is_driven_to_the_finish, 240.0),
		_step("results_and_the_championship", _results_and_the_championship, 60.0),
		_step("tracks_end_with_the_credits", _tracks_end_with_the_credits, 300.0),
	]

func _step(step_name: String, fn: Callable, timeout_s: float) -> Dictionary:
	return {"name": step_name, "fn": fn, "timeout_s": timeout_s, "code": CODE}

# ---------------------------------------------------------------- helpers

func _autoload(autoload_name: String) -> Node:
	return _tree().root.get_node_or_null(autoload_name)

func _router() -> RpgSceneRouter:
	return _autoload("SceneRouter") as RpgSceneRouter

func _stage() -> RpgArcadeStage:
	var router := _router()
	return router.current_map as RpgArcadeStage if router != null else null

func _mode() -> RpgRacingMode:
	var router := _router()
	return router.combat as RpgRacingMode if router != null else null

func _car() -> RpgCar:
	var mode := _mode()
	return mode.car if mode != null and mode.car != null and is_instance_valid(mode.car) else null

func _surfaces() -> RpgTrackSurfaces:
	var stage := _stage()
	return stage.get_node_or_null("Surfaces") as RpgTrackSurfaces if stage != null else null

func _race() -> RpgRace:
	var mode := _mode()
	return mode.current_race() if mode != null else null

func _camera() -> RpgRaceCamera:
	var stage := _stage()
	return stage.get_node_or_null("Camera") as RpgRaceCamera if stage != null else null

func _wait_for(check: Callable, frames: int) -> bool:
	for i in frames:
		if check.call():
			return true
		await _tree().physics_frame
	return check.call()

func _frames(count: int) -> void:
	for i in count:
		await _tree().physics_frame

func _release_all() -> void:
	for action in ACTIONS:
		if InputMap.has_action(action):
			Input.action_release(action)

## Where the car begins, and the way it points there.
var _start := Vector2.ZERO
var _start_heading := 0.0

## Where the picture of the car is on the screen, in px of the window: its place in a track
## seen from above, and where the view puts it in one seen at an angle.
func _on_screen(car: RpgCar) -> Vector2:
	var parent := car.get_parent() as Node2D
	var drawn := car.shown_position()
	return car.get_canvas_transform() * (parent.to_global(drawn) if parent != null else drawn)

## How long a tile of the plan is where the car is drawn, in px of the track's scene.
func _tile_seen(car: RpgCar) -> float:
	var seen := car.view()
	return car.tile_size * (seen.scale_px() if seen != null else 1.0)

## Puts the car back at the start, standing.
func _back_to_start() -> void:
	_release_all()
	var car := _car()
	car.place(_start, _start_heading)
	await _frames(3)

# ---------------------------------------------------------------- the steps

func _title_new_game() -> String:
	var tree := _tree()
	var save := _autoload("SaveManager") as RpgSaveManager
	if save == null or _autoload("GameState") == null:
		return "SaveManager or GameState autoload is missing"
	save.set("dir", SAVE_DIR)  # never touch the player's real saves
	for slot in range(RpgSaveManager.AUTOSAVE_SLOT, RpgSaveManager.SLOTS + 1):
		save.delete(slot)
	var title: Control = null
	for i in 600:
		await tree.process_frame
		var scene := tree.current_scene
		if scene != null and scene.name == "TitleScreen":
			title = scene as Control
			break
	if title == null:
		return "the title screen did not appear"
	var router := _router()
	for i in 600:  # the fade-in of the title is still running; go_to calls during it are ignored
		if not router.is_busy():
			break
		await tree.process_frame
	var button := title.get_node("%NewGame") as Button
	for i in 120:
		if button.has_focus():
			break
		await tree.process_frame
	if not button.has_focus():
		button.grab_focus()
		await tree.process_frame
	var key := InputEventKey.new()
	key.keycode = KEY_ENTER
	key.physical_keycode = KEY_ENTER
	key.pressed = true
	Input.parse_input_event(key)
	await tree.process_frame
	key = key.duplicate() as InputEventKey
	key.pressed = false
	Input.parse_input_event(key)
	if not await _wait_for(func() -> bool: return _stage() != null and not router.is_busy(), 600):
		return "pressing confirm on New Game did not open the first track"
	var stage := _stage()
	var cameras := 0
	for node in stage.find_children("*", "Camera2D", true, false):
		if (node as Camera2D).enabled:
			cameras += 1
	if cameras != 1:
		return "a track must have exactly one enabled camera, the first track has %d" % cameras
	if _mode() == null:
		return "the combat mode is not the racing game's"
	var car := _car()
	if car == null:
		return "the first track has no car"
	if _surfaces() == null:
		return "the first track does not say what it is made of (no Surfaces node)"
	if _camera() == null:
		return "the camera of the track is not the race camera"
	for action: StringName in [&"accelerate", &"brake", &"boost", &"fire"]:
		if not InputMap.has_action(action):
			return "the input action %s is missing" % action
	# the race of the track: it counts down, and until the start nobody moves
	var race := _race()
	if race == null:
		return "the first track has no race"
	if race.phase != RpgRace.Phase.COUNTDOWN:
		return "the race does not begin with a countdown (phase %d)" % race.phase
	if race.player != car or race.cars.size() != stage.find_children("Rival*", "CharacterBody2D", true, false).size() + 1:
		return "the race has %d cars and the track %d rivals" % [race.cars.size(), stage.find_children("Rival*", "CharacterBody2D", true, false).size()]
	var surfaces := _surfaces()
	for other in race.cars:
		if surfaces.at(other.position) != "road" or race.line.along(other.position) >= 0.0:
			return "%s does not stand on the road behind the start line (at %s)" % [other.name, other.position]
		if race.line.along(other.position) < race.line.along(car.position) - 0.01:
			return "%s stands behind the player, who starts last" % other.name
	var stood := car.position
	Input.action_press(&"accelerate")
	await _frames(20)
	Input.action_release(&"accelerate")
	if car.position != stood:
		return "the car moved before the start of the race"
	if not await _wait_for(func() -> bool: return race.is_running(), 60 * 6):
		return "the race did not start within six seconds"
	if not car.engine_on:
		return "the car cannot go after the start"
	# the car is tried alone first: the rivals are taken off the track until the race is run
	race.park_rivals(true)
	await _frames(5)
	var view := Rect2(Vector2.ZERO, tree.root.get_visible_rect().size)
	if not view.has_point(_on_screen(car)):
		return "the car is not on the screen (%s)" % _on_screen(car)
	if _mode().phase != RpgArcadeMode.Phase.PLAYING:
		return "the run did not start (phase %d)" % _mode().phase
	_start = car.position
	_start_heading = car.heading
	return ""

func _car_speeds_up_and_brakes() -> String:
	var car := _car()
	var from := car.position
	Input.action_press(&"accelerate")
	await _frames(60)
	var fast := car.speed_tiles()
	Input.action_release(&"accelerate")
	if fast < 5.0:
		return "a second of the pedal made %.1f tiles a second" % fast
	if car.position.distance_to(from) < car.tile_size * 2.0:
		return "the car did not move (%s -> %s)" % [from, car.position]
	if (car.position - from).normalized().dot(car.forward()) < 0.95:
		return "the car did not go the way it points"
	Input.action_press(&"brake")
	var stopped := await _wait_for(func() -> bool: return car.speed_tiles() <= 0.0, 90)
	if not stopped:
		Input.action_release(&"brake")
		return "the brake did not stop the car in a second and a half (%.1f tiles a second)" % car.speed_tiles()
	await _frames(40)
	Input.action_release(&"brake")
	if car.speed_tiles() >= -0.5:
		return "holding the brake did not reverse a car that stands (%.1f)" % car.speed_tiles()
	await _back_to_start()
	return ""

func _car_steers() -> String:
	var car := _car()
	var before := car.heading
	Input.action_press(&"move_right")
	await _frames(20)
	if absf(RpgCarPhysics.angle_difference(before, car.heading)) > 0.001:
		Input.action_release(&"move_right")
		return "a car that stands turned"
	Input.action_press(&"accelerate")
	await _frames(25)
	Input.action_release(&"move_right")
	var turned := RpgCarPhysics.angle_difference(before, car.heading)
	if turned <= 0.2:
		Input.action_release(&"accelerate")
		return "holding move_right turned the car %.2f rad" % turned
	var visual := car.get_node_or_null("Visual") as RpgHeadingSprite
	# the frame of the heading as it is seen: the car's own from above
	if visual != null and visual.headings > 1 and visual.frame != visual.frame_for(car.shown_heading()):
		Input.action_release(&"accelerate")
		return "the picture of the car shows frame %d for the heading %.2f (%.2f on the screen)" % [visual.frame, car.heading, car.shown_heading()]
	Input.action_press(&"move_left")
	await _frames(25)
	Input.action_release(&"move_left")
	Input.action_release(&"accelerate")
	if RpgCarPhysics.angle_difference(before, car.heading) >= turned:
		return "holding move_left did not turn the car back"
	await _back_to_start()
	return ""

func _camera_looks_ahead() -> String:
	var car := _car()
	var camera := _camera()
	if camera.fixed:
		var at := camera.position
		Input.action_press(&"accelerate")
		await _frames(40)
		Input.action_release(&"accelerate")
		if camera.position != at:
			return "a fixed camera moved"
		await _back_to_start()
		return ""
	Input.action_press(&"accelerate")
	await _frames(70)
	# ahead of where the car is drawn, the way it points there
	var ahead := (camera.position - car.shown_position()).dot(car.shown_forward())
	var zoom := camera.zoom.x
	Input.action_release(&"accelerate")
	if ahead <= _tile_seen(car):
		return "the camera is %.1f px ahead of a car at speed" % ahead
	if zoom >= camera.base_zoom:
		return "the camera did not zoom out with the speed (zoom %.2f of %.2f)" % [zoom, camera.base_zoom]
	await _back_to_start()
	await _frames(90)
	if camera.position.distance_to(car.shown_position()) > _tile_seen(car):
		return "the camera did not come back to a car that stands"
	return ""

func _car_boosts() -> String:
	var car := _car()
	var had := car.boosts
	if had <= 0:
		return "the car starts without a boost"
	Input.action_press(&"accelerate")
	await _frames(20)
	Input.action_press(&"boost")
	await _frames(2)
	Input.action_release(&"boost")
	if not car.is_boosting() or car.boosts != had - 1:
		Input.action_release(&"accelerate")
		return "pressing boost did not start one (%d boosts left of %d)" % [car.boosts, had]
	await _frames(25)
	var fast := car.speed_tiles()
	Input.action_release(&"accelerate")
	if fast <= RpgCarPhysics.TOP:
		return "a boost made %.1f tiles a second (the top speed is %.1f)" % [fast, RpgCarPhysics.TOP]
	await _back_to_start()
	return ""

## The first row of the track that has road in it, and the cells of its first run of road:
## [row, first column, last column]. Above it is the verge, and above that the wall.
func _top_road() -> Array[int]:
	var surfaces := _surfaces()
	var cells := surfaces.size_cells()
	for y in cells.y:
		for x in cells.x:
			if surfaces.at_cell(Vector2i(x, y)) != "road":
				continue
			var last := x
			while surfaces.at_cell(Vector2i(last + 1, y)) == "road":
				last += 1
			return [y, x, last]
	return []

func _grass_is_slower() -> String:
	var car := _car()
	var surfaces := _surfaces()
	var top := _top_road()
	if top.is_empty():
		return "the track has no road"
	# the verge above the topmost road, driven along
	var grass := Vector2(top[1] + 0.5, top[0] - 0.5) * surfaces.cell
	if surfaces.at(grass) != "grass":
		return "the cell above the road is %s, not grass" % surfaces.at(grass)
	car.place(grass, 0.0)
	Input.action_press(&"accelerate")
	await _frames(50)
	var fast := car.speed_tiles()
	var on := car.surface
	Input.action_release(&"accelerate")
	if on != "grass":
		return "the car on the verge is on %s (at %s)" % [on, car.position]
	var most := RpgCarPhysics.top_speed("grass")
	if fast > most + 0.01 or fast < most * 0.8:
		return "the pedal on grass made %.1f tiles a second (grass allows %.1f)" % [fast, most]
	await _back_to_start()
	return ""

func _car_bumps_off_a_barrier() -> String:
	var car := _car()
	var surfaces := _surfaces()
	var top := _top_road()
	var bumps: Array[float] = []
	var count := func(lost: float) -> void: bumps.append(lost)
	car.bumped.connect(count)
	# up from the topmost road, over the verge, at the wall at the edge of the field
	car.place(Vector2((top[1] + top[2] + 1) * 0.5, top[0] + 1.5) * surfaces.cell, -PI * 0.5)
	Input.action_press(&"accelerate")
	var hit := await _wait_for(func() -> bool: return not bumps.is_empty(), 240)
	Input.action_release(&"accelerate")
	car.bumped.disconnect(count)
	if not hit:
		return "the car drove up for four seconds and bumped into nothing (it is at %s)" % car.position
	if bumps[0] < 1.0:
		return "a bump at speed cost %.1f tiles a second" % bumps[0]
	if car.position.y < 0.0:
		return "the car went through the wall (it is at %s)" % car.position
	await _frames(20)
	await _back_to_start()
	return ""

## The places of `key` ("waypoints", "checkpoints") of the track that is driven, in px.
func _places(key: String) -> Array[Vector2]:
	var out: Array[Vector2] = []
	for raw: Variant in RpgUtil.to_array(_mode().stages().current().get(key, [])):
		if raw is Dictionary:
			var entry: Dictionary = raw
			var at := RpgUtil.to_array(entry.get("position", []))
			if at.size() >= 2:
				out.append(Vector2(RpgUtil.to_float(at[0]), RpgUtil.to_float(at[1])))
	return out

func _speeds() -> Array[float]:
	var out: Array[float] = []
	for raw: Variant in RpgUtil.to_array(_mode().stages().current().get("waypoints", [])):
		if raw is Dictionary:
			var entry: Dictionary = raw
			out.append(RpgUtil.to_float(entry.get("speed", RpgCarPhysics.TOP), RpgCarPhysics.TOP))
	return out

## How near a waypoint the driver turns to the next one, in tiles: early enough to stay on the
## road through a corner.
const REACH := 4.0

## Puts the car on a pickup that lies on the track and sees what it gives; a weapon is fired.
func _pickup_is_taken_and_used() -> String:
	var car := _car()
	var race := _race()
	var mode := _mode()
	if race.pickups.is_empty():
		return "nothing lies on the first track"
	var seen := {}
	for pickup in race.pickups:
		if not pickup.active or seen.has(pickup.kind):
			continue
		seen[pickup.kind] = true
		car.weapon = ""
		car.shielded = false
		car.boosts = 0
		var level := mode.part_level(pickup.kind)
		car.place(pickup.position, _start_heading)
		await _frames(3)
		if pickup.active:
			return "the %s the car stands on was not taken" % pickup.kind
		match pickup.kind:
			"boost":
				if car.boosts != 1:
					return "a boost pickup gave %d boosts" % car.boosts
			"shield":
				if not car.shielded:
					return "a shield pickup gave no shield"
			"missile", "bomb":
				if car.weapon != pickup.kind:
					return "a %s pickup left the car with '%s'" % [pickup.kind, car.weapon]
				Input.action_press(&"fire")
				await _frames(2)
				Input.action_release(&"fire")
				if car.weapon != "" or race.weapons.size() != 1:
					return "pressing fire did not use the %s (%d weapons on the track)" % [pickup.kind, race.weapons.size()]
				var shot := race.weapons[0]
				var ahead := (shot.position - car.position).dot(car.forward())
				if (pickup.kind == "missile") != (ahead > 0.0):
					return "the %s is %s the car" % [pickup.kind, "ahead of" if ahead > 0.0 else "behind"]
				car.place(_start, _start_heading)  # away from its own bomb
				shot.done = true  # a bomb would lie there for twelve seconds
				if not await _wait_for(func() -> bool: return race.weapons.is_empty(), 30):
					return "the %s was not taken off the track" % pickup.kind
			_:
				if mode.part_level(pickup.kind) != level + 1:
					return "the part %s did not make the car better (level %d)" % [pickup.kind, mode.part_level(pickup.kind)]
				if car.top_mul <= 1.0 and car.grip_mul <= 1.0 and car.accel_mul <= 1.0:
					return "the part %s changed nothing of the car" % pickup.kind
	if seen.is_empty():
		return "no pickup of the first track could be taken"
	car.boosts = 1
	await _back_to_start()
	return ""

## One step of the driver that holds the buttons for the player: toward `goal` (px), down to
## `limit` (tiles a second) in time. `stuck` counts the steps the car has stood; a car that is
## stuck backs off. Returns the new count.
func _drive_toward(car: RpgCar, goal: Vector2, limit: float, stuck: int) -> int:
	var tile := car.tile_size
	var to := goal - car.position
	var speed := car.speed_tiles()
	if stuck > 90:  # backing off what it is stuck on, for forty steps
		_hold(&"accelerate", false)
		_hold(&"brake", true)
		_hold(&"move_left", false)
		_hold(&"move_right", false)
		return stuck + 1 if stuck < 130 else 0
	var wheel := RpgCarPhysics.steer_toward(car.heading, to.angle())
	var room := (speed * speed - limit * limit) / (2.0 * RpgCarPhysics.BRAKE) + 2.5
	var slow := speed > limit and to.length() < room * tile
	var turning := absf(RpgCarPhysics.angle_difference(car.heading, to.angle())) > 0.45 and speed > 6.0
	if car.absolute_steering:
		# the arrows are the heading: those of the way to the waypoint, as it is seen
		var seen := car.view()
		var way := seen.screen_vector(to).normalized() if seen != null else to.normalized()
		_hold(&"move_right", way.x > 0.35)
		_hold(&"move_left", way.x < -0.35)
		_hold(&"move_down", way.y > 0.35)
		_hold(&"move_up", way.y < -0.35)
	else:
		_hold(&"move_right", wheel > 0.15)
		_hold(&"move_left", wheel < -0.15)
	_hold(&"brake", slow)
	_hold(&"accelerate", not slow and not turning)
	return stuck + 1 if absf(speed) < 0.6 and not car.is_spinning() else 0

## The race, run again with the rivals: one lap, the player driven with the input actions.
func _race_is_driven_to_the_finish() -> String:
	var car := _car()
	var race := _race()
	var mode := _mode()
	var router := _router()
	var waypoints := _places("waypoints")
	var speeds := _speeds()
	if waypoints.size() < 4 or speeds.size() != waypoints.size():
		return "the track has %d waypoints" % waypoints.size()
	_release_all()
	var first_stage := _stage().stage_index
	var tracks := mode.stages().size()
	var points := mode.score.points
	var over: Array = []
	_results.clear()
	_parts.assign(mode.parts_won)
	var on_over := func(standings: Array) -> void:
		over.append(standings)
		_results.assign(mode.last_results)  # the mode heard of the finish first
		_track_title = _stage().title_text()
	race.finished.connect(on_over, CONNECT_ONE_SHOT)
	race.park_rivals(false)
	race.laps = 1
	race.begin()
	if race.phase != RpgRace.Phase.COUNTDOWN:
		return "the race did not count down again"
	var rivals: Array[RpgCar] = []
	for other in race.cars:
		if other != car:
			rivals.append(other)
			if not other.visible or not (other.get_node_or_null("Input") is RpgRival):
				return "%s is not on the track with a driver" % other.name
	if not await _wait_for(func() -> bool: return race.is_running(), 60 * 6):
		return "the race did not start"
	var grid_place := race.place_of(car)
	if grid_place != race.cars.size():
		return "the player starts the race at place %d of %d, not last" % [grid_place, race.cars.size()]
	var top_mul := car.top_mul
	var accel_mul := car.accel_mul
	var grip_mul := car.grip_mul
	car.top_mul = top_mul * DEBUG_SPEED
	car.accel_mul = accel_mul * DEBUG_SPEED
	car.grip_mul = grip_mul * DEBUG_SPEED
	var tile := car.tile_size
	var target := 0
	var stuck := 0
	var grass := 0
	var steps := 0
	var best := {}
	var passed := 0
	var missed := ""
	var best_place := grid_place
	var gates := race.gates.size()
	var passing := 0
	var pass_side := 1.0
	for i in 60 * 150:
		if not over.is_empty():
			break
		var to := waypoints[target] - car.position
		if to.length() < tile * REACH:
			target = (target + 1) % waypoints.size()
		# round a rival that is in the way, on the side of the road it is not on
		var way := (waypoints[target] - car.position).normalized()
		var beside := way.orthogonal()
		if passing > 0:
			passing -= 1
		else:
			for other in rivals:
				var off := other.position - car.position
				if off.dot(way) > 0.0 and off.dot(way) < tile * PASS_AHEAD and absf(off.dot(beside)) < tile * PASS_BESIDE:
					passing = PASS_STEPS
					pass_side = -1.0 if off.dot(beside) >= 0.0 else 1.0
					break
		var goal := waypoints[target] + (beside * pass_side * tile * PASS_ASIDE if passing > 0 else Vector2.ZERO)
		stuck = _drive_toward(car, goal, speeds[target] * DEBUG_CORNER, stuck)
		await _tree().physics_frame
		steps += 1
		if car.surface == "grass":
			grass += 1
		for other in rivals:
			best[other.get_instance_id()] = maxf(RpgUtil.to_float(best.get(other.get_instance_id(), 0.0)), race.progress(other))
		# the checkpoints of the lap, each counted where it lies and in its order
		var counted := race.checkpoints_of(car)
		if race.lap_of(car) == 1 and counted != passed and over.is_empty():
			var gate: RpgRaceCheckpoint = race.gates[counted - 1] if counted >= 1 and counted <= gates else null
			if counted != passed + 1 or gate == null:
				missed = "checkpoint %d was counted after %d" % [counted, passed]
			elif car.position.distance_to(gate.position) > gate.width:
				missed = "checkpoint %d at %s was counted with the car at %s" % [counted, gate.position, car.position]
			passed = counted
		if steps > 120:  # the first two seconds are the start: the cars are still side by side
			best_place = mini(best_place, race.place_of(car))
	_release_all()
	car.top_mul = top_mul
	car.accel_mul = accel_mul
	car.grip_mul = grip_mul
	if over.is_empty():
		return "the race did not end in 150 s (the player is on lap %d with %d checkpoints, at %s on %s)" % [race.lap_of(car), race.checkpoints_of(car), car.position, car.surface]
	if grass > steps / 5:
		return "the car was on the grass for %d of %d steps of its race" % [grass, steps]
	if missed != "":
		return "the lap was not counted as it was driven: %s" % missed
	if gates < 1 or passed != gates:
		return "the lap ended with %d of the %d checkpoints of the track counted" % [passed, gates]
	if not rivals.is_empty() and best_place >= grid_place:  # a race against the clock has nobody to pass
		return "the player started at place %d and passed no rival in a lap with the debug speed (it came in at place %d, %d steps)" % [grid_place, mode.last_place, steps]
	print("[rpggen] INFO race_is_driven_to_the_finish: %d checkpoints, from place %d to place %d at best, place %d at the finish" % [passed, grid_place, best_place, mode.last_place])
	var table: Array = over[0]
	if table.size() != race.cars.size():
		return "the standings have %d rows for %d cars" % [table.size(), race.cars.size()]
	for n in table.size():
		var row: Dictionary = table[n]
		if RpgUtil.to_int(row.get("place", 0)) != n + 1:
			return "the standings are not in the order of the places"
	var place := mode.last_place
	if place < 1 or place > race.cars.size():
		return "the player came in at place %d of %d" % [place, race.cars.size()]
	for other in rivals:
		# a rival that drives gets well round the track while the player drives a lap
		if RpgUtil.to_float(best[other.get_instance_id()]) < race.gates.size() * 0.5:
			return "%s got no further than %.1f of %d checkpoints" % [other.name, RpgUtil.to_float(best[other.get_instance_id()]), race.gates.size()]
	if mode.score.points <= points:
		return "the place gave no points"
	# the track is over: the next one begins, or the run ends
	if tracks > 1:
		if not await _wait_for(func() -> bool: return _stage() != null and _stage().stage_index == first_stage + 1 and not router.is_busy() and mode.phase == RpgArcadeMode.Phase.PLAYING, 900):
			return "the next track did not begin after the race"
	return ""

## The rows of the race that was driven, as the mode had them when it ended.
var _results: Array[Dictionary] = []
var _parts: Array[String] = []
var _track_title := ""

func _hud() -> RpgRacingHud:
	for node in _tree().root.find_children("*", "CanvasLayer", true, false):
		if node is RpgRacingHud:
			return node as RpgRacingHud
	return null

func _results_and_the_championship() -> String:
	var mode := _mode()
	var cup := mode.championship
	var cars := _results.size()
	if cars < 1:
		return "the race left no results"
	if cup.races != 1:
		return "the championship has %d races after the first" % cup.races
	var table := cup.table()
	if table.size() != cars:
		return "the table has %d drivers for %d cars" % [table.size(), cars]
	var mine := -1
	for i in cars:
		var row := _results[i]
		if RpgUtil.to_int(row.get("place", 0)) != i + 1 or RpgUtil.to_int(row.get("points", -1)) != RpgChampionship.points_for(i + 1):
			return "row %d of the results is %s" % [i + 1, row]
		if RpgUtil.to_bool(row.get("player", false)):
			mine = i
			if not RpgUtil.to_bool(row.get("finished", false)) or RpgUtil.to_float(row.get("time_s", 0.0)) <= 0.0:
				return "the player's row has no time: %s" % [row]
		if RpgUtil.to_str(table[i].get("driver", "")) != RpgUtil.to_str(row.get("driver", "?")):
			return "after one race the table is not in the order of that race"
	if mine < 0 or cup.points_of(RpgChampionship.PLAYER) != RpgChampionship.points_for(mine + 1):
		return "the player has %d points for place %d" % [cup.points_of(RpgChampionship.PLAYER), mine + 1]
	# the screen the game shows after the race (a smoke run does not wait for it)
	var layer := CanvasLayer.new()
	layer.layer = RpgArcadeMode.SCREEN_LAYER
	_tree().root.add_child(layer)
	var screen := RpgRaceResults.new()
	layer.add_child(screen)
	screen.show_results(_track_title, _results, _parts, table, mode.stages().size() == 1)
	await _frames(20)
	var shown := screen.grid_texts("Race")
	var totals := screen.grid_texts("Table")
	var said := screen.heading_shown()
	var box := screen.get_node_or_null("Center/Box") as Control
	var fits := box != null and screen.get_viewport_rect().encloses(box.get_global_rect())
	var box_size := "%s in %s, the screen %s" % [box.get_global_rect(), screen.get_global_rect(), screen.get_viewport_rect()] if box != null else ""
	layer.queue_free()
	if shown.size() != cars or totals.size() != cars:
		return "the results show %d and %d rows for %d cars" % [shown.size(), totals.size(), cars]
	if shown[mine][1] != RpgChampionship.driver_name(RpgChampionship.PLAYER) or shown[mine][2] == "-":
		return "the player's line of the results is %s" % [shown[mine]]
	if said == "":
		return "the results have no heading"
	if not fits:
		return "the results do not fit the screen: %s" % box_size
	if mode.stages().size() == 1:
		return ""  # the run is over: no next track, and nothing of it is saved
	# the save of the run has the table
	var saved: Dictionary = mode.saved_run().get("extra", {})
	if RpgUtil.to_int(saved.get("races", 0)) != 1 or RpgUtil.to_array(saved.get("points", [])).size() != cars:
		return "the save of the run has no table of the championship: %s" % [saved]
	# the HUD of the track that has begun
	var hud := _hud()
	var race := _race()
	if hud == null or race == null:
		return "there is no race HUD, or no race, on the second track"
	await _frames(3)
	if (hud.get_node("Left/Lives") as Label).visible:
		return "the HUD of a racing game shows lives"
	if hud.row_text("lap") == "" or hud.row_text("place") == "" or hud.row_text("speed") == "":
		return "the HUD has no lap, place or speed"
	if hud.row_text("points") != RpgRacingStrings.t("RACE_POINTS", [cup.points_of(RpgChampionship.PLAYER)]):
		return "the HUD's points are '%s'" % hud.row_text("points")
	if race.phase == RpgRace.Phase.COUNTDOWN and not hud.sign_text().is_valid_int():
		return "the sign does not count down: '%s'" % hud.sign_text()
	var map := hud.track_minimap()
	if map == null or not map.visible or map.track_texture() == null:
		return "the HUD has no map of the track"
	var view := map.get_viewport_rect()
	if not view.encloses(map.get_global_rect()):
		return "the map of the track is not on the screen: %s" % [map.get_global_rect()]
	if Vector2i(map.track_texture().get_size()) != _surfaces().size_cells():
		return "the map is %s px for a track of %s cells" % [map.track_texture().get_size(), _surfaces().size_cells()]
	var mine_dots := 0
	for dot in map.dots():
		mine_dots += 1 if RpgUtil.to_bool(dot["player"]) else 0
		var at: Vector2 = dot["position"]
		if not Rect2(Vector2.ZERO, RpgMinimap.VIEW).has_point(at):
			return "a car is off the map at %s" % [at]
	if map.dots().size() != race.cars.size() or mine_dots != 1:
		return "the map has %d dots (%d the player's) for %d cars" % [map.dots().size(), mine_dots, race.cars.size()]
	return ""

func _hold(action: StringName, down: bool) -> void:
	if down:
		Input.action_press(action)
	else:
		Input.action_release(action)

func _tracks_end_with_the_credits() -> String:
	var mode := _mode()
	var router := _router()
	var finished := [mode.phase == RpgArcadeMode.Phase.FINISHED]
	if not finished[0]:
		mode.run_finished.connect(func(_points: int, _rank: int) -> void: finished[0] = true, CONNECT_ONE_SHOT)
	var count := mode.stages().size()
	for index in range(mode.stages().index if not finished[0] else count, count):
		if not await _wait_for(func() -> bool: return _stage() != null and _stage().stage_index == index and not router.is_busy() and mode.phase == RpgArcadeMode.Phase.PLAYING, 900):
			return "track %d did not begin" % (index + 1)
		var car := _car()
		var race := _race()
		if car == null or race == null:
			return "track %d has no car or no race" % (index + 1)
		if _places("waypoints").size() < 4:
			return "track %d has no waypoints" % (index + 1)
		# every other track: its race counts down and starts, and its car gets going on its road
		if not await _wait_for(func() -> bool: return race.is_running(), 60 * 6):
			return "the race of track %d did not start" % (index + 1)
		race.park_rivals(true)
		var from := car.position
		Input.action_press(&"accelerate")
		await _frames(45)
		Input.action_release(&"accelerate")
		if car.position.distance_to(from) < car.tile_size * 2.0 or car.surface == "grass":
			return "the car of track %d did not get going along its road (%s -> %s, on %s)" % [index + 1, from, car.position, car.surface]
		_stage().finish()
	if not await _wait_for(func() -> bool: return finished[0], 900):
		return "the run did not end after its last track was finished"
	var credits := false
	for i in 120:
		for node in router.find_children("*", "Control", true, false):
			if node is RpgCreditsMenu:
				credits = true
		if credits:
			break
		await _tree().process_frame
	if not credits:
		return "the credits did not open after the last track"
	return ""
