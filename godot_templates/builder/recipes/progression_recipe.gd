extends RefCounted
## Seeds the starters of the feature `progression` (1.5.0, *Skills and achievements*) under
## game/data/ (user_seed: written once, then yours to edit in the dock's Skills, Achievements and
## Item sets tabs): a skill tree of a fighting kind (turn-based, action RPG, metroidvania), the
## achievements the game has the parts for, and the set of the starter gear when data_recipe gave
## the starter weapon and armour its `set_id`.
##
## Only a config that has the feature on gets them; a config written before 1.5.0 has no such key,
## so an older project regenerates as it was: no file, and the same hash.

const RECIPE_VERSION := 1

const SeedUtil := preload("../lib/seed_util.gd")
const JsonUtil := preload("../lib/json_util.gd")
const BuildContext := preload("../lib/build_context.gd")
const DataRecipe := preload("data_recipe.gd")

const TREE_ID := "adventurer"
const TREE_PATH := "res://game/data/skill_trees/adventurer.tres"
const ACHIEVEMENTS_DIR := "res://game/data/achievements/"
const SET_PATH := "res://game/data/item_sets/" + DataRecipe.GEAR_SET + ".tres"

const TREE_DEF := "res://addons/rpg_runtime/data/skill_tree.gd"
const ACHIEVEMENT_DEF := "res://addons/rpg_runtime/data/achievement.gd"
const SET_DEF := "res://addons/rpg_runtime/data/item_set.gd"

## The kinds that have a skill tree: their fights read the stats a tree raises.
const TREE_KINDS: Array[String] = ["turn_based", "arpg", "metroidvania"]
## The kinds with a pause menu to show skills and achievements in.
const KINDS: Array[String] = ["turn_based", "arpg", "metroidvania", "farm"]

## English text of the seeded keys (the translations recipe adds them to strings.tsv).
const SEED_STRINGS := {
	"SKILLS_ADVENTURER_TITLE": "Adventurer",
	"SKILL_VIGOR_NAME": "Vigor",
	"SKILL_VIGOR_DESC": "More health.",
	"SKILL_STRENGTH_NAME": "Strength",
	"SKILL_STRENGTH_DESC": "Hit harder.",
	"SKILL_GUARD_NAME": "Guard",
	"SKILL_GUARD_DESC": "Take less damage.",
	"SKILL_HEALING_NAME": "Healing",
	"SKILL_HEALING_DESC": "Learn the Cure spell.",
	"SKILL_TOUGHNESS_NAME": "Toughness",
	"SKILL_TOUGHNESS_DESC": "A tenth more health.",
	"SKILL_FURY_NAME": "Fury",
	"SKILL_FURY_DESC": "A tenth more attack.",
	"SKILL_SWIFT_NAME": "Swift",
	"SKILL_SWIFT_DESC": "Move faster.",
	"ACHIEVEMENT_ERRAND_NAME": "A helping hand",
	"ACHIEVEMENT_ERRAND_DESC": "Finish the villager's errand.",
	"ACHIEVEMENT_HUNTER_NAME": "Monster hunter",
	"ACHIEVEMENT_HUNTER_DESC": "Defeat ten enemies.",
	"ACHIEVEMENT_SEASONED_NAME": "Seasoned",
	"ACHIEVEMENT_SEASONED_DESC": "Reach level 5.",
	"ACHIEVEMENT_SAVINGS_NAME": "Nest egg",
	"ACHIEVEMENT_SAVINGS_DESC": "Have 500 gold at once.",
	"ACHIEVEMENT_SAVINGS_FARM_DESC": "Have 2000 gold at once.",
	"ACHIEVEMENT_TREASURE_NAME": "Treasure hunter",
	"ACHIEVEMENT_TREASURE_DESC": "Open the chest in the village.",
	"ITEM_SET_TRAVELER_NAME": "Traveler's gear",
}

static func on(ctx: BuildContext) -> bool:
	return JsonUtil.to_bool(ctx.section("features").get("progression", false)) and KINDS.has(_kind(ctx))

static func _kind(ctx: BuildContext) -> String:
	return JsonUtil.to_str(ctx.config.get("archetype", "turn_based"))

static func achievement_path(achievement_id: String) -> String:
	return ACHIEVEMENTS_DIR + achievement_id + ".tres"

func outputs(ctx: BuildContext) -> PackedStringArray:
	if not on(ctx):
		return PackedStringArray()
	var wanted: Array = []
	if TREE_KINDS.has(_kind(ctx)):
		wanted.append(TREE_PATH)
	for achievement_id: String in achievements(ctx):
		wanted.append(achievement_path(achievement_id))
	if _gear_in_set():
		wanted.append(SET_PATH)
	return SeedUtil.missing(wanted)

func input_hash(ctx: BuildContext) -> String:
	if not on(ctx):
		return ctx.stable_hash({"v": RECIPE_VERSION, "on": false})
	return ctx.stable_hash({"v": RECIPE_VERSION, "kind": _kind(ctx), "achievements": achievements(ctx).keys(), "set": _gear_in_set()})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	if not on(ctx):
		return issues
	if TREE_KINDS.has(_kind(ctx)) and not FileAccess.file_exists(TREE_PATH):
		_save(ctx, tree(_kind(ctx)), TREE_PATH, issues)
	var wanted := achievements(ctx)
	for achievement_id: String in wanted:
		if not FileAccess.file_exists(achievement_path(achievement_id)):
			_save(ctx, achievement(achievement_id, JsonUtil.to_dict(wanted[achievement_id])), achievement_path(achievement_id), issues)
	if _gear_in_set() and not FileAccess.file_exists(SET_PATH):
		_save(ctx, gear_set(), SET_PATH, issues)
	return issues

func _save(ctx: BuildContext, res: Resource, path: String, issues: Array) -> void:
	var err := SeedUtil.save(res, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

## The adventurer's tree: vigor, strength and guard on the first row; on the second (open after
## two points above) what each leads to: healing (the Cure spell, turn-based) or toughness, fury
## and swift (speed in a battle, walking speed elsewhere). A reset costs 50 gold.
static func tree(kind: String) -> Resource:
	var made := SeedUtil.make(TREE_DEF)
	made.set("id", StringName(TREE_ID))
	made.set("title", "SKILLS_ADVENTURER_TITLE")
	made.set("points_per_row", 2)
	made.set("reset_gold", 50)
	var turn_based := kind == "turn_based"
	var skills: Array = [
		_skill("vigor", 0, 0, 3, [{"stat": "max_hp", "add": 3}]),
		_skill("strength", 1, 0, 3, [{"stat": "attack", "add": 1}]),
		_skill("guard", 2, 0, 2, [{"stat": "defense", "add": 1}]),
	]
	if turn_based:
		var healing := _skill("healing", 0, 1, 1, [])
		healing["requires"] = {"vigor": 1}
		healing["skill"] = "cure"
		skills.append(healing)
	else:
		var toughness := _skill("toughness", 0, 1, 1, [{"stat": "max_hp", "mul": 1.1}])
		toughness["requires"] = {"vigor": 2}
		skills.append(toughness)
	var fury := _skill("fury", 1, 1, 1, [{"stat": "attack", "mul": 1.1}])
	fury["requires"] = {"strength": 2}
	fury["cost"] = 2
	skills.append(fury)
	var swift := _skill("swift", 2, 1, 1, [{"stat": "speed", "add": 1}] if turn_based else [{"stat": "move_speed", "mul": 1.1}])
	swift["requires"] = {"guard": 1}
	skills.append(swift)
	made.set("skills", SeedUtil.dict_array(skills))
	return made

static func _skill(skill_id: String, column: int, row: int, max_rank: int, bonuses: Array) -> Dictionary:
	var out := {"id": skill_id, "title": "SKILL_%s_NAME" % skill_id.to_upper(), "description": "SKILL_%s_DESC" % skill_id.to_upper(), "cell": [column, row], "max_rank": max_rank, "cost": 1}
	if not bonuses.is_empty():
		out["bonuses"] = bonuses
	return out

## {achievement id: {when, points, rewards, secret}} of what the game has the parts for: the
## errand of the demo, ten enemies (a game that fights), level 5 (not a farm), gold saved (500, a
## farm's 2000) and, secret, the chest of the village.
static func achievements(ctx: BuildContext) -> Dictionary:
	var kind := _kind(ctx)
	var farm := kind == "farm"
	var demo := JsonUtil.to_bool(ctx.section("features").get("demo", true)) and not ctx.demo_removed and kind != "metroidvania"
	var out := {}
	if demo:
		out["errand"] = {"when": "quest_done:%s" % DataRecipe.QUEST_ID, "points": 10}  # the quest pays for itself
	if JsonUtil.to_bool(ctx.section("features").get("combat", false)):
		out["hunter"] = {"when": "count:defeated>=10", "points": 20, "rewards": {"items": [{"item_id": "potion", "qty": 2}]}}
	if not farm:
		out["seasoned"] = {"when": "level>=5", "points": 15}
	out["savings"] = {"when": "gold>=%d" % savings_goal(kind), "points": 10, "description": "ACHIEVEMENT_SAVINGS_FARM_DESC" if farm else ""}
	if demo and not farm and DataRecipe.new()._has_chest(ctx):
		out["treasure"] = {"when": "flag:%s.opened" % DataRecipe.CHEST_ID, "points": 5, "secret": true}
	return out

static func savings_goal(kind: String) -> int:
	return 2000 if kind == "farm" else 500

static func achievement(achievement_id: String, spec: Dictionary) -> Resource:
	var made := SeedUtil.make(ACHIEVEMENT_DEF)
	made.set("id", StringName(achievement_id))
	made.set("title", "ACHIEVEMENT_%s_NAME" % achievement_id.to_upper())
	var description := JsonUtil.to_str(spec.get("description", ""))
	made.set("description", description if description != "" else "ACHIEVEMENT_%s_DESC" % achievement_id.to_upper())
	made.set("when", JsonUtil.to_str(spec.get("when", "")))
	made.set("points", JsonUtil.to_int(spec.get("points", 10)))
	made.set("secret", JsonUtil.to_bool(spec.get("secret", false)))
	made.set("rewards", JsonUtil.to_dict(spec.get("rewards", {})))
	return made

## True when a starter gear item names the set (data_recipe gives it the `set_id` when it seeds
## both a weapon and an armour with the feature on).
static func _gear_in_set() -> bool:
	for word: String in DataRecipe.WEAPON_WORDS + DataRecipe.ARMOR_WORDS:
		var path := "res://game/data/items/%s.tres" % word
		if ResourceLoader.exists(path):
			var item := load(path) as Resource
			if item != null and JsonUtil.to_str(item.get("set_id")) == DataRecipe.GEAR_SET:
				return true
	return false

## The traveler's set: the starter weapon and armour worn together give 5 more health.
static func gear_set() -> Resource:
	var made := SeedUtil.make(SET_DEF)
	made.set("id", StringName(DataRecipe.GEAR_SET))
	made.set("title", "ITEM_SET_TRAVELER_NAME")
	made.set("bonuses", SeedUtil.dict_array([{"pieces": 2, "modifiers": [{"stat": "max_hp", "add": 5}]}]))
	return made
