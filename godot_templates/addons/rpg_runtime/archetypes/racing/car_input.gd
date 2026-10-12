class_name RpgCarInput
extends Node
## Only on the player's car: turns the input actions into what the car wants. The car calls
## poll() at the start of its own physics step.
##
## Actions: `accelerate`, `brake` (which reverses a car that stands), move_left / move_right
## steer, `boost`, `fire` (the weapon the car carries). With *absolute* steering the stick (or the arrows) point where the car is to
## head, and the car turns that way by itself.

static func _pressed(action: StringName) -> bool:
	return InputMap.has_action(action) and Input.is_action_just_pressed(action)

static func _strength(action: StringName) -> float:
	return Input.get_action_strength(action) if InputMap.has_action(action) else 0.0

static func _axis(negative: StringName, positive: StringName) -> float:
	if not InputMap.has_action(negative) or not InputMap.has_action(positive):
		return 0.0
	return Input.get_axis(negative, positive)

func poll(car: CharacterBody2D) -> void:
	# by name: this script does not name the car's class, which names this one
	car.set(&"throttle", _strength(&"accelerate") - _strength(&"brake"))
	car.set(&"steer", _axis(&"move_left", &"move_right"))
	car.set(&"stick", Vector2(_axis(&"move_left", &"move_right"), _axis(&"move_up", &"move_down")))
	if _pressed(&"boost"):
		car.call(&"press_boost")
	if _pressed(&"fire"):
		car.call(&"press_fire")
