class_name RpgSideInteractable
extends Area2D
## Something in a side-view room the player uses by standing beside it and pressing interact: the
## base of the save station, the ability pickup's marker and the end-room trigger. Layer:
## interactables (5). Override _use(actor).

signal used(actor: Node)

@export var entity_id: String = ""
## The tile size of the room (set by the recipe): how far "beside" reaches.
@export var tile_size: float = 16.0

## True when `actor` stands beside this (within a tile up or down): not from a platform above.
func can_interact(actor: Node) -> bool:
	return RpgUtil.beside(self, actor, tile_size)

func interact(actor: Node = null) -> void:
	used.emit(actor)
	_use(actor)

## What using it does.
func _use(_actor: Node) -> void:
	pass
