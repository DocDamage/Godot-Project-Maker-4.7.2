class_name RpgWorldObject
extends Node2D
## Root script of every generated world object (props, obstacles, buildings, chests, signs).
## The node origin is the object's feet/base, so Y-sorting by position.y is correct.

@export var asset_id: String = ""
## Empty for non-persistent props.
@export var entity_id: String = ""
@export var blocks_movement: bool = true
