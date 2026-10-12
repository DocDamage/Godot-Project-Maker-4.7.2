extends RefCounted
## T17.10: fishing and foraging. The things of a morning follow from the seed, the day and the
## season, are the same after a save and a load, are gone when they are picked up and are others
## the next morning; a cast waits, a fish bites and is caught with a held button or gets away;
## a well and dry land take no cast; a cast costs energy and time; the fish follow the season
## and the time of day.

const Fixtures := preload("../lib/fixtures.gd")
const Farmer := preload("test_farmer.gd")

const TILE := 16
const WATER_CELL := Vector2i(7, 2)
const SPOTS: Array[Vector2i] = [Vector2i(1, 6), Vector2i(3, 7), Vector2i(5, 6), Vector2i(8, 7), Vector2i(10, 6), Vector2i(12, 7)]
const FORAGE := [
	{"id": "forage_herb", "name": "Herb", "item": "forage_herb", "seasons": ["spring"], "price": 15, "energy": 8},
	{"id": "forage_leek", "name": "Leek", "item": "forage_leek", "seasons": ["spring", "summer"], "price": 20, "energy": 8},
	{"id": "forage_nut", "name": "Nut", "item": "forage_nut", "seasons": ["autumn"], "price": 25, "energy": 8},
	{"id": "forage_root", "name": "Root", "item": "forage_root", "seasons": ["winter"], "price": 15, "energy": 8},
]
const FISH := [
	{"id": "fish_perch", "name": "Perch", "item": "fish_perch", "seasons": ["spring", "summer", "autumn"], "times": ["morning", "day"], "water": ["pond"], "price": 30, "energy": 12, "speed": 1.0},
	{"id": "fish_carp", "name": "Carp", "item": "fish_carp", "seasons": ["spring", "summer", "winter"], "times": ["day", "evening"], "water": ["pond"], "price": 45, "energy": 12, "speed": 1.2},
	{"id": "fish_eel", "name": "Eel", "item": "fish_eel", "seasons": ["spring", "autumn", "winter"], "times": ["morning", "evening"], "water": ["pond"], "price": 60, "energy": 12, "speed": 1.4},
]
const ITEMS: Array[StringName] = [&"hoe", &"fishing_rod", &"forage_herb", &"forage_leek", &"forage_nut", &"forage_root", &"fish_perch", &"fish_carp", &"fish_eel"]
const STEP := 0.05

var _made: Array[Node] = []
var _toasts: Array[String] = []
var _held := false

## A farm map: a plot at (2, 2), a cell of water at (7, 2) with its body (a pond, or a well),
## the entities, the field and six places to forage. {root, field, entities, water}
func _map(water_kind: String = "pond") -> Dictionary:
	var root := Node2D.new()
	root.name = "Farm"
	var soil := TileMapLayer.new()
	soil.name = "Soil"
	soil.tile_set = Farmer.tile_set()
	root.add_child(soil)
	for y in range(2, 5):
		for x in range(2, 6):
			soil.set_cell(Vector2i(x, y), 0, Vector2i(0, 0))
	soil.set_cell(WATER_CELL, 0, Vector2i(3, 0))
	var ysorted := Node2D.new()
	ysorted.name = "YSorted"
	root.add_child(ysorted)
	var entities := Node2D.new()
	entities.name = "Entities"
	ysorted.add_child(entities)
	var water := RpgWaterSource.new()
	water.name = "Water"
	water.kind = water_kind
	entities.add_child(water)
	var field := RpgField.new()
	field.name = "Field"
	field.field_id = "farm"
	field.crops = RpgCropData.new()
	root.add_child(field)
	field.setup()
	var holder := Node2D.new()
	holder.name = RpgForage.HOLDER
	root.add_child(holder)
	for i in SPOTS.size():
		var marker := Marker2D.new()
		marker.name = "%s%d" % [RpgForage.SPOT_PREFIX, i + 1]
		marker.position = (Vector2(SPOTS[i]) + Vector2(0.5, 0.5)) * TILE
		holder.add_child(marker)
	_made.append(root)
	return {"root": root, "field": field, "entities": entities, "water": water}

## A farm's game with the table of this file. {state, mode, calendar, forage, fishing}
func _game(game_seed: int = 7) -> Dictionary:
	var registry := {}
	for id in ITEMS:
		registry[id] = Fixtures.item(id)
	var state := Fixtures.install_state(registry) as RpgGameState
	state.inventory.registry = state.items
	state.rng.seed_value(game_seed)
	_toasts.clear()
	RpgUtil.events().notify.connect(func(text: String) -> void: _toasts.append(text))
	var mode := RpgFarmMode.new()
	mode.crops = RpgCropData.new()
	mode.ensure_parts()
	mode.forage.add_lists(FORAGE, FISH)
	mode._ready()
	_made.append(mode)
	_held = false
	mode.fishing.button = func() -> bool: return _held
	return {"state": state, "mode": mode, "calendar": RpgCalendar.current(), "forage": mode.forage, "fishing": mode.fishing}

## A farmer on `map` with the rod held, in the cell above the water and looking down at it.
func _farmer(game: Dictionary, map: Dictionary) -> RpgFarmer:
	var state: RpgGameState = game["state"]
	var mode: RpgFarmMode = game["mode"]
	state.inventory.add(&"fishing_rod", 1)
	var farmer := RpgFarmer.new()
	farmer.name = "Player"
	farmer.mode = mode
	farmer.field = map["field"]
	var entities: Node2D = map["entities"]
	entities.add_child(farmer)
	farmer.position = (Vector2(WATER_CELL + Vector2i.UP) + Vector2(0.5, 0.5)) * TILE
	farmer.facing = "down"
	mode.hotbar.hold_item(&"fishing_rod")
	mode.fishing.farmer = farmer
	return farmer

## Casts with the real path (the farmer uses the held rod) and lets the rod's use time end.
func _cast(farmer: RpgFarmer) -> bool:
	var done := farmer.use_held()
	farmer._end_use()
	return done

## Lets the cast run until `done` says so; false when it never did within `seconds`.
func _run(fishing: RpgFishing, done: Callable, seconds: float = 30.0, script: Callable = Callable()) -> bool:
	var left := seconds
	while left > 0.0:
		if done.call():
			return true
		if script.is_valid():
			script.call()
		fishing.advance(STEP)
		left -= STEP
	return done.call() == true

func _cleanup() -> void:
	Fixtures.tree().paused = false
	for node in _made:
		if is_instance_valid(node):
			node.free()
	_made.clear()
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- foraging

func test_the_forage_of_a_morning_follows_from_the_seed_the_day_and_the_season(t) -> void:
	var first := RpgForage.forage_of(FORAGE, 4242, 3, "spring", 6)
	t.eq(first, RpgForage.forage_of(FORAGE, 4242, 3, "spring", 6), "the same every time it is asked")
	t.eq(first, RpgForage.forage_of(FORAGE, 4242 + (1 << 31), 3, "spring", 6), "the seed counts by its low 31 bits")
	var mornings := {}
	var other_seed := {}
	var with_something := 0
	for day in 112:
		var season := RpgCalendar.season_name_of(RpgCalendar.season_of(day))
		var found := RpgForage.forage_of(FORAGE, 4242, day, season, 6)
		t.ok(found.size() >= 1, "every morning something lies somewhere (day %d)" % day)
		with_something += found.size()
		for spot: int in found.keys():
			t.ok(spot >= 0 and spot < 6)
			var item := String(found[spot])
			var wanted := false
			for entry: Dictionary in FORAGE:
				if entry["item"] == item and (entry["seasons"] as Array).has(season):
					wanted = true
			t.ok(wanted, "%s lies in %s (day %d)" % [item, season, day])
		mornings[JSON.stringify(found.keys())] = true
		other_seed[day] = RpgForage.forage_of(FORAGE, 99, day, season, 6) != found
	t.ok(mornings.size() > 10, "the places change from morning to morning: %d patterns" % mornings.size())
	t.ok(other_seed.values().count(true) > 80, "another seed, other mornings")
	var share := with_something / (112.0 * 6.0)
	t.ok(share > 0.3 and share < 0.6, "about %d in a hundred places have something: %.2f" % [RpgForage.CHANCE, share])
	t.eq(RpgForage.forage_of(FORAGE, 1, 1, "spring", 0), {}, "a map without places")
	t.eq(RpgForage.forage_of([FORAGE[2]], 1, 1, "spring", 6), {}, "a season in which nothing lies")
	t.eq(RpgForage.places_of(5, 9, 1), [0] as Array[int], "one place always has something")
	for index in 300:
		var value := RpgForage.roll(31, index, index % 7, index % 3)
		t.ok(value >= 0 and value < 100)

func test_a_morning_is_the_same_after_a_save_and_what_was_picked_is_gone(t) -> void:
	var game := _game(4242)
	var map := _map()
	var state: RpgGameState = game["state"]
	var forage: RpgForage = game["forage"]
	var calendar: RpgCalendar = game["calendar"]
	var root: Node2D = map["root"]
	t.eq(forage.places_on(root).size(), SPOTS.size())
	t.eq(forage.places_on(root)[2], (Vector2(SPOTS[2]) + Vector2(0.5, 0.5)) * TILE, "the markers in their order")
	var shown_now := forage.refresh(root)
	var morning := forage.morning(SPOTS.size())
	var map_seed := RpgForage.map_seed(4242, RpgForage.map_key(root))
	t.eq(RpgForage.map_key(root), "Farm", "a map without an id goes by the name of its node")
	t.ok(map_seed != RpgForage.map_seed(4242, "beach"), "every map has mornings of its own")
	t.eq(morning, RpgForage.forage_of(FORAGE, map_seed, 0, "spring", SPOTS.size()), "the game's morning is its seed's")
	t.eq(shown_now, morning.size())
	t.eq(forage.shown(), _sorted(morning.keys()))
	var first: int = forage.shown()[0]
	var thing := forage.thing_at(first)
	t.ok(thing != null and thing.item_id == morning[first], "the thing lies at its place")
	t.eq(thing.get_parent(), map["entities"], "among the entities of the map: it sorts with the farmer")
	t.eq((map["field"] as RpgField).cell_at(thing.position - Vector2(0.0, 1.0)), SPOTS[first], "in its cell")
	# the random numbers of the game move on; the morning does not
	state.rng.seed_value(1)
	state.flags = RpgUtil.restore_numbers(JSON.parse_string(JSON.stringify(state.flags)))
	t.eq(forage.morning(SPOTS.size()), morning, "the same after the flags went through a save")
	# `interact` picks it up
	thing.interact()
	t.eq(state.inventory.count(morning[first]), 1, "it is in the bag")
	t.ok(forage.thing_at(first) == null, "and gone from the map")
	t.ok(not forage.lying(SPOTS.size()).has(first))
	t.ok(_toasts.has(RpgFarmStrings.t("FARM_FORAGED", [RpgFarmStrings.item_name(morning[first])])), "a toast says what was found: %s" % [_toasts])
	t.ok(not forage.pick(first), "nothing lies there any more")
	# a save and a load later it is still gone, and the rest still lies there
	state.flags = RpgUtil.restore_numbers(JSON.parse_string(JSON.stringify(state.flags)))
	t.eq(forage.refresh(root), morning.size() - 1)
	t.ok(not forage.shown().has(first))
	t.eq(forage.picked_today(), [first] as Array[int])
	# what was picked on one map is not picked on another
	var beach := Node2D.new()
	beach.name = "Beach"
	_made.append(beach)
	forage.refresh(beach)
	t.eq(forage.picked_today(), [] as Array[int], "another map")
	t.eq(forage.refresh(root), morning.size() - 1)
	# the next morning: what the seed gives that day, with nothing picked
	calendar.end_day()
	var next := RpgForage.forage_of(FORAGE, map_seed, 1, "spring", SPOTS.size())
	t.eq(forage.refresh(root), next.size())
	t.eq(forage.picked_today(), [] as Array[int])
	t.eq(forage.shown(), _sorted(next.keys()), "a new morning")
	# in another season other things lie there
	for day in calendar.days_per_season * 2:
		calendar.end_day()
	t.eq(calendar.season_name(), "autumn")
	forage.refresh(root)
	for spot in forage.shown():
		t.eq(forage.thing_at(spot).item_id, &"forage_nut", "what lies in autumn")
	# the things of a map that is gone went with it: the next map is shown without a word
	var were := forage.shown()
	t.ok(not were.is_empty())
	root.free()
	t.ok(forage.thing_at(were[0]) == null, "freed with its map")
	t.eq(forage.refresh(beach), 0, "a map without places")
	_cleanup()

func test_a_full_bag_leaves_the_thing_where_it_lies(t) -> void:
	var game := _game(11)
	var map := _map()
	var state: RpgGameState = game["state"]
	var forage: RpgForage = game["forage"]
	forage.refresh(map["root"])
	var spot: int = forage.shown()[0]
	state.inventory.capacity = 1
	state.inventory.add(&"hoe", 1)
	t.ok(not forage.pick(spot), "no room")
	t.ok(forage.thing_at(spot) != null, "it stays")
	t.ok(_toasts.has(RpgFarmStrings.t("FARM_FULL")))
	t.eq(forage.picked_today(), [] as Array[int])
	state.inventory.capacity = 40
	t.ok(forage.pick(spot))
	# what is found can be eaten: the table says what it restores
	var mode: RpgFarmMode = game["mode"]
	t.eq(mode.food_energy(&"forage_herb"), 8)
	t.eq(mode.food_energy(&"fish_perch"), 12)
	t.eq(mode.food_energy(&"hoe"), 0)
	_cleanup()

func test_the_places_of_a_map_are_its_markers_or_the_planned_cells(t) -> void:
	var game := _game()
	var map := _map()
	var forage: RpgForage = game["forage"]
	var root: Node2D = map["root"]
	var holder := root.get_node(RpgForage.HOLDER)
	# a marker that somebody added in the editor counts by its number, another node does not
	var tenth := Marker2D.new()
	tenth.name = "Spot10"
	tenth.position = Vector2(200, 40)
	holder.add_child(tenth)
	holder.move_child(tenth, 0)
	var other := Node2D.new()
	other.name = "Note"
	holder.add_child(other)
	var places := forage.places_on(root)
	t.eq(places.size(), SPOTS.size() + 1)
	t.eq(places[places.size() - 1], Vector2(200, 40), "Spot10 comes after Spot6")
	# a map without markers: the cells of the planned file, when it is that map
	root.remove_child(holder)
	holder.free()
	t.eq(forage.places_on(root).size(), 0, "no markers and no plan: no places")
	forage.planned_map = "farm"
	forage.planned_spots = [Vector2i(1, 1), Vector2i(9, 3)]
	root.set_script(load("res://addons/rpg_runtime/world/map_root.gd"))
	root.set("map_id", &"farm")
	t.eq(forage.places_on(root), [Vector2(24, 24), Vector2(152, 56)] as Array[Vector2])
	root.set("map_id", &"starter_map")
	t.eq(forage.places_on(root).size(), 0, "another map has none of the farm's places")
	t.eq(forage.places_on(null).size(), 0)
	_cleanup()

static func _sorted(keys: Array) -> Array[int]:
	var out: Array[int] = []
	out.assign(keys)
	out.sort()
	return out

# ---------------------------------------------------------------- fishing

func test_the_fish_follow_the_season_and_the_time_of_day(t) -> void:
	t.eq(RpgFishing.time_of(RpgCalendar.DAY_START), "morning")
	t.eq(RpgFishing.time_of(11 * 60 + 59), "morning")
	t.eq(RpgFishing.time_of(12 * 60), "day")
	t.eq(RpgFishing.time_of(17 * 60 + 59), "day")
	t.eq(RpgFishing.time_of(18 * 60), "evening")
	t.eq(RpgFishing.time_of(25 * 60), "evening", "after midnight")
	t.eq(RpgFishing.fish_of(FISH, "spring", "morning", "pond"), ["fish_perch", "fish_eel"] as Array[String])
	t.eq(RpgFishing.fish_of(FISH, "summer", "morning", "pond"), ["fish_perch"] as Array[String])
	t.eq(RpgFishing.fish_of(FISH, "winter", "evening", "pond"), ["fish_carp", "fish_eel"] as Array[String])
	t.eq(RpgFishing.fish_of(FISH, "winter", "morning", "pond"), ["fish_eel"] as Array[String])
	t.eq(RpgFishing.fish_of(FISH, "spring", "day", "well"), [] as Array[String], "a well has no fish")
	t.eq(RpgFishing.fish_of([{"id": "any", "item": "any"}], "winter", "day", "pond"), ["any"] as Array[String], "an entry that names nothing bites always")
	var seen := {}
	for cast_no in range(1, 60):
		var id := RpgFishing.fish_for(FISH, "spring", "evening", "pond", 77, cast_no)
		t.ok(["fish_carp", "fish_eel"].has(id), "cast %d in a spring evening: %s" % [cast_no, id])
		t.eq(id, RpgFishing.fish_for(FISH, "spring", "evening", "pond", 77, cast_no))
		seen[id] = true
		var wait := RpgFishing.wait_of(77, cast_no)
		t.ok(wait >= RpgFishing.WAIT_MIN and wait <= RpgFishing.WAIT_MAX, "a wait of %.2f s" % wait)
		t.eq(wait, RpgFishing.wait_of(77, cast_no))
	t.eq(seen.size(), 2, "both fish of the evening bite on some cast")
	t.eq(RpgFishing.fish_for(FISH, "summer", "evening", "well", 77, 1), "")
	t.ok(RpgFishing.wait_of(77, 1) != RpgFishing.wait_of(77, 2) or RpgFishing.wait_of(77, 2) != RpgFishing.wait_of(77, 3), "seeded per cast")

func test_a_cast_a_bite_and_a_catch_with_a_scripted_button(t) -> void:
	var game := _game(77)
	var map := _map()
	var farmer := _farmer(game, map)
	var state: RpgGameState = game["state"]
	var mode: RpgFarmMode = game["mode"]
	var fishing: RpgFishing = game["fishing"]
	var calendar: RpgCalendar = game["calendar"]
	var seen := {"cast": 0, "bit": "", "caught": &"", "lost": ""}
	fishing.cast_out.connect(func(_cell: Vector2i) -> void: seen["cast"] += 1)
	fishing.bit.connect(func(id: String) -> void: seen["bit"] = id)
	fishing.caught.connect(func(item: StringName) -> void: seen["caught"] = item)
	fishing.lost.connect(func(why: String) -> void: seen["lost"] = why)
	t.ok(mode.tool_for(&"fishing_rod") is RpgFarmRod, "the rod is a tool of the mode")
	t.eq(farmer.tile_ahead(), WATER_CELL)
	var energy := mode.energy.value
	var minute := calendar.minute
	# the cast: the real path, `use` with the rod held at water
	t.ok(_cast(farmer), "the line is out")
	t.eq(fishing.state, RpgFishing.WAITING)
	t.eq(seen["cast"], 1)
	t.eq(mode.energy.value, energy - 3, "a cast costs a little energy")
	t.eq(calendar.minute, minute + RpgFishing.CAST_MINUTES, "and passes time")
	t.eq(fishing.casts(), 1)
	t.ok(farmer.fishing and farmer.move_locked, "the farmer stands still beyond the rod's use time")
	t.ok(not _cast(farmer), "no second line while one is out")
	t.eq(mode.energy.value, energy - 3)
	var wanted := RpgFishing.fish_for(FISH, "spring", "morning", "pond", 77, 1)
	t.eq(fishing.fish_id, wanted, "the fish the seed and the cast give")
	# the wait: as long as the seed says, not shorter
	var wait := RpgFishing.wait_of(77, 1)
	fishing.advance(wait - 0.1)
	t.eq(fishing.state, RpgFishing.WAITING, "still waiting after %.2f s of %.2f" % [wait - 0.1, wait])
	fishing.advance(0.2)
	t.eq(fishing.state, RpgFishing.BITE, "a bite")
	t.eq(seen["bit"], wanted)
	t.ok(fishing.bar() != null and fishing.bar().visible, "the bite is shown")
	# then the bar opens by itself
	fishing.advance(RpgFishing.BITE_S + 0.01)
	t.eq(fishing.state, RpgFishing.REELING)
	t.eq(fishing.meter, RpgFishing.METER_START)
	# the button is held while the fish is above the middle of the zone, let go while it is below
	var script := func() -> void: _held = fishing.mark > fishing.zone
	t.ok(_run(fishing, func() -> bool: return fishing.state == RpgFishing.IDLE, 30.0, script), "the meter fills (it stands at %.2f)" % fishing.meter)
	t.eq(seen["caught"], StringName(wanted), "caught")
	t.eq(seen["lost"], "")
	t.eq(state.inventory.count(StringName(wanted)), 1, "the fish is in the bag")
	t.eq(calendar.minute, minute + RpgFishing.CAST_MINUTES + RpgFishing.REEL_MINUTES, "landing it took time")
	t.eq(mode.energy.value, energy - 3, "and no more energy")
	t.ok(not farmer.fishing and not farmer.move_locked, "the farmer walks again")
	t.ok(not fishing.bar().visible, "the bar is gone")
	t.ok(_toasts.has(RpgFarmStrings.t("FARM_FISH_CAUGHT", [RpgFarmStrings.item_name(StringName(wanted))])), "a toast names it: %s" % [_toasts])
	# the next cast is another cast of the seed
	_held = false
	fishing.advance(STEP)
	t.ok(_cast(farmer))
	t.eq(fishing.casts(), 2)
	t.eq(fishing.fish_id, RpgFishing.fish_for(FISH, "spring", "morning", "pond", 77, 2))
	_cleanup()

func test_a_fish_that_is_not_held_gets_away(t) -> void:
	var game := _game(5)
	var map := _map()
	var farmer := _farmer(game, map)
	var state: RpgGameState = game["state"]
	var mode: RpgFarmMode = game["mode"]
	var fishing: RpgFishing = game["fishing"]
	var calendar: RpgCalendar = game["calendar"]
	var lost: Array[String] = []
	fishing.lost.connect(func(why: String) -> void: lost.append(why))
	var energy := mode.energy.value
	var minute := calendar.minute
	t.ok(_cast(farmer))
	# nobody touches the button: the zone sinks to the bottom and the meter drains
	t.ok(_run(fishing, func() -> bool: return fishing.state == RpgFishing.REELING), "the bar opens")
	fishing.mark = 0.9
	fishing._target = 0.9
	t.ok(_run(fishing, func() -> bool: return fishing.state == RpgFishing.IDLE), "the cast ends")
	t.eq(lost, [RpgFishing.AWAY] as Array[String], "a miss")
	t.ok(_toasts.has(RpgFarmStrings.t("FARM_FISH_AWAY")))
	for id: StringName in [&"fish_perch", &"fish_carp", &"fish_eel"]:
		t.eq(state.inventory.count(id), 0, "no fish")
	t.eq(mode.energy.value, energy - 3, "the cast was paid for all the same")
	t.eq(calendar.minute, minute + RpgFishing.CAST_MINUTES + RpgFishing.REEL_MINUTES)
	t.ok(not farmer.fishing and not farmer.move_locked)
	# `use` again while waiting pulls the line in: no fish, and that press casts nothing
	t.ok(_cast(farmer))
	_held = true  # still the press that cast
	fishing.advance(STEP)
	t.eq(fishing.state, RpgFishing.WAITING, "the press that cast does not pull it in")
	_held = false
	fishing.advance(STEP)
	_held = true
	fishing.advance(STEP)
	t.eq(fishing.state, RpgFishing.IDLE)
	t.eq(lost[lost.size() - 1], RpgFishing.PULLED)
	t.ok(not _cast(farmer), "the press that pulled it in casts nothing")
	_held = false
	fishing.advance(STEP)
	t.ok(_cast(farmer), "the next press does")
	# a new day ends a cast without a word
	calendar.end_day()
	t.eq(fishing.state, RpgFishing.IDLE)
	t.eq(lost[lost.size() - 1], RpgFishing.ENDED)
	t.ok(not farmer.fishing)
	# a full bag lets the fish go
	state.inventory.capacity = 1
	t.ok(_cast(farmer))
	var script := func() -> void: _held = fishing.mark > fishing.zone
	t.ok(_run(fishing, func() -> bool: return fishing.state == RpgFishing.IDLE, 40.0, script))
	t.eq(lost[lost.size() - 1], RpgFishing.FULL)
	_cleanup()

func test_no_cast_at_a_well_or_away_from_water(t) -> void:
	var game := _game(9)
	var map := _map("well")
	var farmer := _farmer(game, map)
	var mode: RpgFarmMode = game["mode"]
	var fishing: RpgFishing = game["fishing"]
	var calendar: RpgCalendar = game["calendar"]
	var energy := mode.energy.value
	var minute := calendar.minute
	t.eq(RpgFishing.water_kind(map["field"], WATER_CELL), "well")
	t.ok(not _cast(farmer), "a well has no fish")
	t.eq(fishing.state, RpgFishing.IDLE)
	t.ok(_toasts.has(RpgFarmStrings.t("FARM_FISH_WELL")), "a toast says so: %s" % [_toasts])
	t.eq(mode.energy.value, energy, "and it costs nothing")
	t.eq(calendar.minute, minute)
	t.eq(fishing.casts(), 0)
	t.ok(not farmer.fishing and not farmer.move_locked)
	# a pond, but the farmer looks at dry land
	(map["water"] as RpgWaterSource).kind = "pond"
	farmer.facing = "up"
	t.ok(not (map["field"] as RpgField).is_water(farmer.tile_ahead()))
	t.ok(not _cast(farmer), "no water ahead")
	t.eq(mode.energy.value, energy)
	t.eq(fishing.casts(), 0)
	# at zero energy no tool works, the rod neither
	farmer.facing = "down"
	mode.energy.value = 0
	t.ok(not _cast(farmer))
	t.eq(fishing.state, RpgFishing.IDLE)
	mode.energy.fill()
	# a map with water tiles and no body over them is a pond
	(map["water"] as RpgWaterSource).free()
	t.eq(RpgFishing.water_kind(map["field"], WATER_CELL), "pond")
	t.ok(_cast(farmer))
	_cleanup()

func test_which_fish_bites_by_the_calendar_and_nothing_where_none_does(t) -> void:
	var game := _game(123)
	var map := _map()
	var farmer := _farmer(game, map)
	var mode: RpgFarmMode = game["mode"]
	var fishing: RpgFishing = game["fishing"]
	var calendar: RpgCalendar = game["calendar"]
	var cases := [[1, 7 * 60, ["fish_perch"]], [3, 20 * 60, ["fish_carp", "fish_eel"]], [2, 13 * 60, ["fish_perch"]], [0, 13 * 60, ["fish_perch", "fish_carp"]]]
	for case: Array in cases:
		var names: Array = case[2]
		for attempt in 6:
			calendar.season = case[0]
			calendar.minute = case[1]
			mode.energy.fill()
			t.ok(_cast(farmer))
			t.ok(names.has(fishing.fish_id), "%s at minute %d: %s" % [calendar.season_name(), case[1], fishing.fish_id])
			fishing.cancel()
	# a table whose fish do not bite now: the wait ends with nothing
	fishing.cancel()
	mode.forage.fish.clear()
	mode.forage.fish.append({"id": "fish_ice", "item": "fish_ice", "seasons": ["winter"], "times": ["evening"], "water": ["pond"]})
	calendar.season = 0
	calendar.minute = 8 * 60
	t.ok(_cast(farmer), "the line goes out all the same")
	t.eq(fishing.fish_id, "")
	var lost: Array[String] = []
	fishing.lost.connect(func(why: String) -> void: lost.append(why))
	t.ok(_run(fishing, func() -> bool: return fishing.state == RpgFishing.IDLE, 6.0))
	t.eq(lost, [RpgFishing.NOTHING] as Array[String])
	t.ok(_toasts.has(RpgFarmStrings.t("FARM_FISH_NOTHING")))
	t.eq(RpgFishingBar.offset_of(1.0, 80.0), 0.0, "the top of the bar")
	t.eq(RpgFishingBar.offset_of(0.25, 80.0), 60.0)
	t.eq(RpgFishingBar.length_for(180.0), 72.0)
	_cleanup()
