class_name RpgTriggerArea
extends Area2D
## Starts a sequence (`sequence`, kept in the map, or game/data/sequences/<sequence_id>.tres) when
## the player walks in, or, with `on_interact`, when the player presses interact facing it. Give it
## a CollisionShape2D or CollisionPolygon2D child for its shape.
##
## With `once` it fires a single time per game: the flag `<entity_id>.triggered` is set when it
## fires and saved like any other flag. `condition` (a dialogue condition) must hold for it to fire.
## Layers: walk-in areas watch the player (2); interact areas sit on interactables (5) so the
## player's interaction area finds them.

@export var sequence_id: StringName = &""
## A sequence kept in the map itself; when set it is used instead of `sequence_id`.
@export var sequence: RpgSequence
## Needed for `once` (the flag is stored under it); unique like every entity id.
@export var entity_id: String = ""
@export var on_interact: bool = false
@export var once: bool = true
@export var condition: String = ""

func _ready() -> void:
	monitorable = on_interact
	monitoring = not on_interact
	collision_layer = 0
	collision_mask = 0
	if on_interact:
		set_collision_layer_value(5, true)
	else:
		set_collision_mask_value(2, true)
		body_entered.connect(_on_body_entered)

## False when it has fired before (with `once`) or its condition does not hold.
func can_fire() -> bool:
	if sequence == null and sequence_id == &"":
		return false
	var state := RpgUtil.state()
	if once and entity_id != "" and state != null and RpgUtil.to_bool(state.get_flag(entity_id, "triggered", false)):
		return false
	return condition == "" or RpgCondition.evaluate(condition)

## Starts the sequence when it may fire. Returns true when it did.
func fire() -> bool:
	if not can_fire() or RpgSequenceRunner.running():
		return false
	var runner := RpgSequenceRunner.instance()
	if runner == null:
		push_error("[RPG-SEQ] trigger %s: no sequence runner" % name)
		return false
	var to_run := sequence if sequence != null else RpgSequence.load_sequence(sequence_id)
	if to_run == null:
		push_error("[RPG-SEQ] trigger %s: no sequence '%s'" % [name, sequence_id])
		return false
	var state := RpgUtil.state()
	if once and entity_id != "" and state != null:
		state.set_flag(entity_id, "triggered", true)
	return runner.run(to_run)

func _on_body_entered(body: Node) -> void:
	if body.is_in_group("player"):
		fire()

## The player's interaction area calls this for an `on_interact` trigger.
func interact(_actor: Node = null) -> void:
	if on_interact:
		fire()
