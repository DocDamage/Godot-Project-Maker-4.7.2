@tool
class_name RpgAchievement
extends Resource
## An achievement (1.5.0): unlocked once, by itself, as soon as its condition `when` holds (or by
## the dialogue event unlock_achievement:<id>), with a toast; its rewards are given then (what
## does not fit in the bag waits). Files live in game/data/achievements/<id>.tres.
##
## `when` is a dialogue condition. Counters make most of them: count:<name>>=N reads
## GameState.counters, which count by themselves `defeated` and `defeated:<enemy id>` (enemies
## beaten), `items:<item id>` (items gained) and `quests_done`; the dialogue event
## count:<name>[:N] counts anything else.

@export var id: StringName
@export var title: String  # a tr() key
@export var description: String  # a tr() key
@export var icon: Texture2D
## The condition that unlocks it ("" = only the event unlock_achievement does).
@export var when: String = ""
## Shown as "???" until it is unlocked.
@export var secret: bool = false
@export var points: int = 10
## {gold: int, experience: int, items: [{item_id, qty}]}, like a quest's.
@export var rewards: Dictionary = {}

## What is wrong with it, one sentence each.
func problems() -> Array[String]:
	var out: Array[String] = []
	if id == &"":
		out.append("the achievement has no id")
	for why in RpgCondition.problems(when):
		out.append("what unlocks it: %s" % why)
	out.append_array(RpgQuestDefinition.reward_problems(rewards, "its rewards"))
	return out

## The achievement as plain data, and back (the dock's JSON export and import; the icon is
## written as its path).
func to_dict() -> Dictionary:
	var out := {"id": String(id), "title": title, "description": description, "when": when, "secret": secret, "points": points, "rewards": rewards.duplicate(true)}
	if icon != null and icon.resource_path != "":
		out["icon"] = icon.resource_path
	return out

static func from_dict(data: Dictionary) -> RpgAchievement:
	var made := RpgAchievement.new()
	made.id = StringName(str(data.get("id", "")))
	made.title = str(data.get("title", ""))
	made.description = str(data.get("description", ""))
	made.when = str(data.get("when", ""))
	made.secret = RpgUtil.to_bool(data.get("secret", false))
	made.points = RpgUtil.to_int(data.get("points", 10))
	made.rewards = RpgUtil.to_dict(data.get("rewards", {})).duplicate(true)
	var icon_path := str(data.get("icon", ""))
	if icon_path != "" and ResourceLoader.exists(icon_path):
		made.icon = load(icon_path) as Texture2D
	return made
