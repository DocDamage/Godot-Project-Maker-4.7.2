class_name RpgDialogueLine
extends Resource

@export var id: StringName = &""  # optional label for jumps
@export var speaker: String = ""  # tr key or literal
@export var portrait: Texture2D
@export_multiline var text: String = ""  # tr key or literal
@export var choices: Array[RpgDialogueChoice] = []
@export var condition: String = ""  # line is skipped if condition is false
@export var events: PackedStringArray = []  # executed when the line is shown
@export var next: StringName = &""  # jump target (empty = next line)
