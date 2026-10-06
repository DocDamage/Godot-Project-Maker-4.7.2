extends Node
## Entry point of a generated game: switches to the first scene. M6 points it at the title screen.

@export var first_scene: String = ""

func _ready() -> void:
	if first_scene == "":
		push_error("[RPG-BOOT] first_scene is not set")
		return
	get_tree().change_scene_to_file.call_deferred(first_scene)
