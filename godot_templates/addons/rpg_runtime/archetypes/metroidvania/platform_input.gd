class_name RpgPlatformInput
extends Node
## Only on the player: turns the input actions into the platform actor's intentions. The actor
## calls poll() at the start of its own physics step, so a press acts in the same frame.
##
## Actions: move_left / move_right run, move_up / move_down climb, `down` (or move_down) with
## `jump` drops through a one-way platform, `jump`, `dash`, `attack`, `interact`.

## Turned off by a test or a smoke step that drives the actor itself.
var enabled := true

static func _pressed(action: StringName) -> bool:
	return InputMap.has_action(action) and Input.is_action_just_pressed(action)

static func _held(action: StringName) -> bool:
	return InputMap.has_action(action) and Input.is_action_pressed(action)

static func _axis(negative: StringName, positive: StringName) -> float:
	if not InputMap.has_action(negative) or not InputMap.has_action(positive):
		return 0.0
	return Input.get_axis(negative, positive)

func poll(actor: RpgPlatformActor) -> void:
	if not enabled:
		return
	if not actor.input_enabled or RpgSequenceRunner.running():
		actor.move_x = 0.0
		actor.move_y = 0.0
		actor.jump_held = false
		return
	actor.move_x = _axis(&"move_left", &"move_right")
	var vertical := _axis(&"move_up", &"move_down")
	if _held(&"down"):
		vertical = 1.0
	actor.move_y = vertical
	if _pressed(&"jump"):
		actor.press_jump()
	actor.jump_held = _held(&"jump")
	if _pressed(&"dash"):
		actor.press_dash()
	# The player's own actions, by name. This script does not name the player's class, which
	# names this one: with that pair of references Godot reported the scripts as still in use
	# when a validation run quit (VAL-013).
	if _pressed(&"attack") and actor.has_method(&"press_attack"):
		actor.call(&"press_attack")
	if _pressed(&"interact") and actor.has_method(&"try_interact"):
		actor.call(&"try_interact")
