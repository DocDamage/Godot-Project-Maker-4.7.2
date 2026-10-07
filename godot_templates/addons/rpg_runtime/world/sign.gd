class_name RpgSign
extends StaticBody2D
## A readable sign: interacting opens its dialogue.

@export var dialogue: RpgDialogueResource

func interact(actor: Node = null) -> void:
	if dialogue == null:
		return
	var box := RpgUtil.service(&"rpg_dialogue_box")
	if box == null:
		push_error("[RPG-DLG] no dialogue box to show the sign")
		return
	box.call("open", dialogue, actor)
