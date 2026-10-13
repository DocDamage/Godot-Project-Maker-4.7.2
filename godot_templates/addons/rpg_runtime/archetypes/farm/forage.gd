class_name RpgForage
extends Node
## Foraging on a farm (T17.10). A child of the farm's mode (`Forage`), made by it like the
## weather and the end of the day. It also holds the table of the fish (RpgFishing asks it).
##
## * **The places** are the markers `Forage/Spot1` ... `Forage/Spot<n>` of a map (the farm's map
##   recipe writes them where the stored plan says: near the edges of the farm, away from the
##   plot, the paths and the yards). They can be moved, added and taken away in the editor. A
##   farm map made before there were markers gets its places from `generated/data/forage.json`
##   (`spots`, cells of the map `map`).
## * **What lies where** is not stored: the things of a morning follow from the seed of the
##   game (the weather's: the flag `farm_weather.seed`), the map (`map_seed`), the index of the
##   day, the season and the number of places (`forage_of`), so a morning is the same before
##   and after a save, whatever the player did. About CHANCE in a hundred places have
##   something, and one always has. A thing lies there all day and is gone the next morning,
##   when others lie elsewhere.
## * **What was picked up today** is kept in the flags of the game state (`farm_forage.picked`:
##   the index of the day and, for every map, the places), so it is saved with the game.
## * `interact` with a thing (RpgForagePickup) puts it into the inventory; a full bag leaves it.
## * **The table** is `game/data/forage.json` (written once, the user's), then what only
##   `generated/data/forage.json` has: `forage`, entries `{id, name, item, seasons, price,
##   energy}`, and `fish`, entries with `times` (`morning`, `day`, `evening`), `water` (`pond`)
##   and `speed` as well. `energy` is what eating one restores.

## What lies on the map that is shown changed (a morning, a load, a thing picked up).
signal changed
signal picked(item_id: StringName, spot: int)

const NODE_NAME := "Forage"
## The node of a map whose children `Spot<n>` are its places.
const HOLDER := "Forage"
const SPOT_PREFIX := "Spot"
## The user's file of the running game. Set by the farm's mode from its `data_dir`, which the
## recipe gives it: a runtime script names no path of the game itself.
static var user_path := ""
const PLANNED_PATH := "res://generated/data/forage.json"
const FLAG_ENTITY := "farm_forage"
const PICKED_KEY := "picked"
## How many places in a hundred have something on a morning.
const CHANCE := 45
const PICK_SOUND := &"sfx_harvest"

## The things to forage and the fish, in the order of the files.
var things: Array[Dictionary] = []
var fish: Array[Dictionary] = []
## The places of a map that has no markers: its id and the cells (the planned file's).
var planned_map := ""
var planned_spots: Array[Vector2i] = []

var _loaded := false
var _nodes: Dictionary = {}  # spot -> RpgForagePickup
var _positions: Array[Vector2] = []  # of the map that is shown
var _key := ""  # ... and what that map is called (`map_key`)

## The foraging of the running game, or null in a game that is no farm.
static func current() -> RpgForage:
	var mode := RpgFarmMode.current()
	return mode.forage if mode != null else null

## Listens to the calendar, to the maps and to the saves. The mode calls it once the calendar
## exists; a second call changes nothing.
func attach() -> void:
	table()
	var calendar := RpgCalendar.current()
	if calendar != null and not calendar.day_began.is_connected(_on_morning):
		calendar.day_began.connect(_on_morning)
	var bus := RpgUtil.events()
	if bus != null:
		if not bus.map_entered.is_connected(_on_map):
			bus.map_entered.connect(_on_map)
		if not bus.game_loaded.is_connected(_on_loaded):
			bus.game_loaded.connect(_on_loaded)

# ------------------------------------------------------------------ the table

## Reads the files, once. A test gives the entries with `add_lists` instead.
func table() -> void:
	if _loaded:
		return
	_loaded = true
	add_file(user_path)
	add_file(PLANNED_PATH)

## Adds the entries of a file that are not there yet, and its places when it names any. A file
## that is missing adds nothing.
func add_file(path: String) -> void:
	if not FileAccess.file_exists(path):
		return
	var data := RpgUtil.to_dict(RpgUtil.restore_numbers(JSON.parse_string(FileAccess.get_file_as_string(path))))
	add_lists(RpgUtil.to_array(data.get("forage", [])), RpgUtil.to_array(data.get("fish", [])))
	if planned_spots.is_empty():
		planned_map = RpgUtil.to_str(data.get("map", ""))
		for raw: Variant in RpgUtil.to_array(data.get("spots", [])):
			var pair := RpgUtil.to_array(raw)
			if pair.size() == 2:
				planned_spots.append(Vector2i(RpgUtil.to_int(pair[0]), RpgUtil.to_int(pair[1])))

## Adds entries (what a test has instead of a file). One without an id or an item, or whose id
## is there already, is left out.
func add_lists(forage_entries: Array, fish_entries: Array) -> void:
	_loaded = true
	for pair: Array in [[forage_entries, things], [fish_entries, fish]]:
		var into: Array[Dictionary] = pair[1]
		for raw: Variant in RpgUtil.to_array(pair[0]):
			var entry := RpgUtil.to_dict(raw)
			var id := RpgUtil.to_str(entry.get("id", ""))
			if id == "" or RpgUtil.to_str(entry.get("item", "")) == "" or _has(id):
				continue
			into.append(entry)

func _has(id: String) -> bool:
	for entry in things + fish:
		if RpgUtil.to_str(entry.get("id", "")) == id:
			return true
	return false

## The entry of a fish, or {}.
func fish_entry(fish_id: String) -> Dictionary:
	for entry in fish:
		if RpgUtil.to_str(entry.get("id", "")) == fish_id:
			return entry
	return {}

## What eating one of an item restores when it is a thing to forage or a fish, else 0.
func energy_of(item_id: StringName) -> int:
	for entry in things + fish:
		if RpgUtil.to_str(entry.get("item", "")) == String(item_id):
			return maxi(0, RpgUtil.to_int(entry.get("energy", 0)))
	return 0

## True when an entry is there in the season of this name. One that names no season always is.
static func in_season(entry: Dictionary, season_name: String) -> bool:
	var seasons := RpgUtil.to_array(entry.get("seasons", []))
	return seasons.is_empty() or seasons.has(season_name)

# ------------------------------------------------------------------ the things of a morning

## A number from 0 to 99 that follows from a seed, the index of a day, a place and what is
## asked (`salt`), and from nothing else.
static func roll(game_seed: int, day: int, spot: int, salt: int) -> int:
	var mixed := (game_seed & RpgFarmWeather.MASK) ^ ((spot + 1) * 40503) ^ ((salt + 1) * 9973 << 8)
	return RpgFarmWeather.roll(mixed, day)

## The places (0 to `count` - 1) that have something on the morning of a day, in their order:
## each with CHANCE in a hundred, and when none has, one all the same.
static func places_of(game_seed: int, day: int, count: int) -> Array[int]:
	var out: Array[int] = []
	for spot in maxi(0, count):
		if roll(game_seed, day, spot, 0) < CHANCE:
			out.append(spot)
	if out.is_empty() and count > 0:
		out.append(roll(game_seed, day, count, 1) % count)
	return out

## What lies where on the morning of a day: place -> item id, for a game with this seed, in
## the season of this name, on a map with `count` places. `entries` are the things to forage.
## A season in which nothing lies gives {}.
static func forage_of(entries: Array, game_seed: int, day: int, season_name: String, count: int) -> Dictionary:
	var out := {}
	var found: Array[String] = []
	for raw: Variant in entries:
		var entry := RpgUtil.to_dict(raw)
		if in_season(entry, season_name):
			found.append(RpgUtil.to_str(entry.get("item", "")))
	if found.is_empty():
		return out
	for spot in places_of(game_seed, day, count):
		out[spot] = StringName(found[roll(game_seed, day, spot, 2) % found.size()])
	return out

## The seed the things of this game follow from: the weather's.
func game_seed() -> int:
	var mode := get_parent() as RpgFarmMode
	var weather := mode.weather if mode != null else RpgFarmWeather.current()
	return weather.game_seed() if weather != null else 0

## What a map is called here: its `map_id`, else the name of its node.
static func map_key(map: Node) -> String:
	if map == null:
		return ""
	var id: Variant = map.get("map_id")
	return str(id) if id != null and str(id) != "" else String(map.name)

## The seed of the things of one map of a game: every map has mornings of its own.
static func map_seed(of_game: int, key: String) -> int:
	return (of_game ^ key.hash()) & RpgFarmWeather.MASK

## What lay this morning on the map that is shown, which has `count` places: place -> item id.
func morning(count: int) -> Dictionary:
	table()
	var calendar := RpgCalendar.current()
	if calendar == null:
		return {}
	return forage_of(things, map_seed(game_seed(), _key), calendar.today(), calendar.season_name(), count)

func _picked() -> Dictionary:
	var state := RpgUtil.state()
	var calendar := RpgCalendar.current()
	if state == null or calendar == null:
		return {}
	var kept := RpgUtil.to_dict(state.get_flag(FLAG_ENTITY, PICKED_KEY, {}))
	if RpgUtil.to_int(kept.get("day", -1), -1) != calendar.today():
		return {}
	return RpgUtil.to_dict(kept.get("spots", {}))

## The places of the map that is shown whose thing was picked up today.
func picked_today() -> Array[int]:
	var out: Array[int] = []
	for raw: Variant in RpgUtil.to_array(_picked().get(_key, [])):
		out.append(RpgUtil.to_int(raw))
	return out

## What still lies on the map that is shown, which has `count` places: this morning's things
## without the ones that were picked up.
func lying(count: int) -> Dictionary:
	var out := morning(count)
	for spot in picked_today():
		out.erase(spot)
	return out

# ------------------------------------------------------------------ the map

## Where the places of a map are, in the world: its markers `Forage/Spot<n>` by their number,
## else, for the map the planned file names, the cells of that file.
func places_on(map: Node) -> Array[Vector2]:
	var out: Array[Vector2] = []
	if map == null:
		return out
	var holder := map.get_node_or_null(HOLDER)
	if holder != null:
		var numbered := {}
		for child in holder.get_children():
			var marker := child as Node2D
			var number := String(child.name).trim_prefix(SPOT_PREFIX)
			if marker != null and String(child.name).begins_with(SPOT_PREFIX) and number.is_valid_int():
				numbered[int(number)] = RpgUtil.world_position(marker)
		var order: Array = numbered.keys()
		order.sort()
		for number: int in order:
			out.append(numbered[number])
		return out
	table()
	var field := _field_of(map)
	if field == null or planned_map == "" or map_key(map) != planned_map:
		return out
	for cell in planned_spots:
		out.append(field.cell_center(cell))
	return out

func _field_of(map: Node) -> RpgField:
	for child in map.get_children():
		if child is RpgField:
			return child
	return null

func _shown_map() -> Node:
	var router := RpgUtil.router()
	return router.current_map if router != null else null

## Puts what lies on `map` today where it lies (the map that is shown when null), and takes
## away what no longer does. Returns how many things lie there.
func refresh(map: Node = null) -> int:
	if map == null:
		map = _shown_map()
	for old: Variant in _nodes.values():  # the things of a map that is gone went with it
		if is_instance_valid(old) and old is Node:
			var thing: Node = old
			thing.queue_free()
	_nodes.clear()
	_key = map_key(map)
	_positions = places_on(map)
	if map == null or _positions.is_empty():
		changed.emit()
		return 0
	var parent := map.get_node_or_null("YSorted/Entities")
	if parent == null:
		parent = map
	var tile := RpgUtil.map_tile_px(map)
	var diamond := RpgIso.footprint_of(map)
	var there := lying(_positions.size())
	for spot: int in there.keys():
		var item: StringName = there[spot]
		var node := RpgForagePickup.make(spot, item, tile, RpgForagePickup.FALLBACK, diamond)
		node.taken.connect(pick)
		parent.add_child(node)
		# its foot is the bottom of its cell, or the middle of its diamond
		var foot := _positions[spot] + Vector2(0.0, tile * 0.5 - 1.0)
		if diamond != Vector2i.ZERO:
			foot = _positions[spot]
		if node.is_inside_tree():
			node.global_position = foot
		else:
			node.position = foot
		_nodes[spot] = node
	changed.emit()
	return _nodes.size()

## The thing that lies at a place of the map that is shown, or null.
func thing_at(spot: int) -> RpgForagePickup:
	var found: Variant = _nodes.get(spot)
	if not is_instance_valid(found):
		return null
	var node: RpgForagePickup = found
	return node if not node.is_queued_for_deletion() else null

## The places of the map that is shown at which something lies, in their order.
func shown() -> Array[int]:
	var out: Array[int] = []
	for spot: int in _nodes.keys():
		if thing_at(spot) != null:
			out.append(spot)
	out.sort()
	return out

## Picks up the thing of a place into the inventory. False, and it stays, when nothing lies
## there or the bag has no room.
func pick(spot: int) -> bool:
	var state := RpgUtil.state()
	var calendar := RpgCalendar.current()
	var there := lying(_positions.size())
	if state == null or calendar == null or not there.has(spot):
		return false
	var item: StringName = there[spot]
	if state.inventory.room_for(item) < 1:
		RpgUtil.notify(RpgFarmStrings.t("FARM_FULL"))
		return false
	state.inventory.add(item, 1)
	var gone := picked_today()
	gone.append(spot)
	var plain: Array = []
	plain.assign(gone)
	var by_map := _picked()
	by_map[_key] = plain
	state.set_flag(FLAG_ENTITY, PICKED_KEY, {"day": calendar.today(), "spots": by_map})
	var node := thing_at(spot)
	if node != null:
		node.queue_free()
	_nodes.erase(spot)
	RpgMenuUtil.play_ui(PICK_SOUND)
	RpgUtil.notify(RpgFarmStrings.t("FARM_FORAGED", [RpgFarmStrings.item_name(item)]))
	picked.emit(item, spot)
	changed.emit()
	return true

func _on_morning(_day: int) -> void:
	refresh()

func _on_map(_id: StringName) -> void:
	refresh()

func _on_loaded(_slot: int) -> void:
	refresh()
