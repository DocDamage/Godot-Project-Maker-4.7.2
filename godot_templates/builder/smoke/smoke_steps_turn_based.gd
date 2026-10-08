extends RefCounted
## Turn-based smoke steps, appended after the M6 sequence (which ends in the starter map):
## walk into the starter enemy -> win the battle -> rewards -> back on the map -> the enemy stays
## defeated (also across a map change and a save) -> the defeat policy.
##
## The battle is driven by `combat.auto_choose` (always attack the first enemy), and the player's
## stats are set to a smoke profile first (attack 99), so the outcome does not depend on luck.

const JsonUtil := preload("../lib/json_util.gd")
const ImportedStarter := preload("imported_starter.gd")

const ENEMY_ID := "starter_map_enemy_001"
const STARTER_MAP := "res://game/maps/starter_map.tscn"
const INTERIOR_MAP := "res://game/maps/interior_1.tscn"
const SAVE_DIR := "user://smoke_saves"
const SAVE_SLOT := 2
const VICTORY := 0  # RpgEncounterResult.Outcome
const DEFEAT := 1

var _before := {}  # values remembered between steps

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	var list: Array[Dictionary] = [
		{"name": "encounter_start", "fn": _encounter_start, "timeout_s": 25.0},
		{"name": "battle_victory", "fn": _battle_victory, "timeout_s": 30.0},
		{"name": "rewards_granted", "fn": _rewards_granted, "timeout_s": 10.0},
		{"name": "returned_to_map", "fn": _returned_to_map, "timeout_s": 20.0},
		{"name": "enemy_stays_defeated", "fn": _enemy_stays_defeated, "timeout_s": 60.0},
		{"name": "defeat_policy", "fn": _defeat_policy, "timeout_s": 90.0},
		{"name": "game_over_screen", "fn": _game_over_screen, "timeout_s": 40.0},
	]
	if ImportedStarter.active():  # the imported starter map has no enemy to fight
		for step in list:
			var step_name: String = step["name"]
			if step_name != "game_over_screen":
				step["fn"] = func() -> String: return ImportedStarter.note(step_name)
	return list

func _game_over_screen() -> String:
	return await preload("game_over_check.gd").new().run()

# ---------------------------------------------------------------- helpers

func _autoload(autoload_name: String) -> Node:
	return _tree().root.get_node_or_null(autoload_name)

func _player() -> RpgActor:
	var players := _tree().get_nodes_in_group("player")
	return players[0] as RpgActor if players.size() == 1 else null

func _frames(n: int) -> void:
	for i in n:
		await _tree().physics_frame

func _find_entity(scene: Node, entity_id: String) -> Node2D:
	for node in scene.find_children("*", "", true, false):
		if node is Node2D and node.get("entity_id") != null and str(node.get("entity_id")) == entity_id and not node.is_queued_for_deletion():
			return node
	return null

func _wait_for_map(map_name: String, max_frames: int) -> bool:
	var tree := _tree()
	for i in max_frames:
		await tree.physics_frame
		var router: RpgSceneRouter = _autoload("SceneRouter") as RpgSceneRouter
		var scene := tree.current_scene
		if router != null and not router.is_busy() and scene != null and scene.name == map_name:
			return true
	return false

func _combat() -> RpgCombatMode:
	var router: RpgSceneRouter = _autoload("SceneRouter") as RpgSceneRouter
	return router.combat if router != null else null

## Always attack the first living enemy.
func _attack_first(_actor: Object, _battle: Variant) -> Dictionary:
	return {"command_id": &"attack", "target_index": 0}

## Waits until `box["result"]` is set (by an encounter_finished handler). False on timeout.
func _wait_for_result(box: Dictionary, seconds: float) -> bool:
	var start := Time.get_ticks_msec()
	while box["result"] == null and float(Time.get_ticks_msec() - start) < seconds * 1000.0:
		await _tree().process_frame
	return box["result"] != null

# ---------------------------------------------------------------- steps

func _encounter_start() -> String:
	var tree := _tree()
	var scene := tree.current_scene
	var state: RpgGameState = _autoload("GameState") as RpgGameState
	var bus: RpgEvents = _autoload("Events") as RpgEvents
	var combat := _combat()
	if combat == null:
		return "SceneRouter.combat is not set: boot did not create the combat mode"
	if scene == null or scene.name != "StarterMap":
		return "not in the starter map"
	var enemy := _find_entity(scene, ENEMY_ID)
	if enemy == null:
		return "the starter map has no enemy %s" % ENEMY_ID
	var def: RpgEnemyDefinition = enemy.get("definition")
	if def == null:
		return "the enemy has no definition"

	# The smoke profile, and what the later steps compare with.
	var stats: RpgStats = state.get("player_stats")
	stats.attack = 99
	stats.hp = stats.max_hp
	_before["def"] = def
	_before["gold"] = JsonUtil.to_int(state.get("gold"))
	_before["xp_gained"] = -1
	_before["result"] = null
	bus.experience_gained.connect(func(_id: StringName, amount: int) -> void: _before["xp_gained"] = amount)
	combat.encounter_finished.connect(func(result: RpgEncounterResult) -> void: _before["result"] = result)
	combat.set("auto_choose", Callable(self, "_attack_first"))
	enemy.set("wander_enabled", false)

	# Walk into it from two tiles away.
	var p := _player()
	var tile := JsonUtil.to_float(enemy.get("tile_size"))
	p.global_position = enemy.global_position + Vector2(-2.0 * tile, 0.0)
	p.set_facing("right")
	await _frames(3)
	Input.action_press("move_right")
	var entered := false
	for i in 180:
		await tree.physics_frame
		if tree.current_scene != null and tree.current_scene.name == "Battle":
			entered = true
			break
	Input.action_release("move_right")
	if not entered:
		return "walking into the enemy did not open the battle scene within 3 s"
	_before["pre_pos"] = state.get("player_position")
	if tree.current_scene.get("controller") == null:
		return "the battle scene has no controller"
	return ""

func _battle_victory() -> String:
	# Step 1 hooked encounter_finished into _before["result"].
	if not await _wait_for_result(_before, 25.0):
		return "the battle did not finish within 25 s"
	var result: RpgEncounterResult = _before["result"]
	if result.outcome != VICTORY:
		return "the battle ended with outcome %d instead of VICTORY" % result.outcome
	if result.entity_id != ENEMY_ID:
		return "the result is for %s, not %s" % [result.entity_id, ENEMY_ID]
	return ""

func _rewards_granted() -> String:
	var state: RpgGameState = _autoload("GameState") as RpgGameState
	var def: RpgEnemyDefinition = _before["def"]
	var result: RpgEncounterResult = _before["result"]
	if result.xp != def.xp_reward or result.gold != def.gold_reward:
		return "the result says %d xp / %d gold, the enemy is worth %d / %d" % [result.xp, result.gold, def.xp_reward, def.gold_reward]
	if JsonUtil.to_int(_before["xp_gained"]) != def.xp_reward:
		return "experience_gained reported %d, expected %d" % [_before["xp_gained"], def.xp_reward]
	var gold_delta: int = JsonUtil.to_int(state.get("gold")) - JsonUtil.to_int(_before["gold"])
	if gold_delta != def.gold_reward:
		return "gold changed by %d, expected %d" % [gold_delta, def.gold_reward]
	return ""

func _returned_to_map() -> String:
	var tree := _tree()
	if not await _wait_for_map("StarterMap", 900):
		return "the starter map did not come back after the battle"
	await _frames(3)
	var p := _player()
	if p == null:
		return "no player after the battle"
	var pre_pos: Vector2 = _before["pre_pos"]
	var drift: float = p.global_position.distance_to(pre_pos)
	if drift > 1.0:
		return "the player is %.1f px from where the battle started" % drift
	if not JsonUtil.to_bool(p.get("input_enabled")):
		return "the player's input is still frozen"
	if tree.paused:
		return "the game is paused"
	return ""

func _enemy_stays_defeated() -> String:
	var tree := _tree()
	var state: RpgGameState = _autoload("GameState") as RpgGameState
	var save: RpgSaveManager = _autoload("SaveManager") as RpgSaveManager
	var router: RpgSceneRouter = _autoload("SceneRouter") as RpgSceneRouter
	save.set("dir", SAVE_DIR)
	await _frames(3)  # the freed node leaves the tree
	if _find_entity(tree.current_scene, ENEMY_ID) != null:
		return "the defeated enemy is still on the map"
	if state.get_flag(ENEMY_ID, "defeated", false) != true:
		return "the flag %s.defeated was not set" % ENEMY_ID
	if not save.save(SAVE_SLOT):
		return "SaveManager.save(%d) failed" % SAVE_SLOT
	# Away and back again.
	if ResourceLoader.exists(INTERIOR_MAP):
		await router.go_to(INTERIOR_MAP, &"default")
	await router.go_to(STARTER_MAP, &"default")
	await _frames(4)
	if tree.current_scene == null or tree.current_scene.name != "StarterMap":
		return "did not get back to the starter map"
	if _find_entity(tree.current_scene, ENEMY_ID) != null:
		return "the enemy came back after leaving the map"
	# And through a save.
	if not save.load(SAVE_SLOT):
		return "SaveManager.load(%d) failed" % SAVE_SLOT
	if not await _wait_for_map("StarterMap", 900):
		return "the map did not come back after loading"
	await _frames(4)
	if _find_entity(tree.current_scene, ENEMY_ID) != null:
		return "the enemy came back after loading the save"
	save.delete(SAVE_SLOT)
	return ""

## Starts a fight the player cannot win (an enemy with attack 99 that moves first) and waits for it.
func _lost_fight() -> Dictionary:
	var state: RpgGameState = _autoload("GameState") as RpgGameState
	var combat := _combat()
	var base_def: RpgEnemyDefinition = _before["def"]
	var def := base_def.duplicate(true) as RpgEnemyDefinition
	def.base_stats.attack = 99
	def.base_stats.speed = 99
	def.base_stats.max_hp = 9999
	def.base_stats.hp = 9999
	var data := RpgEncounterData.new()
	data.entity_id = "debug_encounter"
	data.enemies = [def]
	var stats: RpgStats = state.get("player_stats")
	stats.defense = 0
	stats.hp = 1
	var box := {"result": null}
	combat.encounter_finished.connect(func(result: RpgEncounterResult) -> void: box["result"] = result, CONNECT_ONE_SHOT)
	combat.start_encounter(data)
	await _wait_for_result(box, 40.0)
	return box

## True when the lost fight ended in a DEFEAT result.
func _was_defeat(box: Dictionary) -> bool:
	var result: RpgEncounterResult = box["result"]
	return result != null and result.outcome == DEFEAT

func _defeat_policy() -> String:
	var tree := _tree()
	var state: RpgGameState = _autoload("GameState") as RpgGameState
	var save: RpgSaveManager = _autoload("SaveManager") as RpgSaveManager
	var combat := _combat()
	save.set("dir", SAVE_DIR)
	for slot in range(JsonUtil.to_int(save.get("AUTOSAVE_SLOT")), 4):
		save.delete(slot)

	# 1. No save: back at the map's default spawn with full HP.
	var box := await _lost_fight()
	if not _was_defeat(box):
		return "the lost fight did not end in DEFEAT"
	if not await _wait_for_map("StarterMap", 900):
		return "no map after the defeat"
	await _frames(3)
	var stats: RpgStats = state.get("player_stats")
	if stats.hp != stats.max_hp:
		return "without a save the player should be back at full HP, got %d/%d" % [stats.hp, stats.max_hp]
	var map := tree.current_scene as RpgMapRoot
	var p := _player()
	var spawn := map.get_spawn(&"default")
	if p == null or spawn == null or p.global_position.distance_to(spawn.global_position) > 1.0:
		return "the player is not at the default spawn after the defeat"

	# 2. With a save: the game goes back to it.
	stats.hp = stats.max_hp - 3
	var saved_hp := stats.hp
	if not save.save(SAVE_SLOT):
		return "SaveManager.save(%d) failed" % SAVE_SLOT
	box = await _lost_fight()
	if not _was_defeat(box):
		return "the second lost fight did not end in DEFEAT"
	if not await _wait_for_map("StarterMap", 900):
		return "no map after the second defeat"
	await _frames(3)
	var hp_now: int = state.get("player_stats").hp  # loading replaced the stats object
	if hp_now != saved_hp:
		return "with a save the player should be back with the saved HP (%d), got %d" % [saved_hp, hp_now]

	combat.set("auto_choose", Callable())
	save.delete(SAVE_SLOT)
	return ""
