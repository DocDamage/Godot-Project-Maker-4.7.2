extends Node
## Autoload "GameState": everything that is saved.

const ITEMS_DIR := "res://game/data/items"
const HERO_PATH := "res://game/data/actors/hero.tres"
const NEW_GAME_PATH := "res://game/data/new_game.tres"

var player_actor_id: StringName = &"hero"
var player_stats: RpgStats = RpgStats.new()
var party: Array[Dictionary] = []  # reserved; [{actor_id, stats}] (turn-based may use)
var inventory := RpgInventory.new()
var gold: int = 0:
	set = set_gold
var current_map: String = ""
var current_spawn: StringName = &"default"
var player_position := Vector2.ZERO
var player_facing := "down"
var flags: Dictionary = {}  # entity_id -> {key: value}
var quests: Dictionary = {}
var playtime_s: float = 0.0
var pending_encounter: RpgEncounterData = null
var rng: RpgRng = RpgRng.new()
var items: Dictionary = {}  # item id -> RpgItemDefinition

func _ready() -> void:
	inventory.registry = items
	rng.seed_from_config()
	load_items()

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
	quests.clear()
	playtime_s = 0.0
	pending_encounter = null
	gold = data.gold
	for entry in data.items:
		inventory.add(StringName(str(entry.get("item_id", ""))), int(entry.get("qty", 1)))
	current_map = data.start_map
	current_spawn = data.start_spawn
	player_position = Vector2.ZERO
	player_facing = "down"
	rng.seed_from_config()

func get_flag(entity_id: String, key: String, default: Variant = null) -> Variant:
	var entry: Variant = flags.get(entity_id)
	if entry is Dictionary:
		return entry.get(key, default)
	return default

func set_flag(entity_id: String, key: String, value: Variant) -> void:
	if not flags.has(entity_id):
		flags[entity_id] = {}
	flags[entity_id][key] = value
	RpgUtil.emit(&"entity_state_changed", [entity_id, key, value])

func flag_count() -> int:
	var n := 0
	for entity_id in flags.keys():
		n += (flags[entity_id] as Dictionary).size()
	return n

## Grants experience to the player and emits the progression events.
func give_experience(amount: int) -> int:
	var gained := player_stats.add_experience(amount)
	RpgUtil.emit(&"experience_gained", [player_actor_id, amount])
	for i in gained:
		RpgUtil.emit(&"level_up", [player_actor_id, player_stats.level - gained + i + 1])
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
		"quests": quests.duplicate(true),
		"playtime_s": playtime_s,
		"rng": rng.get_state(),
	}

func from_dict(d: Dictionary) -> void:
	var data: Dictionary = RpgUtil.restore_numbers(d)
	player_actor_id = StringName(str(data.get("player_actor_id", "hero")))
	player_stats = RpgStats.from_dict(data.get("player_stats", {}))
	party.clear()
	for entry in data.get("party", []):
		party.append({"actor_id": StringName(str(entry.get("actor_id", ""))), "stats": RpgStats.from_dict(entry.get("stats", {}))})
	inventory.load_array(data.get("inventory", []))
	gold = int(data.get("gold", 0))
	current_map = str(data.get("current_map", ""))
	current_spawn = StringName(str(data.get("current_spawn", "default")))
	var pos: Array = data.get("player_position", [0, 0])
	player_position = Vector2(float(pos[0]), float(pos[1]))
	player_facing = str(data.get("player_facing", "down"))
	flags = (data.get("flags", {}) as Dictionary).duplicate(true)
	quests = (data.get("quests", {}) as Dictionary).duplicate(true)
	playtime_s = float(data.get("playtime_s", 0.0))
	rng.set_state(data.get("rng", {}))

func _party_to_array() -> Array:
	var out: Array = []
	for member in party:
		out.append({"actor_id": String(member["actor_id"]), "stats": (member["stats"] as RpgStats).to_dict()})
	return out

func _process(delta: float) -> void:
	if get_tree().paused:
		return
	var router := RpgUtil.router()
	if router != null and router.get("current_map") != null:
		playtime_s += delta
