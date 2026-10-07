class_name RpgEncounterResult
extends Resource

enum Outcome { VICTORY, DEFEAT, ESCAPED }

@export var outcome: Outcome
@export var xp: int
@export var gold: int
@export var items: Array[Dictionary]
@export var entity_id: String
