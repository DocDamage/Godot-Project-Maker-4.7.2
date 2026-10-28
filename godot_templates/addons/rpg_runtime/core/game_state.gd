class_name RpgGameState
extends Node
## Autoload "GameState": everything that is saved.

const ITEMS_DIR := "res://game/data/items"
const HERO_PATH := "res://game/data/actors/hero.tres"
const ACTORS_DIR := "res://game/data/actors"
## The most characters in the party, the player included (a battle fits four a side).
const MAX_PARTY := 4
const SHOPS_DIR := "res://game/data/shops"
const QUESTS_DIR := "res://game/data/quests"
const SEQUENCES_DIR := "res://game/data/sequences"
const DIALOGUE_DIR := "res://game/data/dialogue"
const ENEMIES_DIR := "res://game/data/enemies"
const ENCOUNTERS_DIR := "res://game/data/encounters"
const ITEM_SETS_DIR := "res://game/data/item_sets"
const SKILL_TREES_DIR := "res://game/data/skill_trees"
const ACHIEVEMENTS_DIR := "res://game/data/achievements"
## The value of GameState.quests[id] once a quest is finished.
const QUEST_DONE := "done"
## The value of GameState.quests[id] for a quest that failed.
const QUEST_FAILED := "failed"
const NEW_GAME_PATH := "res://game/data/new_game.tres"
## The child a farm's mode adds for its friendships (T17.09), and its key of a saved game.
const FRIENDSHIP_NODE := "Friendship"
const FRIENDSHIP_KEY := "friendship"
## The equipment slots, in display order. An item goes to the slot of its category.
const EQUIP_SLOTS: Array[StringName] = [&"weapon", &"armor", &"accessory"]
## The stats an equipment preview compares.
const PREVIEW_STATS: Array[StringName] = [&"max_hp", &"attack", &"defense", &"speed", &"magic", &"resistance", &"move_speed"]

var player_actor_id: StringName = &"hero"
var player_stats: RpgStats = RpgStats.new()
## The party members besides the player, in joining order: [{actor_id, stats}]. They fight in the
## turn-based battle; in the action RPG they follow the player and help (RpgAssist).
var party: Array[Dictionary] = []
var inventory := RpgInventory.new()
var gold: int = 0:
	set = set_gold
var current_map: String = ""
var current_spawn: StringName = &"default"
var player_position := Vector2.ZERO
var player_facing := "down"
var flags: Dictionary = {}  # entity_id -> {key: value}
## Numbers a script counts with (sequence and dialogue events set_var / add_var, the condition
## var:<name><op><N>): name -> int. Saved under the optional key `variables`.
var variables: Dictionary = {}
var quests: Dictionary = {}  # quest id -> the id of its current stage, or QUEST_DONE
var quest_defs: Dictionary = {}  # quest id -> RpgQuestDefinition (game/data/quests)
## What each shop has sold, its gold, its rolled wares and what can be bought back
## (RpgShopDefinition.status, 1.5.0): shop id -> {period, sold, funds, wares, buyback}. Saved under
## the optional "shops" key.
var shops: Dictionary = {}
## What was given while the bag was full (1.5.0): [{item_id, qty}], put in the bag as soon as
## there is room (deliver_pending). Saved under the optional "pending_items" key.
var pending_items: Array[Dictionary] = []
## The data of what is worn (1.5.0): actor id -> {slot: data} (the wear of a piece). Saved under
## the optional "worn_data" key.
var worn_data: Dictionary = {}
var item_sets: Dictionary = {}  # set id -> RpgItemSet (loaded from game/data/item_sets on demand)
## Skill trees (1.5.0): tree id -> RpgSkillTree (game/data/skill_trees), what each actor learned
## (actor id -> {tree id: {skill id: rank}}) and the points it has to spend (actor id -> int),
## saved under the optional keys "skill_ranks" and "skill_points". A level gained gives
## `skill_points_per_level` points, in a game that has a tree.
var skill_trees: Dictionary = {}
var skill_ranks: Dictionary = {}
var skill_points: Dictionary = {}
var skill_points_per_level: int = 1
## Achievements (1.5.0): id -> RpgAchievement (game/data/achievements), the ids unlocked (id ->
## true) and the counters their conditions read (name -> int: `count:<name>>=N`), saved under the
## optional keys "achievements" and "counters".
var achievement_defs: Dictionary = {}
var achievements: Dictionary = {}
var counters: Dictionary = {}
## The quest the HUD's tracker shows ("" for none): set by quest_start when none was tracked, and
## by track_quest (the journal, the event track_quest:<id>).
var tracked_quest: StringName = &""
## The cells of each map the player has seen (T12.64): minimap key -> {w, h, bits (one bit per
## cell, row by row)}. Saved under the optional "map_fog" key.
var map_fog: Dictionary = {}
## actor id (String) -> {slot: item id (String)}. Keyed by actor from the start so party members
## (T12.47) get their own; a missing actor or slot means nothing is worn.
var equipment: Dictionary = {}
## The abilities the player has (T14.05, the metroidvania): ids such as "double_jump". An optional
## key of a save: one written by 1.0 or 1.1 has none and loads with an empty list.
var abilities: Array[String] = []
## The breakable tiles the player broke, by room: {room_id: [[x, y], ...]}. Optional like `abilities`.
var broken_cells: Dictionary = {}
## The rooms the player has been in: {room_id: true} (T14.08, the room map). Optional like
## `abilities`; `map_fog`, the top-down maps' fog, keeps its meaning.
var room_fog: Dictionary = {}
var playtime_s: float = 0.0
var pending_encounter: RpgEncounterData = null
var rng: RpgRng = RpgRng.new()
var items: Dictionary = {}  # item id -> RpgItemDefinition
var actor_defs: Dictionary = {}  # actor id -> RpgActorDefinition (loaded from game/data/actors on demand)

func _ready() -> void:
	inventory.registry = items
	rng.seed_from_config()
	load_items()
	load_quests()
	load_skill_trees()
	load_achievements()
	var bus := RpgUtil.events()
	if bus != null:
		for signal_name: StringName in [&"entity_state_changed", &"variable_changed", &"item_added", &"item_removed", &"gold_changed", &"level_up", &"dialogue_finished", &"game_loaded"]:
			if bus.has_signal(signal_name) and not bus.is_connected(signal_name, _on_quest_event):
				bus.connect(signal_name, _on_quest_event)
		for signal_name: StringName in [&"item_removed", &"game_loaded"]:
			if bus.has_signal(signal_name) and not bus.is_connected(signal_name, _on_room_made):
				bus.connect(signal_name, _on_room_made)
		if bus.has_signal(&"item_added") and not bus.is_connected(&"item_added", _on_item_counted):
			bus.connect(&"item_added", _on_item_counted)
		if bus.has_signal(&"quest_changed") and not bus.is_connected(&"quest_changed", _on_quest_counted):
			bus.connect(&"quest_changed", _on_quest_counted)

func set_gold(value: int) -> void:
	gold = maxi(0, value)
	RpgUtil.emit(&"gold_changed", [gold])

## Loads every .tres under res://game/data/items/ (sorted by path) into `items`. The first of two
## equal ids wins.
func load_items(dir_path: String = ITEMS_DIR) -> void:
	items.clear()
	var paths := _list_tres(dir_path)
	paths.sort()
	for path in paths:
		var def := load(path) as RpgItemDefinition
		if def == null:
			continue
		if items.has(def.id):
			push_error("[RPG-DATA] duplicate item id %s in %s" % [def.id, path])
			continue
		items[def.id] = def

## Loads every .tres under res://game/data/quests/ into `quest_defs`.
func load_quests(dir_path: String = QUESTS_DIR) -> void:
	quest_defs.clear()
	var paths := _list_tres(dir_path)
	paths.sort()
	for path in paths:
		var def := load(path) as RpgQuestDefinition
		if def != null and def.id != &"" and not quest_defs.has(def.id):
			quest_defs[def.id] = def

## Loads every .tres under res://game/data/skill_trees/ into `skill_trees`.
func load_skill_trees(dir_path: String = SKILL_TREES_DIR) -> void:
	skill_trees.clear()
	var paths := _list_tres(dir_path)
	paths.sort()
	for path in paths:
		var tree := load(path) as RpgSkillTree
		if tree != null and tree.id != &"" and not skill_trees.has(tree.id):
			skill_trees[tree.id] = tree

## Loads every .tres under res://game/data/achievements/ into `achievement_defs`.
func load_achievements(dir_path: String = ACHIEVEMENTS_DIR) -> void:
	achievement_defs.clear()
	var paths := _list_tres(dir_path)
	paths.sort()
	for path in paths:
		var def := load(path) as RpgAchievement
		if def != null and def.id != &"" and not achievement_defs.has(def.id):
			achievement_defs[def.id] = def

# ------------------------------------------------------------------ the map fog (T12.64)

## Marks the cells within `radius` of `cell` as seen on a map of `size` cells.
func fog_mark(map_key: String, size: Vector2i, cell: Vector2i, radius: int = 4) -> void:
	if size.x <= 0 or size.y <= 0:
		return
	var entry: Dictionary = map_fog.get(map_key, {})
	if RpgUtil.to_int(entry.get("w", 0)) != size.x or RpgUtil.to_int(entry.get("h", 0)) != size.y:
		var empty := PackedByteArray()
		empty.resize((size.x * size.y + 7) / 8)
		entry = {"w": size.x, "h": size.y, "bits": empty}
	var bits: PackedByteArray = entry["bits"]
	for y in range(maxi(0, cell.y - radius), mini(size.y, cell.y + radius + 1)):
		for x in range(maxi(0, cell.x - radius), mini(size.x, cell.x + radius + 1)):
			if Vector2i(x, y).distance_squared_to(cell) <= radius * radius:
				var i := y * size.x + x
				bits[i >> 3] |= 1 << (i & 7)
	entry["bits"] = bits
	map_fog[map_key] = entry

## True when the player has seen `cell` of the map.
func fog_seen(map_key: String, cell: Vector2i) -> bool:
	var entry: Dictionary = map_fog.get(map_key, {})
	var w := RpgUtil.to_int(entry.get("w", 0))
	var h := RpgUtil.to_int(entry.get("h", 0))
	if cell.x < 0 or cell.y < 0 or cell.x >= w or cell.y >= h:
		return false
	var bits: PackedByteArray = entry["bits"]
	var i := cell.y * w + cell.x
	return (bits[i >> 3] & (1 << (i & 7))) != 0

## The maps the player has been to (minimap keys), sorted.
func visited_maps() -> Array[String]:
	var out: Array[String] = []
	for key: Variant in map_fog:
		out.append(str(key))
	out.sort()
	return out

func _fog_to_dict() -> Dictionary:
	var out := {}
	for key: Variant in map_fog:
		var entry: Dictionary = map_fog[key]
		var bits: PackedByteArray = entry["bits"]
		out[str(key)] = {"w": entry["w"], "h": entry["h"], "bits": Marshalls.raw_to_base64(bits)}
	return out

## The optional `map_fog` key of a save; anything malformed is dropped.
static func _fog_from(raw: Variant) -> Dictionary:
	var out := {}
	if not (raw is Dictionary):
		return out
	var table: Dictionary = raw
	for key: Variant in table:
		if not (table[key] is Dictionary):
			continue
		var entry: Dictionary = table[key]
		var w := RpgUtil.to_int(entry.get("w", 0))
		var h := RpgUtil.to_int(entry.get("h", 0))
		var bits := Marshalls.base64_to_raw(str(entry.get("bits", "")))
		if w > 0 and h > 0 and bits.size() == (w * h + 7) / 8:
			out[str(key)] = {"w": w, "h": h, "bits": bits}
	return out

## The entity ids the current stages of active quests point at (a stage's optional "target").
func quest_targets() -> Array[String]:
	var out: Array[String] = []
	for quest_id: Variant in quest_defs:
		var id := StringName(str(quest_id))
		if not quest_is_active(id):
			continue
		var def: RpgQuestDefinition = quest_defs[quest_id]
		var stage := def.stage(def.stage_index(StringName(quest_state(id))))
		var target := str(stage.get("target", ""))
		if target != "" and not out.has(target):
			out.append(target)
	return out

# ------------------------------------------------------------------ quests (T12.48)

func quest_state(quest_id: StringName) -> String:
	return str(quests.get(String(quest_id), ""))

func quest_is_active(quest_id: StringName) -> bool:
	var current := quest_state(quest_id)
	return current != "" and current != QUEST_DONE and current != QUEST_FAILED

func quest_is_done(quest_id: StringName) -> bool:
	return quest_state(quest_id) == QUEST_DONE

func quest_is_failed(quest_id: StringName) -> bool:
	return quest_state(quest_id) == QUEST_FAILED

## True when the quest has not been started and what it requires holds (a quest without
## `requires`, or without a definition, is available until it starts).
func quest_available(quest_id: StringName) -> bool:
	if quest_state(quest_id) != "":
		return false
	var def: RpgQuestDefinition = quest_defs.get(quest_id)
	return def == null or def.requires.strip_edges() == "" or RpgCondition.evaluate_on(def.requires, self)

## The current stage of an active quest ({} for one that is not, or has no definition).
func quest_current_stage(quest_id: StringName) -> Dictionary:
	if not quest_is_active(quest_id):
		return {}
	var def: RpgQuestDefinition = quest_defs.get(quest_id)
	return def.stage(def.stage_index(StringName(quest_state(quest_id)))) if def != null else {}

## True when the quest's current stage waits to be turned in, its condition holds and the bag
## holds what it takes. Counted live: dropping the logs makes the quest not ready again.
func quest_ready(quest_id: StringName) -> bool:
	var stage := quest_current_stage(quest_id)
	return RpgQuestDefinition.turns_in(stage) and _stage_can_finish(stage)

func _stage_can_finish(stage: Dictionary) -> bool:
	var condition := str(stage.get("complete_when", ""))
	if condition != "" and not RpgCondition.evaluate_on(condition, self):
		return false
	for row in RpgQuestDefinition.take_of(stage):
		if inventory.count(StringName(str(row["item_id"]))) < RpgUtil.to_int(row["qty"]):
			return false
	return true

## How far the current stage of an active quest is along: RpgQuestDefinition.progress_of of its
## condition.
func quest_progress(quest_id: StringName) -> Array[Dictionary]:
	return RpgQuestDefinition.progress_of(str(quest_current_stage(quest_id).get("complete_when", "")), self)

func _quest_title(quest_id: StringName) -> String:
	var def: RpgQuestDefinition = quest_defs.get(quest_id)
	return TranslationServer.translate(def.title if def != null and def.title != "" else String(quest_id))

## Starts a quest at its first stage ("active" for a quest without stages or definition). False
## when it was started before, or what it requires does not hold. A quest started while none is
## tracked becomes the tracked one.
func quest_start(quest_id: StringName) -> bool:
	if not quest_available(quest_id):
		return false
	var def: RpgQuestDefinition = quest_defs.get(quest_id)
	var first := def.first_stage() if def != null else &""
	quests[String(quest_id)] = String(first) if first != &"" else "active"
	if not quest_is_active(tracked_quest):
		tracked_quest = quest_id
	RpgUtil.notify(RpgStrings.format("UI_QUEST_NEW", _quest_title(quest_id)))
	RpgUtil.emit(&"quest_changed", [quest_id, quest_state(quest_id)])
	refresh_quests()
	return true

## Fails an active quest: it gives nothing and stays failed. False for one not under way.
func quest_fail(quest_id: StringName) -> bool:
	if not quest_is_active(quest_id):
		return false
	quests[String(quest_id)] = QUEST_FAILED
	_track_another(quest_id)
	RpgUtil.notify(RpgStrings.format("UI_QUEST_FAILED", _quest_title(quest_id)))
	RpgUtil.emit(&"quest_changed", [quest_id, QUEST_FAILED])
	return true

## Finishes the current stage of a quest that is ready to turn in (quest_ready): takes what the
## stage takes, gives its rewards and moves on. False, and nothing changes, when it is not ready.
func quest_turn_in(quest_id: StringName) -> bool:
	if not quest_ready(quest_id):
		return false
	var def: RpgQuestDefinition = quest_defs[quest_id]
	_finish_stage(quest_id, def, def.stage_index(StringName(quest_state(quest_id))))
	return true

## When the tracked quest ends, the tracker moves to the first quest still under way.
func _track_another(ended: StringName) -> void:
	if tracked_quest != ended:
		return
	var active := journal_ids(false)
	tracked_quest = active[0] if not active.is_empty() else &""

## Tracks an active quest; any other id (an empty one too) tracks nothing. Emits quest_changed
## so the tracker shows it.
func track_quest(quest_id: StringName) -> bool:
	tracked_quest = quest_id if quest_is_active(quest_id) else &""
	RpgUtil.emit(&"quest_changed", [tracked_quest, quest_state(tracked_quest)])
	return tracked_quest != &""

## Moves an active quest to `stage_id` (a stage of its definition, when it has one).
func quest_set_stage(quest_id: StringName, stage_id: StringName) -> bool:
	if not quest_is_active(quest_id) or stage_id == &"" or String(stage_id) == QUEST_DONE:
		return false
	var def: RpgQuestDefinition = quest_defs.get(quest_id)
	if def != null and def.stage_index(stage_id) < 0:
		return false
	if quest_state(quest_id) == String(stage_id):
		return false
	quests[String(quest_id)] = String(stage_id)
	RpgUtil.notify(RpgStrings.format("UI_QUEST_UPDATED", _quest_title(quest_id)))
	RpgUtil.emit(&"quest_changed", [quest_id, quest_state(quest_id)])
	refresh_quests()
	return true

## Finishes a quest and gives its rewards, once. A quest that was never started is started and
## finished.
func quest_complete(quest_id: StringName) -> bool:
	if quest_is_done(quest_id) or quest_is_failed(quest_id):
		return false
	quests[String(quest_id)] = QUEST_DONE
	_track_another(quest_id)
	var def: RpgQuestDefinition = quest_defs.get(quest_id)
	if def != null:
		_give_quest_rewards(def.rewards)
	RpgUtil.notify(RpgStrings.format("UI_QUEST_DONE", _quest_title(quest_id)))
	RpgUtil.emit(&"quest_changed", [quest_id, QUEST_DONE])
	return true

func _give_quest_rewards(rewards: Dictionary) -> void:
	gold += RpgUtil.to_int(rewards.get("gold", 0))
	var experience := RpgUtil.to_int(rewards.get("experience", 0))
	if experience > 0:
		give_experience(experience)
	give_items(RpgUtil.to_array(rewards.get("items", [])))

# ------------------------------------------------------------------ skill trees (1.5.0)

## The ids of the skill trees, in id order.
func skill_tree_ids() -> Array[StringName]:
	var out: Array[StringName] = []
	for tree_id: Variant in skill_trees.keys():
		out.append(StringName(str(tree_id)))
	out.sort()
	return out

func skill_tree_of(tree_id: StringName) -> RpgSkillTree:
	var tree: RpgSkillTree = skill_trees.get(tree_id)
	return tree

## What the actor learned of a tree: {skill id: rank} (a copy).
func ranks_of(actor_id: StringName, tree_id: StringName) -> Dictionary:
	return RpgUtil.to_dict(RpgUtil.to_dict(skill_ranks.get(String(actor_id), {})).get(String(tree_id), {})).duplicate()

func points_of(actor_id: StringName) -> int:
	return RpgUtil.to_int(skill_points.get(String(actor_id), 0))

func give_skill_points(actor_id: StringName, amount: int) -> void:
	if amount != 0 and stats_of(actor_id) != null:
		skill_points[String(actor_id)] = maxi(0, points_of(actor_id) + amount)

func _set_ranks(actor_id: StringName, tree_id: StringName, ranks: Dictionary) -> void:
	var per_tree := RpgUtil.to_dict(skill_ranks.get(String(actor_id), {})).duplicate()
	var kept := {}
	for skill_id: Variant in ranks:
		if RpgUtil.to_int(ranks[skill_id]) > 0:
			kept[str(skill_id)] = RpgUtil.to_int(ranks[skill_id])
	if kept.is_empty():
		per_tree.erase(String(tree_id))
	else:
		per_tree[String(tree_id)] = kept
	if per_tree.is_empty():
		skill_ranks.erase(String(actor_id))
	else:
		skill_ranks[String(actor_id)] = per_tree

## Learns one more rank of a skill for the actor, paid in its points. Returns "" or why not
## (RpgSkillTree's codes).
func learn_skill(actor_id: StringName, tree_id: StringName, skill_id: StringName) -> String:
	var tree := skill_tree_of(tree_id)
	if tree == null or stats_of(actor_id) == null:
		return RpgSkillTree.UNKNOWN
	var ranks := ranks_of(actor_id, tree_id)
	var why := tree.learn_problem(ranks, points_of(actor_id), skill_id)
	if why != RpgSkillTree.OK:
		return why
	ranks[String(skill_id)] = RpgSkillTree.rank_in(ranks, skill_id) + 1
	_set_ranks(actor_id, tree_id, ranks)
	skill_points[String(actor_id)] = points_of(actor_id) - RpgSkillTree.cost_of(tree.skill(skill_id))
	_refit(actor_id)
	return RpgSkillTree.OK

## Unlearns one rank and gives its points back. Returns "" or why not.
func unlearn_skill(actor_id: StringName, tree_id: StringName, skill_id: StringName) -> String:
	var tree := skill_tree_of(tree_id)
	if tree == null:
		return RpgSkillTree.UNKNOWN
	var ranks := ranks_of(actor_id, tree_id)
	var why := tree.unlearn_problem(ranks, skill_id)
	if why != RpgSkillTree.OK:
		return why
	ranks[String(skill_id)] = RpgSkillTree.rank_in(ranks, skill_id) - 1
	_set_ranks(actor_id, tree_id, ranks)
	skill_points[String(actor_id)] = points_of(actor_id) + RpgSkillTree.cost_of(tree.skill(skill_id))
	_refit(actor_id)
	return RpgSkillTree.OK

## Why the actor cannot reset the tree now, or "": it cannot be reset, nothing is learned, or the
## gold is short.
func reset_problem(actor_id: StringName, tree_id: StringName) -> String:
	var tree := skill_tree_of(tree_id)
	if tree == null or tree.reset_gold < 0:
		return RpgSkillTree.UNKNOWN
	if ranks_of(actor_id, tree_id).is_empty():
		return RpgSkillTree.NOT_LEARNED
	if gold < tree.reset_gold:
		return RpgShopDefinition.NOT_ENOUGH_GOLD
	return RpgSkillTree.OK

## Unlearns the whole tree for its `reset_gold`; every point comes back. Returns "" or why not.
func reset_skill_tree(actor_id: StringName, tree_id: StringName) -> String:
	var why := reset_problem(actor_id, tree_id)
	if why != RpgSkillTree.OK:
		return why
	var tree := skill_tree_of(tree_id)
	gold -= tree.reset_gold
	skill_points[String(actor_id)] = points_of(actor_id) + tree.spent(ranks_of(actor_id, tree_id))
	_set_ranks(actor_id, tree_id, {})
	_refit(actor_id)
	return RpgSkillTree.OK

## The modifiers of everything the actor learned, in every tree.
func learned_modifiers(actor_id: StringName) -> Array:
	var out: Array = []
	for tree_id in skill_tree_ids():
		var ranks := ranks_of(actor_id, tree_id)
		if not ranks.is_empty():
			out.append_array(skill_tree_of(tree_id).bonuses_of(ranks))
	return out

## The battle skills the actor learned in its trees.
func learned_battle_skills(actor_id: StringName) -> Array[StringName]:
	var out: Array[StringName] = []
	for tree_id in skill_tree_ids():
		for battle_skill in skill_tree_of(tree_id).battle_skills_of(ranks_of(actor_id, tree_id)):
			if not out.has(battle_skill):
				out.append(battle_skill)
	return out

## A stat bonus learned or lost: the hp and mp stay within the new maximum.
func _refit(actor_id: StringName) -> void:
	var refit := stats_of(actor_id)
	if refit != null:
		refit.hp = mini(refit.hp, RpgUtil.max_hp(refit))
		refit.mp = mini(refit.mp, RpgUtil.max_mp(refit))
	RpgUtil.emit(&"equipment_changed", [actor_id, &""])

# ------------------------------------------------------------------ achievements (1.5.0)

func counter(counter_name: String) -> int:
	return RpgUtil.to_int(counters.get(counter_name, 0))

## Adds `by` to a counter (the condition atom count:<name>>=N reads it) and checks the
## achievements. Returns the new count.
func count(counter_name: String, by: int = 1) -> int:
	if counter_name == "" or by == 0:
		return counter(counter_name)
	counters[counter_name] = counter(counter_name) + by
	refresh_achievements()
	return counter(counter_name)

## An enemy of this kind (its RpgEnemyDefinition id) was defeated: counts `defeated` and
## `defeated:<id>`.
func note_defeat(enemy_id: StringName) -> void:
	if achievement_defs.is_empty():
		return  # nothing reads the counters: a game without achievements keeps none
	counters["defeated"] = counter("defeated") + 1
	if enemy_id != &"":
		counters["defeated:%s" % enemy_id] = counter("defeated:%s" % enemy_id) + 1
	refresh_achievements()

## True while items move without being gained (equip, unequip, the items of a new game).
var _moving_gear := false

## An item gained counts `items:<id>` ("Gather 30 logs": count:items:log>=30), in a game that has
## achievements.
func _on_item_counted(item_id: StringName, qty: int) -> void:
	if not _moving_gear and not _delivering_counted:
		RpgCrafting.note_held(self, item_id)  # a recipe found by itself (T18.14)
	if not _moving_gear and not _delivering_counted and not achievement_defs.is_empty():
		count("items:%s" % item_id, qty)

var _delivering_counted := false

func _on_quest_counted(_quest_id: StringName, quest_state_text: String) -> void:
	if quest_state_text == QUEST_DONE and not achievement_defs.is_empty():
		count("quests_done")

func achievement_unlocked(achievement_id: StringName) -> bool:
	return achievements.has(String(achievement_id))

## Unlocks an achievement once: a toast, its rewards (what does not fit waits). False when it was
## unlocked before or does not exist.
func unlock_achievement(achievement_id: StringName) -> bool:
	if achievement_unlocked(achievement_id) or not achievement_defs.has(achievement_id):
		return false
	var def: RpgAchievement = achievement_defs[achievement_id]
	achievements[String(achievement_id)] = true
	RpgUtil.notify(RpgStrings.format("UI_ACHIEVEMENT_UNLOCKED", TranslationServer.translate(def.title if def.title != "" else String(achievement_id))))
	_give_quest_rewards(def.rewards)
	return true

var _refreshing_achievements := false

## Unlocks every achievement whose condition holds.
func refresh_achievements() -> void:
	if _refreshing_achievements or achievement_defs.is_empty():
		return
	_refreshing_achievements = true
	for achievement_id: StringName in achievement_defs:
		var def: RpgAchievement = achievement_defs[achievement_id]
		if not achievement_unlocked(achievement_id) and def.when.strip_edges() != "" and RpgCondition.evaluate_on(def.when, self):
			unlock_achievement(achievement_id)
	_refreshing_achievements = false

## The achievements in id order, and the points of those unlocked.
func achievement_ids() -> Array[StringName]:
	var out: Array[StringName] = []
	for achievement_id: Variant in achievement_defs.keys():
		out.append(StringName(str(achievement_id)))
	out.sort()
	return out

func achievement_points() -> int:
	var total := 0
	for achievement_id in achievement_ids():
		if achievement_unlocked(achievement_id):
			var def: RpgAchievement = achievement_defs[achievement_id]
			total += maxi(0, def.points)
	return total

# ------------------------------------------------------------------ items that wait (1.5.0)

## Puts every row ([{item_id, qty}]) in the bag; what does not fit waits in `pending_items` (a
## toast says so) and comes as soon as there is room. Nothing given is lost. Returns what waits.
func give_items(rows: Array) -> Array[Dictionary]:
	var waiting: Array[Dictionary] = []
	for raw: Variant in rows:
		var row := RpgUtil.to_dict(raw)
		var item_id := StringName(str(row.get("item_id", "")))
		var qty := RpgUtil.to_int(row.get("qty", 1))
		if item_id == &"" or qty <= 0:
			continue
		var left := qty - inventory.add(item_id, qty)
		if left > 0:
			waiting.append({"item_id": String(item_id), "qty": left})
	for row in waiting:
		_wait(StringName(str(row["item_id"])), RpgUtil.to_int(row["qty"]))
		RpgUtil.notify(RpgStrings.format("UI_ITEM_WAITING", _item_label(StringName(str(row["item_id"])), RpgUtil.to_int(row["qty"]))))
	return waiting

func _wait(item_id: StringName, qty: int) -> void:
	for row in pending_items:
		if StringName(str(row["item_id"])) == item_id:
			row["qty"] = RpgUtil.to_int(row["qty"]) + qty
			return
	pending_items.append({"item_id": String(item_id), "qty": qty})

## "Potion" or "Potion x3", by the item's name.
func _item_label(item_id: StringName, qty: int) -> String:
	var def: RpgItemDefinition = items.get(item_id)
	var item_name: String = String(TranslationServer.translate(def.display_name)) if def != null and def.display_name != "" else String(item_id)
	return item_name if qty == 1 else "%s x%d" % [item_name, qty]

var _delivering := false

func _on_room_made(_a: Variant = null, _b: Variant = null) -> void:
	deliver_pending()

## Puts what waits in the bag, as much as fits (a toast for what came). Returns how many came.
func deliver_pending() -> int:
	if _delivering or pending_items.is_empty():
		return 0
	_delivering = true
	_delivering_counted = true
	var came := 0
	var still: Array[Dictionary] = []
	for row: Dictionary in pending_items.duplicate(true):
		var item_id := StringName(str(row["item_id"]))
		var qty := RpgUtil.to_int(row["qty"])
		var added := inventory.add(item_id, qty)
		if added > 0:
			came += added
			RpgUtil.notify(RpgStrings.format("UI_ITEM_DELIVERED", _item_label(item_id, added)))
		if added < qty:
			still.append({"item_id": String(item_id), "qty": qty - added})
	pending_items = still
	_delivering = false
	_delivering_counted = false
	return came

var _refreshing_quests := false

func _on_quest_event(_a: Variant = null, _b: Variant = null, _c: Variant = null) -> void:
	refresh_quests()
	refresh_achievements()

## Moves every active quest past the stages whose `complete_when` holds (a stage that waits to be
## turned in stays; one whose items are not in the bag stays too); finishing the last stage
## completes the quest. A quest whose `fail_when` holds fails, and one that starts by itself
## starts when what it requires holds. Safe to call at any time (a reward that changes state does
## not recurse).
func refresh_quests() -> void:
	if _refreshing_quests:
		return
	_refreshing_quests = true
	var progressed := true
	var guard := 0
	while progressed and guard < 64:
		progressed = false
		guard += 1
		for quest_id: StringName in quest_defs:
			var def: RpgQuestDefinition = quest_defs[quest_id]
			if def.auto_start and def.requires.strip_edges() != "" and quest_available(quest_id):
				_refreshing_quests = false  # the start's own refresh runs the rest
				quest_start(quest_id)
				_refreshing_quests = true
				progressed = true
				continue
			if not quest_is_active(quest_id):
				continue
			if def.fail_when.strip_edges() != "" and RpgCondition.evaluate_on(def.fail_when, self):
				quest_fail(quest_id)
				progressed = true
				continue
			var index := def.stage_index(StringName(quest_state(quest_id)))
			if index < 0:
				continue
			var stage := def.stage(index)
			if str(stage.get("complete_when", "")) == "" or RpgQuestDefinition.turns_in(stage) or not _stage_can_finish(stage):
				continue
			progressed = true
			_finish_stage(quest_id, def, index)
	_refreshing_quests = false

## Takes what stage `index` takes, gives its own rewards and moves the quest to the stage that
## follows (its `next`, else the stage below), or completes it.
func _finish_stage(quest_id: StringName, def: RpgQuestDefinition, index: int) -> void:
	var stage := def.stage(index)
	for row in RpgQuestDefinition.take_of(stage):
		inventory.remove(StringName(str(row["item_id"])), RpgUtil.to_int(row["qty"]))
	_give_quest_rewards(RpgUtil.to_dict(stage.get("rewards", {})))  # a stage's own
	var following := def.next_of(index)
	if following == &"" or not quest_set_stage(quest_id, following):
		quest_complete(quest_id)

## The ids of the defined quests that are active (or finished: done or failed), in id order.
func journal_ids(finished: bool) -> Array[StringName]:
	var out: Array[StringName] = []
	var ids: Array = quest_defs.keys()
	ids.sort()
	for quest_id: StringName in ids:
		if ((quest_is_done(quest_id) or quest_is_failed(quest_id)) if finished else quest_is_active(quest_id)):
			out.append(quest_id)
	return out

func _list_tres(dir_path: String) -> Array[String]:
	var found: Array[String] = []
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return found
	for file_name in dir.get_files():
		var name := file_name.trim_suffix(".remap")
		if name.ends_with(".tres"):
			found.append(dir_path.path_join(name))
	for sub in dir.get_directories():
		found.append_array(_list_tres(dir_path.path_join(sub)))
	return found

## Resets everything. Starting stats come from game/data/actors/hero.tres, starting gold, items and
## map from game/data/new_game.tres.
func new_game() -> void:
	if items.is_empty():
		load_items()
	var data := RpgNewGameData.new()
	if ResourceLoader.exists(NEW_GAME_PATH):
		var loaded := load(NEW_GAME_PATH) as RpgNewGameData
		if loaded != null:
			data = loaded
	player_stats = RpgStats.new()
	if ResourceLoader.exists(HERO_PATH):
		var hero := load(HERO_PATH) as RpgActorDefinition
		if hero != null:
			player_actor_id = hero.id if hero.id != &"" else &"hero"
			if hero.base_stats != null:
				player_stats = hero.base_stats.duplicate(true) as RpgStats
	player_stats.hp = player_stats.max_hp
	player_stats.mp = player_stats.max_mp
	party.clear()
	inventory.slots.clear()
	flags.clear()
	variables.clear()
	quests.clear()
	tracked_quest = &""
	shops.clear()
	pending_items.clear()
	worn_data.clear()
	skill_ranks.clear()
	skill_points.clear()
	skill_points_per_level = maxi(0, data.skill_points_per_level)
	achievements.clear()
	counters.clear()
	equipment.clear()
	abilities.clear()
	broken_cells.clear()
	room_fog.clear()
	playtime_s = 0.0
	map_fog.clear()
	pending_encounter = null
	gold = data.gold
	_moving_gear = true  # what a game starts with is not gained
	for entry in data.items:
		inventory.add(StringName(str(entry.get("item_id", ""))), RpgUtil.to_int(entry.get("qty", 1)))
	_moving_gear = false
	current_map = data.start_map
	current_spawn = data.start_spawn
	player_position = Vector2.ZERO
	player_facing = "down"
	rng.seed_from_config()
	var calendar := RpgCalendar.current()
	if calendar != null:
		calendar.reset()
	var friendship := _friendship()
	if friendship != null:
		friendship.call(&"reset")

# ---------------------------------------------------------------- abilities (T14.05)

func has_ability(id: StringName) -> bool:
	return abilities.has(String(id))

## Gives the player an ability. False when it was there already. Emits Events.ability_granted.
func grant(id: StringName) -> bool:
	var text := String(id)
	if text == "" or abilities.has(text):
		return false
	abilities.append(text)
	RpgUtil.emit(&"ability_granted", [id])
	return true

## Marks a room as visited. True when it was new.
func visit_room(room_id: String) -> bool:
	if room_id == "" or room_fog.has(room_id):
		return false
	room_fog[room_id] = true
	return true

func room_visited(room_id: String) -> bool:
	return room_fog.has(room_id)

## The optional `room_fog` key of a save: {room: true}; anything else is dropped.
static func _room_fog_from(raw: Variant) -> Dictionary:
	var out: Dictionary = {}
	if raw is Dictionary:
		var table: Dictionary = raw
		for room: Variant in table:
			if RpgUtil.to_bool(table[room]) and str(room) != "":
				out[str(room)] = true
	return out

## Remembers that the breakable tile at `cell` of `room_id` is gone.
func remember_broken_cell(room_id: String, cell: Vector2i) -> void:
	var list: Array = broken_cells.get(room_id, [])
	var entry := [cell.x, cell.y]
	if not list.has(entry):
		list.append(entry)
	broken_cells[room_id] = list

## The cells broken in a room.
func broken_cells_of(room_id: String) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	var list: Array = broken_cells.get(room_id, [])
	for entry: Array in list:
		out.append(Vector2i(RpgUtil.to_int(entry[0]), RpgUtil.to_int(entry[1])))
	return out

## The optional `abilities` key of a save: a list of texts, each once; anything else is dropped.
static func _abilities_from(raw: Variant) -> Array[String]:
	var out: Array[String] = []
	if raw is Array:
		var list: Array = raw
		for value: Variant in list:
			if (value is String or value is StringName) and str(value) != "" and not out.has(str(value)):
				out.append(str(value))
	return out

## The optional `broken_cells` key of a save: {room: [[x, y], ...]} of whole numbers.
static func _broken_cells_from(raw: Variant) -> Dictionary:
	var out: Dictionary = {}
	if not (raw is Dictionary):
		return out
	var table: Dictionary = raw
	for room: Variant in table:
		if not (table[room] is Array):
			continue
		var cells: Array = table[room]
		var kept: Array = []
		for cell: Variant in cells:
			if cell is Array:
				var pair: Array = cell
				if pair.size() == 2:
					kept.append([RpgUtil.to_int(pair[0]), RpgUtil.to_int(pair[1])])
		if not kept.is_empty():
			out[str(room)] = kept
	return out

func get_flag(entity_id: String, key: String, default: Variant = null) -> Variant:
	var entry: Variant = flags.get(entity_id)
	if entry is Dictionary:
		var entry_flags: Dictionary = entry
		return entry_flags.get(key, default)
	return default

func set_flag(entity_id: String, key: String, value: Variant) -> void:
	if not flags.has(entity_id):
		flags[entity_id] = {}
	flags[entity_id][key] = value
	RpgUtil.emit(&"entity_state_changed", [entity_id, key, value])

## A variable's value (0 when it was never set).
func get_var(var_name: String) -> int:
	return RpgUtil.to_int(variables.get(var_name, 0))

func set_var(var_name: String, value: int) -> void:
	if var_name == "":
		return
	variables[var_name] = value
	RpgUtil.emit(&"variable_changed", [StringName(var_name), value])

## Adds `amount` (negative to subtract) and returns the new value.
func add_var(var_name: String, amount: int) -> int:
	set_var(var_name, get_var(var_name) + amount)
	return get_var(var_name)

# ------------------------------------------------------------------ equipment (T12.45)

## The slot an item is worn in, or &"" when it cannot be equipped.
static func slot_of(def: RpgItemDefinition) -> StringName:
	if def == null:
		return &""
	match def.category:
		RpgItemDefinition.Category.WEAPON:
			return &"weapon"
		RpgItemDefinition.Category.ARMOR:
			return &"armor"
		RpgItemDefinition.Category.ACCESSORY:
			return &"accessory"
	return &""

## The item worn in `slot` by the actor, or &"".
func equipped_in(actor_id: StringName, slot: StringName) -> StringName:
	var worn: Variant = equipment.get(String(actor_id))
	if worn is Dictionary:
		var worn_slots: Dictionary = worn
		return StringName(str(worn_slots.get(String(slot), "")))
	return &""

## {slot: item id} for every slot (&"" for an empty one).
func equipped_items(actor_id: StringName) -> Dictionary:
	var out: Dictionary = {}
	for slot in EQUIP_SLOTS:
		out[slot] = equipped_in(actor_id, slot)
	return out

## The `modifiers` of everything the actor wears, the bonuses of the sets it wears enough of and
## what it learned in skill trees (1.5.0): what every get_stat call takes.
func equipped_modifiers(actor_id: StringName, replacing: Dictionary = {}) -> Array:
	var out: Array = []
	var pieces: Dictionary = {}  # set id -> pieces worn
	for slot in EQUIP_SLOTS:
		var item_id := equipped_in(actor_id, slot)
		if replacing.has(slot):
			item_id = StringName(str(replacing[slot]))
		var def: RpgItemDefinition = items.get(item_id)
		if def != null:
			out.append_array(def.modifiers)
			if def.set_id != &"":
				pieces[def.set_id] = RpgUtil.to_int(pieces.get(def.set_id, 0)) + 1
	for set_id: StringName in pieces:
		var item_set := item_set_of(set_id)
		if item_set != null:
			out.append_array(item_set.modifiers_for(RpgUtil.to_int(pieces[set_id])))
	if not skill_ranks.is_empty():
		out.append_array(learned_modifiers(actor_id))  # what its skill trees give (1.5.0)
	return out

## The set with this id (game/data/item_sets/<id>.tres), or null.
func item_set_of(set_id: StringName) -> RpgItemSet:
	if item_sets.has(set_id):
		var known: RpgItemSet = item_sets[set_id]
		return known
	var path := "%s/%s.tres" % [ITEM_SETS_DIR, set_id]
	if set_id == &"" or not ResourceLoader.exists(path):
		return null
	var found := load(path) as RpgItemSet
	if found != null:
		item_sets[set_id] = found
	return found

## The sets the actor wears pieces of: [{set_id, worn, bonus_at}] (bonus_at: the fewest pieces that
## give a bonus), in slot order.
func worn_sets(actor_id: StringName) -> Array[Dictionary]:
	var order: Array[StringName] = []
	var worn: Dictionary = {}  # set id -> pieces
	for slot in EQUIP_SLOTS:
		var def: RpgItemDefinition = items.get(equipped_in(actor_id, slot))
		if def != null and def.set_id != &"":
			if not worn.has(def.set_id):
				order.append(def.set_id)
			worn[def.set_id] = RpgUtil.to_int(worn.get(def.set_id, 0)) + 1
	var out: Array[Dictionary] = []
	for set_id in order:
		var item_set := item_set_of(set_id)
		out.append({"set_id": set_id, "worn": worn[set_id], "bonus_at": item_set.first_bonus_at() if item_set != null else 0})
	return out

## The actor's stats: the player's, or a party member's.
func stats_of(actor_id: StringName) -> RpgStats:
	if actor_id == player_actor_id:
		return player_stats
	for member in party:
		if member["actor_id"] == actor_id:
			var member_stats: RpgStats = member["stats"]
			return member_stats
	return null

## The id of the actor that owns `stats` (&"" for an enemy or an unknown copy).
func actor_of(stats: RpgStats) -> StringName:
	if stats == null:
		return &""
	if stats == player_stats:
		return player_actor_id
	for member in party:
		if member["stats"] == stats:
			var member_id: StringName = member["actor_id"]
			return member_id
	return &""

## A stat with the actor's equipment applied. Combat reads attack and defense through this.
func stat_of(actor_id: StringName, stat_name: StringName) -> float:
	var stats := stats_of(actor_id)
	return stats.get_stat(stat_name, equipped_modifiers(actor_id)) if stats != null else 0.0

## Same, for a stats object (the combat code holds the stats, not the actor id).
func effective_stat(stats: RpgStats, stat_name: StringName) -> float:
	var actor_id := actor_of(stats)
	if actor_id == &"":
		return stats.get_stat(stat_name) if stats != null else 0.0
	return stats.get_stat(stat_name, equipped_modifiers(actor_id))

## Walking speed relative to the base move_speed (1.0 without equipment or for anyone but the
## actors that wear some).
func move_speed_factor(stats: RpgStats) -> float:
	if equipment.is_empty() or stats == null or stats.move_speed <= 0.0:
		return 1.0
	return effective_stat(stats, &"move_speed") / stats.move_speed

## How each stat would change if `item_id` replaced what is worn in its slot (&"" takes the slot's
## item off): {stat: delta}, only the stats that change.
func equip_preview(actor_id: StringName, slot: StringName, item_id: StringName) -> Dictionary:
	var stats := stats_of(actor_id)
	var out: Dictionary = {}
	if stats == null:
		return out
	var before := equipped_modifiers(actor_id)
	var after := equipped_modifiers(actor_id, {slot: item_id})
	for stat_name in PREVIEW_STATS:
		var delta := stats.get_stat(stat_name, after) - stats.get_stat(stat_name, before)
		if absf(delta) > 0.0001:
			out[stat_name] = delta
	return out

## Moves one `item_id` from the inventory into its slot; what was worn there goes back to the
## inventory. False (and nothing changes) when the item cannot be worn, is not held, or the old
## piece has nowhere to go.
func equip(actor_id: StringName, item_id: StringName) -> bool:
	var def: RpgItemDefinition = items.get(item_id)
	var slot := slot_of(def)
	if slot == &"" or stats_of(actor_id) == null or not inventory.has(item_id):
		return false
	var old := equipped_in(actor_id, slot)
	var old_data := worn_data_of(actor_id, slot)
	_moving_gear = true
	var data := RpgUtil.to_dict(inventory.take_one(item_id))
	if old != &"" and not inventory.add_with(old, old_data):
		inventory.add_with(item_id, data)
		_moving_gear = false
		return false
	_moving_gear = false
	_set_worn(actor_id, slot, item_id, data)
	return true

## Takes the piece in `slot` off, into the inventory. False when the slot is empty or the inventory
## is full.
func unequip(actor_id: StringName, slot: StringName) -> bool:
	var old := equipped_in(actor_id, slot)
	_moving_gear = true
	var moved := old != &"" and inventory.add_with(old, worn_data_of(actor_id, slot))
	_moving_gear = false
	if not moved:
		return false
	_set_worn(actor_id, slot, &"")
	return true

## The data of the piece worn in `slot` ({} for a plain one or an empty slot).
func worn_data_of(actor_id: StringName, slot: StringName) -> Dictionary:
	return RpgUtil.to_dict(RpgUtil.to_dict(worn_data.get(String(actor_id), {})).get(String(slot), {}))

## How much wear the piece in `slot` has taken, and what it can take: [wear, durability]
## (durability 0: it never wears).
func wear_of(actor_id: StringName, slot: StringName) -> Array[int]:
	var def: RpgItemDefinition = items.get(equipped_in(actor_id, slot))
	var out: Array[int] = [RpgUtil.to_int(worn_data_of(actor_id, slot).get("wear", 0)), def.durability if def != null else 0]
	return out

## Wears the piece the actor has in `slot` by `amount` (1.5.0). Only an item with a `durability`
## wears; when its wear reaches it, it breaks: it is gone from the slot (a toast says so). True
## when it broke.
func wear(actor_id: StringName, slot: StringName, amount: int = 1) -> bool:
	var item_id := equipped_in(actor_id, slot)
	var def: RpgItemDefinition = items.get(item_id)
	if def == null or def.durability <= 0 or amount <= 0:
		return false
	var data := worn_data_of(actor_id, slot).duplicate(true)
	data["wear"] = RpgUtil.to_int(data.get("wear", 0)) + amount
	if RpgUtil.to_int(data["wear"]) < def.durability:
		_set_worn_data(actor_id, slot, data)
		return false
	_set_worn(actor_id, slot, &"")
	RpgUtil.notify(RpgStrings.format("UI_ITEM_BROKE", _item_label(item_id, 1)))
	return true

## Takes away the wear of the piece in `slot` (a shop's repair, 1.5.0). False when it has none.
func mend(actor_id: StringName, slot: StringName) -> bool:
	var data := worn_data_of(actor_id, slot).duplicate(true)
	if RpgUtil.to_int(data.get("wear", 0)) <= 0:
		return false
	data.erase("wear")
	_set_worn_data(actor_id, slot, data)
	return true

## What a hit taken wears: the armour and the accessory.
const WEAR_ON_HIT: Array[StringName] = [&"armor", &"accessory"]

## A hit taken by the owner of `stats`: wears what WEAR_ON_HIT names.
func wear_from_hit(stats: RpgStats) -> void:
	for slot in WEAR_ON_HIT:
		wear_stats(stats, slot)

## wear() for the owner of `stats` (the combat code holds the stats): nothing for an enemy.
func wear_stats(stats: RpgStats, slot: StringName, amount: int = 1) -> bool:
	var actor_id := actor_of(stats)
	return wear(actor_id, slot, amount) if actor_id != &"" else false

func _set_worn_data(actor_id: StringName, slot: StringName, data: Dictionary) -> void:
	var key := String(actor_id)
	var per_slot := RpgUtil.to_dict(worn_data.get(key, {})).duplicate(true)
	if data.is_empty():
		per_slot.erase(String(slot))
	else:
		per_slot[String(slot)] = data.duplicate(true)
	if per_slot.is_empty():
		worn_data.erase(key)
	else:
		worn_data[key] = per_slot

func _set_worn(actor_id: StringName, slot: StringName, item_id: StringName, data: Dictionary = {}) -> void:
	_set_worn_data(actor_id, slot, data if item_id != &"" else {})
	var key := String(actor_id)
	var old_hp := 0
	if stats_of(actor_id) != null:
		old_hp = stats_of(actor_id).hp
	if not equipment.has(key) or not (equipment[key] is Dictionary):
		equipment[key] = {}
	var worn: Dictionary = equipment[key]
	if item_id == &"":
		worn.erase(String(slot))
	else:
		worn[String(slot)] = String(item_id)
	# A smaller max_hp pulls the current hp down with it; a larger one does not heal.
	var worn_stats := stats_of(actor_id)
	if worn_stats != null:
		worn_stats.hp = mini(worn_stats.hp, RpgUtil.max_hp(worn_stats))
		worn_stats.mp = mini(worn_stats.mp, RpgUtil.max_mp(worn_stats))
		if worn_stats.hp <= 0 and old_hp > 0:
			worn_stats.hp = 1
	RpgUtil.emit(&"equipment_changed", [actor_id, slot])

# ------------------------------------------------------------------ party (T12.47)

## The definition of an actor: game/data/actors/<id>.tres (hero.tres for the player), or null.
func actor_definition(actor_id: StringName) -> RpgActorDefinition:
	if actor_defs.has(actor_id):
		var known: RpgActorDefinition = actor_defs[actor_id]
		return known
	var path := HERO_PATH if actor_id == player_actor_id else "%s/%s.tres" % [ACTORS_DIR, actor_id]
	if actor_id == &"" or not ResourceLoader.exists(path):
		return null
	var def := load(path) as RpgActorDefinition
	if def != null:
		actor_defs[actor_id] = def
	return def

## The name shown for an actor: its definition's display name (a translation key), else its id.
func actor_name(actor_id: StringName) -> String:
	var def := actor_definition(actor_id)
	var shown := def.display_name if def != null and def.display_name != "" else ""
	return String(TranslationServer.translate(shown)) if shown != "" else String(actor_id).capitalize()

## The player first, then the members: everyone who fights.
func party_ids() -> Array[StringName]:
	var out: Array[StringName] = [player_actor_id]
	for member in party:
		var member_id: StringName = member["actor_id"]
		out.append(member_id)
	return out

func in_party(actor_id: StringName) -> bool:
	return party_ids().has(actor_id)

## Adds a character (game/data/actors/<id>.tres) at its starting stats. False when it is already in
## the party, the party is full (MAX_PARTY, the player counted) or there is no such actor.
func join_party(actor_id: StringName) -> bool:
	if actor_id == &"" or in_party(actor_id) or party.size() + 1 >= MAX_PARTY:
		return false
	var def := actor_definition(actor_id)
	if def == null:
		push_error("[RPG-DATA] join_party: no actor definition for '%s'" % actor_id)
		return false
	var member_stats := RpgStats.new()
	if def.base_stats != null:
		member_stats = def.base_stats.duplicate(true) as RpgStats
	party.append({"actor_id": actor_id, "stats": member_stats})
	member_stats.hp = RpgUtil.max_hp(member_stats)  # what they wear (kept from an earlier stay) counts
	member_stats.mp = RpgUtil.max_mp(member_stats)
	RpgUtil.notify(RpgStrings.format("UI_PARTY_JOINED", actor_name(actor_id)))
	RpgUtil.emit(&"party_changed")
	return true

## Removes a member; what they wore goes back to the inventory (what does not fit stays with them
## until they come back). The player cannot leave. False when the character is not a member.
func leave_party(actor_id: StringName) -> bool:
	for i in party.size():
		if party[i]["actor_id"] != actor_id:
			continue
		for slot in EQUIP_SLOTS:
			unequip(actor_id, slot)
		party.remove_at(i)
		RpgUtil.notify(RpgStrings.format("UI_PARTY_LEFT", actor_name(actor_id)))
		RpgUtil.emit(&"party_changed")
		return true
	return false

## Nobody is left at 0 hit points once a battle is over.
func revive_party() -> void:
	player_stats.hp = maxi(1, player_stats.hp)
	for member in party:
		var member_stats: RpgStats = member["stats"]
		member_stats.hp = maxi(1, member_stats.hp)

## Full hit and magic points (equipment counted) for the player and every member.
func heal_party_full() -> void:
	player_stats.hp = RpgUtil.max_hp(player_stats)
	player_stats.mp = RpgUtil.max_mp(player_stats)
	for member in party:
		var member_stats: RpgStats = member["stats"]
		member_stats.hp = RpgUtil.max_hp(member_stats)
		member_stats.mp = RpgUtil.max_mp(member_stats)

func flag_count() -> int:
	var n := 0
	for entity_flags: Dictionary in flags.values():
		n += entity_flags.size()
	return n

## Grants experience to the player and every party member (experience is shared) and emits the
## progression events. Returns the player's levels gained.
func give_experience(amount: int) -> int:
	var gained := give_experience_to(player_actor_id, amount)
	for member: Dictionary in party.duplicate():
		var member_id: StringName = member["actor_id"]
		give_experience_to(member_id, amount)
	return gained

## Grants experience to one actor; a level-up refills their hit and magic points (equipment counted). Returns
## the levels gained (0 for an unknown actor).
func give_experience_to(actor_id: StringName, amount: int) -> int:
	var actor_stats := stats_of(actor_id)
	if actor_stats == null:
		return 0
	var gained := actor_stats.add_experience(amount)
	if gained > 0:
		actor_stats.hp = RpgUtil.max_hp(actor_stats)  # the level-up refill counts the equipment
		actor_stats.mp = RpgUtil.max_mp(actor_stats)
	if gained > 0 and not skill_trees.is_empty():
		give_skill_points(actor_id, gained * skill_points_per_level)
	RpgUtil.emit(&"experience_gained", [actor_id, amount])
	for i in gained:
		RpgUtil.emit(&"level_up", [actor_id, actor_stats.level - gained + i + 1])
	return gained

func to_dict() -> Dictionary:
	return {
		"player_actor_id": String(player_actor_id),
		"player_stats": player_stats.to_dict(),
		"party": _party_to_array(),
		"inventory": inventory.to_array(),
		"gold": gold,
		"current_map": current_map,
		"current_spawn": String(current_spawn),
		"player_position": [player_position.x, player_position.y],
		"player_facing": player_facing,
		"flags": flags.duplicate(true),
		"variables": variables.duplicate(true),
		"quests": quests.duplicate(true),
		"equipment": equipment.duplicate(true),
		"playtime_s": playtime_s,
		"rng": rng.get_state(),
	}.merged({"map_fog": _fog_to_dict()} if not map_fog.is_empty() else {}).merged({"tracked_quest": String(tracked_quest)} if tracked_quest != &"" else {}).merged({"shops": shops.duplicate(true)} if not shops.is_empty() else {}).merged({"pending_items": pending_items.duplicate(true)} if not pending_items.is_empty() else {}).merged({"worn_data": worn_data.duplicate(true)} if not worn_data.is_empty() else {}).merged(_progress_keys()).merged(_side_view_keys()).merged(_calendar_key()).merged(_friendship_key())

## The optional keys of skill trees and achievements (1.5.0): only what holds something.
func _progress_keys() -> Dictionary:
	var out := {}
	if not skill_ranks.is_empty():
		out["skill_ranks"] = skill_ranks.duplicate(true)
	if not skill_points.is_empty():
		out["skill_points"] = skill_points.duplicate(true)
	if not achievements.is_empty():
		out["achievements"] = achievements.keys()
	if not counters.is_empty():
		out["counters"] = counters.duplicate(true)
	return out

## The `calendar` key of a save (T17.03): written only by a game that has a calendar, so the save
## of every other game has exactly the keys it had.
func _calendar_key() -> Dictionary:
	var calendar := RpgCalendar.current()
	return {RpgCalendar.SAVE_KEY: calendar.to_dict()} if calendar != null else {}

## The friendships of a farm (T17.09): the child `Friendship` its mode makes (RpgFriendship,
## which only a farm's project has, so it is found by its name), or null.
func _friendship() -> Node:
	var node := get_node_or_null(FRIENDSHIP_NODE)
	return node if node != null and node.has_method(&"to_dict") else null

## The `friendship` key of a save: written only by a game that has friendships.
func _friendship_key() -> Dictionary:
	var friendship := _friendship()
	return {FRIENDSHIP_KEY: friendship.call(&"to_dict")} if friendship != null else {}

## The save keys of the metroidvania, written only when there is something to write, so a
## top-down save has exactly the keys it had in 1.1.
func _side_view_keys() -> Dictionary:
	var out: Dictionary = {}
	if not abilities.is_empty():
		out["abilities"] = abilities.duplicate()
	if not broken_cells.is_empty():
		out["broken_cells"] = broken_cells.duplicate(true)
	if not room_fog.is_empty():
		out["room_fog"] = room_fog.duplicate()
	return out

func from_dict(d: Dictionary) -> void:
	var data: Dictionary = RpgUtil.restore_numbers(d)
	player_actor_id = StringName(str(data.get("player_actor_id", "hero")))
	var stats_data: Dictionary = data.get("player_stats", {})
	player_stats = RpgStats.from_dict(stats_data)
	party.clear()
	var party_data: Array = data.get("party", [])
	for entry: Dictionary in party_data:
		if str(entry.get("actor_id", "")) == "" or party.size() + 1 >= MAX_PARTY:
			continue
		var member_data: Dictionary = entry.get("stats", {})
		party.append({"actor_id": StringName(str(entry.get("actor_id", ""))), "stats": RpgStats.from_dict(member_data)})
	var inventory_data: Array = data.get("inventory", [])
	inventory.load_array(inventory_data)
	gold = RpgUtil.to_int(data.get("gold", 0))
	current_map = str(data.get("current_map", ""))
	current_spawn = StringName(str(data.get("current_spawn", "default")))
	var pos: Array = data.get("player_position", [0, 0])
	player_position = Vector2(RpgUtil.to_float(pos[0]), RpgUtil.to_float(pos[1]))
	player_facing = str(data.get("player_facing", "down"))
	var flags_data: Dictionary = data.get("flags", {})
	flags = flags_data.duplicate(true)
	variables = _variables_from(data.get("variables", {}))
	var quests_data: Dictionary = data.get("quests", {})
	quests = quests_data.duplicate(true)
	tracked_quest = StringName(str(data.get("tracked_quest", "")))  # optional: older saves track none
	shops = RpgUtil.to_dict(data.get("shops", {})).duplicate(true)  # optional: every shop as stocked
	pending_items.clear()  # optional: nothing waits
	for raw: Variant in RpgUtil.to_array(data.get("pending_items", [])):
		var row := RpgUtil.to_dict(raw)
		if str(row.get("item_id", "")) != "" and RpgUtil.to_int(row.get("qty", 0)) > 0:
			pending_items.append({"item_id": str(row["item_id"]), "qty": RpgUtil.to_int(row["qty"])})
	worn_data = RpgUtil.to_dict(data.get("worn_data", {})).duplicate(true)  # optional: nothing worn
	skill_ranks = RpgUtil.to_dict(data.get("skill_ranks", {})).duplicate(true)  # optional: nothing learned
	skill_points = RpgUtil.to_dict(data.get("skill_points", {})).duplicate(true)
	achievements.clear()  # optional: nothing unlocked
	for achievement_id: Variant in RpgUtil.to_array(data.get("achievements", [])):
		achievements[str(achievement_id)] = true
	counters = RpgUtil.to_dict(data.get("counters", {})).duplicate(true)
	equipment = _equipment_from(data.get("equipment", {}))
	playtime_s = RpgUtil.to_float(data.get("playtime_s", 0.0))
	var rng_data: Dictionary = data.get("rng", {})
	rng.set_state(rng_data)
	map_fog = _fog_from(d.get("map_fog", {}))
	abilities = _abilities_from(data.get("abilities"))
	broken_cells = _broken_cells_from(data.get("broken_cells"))
	room_fog = _room_fog_from(data.get("room_fog"))
	var calendar := RpgCalendar.current()
	if calendar != null:  # a save without the key is the first morning
		calendar.from_dict(data.get(RpgCalendar.SAVE_KEY))
	var friendship := _friendship()
	if friendship != null:  # a save without the key: nobody is met
		friendship.call(&"from_dict", data.get(FRIENDSHIP_KEY))

## The optional `variables` key of a save: whole numbers by name; anything else is dropped.
static func _variables_from(raw: Variant) -> Dictionary:
	var out: Dictionary = {}
	if not (raw is Dictionary):
		return out
	var table: Dictionary = raw
	for key: Variant in table:
		if typeof(table[key]) in [TYPE_INT, TYPE_FLOAT]:
			out[str(key)] = RpgUtil.to_int(table[key])
	return out

## The optional `equipment` key of a save: anything that is not {actor: {slot: item}} is dropped,
## so an old save (no key) loads with empty slots.
static func _equipment_from(raw: Variant) -> Dictionary:
	var out: Dictionary = {}
	if not (raw is Dictionary):
		return out
	var by_actor: Dictionary = raw
	for actor_key: Variant in by_actor:
		var worn: Variant = by_actor[actor_key]
		if not (worn is Dictionary):
			continue
		var worn_slots: Dictionary = worn
		var kept: Dictionary = {}
		for slot in EQUIP_SLOTS:
			var item_id := str(worn_slots.get(String(slot), ""))
			if item_id != "":
				kept[String(slot)] = item_id
		if not kept.is_empty():
			out[str(actor_key)] = kept
	return out

func _party_to_array() -> Array:
	var out: Array = []
	for member in party:
		var member_stats: RpgStats = member["stats"]
		out.append({"actor_id": RpgUtil.to_str(member["actor_id"]), "stats": member_stats.to_dict()})
	return out

func _process(delta: float) -> void:
	if get_tree().paused:
		return
	var router := RpgUtil.router()
	if router != null and router.get("current_map") != null:
		playtime_s += delta
