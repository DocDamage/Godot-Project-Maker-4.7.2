class_name RpgBattleCommand
extends Resource
## One thing a battler can choose to do. Concrete commands live in commands/; their .tres
## instances are seeded into game/data/battle_commands/ so the user can retune them.

## `targets` values.
const TARGET_SELF := 0
const TARGET_ONE_ENEMY := 1
const TARGET_ONE_ALLY := 2
const TARGET_ALL_ENEMIES := 3

@export var id: StringName
@export var label: String  # a tr() key
@export var targets: int = TARGET_ONE_ENEMY
@export var priority: int = 0  # higher acts first within a round (Defend uses 10)

func can_use(_user: RpgBattleActor, _battle: RpgBattleController) -> bool:
	return true

## Returns log entries: [{type: "damage"|"heal"|"text"|"status", target, amount, text}].
func execute(_user: RpgBattleActor, _targets: Array[RpgBattleActor], _battle: RpgBattleController) -> Array[Dictionary]:
	return []

## A log entry with the optional fields filled in.
static func entry(type: String, text: String, target: RpgBattleActor = null, amount: int = 0, crit: bool = false) -> Dictionary:
	return {"type": type, "text": text, "target": target, "amount": amount, "crit": crit}
