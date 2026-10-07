class_name RpgNewGameData
extends Resource

@export var start_map: String = "res://game/maps/starter_map.tscn"
@export var start_spawn: StringName = &"default"
@export var gold: int = 50
@export var items: Array[Dictionary] = []  # [{item_id, qty}]
