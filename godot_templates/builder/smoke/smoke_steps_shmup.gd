extends RefCounted
## The smoke steps of a shoot-em-up (T16.04): the title and a new game, then the ship in its
## first stage. It flies with the real input actions, fires into the bullet pool, drops a bomb,
## is destroyed and comes back, while the stage scrolls; then the first wave of enemies is
## fought and a power-up is picked up. The steps about the ship alone hold the scrolling, so
## that no enemy comes while they run. Then the boss of the first stage is fought and beaten,
## and the run is taken through every other stage and its boss to the credits (the stages are
## skipped to their end: the steps are about the bosses and the way from stage to stage).

const SAVE_DIR := "user://smoke_saves"

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	return [
		{"name": "title_new_game", "fn": _title_new_game, "timeout_s": 40.0},
		{"name": "stage_scrolls", "fn": _stage_scrolls, "timeout_s": 20.0},
		{"name": "ship_flies", "fn": _ship_flies, "timeout_s": 20.0},
		{"name": "ship_shoots", "fn": _ship_shoots, "timeout_s": 20.0},
		{"name": "bomb_clears_bullets", "fn": _bomb_clears_bullets, "timeout_s": 20.0},
		{"name": "ship_is_destroyed_and_returns", "fn": _ship_is_destroyed_and_returns, "timeout_s": 20.0},
		{"name": "wave_is_fought", "fn": _wave_is_fought, "timeout_s": 40.0},
		{"name": "power_up_is_picked_up", "fn": _power_up_is_picked_up, "timeout_s": 20.0},
		{"name": "boss_is_beaten", "fn": _boss_is_beaten, "timeout_s": 60.0},
		{"name": "run_reaches_the_credits", "fn": _run_reaches_the_credits, "timeout_s": 240.0},
	]

# ---------------------------------------------------------------- helpers

func _autoload(autoload_name: String) -> Node:
	return _tree().root.get_node_or_null(autoload_name)

func _router() -> RpgSceneRouter:
	return _autoload("SceneRouter") as RpgSceneRouter

func _stage() -> RpgArcadeStage:
	var router := _router()
	return router.current_map as RpgArcadeStage if router != null else null

func _mode() -> RpgShmupMode:
	var router := _router()
	return router.combat as RpgShmupMode if router != null else null

func _ship() -> RpgShmupShip:
	var mode := _mode()
	return mode.ship if mode != null and mode.ship != null and is_instance_valid(mode.ship) else null

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
	if stage.stage_index != 0:
		return "a new game starts in stage %d, not in the first" % (stage.stage_index + 1)
	var cameras := 0
	for node in stage.find_children("*", "Camera2D", true, false):
		if (node as Camera2D).enabled:
			cameras += 1
	if cameras != 1:
		return "a stage must have exactly one enabled camera, the first stage has %d" % cameras
	var mode := _mode()
	if mode == null:
		return "the combat mode is not the shoot-em-up's"
	if _ship() == null:
		return "the first stage has no ship"
	if _pool() == null:
		return "the first stage has no bullet pool"
	if mode.phase != RpgArcadeMode.Phase.PLAYING or mode.lives.count != mode.lives.start_lives:
		return "the run did not start with its lives (phase %d, %d lives)" % [mode.phase, mode.lives.count]
	if mode.stages().size() < 1:
		return "the list of stages is empty"
	return ""

func _stage_scrolls() -> String:
	var stage := _stage()
	var scroll := stage.scroller()
	var before := scroll.progress
	var camera := stage.get_node_or_null("Camera") as Camera2D
	var seen := camera.position
	await _frames(30)
	if scroll.progress <= before:
		return "the stage does not scroll (progress %.1f after 30 frames)" % scroll.progress
	var moved := camera.position - seen
	var way := RpgShmupMath.forward_of(_mode().orientation)
	if moved.dot(way) <= 0.0:
		return "the camera moved %s, not along %s" % [moved, way]
	scroll.hold(self)  # the next steps are about the ship alone: no wave comes meanwhile
	return ""

func _ship_flies() -> String:
	var ship := _ship()
	var start := ship.offset()
	Input.action_press(&"move_right")
	await _frames(20)
	Input.action_release(&"move_right")
	if ship.offset().x <= start.x:
		return "holding move_right did not move the ship (%s -> %s)" % [start, ship.offset()]
	Input.action_press(&"move_left")
	await _frames(600)
	Input.action_release(&"move_left")
	var edge := ship.play_area.position.x + ship.half_size.x
	if absf(ship.offset().x - edge) > 0.5:
		return "the ship did not stop at the left edge of the play area (%.1f, the edge is %.1f)" % [ship.offset().x, edge]
	var view := _tree().root.get_visible_rect().size
	var on_screen := ship.get_global_transform_with_canvas().origin
	if not Rect2(Vector2.ZERO, view).has_point(on_screen):
		return "the ship is not on the screen (%s)" % on_screen
	return ""

func _ship_shoots() -> String:
	var pool := _pool()
	var team := RpgArcadeBulletPool.Team.PLAYER
	if pool.active(team) != 0:
		pool.clear(team)
	Input.action_press(&"shoot")
	await _frames(30)
	Input.action_release(&"shoot")
	var flying := pool.active(team)
	if flying <= 0:
		return "holding shoot fired no bullet"
	var ship := _ship()
	var way := ship.forward()
	for at in pool.positions(team):
		if (at - ship.position).dot(way) < 0.0:
			return "a bullet is behind the ship (%s, the ship is at %s)" % [at, ship.position]
	await _frames(240)
	if pool.active(team) != 0:
		return "%d bullets are still flying 4 s after the last shot: they do not leave the screen" % pool.active(team)
	return ""

func _bomb_clears_bullets() -> String:
	var pool := _pool()
	var ship := _ship()
	var team := RpgArcadeBulletPool.Team.ENEMY
	var sent := RpgShmupEnemyBullet.fire(pool, ship.position - ship.forward() * 60.0, RpgShmupEnemyBullet.ring(12, 0.0))
	if sent != 12 or pool.active(team) != 12:
		return "12 enemy bullets were fired and %d are flying" % pool.active(team)
	var before := ship.bomb().count
	Input.action_press(&"bomb")
	await _frames(3)
	Input.action_release(&"bomb")
	if ship.bomb().count != before - 1:
		return "pressing bomb used %d bombs" % (before - ship.bomb().count)
	if pool.active(team) != 0:
		return "the bomb left %d enemy bullets on the screen" % pool.active(team)
	return ""

func _ship_is_destroyed_and_returns() -> String:
	var mode := _mode()
	var ship := _ship()
	var pool := _pool()
	var lives := mode.lives.count
	RpgShmupEnemyBullet.fire(pool, ship.position, RpgShmupEnemyBullet.ring(1, 0.0))
	await _frames(5)
	if mode.lives.count != lives - 1:
		return "a bullet on the ship took %d lives" % (lives - mode.lives.count)
	if ship.dead or not ship.is_invulnerable():
		return "the ship did not come back blinking (dead %s, invulnerable %s)" % [ship.dead, ship.is_invulnerable()]
	RpgShmupEnemyBullet.fire(pool, ship.position, RpgShmupEnemyBullet.ring(1, 0.0))
	await _frames(5)
	if mode.lives.count != lives - 1:
		return "the ship was hit while it blinked"
	pool.clear(RpgArcadeBulletPool.Team.ENEMY)
	if mode.phase != RpgArcadeMode.Phase.PLAYING:
		return "the run is not being played after a lost life (phase %d)" % mode.phase
	return ""

func _enemies() -> Array[RpgShmupEnemy]:
	var out: Array[RpgShmupEnemy] = []
	for node in _tree().get_nodes_in_group(RpgArcadeBulletPool.TARGET_GROUP):
		if node is RpgShmupEnemy and not node.is_queued_for_deletion():
			out.append(node as RpgShmupEnemy)
	return out

func _wave_is_fought() -> String:
	var stage := _stage()
	var mode := _mode()
	var ship := _ship()
	if stage.spawners.is_empty():
		return "the first stage has no waves"
	var first := stage.spawners[0]
	if not first.is_waiting():
		return "the first wave came while the scrolling was held"
	ship.set(&"_safe_left", 600.0)  # the step is about the enemies: nothing destroys the ship in it
	stage.scroller().release(self)
	if not await _wait_for(func() -> bool: return not first.is_waiting(), 900):
		return "the first wave did not come (progress %.1f, it comes at %.1f)" % [stage.scroller().progress, first.wave.at]
	var came := _enemies()
	if came.size() != first.wave.count:
		return "the first wave is of %d enemies and %d came" % [first.wave.count, came.size()]
	await _frames(120)
	var view := Rect2(Vector2.ZERO, _tree().root.get_visible_rect().size)
	var seen := 0
	for enemy in came:
		if is_instance_valid(enemy) and view.has_point(enemy.get_global_transform_with_canvas().origin):
			seen += 1
	if seen == 0:
		return "no enemy of the first wave is on the screen two seconds after it came"
	var before := mode.score.points
	for enemy in came:
		if is_instance_valid(enemy):
			enemy.take_hit(99)
	if not await _wait_for(func() -> bool: return first.is_cleared(), 60):
		return "the first wave is not cleared after every enemy of it was shot"
	# kills are counted with the multiplier, so only the least they can make is checked
	if mode.score.points < before + first.wave.count * 100 + first.wave.bonus:
		return "%d kills and the bonus of the formation made %d points" % [first.wave.count, mode.score.points - before]
	stage.scroller().hold(self)
	return ""

func _power_up_is_picked_up() -> String:
	var stage := _stage()
	var ship := _ship()
	var scene_path := "res://generated/scenes/shmup/powerup.tscn"
	if not ResourceLoader.exists(scene_path):
		return "%s is missing" % scene_path
	var capsule := (load(scene_path) as PackedScene).instantiate() as RpgShmupPowerup
	if capsule == null:
		return "%s is not a power-up" % scene_path
	capsule.kind = "weapon_up"
	capsule.position = ship.position + ship.forward() * 40.0
	stage.entities().add_child(capsule)
	var level := ship.weapon().level
	var id := capsule.get_instance_id()  # a lambda must not hold a node that is freed meanwhile
	if not await _wait_for(func() -> bool: return not is_instance_id_valid(id), 300):
		return "the capsule did not drift to the ship"
	if ship.weapon().level != level + 1:
		return "a weapon capsule left the weapon at level %d" % ship.weapon().level
	ship.set(&"_safe_left", 0.0)
	stage.scroller().release(self)
	return ""

## Takes the stage that is played to its end: the scroller is put there and what is on the
## screen is shot. Returns the boss when it has come in and fights, or null.
func _skip_to_boss() -> RpgShmupBoss:
	var stage := _stage()
	var ship := _ship()
	if ship != null:
		ship.set(&"_safe_left", 600.0)
	var scroll := stage.scroller()
	scroll.release(self)
	scroll.progress = scroll.length
	for i in 600:
		for enemy in _enemies():
			enemy.take_hit(999)
		if stage.boss != null and is_instance_valid(stage.boss) and stage.boss.is_fighting():
			return stage.boss as RpgShmupBoss
		await _tree().physics_frame
	return null

func _boss_is_beaten() -> String:
	var stage := _stage()
	var mode := _mode()
	var pool := _pool()
	if not stage.has_boss():
		return "the first stage has no boss"
	var boss := await _skip_to_boss()
	if boss == null:
		return "the boss of the first stage did not come in at the end of the stage"
	if not stage.scroller().is_held():
		return "the stage scrolls on while its boss fights"
	var view := Rect2(Vector2.ZERO, _tree().root.get_visible_rect().size)
	if not view.has_point(boss.get_global_transform_with_canvas().origin):
		return "the boss is not on the screen (%s)" % boss.get_global_transform_with_canvas().origin
	if boss.phases.size() < 2:
		return "the boss has %d phase(s); the plan gives it two at least" % boss.phases.size()
	pool.clear(RpgArcadeBulletPool.Team.ENEMY)
	if not await _wait_for(func() -> bool: return pool.active(RpgArcadeBulletPool.Team.ENEMY) > 0, 600):
		return "the boss did not fire in ten seconds"
	var before := boss.phase_index()
	boss.take_hit(boss.health - 1)
	if boss.phase_index() == before:
		return "the boss did not change its phase as its health fell"
	var score := mode.score.points
	boss.take_hit(5)
	if mode.score.points <= score:
		return "beating the boss gave no points"
	if pool.active(RpgArcadeBulletPool.Team.ENEMY) != 0:
		return "the bullets of a beaten boss are still flying"
	var router := _router()
	if mode.stages().size() < 2:
		# the only stage: its boss ends the run
		if not await _wait_for(func() -> bool: return mode.phase == RpgArcadeMode.Phase.FINISHED, 600):
			return "the run did not end after the boss of its only stage"
		return ""
	if not await _wait_for(func() -> bool: return _stage() != null and _stage().stage_index == 1 and not router.is_busy(), 900):
		return "the second stage did not begin after the boss of the first"
	if mode.lives.count < 1 or mode.phase != RpgArcadeMode.Phase.PLAYING:
		return "the run is not being played in the second stage"
	return ""

func _run_reaches_the_credits() -> String:
	var mode := _mode()
	var router := _router()
	# a run of one stage ended with the boss of the step before
	var finished := [mode.phase == RpgArcadeMode.Phase.FINISHED]
	if not finished[0]:
		mode.run_finished.connect(func(_points: int, _rank: int) -> void: finished[0] = true, CONNECT_ONE_SHOT)
	var count := mode.stages().size()
	for index in range(mode.stages().index if not finished[0] else count, count):
		if not await _wait_for(func() -> bool: return _stage() != null and _stage().stage_index == index and not router.is_busy() and mode.phase == RpgArcadeMode.Phase.PLAYING, 900):
			return "stage %d did not begin" % (index + 1)
		var boss := await _skip_to_boss()
		if boss == null:
			return "the boss of stage %d did not come in" % (index + 1)
		boss.take_hit(boss.health)
	if not await _wait_for(func() -> bool: return finished[0], 900):
		return "the run did not end after the boss of the last stage"
	if RpgArcadeHighScores.read().is_empty():
		return "the finished run is not in the high-score table"
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
