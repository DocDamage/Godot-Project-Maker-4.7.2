extends Node
## Autoload "SceneRouter": changes maps with a fade and puts the player on a spawn point.

signal map_changed(map_id: StringName)

const FADE_SECONDS := 0.2

var current_map: RpgMapRoot
var ignored_calls := 0  # go_to calls that arrived while a change was running
var _busy := false
var _fade_layer: CanvasLayer
var _fade_rect: ColorRect

func _ready() -> void:
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

## Fades out, loads `map_path`, places the player on the spawn point and fades in again.
func go_to(map_path: String, spawn_id: StringName = &"default") -> void:
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
		_place_player(current_map, spawn_id)
	await _fade(0.0)
	_busy = false
	map_changed.emit(current_map.map_id if current_map != null else &"")

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
