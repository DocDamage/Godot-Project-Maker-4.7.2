class_name RpgShmupShipInput
extends Node
## Only on the ship: turns the input actions into what the ship wants to do. The ship calls
## poll() at the start of its own step.
##
## Actions: move_left / move_right / move_up / move_down fly, `shoot`, `bomb`, `focus`.

## Turned off by a test or a smoke step that flies the ship itself.
var enabled := true
## With auto-fire, holding `shoot` keeps firing; without, every press is one shot.
@export var auto_fire: bool = true

static func _pressed(action: StringName) -> bool:
	return InputMap.has_action(action) and Input.is_action_just_pressed(action)

static func _held(action: StringName) -> bool:
	return InputMap.has_action(action) and Input.is_action_pressed(action)

static func _axis(negative: StringName, positive: StringName) -> float:
	if not InputMap.has_action(negative) or not InputMap.has_action(positive):
		return 0.0
	return Input.get_axis(negative, positive)

func poll(ship: Node) -> void:
	if not enabled:
		return
	ship.set(&"move", Vector2(_axis(&"move_left", &"move_right"), _axis(&"move_up", &"move_down")))
	ship.set(&"focusing", _held(&"focus"))
	if auto_fire:
		ship.set(&"shooting", _held(&"shoot"))
	else:
		ship.set(&"shooting", false)
		if _pressed(&"shoot"):
			ship.call(&"press_shoot")
	if _pressed(&"bomb"):
		ship.call(&"press_bomb")
