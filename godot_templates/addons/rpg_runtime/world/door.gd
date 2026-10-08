class_name RpgDoor
extends Area2D
## A trigger that moves the player to another map. Walk-in by default; with `require_interact`
## the player has to stand in the area and press the interact action.

@export_file("*.tscn") var target_map: String = ""
@export var target_spawn: StringName = &"default"
@export var require_interact: bool = false  # false: walk-in; true: press interact

signal used

var _player_inside := false

func _ready() -> void:
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)

func _on_body_entered(body: Node) -> void:
	if not body.is_in_group("player"):
		return
	_player_inside = true
	if not require_interact:
		use()

func _on_body_exited(body: Node) -> void:
	if body.is_in_group("player"):
		_player_inside = false

func _unhandled_input(event: InputEvent) -> void:
	if require_interact and _player_inside and event.is_action_pressed("interact"):
		get_viewport().set_input_as_handled()
		use()

## Sends the player to `target_map`. Returns false when the door has no target.
func use() -> bool:
	if target_map == "":
		push_warning("[RPG-WORLD] door %s has no target_map" % name)
		return false
	used.emit()
	RpgUtil.emit(&"door_used", [str(name)])
	var router := get_node_or_null("/root/SceneRouter") as RpgSceneRouter
	if router == null:
		push_error("[RPG-WORLD] SceneRouter autoload is missing")
		return false
	router.go_to(target_map, target_spawn)
	return true
