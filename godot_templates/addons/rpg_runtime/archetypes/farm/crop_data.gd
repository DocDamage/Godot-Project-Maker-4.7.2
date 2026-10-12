class_name RpgCropData
extends RefCounted
## The crops of a farm (T17.05): `game/data/crops.json`, one entry a crop. The file is the
## user's (written once); the crops rpggen planned since (a crop added to the packs later) are
## taken from `generated/data/crops.json`, which every build writes, when the user's file does
## not list them.
##
## An entry: `id`, `name`, `seed` and `produce` (item ids), `seasons` (the names of the seasons
## it grows in), `days` (watered nights from seed to ripe), `stages` (the pictures of its growth
## strip; the last is the ripe one), `regrow` (0: one harvest; else the days to the next one),
## `seed_price`, `price`, `energy` (what eating one restores) and `scene`.

const USER_PATH := "res://game/data/crops.json"
const PLANNED_PATH := "res://generated/data/crops.json"

## Crop id -> its entry, and the ids in the order of the files.
var crops: Dictionary = {}
var order: Array[String] = []

## The crops of the running game: the user's file, then what only the planned file has.
static func load_default() -> RpgCropData:
	var data := RpgCropData.new()
	data.add_file(USER_PATH)
	data.add_file(PLANNED_PATH)
	return data

## Adds the crops of a file that are not there yet. A file that is missing or is not a list of
## crops adds nothing.
func add_file(path: String) -> void:
	if not FileAccess.file_exists(path):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	add_list(RpgUtil.to_array(RpgUtil.to_dict(RpgUtil.restore_numbers(parsed)).get("crops", [])))

## Adds entries (what a test has instead of a file). An entry without an id, or whose id is
## there already, is left out.
func add_list(entries: Array) -> void:
	for raw: Variant in entries:
		var entry := RpgUtil.to_dict(raw)
		var id := RpgUtil.to_str(entry.get("id", ""))
		if id == "" or crops.has(id):
			continue
		crops[id] = entry
		order.append(id)

func has(crop_id: String) -> bool:
	return crops.has(crop_id)

## The entry of a crop, or {}.
func crop(crop_id: String) -> Dictionary:
	return RpgUtil.to_dict(crops.get(crop_id, {}))

## The id of the crop this item is the seed of, or "".
func crop_of_seed(item_id: StringName) -> String:
	for id in order:
		if RpgUtil.to_str(crop(id).get("seed", "")) == String(item_id):
			return id
	return ""

## The id of the crop this item is the produce of, or "".
func crop_of_produce(item_id: StringName) -> String:
	for id in order:
		if RpgUtil.to_str(crop(id).get("produce", "")) == String(item_id):
			return id
	return ""

func days(crop_id: String) -> int:
	return maxi(1, RpgUtil.to_int(crop(crop_id).get("days", 1), 1))

func stages(crop_id: String) -> int:
	return maxi(1, RpgUtil.to_int(crop(crop_id).get("stages", 1), 1))

## 0 for a crop that is harvested once.
func regrow(crop_id: String) -> int:
	return clampi(RpgUtil.to_int(crop(crop_id).get("regrow", 0)), 0, days(crop_id))

## True when the crop grows in the season of this name. A crop that names no season grows in all.
func grows_in(crop_id: String, season_name: String) -> bool:
	var seasons := RpgUtil.to_array(crop(crop_id).get("seasons", []))
	return seasons.is_empty() or seasons.has(season_name)

## The crops that grow in a season, in the order of the files.
func of_season(season_name: String) -> Array[String]:
	var out: Array[String] = []
	for id in order:
		if grows_in(id, season_name):
			out.append(id)
	return out

# ------------------------------------------------------------------ the arithmetic (crop_plan.py)

## The picture of a crop that has grown `grown` of its `total_days`: the frames of its strip
## spread evenly over the days, the first on the day it is planted and the last when it is ripe.
static func stage_of(grown: int, total_days: int, stage_count: int) -> int:
	var total := maxi(1, total_days)
	var last := maxi(1, stage_count) - 1
	return clampi(grown, 0, total) * last / total

static func is_ripe(grown: int, total_days: int) -> bool:
	return grown >= maxi(1, total_days)
