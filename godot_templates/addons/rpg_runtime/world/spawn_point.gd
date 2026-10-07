class_name RpgSpawnPoint
extends Marker2D
## Where the player appears after entering a map through the SceneRouter.

@export var spawn_id: StringName = &"default"
@export var facing: String = "down"

func _ready() -> void:
	add_to_group("spawn_points")
