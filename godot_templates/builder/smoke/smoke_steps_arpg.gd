extends RefCounted
## Action-RPG smoke steps, appended after the M6 sequence (which ends in the starter map):
## an enemy sees the player (and not through a wall) -> the player's attack hits only on its active
## frames -> an enemy dies and pays out -> the player is hurt once per invulnerability window ->
## the dodge -> the defeat persists through a save -> the player's death policy.
##
## Enemies are frozen (`machine.enabled = false`) while the step under test is about the player,
## so the outcome does not depend on what the enemy does.

const ENEMY_1 := "starter_map_enemy_001"
const ENEMY_2 := "starter_map_enemy_002"
const SAVE_DIR := "user://smoke_saves"
const SAVE_SLOT := 3
const DODGE_DISTANCE := 44.0
const DODGE_TOLERANCE := 8.0

var _box := {}  # values remembered between steps

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	return [
		{"name": "enemy_detects", "fn": _enemy_detects, "timeout_s": 25.0},
		{"name": "player_attack_hits", "fn": _player_attack_hits, "timeout_s": 15.0},
		{"name": "no_damage_outside_active_frames", "fn": _no_damage_outside_active_frames, "timeout_s": 15.0},
		{"name": "enemy_dies", "fn": _enemy_dies, "timeout_s": 25.0},
		{"name": "player_hurt_invuln", "fn": _player_hurt_invuln, "timeout_s": 30.0},
		{"name": "dodge", "fn": _dodge, "timeout_s": 15.0},
		{"name": "persist", "fn": _persist, "timeout_s": 40.0},
		{"name": "death_policy", "fn": _death_policy, "timeout_s": 40.0},
	]

# ---------------------------------------------------------------- helpers

func _autoload(autoload_name: String) -> Node:
	return _tree().root.get_node_or_null(autoload_name)

func _player() -> Node2D:
	var players := _tree().get_nodes_in_group("player")
	return players[0] as Node2D if players.size() == 1 else null

func _combat_of(player: Node) -> RpgPlayerCombat:
	return player.get_node_or_null("PlayerCombat") as RpgPlayerCombat

func _frames(n: int) -> void:
	for i in n:
		await _tree().physics_frame

func _seconds(s: float) -> void:
	await _frames(int(ceil(s * 60.0)))

func _find_enemy(entity_id: String) -> RpgEnemyAi:
	var scene := _tree().current_scene
	if scene == null:
		return null
	for node in scene.find_children("*", "", true, false):
		if node is RpgEnemyAi and (node as RpgEnemyAi).entity_id == entity_id and not node.is_queued_for_deletion():
			return node
	return null

func _wait_for_map(map_name: String, max_frames: int) -> bool:
	var tree := _tree()
	for i in max_frames:
		await tree.physics_frame
		var router := _autoload("SceneRouter")
		var scene := tree.current_scene
		if router != null and not router.is_busy() and scene != null and scene.name == map_name:
			return true
	return false

## Holds an action for a few frames (a "just pressed" is seen at least once).
func _tap(action: String) -> void:
	Input.action_press(action)
	await _frames(3)
	Input.action_release(action)

func _freeze(enemy: RpgEnemyAi) -> void:
	enemy.machine.enabled = false
	enemy.move_dir(Vector2.ZERO)

## The player stands `tiles` tiles left of the enemy, facing it; waits until the player can act.
func _stand_next_to(player: Node2D, enemy: RpgEnemyAi, tiles: float) -> void:
	var combat := _combat_of(player)
	for i in 120:
		if combat.state() == RpgPlayerCombat.IDLE or combat.state() == RpgPlayerCombat.MOVE:
			break
		await _tree().physics_frame
	player.global_position = enemy.global_position + Vector2(-tiles * enemy.tile_size, 0.0)
	player.call("set_facing", "right")
	await _frames(2)

func _wait_idle(combat: RpgPlayerCombat, max_frames: int) -> bool:
	for i in max_frames:
		if combat.state() == RpgPlayerCombat.IDLE:
			return true
		await _tree().physics_frame
	return false

# ---------------------------------------------------------------- steps

func _enemy_detects() -> String:
	var tree := _tree()
	var scene := tree.current_scene
	if scene == null or scene.name != "StarterMap":
		return "not in the starter map"
	var p := _player()
	if p == null or _combat_of(p) == null:
		return "the player has no PlayerCombat (is the arpg player scene in the map?)"
	var e1 := _find_enemy(ENEMY_1)
	var e2 := _find_enemy(ENEMY_2)
	if e1 == null or e2 == null:
		return "the starter map needs the enemies %s and %s" % [ENEMY_1, ENEMY_2]
	# Enemy 2 only watches until its own step; enemy 1 stays at home.
	e2.input_enabled = false
	e1.wander.radius_px = 0.0
	var tile := e1.tile_size

	# A wall between them: in range, but no line of sight -> no detection.
	var spot := e1.global_position + Vector2(-3.0 * tile, 0.0)
	p.global_position = spot
	var wall := StaticBody2D.new()
	wall.collision_layer = 1
	wall.collision_mask = 0
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(4.0, tile * 4.0)
	shape.shape = rect
	wall.add_child(shape)
	scene.add_child(wall)
	wall.global_position = e1.global_position + Vector2(-1.5 * tile, 0.0)
	await _seconds(0.8)
	var distance := e1.detection.distance_to_player()
	if distance > e1.detection.vision_px:
		return "the player is %.0f px away, outside the vision radius %.0f px: the wall test would prove nothing" % [distance, e1.detection.vision_px]
	if e1.state() == RpgEnemyAi.ALERT or e1.state() == RpgEnemyAi.CHASE:
		return "the enemy saw the player through a wall (state %s)" % e1.state()
	# The wall goes away: within 2 s the enemy chases.
	wall.queue_free()
	await _frames(3)
	var chased := false
	for i in 120:
		await tree.physics_frame
		if e1.state() == RpgEnemyAi.CHASE:
			chased = true
			break
	if not chased:
		return "with a clear line of sight the enemy did not chase within 2 s (state %s)" % e1.state()
	return ""

func _player_attack_hits() -> String:
	var p := _player()
	var e1 := _find_enemy(ENEMY_1)
	_freeze(e1)
	e1.hurtbox.invulnerable_until_ms = 0
	var combat := _combat_of(p)
	var box := {"hit": false}
	e1.health.changed.connect(func(_hp: int, _max: int) -> void: box["hit"] = true)
	await _stand_next_to(p, e1, 1.0)
	_freeze(e1)
	e1.global_position = p.global_position + Vector2(e1.tile_size, 0.0)
	await _frames(2)
	await _tap("attack")
	for i in 30:  # 0.5 s
		if box["hit"]:
			break
		await _tree().physics_frame
	if not box["hit"]:
		return "the player's attack did not reach the enemy within 0.5 s (player state %s)" % combat.state()
	return ""

func _no_damage_outside_active_frames() -> String:
	var p := _player()
	var e1 := _find_enemy(ENEMY_1)
	var combat := _combat_of(p)
	if not await _wait_idle(combat, 120):
		return "the player did not return to IDLE after the first attack (state %s)" % combat.state()
	_freeze(e1)
	e1.hurtbox.invulnerable_until_ms = 0
	var stats: RpgStats = _autoload("GameState").get("player_stats")
	var hp_before := e1.health.hp()
	var box := {"hit": false}
	e1.health.changed.connect(func(_hp: int, _max: int) -> void: box["hit"] = true)
	# The enemy is far away while the attack starts.
	p.global_position = e1.global_position + Vector2(-5.0 * e1.tile_size, 0.0)
	p.call("set_facing", "right")
	await _frames(2)
	await _tap("attack")
	var hitbox: RpgHitbox = p.get_node("AttackHitbox")
	var seen_active := false
	for i in 90:
		await _tree().physics_frame
		if hitbox.active:
			seen_active = true
		elif seen_active:
			break
	if not seen_active:
		return "the attack hitbox was never active"
	if hitbox.active:
		return "the attack hitbox stayed active for 1.5 s"
	# After the active window the enemy appears inside the hitbox's area.
	e1.global_position = hitbox.global_position - e1.hurtbox.position
	await _seconds(0.5)
	if box["hit"] or e1.health.hp() != hp_before:
		return "the enemy took damage although it entered the hitbox after the active frames"
	if stats == null:
		return "no player stats"
	return ""

func _enemy_dies() -> String:
	var tree := _tree()
	var state := _autoload("GameState")
	var bus := _autoload("Events")
	var p := _player()
	var e1 := _find_enemy(ENEMY_1)
	var combat := _combat_of(p)
	var def := e1.definition as RpgEnemyDefinition
	var stats: RpgStats = state.get("player_stats")
	stats.attack = 99
	_box["gold"] = int(state.get("gold"))
	_box["xp"] = -1
	var died := {"v": false}
	bus.experience_gained.connect(func(_id: StringName, amount: int) -> void: _box["xp"] = amount, CONNECT_ONE_SHOT)
	e1.health.died.connect(func() -> void: died["v"] = true)
	e1.hurtbox.invulnerable_until_ms = 0
	_freeze(e1)
	var start := Time.get_ticks_msec()
	while not died["v"] and Time.get_ticks_msec() - start < 5000:
		if combat.state() == RpgPlayerCombat.IDLE and e1.hurtbox.is_inside_tree():
			e1.hurtbox.invulnerable_until_ms = 0
			p.global_position = e1.global_position + Vector2(-e1.tile_size, 0.0)
			p.call("set_facing", "right")
			await _frames(2)
			await _tap("attack")
		await tree.physics_frame
	if not died["v"]:
		return "the enemy did not die within 5 s of attacking"
	e1.machine.enabled = true  # lets the dead enemy free itself
	await _frames(2)
	if int(_box["xp"]) != def.xp_reward:
		return "experience_gained reported %d, expected %d" % [_box["xp"], def.xp_reward]
	var gold_delta: int = int(state.get("gold")) - int(_box["gold"])
	if gold_delta != def.gold_reward:
		return "gold changed by %d, expected %d" % [gold_delta, def.gold_reward]
	if state.get_flag(ENEMY_1, "defeated", false) != true:
		return "the flag %s.defeated was not set" % ENEMY_1
	return ""

func _player_hurt_invuln() -> String:
	var tree := _tree()
	var state := _autoload("GameState")
	var bus := _autoload("Events")
	var p := _player()
	var combat := _combat_of(p)
	var e2 := _find_enemy(ENEMY_2)
	if e2 == null:
		return "enemy 2 is gone"
	var stats: RpgStats = state.get("player_stats")
	await _wait_idle(combat, 120)
	stats.hp = stats.max_hp
	stats.defense = 2
	var hits: Array[int] = []
	bus.player_damaged.connect(func(amount: int) -> void: hits.append(amount))
	var hurtbox: RpgHurtbox = p.get_node("Hurtbox")
	# Enemy 2 walks up and attacks.
	e2.input_enabled = true
	e2.machine.enabled = true
	e2.wander.radius_px = 0.0
	p.global_position = e2.global_position + Vector2(-2.0 * e2.tile_size, 0.0)
	p.call("set_facing", "right")
	var start := Time.get_ticks_msec()
	while hits.is_empty() and Time.get_ticks_msec() - start < 12000:
		await tree.physics_frame
	if hits.is_empty():
		return "enemy 2 did not hit the player within 12 s (state %s)" % e2.state()
	var first_ms := Time.get_ticks_msec()
	# Freeze the enemy: the next hits are made by hand.
	_freeze(e2)
	var base := RpgArpgMath.base_damage(e2.health.stats().attack, stats.defense)
	if hits[0] != base and hits[0] != int(round(base * RpgArpgMath.CRIT_MULTIPLIER)):
		return "the hit did %d damage, the formula gives %d" % [hits[0], base]
	var hp_after_first := stats.hp
	if hp_after_first != stats.max_hp - hits[0]:
		return "HP is %d after one hit of %d from %d" % [hp_after_first, hits[0], stats.max_hp]
	# A second hit inside the 0.6 s window does nothing.
	var info := RpgDamageInfo.new()
	info.amount = 3
	await _frames(2)
	if hurtbox.receive(info) or stats.hp != hp_after_first:
		return "a second hit within the invulnerability window changed the HP"
	# The HUD shows the new HP without being polled.
	var hud := _autoload("SceneRouter").get_node_or_null("HudArpg")
	if hud == null:
		return "the HUD scene HudArpg is not under the router"
	var hp_text := hud.get_node_or_null("%HpText") as Label
	if hp_text == null or hp_text.text != "%d/%d" % [stats.hp, stats.max_hp]:
		return "the HUD says '%s' but the HP is %d/%d" % [hp_text.text if hp_text != null else "(no label)", stats.hp, stats.max_hp]
	# After the window the next hit lands.
	while Time.get_ticks_msec() - first_ms < 700:
		await tree.physics_frame
	if not hurtbox.receive(info) or stats.hp != hp_after_first - 3:
		return "a hit after the invulnerability window did not land"
	await _wait_idle(combat, 60)
	stats.hp = stats.max_hp
	return ""

func _dodge() -> String:
	var tree := _tree()
	var p := _player()
	var combat := _combat_of(p)
	var map := tree.current_scene as RpgMapRoot
	var spawn := map.get_spawn(&"default")
	if not await _wait_idle(combat, 180):
		return "the player did not return to IDLE (state %s)" % combat.state()
	await _seconds(0.7)  # the cooldown of a dodge is 0.6 s
	p.global_position = spawn.global_position
	p.call("set_facing", "down")
	await _frames(3)
	var before := p.global_position
	var hurtbox: RpgHurtbox = p.get_node("Hurtbox")
	await _tap("dodge")
	var invulnerable := false
	var entered := false
	for i in 60:
		if combat.state() == RpgPlayerCombat.DODGE:
			entered = true
			if hurtbox.is_invulnerable():
				invulnerable = true
		elif entered:
			break
		await tree.physics_frame
	if not entered:
		return "pressing dodge did not start the DODGE state (state %s)" % combat.state()
	if not invulnerable:
		return "the player was not invulnerable during the dodge"
	await _frames(2)
	var moved: float = p.global_position.distance_to(before)
	if absf(moved - DODGE_DISTANCE) > DODGE_TOLERANCE:
		return "the dodge moved the player %.1f px, expected %.0f +- %.0f" % [moved, DODGE_DISTANCE, DODGE_TOLERANCE]
	return ""

func _persist() -> String:
	var tree := _tree()
	var state := _autoload("GameState")
	var save := _autoload("SaveManager")
	save.set("dir", SAVE_DIR)
	await _seconds(0.8)  # a dead enemy frees itself 0.6 s after dying
	if _find_enemy(ENEMY_1) != null:
		return "the dead enemy is still on the map"
	if state.get_flag(ENEMY_1, "defeated", false) != true:
		return "the flag %s.defeated is missing" % ENEMY_1
	if not save.save(SAVE_SLOT):
		return "SaveManager.save(%d) failed" % SAVE_SLOT
	if not save.load(SAVE_SLOT):
		return "SaveManager.load(%d) failed" % SAVE_SLOT
	if not await _wait_for_map("StarterMap", 900):
		return "the map did not come back after loading"
	await _frames(4)
	if _find_enemy(ENEMY_1) != null:
		return "the dead enemy came back after loading the save"
	if _find_enemy(ENEMY_2) == null:
		return "the living enemy 2 is gone after loading"
	save.delete(SAVE_SLOT)
	return ""

func _death_policy() -> String:
	var tree := _tree()
	var state := _autoload("GameState")
	var save := _autoload("SaveManager")
	var router := _autoload("SceneRouter")
	save.set("dir", SAVE_DIR)
	for slot in range(1, 4):
		save.delete(slot)  # no save: the player wakes up at the default spawn
	var p := _player()
	var e2 := _find_enemy(ENEMY_2)
	if p == null or e2 == null:
		return "no player or no enemy 2 after loading"
	var stats: RpgStats = state.get("player_stats")
	stats.defense = 0
	stats.hp = 1
	e2.input_enabled = true
	e2.machine.enabled = true
	e2.wander.radius_px = 0.0
	p.global_position = e2.global_position + Vector2(-2.0 * e2.tile_size, 0.0)
	p.call("set_facing", "right")
	var combat := _combat_of(p)
	var start := Time.get_ticks_msec()
	while combat.state() != RpgPlayerCombat.DEAD and Time.get_ticks_msec() - start < 12000:
		await tree.physics_frame
	if combat.state() != RpgPlayerCombat.DEAD:
		return "the player did not die within 12 s with 1 HP (HP %d)" % stats.hp
	# The policy starts 1.5 s after the death: the router goes busy and the map is loaded again.
	var saw_busy := false
	for i in 600:
		await tree.physics_frame
		if router.is_busy():
			saw_busy = true
		elif saw_busy:
			break
	if not saw_busy:
		return "no respawn followed the death"
	if not await _wait_for_map("StarterMap", 300):
		return "the map did not come back after the death"
	await _frames(3)
	var after: Node2D = _player()
	stats = state.get("player_stats")
	if after == null or stats.hp <= 0:
		return "after the death the player has %d HP" % (stats.hp if stats != null else -1)
	var spawn := (tree.current_scene as RpgMapRoot).get_spawn(&"default")
	if after.global_position.distance_to(spawn.global_position) > 1.0:
		return "the player did not respawn at the default spawn"
	if not bool(after.get("input_enabled")):
		return "the respawned player cannot move"
	return ""
