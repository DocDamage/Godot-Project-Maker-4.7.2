extends RefCounted
## The smoke steps of a run and gun (T16.08): the title and a new game, then the soldier in its
## first stage. It runs with the real input actions and the camera follows it, to the right
## only; it jumps, aims up and fires, crouches, throws a grenade, dies and drops back in; and
## then the first wave of enemies is fought, a weapon is picked up, a trap of turrets stops the
## camera until it is destroyed, and at the end of the stage the run ends with the credits. In
## the steps about enemies the soldier is made safe: they are about what comes, not about
## dodging it. The bosses get their steps with their own card.

const SAVE_DIR := "user://smoke_saves"

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	return [
		{"name": "title_new_game", "fn": _title_new_game, "timeout_s": 40.0},
		{"name": "soldier_runs_and_the_camera_follows", "fn": _soldier_runs_and_the_camera_follows, "timeout_s": 30.0},
		{"name": "camera_never_goes_back", "fn": _camera_never_goes_back, "timeout_s": 20.0},
		{"name": "soldier_jumps", "fn": _soldier_jumps, "timeout_s": 20.0},
		{"name": "soldier_aims_and_shoots", "fn": _soldier_aims_and_shoots, "timeout_s": 20.0},
		{"name": "soldier_crouches", "fn": _soldier_crouches, "timeout_s": 20.0},
		{"name": "grenade_goes_off", "fn": _grenade_goes_off, "timeout_s": 20.0},
		{"name": "soldier_dies_and_drops_back_in", "fn": _soldier_dies_and_drops_back_in, "timeout_s": 30.0},
		{"name": "wave_is_fought", "fn": _wave_is_fought, "timeout_s": 60.0},
		{"name": "weapon_is_picked_up", "fn": _weapon_is_picked_up, "timeout_s": 30.0},
		{"name": "trap_stops_the_camera", "fn": _trap_stops_the_camera, "timeout_s": 60.0},
		{"name": "stage_ends_with_the_credits", "fn": _stage_ends_with_the_credits, "timeout_s": 90.0},
	]

# ---------------------------------------------------------------- helpers

func _autoload(autoload_name: String) -> Node:
	return _tree().root.get_node_or_null(autoload_name)

func _router() -> RpgSceneRouter:
	return _autoload("SceneRouter") as RpgSceneRouter

func _stage() -> RpgArcadeStage:
	var router := _router()
	return router.current_map as RpgArcadeStage if router != null else null

func _mode() -> RpgRunAndGunMode:
	var router := _router()
	return router.combat as RpgRunAndGunMode if router != null else null

func _soldier() -> RpgSoldier:
	var mode := _mode()
	return mode.soldier if mode != null and mode.soldier != null and is_instance_valid(mode.soldier) else null

func _pool() -> RpgArcadeBulletPool:
	var stage := _stage()
	return stage.get_node_or_null("Bullets") as RpgArcadeBulletPool if stage != null else null

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
	for action: StringName in [&"move_left", &"move_right", &"move_up", &"move_down", &"jump", &"shoot", &"grenade", &"aim_lock"]:
		if InputMap.has_action(action):
			Input.action_release(action)

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
	if button.get_parent().get_node_or_null("HighScores") == null:
		return "the title screen has no High scores entry"
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
		return "pressing confirm on New Game did not open the first stage"
	var stage := _stage()
	var cameras := 0
	for node in stage.find_children("*", "Camera2D", true, false):
		if (node as Camera2D).enabled:
			cameras += 1
	if cameras != 1:
		return "a stage must have exactly one enabled camera, the first stage has %d" % cameras
	var mode := _mode()
	if mode == null:
		return "the combat mode is not the run and gun's"
	var soldier := _soldier()
	if soldier == null:
		return "the first stage has no soldier"
	if _pool() == null:
		return "the first stage has no bullet pool"
	if not await _wait_for(func() -> bool: return soldier.is_on_floor(), 180):
		return "the soldier does not stand on the floor of the stage (at %s)" % soldier.position
	var view := Rect2(Vector2.ZERO, tree.root.get_visible_rect().size)
	if not view.has_point(soldier.get_global_transform_with_canvas().origin):
		return "the soldier is not on the screen (%s)" % soldier.get_global_transform_with_canvas().origin
	if mode.phase != RpgArcadeMode.Phase.PLAYING or mode.lives.count != mode.lives.start_lives:
		return "the run did not start with its lives (phase %d, %d lives)" % [mode.phase, mode.lives.count]
	return ""

func _soldier_runs_and_the_camera_follows() -> String:
	var stage := _stage()
	var soldier := _soldier()
	var scroll := stage.scroller()
	var camera := stage.get_node_or_null("Camera") as Camera2D
	var from := soldier.position.x
	var seen := camera.position.x
	Input.action_press(&"move_right")
	await _frames(180)
	Input.action_release(&"move_right")
	if soldier.position.x <= from + 16.0:
		return "holding move_right did not move the soldier (%.1f -> %.1f)" % [from, soldier.position.x]
	if soldier.facing != 1:
		return "the soldier does not face the way it runs"
	if scroll.progress <= 0.0 or camera.position.x <= seen:
		return "the camera did not follow the soldier (progress %.1f)" % scroll.progress
	if not soldier.is_on_floor():
		return "the soldier left the floor while running on a flat stage"
	return ""

func _camera_never_goes_back() -> String:
	var stage := _stage()
	var soldier := _soldier()
	var scroll := stage.scroller()
	var reached := scroll.progress
	var from := soldier.position.x
	Input.action_press(&"move_left")
	await _frames(30)
	Input.action_release(&"move_left")
	if soldier.position.x >= from:
		return "holding move_left did not move the soldier back"
	if scroll.progress != reached:
		return "the camera went back with the soldier (progress %.1f -> %.1f)" % [reached, scroll.progress]
	if soldier.facing != -1:
		return "the soldier does not face left"
	return ""

func _soldier_jumps() -> String:
	var soldier := _soldier()
	var floor_y := soldier.position.y
	Input.action_press(&"jump")
	var top := floor_y
	for i in 90:
		await _tree().physics_frame
		top = minf(top, soldier.position.y)
		if i > 10 and soldier.is_on_floor():
			break
	Input.action_release(&"jump")
	if floor_y - top < soldier.tile_size * 2.0:
		return "a held jump rose %.1f px (two tiles are %.1f)" % [floor_y - top, soldier.tile_size * 2.0]
	if not await _wait_for(func() -> bool: return soldier.is_on_floor(), 120):
		return "the soldier did not land again"
	return ""

func _soldier_aims_and_shoots() -> String:
	var soldier := _soldier()
	var pool := _pool()
	var team := RpgArcadeBulletPool.Team.PLAYER
	pool.clear(team)
	Input.action_press(&"move_right")
	await _frames(3)
	Input.action_release(&"move_right")
	Input.action_press(&"shoot")
	await _frames(12)
	if pool.active(team) <= 0:
		Input.action_release(&"shoot")
		return "holding shoot fired no bullet"
	for at in pool.positions(team):
		if at.x < soldier.position.x:
			Input.action_release(&"shoot")
			return "a bullet fired forward is behind the soldier (%s, the soldier is at %s)" % [at, soldier.position]
	pool.clear(team)
	Input.action_press(&"move_up")
	await _frames(12)
	Input.action_release(&"shoot")
	Input.action_release(&"move_up")
	if soldier.aim != Vector2.UP:
		return "holding up aims %s, not up" % soldier.aim
	var flying := pool.positions(team)
	if flying.is_empty():
		return "no bullet was fired upward"
	for at in flying:
		if at.y > soldier.position.y or absf(at.x - soldier.position.x) > soldier.tile_size:
			return "a bullet fired up is not above the soldier (%s, the soldier is at %s)" % [at, soldier.position]
	await _frames(180)
	if pool.active(team) != 0:
		return "%d bullets are still flying 3 s after the last shot" % pool.active(team)
	return ""

func _soldier_crouches() -> String:
	var soldier := _soldier()
	var standing := soldier.hit_radius
	var high := soldier.hit_center().y
	Input.action_press(&"move_down")
	await _frames(6)
	var down := soldier.crouching
	var low := soldier.hit_center().y
	var small := soldier.hit_radius
	var aim := soldier.aim
	Input.action_release(&"move_down")
	await _frames(3)
	if not down:
		return "holding down on the floor is not a crouch"
	if low <= high or small >= standing:
		return "a crouch does not lower what can be hit (%.1f -> %.1f, radius %.1f -> %.1f)" % [high, low, standing, small]
	if aim.y != 0.0:
		return "a crouched soldier aims %s, not forward" % aim
	if soldier.crouching:
		return "the soldier stays down after the button is let go"
	return ""

func _grenade_goes_off() -> String:
	var soldier := _soldier()
	var before := soldier.grenades
	var thrown: Array = []
	soldier.grenade_thrown.connect(func(grenade: Node2D) -> void: thrown.append(grenade.get_instance_id()), CONNECT_ONE_SHOT)
	Input.action_press(&"grenade")
	await _frames(3)
	Input.action_release(&"grenade")
	if soldier.grenades != before - 1 or thrown.is_empty():
		return "pressing grenade threw %d grenades" % (before - soldier.grenades)
	var id: int = thrown[0]
	if not await _wait_for(func() -> bool: return not is_instance_id_valid(id), 240):
		return "the grenade did not go off within four seconds"
	return ""

func _soldier_dies_and_drops_back_in() -> String:
	var mode := _mode()
	var soldier := _soldier()
	var stage := _stage()
	var lives := mode.lives.count
	var floor_y := soldier.position.y
	soldier.hit()
	await _frames(5)
	var expected := lives - 1 if soldier.max_health == 1 else lives
	if mode.lives.count != expected:
		return "a hit took %d lives of a soldier with %d health" % [lives - mode.lives.count, soldier.max_health]
	if soldier.max_health > 1:
		return ""
	if soldier.dead or not soldier.is_invulnerable():
		return "the soldier did not come back blinking (dead %s, invulnerable %s)" % [soldier.dead, soldier.is_invulnerable()]
	if soldier.position.y >= floor_y - soldier.tile_size * 2.0:
		return "the soldier did not drop in from the top of the screen (y %.1f, the floor is at %.1f)" % [soldier.position.y, floor_y]
	if soldier.hit():
		return "the soldier was hit while it blinked"
	if not await _wait_for(func() -> bool: return soldier.is_on_floor(), 240):
		return "the soldier that dropped in did not land"
	if mode.phase != RpgArcadeMode.Phase.PLAYING:
		return "the run is not being played after a lost life (phase %d)" % mode.phase
	if stage.scroller().progress < 0.0:
		return "the stage lost its progress"
	return ""

func _enemies() -> Array[RpgGunEnemy]:
	var out: Array[RpgGunEnemy] = []
	for node in _tree().get_nodes_in_group(RpgArcadeBulletPool.TARGET_GROUP):
		if node is RpgGunEnemy and not node.is_queued_for_deletion():
			out.append(node as RpgGunEnemy)
	return out

## Puts the camera at `progress` of the stage and the soldier two fifths into the screen there
## (the screen's right edge is a wall, so the soldier alone cannot be put ahead of the camera).
func _jump_to(progress: float) -> void:
	var soldier := _soldier()
	var scroll := _stage().scroller()
	scroll.follow(progress)
	soldier.position.x = scroll.view_center().x - soldier.view.x * 0.1
	soldier.velocity = Vector2.ZERO

func _shoot_everything() -> void:
	for enemy in _enemies():
		enemy.die()

func _wave_is_fought() -> String:
	var stage := _stage()
	var mode := _mode()
	var soldier := _soldier()
	if stage.spawners.is_empty():
		return "the first stage has no waves"
	var first := stage.spawners[0]
	if not first.is_waiting():
		return "the first wave came before the soldier reached it (progress %.1f, it comes at %.1f)" % [stage.scroller().progress, first.wave.at]
	soldier.set(&"_safe_left", 600.0)
	Input.action_press(&"move_right")
	var came := await _wait_for(func() -> bool: return not first.is_waiting(), 900)
	Input.action_release(&"move_right")
	if not came:
		return "the first wave did not come (progress %.1f, it comes at %.1f)" % [stage.scroller().progress, first.wave.at]
	var enemies := _enemies()
	if enemies.size() != first.wave.count:
		return "the first wave is of %d enemies and %d came" % [first.wave.count, enemies.size()]
	var from: Array[float] = []
	for enemy in enemies:
		from.append(enemy.position.x)
	await _frames(90)
	var view := Rect2(Vector2.ZERO, _tree().root.get_visible_rect().size)
	var seen := 0
	var moved := 0
	for i in enemies.size():
		if not is_instance_valid(enemies[i]):
			continue
		if view.has_point(enemies[i].get_global_transform_with_canvas().origin):
			seen += 1
		if enemies[i].position.x < from[i] - 8.0:
			moved += 1
	if seen == 0:
		return "no enemy of the first wave is on the screen a second and a half after it came"
	if moved == 0:
		return "no enemy of the first wave came toward the soldier"
	var before := mode.score.points
	_shoot_everything()
	if not await _wait_for(func() -> bool: return first.is_cleared(), 60):
		return "the first wave is not cleared after every enemy of it was shot"
	if mode.score.points < before + first.wave.count * 100:
		return "%d kills made %d points" % [first.wave.count, mode.score.points - before]
	return ""

func _weapon_is_picked_up() -> String:
	var stage := _stage()
	var soldier := _soldier()
	var scene_path := "res://generated/scenes/run_and_gun/weapon_pickup.tscn"
	if not ResourceLoader.exists(scene_path):
		return "%s is missing" % scene_path
	if soldier.weapon() != "machine_gun":
		return "the soldier starts with %s, not with the machine gun" % soldier.weapon()
	var pickup := (load(scene_path) as PackedScene).instantiate() as RpgWeaponPickup
	if pickup == null:
		return "%s is not a weapon pickup" % scene_path
	pickup.weapon = "spread"
	pickup.position = soldier.position + Vector2(0.0, -soldier.tile_size * 4.0)
	stage.entities().add_child(pickup)
	pickup.drop()
	var id := pickup.get_instance_id()
	if not await _wait_for(func() -> bool: return not is_instance_id_valid(id), 300):
		return "the weapon that fell on the soldier was not picked up"
	if soldier.weapon() != "spread" or soldier.gun().bullets_per_shot != 5:
		return "the soldier holds %s after picking up the spread" % soldier.weapon()
	var pool := _pool()
	pool.clear(RpgArcadeBulletPool.Team.PLAYER)
	Input.action_press(&"shoot")
	await _frames(4)
	Input.action_release(&"shoot")
	if pool.active(RpgArcadeBulletPool.Team.PLAYER) < 5:
		return "a shot of the spread is %d bullets" % pool.active(RpgArcadeBulletPool.Team.PLAYER)
	return ""

func _trap_stops_the_camera() -> String:
	var stage := _stage()
	var soldier := _soldier()
	var scroll := stage.scroller()
	var trap: RpgArcadeSpawner = null
	for spawner in stage.spawners:
		if spawner.wave.blocking and spawner.is_waiting():
			trap = spawner
			break
	if trap == null:
		return ""  # a stage without a trap: nothing to stop the camera
	soldier.set(&"_safe_left", 600.0)
	# the camera and the soldier are put where the trap comes; what came on the way is shot
	_jump_to(trap.wave.at)
	if not await _wait_for(func() -> bool: return not trap.is_waiting(), 120):
		return "the trap did not come at its place (progress %.1f, it comes at %.1f)" % [scroll.progress, trap.wave.at]
	for enemy in _enemies():
		if not (enemy is RpgGunTurret):
			enemy.die()
	await _frames(10)
	if not scroll.is_held():
		return "the camera is not held while the trap stands"
	var held_at := scroll.progress
	Input.action_press(&"move_right")
	await _frames(90)
	Input.action_release(&"move_right")
	if scroll.progress != held_at:
		return "the camera went on past a trap that still stands (progress %.1f -> %.1f)" % [held_at, scroll.progress]
	var fired := 0
	for enemy in _enemies():
		if enemy is RpgGunTurret:
			fired += enemy.shots
	_shoot_everything()
	if not await _wait_for(func() -> bool: return trap.is_cleared() and not scroll.is_held(), 120):
		return "the camera is still held after the trap was destroyed"
	return ""

func _stage_ends_with_the_credits() -> String:
	var mode := _mode()
	var soldier := _soldier()
	var stage := _stage()
	var router := _router()
	var scroll := stage.scroller()
	var finished := [false]
	mode.run_finished.connect(func(_points: int, _rank: int) -> void: finished[0] = true, CONNECT_ONE_SHOT)
	_release_all()
	soldier.set(&"_safe_left", 600.0)
	# the camera and the soldier are put a screen before the end, and the soldier runs the
	# rest; what comes is shot
	_shoot_everything()
	await _frames(3)
	_jump_to(scroll.length - soldier.view.x)
	await _frames(5)
	if not soldier.is_on_floor() and not await _wait_for(func() -> bool: return soldier.is_on_floor(), 120):
		return "there is no floor a screen before the end of the stage"
	Input.action_press(&"move_right")
	var done := false
	for i in 1800:
		_shoot_everything()
		if finished[0]:
			done = true
			break
		await _tree().physics_frame
	Input.action_release(&"move_right")
	if not done:
		return "running to the end of the stage did not end it (progress %.1f of %.1f)" % [scroll.progress, scroll.length]
	if not mode.saved_run().is_empty():
		return "a finished run is still in the saved game"
	var credits := false
	for i in 120:
		for node in router.find_children("*", "Control", true, false):
			if node is RpgCreditsMenu:
				credits = true
		if credits:
			break
		await _tree().process_frame
	if not credits:
		return "the credits did not open after the last stage"
	return ""
