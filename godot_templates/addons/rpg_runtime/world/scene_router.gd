extends Node
## Autoload "SceneRouter": changes maps with a fade, puts the player on a spawn point, keeps a small
## scene stack for battles, and hosts the persistent services boot creates (audio, combat mode).

signal map_changed(map_id: StringName)

const FADE_SECONDS := 0.2
const MAX_STACK := 4

var current_map: RpgMapRoot
var combat: RpgCombatMode = null  # the archetype's combat mode, created by boot
var audio: Node = null  # RpgAudio, created by boot
var ignored_calls := 0  # go_to calls that arrived while a change was running
var _busy := false
var _stack: Array[Dictionary] = []  # [{map, position, facing}]
var _fade_layer: CanvasLayer
var _fade_rect: ColorRect

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_fade_layer = CanvasLayer.new()
	_fade_layer.layer = 100
	_fade_rect = ColorRect.new()
	_fade_rect.color = Color.BLACK
	_fade_rect.modulate.a = 0.0
	_fade_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_fade_rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_fade_layer.add_child(_fade_rect)
	add_child(_fade_layer)

func is_busy() -> bool:
	return _busy

func stack_depth() -> int:
	return _stack.size()

## Fades out, loads `map_path`, places the player on the spawn point and fades in again.
func go_to(map_path: String, spawn_id: StringName = &"default") -> void:
	await _transition(map_path, spawn_id, false, Vector2.ZERO, "")

## After loading a save: goes to GameState.current_map and puts the player at the saved position.
func reload_from_state() -> void:
	var state := RpgUtil.state()
	if state == null:
		push_error("[RPG-WORLD] GameState is not available to reload from")
		return
	await _transition(str(state.current_map), state.current_spawn, true, state.player_position, str(state.player_facing))

## Remembers the current map, player position and facing, then switches to `path` without
## spawning. `payload` is handed to the new scene's `setup(payload)` when it has one. The stack
## depth is limited to 4.
func push_scene(path: String, payload: Resource = null) -> void:
	if _busy:
		ignored_calls += 1
		return
	if _stack.size() >= MAX_STACK:
		push_error("[RPG-WORLD] scene stack is full (%d)" % MAX_STACK)
		return
	var state := RpgUtil.state()
	var entry := {"map": "", "position": Vector2.ZERO, "facing": "down"}
	if current_map != null:
		entry["map"] = current_map.scene_file_path
		var player := current_map.get_player()
		if player != null:
			entry["position"] = player.global_position
			entry["facing"] = str(player.get("facing")) if "facing" in player else "down"
	if state != null:
		state.current_map = entry["map"]
		state.player_position = entry["position"]
		state.player_facing = entry["facing"]
		if payload is RpgEncounterData:
			state.pending_encounter = payload
	_stack.append(entry)
	_busy = true
	await _fade(1.0)
	var tree := get_tree()
	var err := tree.change_scene_to_file(path)
	if err != OK:
		push_error("[RPG-WORLD] cannot load scene %s (error %d)" % [path, err])
		_stack.pop_back()
		await _fade(0.0)
		_busy = false
		return
	await tree.scene_changed
	current_map = tree.current_scene as RpgMapRoot
	if tree.current_scene != null and tree.current_scene.has_method("setup"):
		tree.current_scene.call("setup", payload)
	await _fade(0.0)
	_busy = false

## Returns to the map saved by push_scene, puts the player at the saved position (not a spawn)
## and emits Events.encounter_finished(result) after the fade-in.
func pop_scene(result: Resource = null) -> void:
	if _busy:
		ignored_calls += 1
		return
	if _stack.is_empty():
		push_error("[RPG-WORLD] pop_scene with an empty stack")
		return
	var entry: Dictionary = _stack.pop_back()
	await _transition(str(entry["map"]), &"default", true, entry["position"], str(entry["facing"]))
	var state := RpgUtil.state()
	if state != null:
		state.pending_encounter = null
	RpgUtil.emit(&"encounter_finished", [result])

func _transition(map_path: String, spawn_id: StringName, at_position: bool, position: Vector2, facing: String) -> void:
	if _busy:
		ignored_calls += 1
		return
	_busy = true
	await _fade(1.0)
	var tree := get_tree()
	var err := tree.change_scene_to_file(map_path)
	if err != OK:
		push_error("[RPG-WORLD] cannot load map %s (error %d)" % [map_path, err])
		await _fade(0.0)
		_busy = false
		return
	await tree.scene_changed
	current_map = tree.current_scene as RpgMapRoot
	if current_map != null:
		if at_position:
			_place_player_at(current_map, position, facing)
		else:
			_place_player(current_map, spawn_id)
		_remember_map(map_path, spawn_id)
	await _fade(0.0)
	_busy = false
	var id: StringName = current_map.map_id if current_map != null else &""
	map_changed.emit(id)
	if current_map != null:
		RpgUtil.emit(&"map_entered", [id])
		_apply_map_music()

## Starts the music the map asks for (`music_asset_id`) unless that track already plays. A map
## without one keeps the current track.
func _apply_map_music() -> void:
	if current_map == null or audio == null:
		return
	var wanted := str(current_map.music_asset_id)
	if wanted != "" and wanted != str(audio.get("current_music_id")):
		audio.call("play_music", wanted)

func _remember_map(map_path: String, spawn_id: StringName) -> void:
	var state := RpgUtil.state()
	if state != null:
		state.current_map = map_path
		state.current_spawn = spawn_id

func _fade(alpha: float) -> void:
	if _fade_rect == null:
		return
	var tween := create_tween()
	tween.tween_property(_fade_rect, "modulate:a", alpha, FADE_SECONDS)
	await tween.finished

## The spawn to use: this id, else "default", else the first one, else null (see RpgMapRoot).
static func resolve_spawn(map: RpgMapRoot, spawn_id: StringName) -> RpgSpawnPoint:
	return map.get_spawn(spawn_id)

func _place_player(map: RpgMapRoot, spawn_id: StringName) -> void:
	var player := map.get_player()
	var spawn := resolve_spawn(map, spawn_id)
	var target := Vector2.ZERO
	if spawn == null:
		push_error("[RPG-WORLD] no spawn in map %s" % map.name)
	else:
		target = spawn.global_position
	if player == null:
		return
	player.global_position = target
	if spawn != null and "facing" in player:
		player.set("facing", spawn.facing)
	_apply_camera_limits(map, player)

func _place_player_at(map: RpgMapRoot, position: Vector2, facing: String) -> void:
	var player := map.get_player()
	if player == null:
		return
	player.global_position = position
	if facing != "" and "facing" in player:
		player.set("facing", facing)
	_apply_camera_limits(map, player)

func _apply_camera_limits(map: RpgMapRoot, player: Node2D) -> void:
	var camera := player.get_node_or_null("Camera") as Camera2D
	if camera == null:
		return
	var rect := map.used_rect_px()
	if rect.size != Vector2.ZERO:
		var origin := map.global_position
		camera.limit_left = int(origin.x + rect.position.x)
		camera.limit_top = int(origin.y + rect.position.y)
		camera.limit_right = int(origin.x + rect.end.x)
		camera.limit_bottom = int(origin.y + rect.end.y)
	camera.reset_smoothing()
