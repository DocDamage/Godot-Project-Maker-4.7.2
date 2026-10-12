class_name RpgAnimalData
extends RefCounted
## The animals a farm can have (T17.07): `game/data/animals.json`. The file is the user's
## (written once); the kinds and the houses rpggen planned since are taken from
## `generated/data/animals.json`, which every build writes, when the user's file does not list
## them. A farm without an animal house has neither file, and this is empty.
##
## * `animals`: one entry a kind. `id` and `name`; `house` (`coop` or `barn`); `ticket` (the
##   item the shop lists it as: it is never in the bag) and `cost`; `product` and `price`,
##   `large` and `large_price` (the items an animal gives, the second from LARGE_HEARTS hearts
##   on; the prices are the items' own `value`, these are for whoever reads the file);
##   `collect` (`floor`: the product lies in the house in the morning; `hand`: `interact` with
##   the animal takes it); `variants`: the pictures of the kind, `{id, colour, scene}`.
## * `feed`: `{item, price}`, what goes into a trough.
## * `names`: what an animal is called when it is bought, in turn.
## * `houses`: `{kind, map, yard_map, stalls}`: the scene of the room, the scene of the map its
##   yard is on, and how many animals it has room for.

## The user's file of the running game. Set by the farm's mode from its `data_dir`, which the
## recipe gives it: a runtime script names no path of the game itself.
static var user_path := ""
const PLANNED_PATH := "res://generated/data/animals.json"
const ON_THE_FLOOR := "floor"
const BY_HAND := "hand"

## Kind id -> its entry, and the ids in the order of the files.
var kinds: Dictionary = {}
var order: Array[String] = []
## House kind ("coop") -> its entry, and the kinds in the order of the files.
var houses: Dictionary = {}
var house_order: Array[String] = []
var names: Array[String] = []
var feed_item: StringName = &""
var feed_price := -1

## The animals of the running game: the user's file, then what only the planned file has.
static func load_default() -> RpgAnimalData:
	var data := RpgAnimalData.new()
	data.add_file(user_path)
	data.add_file(PLANNED_PATH)
	return data

## Adds what a file has that is not there yet. A file that is missing or is no table adds nothing.
func add_file(path: String) -> void:
	if not FileAccess.file_exists(path):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	add(RpgUtil.to_dict(RpgUtil.restore_numbers(parsed)))

## Adds the kinds and the houses of a table (what a test has instead of a file) that are not
## there yet; the feed and the names of the first table that has them count.
func add(table: Dictionary) -> void:
	for raw: Variant in RpgUtil.to_array(table.get("animals", [])):
		var entry := RpgUtil.to_dict(raw)
		var id := RpgUtil.to_str(entry.get("id", ""))
		if id == "" or kinds.has(id):
			continue
		kinds[id] = entry
		order.append(id)
	for raw: Variant in RpgUtil.to_array(table.get("houses", [])):
		var entry := RpgUtil.to_dict(raw)
		var id := RpgUtil.to_str(entry.get("kind", ""))
		if id == "" or houses.has(id):
			continue
		houses[id] = entry
		house_order.append(id)
	var feed := RpgUtil.to_dict(table.get("feed", {}))
	if feed_item == &"" and RpgUtil.to_str(feed.get("item", "")) != "":
		feed_item = StringName(RpgUtil.to_str(feed["item"]))
		feed_price = RpgUtil.to_int(feed.get("price", -1), -1)
	if names.is_empty():
		for raw: Variant in RpgUtil.to_array(table.get("names", [])):
			if RpgUtil.to_str(raw) != "":
				names.append(RpgUtil.to_str(raw))

## True for a farm that keeps no animals: it has no animal house.
func is_empty() -> bool:
	return houses.is_empty()

func has(kind_id: String) -> bool:
	return kinds.has(kind_id)

## The entry of a kind, or {}.
func kind(kind_id: String) -> Dictionary:
	return RpgUtil.to_dict(kinds.get(kind_id, {}))

## The entry of a house, or {}.
func house(house_id: String) -> Dictionary:
	return RpgUtil.to_dict(houses.get(house_id, {}))

## The house a kind lives in ("coop"), or "".
func house_of(kind_id: String) -> String:
	return RpgUtil.to_str(kind(kind_id).get("house", ""))

## How many animals a house has room for; 0 for a house the farm does not have.
func stalls(house_id: String) -> int:
	return maxi(0, RpgUtil.to_int(house(house_id).get("stalls", 0)))

## The kinds that live in a house, in the order of the files.
func kinds_of(house_id: String) -> Array[String]:
	var out: Array[String] = []
	for id in order:
		if house_of(id) == house_id:
			out.append(id)
	return out

## The kind the shop lists as this item, or "".
func kind_of_ticket(item_id: StringName) -> String:
	for id in order:
		if RpgUtil.to_str(kind(id).get("ticket", "")) == String(item_id):
			return id
	return ""

## The pictures of a kind: `{id, colour, scene}` each.
func variants(kind_id: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in RpgUtil.to_array(kind(kind_id).get("variants", [])):
		out.append(RpgUtil.to_dict(raw))
	return out

## The scene of variant `index` of a kind (one beyond the last is the first again), or "".
func scene_of(kind_id: String, index: int) -> String:
	var found := variants(kind_id)
	if found.is_empty():
		return ""
	return RpgUtil.to_str(found[posmod(index, found.size())].get("scene", ""))

## True when the product of a kind lies in its house in the morning (an egg); false when
## `interact` with the animal takes it (milk).
func on_the_floor(kind_id: String) -> bool:
	return RpgUtil.to_str(kind(kind_id).get("collect", BY_HAND)) == ON_THE_FLOOR

## What a kind gives: its `large` product when `large` and it has one, else its `product`.
func product(kind_id: String, large: bool = false) -> StringName:
	var entry := kind(kind_id)
	var better := RpgUtil.to_str(entry.get("large", ""))
	if large and better != "":
		return StringName(better)
	return StringName(RpgUtil.to_str(entry.get("product", "")))
