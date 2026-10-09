class_name RpgDoor
extends Area2D
## A trigger that moves the player to another map. Walk-in by default; with `require_interact`
## the player has to stand in the area and press the interact action. With `key_item` it is locked
## until the player comes holding that item (the flag `<entity_id>.unlocked` remembers it).

@export_file("*.tscn") var target_map: String = ""
@export var target_spawn: StringName = &"default"
@export var require_interact: bool = false  # false: walk-in; true: press interact
## Locked until the player has this item; empty = never locked.
@export var key_item: StringName = &""
@export var consume_key: bool = true
## Needed for a lock that stays open (the flag is stored under it).
@export var entity_id: String = ""

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

func is_locked() -> bool:
	if key_item == &"":
		return false
	var state := RpgUtil.state()
	return state == null or entity_id == "" or not RpgUtil.to_bool(state.get_flag(entity_id, "unlocked", false))

## Unlocks it with the key when the player holds it; a message either way. False while locked.
func try_unlock() -> bool:
	if not is_locked():
		return true
	var state := RpgUtil.state()
	if state == null:
		return false
	var key_name := RpgGate.item_name(state, key_item)
	if not state.inventory.has(key_item):
		RpgUtil.notify(RpgStrings.format("UI_LOCKED_NEED", key_name))
		return false
	if consume_key:
		state.inventory.remove(key_item, 1)
	if entity_id != "":
		state.set_flag(entity_id, "unlocked", true)
	RpgUtil.notify(RpgStrings.format("UI_UNLOCKED", key_name))
	return true

## Sends the player to `target_map`. Returns false when the door has no target or stays locked.
func use() -> bool:
	if target_map == "":
		push_warning("[RPG-WORLD] door %s has no target_map" % name)
		return false
	if not try_unlock():
		return false
	used.emit()
	RpgUtil.emit(&"door_used", [str(name)])
	var router := get_node_or_null("/root/SceneRouter") as RpgSceneRouter
	if router == null:
		push_error("[RPG-WORLD] SceneRouter autoload is missing")
		return false
	router.go_to(target_map, target_spawn)
	return true
