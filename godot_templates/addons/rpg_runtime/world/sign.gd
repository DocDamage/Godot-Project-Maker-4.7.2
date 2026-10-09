class_name RpgSign
extends StaticBody2D
## A readable sign: interacting opens its dialogue.

@export var dialogue: RpgDialogueResource
## In a side-view room (T14.04): read from beside it, from either side, not from above.
@export var side_view: bool = false
@export var tile_size: float = 16.0

## Asked by the side-view player before it interacts.
func can_interact(actor: Node) -> bool:
	return not side_view or RpgUtil.beside(self, actor, tile_size)

func interact(actor: Node = null) -> void:
	if dialogue == null:
		return
	var box := RpgUtil.service(&"rpg_dialogue_box")
	if box == null:
		push_error("[RPG-DLG] no dialogue box to show the sign")
		return
	box.call("open", dialogue, actor)
