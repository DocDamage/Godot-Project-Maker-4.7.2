extends RefCounted
## M6 smoke scenario, the shared core sequence: title -> new game -> walk -> talk to the NPC -> open
## the chest -> building round trip -> save -> mutate -> load -> pause menu.
##
## The M1 and M4 step files are composed in here because the game now starts at the title screen
## and the order matters (the NPC and chest steps sit between them).

const JsonUtil := preload("../lib/json_util.gd")

const SAVE_DIR := "user://smoke_saves"
const NPC_ID := "starter_map_npc_001"
const CHEST_ID := "starter_map_chest_001"

var _m1 := preload("smoke_steps_m1.gd").new()
var _m4 := preload("smoke_steps_m4.gd").new()
var _before := {}  # values remembered between steps

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	var list: Array[Dictionary] = []
	list.append({"name": "title_new_game", "fn": _title_new_game, "timeout_s": 30.0})
	list.append({"name": "map_music", "fn": _map_music, "timeout_s": 15.0})
	list.append_array(_m1.steps())
	list.append({"name": "npc_dialogue", "fn": _npc_dialogue, "timeout_s": 40.0})
	list.append({"name": "chest_open", "fn": _chest_open, "timeout_s": 20.0})
	# building_round_trip: the M4 steps.
	list.append_array(_m4.steps())
	list.append({"name": "autosave", "fn": _autosave, "timeout_s": 40.0})
	list.append({"name": "save_slot_1", "fn": _save_slot_1, "timeout_s": 10.0})
	list.append({"name": "mutate_then_load", "fn": _mutate_then_load, "timeout_s": 30.0})
	list.append({"name": "pause_menu", "fn": _pause_menu, "timeout_s": 15.0})
	return list

# ---------------------------------------------------------------- helpers

func _autoload(autoload_name: String) -> Node:
	return _tree().root.get_node_or_null(autoload_name)

func _player() -> RpgActor:
	var players := _tree().get_nodes_in_group("player")
	return players[0] as RpgActor if players.size() == 1 else null

func _frames(n: int) -> void:
	for i in n:
		await _tree().physics_frame

## True as soon as `done` returns true within `max_frames` physics frames.
func _wait_for(done: Callable, max_frames: int) -> bool:
	for i in max_frames:
		if done.call():
			return true
		await _tree().physics_frame
	return JsonUtil.to_bool(done.call())

func _wait_for_map(map_name: String, max_frames: int) -> bool:
	var tree := _tree()
	for i in max_frames:
		await tree.physics_frame
		var router: RpgSceneRouter = _autoload("SceneRouter") as RpgSceneRouter
		var scene := tree.current_scene
		if router != null and not router.is_busy() and scene != null and scene.name == map_name:
			return true
	return false

func _action_event(action: String, pressed: bool) -> InputEventAction:
	var ev := InputEventAction.new()
	ev.action = action
	ev.pressed = pressed
	return ev

## Presses and releases an input action through the event pipeline.
func _press(action: String) -> void:
	Input.parse_input_event(_action_event(action, true))
	await _tree().process_frame
	Input.parse_input_event(_action_event(action, false))
	await _tree().process_frame

func _find_entity(scene: Node, entity_id: String) -> Node2D:
	for node in scene.find_children("*", "", true, false):
		if node is Node2D and node.get("entity_id") != null and str(node.get("entity_id")) == entity_id:
			return node
	return null

## Puts the player just below `target` facing up, so its interaction area overlaps the target.
func _stand_below(target: Node2D) -> void:
	var p := _player()
	p.global_position = target.global_position + Vector2(0, 9)
	p.set_facing("up")
	await _frames(3)

## Interacts and waits for `done` to return true. Returns false on timeout.
func _interact_until(done: Callable, max_frames: int = 60) -> bool:
	var tree := _tree()
	Input.action_press("interact")
	await _frames(2)
	Input.action_release("interact")
	for i in max_frames:
		if done.call():
			return true
		await tree.physics_frame
	return JsonUtil.to_bool(done.call())

# ---------------------------------------------------------------- steps

func _title_new_game() -> String:
	var tree := _tree()
	var save: RpgSaveManager = _autoload("SaveManager") as RpgSaveManager
	if save == null or _autoload("GameState") == null:
		return "SaveManager or GameState autoload is missing"
	save.set("dir", SAVE_DIR)  # never touch the player's real saves
	for slot in range(1, 4):
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
	var router: RpgSceneRouter = _autoload("SceneRouter") as RpgSceneRouter
	for i in 600:  # the fade-in of the title is still running; go_to calls during it are ignored
		if not router.is_busy():
			break
		await tree.process_frame
	var button := title.get_node("%NewGame") as Button
	for i in 120:  # let the deferred initial focus happen
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
	if not await _wait_for_map("StarterMap", 600):
		return "pressing confirm on New Game did not open the starter map"
	return ""

## The sound slots of the generated config (slot -> asset id; missing or "" = silent).
func _configured_sounds() -> Dictionary:
	var path := "res://rpggen/generator_config.json"
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if parsed is Dictionary:
		var table: Dictionary = parsed
		var sounds: Dictionary = table.get("sounds", {})
		return sounds
	return {}

func _audio() -> RpgAudio:
	var router: RpgSceneRouter = _autoload("SceneRouter") as RpgSceneRouter
	return router.audio as RpgAudio if router != null else null

## When a map music is configured, the starter map starts it. A pack without music passes with a note.
func _map_music() -> String:
	var wanted := str(_configured_sounds().get("music_map", ""))
	if wanted == "":
		print("[rpggen] INFO map_music: no map music is configured, step passes")
		return ""
	var audio := _audio()
	if audio == null:
		return "the game has no audio service"
	for i in 120:
		if str(audio.get("current_music_id")) == wanted:
			return ""
		await _tree().process_frame
	return "the map music should be %s but %s plays" % [wanted, str(audio.get("current_music_id"))]

func _npc_dialogue() -> String:
	var tree := _tree()
	var scene := tree.current_scene
	var state: RpgGameState = _autoload("GameState") as RpgGameState
	var bus: RpgEvents = _autoload("Events") as RpgEvents
	var npc := _find_entity(scene, NPC_ID)
	if npc == null:
		print("[rpggen] INFO npc_dialogue: the starter map has no NPC, step passes")
		return ""
	var seen := {"started": false, "finished": false}
	bus.dialogue_started.connect(func(_r: Resource) -> void: seen["started"] = true)
	bus.dialogue_finished.connect(func(_r: Resource) -> void: seen["finished"] = true)
	var potions_before: int = state.inventory.count(&"potion")
	await _stand_below(npc)
	if not await _interact_until(func() -> bool: return seen["started"]):
		return "interacting with the NPC did not start a dialogue"
	for i in 60:
		if seen["finished"]:
			break
		await _press("confirm")  # completes the typing, advances, or picks choice 0
		await _frames(2)
	if not seen["finished"]:
		return "the dialogue did not finish"
	if state.get_flag("starter_npc", "talked", false) != true:
		return "flag starter_npc.talked was not set"
	var gained: int = state.inventory.count(&"potion") - potions_before
	if gained != 1:
		return "expected 1 potion from the NPC, got %d" % gained
	await _frames(6)  # input is re-enabled two physics frames after the box closes
	return ""

func _chest_open() -> String:
	var tree := _tree()
	var scene := tree.current_scene
	var state: RpgGameState = _autoload("GameState") as RpgGameState
	var chest := _find_entity(scene, CHEST_ID)
	if chest == null:
		print("[rpggen] INFO chest_open: the starter map has no chest, step passes")
		return ""
	var gold_before: int = state.gold
	var audio := _audio()
	var expects_sound: bool = str(_configured_sounds().get("sfx_chest", "")) != "" and audio != null
	await _stand_below(chest)
	var opened := func() -> bool: return state.get_flag(CHEST_ID, "opened", false) == true
	if not await _interact_until(opened):
		return "interacting with the chest did not open it"
	if state.gold <= gold_before:
		return "opening the chest gave no gold"
	if expects_sound:
		var chest_sound: AudioStream = audio.bank.stream(&"sfx_chest")
		var heard := chest_sound == null  # a slot that does not load is VAL-020's business
		for i in 15:
			if heard:
				break
			for child in audio.get_children():
				var player := child as AudioStreamPlayer
				if player != null and player.playing and player.stream == chest_sound:
					heard = true
			await _tree().physics_frame
		if not heard:
			return "opening the chest played no sound although sfx_chest is configured"
	else:
		print("[rpggen] INFO chest_open: no chest sound is configured, the sound check is skipped")
	return ""

## Entering a map writes the autosave (slot 0) with that map in its header; with the setting off
## nothing is written. The map is entered again through the router, as the game does it.
func _autosave() -> String:
	var tree := _tree()
	var save: RpgSaveManager = _autoload("SaveManager") as RpgSaveManager
	var settings: RpgSettingsStore = _autoload("RpgSettings") as RpgSettingsStore
	var router: RpgSceneRouter = _autoload("SceneRouter") as RpgSceneRouter
	var map := tree.current_scene as RpgMapRoot
	if save == null or router == null or map == null:
		return "no SaveManager, SceneRouter or map"
	var map_path := map.scene_file_path
	save.set("dir", SAVE_DIR)
	var was_on: bool = settings == null or JsonUtil.to_bool(settings.get("autosave"))
	# 1. on: the autosave appears
	if settings != null:
		settings.set("autosave", true)
	save.delete(0)
	save.reset_autosave_cooldown()
	router.go_to(map_path, &"default")
	if not await _wait_for_map("StarterMap", 600):
		return "the map did not come back"
	var wrote := await _wait_for(func() -> bool: return save.has_save(0), 120)
	if not wrote:
		return "entering the map wrote no autosave"
	var header: Dictionary = save.header(0)
	if str(header.get("map", "")) != "starter_map":
		return "the autosave header names the map '%s', not the starter map" % str(header.get("map", ""))
	# 2. off: nothing is written
	if settings != null:
		settings.set("autosave", false)
	save.delete(0)
	save.reset_autosave_cooldown()
	router.go_to(map_path, &"default")
	if not await _wait_for_map("StarterMap", 600):
		return "the map did not come back (autosave off)"
	await _frames(30)
	var wrote_anyway: bool = save.has_save(0)
	if settings != null:
		settings.set("autosave", was_on)
	if wrote_anyway:
		return "an autosave was written although the setting is off"
	return ""

func _save_slot_1() -> String:
	var save: RpgSaveManager = _autoload("SaveManager") as RpgSaveManager
	return "" if save.save(1) else "SaveManager.save(1) returned false"

func _mutate_then_load() -> String:
	var tree := _tree()
	var state: RpgGameState = _autoload("GameState") as RpgGameState
	var save: RpgSaveManager = _autoload("SaveManager") as RpgSaveManager
	var p := _player()
	if tree.current_scene == null or tree.current_scene.name != "StarterMap" or p == null:
		return "not in the starter map"
	var saved_pos := p.global_position
	var saved_gold: int = state.gold
	var tile := 16.0
	var ground := tree.current_scene.get_node_or_null("Ground") as TileMapLayer
	if ground != null and ground.tile_set != null:
		tile = float(ground.tile_set.tile_size.x)
	p.global_position += Vector2(5.0 * tile, 0.0)
	state.gold = saved_gold + 100
	await _frames(2)
	if not save.load(1):
		return "SaveManager.load(1) returned false"
	if not await _wait_for_map("StarterMap", 600):
		return "the map did not come back after loading"
	await _frames(2)
	p = _player()
	if p == null:
		return "no player after loading"
	if p.global_position.distance_to(saved_pos) > 1.0:
		return "player restored %.1f px away from the saved position" % p.global_position.distance_to(saved_pos)
	if state.gold != saved_gold:
		return "gold is %d after loading, expected %d" % [state.gold, saved_gold]
	var chest := _find_entity(tree.current_scene, CHEST_ID)
	if chest != null and not JsonUtil.to_bool(chest.get("opened")):
		return "the chest is closed again after loading"
	return ""

func _pause_menu() -> String:
	var tree := _tree()
	var failure := ""
	await _press("menu")
	for i in 10:
		await tree.process_frame
	if not tree.paused:
		failure = "pressing menu did not pause the game"
	else:
		var focus := tree.root.gui_get_focus_owner()
		if focus == null or focus.name != "Resume":
			failure = "focus is on %s, expected Resume" % (focus.name if focus != null else "nothing")
		await _press("cancel")
		for i in 5:
			await tree.process_frame
		if failure == "" and tree.paused:
			failure = "cancel did not close the pause menu"
	tree.paused = false
	var save: RpgSaveManager = _autoload("SaveManager") as RpgSaveManager
	for slot in range(1, 4):
		save.delete(slot)
	return failure
