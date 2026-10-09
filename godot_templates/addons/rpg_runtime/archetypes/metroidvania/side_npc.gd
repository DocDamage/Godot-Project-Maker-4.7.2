class_name RpgSideNpc
extends RpgPlatformActor
## A talkative character of a side-view room. It stands on the floor (the platform actor's
## gravity), looks left or right, and turns to whoever talks to it. Layer: npcs (4).

@export var entity_id: String = ""
@export var dialogue: RpgDialogueResource
## The side it looks to until somebody talks to it: -1 left, 1 right.
@export var start_facing: int = 1

func _ready() -> void:
	facing = -1 if start_facing < 0 else 1
	super._ready()

## Turns toward the actor and starts the dialogue.
func interact(actor: Node = null) -> void:
	if actor is Node2D:
		var dx := RpgUtil.world_position(actor as Node2D).x - RpgUtil.world_position(self).x
		if absf(dx) > 0.5:
			set_facing(1 if dx > 0.0 else -1)
			_animate()
	if dialogue == null:
		return
	var box := RpgUtil.service(&"rpg_dialogue_box")
	if box == null:
		push_error("[RPG-DLG] no dialogue box to show %s" % name)
		return
	box.call("open", dialogue, actor)
