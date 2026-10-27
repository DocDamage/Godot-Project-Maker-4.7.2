class_name RpgNewGameData
extends Resource

@export var start_map: String = "res://game/maps/starter_map.tscn"
@export var start_spawn: StringName = &"default"
@export var gold: int = 50
@export var items: Array[Dictionary] = []  # [{item_id, qty}]
## The skill points a level gained gives, in a game with skill trees (1.5.0).
@export var skill_points_per_level: int = 1
