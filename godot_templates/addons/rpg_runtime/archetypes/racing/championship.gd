class_name RpgChampionship
extends RefCounted
## The championship of a racing game: the races of a run and what each driver took from them.
## A place is worth points (10, 6, 4, 3, 2, 1, then nothing); the table is the drivers by their
## points, and of two with the same points the one who was better in the last race is ahead.
## With `elimination` a player who came in last twice is out.
##
## RpgRacingMode has one, gives it the standings of every race that ends (`record`) and keeps
## it in the save of the run (`to_data`, `from_data`).

## The points of a place, the first first.
const POINTS: Array[int] = [10, 6, 4, 3, 2, 1]
## The driver the player is; a rival is `rival_1`, `rival_2`, ...
const PLAYER := "player"
## How often the player may come in last before it is out.
const LAST_LIMIT := 2

## A player who came in last LAST_LIMIT times is out.
var elimination := false
## How many races were driven.
var races := 0
## How often the player came in last.
var last_count := 0
## The drivers in the order they were first seen, and the points of each.
var drivers: Array[String] = []
var totals := {}
## The place of each driver in the race driven last.
var last_places := {}

static func points_for(place: int) -> int:
	return POINTS[place - 1] if place >= 1 and place <= POINTS.size() else 0

## The driver of `car`: the player, or the rival its node is named after (`Rival2`: `rival_2`).
static func driver_of(car: RpgCar) -> String:
	if car.is_player:
		return PLAYER
	var digits := ""
	for letter in String(car.name):
		if letter.is_valid_int():
			digits += letter
	return "rival_%d" % maxi(1, digits.to_int())

## What a driver is called on a screen: its name when the drivers are people (T18.19).
static func driver_name(driver: String) -> String:
	var named := RpgRacePeople.name_of(driver)
	if named != "":
		return named
	if driver == PLAYER:
		return RpgRacingStrings.t("RACE_DRIVER_YOU")
	return RpgRacingStrings.t("RACE_DRIVER_RIVAL", [maxi(1, driver.get_slice("_", 1).to_int())])

func _know(driver: String) -> void:
	if not totals.has(driver):
		drivers.append(driver)
		totals[driver] = 0

func points_of(driver: String) -> int:
	return RpgUtil.to_int(totals.get(driver, 0))

## Counts a race. `standings` is what RpgRace.standings gives (rows in the order of the
## places, each with its `car`), or rows that name their `driver`. Returns the rows of the
## race: `driver`, `place`, `player`, `finished`, `time_s`, the `points` of the place and the
## driver's `total` after it.
func record(standings: Array) -> Array[Dictionary]:
	var rows: Array[Dictionary] = []
	for raw: Variant in standings:
		if not raw is Dictionary:
			continue
		var entry: Dictionary = raw
		var driver := RpgUtil.to_str(entry.get("driver", ""))
		var car: Variant = entry.get("car")
		if driver == "" and car is RpgCar:
			var driven: RpgCar = car
			driver = driver_of(driven)
		if driver == "" or rows.any(func(row: Dictionary) -> bool: return row["driver"] == driver):
			continue
		rows.append({
			"driver": driver,
			"place": rows.size() + 1,
			"player": driver == PLAYER,
			"finished": RpgUtil.to_bool(entry.get("finished", true)),
			"time_s": RpgUtil.to_float(entry.get("time_s", 0.0)),
		})
	if rows.is_empty():
		return rows
	races += 1
	last_places.clear()
	for row in rows:
		var driver: String = row["driver"]
		var place: int = row["place"]
		_know(driver)
		totals[driver] = points_of(driver) + points_for(place)
		last_places[driver] = place
		row["points"] = points_for(place)
		row["total"] = points_of(driver)
		if driver == PLAYER and rows.size() >= 2 and place == rows.size():
			last_count += 1
	return rows

## The table: the drivers, the first first, each with its `driver`, `place`, `points` and
## whether it is the `player`.
func table() -> Array[Dictionary]:
	var order: Array[String] = drivers.duplicate()
	order.sort_custom(func(a: String, b: String) -> bool:
		if points_of(a) != points_of(b):
			return points_of(a) > points_of(b)
		var last_a := RpgUtil.to_int(last_places.get(a, 99), 99)
		var last_b := RpgUtil.to_int(last_places.get(b, 99), 99)
		if last_a != last_b:
			return last_a < last_b
		return drivers.find(a) < drivers.find(b))
	var out: Array[Dictionary] = []
	for driver in order:
		out.append({"driver": driver, "place": out.size() + 1, "points": points_of(driver), "player": driver == PLAYER})
	return out

## The place of a driver in the table (0: not in it).
func place_of(driver: String) -> int:
	for row in table():
		if row["driver"] == driver:
			return RpgUtil.to_int(row["place"])
	return 0

## The driver at the top of the table ("" before the first race).
func leader() -> String:
	var all := table()
	return RpgUtil.to_str(all[0]["driver"]) if not all.is_empty() else ""

func is_eliminated() -> bool:
	return elimination and last_count >= LAST_LIMIT

## What the save of the run keeps.
func to_data() -> Dictionary:
	var points: Array = []
	for driver in drivers:
		points.append([driver, points_of(driver), RpgUtil.to_int(last_places.get(driver, 0))])
	return {"races": races, "last": last_count, "points": points}

## Takes what `to_data` gave; {} is a championship before its first race.
func from_data(data: Dictionary) -> void:
	races = maxi(0, RpgUtil.to_int(data.get("races", 0)))
	last_count = maxi(0, RpgUtil.to_int(data.get("last", 0)))
	drivers.clear()
	totals.clear()
	last_places.clear()
	for raw: Variant in RpgUtil.to_array(data.get("points", [])):
		var row := RpgUtil.to_array(raw)
		if row.size() < 2 or RpgUtil.to_str(row[0]) == "":
			continue
		var driver := RpgUtil.to_str(row[0])
		_know(driver)
		totals[driver] = maxi(0, RpgUtil.to_int(row[1]))
		if row.size() >= 3 and RpgUtil.to_int(row[2]) > 0:
			last_places[driver] = RpgUtil.to_int(row[2])
