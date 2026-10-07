class_name RpgEnemyDefinition
extends RpgActorDefinition

@export var xp_reward: int = 5
@export var gold_reward: int = 3
@export var loot: RpgLootTable
@export var behavior: Dictionary = {}  # ARPG AI params (M9); turn-based AI weights (M7)
