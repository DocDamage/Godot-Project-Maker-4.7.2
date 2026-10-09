@tool
class_name RpgDialogueChoice
extends Resource

@export var text: String
@export var next: StringName  # line id
@export var condition: String = ""
