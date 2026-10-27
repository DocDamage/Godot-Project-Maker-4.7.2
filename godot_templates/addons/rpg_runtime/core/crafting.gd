class_name RpgCrafting
extends RefCounted
## Crafting (1.5.0, T18.14): the recipes of game/data/recipes (RpgRecipe), what the player knows,
## crafting by hand, and the queues and trays of the stations. Everything it keeps is in the
## flags of the game state (`crafting`: `known`, `held`, `stations`), so it is saved with the game
## and the save has no new key.
##
## * **By hand** (`craft`): one `Inventory.transact`: the ingredients are taken and the results
##   given together, or nothing changes; a bag without room is NO_ROOM before anything is taken.
## * **At a station** (`queue`): the ingredients are taken when the craft is queued; each craft
##   takes the recipe's `minutes` of game time (seconds of play in a game without a calendar),
##   one after the other. A finished craft goes into the bag, or waits in the station's tray
##   when the bag is full (`update`, which the station and the window call; nothing ticks, so a
##   station off the screen goes on working). Cancelling a craft that is not finished gives its
##   ingredients back; Collect all takes the tray.
## * **Learning**: a recipe is `known` from the start, `taught` (the dialogue event
##   `learn_recipe:<id>`, a festival, a gift) or `found` once every ingredient has been held
##   (GameState calls `note_held` for every item gained).
## * Each craft counts `crafted` and `crafted:<item>` (the condition atom `crafted:<item>[>=N]`).

const FLAG_ENTITY := "crafting"
const RECIPES_DIR := "res://game/data/recipes"

const OK := ""
const NOT_KNOWN := "not_known"
const MISSING := "missing"
const NO_ROOM := "no_room"
const WRONG_STATION := "wrong_station"
const UNKNOWN := "unknown"

## Where the recipes are read from (a test points it at its own folder).
static var recipes_dir := RECIPES_DIR
static var _book: Dictionary = {}  # id -> RpgRecipe
static var _book_dir := ""

# ------------------------------------------------------------------ the recipes

## Every recipe of `recipes_dir`, by id (read once; `reload_book()` reads them again).
static func book() -> Dictionary:
	if _book_dir != recipes_dir:
		reload_book()
	return _book

static func reload_book() -> void:
	_book = {}
	_book_dir = recipes_dir
	var dir := DirAccess.open(recipes_dir)
	if dir == null:
		return
	var names := Array(dir.get_files())
	names.sort()
	for file_name: String in names:
		var clean := file_name.trim_suffix(".remap")
		if not clean.ends_with(".tres"):
			continue
		var made := load(recipes_dir.path_join(clean)) as RpgRecipe
		if made != null and made.id != &"" and not _book.has(made.id):
			_book[made.id] = made

## The recipes in their order (by id); those made at `station` only when it is given (&"" is
## by hand), all of them when `station` is null.
static func recipes(station: Variant = null) -> Array[RpgRecipe]:
	var out: Array[RpgRecipe] = []
	var ids := book().keys()
	ids.sort()
	for recipe_id: Variant in ids:
		var made: RpgRecipe = _book[recipe_id]
		if station == null or made.station == StringName(str(station)):
			out.append(made)
	return out

static func recipe(recipe_id: StringName) -> RpgRecipe:
	var found: RpgRecipe = book().get(recipe_id)
	return found

## True when the game has a recipe made by hand: the pause menu then has Crafting.
static func by_hand_exists() -> bool:
	return not recipes(&"").is_empty()

# ------------------------------------------------------------------ what is kept

static func _flag(game: RpgGameState, key: String, fallback: Variant) -> Variant:
	return game.get_flag(FLAG_ENTITY, key, fallback)

static func _put(game: RpgGameState, key: String, value: Variant) -> void:
	game.set_flag(FLAG_ENTITY, key, value)

static func known(game: RpgGameState, made: RpgRecipe) -> bool:
	if made == null:
		return false
	return made.learn == RpgRecipe.KNOWN or RpgUtil.to_array(_flag(game, "known", [])).has(String(made.id))

## Learns a recipe (taught, or found). False when it was known, or there is no such recipe.
static func learn(game: RpgGameState, recipe_id: StringName, say: bool = true) -> bool:
	var made := recipe(recipe_id)
	if made == null or known(game, made):
		return false
	var list := RpgUtil.to_array(_flag(game, "known", [])).duplicate()
	list.append(String(recipe_id))
	_put(game, "known", list)
	if say:
		RpgUtil.notify(RpgStrings.format("UI_RECIPE_LEARNED", TranslationServer.translate(made.title)))
	return true

## An item was gained: it counts as held, and a recipe that is found by itself is learned once
## every ingredient of it has been held.
static func note_held(game: RpgGameState, item_id: StringName) -> void:
	if book().is_empty():
		return
	var held := RpgUtil.to_array(_flag(game, "held", []))
	if not held.has(String(item_id)):
		held = held.duplicate()
		held.append(String(item_id))
		_put(game, "held", held)
	for made in recipes():
		if made.learn != RpgRecipe.FOUND or known(game, made) or not made.ingredients.has(String(item_id)) and not made.ingredients.has(item_id):
			continue
		var all := true
		for wanted: Variant in made.ingredients:
			if not held.has(str(wanted)):
				all = false
		if all:
			learn(game, made.id)

# ------------------------------------------------------------------ by hand

## {item id: how many more are needed} to make `amount` of a recipe ({} when nothing lacks).
static func lacking(game: RpgGameState, made: RpgRecipe, amount: int = 1) -> Dictionary:
	var out := {}
	for row: Variant in RpgRecipe.rows(made.ingredients, amount):
		var wanted := RpgUtil.to_dict(row)
		var item_id := StringName(str(wanted["item_id"]))
		var short := RpgUtil.to_int(wanted["qty"]) - game.inventory.count(item_id)
		if short > 0:
			out[String(item_id)] = short
	return out

## The most of a recipe the bag's ingredients make (0 when one is missing).
static func most(game: RpgGameState, made: RpgRecipe) -> int:
	var out := -1
	for item_id: Variant in made.ingredients:
		var each := maxi(1, RpgUtil.to_int(made.ingredients[item_id]))
		var can := floori(float(game.inventory.count(StringName(str(item_id)))) / float(each))
		out = can if out < 0 else mini(out, can)
	return maxi(0, out)

## Why `amount` of a recipe cannot be made by hand now, or OK.
static func check(game: RpgGameState, made: RpgRecipe, amount: int = 1) -> String:
	if made == null:
		return UNKNOWN
	if not known(game, made):
		return NOT_KNOWN
	if not lacking(game, made, amount).is_empty():
		return MISSING
	if not game.inventory.fits(RpgRecipe.rows(made.results, amount), RpgRecipe.rows(made.ingredients, amount)):
		return NO_ROOM
	return OK

## Makes `amount` of a recipe by hand: all or nothing. Returns OK or why not.
static func craft(game: RpgGameState, made: RpgRecipe, amount: int = 1) -> String:
	if made != null and made.station != &"":
		return WRONG_STATION
	var why := check(game, made, amount)
	if why != OK:
		return why
	if not game.inventory.transact(RpgRecipe.rows(made.results, amount), RpgRecipe.rows(made.ingredients, amount)):
		return NO_ROOM
	_counted(game, made, amount)
	return OK

static func _counted(game: RpgGameState, made: RpgRecipe, amount: int) -> void:
	game.count("crafted", amount)
	for item_id: Variant in made.results:
		game.count("crafted:%s" % item_id, RpgUtil.to_int(made.results[item_id]) * amount)

# ------------------------------------------------------------------ the stations

## The time of the game a station counts in: game minutes since the first morning with a
## calendar, seconds of play without one.
static func now(game: RpgGameState) -> int:
	var calendar := RpgCalendar.current()
	if calendar != null:
		return calendar.today() * RpgCalendar.DAY_MINUTES + (calendar.minute - RpgCalendar.DAY_START)
	return floori(game.playtime_s)

## The state of a station (`key`: its entity id): {queue: [{recipe, amount, start, done}], tray:
## [{item_id, qty}]}.
static func station_state(game: RpgGameState, key: String) -> Dictionary:
	var all := RpgUtil.to_dict(_flag(game, "stations", {}))
	var mine := RpgUtil.to_dict(all.get(key, {}))
	return {"queue": RpgUtil.to_array(mine.get("queue", [])).duplicate(true), "tray": RpgUtil.to_array(mine.get("tray", [])).duplicate(true)}

static func _store(game: RpgGameState, key: String, mine: Dictionary) -> void:
	var all := RpgUtil.to_dict(_flag(game, "stations", {})).duplicate(true)
	if RpgUtil.to_array(mine["queue"]).is_empty() and RpgUtil.to_array(mine["tray"]).is_empty():
		all.erase(key)
	else:
		all[key] = mine
	_put(game, "stations", all)

## Queues `amount` of a recipe at the station `key` of kind `station_id`: the ingredients are
## taken now. Returns OK or why not.
static func queue(game: RpgGameState, key: String, station_id: StringName, made: RpgRecipe, amount: int = 1) -> String:
	if made == null:
		return UNKNOWN
	if made.station != station_id:
		return WRONG_STATION
	if not known(game, made):
		return NOT_KNOWN
	if not lacking(game, made, amount).is_empty():
		return MISSING
	if not game.inventory.transact([], RpgRecipe.rows(made.ingredients, amount)):
		return MISSING
	update(game, key)
	var mine := station_state(game, key)
	var jobs: Array = mine["queue"]
	var start := now(game)
	if not jobs.is_empty():
		start = maxi(start, RpgUtil.to_int(RpgUtil.to_dict(jobs[jobs.size() - 1])["done"]))
	jobs.append({"recipe": String(made.id), "amount": amount, "start": start, "done": start + made.minutes * amount})
	_store(game, key, mine)
	update(game, key)
	return OK

## Moves what is finished out of the queue: into the bag, or into the tray when it has no room.
## Returns how many crafts finished.
static func update(game: RpgGameState, key: String) -> int:
	var mine := station_state(game, key)
	var jobs: Array = mine["queue"]
	var tray: Array = mine["tray"]
	var finished := 0
	var at := now(game)
	while not jobs.is_empty() and RpgUtil.to_int(RpgUtil.to_dict(jobs[0])["done"]) <= at:
		var job := RpgUtil.to_dict(jobs.pop_front())
		var made := recipe(StringName(str(job["recipe"])))
		finished += 1
		if made == null:
			continue
		var amount := RpgUtil.to_int(job.get("amount", 1), 1)
		var giving := RpgRecipe.rows(made.results, amount)
		if not game.inventory.transact(giving, []):
			for row: Variant in giving:
				tray.append({"item_id": str(RpgUtil.to_dict(row)["item_id"]), "qty": RpgUtil.to_int(RpgUtil.to_dict(row)["qty"])})
		_counted(game, made, amount)
	if finished > 0:
		_store(game, key, mine)
	return finished

## How far a queued craft is, 0 to 1.
static func progress(game: RpgGameState, job: Dictionary) -> float:
	var start := RpgUtil.to_int(job.get("start", 0))
	var done := RpgUtil.to_int(job.get("done", 0))
	if done <= start:
		return 1.0
	return clampf(float(now(game) - start) / float(done - start), 0.0, 1.0)

## Cancels craft `index` of the queue: its ingredients come back (into the tray when the bag has
## no room), and the crafts after it move up. False for one that is finished or not there.
static func cancel(game: RpgGameState, key: String, index: int) -> bool:
	update(game, key)
	var mine := station_state(game, key)
	var jobs: Array = mine["queue"]
	if index < 0 or index >= jobs.size():
		return false
	var job := RpgUtil.to_dict(jobs[index])
	jobs.remove_at(index)
	var made := recipe(StringName(str(job["recipe"])))
	if made != null:
		var giving := RpgRecipe.rows(made.ingredients, RpgUtil.to_int(job.get("amount", 1), 1))
		if not game.inventory.transact(giving, []):
			var tray: Array = mine["tray"]
			for row: Variant in giving:
				tray.append({"item_id": str(RpgUtil.to_dict(row)["item_id"]), "qty": RpgUtil.to_int(RpgUtil.to_dict(row)["qty"])})
	# the crafts after it start sooner: each where the one before ends (or now)
	var at := now(game)
	for i in range(index, jobs.size()):
		var later := RpgUtil.to_dict(jobs[i])
		var length := RpgUtil.to_int(later["done"]) - RpgUtil.to_int(later["start"])
		var start := at if i == 0 else maxi(at, RpgUtil.to_int(RpgUtil.to_dict(jobs[i - 1])["done"]))
		if RpgUtil.to_int(later["start"]) > start:
			later["start"] = start
			later["done"] = start + length
	_store(game, key, mine)
	return true

## Takes what lies in the tray into the bag, as much as fits. Returns how many rows came out.
static func collect_all(game: RpgGameState, key: String) -> int:
	update(game, key)
	var mine := station_state(game, key)
	var tray: Array = mine["tray"]
	var left: Array = []
	var taken := 0
	for raw: Variant in tray:
		var row := RpgUtil.to_dict(raw)
		if game.inventory.transact([row], []):
			taken += 1
		else:
			left.append(row)
	mine["tray"] = left
	_store(game, key, mine)
	return taken
