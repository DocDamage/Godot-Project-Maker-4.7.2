class_name RpgNpc
extends RpgActor
## A talkative actor. Layer: npcs (4).

@export var entity_id: String = ""
@export var dialogue: RpgDialogueResource

## The schedule this NPC carries (T17.09): its child `Schedule`, or null. Most NPCs have none
## and stand where their map put them; one that has one is moved by it, and is not talked to
## while it is away on another map.
func schedule() -> RpgSchedule:
	return get_node_or_null(RpgSchedule.NODE_NAME) as RpgSchedule

## Turns toward the actor and starts the dialogue.
func interact(actor: Node = null) -> void:
	var plan := schedule()
	if plan != null and plan.away():
		return
	if actor is Node2D:
		var d := (actor as Node2D).global_position - global_position
		if d != Vector2.ZERO:
			set_facing(RpgAnimationDriver.dir_to_facing(d))
	if dialogue == null:
		return
	var box := RpgUtil.service(&"rpg_dialogue_box")
	if box == null:
		push_error("[RPG-DLG] no dialogue box to show %s" % name)
		return
	box.call("open", dialogue, actor)
