class_name RpgSequenceRunner
extends Node
## Plays RpgSequence commands (the list is in sequence.gd). Boot creates one under SceneRouter as
## "SequenceRunner"; RpgSequenceRunner.instance() finds it. It is driven by tick(delta) from
## _physics_process, so it advances in fixed steps and a sequence plays the same way every time.
##
## While a sequence runs, the player's input, the pause menu, autosave, random encounters and enemies
## are held (they ask RpgSequenceRunner.running()). Characters are walked by setting their position,
## so walls do not stop them. A sequence that leaves the screen black, the camera panned or locked,
## or a character holding an animation is put back to normal when it ends.

signal started(sequence_id: StringName)
signal finished(sequence_id: StringName, skipped: bool)

const NODE_NAME := "SequenceRunner"
const MAX_CALL_DEPTH := 8
## More commands than this in one physics frame means a loop that never waits: the sequence stops.
const MAX_INSTANT := 1000
const DEFAULT_SPEED_TILES := 4.0
const DEFAULT_FADE_S := 0.3
const DEFAULT_PAN_S := 0.5
const DEFAULT_SHAKE_S := 0.4
const DEFAULT_SHAKE_PX := 3.0
## Timed steps end within this much of their length, so that a sum of 1/60 s steps that comes out
## a hair short of 0.5 does not cost a frame.
const EPSILON := 0.000001

## Stand-ins for tests: the map whose characters are used (default SceneRouter.current_map) and the
## dialogue box (default the node of the group "rpg_dialogue_box").
var map_override: Node = null
var box_override: Node = null

var _queue: Array[RpgSequence] = []
var _pending: Array[RpgSequence] = []  # requested while a dialogue was open
var _frames: Array[Dictionary] = []  # [{sequence: RpgSequence, pc: int}], the called one last
var _task: Dictionary = {}  # what the current command waits for
var _background: Array[Dictionary] = []  # moves, fades, pans and shakes started with wait: false
var _skipping := false
var _id: StringName = &""
var _held: Array[Node] = []  # actors walked by script or holding an animation
var _pan := Vector2.ZERO
var _shake := Vector2.ZERO
var _camera_locked := false
var _camera_used := false  # pan, shake or lock happened: the camera is put back at the end
var _faded := false

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_PAUSABLE  # a menu or shop opened by a sequence holds it
	var bus := RpgUtil.events()
	if bus != null:
		bus.sequence_requested.connect(_on_requested)
		bus.dialogue_finished.connect(_on_dialogue_finished)

## The runner of the running game, or null.
static func instance() -> RpgSequenceRunner:
	var router := RpgUtil.router()
	return router.get_node_or_null(NODE_NAME) as RpgSequenceRunner if router != null else null

## True while a sequence plays. Everything that must hold still during a cutscene asks this.
static func running() -> bool:
	var runner := instance()
	return runner != null and runner.is_running()

func is_running() -> bool:
	return not _frames.is_empty()

func current_id() -> StringName:
	return _id

func queued() -> int:
	return _queue.size()

## Starts the sequence, or queues it behind the one that is running. False for null.
func run(sequence: RpgSequence) -> bool:
	if sequence == null:
		return false
	if is_running():
		_queue.append(sequence)
	else:
		_begin(sequence)
	return true

## run() for game/data/sequences/<id>.tres. False when there is no such file.
func run_id(sequence_id: StringName) -> bool:
	var sequence := RpgSequence.load_sequence(sequence_id)
	if sequence == null:
		push_error("[RPG-SEQ] no sequence '%s' in %s" % [sequence_id, RpgSequence.SEQUENCES_DIR])
		return false
	return run(sequence)

func can_skip() -> bool:
	if not is_running() or _skipping:
		return false
	var outer: RpgSequence = _frames[0]["sequence"]
	return outer.skippable and _task.get("kind", "") != "battle"

## Plays the rest at once (see RpgSequence.skippable). False when it cannot be skipped.
func skip() -> bool:
	if not can_skip():
		return false
	_skipping = true
	for task in _background:
		_advance(task, 0.0)
	_background.clear()
	return true

func _unhandled_input(event: InputEvent) -> void:
	if not can_skip() or not InputMap.has_action("cancel") or not event.is_action_pressed("cancel"):
		return
	get_viewport().set_input_as_handled()
	skip()

func _physics_process(delta: float) -> void:
	tick(delta)

## Advances the running sequence by `delta` seconds: the background tasks first, then the current
## command and every following command that takes no time.
func tick(delta: float) -> void:
	if _frames.is_empty():
		if _queue.is_empty():
			return
		var next: RpgSequence = _queue.pop_front()
		_begin(next)
	for task: Dictionary in _background.duplicate():
		if _advance(task, delta):
			_background.erase(task)
	var budget := delta
	var executed := 0
	while not _frames.is_empty():
		if not _task.is_empty():
			if not _advance(_task, budget):
				return
			budget = 0.0
			_task = {}
			continue
		var command := _next_command()
		if command.is_empty():
			break
		executed += 1
		if executed > MAX_INSTANT:
			push_error("[RPG-SEQ] sequence '%s' ran %d commands without waiting; stopped" % [_id, MAX_INSTANT])
			_frames.clear()
			break
		_execute(command)
	_finish()

func _begin(sequence: RpgSequence) -> void:
	_frames = [{"sequence": sequence, "pc": 0}]
	_id = sequence.id
	_skipping = false
	started.emit(_id)
	RpgUtil.emit(&"sequence_started", [_id])

func _next_command() -> Dictionary:
	while not _frames.is_empty():
		var frame: Dictionary = _frames.back()
		var sequence: RpgSequence = frame["sequence"]
		var pc: int = frame["pc"]
		if pc < sequence.commands.size():
			frame["pc"] = pc + 1
			return sequence.commands[pc]
		_frames.pop_back()
	return {}

## Puts everything back once the last command is done (or the sequence was stopped).
func _finish() -> void:
	_complete_background()
	_task = {}
	for node in _held:
		_release(node)
	_held.clear()
	if _camera_used:
		_pan = Vector2.ZERO
		_shake = Vector2.ZERO
		_apply_camera()
		_unlock_camera()
		_camera_used = false
	var router := RpgUtil.router()
	if _faded and router != null:
		router.set_fade_alpha(0.0)
	_faded = false
	var done_id := _id
	var was_skipped := _skipping
	_id = &""
	_skipping = false
	finished.emit(done_id, was_skipped)
	RpgUtil.emit(&"sequence_finished", [done_id])

# ---------------------------------------------------------------- commands

func _execute(command: Dictionary) -> void:
	var name := str(command.get("cmd", ""))
	match name:
		"move_actor":
			_cmd_move(command)
		"face":
			_cmd_face(command)
		"animate":
			_cmd_animate(command)
		"wait":
			_task = {"kind": "wait", "left": RpgUtil.to_float(command.get("seconds", 0.0))}
		"fade_out", "fade_in":
			_cmd_fade(command, 1.0 if name == "fade_out" else 0.0)
		"shake":
			_camera_used = true
			_start({"kind": "shake", "t": 0.0, "seconds": RpgUtil.to_float(command.get("seconds", DEFAULT_SHAKE_S)), "strength": RpgUtil.to_float(command.get("strength", DEFAULT_SHAKE_PX))}, command)
		"camera_pan":
			_cmd_pan(command)
		"camera_lock":
			_lock_camera()
		"camera_unlock":
			_unlock_camera()
		"play_sound":
			_cmd_sound(command)
		"show_dialogue":
			_cmd_dialogue(command)
		"give_item", "take_item":
			RpgDialogueRunner.execute_event("%s:%s:%d" % [name, str(command.get("item", "")), RpgUtil.to_int(command.get("qty", 1))])
		"set_flag":
			var state := RpgUtil.state()
			if state != null:
				state.set_flag(str(command.get("entity", "")), str(command.get("key", "")), command.get("value", true))
		"set_var":
			var state := RpgUtil.state()
			if state != null:
				state.set_var(str(command.get("name", "")), RpgUtil.to_int(command.get("value", 0)))
		"add_var":
			var state := RpgUtil.state()
			if state != null:
				state.add_var(str(command.get("name", "")), RpgUtil.to_int(command.get("amount", 1)))
		"event":
			RpgDialogueRunner.execute_event(str(command.get("event", "")))
		"start_battle":
			_cmd_battle(command)
		"change_map":
			_task = {"kind": "map", "map": str(command.get("map", "")), "spawn": StringName(str(command.get("spawn", "default"))), "requested": false}
		"label":
			pass
		"goto":
			_jump(str(command.get("label", "")))
		"if":
			if RpgCondition.evaluate(str(command.get("condition", ""))):
				_jump(str(command.get("goto", "")))
			elif str(command.get("else", "")) != "":
				_jump(str(command.get("else", "")))
		"call":
			_cmd_call(command)
		"wait_for":
			_task = {"kind": "wait_for", "entity": str(command.get("entity", ""))}
		"end":
			_frames.pop_back()
		_:
			push_error("[RPG-SEQ] sequence '%s': unknown command '%s'" % [_id, name])

## A task that waits (the default) or runs in the background (`wait: false`).
func _start(task: Dictionary, command: Dictionary) -> void:
	if RpgUtil.to_bool(command.get("wait", true)):
		_task = task
	else:
		_background.append(task)

func _jump(label: String) -> void:
	var frame: Dictionary = _frames.back()
	var sequence: RpgSequence = frame["sequence"]
	var index := sequence.label_index(label)
	if index < 0:
		push_error("[RPG-SEQ] sequence '%s': no label '%s'" % [sequence.id, label])
		return
	frame["pc"] = index

func _cmd_call(command: Dictionary) -> void:
	var sequence_id := StringName(str(command.get("sequence", "")))
	if _frames.size() >= MAX_CALL_DEPTH:
		push_error("[RPG-SEQ] calls nested deeper than %d at '%s'" % [MAX_CALL_DEPTH, sequence_id])
		return
	var called := RpgSequence.load_sequence(sequence_id)
	if called == null:
		push_error("[RPG-SEQ] call: no sequence '%s'" % sequence_id)
		return
	_frames.append({"sequence": called, "pc": 0})

func _cmd_move(command: Dictionary) -> void:
	var node := _entity(str(command.get("entity", "")))
	if node == null:
		return
	var tile := float(_tile_px())
	var offset := RpgSequence.tiles_of(command, "tiles")
	var points: Array[Vector2] = []
	var corner := node.position + Vector2(offset.x * tile, 0.0)
	if offset.x != 0:
		points.append(corner)
	if offset.y != 0:
		points.append(corner + Vector2(0.0, offset.y * tile))
	var speed := RpgUtil.to_float(command.get("speed", 0.0)) * tile
	if speed <= 0.0:
		speed = _walk_speed(node, tile)
	if node is RpgActor:
		(node as RpgActor).scripted_walk = true
		_hold(node)
	_start({"kind": "move", "node": node, "points": points, "speed": speed}, command)

func _walk_speed(node: Node, tile: float) -> float:
	var actor := node as RpgActor
	var movement: RpgMovement = actor.component("Movement") as RpgMovement if actor != null else null
	return movement.speed if movement != null and movement.speed > 0.0 else DEFAULT_SPEED_TILES * tile

func _cmd_face(command: Dictionary) -> void:
	var node := _entity(str(command.get("entity", "")))
	if node == null:
		return
	var dir := str(command.get("dir", ""))
	if command.has("toward"):
		var other := _entity(str(command.get("toward", "")))
		if other == null:
			return
		var d := _where(other) - _where(node)
		if d == Vector2.ZERO:
			return
		dir = RpgAnimationDriver.dir_to_facing(d)
	_set_facing(node, dir)

func _cmd_animate(command: Dictionary) -> void:
	var actor := _entity(str(command.get("entity", ""))) as RpgActor
	if actor == null:
		return
	var animation := str(command.get("animation", ""))
	if animation == "":
		_release(actor)
		_held.erase(actor)
		return
	if not actor.hold_animation(animation):
		push_warning("[RPG-SEQ] %s has no animation '%s_%s'" % [actor.name, animation, actor.facing])
		return
	_hold(actor)
	if command.has("seconds"):
		_start({"kind": "hold", "node": actor, "left": RpgUtil.to_float(command.get("seconds", 0.0))}, command)

func _cmd_fade(command: Dictionary, to: float) -> void:
	var router := RpgUtil.router()
	if router == null:
		return
	_faded = to > 0.0
	_start({"kind": "fade", "from": router.fade_alpha(), "to": to, "t": 0.0, "seconds": RpgUtil.to_float(command.get("seconds", DEFAULT_FADE_S))}, command)

func _cmd_pan(command: Dictionary) -> void:
	var to := Vector2.ZERO
	if command.has("entity"):
		var target := _entity(str(command.get("entity", "")))
		var player := _entity("player")
		if target != null and player != null:
			to = _where(target) - _where(player)
	else:
		to = Vector2(RpgSequence.tiles_of(command, "tiles")) * float(_tile_px())
	_camera_used = true
	_start({"kind": "pan", "from": _pan, "to": to, "t": 0.0, "seconds": RpgUtil.to_float(command.get("seconds", DEFAULT_PAN_S))}, command)

func _cmd_sound(command: Dictionary) -> void:
	var router := RpgUtil.router()
	var audio: Node = router.audio if router != null else null
	if audio != null and audio.has_method("play"):
		audio.call("play", StringName(str(command.get("slot", ""))))

func _cmd_dialogue(command: Dictionary) -> void:
	var resource := _dialogue_of(command)
	if resource == null:
		return
	var box := _box()
	if _skipping or box == null:
		var walker := RpgDialogueRunner.new()
		walker.start(resource)
		walker.fast_forward()
		return
	_task = {"kind": "dialogue", "resource": resource, "opened": false}

## The dialogue of a show_dialogue command: a file (an id under game/data/dialogue or a res://
## path) or lines written into the command.
static func _dialogue_of(command: Dictionary) -> RpgDialogueResource:
	if command.has("lines"):
		var resource := RpgDialogueResource.new()
		for text: Variant in RpgUtil.to_array(command.get("lines")):
			var line := RpgDialogueLine.new()
			line.text = str(text)
			line.speaker = str(command.get("speaker", ""))
			resource.lines.append(line)
		return resource
	var ref := str(command.get("dialogue", ""))
	var path := ref if ref.contains("://") else "%s/%s.tres" % [RpgGameState.DIALOGUE_DIR, ref]
	if ref == "" or not ResourceLoader.exists(path):
		push_error("[RPG-SEQ] show_dialogue: no dialogue '%s'" % ref)
		return null
	return load(path) as RpgDialogueResource

func _cmd_battle(command: Dictionary) -> void:
	var data := RpgEncounterData.new()
	for enemy_id: Variant in RpgUtil.to_array(command.get("enemies")):
		var ref := str(enemy_id)
		var path := ref if ref.contains("://") else "%s/%s.tres" % [RpgGameState.ENEMIES_DIR, ref]
		var def: RpgEnemyDefinition = load(path) as RpgEnemyDefinition if ResourceLoader.exists(path) else null
		if def == null:
			push_error("[RPG-SEQ] start_battle: no enemy '%s'" % str(enemy_id))
			continue
		data.enemies.append(def)
	if data.enemies.is_empty():
		return
	data.can_escape = RpgUtil.to_bool(command.get("can_escape", true))
	_task = {"kind": "battle", "data": data, "state": "waiting", "outcome": -1}

# ---------------------------------------------------------------- tasks

## Moves a task on by `delta`; true when it is done. While skipping every timed task ends at once.
func _advance(task: Dictionary, delta: float) -> bool:
	var step := INF if _skipping else delta
	match str(task["kind"]):
		"wait":
			var left: float = task["left"]
			task["left"] = left - step
			return left - step <= EPSILON
		"hold":
			var left: float = task["left"]
			task["left"] = left - step
			if left - step > EPSILON:
				return false
			var held: Node = task["node"]
			if is_instance_valid(held):
				_release(held)
				_held.erase(held)
			return true
		"move":
			return _advance_move(task, step)
		"fade", "pan", "shake":
			return _advance_curve(task, step)
		"dialogue":
			return _advance_dialogue(task)
		"battle":
			return _advance_battle(task)
		"map":
			return _advance_map(task)
		"wait_for":
			return _waiting_for(str(task["entity"])) == 0
	return true

func _advance_move(task: Dictionary, step: float) -> bool:
	var node: Node2D = task["node"] if is_instance_valid(task["node"]) else null
	var points: Array[Vector2] = task["points"]
	if node == null:
		return true
	var budget := step * RpgUtil.to_float(task["speed"])
	while not points.is_empty() and budget > 0.0:
		var to := points[0]
		var d := to - node.position
		if d != Vector2.ZERO:
			_set_facing(node, RpgAnimationDriver.dir_to_facing(d))
		if d.length() <= budget:
			node.position = to
			budget -= d.length()
			points.pop_front()
		else:
			node.position += d.normalized() * budget
			budget = 0.0
	if not points.is_empty():
		return false
	if node is RpgActor:
		(node as RpgActor).scripted_walk = false
	return true

## Fades, pans and shakes: a value that runs from 0 to `seconds`.
func _advance_curve(task: Dictionary, step: float) -> bool:
	var seconds: float = task["seconds"]
	var t: float = minf(RpgUtil.to_float(task["t"]) + step, seconds)
	if seconds - t <= EPSILON:
		t = seconds
	task["t"] = t
	var k := 1.0 if seconds <= 0.0 else t / seconds
	match str(task["kind"]):
		"fade":
			var router := RpgUtil.router()
			if router != null:
				router.set_fade_alpha(lerpf(RpgUtil.to_float(task["from"]), RpgUtil.to_float(task["to"]), k))
		"pan":
			var from: Vector2 = task["from"]
			var to: Vector2 = task["to"]
			_pan = from.lerp(to, k)
		"shake":
			var strength: float = task["strength"]
			_shake = Vector2.ZERO if k >= 1.0 or not _shake_enabled() else Vector2(sin(t * 61.0), cos(t * 47.0)) * strength * (1.0 - k)
	_apply_camera()
	return k >= 1.0

func _advance_dialogue(task: Dictionary) -> bool:
	var box := _box()
	var resource: RpgDialogueResource = task["resource"]
	var opened: bool = task["opened"]
	if box == null:
		return true
	var open := RpgUtil.to_bool(box.call("is_open"))
	if not opened:
		if open:
			return false  # someone else's dialogue: wait for it
		if _skipping:
			var walker := RpgDialogueRunner.new()
			walker.start(resource)
			walker.fast_forward()
			return true
		box.call("open", resource, null)  # no actor: the box leaves the player's input alone
		task["opened"] = true
		return not RpgUtil.to_bool(box.call("is_open"))
	if open and _skipping:
		box.call("fast_forward")
		return true
	return not open

func _advance_battle(task: Dictionary) -> bool:
	var router := RpgUtil.router()
	var combat: RpgCombatMode = router.combat if router != null else null
	if combat == null:
		push_error("[RPG-SEQ] start_battle: this game has no combat mode")
		return true
	match str(task["state"]):
		"waiting":
			if combat.is_in_combat() or router.is_busy():
				return false
			_complete_background()
			if not combat.encounter_finished.is_connected(_on_battle_finished):
				combat.encounter_finished.connect(_on_battle_finished, CONNECT_ONE_SHOT)
			var data: RpgEncounterData = task["data"]
			combat.start_encounter(data)
			if not combat.is_in_combat():
				combat.encounter_finished.disconnect(_on_battle_finished)
				push_warning("[RPG-SEQ] start_battle: the combat mode did not start a battle")
				return true
			task["state"] = "fighting"
			return false
	var outcome := RpgUtil.to_int(task["outcome"], -1)
	if outcome < 0:
		return false
	_reset_camera_state()  # the map was loaded again behind the battle
	if outcome == RpgEncounterResult.Outcome.DEFEAT:
		_frames.clear()  # the defeat policy takes over
	return true

func _on_battle_finished(result: RpgEncounterResult) -> void:
	if str(_task.get("kind", "")) == "battle":
		_task["outcome"] = result.outcome if result != null else RpgEncounterResult.Outcome.ESCAPED

func _advance_map(task: Dictionary) -> bool:
	var router := RpgUtil.router()
	if router == null:
		return true
	if router.is_busy():
		return false
	if RpgUtil.to_bool(task["requested"]):
		return true
	_complete_background()
	_reset_camera_state()
	_faded = false  # the change fades in by itself
	var spawn: StringName = task["spawn"]
	router.go_to(str(task["map"]), spawn)
	task["requested"] = true
	return not router.is_busy()

## How many background tasks move `entity` (all background tasks when it is "").
func _waiting_for(entity: String) -> int:
	var node: Node2D = _entity(entity) if entity != "" else null
	var count := 0
	for task in _background:
		if entity == "" or (str(task["kind"]) == "move" and is_instance_valid(task["node"]) and task["node"] == node):
			count += 1
	return count

func _complete_background() -> void:
	var was := _skipping
	_skipping = true
	for task in _background:
		_advance(task, 0.0)
	_background.clear()
	_skipping = was

# ---------------------------------------------------------------- characters and camera

## The map in use: the test override, else the router's current map.
func _map() -> Node:
	if map_override != null and is_instance_valid(map_override):
		return map_override
	var router := RpgUtil.router()
	return router.current_map if router != null else null

func _box() -> Node:
	if box_override != null and is_instance_valid(box_override):
		return box_override
	return RpgUtil.service(&"rpg_dialogue_box")

## "player", or the node with this entity_id in the current map; null (and an error) otherwise.
func _entity(entity_id: String) -> Node2D:
	var map := _map()
	if map == null or entity_id == "":
		return null
	for node in map.find_children("*", "", true, false):
		if not (node is Node2D) or node.is_queued_for_deletion():
			continue
		if entity_id == "player" and node.is_in_group("player"):
			return node as Node2D
		if entity_id != "player" and node.get("entity_id") != null and str(node.get("entity_id")) == entity_id:
			return node as Node2D
	push_error("[RPG-SEQ] sequence '%s': no '%s' in the map" % [_id, entity_id])
	return null

func _tile_px() -> int:
	return RpgUtil.map_tile_px(_map())

static func _where(node: Node2D) -> Vector2:
	return RpgUtil.world_position(node)

func _set_facing(node: Node, dir: String) -> void:
	if not RpgSequence.DIRECTIONS.has(dir):
		return
	if node is RpgActor:
		(node as RpgActor).set_facing(dir)
	elif "facing" in node:
		node.set("facing", dir)

func _hold(node: Node) -> void:
	if not _held.has(node):
		_held.append(node)

func _release(node: Node) -> void:
	if not is_instance_valid(node) or not (node is RpgActor):
		return
	var actor := node as RpgActor
	actor.scripted_walk = false
	if actor.animation_locked:
		actor.release_animation()

func _apply_camera() -> void:
	var camera := _camera_if_any()
	if camera != null:
		camera.offset = _pan + _shake

## The player's camera (a child named "Camera"), or null.
func _camera_if_any() -> Camera2D:
	var map := _map()
	if map == null:
		return null
	for node in map.find_children("*", "", true, false):
		if node.is_in_group("player"):
			return node.get_node_or_null("Camera") as Camera2D
	return null

## The camera stays where it is while the player moves on (until camera_unlock or the end).
func _lock_camera() -> void:
	var camera := _camera_if_any()
	if camera == null or _camera_locked:
		return
	var at := _where(camera)
	camera.top_level = true
	if camera.is_inside_tree():
		camera.global_position = at
	_camera_locked = true
	_camera_used = true

func _unlock_camera() -> void:
	if not _camera_locked:
		return
	_camera_locked = false
	var camera := _camera_if_any()
	if camera != null:
		camera.top_level = false
		camera.position = Vector2.ZERO

## After a map change or a battle the map (and its camera) are new.
func _reset_camera_state() -> void:
	_pan = Vector2.ZERO
	_shake = Vector2.ZERO
	_camera_locked = false
	_held.clear()

func _shake_enabled() -> bool:
	var settings := RpgUtil.settings()
	return settings == null or RpgUtil.to_bool(settings.get("screen_shake"))

# ---------------------------------------------------------------- requests

## `run_sequence:<id>` from a dialogue: starts once the dialogue has closed; behind a running one.
func _on_requested(sequence_id: StringName) -> void:
	var sequence := RpgSequence.load_sequence(sequence_id)
	if sequence == null:
		push_error("[RPG-SEQ] run_sequence: no sequence '%s'" % sequence_id)
		return
	var box := _box()
	if not is_running() and box != null and RpgUtil.to_bool(box.call("is_open")):
		_pending.append(sequence)
	else:
		run(sequence)

func _on_dialogue_finished(_resource: Resource) -> void:
	if not _pending.is_empty():
		_start_pending_later.call_deferred()

# Three physics frames let the dialogue box hand the player their controls back first.
func _start_pending_later() -> void:
	for i in 3:
		await get_tree().physics_frame
	var pending := _pending.duplicate()
	_pending.clear()
	for sequence: RpgSequence in pending:
		run(sequence)
