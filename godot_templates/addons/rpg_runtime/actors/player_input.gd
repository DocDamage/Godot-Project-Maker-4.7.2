class_name RpgPlayerInput
extends Node
## Only on the player: turns the input actions into movement and interaction.

var actor: RpgActor
var interaction: RpgInteraction

func _ready() -> void:
	var node := get_parent()
	while node != null and not (node is RpgActor):
		node = node.get_parent()
	actor = node as RpgActor
	if actor == null:
		push_error("[RPG-ACTOR] PlayerInput has no RpgActor ancestor")
		return
	interaction = actor.get_node_or_null("Interaction") as RpgInteraction

func _physics_process(_delta: float) -> void:
	if actor == null:
		return
	if not actor.input_enabled:
		actor.move_dir(Vector2.ZERO)
		return
	actor.move_dir(Input.get_vector("move_left", "move_right", "move_up", "move_down"))
	if Input.is_action_just_pressed("interact") and interaction != null:
		interaction.try_interact()
