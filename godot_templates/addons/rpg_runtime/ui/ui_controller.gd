class_name RpgUiController
extends Node
## Created by boot under SceneRouter. Opens the pause menu on `menu` during gameplay.

var _layer: CanvasLayer = null
var _menu: Control = null
var _closed_frame := -1

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS

func is_pause_open() -> bool:
	return _menu != null and is_instance_valid(_menu)

func _in_gameplay() -> bool:
	var router := RpgUtil.router()
	if router == null or router.get("current_map") == null or router.is_busy():
		return false
	var box := RpgUtil.service(&"rpg_dialogue_box")
	if box != null and box.call("is_open"):
		return false
	var combat: Variant = router.get("combat")
	if combat != null and combat.is_in_combat():
		return false
	return true

func _unhandled_input(event: InputEvent) -> void:
	if not event.is_action_pressed("menu"):
		return
	if is_pause_open() or _closed_frame == Engine.get_process_frames() or not _in_gameplay():
		return
	get_viewport().set_input_as_handled()
	open_pause()

## Pauses the tree and shows the pause menu. Returns the menu (null when the scene is missing).
func open_pause() -> Control:
	var path := RpgMenuUtil.scene_path("pause_menu")
	if not ResourceLoader.exists(path):
		push_error("[RPG-UI] %s is missing" % path)
		return null
	if _layer == null:
		_layer = CanvasLayer.new()
		_layer.layer = 60
		_layer.process_mode = Node.PROCESS_MODE_ALWAYS
		add_child(_layer)
	_menu = (load(path) as PackedScene).instantiate() as Control
	_layer.add_child(_menu)
	_menu.tree_exited.connect(_on_closed)
	get_tree().paused = true
	RpgUtil.emit(&"game_paused", [true])
	return _menu

func _on_closed() -> void:
	_menu = null
	_closed_frame = Engine.get_process_frames()
