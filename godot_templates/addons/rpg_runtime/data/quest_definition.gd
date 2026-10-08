class_name RpgQuestDefinition
extends Resource
## A quest: stages in order, each finished by a condition, and what completing it gives. Files live
## in game/data/quests/<id>.tres. GameState.quests[id] holds the id of the current stage while the
## quest is active and "done" afterwards; the dialogue events quest_start, quest_stage and
## quest_complete move it, and a stage whose `complete_when` holds moves on by itself.

@export var id: StringName
@export var title: String  # a tr() key
## [{id, description (a tr() key), complete_when (a condition; "" = only an event finishes it)}].
## Stage ids must not be "done".
@export var stages: Array[Dictionary] = []
## {gold: int, experience: int, items: [{item_id, qty}]}
@export var rewards: Dictionary = {}

func stage_ids() -> Array[StringName]:
	var out: Array[StringName] = []
	for stage_row in stages:
		out.append(StringName(str(stage_row.get("id", ""))))
	return out

func stage_index(stage_id: StringName) -> int:
	return stage_ids().find(stage_id)

func stage(index: int) -> Dictionary:
	return stages[index] if index >= 0 and index < stages.size() else {}

func first_stage() -> StringName:
	return StringName(str(stages[0].get("id", ""))) if not stages.is_empty() else &""
