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
## The value of GameState.quests[id] once a quest is finished.
const QUEST_DONE := "done"
const NEW_GAME_PATH := "res://game/data/new_game.tres"
## The equipment slots, in display order. An item goes to the slot of its category.
const EQUIP_SLOTS: Array[StringName] = [&"weapon", &"armor", &"accessory"]
## The stats an equipment preview compares.
const PREVIEW_STATS: Array[StringName] = [&"max_hp", &"attack", &"defense", &"speed", &"magic", &"resistance", &"move_speed"]

var player_actor_id: StringName = &"hero"
var player_stats: RpgStats = RpgStats.new()
## The party members besides the player, in joining order: [{actor_id, stats}]. Only the turn-based
## battle uses them; the action RPG has no followers.
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
## actor id (String) -> {slot: item id (String)}. Keyed by actor from the start so party members
## (T12.47) get their own; a missing actor or slot means nothing is worn.
var equipment: Dictionary = {}
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
	var bus := RpgUtil.events()
	if bus != null:
		for signal_name: StringName in [&"entity_state_changed", &"variable_changed", &"item_added", &"item_removed", &"gold_changed", &"level_up", &"dialogue_finished", &"game_loaded"]:
			if bus.has_signal(signal_name) and not bus.is_connected(signal_name, _on_quest_event):
				bus.connect(signal_name, _on_quest_event)

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

# ------------------------------------------------------------------ quests (T12.48)

func quest_state(quest_id: StringName) -> String:
	return str(quests.get(String(quest_id), ""))

func quest_is_active(quest_id: StringName) -> bool:
	var current := quest_state(quest_id)
	return current != "" and current != QUEST_DONE

func quest_is_done(quest_id: StringName) -> bool:
	return quest_state(quest_id) == QUEST_DONE

func _quest_title(quest_id: StringName) -> String:
	var def: RpgQuestDefinition = quest_defs.get(quest_id)
	return TranslationServer.translate(def.title if def != null and def.title != "" else String(quest_id))

## Starts a quest at its first stage ("active" for a quest without stages or definition). False
## when it was started before.
func quest_start(quest_id: StringName) -> bool:
	if quest_state(quest_id) != "":
		return false
	var def: RpgQuestDefinition = quest_defs.get(quest_id)
	var first := def.first_stage() if def != null else &""
	quests[String(quest_id)] = String(first) if first != &"" else "active"
	RpgUtil.notify(String(TranslationServer.translate("UI_QUEST_NEW")) % _quest_title(quest_id))
	RpgUtil.emit(&"quest_changed", [quest_id, quest_state(quest_id)])
	refresh_quests()
	return true

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
	RpgUtil.notify(String(TranslationServer.translate("UI_QUEST_UPDATED")) % _quest_title(quest_id))
	RpgUtil.emit(&"quest_changed", [quest_id, quest_state(quest_id)])
	refresh_quests()
	return true

## Finishes a quest and gives its rewards, once. A quest that was never started is started and
## finished.
func quest_complete(quest_id: StringName) -> bool:
	if quest_is_done(quest_id):
		return false
	quests[String(quest_id)] = QUEST_DONE
	var def: RpgQuestDefinition = quest_defs.get(quest_id)
	if def != null:
		_give_quest_rewards(def.rewards)
	RpgUtil.notify(String(TranslationServer.translate("UI_QUEST_DONE")) % _quest_title(quest_id))
	RpgUtil.emit(&"quest_changed", [quest_id, QUEST_DONE])
	return true

func _give_quest_rewards(rewards: Dictionary) -> void:
	gold += RpgUtil.to_int(rewards.get("gold", 0))
	var experience := RpgUtil.to_int(rewards.get("experience", 0))
	if experience > 0:
		give_experience(experience)
	var reward_items: Variant = rewards.get("items", [])
	if reward_items is Array:
		var list: Array = reward_items
		for entry: Variant in list:
			if entry is Dictionary:
				var row: Dictionary = entry
				inventory.add(StringName(str(row.get("item_id", ""))), RpgUtil.to_int(row.get("qty", 1)))

var _refreshing_quests := false

func _on_quest_event(_a: Variant = null, _b: Variant = null, _c: Variant = null) -> void:
	refresh_quests()

## Moves every active quest past the stages whose `complete_when` holds; finishing the last stage
## completes the quest. Safe to call at any time (a reward that changes state does not recurse).
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
			if not quest_is_active(quest_id):
				continue
			var def: RpgQuestDefinition = quest_defs[quest_id]
			var index := def.stage_index(StringName(quest_state(quest_id)))
			if index < 0:
				continue
			var condition := str(def.stage(index).get("complete_when", ""))
			if condition == "" or not RpgCondition.evaluate(condition):
				continue
			progressed = true
			if index + 1 >= def.stages.size():
				quest_complete(quest_id)
			else:
				quest_set_stage(quest_id, StringName(str(def.stage(index + 1).get("id", ""))))
	_refreshing_quests = false

## The ids of the defined quests that are active (or finished), in id order.
func journal_ids(finished: bool) -> Array[StringName]:
	var out: Array[StringName] = []
	var ids: Array = quest_defs.keys()
	ids.sort()
	for quest_id: StringName in ids:
		if (quest_is_done(quest_id) if finished else quest_is_active(quest_id)):
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
	party.clear()
	inventory.slots.clear()
	flags.clear()
	variables.clear()
	quests.clear()
	equipment.clear()
	playtime_s = 0.0
	pending_encounter = null
	gold = data.gold
	for entry in data.items:
		inventory.add(StringName(str(entry.get("item_id", ""))), RpgUtil.to_int(entry.get("qty", 1)))
	current_map = data.start_map
	current_spawn = data.start_spawn
	player_position = Vector2.ZERO
	player_facing = "down"
	rng.seed_from_config()

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

## The `modifiers` of everything the actor wears: what every get_stat call takes.
func equipped_modifiers(actor_id: StringName, replacing: Dictionary = {}) -> Array:
	var out: Array = []
	for slot in EQUIP_SLOTS:
		var item_id := equipped_in(actor_id, slot)
		if replacing.has(slot):
			item_id = StringName(str(replacing[slot]))
		var def: RpgItemDefinition = items.get(item_id)
		if def != null:
			out.append_array(def.modifiers)
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
	inventory.remove(item_id, 1)
	if old != &"" and inventory.add(old, 1) == 0:
		inventory.add(item_id, 1)
		return false
	_set_worn(actor_id, slot, item_id)
	return true

## Takes the piece in `slot` off, into the inventory. False when the slot is empty or the inventory
## is full.
func unequip(actor_id: StringName, slot: StringName) -> bool:
	var old := equipped_in(actor_id, slot)
	if old == &"" or inventory.add(old, 1) == 0:
		return false
	_set_worn(actor_id, slot, &"")
	return true

func _set_worn(actor_id: StringName, slot: StringName, item_id: StringName) -> void:
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
	RpgUtil.notify(String(TranslationServer.translate("UI_PARTY_JOINED")) % actor_name(actor_id))
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
		RpgUtil.notify(String(TranslationServer.translate("UI_PARTY_LEFT")) % actor_name(actor_id))
		RpgUtil.emit(&"party_changed")
		return true
	return false

## Nobody is left at 0 hit points once a battle is over.
func revive_party() -> void:
	player_stats.hp = maxi(1, player_stats.hp)
	for member in party:
		var member_stats: RpgStats = member["stats"]
		member_stats.hp = maxi(1, member_stats.hp)

## Full hit points (equipment counted) for the player and every member.
func heal_party_full() -> void:
	player_stats.hp = RpgUtil.max_hp(player_stats)
	for member in party:
		var member_stats: RpgStats = member["stats"]
		member_stats.hp = RpgUtil.max_hp(member_stats)

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

## Grants experience to one actor; a level-up refills their hit points (equipment counted). Returns
## the levels gained (0 for an unknown actor).
func give_experience_to(actor_id: StringName, amount: int) -> int:
	var actor_stats := stats_of(actor_id)
	if actor_stats == null:
		return 0
	var gained := actor_stats.add_experience(amount)
	if gained > 0:
		actor_stats.hp = RpgUtil.max_hp(actor_stats)  # the level-up refill counts the equipment
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
	}

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
	equipment = _equipment_from(data.get("equipment", {}))
	playtime_s = RpgUtil.to_float(data.get("playtime_s", 0.0))
	var rng_data: Dictionary = data.get("rng", {})
	rng.set_state(rng_data)

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
