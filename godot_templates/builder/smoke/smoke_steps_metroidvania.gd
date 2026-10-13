extends RefCounted
## The metroidvania's smoke steps (T14.11): the whole run of a metroidvania project, from the title
## screen to the last room. The shared sequence of the other archetypes walks a top-down village
## (a villager below the player, a house, a field), so this archetype has a sequence of its own:
## the title and a new game, a dialogue and the inventory, then the side-view game itself:
##
##   a jump over a gap -> a one-way platform -> spikes -> a ledge that needs an ability ->
##   a room change -> the hermit -> the guardian -> the double jump -> the dash's pickup ->
##   the dash -> a save station, the title and Continue -> a defeat -> the last room
##
## Everything is read from the stored world plan (rpggen/world_plan.json), so the steps follow the
## world that was generated, whatever the seed. A step about an ability the world does not have
## passes with a note. The player is moved with the real input actions where the step is about
## moving, and put in place (teleported) where it is about something else.

const JsonUtil := preload("../lib/json_util.gd")

## The addon's smoke runner: it knows the folder this run saves into (a run's own).
const SmokeRunner := preload("res://addons/rpg_runtime/debug/smoke_runner.gd")
const WORLD_PLAN := "res://rpggen/world_plan.json"
const TITLE_SCENE := "res://generated/scenes/ui/title_screen.tscn"
const SAVE_SLOT := 1
const END_FLAG := ["game", "finished"]

var _plan: Dictionary = {}

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	return [
		{"name": "title_new_game", "fn": _title_new_game, "timeout_s": 40.0},
		{"name": "sign_dialogue", "fn": _sign_dialogue, "timeout_s": 30.0},
		{"name": "inventory_item", "fn": _inventory_item, "timeout_s": 15.0},
		{"name": "jump_clears_gap", "fn": _jump_clears_gap, "timeout_s": 20.0},
		{"name": "one_way_platform", "fn": _one_way_platform, "timeout_s": 20.0},
		{"name": "hazard_hurts_and_returns", "fn": _hazard_hurts_and_returns, "timeout_s": 20.0},
		{"name": "gate_blocks", "fn": _gate_blocks, "timeout_s": 30.0},
		{"name": "room_transition", "fn": _room_transition, "timeout_s": 30.0},
		{"name": "npc_talks", "fn": _npc_talks, "timeout_s": 30.0},
		{"name": "guardian_dies", "fn": _guardian_dies, "timeout_s": 40.0},
		{"name": "double_jump_reaches_ledge", "fn": _double_jump_reaches_ledge, "timeout_s": 30.0},
		{"name": "pickup_dash", "fn": _pickup_dash, "timeout_s": 30.0},
		{"name": "dash_crosses_gap", "fn": _dash_crosses_gap, "timeout_s": 30.0},
		{"name": "save_station_persist", "fn": _save_station_persist, "timeout_s": 60.0},
		{"name": "defeat_returns_to_station", "fn": _defeat_returns_to_station, "timeout_s": 40.0},
		{"name": "end_room", "fn": _end_room, "timeout_s": 40.0},
	]

# ---------------------------------------------------------------- helpers

func _autoload(autoload_name: String) -> Node:
	return _tree().root.get_node_or_null(autoload_name)

func _state() -> RpgGameState:
	return _autoload("GameState") as RpgGameState

func _router() -> RpgSceneRouter:
	return _autoload("SceneRouter") as RpgSceneRouter

func _player() -> RpgPlatformPlayer:
	for node in _tree().get_nodes_in_group("player"):
		if node is RpgPlatformPlayer and is_instance_valid(node) and not node.is_queued_for_deletion() and node.is_inside_tree():
			return node
	return null

func _frames(n: int) -> void:
	for i in n:
		await _tree().physics_frame

func _wait_for(done: Callable, max_frames: int) -> bool:
	for i in max_frames:
		if done.call():
			return true
		await _tree().physics_frame
	return JsonUtil.to_bool(done.call())

func _tap(action: String, frames: int = 3) -> void:
	Input.action_press(action)
	await _frames(frames)
	Input.action_release(action)

func _release_all() -> void:
	for action: String in ["move_left", "move_right", "move_up", "move_down", "down", "jump", "dash", "attack", "interact"]:
		if InputMap.has_action(action):
			Input.action_release(action)

func _rooms() -> Dictionary:
	if _plan.is_empty() and FileAccess.file_exists(WORLD_PLAN):
		_plan = JsonUtil.to_dict(JsonUtil.to_dict(JsonUtil.read(WORLD_PLAN)).get("rooms", {}))
	return _plan

func _room_list() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in JsonUtil.to_array(_rooms().get("list", [])):
		out.append(JsonUtil.to_dict(raw))
	return out

func _room(id: String) -> Dictionary:
	for room in _room_list():
		if JsonUtil.to_str(room.get("id", "")) == id:
			return room
	return {}

func _start_id() -> String:
	return JsonUtil.to_str(_rooms().get("start", ""))

func _abilities() -> Array:
	return JsonUtil.to_array(_rooms().get("abilities", []))

func _cell(value: Variant) -> Vector2i:
	var pair := JsonUtil.to_array(value)
	return Vector2i(JsonUtil.to_int(pair[0]), JsonUtil.to_int(pair[1])) if pair.size() == 2 else Vector2i.ZERO

func _current() -> RpgRoom:
	var router := _router()
	return router.current_map as RpgRoom if router != null else null

func _tile() -> float:
	var room := _current()
	return float(room.tile_size) if room != null else 16.0

## The room with a gate for `ability`, and the gate: [room, gate], or [] without one.
func _gated(ability: String) -> Array:
	for room in _room_list():
		for raw: Variant in JsonUtil.to_array(room.get("gates", [])):
			var gate := JsonUtil.to_dict(raw)
			if JsonUtil.to_str(gate.get("ability", "")) == ability:
				return [room, gate]
	return []

func _in_room(id: String) -> bool:
	var room := _current()
	var router := _router()
	return room != null and is_instance_valid(room) and room.is_inside_tree() and String(room.map_id) == id and not router.is_busy() and _player() != null

## Goes to a room through the router (a fade) and waits until it is shown. The enemies of the
## room are stopped and the player cannot be hurt, unless the step asks otherwise afterwards.
func _enter(id: String) -> bool:
	_release_all()
	var room := _room(id)
	var router := _router()
	if room.is_empty() or router == null:
		return false
	# A call the router gets while it is still busy is ignored, so on a slow machine one try may
	# not be enough: wait for it, ask, and ask again when the room did not come.
	for attempt in 3:
		if _in_room(id):
			break
		await _wait_for(func() -> bool: return not router.is_busy(), 600)
		router.go_to("res://" + JsonUtil.to_str(room["map"]), &"default")
		if await _wait_for(func() -> bool: return _in_room(id), 900):
			break
	if not _in_room(id):
		var shown := _current()
		print("[rpggen] INFO could not enter %s: the map is %s, the router is %s, calls ignored %d, player %s" % [id, String(shown.map_id) if shown != null else "none", "busy" if router.is_busy() else "idle", router.ignored_calls, "there" if _player() != null else "missing"])
		return false
	await _frames(4)
	_calm()
	return true

## Stops the room's enemies and shields the player for a long while.
func _calm() -> void:
	var room := _current()
	if room == null:
		return
	for node in room.find_children("*", "CharacterBody2D", true, false):
		if node is RpgSideEnemy:
			node.process_mode = Node.PROCESS_MODE_DISABLED
	var player := _player()
	if player != null and player.hurtbox != null:
		player.hurtbox.make_invulnerable(600.0)

func _vulnerable(player: RpgPlatformPlayer) -> void:
	if player.hurtbox != null:
		player.hurtbox.invulnerable_until_ms = 0

## Puts the player's feet on the floor of a feet cell and waits until it stands.
func _put(cell: Vector2i) -> bool:
	var player := _player()
	if player == null:
		return false
	_release_all()
	var tile := _tile()
	player.global_position = Vector2((cell.x + 0.5) * tile, (cell.y + 1.0) * tile)
	player.velocity = Vector2.ZERO
	player.on_ladder = false
	await _frames(2)
	# asked of the player there is, not of the one that was put: a room that is entered again
	# while this waits (a slow machine) frees it, and a freed capture is a script error
	var standing := func() -> bool:
		var now := _player()
		return now != null and now.is_on_floor()
	return await _wait_for(standing, 90)

func _row_of(room: Dictionary, y: int) -> String:
	var rows := JsonUtil.to_array(room.get("tiles", []))
	return JsonUtil.to_str(rows[y]) if y >= 0 and y < rows.size() else ""

## The first run of `symbol` in a room's tiles: [row, first column, last column], or [].
func _run_of(room: Dictionary, symbol: String) -> Array:
	var rows := JsonUtil.to_array(room.get("tiles", []))
	for y in rows.size():
		var row := JsonUtil.to_str(rows[y])
		var first := row.find(symbol)
		if first >= 0:
			var last := first
			while last + 1 < row.length() and row[last + 1] == symbol:
				last += 1
			return [y, first, last]
	return []

func _floor_row(room: Dictionary) -> int:
	return _cell(room["size"]).y - 3

func _exit_of(room: Dictionary, edge: String) -> Dictionary:
	for raw: Variant in JsonUtil.to_array(room.get("exits", [])):
		var exit_spec := JsonUtil.to_dict(raw)
		if JsonUtil.to_str(exit_spec.get("edge", "")) == edge:
			return exit_spec
	return {}

func _find_entity(scene: Node, entity_id: String) -> Node2D:
	for node in scene.find_children("*", "", true, false):
		if node is Node2D and node.get("entity_id") != null and str(node.get("entity_id")) == entity_id and not node.is_queued_for_deletion():
			return node
	return null

func _dialogue_box() -> Node:
	return RpgUtil.service(&"rpg_dialogue_box")

func _box_open() -> bool:
	var box := _dialogue_box()
	return box != null and JsonUtil.to_bool(box.call("is_open"))

func _press(action: String) -> void:
	var ev := InputEventAction.new()
	ev.action = action
	ev.pressed = true
	Input.parse_input_event(ev)
	await _tree().process_frame
	ev = InputEventAction.new()
	ev.action = action
	ev.pressed = false
	Input.parse_input_event(ev)
	await _tree().process_frame

# ---------------------------------------------------------------- the title, a dialogue, the bag

func _title_new_game() -> String:
	var tree := _tree()
	var save := _autoload("SaveManager") as RpgSaveManager
	if save == null or _state() == null:
		return "SaveManager or GameState autoload is missing"
	save.set("dir", SmokeRunner.save_dir())  # never touch the player's real saves
	for slot in range(RpgSaveManager.AUTOSAVE_SLOT, RpgSaveManager.SLOTS + 1):
		save.delete(slot)
	if _rooms().is_empty() or _start_id() == "":
		return "the project has no stored plan of rooms (%s)" % WORLD_PLAN
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
	if not await _wait_for(func() -> bool: return _in_room(_start_id()), 600):
		return "pressing confirm on New Game did not open the start room"
	var room := _current()
	var cameras := 0
	for node in room.find_children("*", "Camera2D", true, false):
		if (node as Camera2D).enabled:
			cameras += 1
	if cameras != 1:
		return "a room must have exactly one enabled camera, the start room has %d" % cameras
	var player := _player()
	if not await _wait_for(func() -> bool: return player.is_on_floor(), 120):
		return "the player does not stand on the floor of the start room"
	var state := _state()
	if not state.room_visited(_start_id()):
		return "the start room is not on the room map"
	return ""

## The sign of the first room: interact opens its dialogue, confirm closes it.
func _sign_dialogue() -> String:
	var room := _room(_start_id())
	var scene := _current()
	var sign_node := scene.get_node_or_null("Entities/Sign") as Node2D
	if not room.has("sign") or sign_node == null:
		print("[rpggen] INFO sign_dialogue: the start room has no sign (the packs have none), step passes")
		return ""
	var player := _player()
	_calm()
	await _put(_cell(room["sign"]) + Vector2i(-1, 0))
	await _frames(4)
	if player.find_target() != sign_node:
		return "the player beside the sign does not find it"
	await _tap("interact")
	if not await _wait_for(_box_open, 60):
		return "interacting with the sign did not open a dialogue"
	if player.input_enabled:
		return "the player can still move while the dialogue is open"
	for i in 30:
		if not _box_open():
			break
		await _press("confirm")
		await _frames(2)
	if _box_open():
		return "the sign's dialogue did not close"
	await _frames(6)
	if not player.input_enabled:
		return "the player did not get its controls back after the dialogue"
	return ""

## A new game starts with potions: using one from the bag heals.
func _inventory_item() -> String:
	var state := _state()
	var have: int = state.inventory.count(&"potion")
	if have <= 0:
		return "a new game should start with a potion in the bag"
	var stats := state.player_stats
	var full := RpgUtil.max_hp(stats)
	stats.hp = maxi(1, full - 6)
	var before := stats.hp
	if not state.inventory.use(&"potion", stats):
		return "the potion could not be used"
	if stats.hp <= before or state.inventory.count(&"potion") != have - 1:
		return "using a potion should heal and take one out of the bag (hp %d -> %d)" % [before, stats.hp]
	stats.hp = full
	return ""

# ---------------------------------------------------------------- moving

func _jump_clears_gap() -> String:
	if not await _enter(_start_id()):
		return "the start room could not be entered"
	var room := _room(_start_id())
	var floor_row := _floor_row(room)
	var floor_text := _row_of(room, floor_row)
	var gap_from := floor_text.find(".", 2)
	if gap_from < 0:
		return "the start room has no gap in its floor"
	var gap_to := gap_from
	while gap_to + 1 < floor_text.length() and floor_text[gap_to + 1] == ".":
		gap_to += 1
	var player := _player()
	var state := _state()
	_vulnerable(player)  # falling into the gap would cost a hit point: the step would see it
	await _put(Vector2i(gap_from - 3, floor_row - 1))
	var hp := state.player_stats.hp
	var tile := _tile()
	Input.action_press("move_right")
	if not await _wait_for(func() -> bool: return player.global_position.x >= gap_from * tile - 5.0, 120):
		_release_all()
		return "the player did not run to the edge of the gap"
	Input.action_press("jump")
	var across := await _wait_for(func() -> bool: return player.is_on_floor() and player.global_position.x > (gap_to + 1) * tile + 2.0, 180)
	_release_all()
	if not across:
		return "the player did not land on the far side of the %d-tile gap (x %.0f)" % [gap_to - gap_from + 1, player.global_position.x]
	if state.player_stats.hp != hp:
		return "the jump over the gap cost a hit point"
	return ""

func _one_way_platform() -> String:
	if not await _enter(_start_id()):
		return "the start room could not be entered"
	var room := _room(_start_id())
	var plank := _run_of(room, "=")
	if plank.is_empty():
		return "the start room has no one-way platform"
	var row: int = plank[0]
	var middle := (JsonUtil.to_int(plank[1]) + JsonUtil.to_int(plank[2])) / 2
	var player := _player()
	var tile := _tile()
	var floor_row := _floor_row(room)
	await _put(Vector2i(middle, floor_row - 1))
	var top := row * tile
	Input.action_press("jump")  # held: a full jump, up through the platform
	var above := await _wait_for(func() -> bool: return player.global_position.y < top - 1.0, 60)
	Input.action_release("jump")
	if not above:
		return "the player did not pass through the one-way platform from below"
	if not await _wait_for(func() -> bool: return player.is_on_floor() and absf(player.global_position.y - top) < 1.5, 120):
		return "the player does not stand on the one-way platform (y %.1f, its top is at %.1f)" % [player.global_position.y, top]
	if not player.standing_on_one_way():
		return "standing on the platform is not seen as standing on a one-way tile"
	var jumps := [0]
	var count := func() -> void: jumps[0] += 1
	player.jumped.connect(count)
	Input.action_press("down")
	await _frames(2)
	Input.action_press("jump")
	await _frames(4)
	_release_all()
	var down := await _wait_for(func() -> bool: return player.is_on_floor() and absf(player.global_position.y - floor_row * tile) < 1.5, 120)
	player.jumped.disconnect(count)
	if not down:
		return "down + jump did not drop the player through the platform (y %.1f)" % player.global_position.y
	if jumps[0] != 0:
		return "dropping through a platform must not be a jump"
	return ""

func _hazard_hurts_and_returns() -> String:
	if not await _enter(_start_id()):
		return "the start room could not be entered"
	var room := _room(_start_id())
	var floor_row := _floor_row(room)
	var above := _row_of(room, floor_row - 1)
	var spike := above.find("^")
	if spike < 0:
		return "the start room has no spikes on its floor"
	var player := _player()
	var state := _state()
	var tile := _tile()
	await _put(Vector2i(spike - 3, floor_row - 1))
	await _frames(30)  # half a second on one cell: this is safe ground now
	if not player.has_safe_position:
		return "standing still did not make safe ground"
	var safe := player.safe_position
	_vulnerable(player)
	var hp := state.player_stats.hp
	var returned := [false]
	var on_return := func() -> void: returned[0] = true
	player.returned_to_safe_ground.connect(on_return)
	Input.action_press("move_right")
	var hurt := await _wait_for(func() -> bool: return state.player_stats.hp < hp, 120)
	_release_all()
	if not hurt:
		player.returned_to_safe_ground.disconnect(on_return)
		return "walking onto the spikes did not hurt"
	if state.player_stats.hp != hp - 1:
		return "spikes should cost 1 hit point, they cost %d" % (hp - state.player_stats.hp)
	var back := await _wait_for(func() -> bool: return returned[0], 60)
	player.returned_to_safe_ground.disconnect(on_return)
	if not back:
		return "the player was not put back on safe ground within a second"
	if player.global_position.distance_to(safe) > tile * 1.5 or player.global_position.x > spike * tile:
		return "the player is at %s, the last safe ground was %s" % [player.global_position, safe]
	await _frames(40)
	if state.player_stats.hp != hp - 1:
		return "one touch of the spikes hurt more than once"
	state.heal_party_full()
	return ""

## At the ledge that needs the double jump (or the high jump): without the ability the player
## does not get up there.
func _gate_blocks() -> String:
	var found := _gated("double_jump")
	if found.is_empty():
		found = _gated("high_jump")
	if found.is_empty():
		print("[rpggen] INFO gate_blocks: this world has no ledge gate, step passes")
		return ""
	var room: Dictionary = found[0]
	var gate: Dictionary = found[1]
	if _state().has_ability(StringName(JsonUtil.to_str(gate["ability"]))):
		return "the player has %s before the game gave it" % gate["ability"]
	if not await _enter(JsonUtil.to_str(room["id"])):
		return "the room of the ledge could not be entered"
	var player := _player()
	var tile := _tile()
	var cell := _cell(gate["cell"])
	var ledge_top := (_floor_row(room) - JsonUtil.to_int(gate["size"])) * tile
	await _put(cell)
	Input.action_press("move_right")
	var highest := player.global_position.y
	for i in 120:  # two seconds of jumping at it
		if i % 30 == 0:
			Input.action_press("jump")
		elif i % 30 == 25:
			Input.action_release("jump")
		await _tree().physics_frame
		highest = minf(highest, player.global_position.y)
		if player.is_on_floor() and player.global_position.y <= ledge_top + 1.0:
			_release_all()
			return "the player got onto the %d-tile ledge without %s" % [JsonUtil.to_int(gate["size"]), gate["ability"]]
	_release_all()
	if highest <= ledge_top:
		return "a plain jump reached the height of the ledge (%.0f px above the floor)" % (_floor_row(room) * tile - highest)
	return ""

func _room_transition() -> String:
	var start := _room(_start_id())
	if not await _enter(_start_id()):
		return "the start room could not be entered"
	var east := _exit_of(start, "E")
	if east.is_empty():
		return "the start room has no exit to the east"
	var target := JsonUtil.to_str(east["to"])
	var size := _cell(start["size"])
	var player := _player()
	var saves := _autoload("SaveManager") as RpgSaveManager
	saves.delete(RpgSaveManager.AUTOSAVE_SLOT)
	await _put(Vector2i(size.x - 4, _floor_row(start) - 1))
	Input.action_press("move_right")
	var changed := await _wait_for(func() -> bool: return _in_room(target), 300)
	if not changed:
		_release_all()
		return "walking through the east exit did not change the room (still %s)" % String(_current().map_id if _current() != null else &"?")
	var arrived := _player()
	var speed := arrived.velocity.x
	_release_all()
	var tile := _tile()
	if arrived.global_position.x > 6.0 * tile:
		return "the player should appear at the west exit of %s, it is at x %.0f" % [target, arrived.global_position.x]
	if arrived.facing != 1:
		return "the player should still look to the right after the room change"
	if speed <= 0.0:
		return "the player lost its speed in the room change"
	if not _state().room_visited(target):
		return "the room entered is not on the room map"
	await _frames(20)
	if not saves.has_save(RpgSaveManager.AUTOSAVE_SLOT):
		return "a room change should save into the autosave slot"
	_calm()
	return ""

## The hermit of the last room: the dialogue opens and the hermit turns to the player. The talk
## is cut short here; the last step has it to the end.
func _npc_talks() -> String:
	var end_id := JsonUtil.to_str(_rooms().get("end", ""))
	var room := _room(end_id)
	if not await _enter(end_id):
		return "the last room could not be entered"
	var npc := _current().get_node_or_null("Entities/Hermit") as RpgSideNpc
	if npc == null or not room.has("npc"):
		print("[rpggen] INFO npc_talks: the last room has no NPC (the packs have none), step passes")
		return ""
	var player := _player()
	await _put(_cell(room["npc"]) + Vector2i(-1, 0))
	await _wait_for(func() -> bool: return npc.is_on_floor(), 60)
	await _frames(4)
	if npc.facing != -1:
		npc.set_facing(1)  # look away first, so that turning is seen
		await _frames(2)
		npc.set_facing(1)
	player.set_facing(1)
	await _tap("interact")
	if not await _wait_for(_box_open, 60):
		return "interacting with the NPC did not open a dialogue"
	if npc.facing != -1:
		return "the NPC should face the player on its left"
	var box := _dialogue_box()
	box.call("_close")  # without running the rest: the last line is the end of the game
	await _frames(8)
	if _state().get_flag(END_FLAG[0], END_FLAG[1], false) == true:
		return "the end flag is set before the hermit's last line"
	return ""

# ---------------------------------------------------------------- the guardian and the abilities

func _guardian_dies() -> String:
	var guardian_id := JsonUtil.to_str(_rooms().get("guardian", ""))
	var abilities := _abilities()
	if guardian_id == "" or abilities.is_empty():
		print("[rpggen] INFO guardian_dies: this world has no guardian, step passes")
		return ""
	if not await _enter(guardian_id):
		return "the guardian's room could not be entered"
	var scene := _current()
	var state := _state()
	var first := StringName(JsonUtil.to_str(abilities[0]))
	var guardian := scene.get_node_or_null("Entities/Guardian") as RpgGuardian
	if guardian == null:
		# no enemy art at all: the ability lies in the room as a pickup instead
		var pickup := scene.get_node_or_null("Entities/Ability_%s" % first) as RpgAbilityPickup
		if pickup == null:
			return "the guardian's room has neither a guardian nor the pickup of %s" % first
		pickup.collect()
		return "" if state.has_ability(first) else "the pickup in the guardian's room did not grant %s" % first
	var gates: Array[RpgGate] = []
	for node in scene.get_node("Entities").get_children():
		if node is RpgGate:
			gates.append(node)
	if gates.is_empty():
		return "the guardian's room has no gate in its exits"
	for gate in gates:
		if gate.open:
			return "the exits of the guardian's room should be closed while it lives"
	var player := _player()
	var tile := _tile()
	guardian.process_mode = Node.PROCESS_MODE_INHERIT  # awake: it has to be hit
	guardian.speed_scale = 0.0
	state.player_stats.attack = 99
	var died := [false]
	guardian.died.connect(func() -> void: died[0] = true)
	player.global_position = guardian.global_position + Vector2(-tile * 1.1, 0.0)
	player.set_facing(1)
	await _frames(4)
	for i in 20:
		if died[0]:
			break
		guardian.speed_scale = 0.0
		guardian.velocity.x = 0.0
		player.global_position.x = guardian.global_position.x - tile * 1.1
		player.set_facing(1)
		await _tap("attack")
		await _frames(24)
	if not died[0]:
		return "the guardian did not die (hp %d)" % (guardian.health.hp() if is_instance_valid(guardian) else -1)
	await _frames(4)
	for gate in gates:
		if not gate.open:
			return "the exits should open when the guardian is defeated"
	if not state.has_ability(first):
		return "defeating the guardian should grant %s" % first
	if state.get_flag("%s_guardian" % guardian_id, "defeated", false) != true:
		return "the guardian's defeated flag is not set"
	state.player_stats.attack = 2
	return ""

func _double_jump_reaches_ledge() -> String:
	var found := _gated("double_jump")
	if found.is_empty():
		print("[rpggen] INFO double_jump_reaches_ledge: this world has no double-jump ledge, step passes")
		return ""
	var room: Dictionary = found[0]
	var gate: Dictionary = found[1]
	var state := _state()
	state.grant(&"double_jump")  # the guardian's, or the pickup's when this world orders them otherwise
	if not await _enter(JsonUtil.to_str(room["id"])):
		return "the room of the ledge could not be entered"
	var player := _player()
	var tile := _tile()
	var ledge_top := (_floor_row(room) - JsonUtil.to_int(gate["size"])) * tile
	await _put(_cell(gate["cell"]))
	await _tap("jump", 26)  # a full jump straight up, beside the overhang
	await _wait_for(func() -> bool: return player.velocity.y >= -20.0, 40)
	Input.action_press("jump")  # the second jump, near the top of the first
	await _frames(3)
	if not await _wait_for(func() -> bool: return player.global_position.y < ledge_top - 3.0, 60):
		_release_all()
		return "two jumps did not rise above the %d-tile ledge" % JsonUtil.to_int(gate["size"])
	Input.action_press("move_right")
	var up := await _wait_for(func() -> bool: return player.is_on_floor() and absf(player.global_position.y - ledge_top) < 1.5, 120)
	_release_all()
	if not up:
		return "the player does not stand on the ledge (y %.1f, its top is at %.1f)" % [player.global_position.y, ledge_top]
	return ""

func _pickup_dash() -> String:
	var state := _state()
	var holder: Dictionary = {}
	for room in _room_list():
		if JsonUtil.to_str(JsonUtil.to_dict(room.get("pickup", {})).get("ability", "")) == "dash":
			holder = room
	if holder.is_empty():
		if _abilities().has("dash") and not state.has_ability(&"dash"):
			return "the world has the dash but no room has its pickup"
		print("[rpggen] INFO pickup_dash: this world has no dash pickup, step passes")
		return ""
	if not await _enter(JsonUtil.to_str(holder["id"])):
		return "the room of the dash pickup could not be entered"
	var pickup := _current().get_node_or_null("Entities/Ability_dash") as RpgAbilityPickup
	if pickup == null:
		return "the room has no node for the dash pickup"
	var toasts: Array = []
	var bus := _autoload("Events") as RpgEvents
	var on_toast := func(text: String) -> void: toasts.append(text)
	bus.notify.connect(on_toast)
	var player := _player()
	var cell := _cell(JsonUtil.to_dict(holder["pickup"])["cell"])
	var tile := _tile()
	player.global_position = Vector2((cell.x + 0.5) * tile, (cell.y + 1.0) * tile)
	player.velocity = Vector2.ZERO
	var got := await _wait_for(func() -> bool: return state.has_ability(&"dash"), 60)
	bus.notify.disconnect(on_toast)
	if not got:
		return "touching the dash pickup did not grant the dash"
	if toasts.is_empty():
		return "the pickup showed no toast"
	await _frames(4)
	if is_instance_valid(pickup) and not pickup.is_queued_for_deletion():
		return "the pickup did not remove itself"
	return ""

func _dash_crosses_gap() -> String:
	var found := _gated("dash")
	if found.is_empty():
		print("[rpggen] INFO dash_crosses_gap: this world has no dash gap, step passes")
		return ""
	var room: Dictionary = found[0]
	var gate: Dictionary = found[1]
	var state := _state()
	state.grant(&"dash")
	if not await _enter(JsonUtil.to_str(room["id"])):
		return "the room of the gap could not be entered"
	var player := _player()
	var tile := _tile()
	var floor_row := _floor_row(room)
	var gap_from := _cell(gate["cell"]).x + 1
	var gap_to := gap_from + JsonUtil.to_int(gate["size"]) - 1
	_vulnerable(player)
	state.heal_party_full()
	var hp := state.player_stats.hp
	await _put(Vector2i(gap_from - 3, floor_row - 1))
	Input.action_press("move_right")
	if not await _wait_for(func() -> bool: return player.global_position.x >= gap_from * tile - 5.0, 120):
		_release_all()
		return "the player did not run to the edge of the gap"
	Input.action_press("jump")
	await _frames(3)
	await _wait_for(func() -> bool: return player.velocity.y >= -20.0, 40)
	if state.has_ability(&"double_jump"):
		Input.action_release("jump")
		await _frames(2)
		Input.action_press("jump")
		await _frames(3)
		await _wait_for(func() -> bool: return player.velocity.y >= -20.0, 40)
	await _tap("dash")
	var across := await _wait_for(func() -> bool: return player.is_on_floor() and player.global_position.x > (gap_to + 1) * tile + 2.0, 180)
	_release_all()
	if not across:
		return "the dash did not carry the player across the %d-tile gap (x %.0f, the far side starts at %.0f)" % [JsonUtil.to_int(gate["size"]), player.global_position.x, (gap_to + 1) * tile]
	if state.player_stats.hp != hp:
		return "crossing the gap cost a hit point"
	return ""

# ---------------------------------------------------------------- saving and defeat

## An ordinary enemy of the plan: [room id, entity id], or [].
func _an_enemy() -> Array:
	for room in _room_list():
		if not JsonUtil.to_array(room.get("enemies", [])).is_empty():
			return [JsonUtil.to_str(room["id"]), "%s_enemy_001" % room["id"]]
	return []

func _save_station_persist() -> String:
	var start := _room(_start_id())
	if not await _enter(_start_id()):
		return "the start room could not be entered"
	var station := _current().get_node_or_null("Entities/SaveStation") as RpgSaveStation
	if station == null or not start.has("station"):
		return "the start room has no save station"
	var state := _state()
	var saves := _autoload("SaveManager") as RpgSaveManager
	var enemy := _an_enemy()
	if not enemy.is_empty():
		state.set_flag(JsonUtil.to_str(enemy[1]), "defeated", true)  # as if the player had beaten it
	state.player_stats.hp = maxi(1, state.player_stats.hp - 3)
	var held: Array = state.abilities.duplicate()
	var player := _player()
	await _put(_cell(start["station"]))
	await _frames(70)  # entering the room saved by itself; the save made here has to be the newer one
	if player.find_target() != station:
		return "the player at the station does not find it"
	# the pause menu's Save is off in this archetype: the station is where one saves
	var controller := _router().get_node_or_null("UiController") as RpgUiController
	await _tap("interact")
	if not await _wait_for(func() -> bool: return controller.is_pause_open(), 60):
		return "using the station did not open the save menu"
	if state.player_stats.hp != RpgUtil.max_hp(state.player_stats):
		return "resting at a station should restore the health"
	if not enemy.is_empty() and state.get_flag(JsonUtil.to_str(enemy[1]), "defeated", false) == true:
		return "resting at a station should bring the enemies back"
	var menu: RpgSaveLoadMenu = null
	for node in controller.find_children("*", "Control", true, false):
		if node is RpgSaveLoadMenu:
			menu = node
	if menu == null:
		return "the menu the station opened is not the save menu"
	(menu.get_node("%%Slot%d" % SAVE_SLOT) as Button).pressed.emit()
	await _tree().process_frame
	await _tree().process_frame
	if not saves.has_save(SAVE_SLOT):
		return "choosing slot %d at the station did not save" % SAVE_SLOT
	menu.close()
	if not await _wait_for(func() -> bool: return not _tree().paused, 60):
		return "the game did not go on after the save menu closed"
	var station_at := station.global_position
	# quit to the title, then Continue
	var router := _router()
	await _wait_for(func() -> bool: return not router.is_busy(), 300)
	router.go_to(TITLE_SCENE)
	var tree := _tree()
	if not await _wait_for(func() -> bool: return tree.current_scene != null and tree.current_scene.name == "TitleScreen" and not router.is_busy(), 600):
		return "the title screen did not appear"
	state.abilities.clear()  # whatever the title leaves in memory, Continue has to bring it back
	var button := (tree.current_scene as Control).get_node("%Continue") as Button
	if button.disabled:
		return "Continue is disabled although there is a save"
	button.pressed.emit()
	if not await _wait_for(func() -> bool: return _in_room(_start_id()), 600):
		return "Continue did not open the start room"
	await _frames(6)
	var loaded := _player()
	if loaded.global_position.distance_to(station_at) > _tile() * 2.0:
		return "after Continue the player should be at the station, it is at %s" % loaded.global_position
	for ability: Variant in held:
		if not state.has_ability(StringName(JsonUtil.to_str(ability))):
			return "the ability %s was lost by saving and loading" % ability
	if not enemy.is_empty():
		if not await _enter(JsonUtil.to_str(enemy[0])):
			return "the room of the enemy could not be entered"
		if _find_entity(_current(), JsonUtil.to_str(enemy[1])) == null:
			return "the enemy %s should be back after the rest" % enemy[1]
	return ""

## At 0 hit points the player returns to the last station used, with full health and with what
## it had.
func _defeat_returns_to_station() -> String:
	var start := _room(_start_id())
	var state := _state()
	var point := RpgSaveStation.respawn_point(state)
	if point.is_empty():
		return "no station is remembered as the place to return to"
	var end_id := JsonUtil.to_str(_rooms().get("end", ""))
	if not await _enter(end_id):  # far from the station
		return "the last room could not be entered"
	var held: Array = state.abilities.duplicate()
	var gold := state.gold
	state.gold = gold + 7  # progress since the last save: it is kept
	var player := _player()
	_vulnerable(player)
	var blow := RpgDamageInfo.new()
	blow.amount = 9999
	player.health.take(blow)
	if not player.is_dead():
		return "9999 damage did not defeat the player"
	var fallen := player.get_instance_id()  # the node is gone once the room has changed
	if not await _wait_for(func() -> bool: return _in_room(_start_id()) and _player().get_instance_id() != fallen, 600):
		return "the defeated player was not taken back to the room of the station"
	await _frames(6)
	var back := _player()
	var station_at: Vector2 = point["position"]
	if back.global_position.distance_to(station_at) > _tile() * 2.0:
		return "the player should be at the station %s, it is at %s" % [station_at, back.global_position]
	if state.player_stats.hp != RpgUtil.max_hp(state.player_stats):
		return "the player should come back with full health"
	if state.gold != gold + 7 or state.abilities != held:
		return "what the player had since the last save was lost"
	if start.is_empty():
		return "the plan has no start room"
	return ""

func _end_room() -> String:
	var end_id := JsonUtil.to_str(_rooms().get("end", ""))
	var room := _room(end_id)
	if not await _enter(end_id):
		return "the last room could not be entered"
	var state := _state()
	var npc := _current().get_node_or_null("Entities/Hermit") as RpgSideNpc
	if npc == null or not room.has("npc"):
		print("[rpggen] INFO end_room: the last room has no NPC (the packs have none), step passes")
		return ""
	await _put(_cell(room["npc"]) + Vector2i(-1, 0))
	await _frames(4)
	_player().set_facing(1)
	await _tap("interact")
	if not await _wait_for(_box_open, 60):
		return "interacting with the hermit did not open the dialogue"
	for i in 40:
		if not _box_open():
			break
		await _press("confirm")
		await _frames(2)
	if _box_open():
		return "the hermit's dialogue did not finish"
	if state.get_flag(END_FLAG[0], END_FLAG[1], false) != true:
		return "the hermit's last line should set the end flag (%s.%s)" % END_FLAG
	# the credits open when the dialogue closes; they are closed again so the run can end
	var controller := _router().get_node_or_null("UiController") as RpgUiController
	if await _wait_for(func() -> bool: return controller.is_pause_open(), 60):
		for node in controller.find_children("*", "Control", true, false):
			if node is RpgCreditsMenu:
				node.queue_free()
		await _wait_for(func() -> bool: return not _tree().paused, 60)
	_tree().paused = false
	return ""
