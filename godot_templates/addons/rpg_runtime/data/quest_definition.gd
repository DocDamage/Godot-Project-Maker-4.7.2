@tool
class_name RpgQuestDefinition
extends Resource
## (A tool script, like the dialogue resources: the dock's Quests tab calls its methods on a
## quest loaded in the editor.)
## A quest: stages in order, each finished by a condition, and what completing it gives. Files live
## in game/data/quests/<id>.tres. GameState.quests[id] holds the id of the current stage while the
## quest is active, "done" afterwards and "failed" for one that failed; the dialogue events
## quest_start, quest_stage, quest_turn_in, quest_complete and quest_fail move it, and a stage
## whose `complete_when` holds moves on by itself (unless it waits to be turned in).

## What `next` says to finish the quest, and what GameState.quests holds for a finished one.
const DONE := "done"
## What GameState.quests holds for a quest that failed (its `fail_when` held, or quest_fail).
const FAILED := "failed"

@export var id: StringName
@export var title: String  # a tr() key
## [{id, description (a tr() key), complete_when (a condition; "" = only an event finishes it)}].
## Stage ids must not be "done". Optional keys: `target` (the entity the minimap marks), `title`
## (a tr() key for editors), `next` (the stage that follows when the condition holds: a stage
## id, or "done"; without it the stage below follows), `rewards` (given when the condition
## finishes the stage; the same shape as the quest's), `turn_in` (true: the stage does not move
## on by itself; while its condition holds the quest is ready to turn in, and the event
## quest_turn_in finishes it) and `take` ([{item_id, qty}], taken from the bag when the stage
## finishes; a stage whose items are not all in the bag does not finish).
@export var stages: Array[Dictionary] = []
## {gold: int, experience: int, items: [{item_id, qty}]}
@export var rewards: Dictionary = {}
## A condition the quest needs before it can start ("" = none): quest_start refuses it while the
## condition does not hold (a chain: "quest_done:first").
@export var requires: String = ""
## True: the quest starts by itself as soon as `requires` holds.
@export var auto_start: bool = false
## A condition that fails the quest while it is under way ("" = it cannot fail by itself). A
## failed quest gives nothing and stays failed.
@export var fail_when: String = ""

func stage_ids() -> Array[StringName]:
	var out: Array[StringName] = []
	for stage_row in stages:
		out.append(StringName(str(stage_row.get("id", ""))))
	return out

func stage_index(stage_id: StringName) -> int:
	return stage_ids().find(stage_id)

func stage(index: int) -> Dictionary:
	return stages[index] if index >= 0 and index < stages.size() else {}

## True when the stage waits for quest_turn_in instead of moving on by itself.
static func turns_in(stage_row: Dictionary) -> bool:
	return RpgUtil.to_bool(stage_row.get("turn_in", false))

## The items a stage takes when it finishes: [{item_id, qty}] with qty 1 or more.
static func take_of(stage_row: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var raw: Variant = stage_row.get("take", [])
	if raw is Array:
		var list: Array = raw
		for entry: Variant in list:
			var row := RpgUtil.to_dict(entry)
			var item_id := str(row.get("item_id", ""))
			if item_id != "":
				out.append({"item_id": item_id, "qty": maxi(1, RpgUtil.to_int(row.get("qty", 1)))})
	return out

## How far `state` is along the atoms of `condition` that count something, in order: [{atom,
## what, have, need}] for item:<id>>=N, gold>=N, level>=N, var:<name>>=N (or >N) and
## friendship:<id>>=N and count:<name>>=N, where `what` is the item, variable, person or counter
## ("gold", "level" for those).
## Atoms that count nothing (flags, quests) are left out; `have` is not capped at `need`, and it
## goes down again when the bag does ("Logs 5/8" after dropping three).
static func progress_of(condition: String, state: RpgGameState) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if state == null:
		return out
	for token in condition.strip_edges().split(" ", false):
		var count := _count(token, state)
		if not count.is_empty():
			out.append(count)
	return out

static func _count(atom: String, state: RpgGameState) -> Dictionary:
	if atom.begins_with("item:") and atom.contains(">="):
		var item_id := atom.trim_prefix("item:").get_slice(">=", 0)
		return _counted(atom, item_id, state.inventory.count(StringName(item_id)), atom.get_slice(">=", 1), 0)
	if atom.begins_with("gold>="):
		return _counted(atom, "gold", RpgUtil.to_int(state.gold), atom.trim_prefix("gold>="), 0)
	if atom.begins_with("level>="):
		return _counted(atom, "level", RpgUtil.to_int(state.player_stats.level), atom.trim_prefix("level>="), 0)
	if atom.begins_with("var:"):
		var body := atom.trim_prefix("var:")
		var at := body.find(">")
		if at <= 0:
			return {}
		var var_name := body.substr(0, at)
		if body.substr(at).begins_with(">="):
			return _counted(atom, var_name, state.get_var(var_name), body.substr(at + 2), 0)
		return _counted(atom, var_name, state.get_var(var_name), body.substr(at + 1), 1)  # >N: N + 1
	if atom.begins_with("count:") and atom.contains(">="):
		var counted := atom.trim_prefix("count:")
		var at_count := counted.rfind(">=")
		return _counted(atom, counted.substr(0, at_count), state.counter(counted.substr(0, at_count)), counted.substr(at_count + 2), 0)
	if atom.begins_with("friendship:") and atom.contains(">="):
		var person := atom.trim_prefix("friendship:").get_slice(">=", 0)
		var friendship := state.get_node_or_null(RpgGameState.FRIENDSHIP_NODE)
		var hearts := 0
		if friendship != null and friendship.has_method(&"hearts"):
			hearts = RpgUtil.to_int(friendship.call(&"hearts", person))
		return _counted(atom, person, hearts, atom.get_slice(">=", 1), 0)
	return {}

static func _counted(atom: String, what: String, have: int, need_text: String, more: int) -> Dictionary:
	if not need_text.is_valid_int():
		return {}
	return {"atom": atom, "what": what, "have": have, "need": need_text.to_int() + more}

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
	for why in RpgCondition.problems(requires):
		out.append("what the quest requires: %s" % why)
	for why in RpgCondition.problems(fail_when):
		out.append("what fails the quest: %s" % why)
	if auto_start and requires.strip_edges() == "":
		out.append("the quest starts by itself but requires nothing: give it a condition")
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
		if row.has("turn_in") and typeof(row["turn_in"]) != TYPE_BOOL:
			out.append("%s: 'turn_in' must be true or false" % where)
		var take: Variant = row.get("take", [])
		if not (take is Array):
			out.append("%s: 'take' must be a list" % where)
		else:
			var take_list: Array = take
			for entry: Variant in take_list:
				if not (entry is Dictionary) or str(RpgUtil.to_dict(entry).get("item_id", "")) == "":
					out.append("%s: every item it takes needs an 'item_id'" % where)
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
## of the stage it stops at, or "done". A stage that waits to be turned in stops it. Nothing is
## changed.
func reached(state: RpgGameState) -> String:
	if stages.is_empty():
		return DONE
	var index := 0
	for _guard in stages.size() + 1:
		var condition := str(stage(index).get("complete_when", ""))
		if condition == "" or turns_in(stage(index)) or not RpgCondition.evaluate_on(condition, state):
			return str(stage(index).get("id", ""))
		var following := next_of(index)
		if following == &"" or stage_index(following) < 0:
			return DONE
		index = stage_index(following)
	return str(stage(index).get("id", ""))  # the stages lead in a circle

## The quest as plain data, and back (the dock's JSON export and import). `requires`,
## `auto_start` and `fail_when` are written only when set.
func to_dict() -> Dictionary:
	var out := {"id": String(id), "title": title, "stages": stages.duplicate(true), "rewards": rewards.duplicate(true)}
	if requires != "":
		out["requires"] = requires
	if auto_start:
		out["auto_start"] = true
	if fail_when != "":
		out["fail_when"] = fail_when
	return out

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
	quest.requires = str(data.get("requires", ""))
	quest.auto_start = RpgUtil.to_bool(data.get("auto_start", false))
	quest.fail_when = str(data.get("fail_when", ""))
	return quest
