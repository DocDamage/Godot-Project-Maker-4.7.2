extends Node
## Entry point of a generated game: sends the SceneRouter to the first scene. M6 points it at the
## title screen.

@export var first_scene: String = ""

func _ready() -> void:
	if first_scene == "":
		push_error("[RPG-BOOT] first_scene is not set")
		return
	var router := get_node_or_null("/root/SceneRouter")
	if router != null:
		router.go_to.call_deferred(first_scene)
	else:
		get_tree().change_scene_to_file.call_deferred(first_scene)
