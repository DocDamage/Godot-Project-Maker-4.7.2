class_name RpgPlayerInput
extends Node
## Only on the player: turns the input actions into movement and interaction.

var actor: RpgActor
var interaction: RpgInteraction
## The map the pad was last asked about (its instance id) and its diamond: zero on squares.
var _map_id := 0
var _footprint := Vector2i.ZERO

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
	if not actor.input_enabled or RpgSequenceRunner.running():
		actor.move_dir(Vector2.ZERO)
		return
	if actor.move_locked:
		return
	actor.move_dir(pad(Input.get_vector("move_left", "move_right", "move_up", "move_down")))
	if Input.is_action_just_pressed("interact") and interaction != null:
		interaction.try_interact()

## Where the pad's `input` moves the player. On a map of squares it is the input itself. On an
## isometric map (T17.14) it is too with the default controls (`iso_controls: screen`: up is up
## on the screen), and with `grid` controls the four directions follow the diamond's axes.
func pad(input: Vector2) -> Vector2:
	if input == Vector2.ZERO:
		return input
	var map := actor.map_node()
	var id := map.get_instance_id() if map != null else 0
	if id != _map_id:
		_map_id = id
		_footprint = RpgIso.footprint_of(map)
	if _footprint == Vector2i.ZERO:
		return input
	return RpgIso.pad_vector(input, RpgIso.controls(), _footprint)
