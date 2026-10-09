class_name RpgSpawnPoint
extends Marker2D
## Where the player appears after entering a map through the SceneRouter.

@export var spawn_id: StringName = &"default"
@export var facing: String = "down"
## In a side-view room (T14.04) the player looks left or right: `facing` is "left" or "right" there
## and the top-down directions are ignored.
@export var side_view: bool = false

## The side to look to in a side-view room: -1 left, 1 right.
func side() -> int:
	return -1 if facing == "left" else 1

func _ready() -> void:
	add_to_group("spawn_points")
