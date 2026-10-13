extends RefCounted
## The smoke steps of a shoot-em-up (T16.04): the title and a new game, then the ship in its
## first stage. It flies with the real input actions, fires into the bullet pool, drops a bomb,
## is destroyed and comes back, while the stage scrolls; then the first wave of enemies is
## fought, the second is survived without a shot (the ship is made safe, as it is in every step
## about the enemies), the carrier in the middle of the stage is shot down and the power-up it
## leaves is flown to and picked up. The steps about the ship alone hold the scrolling, so that
## no enemy comes while they run. Then the boss of the first stage is fought and beaten, the
## stage is cleared with its tally, the run that was saved as the second stage began is taken
## up again with Continue on the title screen, and it is taken through every other stage and
## its boss to the credits (the stages are skipped to their end: the steps are about the bosses
## and the way from stage to stage).

## The addon's smoke runner: it knows the folder this run saves into (a run's own).
const SmokeRunner := preload("res://addons/rpg_runtime/debug/smoke_runner.gd")
## What a failed step of this sequence is reported as (docs/spec/03_ERROR_CODES.md).
const CODE := "SMOKE-010"

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	return [
		_step("title_new_game", _title_new_game, 40.0),
		_step("stage_scrolls", _stage_scrolls, 20.0),
		_step("ship_flies", _ship_flies, 20.0),
		_step("ship_shoots", _ship_shoots, 20.0),
		_step("bomb_clears_bullets", _bomb_clears_bullets, 20.0),
		_step("ship_is_destroyed_and_returns", _ship_is_destroyed_and_returns, 20.0),
		_step("wave_is_fought", _wave_is_fought, 40.0),
		_step("second_wave_is_survived", _second_wave_is_survived, 40.0),
		_step("carrier_is_shot_down", _carrier_is_shot_down, 60.0),
		_step("power_up_is_picked_up", _power_up_is_picked_up, 30.0),
		_step("boss_is_beaten", _boss_is_beaten, 60.0),
		_step("run_is_saved_and_continued", _run_is_saved_and_continued, 60.0),
		_step("run_reaches_the_credits", _run_reaches_the_credits, 240.0),
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
	save.set("dir", SmokeRunner.save_dir())  # never touch the player's real saves
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

## The second wave is not shot: it comes, is on the screen, and the ship (which nothing can
## destroy in this step) is still there with its lives when the wave has had its time.
func _second_wave_is_survived() -> String:
	var stage := _stage()
	var mode := _mode()
	var ship := _ship()
	if stage.spawners.size() < 2:
		return "the first stage has %d wave(s); the plan gives it two at least" % stage.spawners.size()
	var second := stage.spawners[1]
	if not second.is_waiting():
		return "the second wave came while the scrolling was held"
	ship.set(&"_safe_left", 600.0)
	var lives := mode.lives.count
	stage.scroller().release(self)
	if not await _wait_for(func() -> bool: return not second.is_waiting(), 900):
		return "the second wave did not come (progress %.1f, it comes at %.1f)" % [stage.scroller().progress, second.wave.at]
	var came := _enemies()
	if came.size() < 1 or came.size() > second.wave.count:
		return "the second wave is of %d enemies and %d came" % [second.wave.count, came.size()]
	var ids: Array[int] = []
	for enemy in came:
		ids.append(enemy.get_instance_id())
	var inside := {}
	for i in 240:
		await _tree().physics_frame
		for id in ids:
			var enemy := instance_from_id(id) as RpgShmupEnemy if is_instance_id_valid(id) else null
			if enemy != null and enemy.is_inside_screen():
				inside[id] = true
	if inside.is_empty():
		return "no enemy of the second wave was on the screen in the four seconds after it came"
	if ship.dead or mode.lives.count < lives or mode.phase != RpgArcadeMode.Phase.PLAYING:
		return "the second wave was not survived (%d of %d lives, phase %d)" % [mode.lives.count, lives, mode.phase]
	for enemy in _enemies():
		enemy.take_hit(999)
	if not await _wait_for(func() -> bool: return second.is_cleared(), 600):
		return "the second wave is not over after what was left of it was shot"
	stage.scroller().hold(self)
	return ""

## The capsule the carrier left, for the step that picks it up (0 when there is none).
var _left_capsule := 0
## How far a capsule may have drifted from where it was left when it is looked for, in px.
const CAPSULE_DRIFT := 24.0

func _capsules() -> Array[RpgShmupPowerup]:
	var out: Array[RpgShmupPowerup] = []
	for node in _stage().entities().get_children():
		if node is RpgShmupPowerup and not node.is_queued_for_deletion():
			out.append(node as RpgShmupPowerup)
	return out

## The carrier in the middle of the stage: the stage is taken to where it comes, it flies in
## and stays, releases a small enemy, takes more than one hit, and leaves its power-up.
func _carrier_is_shot_down() -> String:
	var stage := _stage()
	var mode := _mode()
	var ship := _ship()
	var scroll := stage.scroller()
	var wave: RpgArcadeSpawner = null
	for spawner in stage.spawners:
		if spawner.wave.enemy == "carrier" and spawner.is_waiting():
			wave = spawner
			break
	if wave == null:
		print("[rpggen] INFO carrier_is_shot_down: the first stage has no carrier to come (a list of waves made by hand), step passes")
		return ""
	ship.set(&"_safe_left", 600.0)
	scroll.release(self)
	scroll.progress = maxf(scroll.progress, wave.wave.at)
	var carrier: RpgShmupCarrier = null
	for i in 900:
		carrier = null
		for enemy in _enemies():  # what was passed on the way comes at once and is shot
			if enemy is RpgShmupCarrier:
				carrier = enemy as RpgShmupCarrier
			else:
				enemy.take_hit(999)
		if carrier != null and carrier.is_holding() and (carrier.escort_scene == null or carrier.released > 0):
			break
		await _tree().physics_frame
	if carrier == null:
		return "the carrier did not come (progress %.1f, it comes at %.1f)" % [scroll.progress, wave.wave.at]
	if not carrier.is_holding():
		return "the carrier did not stay on the screen (at %s of the screen)" % carrier.on_screen()
	if carrier.escort_scene != null and carrier.released < 1:
		return "the carrier released no small enemy in fifteen seconds"
	if not carrier.is_inside_screen():
		return "the carrier is not on the screen (%s)" % carrier.on_screen()
	if carrier.health < 2 or carrier.drop == "":
		return "the carrier has %d health and leaves '%s'" % [carrier.health, carrier.drop]
	scroll.hold(self)
	var health := carrier.health
	var before := mode.score.points
	var drop := carrier.drop
	var at := carrier.position
	var known := {}
	for capsule in _capsules():
		known[capsule.get_instance_id()] = true
	carrier.take_hit(health - 1)
	if not is_instance_valid(carrier) or carrier.health != 1 or wave.is_cleared():
		return "%d hits shot down a carrier of %d health" % [health - 1, health]
	carrier.take_hit(1)
	if not await _wait_for(func() -> bool: return wave.is_cleared(), 60):
		return "the wave of the carrier is not cleared after it was shot down"
	if mode.score.points < before + wave.wave.points:
		return "the carrier made %d points, it is worth %d" % [mode.score.points - before, wave.wave.points]
	await _frames(3)  # the capsule is put into the stage after the step of the kill
	_left_capsule = 0
	for capsule in _capsules():
		if not known.has(capsule.get_instance_id()) and capsule.kind == drop and capsule.position.distance_to(at) <= CAPSULE_DRIFT:
			_left_capsule = capsule.get_instance_id()
	if _left_capsule == 0:
		return "the carrier left no '%s' power-up where it was shot down (%s)" % [drop, at]
	return ""

## Holds the move actions that take the ship toward `goal` (a place of the stage).
func _fly_toward(ship: RpgShmupShip, goal: Vector2) -> void:
	var to := goal - ship.position
	_hold(&"move_right", to.x > 2.0)
	_hold(&"move_left", to.x < -2.0)
	_hold(&"move_down", to.y > 2.0)
	_hold(&"move_up", to.y < -2.0)

func _hold(action: StringName, down: bool) -> void:
	if down:
		Input.action_press(action)
	else:
		Input.action_release(action)

func _release_moves() -> void:
	for action: StringName in [&"move_left", &"move_right", &"move_up", &"move_down"]:
		Input.action_release(action)

## The power-up the carrier left is flown to with the move actions and picked up; in a stage
## without a carrier a weapon capsule is put ahead of the ship and drifts to it.
func _power_up_is_picked_up() -> String:
	var stage := _stage()
	var ship := _ship()
	var mode := _mode()
	var capsule := instance_from_id(_left_capsule) as RpgShmupPowerup if _left_capsule != 0 and is_instance_id_valid(_left_capsule) else null
	var flown := capsule != null
	if capsule == null:
		var scene_path := "res://generated/scenes/shmup/powerup.tscn"
		if not ResourceLoader.exists(scene_path):
			return "%s is missing" % scene_path
		capsule = (load(scene_path) as PackedScene).instantiate() as RpgShmupPowerup
		if capsule == null:
			return "%s is not a power-up" % scene_path
		capsule.kind = "weapon_up"
		capsule.position = ship.position + ship.forward() * 40.0
		stage.entities().add_child(capsule)
	var kind := capsule.kind
	var level := ship.weapon().level
	var points := mode.score.points
	var id := capsule.get_instance_id()  # a lambda must not hold a node that is freed meanwhile
	var taken := [false]
	capsule.picked.connect(func(_kind: String) -> void: taken[0] = true, CONNECT_ONE_SHOT)
	capsule = null
	for i in 600:
		if not is_instance_id_valid(id):
			break
		if flown:
			_fly_toward(ship, (instance_from_id(id) as Node2D).position)
		await _tree().physics_frame
	_release_moves()
	if is_instance_id_valid(id):
		return "the '%s' capsule was not reached in ten seconds (it is at %s, the ship at %s)" % [kind, (instance_from_id(id) as Node2D).position, ship.position]
	if not taken[0]:
		return "the '%s' capsule left the screen before the ship had it" % kind
	if kind.begins_with("weapon:"):
		if ship.weapon().kind != kind.trim_prefix("weapon:"):
			return "a '%s' capsule left the ship with the %s weapon" % [kind, ship.weapon().kind]
	elif kind == "weapon_up":
		if ship.weapon().level != level + 1 and mode.score.points <= points:
			return "a weapon capsule left the weapon at level %d and gave no points" % ship.weapon().level
	var pool := _pool()
	pool.clear(RpgArcadeBulletPool.Team.PLAYER)
	Input.action_press(&"shoot")
	await _frames(6)
	Input.action_release(&"shoot")
	var want := RpgShmupWeapon.bullet_count(ship.weapon().kind, ship.weapon().level)
	if pool.active(RpgArcadeBulletPool.Team.PLAYER) < want:
		return "the %s weapon at level %d fires %d bullets and %d are flying" % [ship.weapon().kind, ship.weapon().level, want, pool.active(RpgArcadeBulletPool.Team.PLAYER)]
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
	var cleared: Array = []
	var stage_title := stage.title_text()
	mode.stage_cleared.connect(func(index: int, bonus: Dictionary) -> void: cleared.append([index, bonus, mode.score.points, mode.lives.count]), CONNECT_ONE_SHOT)
	boss.take_hit(5)
	if mode.score.points <= score:
		return "beating the boss gave no points"
	if pool.active(RpgArcadeBulletPool.Team.ENEMY) != 0:
		return "the bullets of a beaten boss are still flying"
	score = mode.score.points
	if not await _wait_for(func() -> bool: return not cleared.is_empty(), 600):
		return "the first stage was not cleared after its boss was beaten"
	var told: Array = cleared[0]
	var shown := await _stage_clear_is_shown(stage_title, told, score)
	if shown != "":
		return shown
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

## The tally of a cleared stage: `told` is what the mode said ([index, bonus, score, lives]),
## `before` the score before it. The screen is put up as the game shows it (a smoke run does
## not wait for it).
func _stage_clear_is_shown(stage_title: String, told: Array, before: int) -> String:
	var bonus: Dictionary = told[1]
	var points := RpgUtil.to_int(told[2])
	var lives := RpgUtil.to_int(told[3])
	var time_bonus := RpgUtil.to_int(bonus.get("time_bonus", -1))
	var life_bonus := RpgUtil.to_int(bonus.get("life_bonus", -1))
	if RpgUtil.to_int(told[0]) != 0:
		return "the stage that was cleared is stage %d" % (RpgUtil.to_int(told[0]) + 1)
	# a bonus for every life the run had; the tally itself may have given one more since
	if life_bonus != lives * RpgArcadeStageClear.LIFE_BONUS and life_bonus != (lives - 1) * RpgArcadeStageClear.LIFE_BONUS:
		return "the tally gives %d for the lives of a run that has %d" % [life_bonus, lives]
	if time_bonus < 0 or RpgUtil.to_int(bonus.get("total", -1)) != time_bonus + life_bonus or points != before + time_bonus + life_bonus:
		return "the tally is %s and the score went from %d to %d" % [bonus, before, points]
	var layer := CanvasLayer.new()
	layer.layer = RpgArcadeMode.SCREEN_LAYER
	_tree().root.add_child(layer)
	var screen := RpgArcadeStageClear.new()
	layer.add_child(screen)
	screen.show_tally(stage_title, bonus, points)
	await _frames(10)
	var heading := screen.find_child("Heading", true, false) as Label
	var rows := screen.find_child("Rows", true, false) as GridContainer
	var box := screen.find_child("Box", true, false) as Control
	var said := heading.text if heading != null else ""
	var values: Array[String] = []
	if rows != null:
		for cell in rows.get_children():
			values.append((cell as Label).text)
	var fits := box != null and screen.get_viewport_rect().encloses(box.get_global_rect())
	layer.queue_free()
	if not said.contains(RpgArcadeStrings.t("ARC_STAGE_CLEAR")):
		return "the heading of the tally is '%s'" % said
	if values.size() != 6 or values[1] != str(time_bonus) or values[3] != str(life_bonus) or values[5] != str(points):
		return "the rows of the tally are %s for %s and a score of %d" % [values, bonus, points]
	if not fits:
		return "the tally does not fit the screen"
	return ""

## The run is saved by itself as a stage begins. What happens after that is not in the save:
## the title screen's Continue takes the run up where the second stage began, with the score
## and the lives it had then.
func _run_is_saved_and_continued() -> String:
	var mode := _mode()
	var router := _router()
	var tree := _tree()
	var saves := _autoload("SaveManager") as RpgSaveManager
	if mode.phase == RpgArcadeMode.Phase.FINISHED:
		# the only stage ended the run, and a finished run is not kept (the last step looks)
		print("[rpggen] INFO run_is_saved_and_continued: a run of one stage has no stage to go on from, step passes")
		return ""
	# the save is written a frame after the stage is entered: the file has to be this stage's
	# before the game is left (the title would otherwise be reached before the save was made)
	var here := _stage().scene_file_path.get_file().get_basename()
	var held := func() -> String: return RpgUtil.to_str(saves.header(RpgSaveManager.AUTOSAVE_SLOT).get("map", ""))
	if not await _wait_for(func() -> bool: return held.call() == here, 120):
		return "the stage that began did not save the run into the autosave slot (the slot holds '%s', the stage is %s)" % [held.call(), here]
	for slot in range(1, RpgSaveManager.SLOTS + 1):
		if saves.has_save(slot):
			return "the run was saved into slot %d, which is the player's" % slot
	var index := _stage().stage_index
	var points := mode.score.points
	var lives := mode.lives.count
	var kept := mode.saved_run()
	if RpgUtil.to_int(kept.get("stage", -1)) != index or RpgUtil.to_int(kept.get("score", -1)) != points or RpgUtil.to_int(kept.get("lives", -1)) != lives:
		return "the saved run is %s; the run is in stage %d with %d points and %d lives" % [kept, index + 1, points, lives]
	if points <= 0:
		return "the run has no points after a stage"
	mode.pickup(500)  # points the save does not have
	if mode.score.points <= points:
		return "a pickup gave no points"
	await _wait_for(func() -> bool: return not router.is_busy(), 300)
	router.go_to(RpgMenuUtil.TITLE_SCENE)
	if not await _wait_for(func() -> bool: return tree.current_scene != null and tree.current_scene.name == "TitleScreen" and not router.is_busy(), 600):
		return "the title screen did not appear"
	var button := (tree.current_scene as Control).get_node("%Continue") as Button
	if button.disabled:
		return "Continue is disabled although the run was saved"
	button.pressed.emit()
	if not await _wait_for(func() -> bool: return _stage() != null and _stage().stage_index == index and not router.is_busy() and _mode() != null and _mode().phase == RpgArcadeMode.Phase.PLAYING, 900):
		var there := "stage %d" % (_stage().stage_index + 1) if _stage() != null else "no stage"
		return "Continue did not open stage %d (it opened %s, the run is in phase %d)" % [index + 1, there, _mode().phase if _mode() != null else -1]
	mode = _mode()
	if mode.score.points != points or mode.lives.count != lives:
		return "the run came back with %d points and %d lives; it was saved with %d and %d" % [mode.score.points, mode.lives.count, points, lives]
	if _ship() == null or _pool() == null:
		return "the stage that was loaded has no ship or no bullet pool"
	if mode.stages().index != index:
		return "the run that came back is in stage %d of its list" % (mode.stages().index + 1)
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
