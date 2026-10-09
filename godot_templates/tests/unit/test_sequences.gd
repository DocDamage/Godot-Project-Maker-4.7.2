extends RefCounted
## Event sequencer (T12.54): every command, the flow commands (labels, if, call, end), background
## moves and wait_for, skipping, the guards that hold the game during a cutscene, triggers and
## variables. The runner is driven with tick(), one physics frame (1/60 s) at a time.

const Fixtures := preload("../lib/fixtures.gd")

const DT := 1.0 / 60.0
const TMP_DIR := "user://test_sequences"

class FakeRouter extends RpgSceneRouter:
	var visits: Array = []
	func go_to(map_path: String, spawn_id: StringName = &"default") -> void:
		visits.append([map_path, spawn_id])

class FakeBox extends Node:
	var opened: Array = []
	var _open := false
	var _runner := RpgDialogueRunner.new()
	func open(res: RpgDialogueResource, _actor: Node = null) -> void:
		opened.append(res)
		_runner.start(res)
		_open = true
	func is_open() -> bool:
		return _open
	func close() -> void:
		_open = false
	func fast_forward() -> void:
		_runner.fast_forward()
		_open = false

class FakeAudio extends Node:
	var played: Array = []
	func play(slot: StringName, _volume_db: float = 0.0, _pitch: float = 1.0) -> void:
		played.append(slot)

class FakeCombat extends RpgCombatMode:
	var started: Array = []
	var fighting := false
	func start_encounter(data: RpgEncounterData) -> void:
		started.append(data)
		fighting = true
	func is_in_combat() -> bool:
		return fighting
	func end_battle(outcome: RpgEncounterResult.Outcome) -> void:
		fighting = false
		var result := RpgEncounterResult.new()
		result.outcome = outcome
		encounter_finished.emit(result)

# ---------------------------------------------------------------- fixtures

## GameState, Events, a router with a fake audio and the runner under it, a map with the player
## (with a camera) and an NPC on a 16 px grid. Returns {state, router, runner, map, player, npc, box}.
func _world() -> Dictionary:
	var state := Fixtures.install_state({&"potion": Fixtures.item(&"potion")})
	state.new_game()
	var root := Fixtures.tree().root
	var old := root.get_node_or_null("SceneRouter")
	if old != null:
		root.remove_child(old)
		old.free()
	var router := FakeRouter.new()
	router.name = "SceneRouter"
	root.add_child(router)
	if not router.is_node_ready():  # add_child readies it once the tree runs
		router._ready()
	var audio := FakeAudio.new()
	router.add_child(audio)
	router.audio = audio
	var runner := RpgSequenceRunner.new()
	runner.name = RpgSequenceRunner.NODE_NAME
	router.add_child(runner)
	var map := Node2D.new()
	map.name = "Map"
	var player := RpgActor.new()
	player.name = "Player"
	player.add_to_group("player")
	var camera := Camera2D.new()
	camera.name = "Camera"
	player.add_child(camera)
	map.add_child(player)
	var npc := RpgNpc.new()
	npc.name = "Npc"
	npc.entity_id = "town_npc_001"
	npc.position = Vector2(64, 32)
	map.add_child(npc)
	runner.map_override = map
	var box := FakeBox.new()
	runner.box_override = box
	return {"state": state, "router": router, "runner": runner, "map": map, "player": player, "npc": npc, "box": box}

func _teardown(w: Dictionary) -> void:
	(w["map"] as Node).free()
	(w["box"] as Node).free()
	Fixtures.uninstall("SceneRouter")
	Fixtures.uninstall_state()

func _seq(commands: Array, skippable: bool = false, id: StringName = &"test") -> RpgSequence:
	var s := RpgSequence.new()
	s.id = id
	s.skippable = skippable
	var typed: Array[Dictionary] = []
	for c: Dictionary in commands:
		typed.append(c)
	s.commands = typed
	return s

## Ticks until the runner is idle; returns the number of frames (or -1 after `limit`).
func _run_out(runner: RpgSequenceRunner, limit: int = 2000) -> int:
	for i in limit:
		if not runner.is_running() and runner.queued() == 0:
			return i
		runner.tick(DT)
	return -1

func _ticks(runner: RpgSequenceRunner, n: int) -> void:
	for i in n:
		runner.tick(DT)

func _save_tmp(res: Resource, file_name: String) -> String:
	DirAccess.make_dir_recursive_absolute(TMP_DIR)
	var path := TMP_DIR + "/" + file_name
	ResourceSaver.save(res, path)
	return path

# ---------------------------------------------------------------- the resource

func test_problems_name_unknown_commands_missing_arguments_and_labels(t) -> void:
	var s := _seq([
		{"cmd": "dance"},
		{"cmd": "move_actor", "entity": "player"},
		{"cmd": "goto", "label": "nowhere"},
		{"cmd": "if", "condition": "flag:a.b", "goto": "here", "else": "missing"},
		{"cmd": "label", "name": "here"},
		{"cmd": "face", "entity": "player", "dir": "north"},
		{"cmd": "show_dialogue"},
		{"cmd": "move_actor", "entity": "player", "tiles": [1]},
	])
	var found := s.problems()
	t.eq(found.size(), 7, str(found))
	t.ok(found[0].contains("not a known command"))
	t.ok(found[1].contains("needs 'tiles'"))
	t.ok(found[2].contains("unknown label 'nowhere'"))
	t.ok(found[3].contains("unknown label 'missing'"))
	t.ok(found[4].contains("direction 'north'"))
	t.ok(found[5].contains("'dialogue' or 'lines'"))
	t.ok(found[6].contains("[dx, dy]"))
	t.eq(_seq([{"cmd": "wait", "seconds": 1}, {"cmd": "end"}]).problems().size(), 0)

# ---------------------------------------------------------------- one test per command

func test_move_actor_walks_x_then_y_at_its_speed(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var npc: RpgNpc = w["npc"]
	runner.run(_seq([{"cmd": "move_actor", "entity": "town_npc_001", "tiles": [2, -1], "speed": 4}]))
	runner.tick(DT)
	t.ok(npc.scripted_walk, "the walk animation plays while it is moved")
	t.eq(npc.facing, "right")
	var frames := _run_out(runner)
	t.eq(npc.position, Vector2(96, 16), "two tiles right, then one up")
	t.eq(npc.facing, "up", "it faces the way it last walked")
	t.ok(not npc.scripted_walk)
	t.ok(frames >= 43 and frames <= 46, "48 px at 64 px/s is 45 frames, got %d" % frames)
	_teardown(w)

func test_face_turns_to_a_direction_or_toward_someone(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var npc: RpgNpc = w["npc"]
	runner.run(_seq([{"cmd": "face", "entity": "town_npc_001", "dir": "left"}]))
	_run_out(runner)
	t.eq(npc.facing, "left")
	runner.run(_seq([{"cmd": "face", "entity": "player", "toward": "town_npc_001"}]))
	_run_out(runner)
	t.eq((w["player"] as RpgActor).facing, "right", "the NPC stands to the right of the player")
	_teardown(w)

func test_wait_takes_its_time(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	runner.run(_seq([{"cmd": "wait", "seconds": 0.5}, {"cmd": "set_flag", "entity": "x", "key": "after", "value": true}]))
	_ticks(runner, 29)
	t.ok(runner.is_running() and not (w["state"] as RpgGameState).get_flag("x", "after", false), "still waiting after 29 frames")
	_ticks(runner, 1)
	t.ok(not runner.is_running(), "done on frame 30")
	t.eq((w["state"] as RpgGameState).get_flag("x", "after"), true)
	_teardown(w)

func test_fade_out_and_in(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var router: RpgSceneRouter = w["router"]
	runner.run(_seq([{"cmd": "fade_out", "seconds": 0.5}, {"cmd": "wait", "seconds": 0.1}, {"cmd": "fade_in", "seconds": 0.5}]))
	_ticks(runner, 15)
	t.near(router.fade_alpha(), 0.5, 0.02)
	_ticks(runner, 15)
	t.near(router.fade_alpha(), 1.0)
	_run_out(runner)
	t.near(router.fade_alpha(), 0.0)
	runner.run(_seq([{"cmd": "fade_out", "seconds": 0.1}]))
	_run_out(runner)
	t.near(router.fade_alpha(), 0.0)
	_teardown(w)

func test_a_sequence_that_ends_black_is_faded_back(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	runner.run(_seq([{"cmd": "fade_out", "seconds": 0.1}]))
	_run_out(runner)
	t.near((w["router"] as RpgSceneRouter).fade_alpha(), 0.0)
	_teardown(w)

func test_shake_moves_the_camera_and_settles(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var camera := (w["player"] as Node).get_node("Camera") as Camera2D
	runner.run(_seq([{"cmd": "shake", "seconds": 0.5, "strength": 4}]))
	_ticks(runner, 5)
	t.ok(camera.offset != Vector2.ZERO, "the camera is off centre while it shakes")
	t.ok(camera.offset.length() <= 4.0 * 1.5)
	_run_out(runner)
	t.eq(camera.offset, Vector2.ZERO)
	_teardown(w)

func test_play_sound_uses_the_slot(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	runner.run(_seq([{"cmd": "play_sound", "slot": "sfx_chest"}]))
	_run_out(runner)
	t.eq((w["router"].audio as FakeAudio).played, [&"sfx_chest"])
	_teardown(w)

func test_show_dialogue_waits_for_the_box(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var box: FakeBox = w["box"]
	runner.run(_seq([{"cmd": "show_dialogue", "lines": ["Hello.", "Bye."], "speaker": "Mira"}, {"cmd": "set_flag", "entity": "x", "key": "done"}]))
	_ticks(runner, 10)
	t.eq(box.opened.size(), 1)
	var res: RpgDialogueResource = box.opened[0]
	t.eq(res.lines.size(), 2)
	t.eq(res.lines[0].speaker, "Mira")
	t.ok(runner.is_running(), "the sequence waits while the box is open")
	box.close()
	_run_out(runner)
	t.eq((w["state"] as RpgGameState).get_flag("x", "done"), true)
	_teardown(w)

func test_show_dialogue_loads_a_file(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var res := RpgDialogueResource.new()
	var line := RpgDialogueLine.new()
	line.text = "From a file."
	res.lines.append(line)
	var path := _save_tmp(res, "talk.tres")
	runner.run(_seq([{"cmd": "show_dialogue", "dialogue": path}]))
	runner.tick(DT)
	var box: FakeBox = w["box"]
	t.eq(box.opened.size(), 1)
	t.eq((box.opened[0] as RpgDialogueResource).lines[0].text, "From a file.")
	box.close()
	_run_out(runner)
	_teardown(w)

func test_items_flags_variables_and_events(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var state: RpgGameState = w["state"]
	var gold_before := state.gold
	runner.run(_seq([
		{"cmd": "give_item", "item": "potion", "qty": 3},
		{"cmd": "take_item", "item": "potion"},
		{"cmd": "set_flag", "entity": "bridge", "key": "built", "value": 2},
		{"cmd": "set_var", "name": "planks", "value": 5},
		{"cmd": "add_var", "name": "planks", "amount": -2},
		{"cmd": "event", "event": "give_gold:7"},
	]))
	_run_out(runner)
	t.eq(state.inventory.count(&"potion"), 2)
	t.eq(state.get_flag("bridge", "built"), 2)
	t.eq(state.get_var("planks"), 3)
	t.eq(state.gold, gold_before + 7)
	_teardown(w)

func test_start_battle_waits_for_the_result(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var combat := FakeCombat.new()
	(w["router"] as RpgSceneRouter).combat = combat
	var enemy := RpgEnemyDefinition.new()
	enemy.id = &"boss"
	var path := _save_tmp(enemy, "boss.tres")
	runner.run(_seq([{"cmd": "start_battle", "enemies": [path, path], "can_escape": false}, {"cmd": "set_flag", "entity": "x", "key": "after"}]))
	_ticks(runner, 3)
	t.eq(combat.started.size(), 1)
	var data: RpgEncounterData = combat.started[0]
	t.eq(data.enemies.size(), 2)
	t.ok(not data.can_escape)
	t.ok(not runner.can_skip(), "a battle is never skipped")
	combat.end_battle(RpgEncounterResult.Outcome.VICTORY)
	_run_out(runner)
	t.eq((w["state"] as RpgGameState).get_flag("x", "after"), true, "it carries on after a victory")
	runner.run(_seq([{"cmd": "start_battle", "enemies": [path]}, {"cmd": "set_flag", "entity": "x", "key": "lost"}]))
	_ticks(runner, 3)
	combat.end_battle(RpgEncounterResult.Outcome.DEFEAT)
	_run_out(runner)
	t.eq((w["state"] as RpgGameState).get_flag("x", "lost", false), false, "a defeat ends the sequence")
	combat.free()
	_teardown(w)

func test_change_map_goes_through_the_router(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var router: FakeRouter = w["router"]
	runner.run(_seq([{"cmd": "change_map", "map": "res://game/maps/field_1.tscn", "spawn": "west_entry"}]))
	_run_out(runner)
	t.eq(router.visits, [["res://game/maps/field_1.tscn", &"west_entry"]])
	_teardown(w)

func test_camera_pan_and_back(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var camera := (w["player"] as Node).get_node("Camera") as Camera2D
	runner.run(_seq([{"cmd": "camera_pan", "tiles": [4, 0], "seconds": 0.5}, {"cmd": "wait", "seconds": 1.0}]))
	_ticks(runner, 15)
	t.near(camera.offset.x, 32.0, 1.5)
	_ticks(runner, 20)
	t.eq(camera.offset, Vector2(64, 0))
	runner.tick(DT)
	_run_out(runner)
	t.eq(camera.offset, Vector2.ZERO, "the camera returns when the sequence ends")
	runner.run(_seq([{"cmd": "camera_pan", "entity": "town_npc_001", "seconds": 0.0}, {"cmd": "wait", "seconds": 0.1}]))
	_ticks(runner, 2)
	t.eq(camera.offset, Vector2(64, 32), "centred on the NPC")
	_run_out(runner)
	_teardown(w)

func test_camera_lock_keeps_the_camera_until_unlocked(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var camera := (w["player"] as Node).get_node("Camera") as Camera2D
	runner.run(_seq([{"cmd": "camera_lock"}, {"cmd": "wait", "seconds": 0.1}, {"cmd": "camera_unlock"}, {"cmd": "camera_lock"}]))
	runner.tick(DT)
	t.ok(camera.top_level, "locked: the camera no longer follows its parent")
	_run_out(runner)
	t.ok(not camera.top_level, "unlocked at the end")
	t.eq(camera.position, Vector2.ZERO)
	_teardown(w)

func test_animate_holds_an_animation_until_released(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var npc: RpgNpc = w["npc"]
	var sprite := AnimatedSprite2D.new()
	sprite.name = "Visual"
	var frames := SpriteFrames.new()
	frames.add_animation("idle_down")
	frames.add_frame("idle_down", PlaceholderTexture2D.new())
	frames.add_animation("attack_down")
	frames.add_frame("attack_down", PlaceholderTexture2D.new())
	sprite.sprite_frames = frames
	npc.add_child(sprite)
	npc._ready()
	runner.run(_seq([{"cmd": "animate", "entity": "town_npc_001", "animation": "attack", "seconds": 0.25}, {"cmd": "wait", "seconds": 0.5}]))
	runner.tick(DT)
	t.ok(npc.animation_locked)
	t.eq(String(sprite.animation), "attack_down")
	_ticks(runner, 15)
	t.ok(not npc.animation_locked, "released after its seconds")
	runner.run(_seq([{"cmd": "animate", "entity": "town_npc_001", "animation": "attack"}]))
	_run_out(runner)
	t.ok(not npc.animation_locked, "released when the sequence ends")
	runner.run(_seq([{"cmd": "animate", "entity": "town_npc_001", "animation": "dance"}]))
	_run_out(runner)
	t.ok(not npc.animation_locked, "a missing animation is skipped")
	_teardown(w)

# ---------------------------------------------------------------- flow

func test_labels_goto_and_if_else(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var state: RpgGameState = w["state"]
	state.set_var("count", 0)
	runner.run(_seq([
		{"cmd": "label", "name": "loop"},
		{"cmd": "add_var", "name": "count", "amount": 1},
		{"cmd": "if", "condition": "var:count<3", "goto": "loop"},
		{"cmd": "if", "condition": "flag:door.open", "goto": "open", "else": "shut"},
		{"cmd": "label", "name": "open"},
		{"cmd": "set_flag", "entity": "x", "key": "went", "value": "open"},
		{"cmd": "goto", "label": "out"},
		{"cmd": "label", "name": "shut"},
		{"cmd": "set_flag", "entity": "x", "key": "went", "value": "shut"},
		{"cmd": "label", "name": "out"},
	]))
	_run_out(runner)
	t.eq(state.get_var("count"), 3)
	t.eq(state.get_flag("x", "went"), "shut")
	_teardown(w)

func test_call_runs_another_sequence_and_comes_back(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var state: RpgGameState = w["state"]
	var inner := _seq([{"cmd": "add_var", "name": "order", "amount": 10}, {"cmd": "end"}, {"cmd": "add_var", "name": "order", "amount": 1000}], false, &"inner")
	var path := _save_tmp(inner, "inner.tres")
	runner.run(_seq([{"cmd": "add_var", "name": "order", "amount": 1}, {"cmd": "call", "sequence": path}, {"cmd": "add_var", "name": "order", "amount": 100}]))
	_run_out(runner)
	t.eq(state.get_var("order"), 111, "end returns from the called sequence; the caller carries on")
	_teardown(w)

func test_a_loop_that_never_waits_is_stopped(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	runner.run(_seq([{"cmd": "label", "name": "a"}, {"cmd": "goto", "label": "a"}]))
	runner.tick(DT)
	t.ok(not runner.is_running(), "stopped after %d commands" % RpgSequenceRunner.MAX_INSTANT)
	_teardown(w)

func test_moves_in_the_background_and_wait_for(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var npc: RpgNpc = w["npc"]
	var player: RpgActor = w["player"]
	runner.run(_seq([
		{"cmd": "move_actor", "entity": "town_npc_001", "tiles": [4, 0], "speed": 4, "wait": false},
		{"cmd": "move_actor", "entity": "player", "tiles": [0, 2], "speed": 4, "wait": false},
		{"cmd": "wait_for", "entity": "player"},
		{"cmd": "set_flag", "entity": "x", "key": "player_there"},
		{"cmd": "wait_for"},
	]))
	_ticks(runner, 10)
	t.ok(npc.position.x > 64.0 and player.position.y > 0.0, "both walk at the same time")
	_ticks(runner, 22)
	t.eq(player.position, Vector2(0, 32))
	t.eq((w["state"] as RpgGameState).get_flag("x", "player_there"), true, "wait_for the player ends when the player arrives")
	t.ok(runner.is_running(), "the NPC (64 px) is still walking")
	_run_out(runner)
	t.eq(npc.position, Vector2(128, 32))
	_teardown(w)

func test_the_same_sequence_plays_the_same_way(t) -> void:
	var results: Array = []
	for attempt in 2:
		var w := _world()
		var runner: RpgSequenceRunner = w["runner"]
		runner.run(_seq([
			{"cmd": "move_actor", "entity": "town_npc_001", "tiles": [3, 2], "wait": false},
			{"cmd": "wait", "seconds": 0.3},
			{"cmd": "move_actor", "entity": "player", "tiles": [-1, 0], "speed": 2.5},
			{"cmd": "wait_for"},
		]))
		var frames := _run_out(runner)
		results.append([frames, (w["npc"] as Node2D).position, (w["player"] as Node2D).position])
		_teardown(w)
	t.eq(results[0], results[1])

func test_a_second_sequence_waits_its_turn(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var state: RpgGameState = w["state"]
	runner.run(_seq([{"cmd": "wait", "seconds": 0.2}, {"cmd": "set_var", "name": "n", "value": 1}], false, &"first"))
	runner.run(_seq([{"cmd": "set_var", "name": "n", "value": 2}], false, &"second"))
	t.eq(runner.current_id(), &"first")
	t.eq(runner.queued(), 1)
	_run_out(runner)
	t.eq(state.get_var("n"), 2, "the second one ran after the first")
	_teardown(w)

# ---------------------------------------------------------------- skipping and holding the game

func test_skip_plays_the_rest_at_once(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var npc: RpgNpc = w["npc"]
	var box: FakeBox = w["box"]
	var choice_a := RpgDialogueChoice.new()
	choice_a.text = "A"
	choice_a.next = &"a"
	var choice_b := RpgDialogueChoice.new()
	choice_b.text = "B"
	choice_b.next = &"b"
	var res := RpgDialogueResource.new()
	var ask := RpgDialogueLine.new()
	ask.text = "Which?"
	ask.choices.assign([choice_a, choice_b])
	var line_a := RpgDialogueLine.new()
	line_a.id = &"a"
	line_a.events = PackedStringArray(["set_flag:x.picked=a"])
	line_a.next = &"done"
	var line_b := RpgDialogueLine.new()
	line_b.id = &"b"
	line_b.events = PackedStringArray(["set_flag:x.picked=b"])
	line_b.next = &"done"
	var done := RpgDialogueLine.new()
	done.id = &"done"
	done.text = "Bye."
	res.lines.assign([ask, line_a, line_b, done])
	var path := _save_tmp(res, "ask.tres")
	var s := _seq([
		{"cmd": "fade_out", "seconds": 1.0},
		{"cmd": "move_actor", "entity": "town_npc_001", "tiles": [5, 0], "speed": 1},
		{"cmd": "show_dialogue", "dialogue": path},
		{"cmd": "give_item", "item": "potion"},
		{"cmd": "wait", "seconds": 30},
	], true)
	runner.run(s)
	_ticks(runner, 3)
	t.ok(runner.can_skip())
	t.ok(runner.skip())
	runner.tick(DT)
	t.ok(not runner.is_running(), "everything after the skip ran in one frame")
	t.eq(npc.position, Vector2(144, 32), "the NPC is where the walk would have taken it")
	t.eq((w["state"] as RpgGameState).get_flag("x", "picked"), "a", "the dialogue ran with its first choice")
	t.eq((w["state"] as RpgGameState).inventory.count(&"potion"), 1)
	t.eq(box.opened.size(), 0, "a skipped dialogue is not shown")
	t.near((w["router"] as RpgSceneRouter).fade_alpha(), 0.0)
	runner.run(_seq([{"cmd": "wait", "seconds": 1}]))
	t.ok(not runner.skip(), "a sequence that is not skippable plays out")
	_teardown(w)

func test_running_holds_autosave_and_reports_itself(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var router: RpgSceneRouter = w["router"]
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER)
	save.dir = "user://test_sequences_saves"
	var map := RpgMapRoot.new()
	router.current_map = map
	save.reset_autosave_cooldown()
	t.ok(save.can_autosave(), "a settled map may be autosaved")
	t.ok(not RpgSequenceRunner.running())
	runner.run(_seq([{"cmd": "wait", "seconds": 1}]))
	t.ok(RpgSequenceRunner.running())
	t.ok(not save.can_autosave(), "no autosave while a sequence runs")
	_run_out(runner)
	t.ok(save.can_autosave())
	router.current_map = null
	map.free()
	Fixtures.uninstall("SaveManager")
	_teardown(w)

func test_the_dialogue_event_requests_a_sequence(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	if not runner.is_node_ready():  # add_child readies it once the tree runs
		runner._ready()
	var path := _save_tmp(_seq([{"cmd": "set_var", "name": "asked", "value": 1}], false, &"asked"), "asked.tres")
	t.ok(RpgDialogueRunner.execute_event("run_sequence:" + path))
	t.eq(runner.current_id(), &"asked")
	_run_out(runner)
	t.eq((w["state"] as RpgGameState).get_var("asked"), 1)
	t.ok(not RpgDialogueRunner.execute_event("run_sequence:"), "an event without an id is malformed")
	_teardown(w)

# ---------------------------------------------------------------- triggers

func test_a_trigger_fires_once_and_respects_its_condition(t) -> void:
	var w := _world()
	var runner: RpgSequenceRunner = w["runner"]
	var state: RpgGameState = w["state"]
	var path := _save_tmp(_seq([{"cmd": "add_var", "name": "fired", "amount": 1}], false, &"intro"), "intro.tres")
	var trigger := RpgTriggerArea.new()
	trigger.sequence_id = StringName(path)
	trigger.entity_id = "town_trigger_001"
	trigger.condition = "var:allowed>=1"
	t.ok(not trigger.fire(), "the condition does not hold yet")
	state.set_var("allowed", 1)
	t.ok(trigger.fire())
	_run_out(runner)
	t.eq(state.get_var("fired"), 1)
	t.eq(state.get_flag("town_trigger_001", "triggered"), true)
	t.ok(not trigger.fire(), "once: it does not fire again")
	trigger.once = false
	t.ok(trigger.fire())
	_run_out(runner)
	t.eq(state.get_var("fired"), 2)
	trigger.free()
	_teardown(w)

# ---------------------------------------------------------------- variables

func test_variable_conditions_events_and_saves(t) -> void:
	var state := Fixtures.install_state()
	state.new_game()
	t.ok(RpgCondition.evaluate("var:keys==0"), "a variable never set is 0")
	t.ok(RpgDialogueRunner.execute_event("set_var:keys=2"))
	t.ok(RpgDialogueRunner.execute_event("add_var:keys:3"))
	t.ok(RpgDialogueRunner.execute_event("add_var:keys:-1"))
	t.eq(state.get_var("keys"), 4)
	for expr: String in ["var:keys>=4", "var:keys<=4", "var:keys==4", "var:keys!=5", "var:keys>3", "var:keys<5"]:
		t.ok(RpgCondition.evaluate(expr), expr)
	for expr: String in ["var:keys>4", "var:keys<4", "var:keys!=4"]:
		t.ok(not RpgCondition.evaluate(expr), expr)
	t.ok(not RpgDialogueRunner.execute_event("set_var:keys=lots"))
	t.ok(not RpgDialogueRunner.execute_event("add_var:keys"))
	var saved: Dictionary = state.to_dict()
	state.new_game()
	t.eq(state.get_var("keys"), 0, "a new game starts from zero")
	state.from_dict(JSON.parse_string(JSON.stringify(saved)))
	t.eq(state.get_var("keys"), 4, "variables survive a save")
	saved.erase("variables")
	state.from_dict(saved)
	t.eq(state.variables, {}, "an older save without the key loads with none")
	Fixtures.uninstall_state()

func test_dialogue_fast_forward_runs_events_and_takes_the_first_choice(t) -> void:
	var state := Fixtures.install_state()
	var res := RpgDialogueResource.new()
	var first := RpgDialogueLine.new()
	first.events = PackedStringArray(["set_var:seen=1"])
	var choice := RpgDialogueChoice.new()
	choice.text = "Go"
	choice.next = &"end"
	first.choices.assign([choice])
	var end := RpgDialogueLine.new()
	end.id = &"end"
	end.events = PackedStringArray(["add_var:seen:1"])
	res.lines.assign([first, end])
	var runner := RpgDialogueRunner.new()
	runner.start(res)
	runner.fast_forward()
	t.ok(runner.is_finished())
	t.eq(state.get_var("seen"), 2)
	Fixtures.uninstall_state()
