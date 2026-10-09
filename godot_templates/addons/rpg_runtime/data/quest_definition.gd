@tool
class_name RpgQuestDefinition
extends Resource
## (A tool script, like the dialogue resources: the dock's Quests tab calls its methods on a
## quest loaded in the editor.)
## A quest: stages in order, each finished by a condition, and what completing it gives. Files live
## in game/data/quests/<id>.tres. GameState.quests[id] holds the id of the current stage while the
## quest is active and "done" afterwards; the dialogue events quest_start, quest_stage and
## quest_complete move it, and a stage whose `complete_when` holds moves on by itself.

## What `next` says to finish the quest, and what GameState.quests holds for a finished one.
const DONE := "done"

@export var id: StringName
@export var title: String  # a tr() key
## [{id, description (a tr() key), complete_when (a condition; "" = only an event finishes it)}].
## Stage ids must not be "done". Optional keys: `target` (the entity the minimap marks), `title`
## (a tr() key for editors), `next` (the stage that follows when the condition holds: a stage
## id, or "done"; without it the stage below follows) and `rewards` (given when the condition
## finishes the stage; the same shape as the quest's).
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

## The stage that follows stage `index` when its condition holds: its `next`, else the stage
## below. &"" means the quest is complete (the last stage, or `next` = "done").
func next_of(index: int) -> StringName:
	return next_in(stages, index)

static func next_in(stage_list: Array, index: int) -> StringName:
	if index < 0 or index >= stage_list.size():
		return &""
	var wanted := str(RpgUtil.to_dict(stage_list[index]).get("next", ""))
	if wanted == DONE:
		return &""
	if wanted != "":
		return StringName(wanted)
	if index + 1 >= stage_list.size():
		return &""
	return StringName(str(RpgUtil.to_dict(stage_list[index + 1]).get("id", "")))

## One [from, to] per stage, in order: the stage's id and where it leads ("done" at the end).
func edges() -> Array[Array]:
	return edges_of(stages)

static func edges_of(stage_list: Array) -> Array[Array]:
	var out: Array[Array] = []
	for i in stage_list.size():
		var following := next_in(stage_list, i)
		out.append([str(RpgUtil.to_dict(stage_list[i]).get("id", "")), String(following) if following != &"" else DONE])
	return out

## What is wrong with the quest, one sentence each (empty when nothing is): a missing id, no
## stages, stage ids that are empty, repeated or "done", conditions that do not parse, a `next`
## that names no stage, and rewards that are not numbers and items.
func problems() -> Array[String]:
	var out := problems_of(stages)
	if id == &"":
		out.push_front("the quest has no id")
	out.append_array(reward_problems(rewards, "the quest's rewards"))
	return out

static func problems_of(stage_list: Array) -> Array[String]:
	var out: Array[String] = []
	if stage_list.is_empty():
		out.append("the quest has no stages")
	var seen: Array[String] = []
	for i in stage_list.size():
		var row := RpgUtil.to_dict(stage_list[i])
		var stage_id := str(row.get("id", ""))
		var where := "stage %d (%s)" % [i + 1, stage_id if stage_id != "" else "no id"]
		if stage_id == "":
			out.append("%s needs an id" % where)
		elif stage_id == DONE:
			out.append("%s cannot be called 'done'" % where)
		elif seen.has(stage_id):
			out.append("%s repeats the id of an earlier stage" % where)
		seen.append(stage_id)
		for why in RpgCondition.problems(str(row.get("complete_when", ""))):
			out.append("%s: %s" % [where, why])
		out.append_array(reward_problems(RpgUtil.to_dict(row.get("rewards", {})), where))
	for i in stage_list.size():
		var row := RpgUtil.to_dict(stage_list[i])
		var wanted := str(row.get("next", ""))
		if wanted != "" and wanted != DONE and not seen.has(wanted):
			out.append("stage %d (%s) leads to the unknown stage '%s'" % [i + 1, str(row.get("id", "")), wanted])
	return out

static func reward_problems(reward: Dictionary, where: String) -> Array[String]:
	var out: Array[String] = []
	for key: String in ["gold", "experience"]:
		if reward.has(key) and (not typeof(reward[key]) in [TYPE_INT, TYPE_FLOAT] or RpgUtil.to_int(reward[key]) < 0):
			out.append("%s: '%s' must be a number, 0 or more" % [where, key])
	var reward_items: Variant = reward.get("items", [])
	if not (reward_items is Array):
		out.append("%s: 'items' must be a list" % where)
		return out
	var list: Array = reward_items
	for entry: Variant in list:
		if not (entry is Dictionary) or str(RpgUtil.to_dict(entry).get("item_id", "")) == "":
			out.append("%s: every item needs an 'item_id'" % where)
	return out

## Where the quest gets to from its first stage with `state` as it is (an editor's test): the id
## of the stage it stops at, or "done". Nothing is changed.
func reached(state: RpgGameState) -> String:
	if stages.is_empty():
		return DONE
	var index := 0
	for _guard in stages.size() + 1:
		var condition := str(stage(index).get("complete_when", ""))
		if condition == "" or not RpgCondition.evaluate_on(condition, state):
			return str(stage(index).get("id", ""))
		var following := next_of(index)
		if following == &"" or stage_index(following) < 0:
			return DONE
		index = stage_index(following)
	return str(stage(index).get("id", ""))  # the stages lead in a circle

## The quest as plain data, and back (the dock's JSON export and import).
func to_dict() -> Dictionary:
	return {"id": String(id), "title": title, "stages": stages.duplicate(true), "rewards": rewards.duplicate(true)}

static func from_dict(data: Dictionary) -> RpgQuestDefinition:
	var quest := RpgQuestDefinition.new()
	quest.id = StringName(str(data.get("id", "")))
	quest.title = str(data.get("title", ""))
	var raw_stages: Variant = data.get("stages", [])
	if raw_stages is Array:
		var list: Array = raw_stages
		for raw: Variant in list:
			if raw is Dictionary:
				quest.stages.append(RpgUtil.to_dict(raw).duplicate(true))
	quest.rewards = RpgUtil.to_dict(data.get("rewards", {})).duplicate(true)
	return quest
