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
	list.append({"name": "save_overwrite_confirm", "fn": _save_overwrite_confirm, "timeout_s": 15.0})
	list.append({"name": "equip_raises_attack", "fn": _equip_raises_attack, "timeout_s": 15.0})
	list.append({"name": "shop_buy_sell", "fn": _shop_buy_sell, "timeout_s": 20.0})
	list.append({"name": "quest_journal", "fn": _quest_journal, "timeout_s": 20.0})
	list.append({"name": "party_members", "fn": _party_members, "timeout_s": 20.0})
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

var _asked: Array[int] = []
var _answer := false

## The save menu's auto-confirm hook (instead of the dialog): records the slot, answers `_answer`.
func _on_overwrite_asked(slot: int) -> bool:
	_asked.append(slot)
	return _answer

## Saving over a used slot asks first: "no" leaves the save as it was, "yes" replaces it, and an
## empty slot is saved without a question.
func _save_overwrite_confirm() -> String:
	var state: RpgGameState = _autoload("GameState") as RpgGameState
	var save: RpgSaveManager = _autoload("SaveManager") as RpgSaveManager
	if state == null or save == null or not save.has_save(1):
		return "slot 1 has no save to overwrite"
	var menu := (load(RpgMenuUtil.scene_path("save_load_menu")) as PackedScene).instantiate() as RpgSaveLoadMenu
	menu.mode = "save"
	menu.confirm_overwrite = _on_overwrite_asked
	_tree().root.add_child(menu)
	_asked.clear()
	var gold: int = state.gold
	var failure := ""
	state.gold = gold + 1
	_answer = false
	(menu.get_node("%Slot1") as Button).pressed.emit()
	await _frames(3)
	if _asked != [1]:
		failure = "pressing a used slot asked %s, expected [1]" % str(_asked)
	elif RpgUtil.to_int(save.header(1).get("gold", -1)) != gold:
		failure = "the save was replaced although the answer was no"
	if failure == "":
		_answer = true
		(menu.get_node("%Slot1") as Button).pressed.emit()
		await _frames(3)
		if _asked != [1, 1]:
			failure = "the second press asked %s, expected [1, 1]" % str(_asked)
		elif RpgUtil.to_int(save.header(1).get("gold", -1)) != gold + 1:
			failure = "the save was not replaced although the answer was yes"
	if failure == "":
		save.delete(3)
		(menu.get_node("%Slot3") as Button).pressed.emit()
		await _frames(3)
		if _asked.size() != 2:
			failure = "an empty slot asked before saving"
		elif not save.has_save(3):
			failure = "an empty slot was not saved"
		save.delete(3)
	state.gold = gold
	save.save(1)  # slot 1 is what it was after save_slot_1, for the next step
	menu.queue_free()
	return failure

## Wearing a weapon from the status menu raises the attack stat (and the menu says so); taking it
## off puts the stat back. The sword is a test item, removed again afterwards.
func _equip_raises_attack() -> String:
	var state: RpgGameState = _autoload("GameState") as RpgGameState
	if state == null:
		return "GameState is missing"
	var sword := RpgItemDefinition.new()
	sword.id = &"smoke_sword"
	sword.display_name = "Smoke Sword"
	sword.category = RpgItemDefinition.Category.WEAPON
	sword.max_stack = 1
	var mods: Array[Dictionary] = [{"stat": "attack", "add": 3.0, "mul": 1.0}]
	sword.modifiers = mods
	state.items[sword.id] = sword
	state.inventory.add(sword.id, 1)
	var id: StringName = state.player_actor_id
	var before: float = state.stat_of(id, &"attack")
	var menu := (load(RpgMenuUtil.scene_path("status_menu")) as PackedScene).instantiate() as RpgStatusMenu
	_tree().root.add_child(menu)
	await _frames(2)
	var failure := ""
	var slot_button := menu.find_child("Slot_weapon", true, false) as Button
	if slot_button == null:
		failure = "the status menu has no weapon slot"
	else:
		slot_button.pressed.emit()
		await _frames(2)
		var choice := menu.find_child("Choice_smoke_sword", true, false) as Button
		if choice == null:
			failure = "the equip picker does not offer the sword"
		else:
			choice.pressed.emit()
			await _frames(3)
	if failure == "":
		var after: float = state.stat_of(id, &"attack")
		var shown := ""
		for label in menu.find_children("*", "Label", true, false):
			if (label as Label).text.begins_with(menu.tr("UI_ATTACK") + ":"):
				shown = (label as Label).text
		if state.equipped_in(id, &"weapon") != sword.id:
			failure = "the sword was not equipped"
		elif absf(after - before - 3.0) > 0.001:
			failure = "attack went from %s to %s, expected +3" % [before, after]
		elif not shown.ends_with(str(roundi(after))):
			failure = "the status menu shows '%s', expected attack %d" % [shown, roundi(after)]
	if state.equipped_in(id, &"weapon") == sword.id:
		state.unequip(id, &"weapon")
	if failure == "" and absf(state.stat_of(id, &"attack") - before) > 0.001:
		failure = "attack did not return to %s after taking the sword off" % before
	state.inventory.remove(sword.id, state.inventory.count(sword.id))
	state.items.erase(sword.id)
	menu.queue_free()
	return failure

## The village shop through the event bus (what `open_shop:village_shop` does): it opens paused,
## pressing the potion buys one for its price, pressing it with no gold buys nothing, and the Sell
## tab pays back half. Everything is put back afterwards.
func _shop_buy_sell() -> String:
	var tree := _tree()
	var state: RpgGameState = _autoload("GameState") as RpgGameState
	var router: Node = _autoload("SceneRouter")
	var controller := router.get_node_or_null("UiController") as RpgUiController if router != null else null
	if state == null or controller == null:
		return "GameState or the UiController is missing"
	if RpgShopDefinition.load_shop(&"village_shop") == null:
		return "game/data/shops/village_shop.tres was not seeded"
	var gold: int = state.gold
	var potions: int = state.inventory.count(&"potion")
	state.gold = 100
	RpgUtil.emit(&"shop_requested", [&"village_shop"])
	var menu: RpgShopMenu = null
	for i in 30:
		await tree.physics_frame
		menu = _shop_menu(controller)
		if menu != null:
			break
	var failure := ""
	if menu == null:
		failure = "the shop did not open"
	elif not tree.paused:
		failure = "the game was not paused behind the shop"
	if failure == "":
		var potion := _shop_row(menu, &"potion")
		if potion == null:
			failure = "the potion is not on sale"
		else:
			potion.pressed.emit()
			await _frames(2)
			if state.gold != 90 or state.inventory.count(&"potion") != potions + 1:
				failure = "buying a potion left gold %d and %d potions" % [state.gold, state.inventory.count(&"potion")]
	if failure == "":
		state.gold = 0
		_shop_row(menu, &"potion").pressed.emit()
		await _frames(2)
		if state.inventory.count(&"potion") != potions + 1:
			failure = "a potion was bought without gold"
	if failure == "":
		menu.set_mode(RpgShopMenu.SELL)
		await _frames(2)
		var sell_row := _shop_row(menu, &"potion")
		if sell_row == null:
			failure = "the potion cannot be sold"
		else:
			sell_row.pressed.emit()
			await _frames(2)
			if state.gold != 5 or state.inventory.count(&"potion") != potions:
				failure = "selling left gold %d and %d potions" % [state.gold, state.inventory.count(&"potion")]
	if menu != null and is_instance_valid(menu):
		menu.close()
	await _frames(2)
	if failure == "" and tree.paused:
		failure = "closing the shop did not unpause the game"
	tree.paused = false
	state.gold = gold
	return failure

func _shop_menu(controller: RpgUiController) -> RpgShopMenu:
	var open_menu: Node = controller.get("_menu")
	return open_menu as RpgShopMenu

func _shop_row(menu: RpgShopMenu, item_id: StringName) -> Button:
	for row in menu.rows():
		if menu.item_of(row) == item_id:
			return row
	return null

## The demo quest "errand" followed the real play so far (the villager started it, the talk and the
## chest finished two stages), telling the villager finishes it and pays 25 gold, and the journal
## lists it under Completed. The pause menu has a Journal button. The state is put back afterwards.
func _quest_journal() -> String:
	var state: RpgGameState = _autoload("GameState") as RpgGameState
	if state == null or not state.quest_defs.has(&"errand"):
		return "the demo quest game/data/quests/errand.tres was not seeded"
	var failure := ""
	var quests_before: Dictionary = state.quests.duplicate(true)
	var flags_before: Dictionary = state.flags.duplicate(true)
	var gold: int = state.gold
	if state.quest_state(&"errand") != "return":
		failure = "after the talk and the chest the quest is at '%s', expected 'return' (flags %s)" % [state.quest_state(&"errand"), str(state.flags)]
	var pause := (load(RpgMenuUtil.scene_path("pause_menu")) as PackedScene).instantiate() as Control
	if failure == "" and pause.get_node_or_null("%Journal") == null:
		failure = "the pause menu has no Journal button"
	pause.free()
	var menu := (load(RpgMenuUtil.scene_path("journal_menu")) as PackedScene).instantiate() as RpgJournalMenu
	_tree().root.add_child(menu)
	await _frames(2)
	if failure == "" and menu.rows().size() != 1:
		failure = "the journal lists %d active quests, expected 1" % menu.rows().size()
	if failure == "":
		RpgDialogueRunner.execute_event("set_flag:starter_npc.reported=true")
		await _frames(2)
		if not state.quest_is_done(&"errand"):
			failure = "telling the villager did not finish the quest (%s)" % state.quest_state(&"errand")
		elif state.gold != gold + 25:
			failure = "the reward was not paid: gold %d, expected %d" % [state.gold, gold + 25]
	if failure == "":
		menu.set_tab(RpgJournalMenu.FINISHED)
		await _frames(2)
		if menu.rows().size() != 1 or menu.quest_of(menu.rows()[0]) != &"errand":
			failure = "the Completed tab does not list the quest"
	menu.queue_free()
	state.quests = quests_before
	state.flags = flags_before
	state.gold = gold
	return failure

## A character joins through the dialogue event (the seeded companion of a turn-based demo, else a
## stand-in), the status menu pages to them, the save data lists them, and the event takes them out
## again. The party is put back afterwards.
func _party_members() -> String:
	var state: RpgGameState = _autoload("GameState") as RpgGameState
	if state == null:
		return "GameState is missing"
	var ally: StringName = &"companion"
	var stand_in := state.actor_definition(ally) == null
	if stand_in:  # an action RPG, or a demo without the villager: a made-up ally
		ally = &"smoke_ally"
		var def := RpgActorDefinition.new()
		def.id = ally
		def.display_name = "Ally"
		def.base_stats = RpgStats.new()
		state.actor_defs[ally] = def
	var party_before: Array[Dictionary] = state.party.duplicate()
	state.party.clear()
	var failure := ""
	RpgDialogueRunner.execute_event("join_party:%s" % ally)
	if not state.in_party(ally):
		failure = "join_party:%s did not add the character" % ally
	var menu := (load(RpgMenuUtil.scene_path("status_menu")) as PackedScene).instantiate() as RpgStatusMenu
	_tree().root.add_child(menu)
	await _frames(2)
	if failure == "" and menu.find_child("Member", true, false) == null:
		failure = "the status menu has no member button with two characters"
	if failure == "":
		menu.page(1)
		await _frames(2)
		if menu.shown_actor() != ally:
			failure = "the status menu shows %s after paging, expected %s" % [menu.shown_actor(), ally]
	menu.queue_free()
	if failure == "":
		var saved: Array = RpgUtil.to_array(state.to_dict().get("party"))
		if saved.size() != 1 or str(RpgUtil.to_dict(saved[0]).get("actor_id", "")) != String(ally):
			failure = "the save data lists %s as the party" % str(saved)
	if failure == "":
		RpgDialogueRunner.execute_event("leave_party:%s" % ally)
		if state.in_party(ally):
			failure = "leave_party:%s did not remove the character" % ally
	state.party.assign(party_before)
	state.actor_defs.erase(&"smoke_ally")
	return failure

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
