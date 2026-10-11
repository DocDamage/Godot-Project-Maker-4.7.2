extends RefCounted
## The smoke steps of a racing game (T16.12): the title and a new game, then the car on its
## first track. It is driven with the real input actions: it speeds up and brakes, steers, is
## slower on the grass, bumps off a barrier, boosts, the camera looks ahead of it, and then it
## is driven once round the track by a simple driver (head for the next corner, brake before
## it). The track is ended by hand (there is no race yet) and the run goes to the credits.

const SAVE_DIR := "user://smoke_saves"
const ACTIONS: Array[StringName] = [&"accelerate", &"brake", &"boost", &"move_left", &"move_right", &"move_up", &"move_down"]

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	return [
		{"name": "title_new_game", "fn": _title_new_game, "timeout_s": 40.0},
		{"name": "car_speeds_up_and_brakes", "fn": _car_speeds_up_and_brakes, "timeout_s": 30.0},
		{"name": "car_steers", "fn": _car_steers, "timeout_s": 30.0},
		{"name": "camera_looks_ahead", "fn": _camera_looks_ahead, "timeout_s": 30.0},
		{"name": "car_boosts", "fn": _car_boosts, "timeout_s": 30.0},
		{"name": "grass_is_slower", "fn": _grass_is_slower, "timeout_s": 40.0},
		{"name": "car_bumps_off_a_barrier", "fn": _car_bumps_off_a_barrier, "timeout_s": 40.0},
		{"name": "car_drives_round_the_track", "fn": _car_drives_round_the_track, "timeout_s": 120.0},
		{"name": "track_ends_with_the_credits", "fn": _track_ends_with_the_credits, "timeout_s": 60.0},
	]

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
	for action: StringName in [&"accelerate", &"brake", &"boost"]:
		if not InputMap.has_action(action):
			return "the input action %s is missing" % action
	await _frames(10)
	if car.surface != "road":
		return "the car does not start on the road (it is on %s at %s)" % [car.surface, car.position]
	var view := Rect2(Vector2.ZERO, tree.root.get_visible_rect().size)
	if not view.has_point(car.get_global_transform_with_canvas().origin):
		return "the car is not on the screen (%s)" % car.get_global_transform_with_canvas().origin
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
	if visual != null and visual.headings > 1 and visual.frame != visual.frame_for(car.heading):
		Input.action_release(&"accelerate")
		return "the picture of the car shows frame %d for the heading %.2f" % [visual.frame, car.heading]
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
	var ahead := (camera.position - car.position).dot(car.forward())
	var zoom := camera.zoom.x
	Input.action_release(&"accelerate")
	if ahead <= car.tile_size:
		return "the camera is %.1f px ahead of a car at speed" % ahead
	if zoom >= 1.0:
		return "the camera did not zoom out with the speed (zoom %.2f)" % zoom
	await _back_to_start()
	await _frames(90)
	if camera.position.distance_to(car.position) > car.tile_size:
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

func _grass_is_slower() -> String:
	var car := _car()
	var surfaces := _surfaces()
	# the field outside the ring: to the left of the start
	var grass := _start + Vector2(-car.tile_size * 3.5, 0.0)
	if surfaces.at(grass) != "grass":
		return "the cell left of the road is %s, not grass" % surfaces.at(grass)
	car.place(grass, _start_heading)
	Input.action_press(&"accelerate")
	await _frames(120)
	var fast := car.speed_tiles()
	var on := car.surface
	Input.action_release(&"accelerate")
	if on != "grass":
		return "the car on the field is on %s" % on
	var most := RpgCarPhysics.top_speed("grass")
	if fast > most + 0.01 or fast < most * 0.8:
		return "two seconds of the pedal on grass made %.1f tiles a second (grass allows %.1f)" % [fast, most]
	await _back_to_start()
	return ""

func _car_bumps_off_a_barrier() -> String:
	var car := _car()
	var bumps: Array[float] = []
	var count := func(lost: float) -> void: bumps.append(lost)
	car.bumped.connect(count)
	# to the left, at the barrier at the edge of the field
	car.place(_start, PI)
	Input.action_press(&"accelerate")
	var hit := await _wait_for(func() -> bool: return not bumps.is_empty(), 240)
	Input.action_release(&"accelerate")
	car.bumped.disconnect(count)
	if not hit:
		return "the car drove to the left for four seconds and bumped into nothing (it is at %s)" % car.position
	if bumps[0] < 1.0:
		return "a bump at speed cost %.1f tiles a second" % bumps[0]
	if car.position.x < 0.0:
		return "the car went through the barrier (it is at %s)" % car.position
	await _frames(20)
	await _back_to_start()
	return ""

## The corners of the ring the driver heads for, in the order the car meets them from the start
## (which is on the left straight, heading up): where the middle of the road turns.
func _corners() -> Array[Vector2]:
	var surfaces := _surfaces()
	var cells := surfaces.size_cells()
	var first := Vector2i(-1, -1)
	var last := Vector2i(-1, -1)
	for y in cells.y:
		for x in cells.x:
			if surfaces.at_cell(Vector2i(x, y)) == "road":
				if first.x < 0:
					first = Vector2i(x, y)
				last = Vector2i(x, y)
	var width := 0
	while surfaces.at_cell(first + Vector2i(width, width)) == "road":
		width += 1
	var half := width * 0.5
	var a := (Vector2(first) + Vector2(half, half)) * surfaces.cell
	var b := (Vector2(last) + Vector2(1.0 - half, 1.0 - half)) * surfaces.cell
	var out: Array[Vector2] = [a, Vector2(b.x, a.y), b, Vector2(a.x, b.y)]
	return out

func _car_drives_round_the_track() -> String:
	var car := _car()
	var corners := _corners()
	corners.append(_start)  # and back to where it began
	var off_road := 0
	var steps := 0
	for goal in corners:
		var reached := false
		for i in 60 * 25:
			var to := goal - car.position
			if to.length() < car.tile_size * 2.5:
				reached = true
				break
			var wheel := RpgCarPhysics.steer_toward(car.heading, to.angle())
			# slow before a corner: no faster than a turn of the road's own width allows
			var slow := to.length() < car.tile_size * 7.0 and car.speed_tiles() > 5.0
			if car.absolute_steering:
				# the arrows are the heading: those of the way to the corner
				var way := to.normalized()
				_hold(&"move_right", way.x > 0.35)
				_hold(&"move_left", way.x < -0.35)
				_hold(&"move_down", way.y > 0.35)
				_hold(&"move_up", way.y < -0.35)
			else:
				_hold(&"move_right", wheel > 0.15)
				_hold(&"move_left", wheel < -0.15)
			_hold(&"brake", slow)
			_hold(&"accelerate", not slow)
			await _tree().physics_frame
			steps += 1
			if car.surface != "road":
				off_road += 1
		if not reached:
			_release_all()
			return "the driver did not reach the corner at %s in 25 s (the car is at %s on %s)" % [goal, car.position, car.surface]
	_release_all()
	if off_road > steps / 10:
		return "the car was off the road for %d of %d steps of its lap" % [off_road, steps]
	if car.position.distance_to(_start) > car.tile_size * 3.0:
		return "the lap did not end where it began (%s, the start is %s)" % [car.position, _start]
	return ""

func _hold(action: StringName, down: bool) -> void:
	if down:
		Input.action_press(action)
	else:
		Input.action_release(action)

func _track_ends_with_the_credits() -> String:
	var mode := _mode()
	var router := _router()
	var stage := _stage()
	var finished := [false]
	mode.run_finished.connect(func(_points: int, _rank: int) -> void: finished[0] = true, CONNECT_ONE_SHOT)
	stage.finish()
	if not await _wait_for(func() -> bool: return finished[0], 900):
		return "the run did not end after its only track was finished"
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
