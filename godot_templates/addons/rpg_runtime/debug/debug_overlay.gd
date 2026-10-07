class_name RpgDebugOverlay
extends CanvasLayer
## F3 toggles a status panel and a one-line console. Exists only in debug builds with the
## debug_tools feature on (boot decides).
##
## Commands: tp <spawn_id> | give <item_id> [qty] | gold <n> | flag <entity>.<key>=<v> | heal |
##           encounter | collision | help

const HELP := "tp <spawn_id> | give <item_id> [qty] | gold <n> | flag <entity>.<key>=<v> | heal | encounter | collision | help"

var _label: Label
var _input: LineEdit
var _output: Label
var _root: PanelContainer

func _ready() -> void:
	layer = 90
	process_mode = Node.PROCESS_MODE_ALWAYS
	_root = PanelContainer.new()
	_root.position = Vector2(4, 4)
	var box := VBoxContainer.new()
	_root.add_child(box)
	_label = Label.new()
	box.add_child(_label)
	_output = Label.new()
	box.add_child(_output)
	_input = LineEdit.new()
	_input.placeholder_text = "help"
	_input.custom_minimum_size = Vector2(260, 0)
	_input.text_submitted.connect(_on_submit)
	box.add_child(_input)
	add_child(_root)
	_root.visible = false

func _unhandled_input(event: InputEvent) -> void:
	if InputMap.has_action("debug_toggle") and event.is_action_pressed("debug_toggle"):
		_root.visible = not _root.visible
		if _root.visible:
			_input.grab_focus()
		get_viewport().set_input_as_handled()

func _process(_delta: float) -> void:
	if _root == null or not _root.visible:
		return
	var state := RpgUtil.state()
	var router := RpgUtil.router()
	var lines: PackedStringArray = ["FPS %d" % Engine.get_frames_per_second()]
	if router != null and router.get("current_map") != null:
		var map := router.get("current_map") as RpgMapRoot
		lines.append("map %s" % map.map_id)
		var player := map.get_player()
		if player != null:
			lines.append("pos %d,%d" % [player.global_position.x, player.global_position.y])
			lines.append("tile %s" % str(_tile_under(map, player)))
	if state != null:
		lines.append("flags %d" % state.flag_count())
	_label.text = "\n".join(lines)

func _tile_under(map: RpgMapRoot, player: Node2D) -> Variant:
	var ground := map.get_node_or_null("Ground") as TileMapLayer
	if ground == null:
		return "-"
	return ground.local_to_map(ground.to_local(player.global_position))

func _on_submit(text: String) -> void:
	_output.text = run_command(text)
	_input.clear()

## Runs one console command and returns its output line.
func run_command(text: String) -> String:
	var parts := text.strip_edges().split(" ", false)
	if parts.is_empty():
		return ""
	var state := RpgUtil.state()
	var router := RpgUtil.router()
	if state == null:
		return "GameState is not available"
	match parts[0]:
		"help":
			return HELP
		"gold":
			if parts.size() < 2 or not parts[1].is_valid_int():
				return "usage: gold <n>"
			state.gold = int(parts[1])
			return "gold = %d" % state.gold
		"give":
			if parts.size() < 2:
				return "usage: give <item_id> [qty]"
			var qty := int(parts[2]) if parts.size() > 2 else 1
			var added: int = state.inventory.add(StringName(parts[1]), qty)
			return "gave %d x %s" % [added, parts[1]]
		"flag":
			if parts.size() < 2 or not parts[1].contains(".") or not parts[1].contains("="):
				return "usage: flag <entity>.<key>=<v>"
			RpgDialogueRunner.execute_event("set_flag:" + parts[1])
			return "ok"
		"heal":
			state.player_stats.hp = state.player_stats.max_hp
			return "healed"
		"tp":
			if parts.size() < 2 or router == null or router.get("current_map") == null:
				return "usage: tp <spawn_id> (inside a map)"
			var map := router.get("current_map") as RpgMapRoot
			var spawn := map.get_spawn(StringName(parts[1]))
			var player := map.get_player()
			if spawn == null or player == null or spawn.spawn_id != StringName(parts[1]):
				return "unknown spawn %s" % parts[1]
			player.global_position = spawn.global_position
			return "teleported"
		"encounter":
			return _start_test_encounter(router)
		"collision":
			var tree := get_tree()
			tree.debug_collisions_hint = not tree.debug_collisions_hint
			return "collision shapes %s (affects shapes created from now on)" % ("on" if tree.debug_collisions_hint else "off")
	return "unknown command (help)"

func _start_test_encounter(router: Node) -> String:
	if router == null or router.get("combat") == null:
		return "no combat mode in this game"
	var enemy: RpgEnemyDefinition = null
	for path in _enemy_paths():
		enemy = load(path) as RpgEnemyDefinition
		if enemy != null:
			break
	if enemy == null:
		return "no enemy definition under res://game/data/enemies/"
	var data := RpgEncounterData.new()
	data.enemies = [enemy]
	data.entity_id = "debug_encounter"
	router.get("combat").call("start_encounter", data)
	return "encounter started"

func _enemy_paths() -> Array[String]:
	var out: Array[String] = []
	var dir := DirAccess.open("res://game/data/enemies")
	if dir == null:
		return out
	var files := dir.get_files()
	files.sort()
	for f in files:
		if f.trim_suffix(".remap").ends_with(".tres"):
			out.append("res://game/data/enemies/" + f.trim_suffix(".remap"))
	return out
