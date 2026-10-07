class_name RpgMovement
extends Node
## Moves the owning RpgActor from `desired` (a direction) plus a decaying knockback velocity.

@export var speed: float = 80.0
var desired := Vector2.ZERO
var external_velocity := Vector2.ZERO  # knockback (ARPG); decays: *= 0.85 per physics frame

var actor: RpgActor

func _ready() -> void:
	actor = _find_actor()
	if actor == null:
		push_error("[RPG-ACTOR] Movement has no RpgActor ancestor")

func _find_actor() -> RpgActor:
	var node := get_parent()
	while node != null:
		if node is RpgActor:
			return node
		node = node.get_parent()
	return null

func _physics_process(_delta: float) -> void:
	if actor == null:
		return
	actor.velocity = desired * speed + external_velocity
	actor.move_and_slide()
	external_velocity *= 0.85
	if external_velocity.length() < 0.5:
		external_velocity = Vector2.ZERO
