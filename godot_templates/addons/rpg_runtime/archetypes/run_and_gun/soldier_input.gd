class_name RpgSoldierInput
extends Node
## Only on the soldier: turns the input actions into what the soldier wants. The soldier calls
## poll() at the start of its own physics step, so a press acts in the same frame.
##
## Actions: move_left / move_right run, move_up / move_down aim (and climb a ladder), `jump`,
## `shoot`, `grenade`, `aim_lock`. Down with jump drops through a one-way platform.

## Turned off by a test or a smoke step that moves the soldier itself.
var enabled := true

static func _pressed(action: StringName) -> bool:
	return InputMap.has_action(action) and Input.is_action_just_pressed(action)

static func _held(action: StringName) -> bool:
	return InputMap.has_action(action) and Input.is_action_pressed(action)

static func _axis(negative: StringName, positive: StringName) -> float:
	if not InputMap.has_action(negative) or not InputMap.has_action(positive):
		return 0.0
	return Input.get_axis(negative, positive)

func poll(soldier: RpgPlatformActor) -> void:
	if not enabled:
		return
	soldier.move_x = _axis(&"move_left", &"move_right")
	soldier.move_y = _axis(&"move_up", &"move_down")
	if _pressed(&"jump"):
		soldier.press_jump()
	soldier.jump_held = _held(&"jump")
	# by name: this script does not name the soldier's class, which names this one
	soldier.set(&"shooting", _held(&"shoot"))
	soldier.set(&"aim_locked", _held(&"aim_lock"))
	if _pressed(&"grenade"):
		soldier.call(&"press_grenade")
