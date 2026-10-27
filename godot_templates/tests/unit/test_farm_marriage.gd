extends RefCounted
## T17.26: marriage. Who can be courted, the eight hearts and the bouquet, the ten and the
## pendant, the wedding three days later on a day for everybody, the spouse's day and its NPC in
## the farmhouse, the morning's help (watering, feeding, the table), neglect, the shop's rows,
## the atoms of the dialogue, the save, and a farm with marriage and without festivals.

const Fixtures := preload("../lib/fixtures.gd")
const People := preload("../../builder/recipes/farm/people_recipes.gd")
const FarmBuild := preload("../../builder/recipes/farm/farm_build.gd")
const MarriageRecipe := preload("../../builder/recipes/farm/marriage_recipe.gd")

const CROPS := [
	{"id": "corn", "name": "Corn", "seed": "seed_corn", "produce": "crop_corn", "seasons": ["spring", "summer", "autumn"], "days": 3, "stages": 4, "regrow": 0, "seed_price": 15, "price": 30, "energy": 14},
]
const PRICES := {&"crop_corn": 30, &"seed_corn": 15, &"stone": 2, &"bouquet": 200, &"pendant": 2000}
const VILLAGE := "starter_map"
const HOUSE_PATH := "res://test_marriage_house.tscn"
const NPC_PATH := "user://test_farm_marriage_npc.tscn"
const PEOPLE := [
	{
		"id": "anna", "name": "Anna", "home": 1, "job": "shopkeeper", "courtable": false,
		"loves": ["crop_corn"], "likes": [], "dislikes": ["stone"],
		"schedule": [{"hour": 6, "map": VILLAGE, "place": "home_1"}, {"hour": 8, "map": VILLAGE, "place": "work"}, {"hour": 18, "map": VILLAGE, "place": "home_1"}],
	},
	{
		"id": "bert", "name": "Bert", "home": 2, "job": "", "courtable": true, "scene": NPC_PATH,
		"loves": ["stone"], "likes": [], "dislikes": ["crop_corn"],
		"schedule": [{"hour": 6, "map": VILLAGE, "place": "home_2"}, {"hour": 9, "map": VILLAGE, "place": "square_2"}, {"hour": 19, "map": VILLAGE, "place": "home_2"}],
	},
	{"id": "clara", "name": "Clara", "home": 1, "job": "", "loves": [], "likes": [], "dislikes": [], "schedule": [{"hour": 6, "map": VILLAGE, "place": "home_1_2"}]},
]
const EVENTS := [
	{"id": "egg_hunt", "kind": "egg_hunt", "name": "Egg hunt", "season": "spring", "day": 12, "from": 9, "to": 20, "map": VILLAGE, "place": "square", "spots": ["festival_egg_1"], "each": 20, "goal": 1},
]
const HEARTS := RpgFriendship.HEART_POINTS

var _made: Array[Node] = []

func _crops() -> RpgCropData:
	var data := RpgCropData.new()
	data.add_list(CROPS)
	return data

## A farm's game: the items, the mode with its calendar, the people. {state, mode, calendar,
## events, friends, marriage}
func _game(courting: bool = true, festivals: bool = true) -> Dictionary:
	var registry := {}
	for id: StringName in PRICES.keys():
		var def := Fixtures.item(id)
		def.value = PRICES[id]
		registry[id] = def
	var state := Fixtures.install_state(registry) as RpgGameState
	state.inventory.registry = state.items
	var mode := RpgFarmMode.new()
	mode.crops = _crops()
	mode.festivals = festivals
	mode.courting = courting
	mode._ready()
	_made.append(mode)
	var friends := RpgFriendship.current()
	friends.add_list(PEOPLE)
	if festivals:
		mode.events.add_list(EVENTS)
	return {"state": state, "mode": mode, "calendar": RpgCalendar.current(), "events": mode.events, "friends": friends, "marriage": mode.marriage}

func _go_to(calendar: RpgCalendar, season: int, day: int, year: int = 1) -> void:
	calendar.season = season
	calendar.day = day
	calendar.year = year
	calendar.minute = 12 * 60

func _cleanup() -> void:
	Fixtures.tree().paused = false
	for node in _made:
		if is_instance_valid(node):
			node.free()
	_made.clear()
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()
	RpgSchedule.source = Callable()
	RpgSchedule.override = Callable()
	RpgFriendship.cap_of = Callable()
	RpgSchedule.set_weather("")

## Bert is courted and at ten hearts.
func _courted(game: Dictionary) -> void:
	var state: RpgGameState = game["state"]
	var friends: RpgFriendship = game["friends"]
	var marriage: RpgMarriage = game["marriage"]
	friends.add_points("bert", 8 * HEARTS)
	state.inventory.add(&"bouquet", 1)
	marriage.give("bert", &"bouquet")
	friends.add_points("bert", 2 * HEARTS)

## Bert is married: the pendant, then the nights up to the wedding's.
func _married(game: Dictionary) -> void:
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var marriage: RpgMarriage = game["marriage"]
	_courted(game)
	state.inventory.add(&"pendant", 1)
	marriage.give("bert", &"pendant")
	for i in RpgMarriage.WEDDING_AFTER + 1:
		calendar.end_day()

## A farmhouse: a room of 8 x 7 tiles of 16 px, the bed's flags as a bed at (1, 1) leaves them
## (the farmer wakes on (2, 2)).
func _house(state: RpgGameState) -> RpgMapRoot:
	var map := RpgMapRoot.new()
	map.name = "FarmHouse"
	map.map_id = "test_marriage_house"
	map.scene_file_path = HOUSE_PATH
	var layer := TileMapLayer.new()
	layer.name = "Ground"
	var tiles := TileSet.new()
	tiles.tile_size = Vector2i(16, 16)
	var source := TileSetAtlasSource.new()
	source.texture = ImageTexture.create_from_image(Image.create_empty(16, 16, false, Image.FORMAT_RGBA8))
	source.texture_region_size = Vector2i(16, 16)
	source.create_tile(Vector2i.ZERO)
	tiles.add_source(source, 0)
	layer.tile_set = tiles
	for x in 8:
		for y in 7:
			layer.set_cell(Vector2i(x, y), 0, Vector2i.ZERO)
	map.add_child(layer)
	var sorted := Node2D.new()
	sorted.name = "YSorted"
	map.add_child(sorted)
	var entities := Node2D.new()
	entities.name = "Entities"
	sorted.add_child(entities)
	state.set_flag(RpgBed.FLAG_ENTITY, "map", HOUSE_PATH)
	state.set_flag(RpgBed.FLAG_ENTITY, "x", 40.0)
	state.set_flag(RpgBed.FLAG_ENTITY, "y", 40.0)
	state.set_flag(RpgBed.FLAG_ENTITY, "known", true)
	_made.append(map)
	return map

## The scene of an NPC that the spouse in the farmhouse is made of.
func _npc_scene() -> void:
	var npc := RpgNpc.new()
	npc.name = "Bert"
	var packed := PackedScene.new()
	packed.pack(npc)
	ResourceSaver.save(packed, NPC_PATH)
	npc.free()

# ---------------------------------------------------------------- without it

func test_a_farm_without_marriage_has_none(t) -> void:
	var game := _game(false)
	var mode: RpgFarmMode = game["mode"]
	var friends: RpgFriendship = game["friends"]
	var state: RpgGameState = game["state"]
	t.ok(mode.marriage != null and not mode.marriage.enabled, "the part is there and does nothing")
	t.ok(RpgMarriage.current() == null and not RpgFriendship.cap_of.is_valid())
	friends.add_points("bert", 10 * HEARTS)
	t.eq(friends.hearts("bert"), 10, "nobody is held at eight hearts")
	state.inventory.add(&"bouquet", 1)
	t.eq(friends.gift("bert", &"bouquet"), RpgFriendship.NEUTRAL, "a bouquet is a gift like any other")
	t.ok(not RpgCondition.evaluate("courting:bert") and not RpgCondition.evaluate("spouse:bert"), "the atoms are false, not unknown")
	var calendar: RpgCalendar = game["calendar"]
	var before := friends.points_of("bert")
	calendar.end_day()
	t.eq(friends.points_of("bert"), before, "and nothing is neglected")
	_cleanup()

# ---------------------------------------------------------------- who and the hearts

func test_who_can_be_courted_and_the_eight_hearts(t) -> void:
	var game := _game()
	var friends: RpgFriendship = game["friends"]
	var marriage: RpgMarriage = game["marriage"]
	t.ok(RpgMarriage.current() == marriage)
	t.ok(marriage.is_courtable("bert") and not marriage.is_courtable("anna"))
	t.ok(not marriage.is_courtable("clara"), "an entry without the key is the plan's: not planned, not courtable")
	marriage.add_planned([{"id": "clara", "courtable": true}, {"id": "anna", "courtable": true}])
	t.ok(marriage.is_courtable("clara"), "the planned people's key counts where the entry has none")
	t.ok(not marriage.is_courtable("anna"), "the user's file wins")
	t.eq(marriage.courtable(), ["bert", "clara"] as Array[String])
	friends.add_points("bert", 10 * HEARTS)
	friends.add_points("anna", 10 * HEARTS)
	t.eq(friends.hearts("bert"), RpgMarriage.COURT_HEARTS, "somebody to court has eight hearts until courted")
	t.eq(friends.hearts("anna"), 10)
	_cleanup()

func test_a_bouquet_from_eight_hearts_begins_courting(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var friends: RpgFriendship = game["friends"]
	var marriage: RpgMarriage = game["marriage"]
	state.inventory.add(&"bouquet", 2)
	friends.add_points("bert", 7 * HEARTS)
	t.eq(friends.gift("bert", &"bouquet"), "", "below eight hearts it is not taken")
	t.eq(state.inventory.count(&"bouquet"), 2, "and stays in the bag")
	friends.add_points("anna", 10 * HEARTS)
	t.eq(friends.gift("anna", &"bouquet"), "", "nor by somebody who cannot be courted")
	friends.add_points("bert", HEARTS)
	var left := friends.gifts_left("bert")
	t.eq(friends.gift("bert", &"bouquet"), RpgMarriage.COURTING)
	t.eq(state.inventory.count(&"bouquet"), 1)
	t.eq(friends.gifts_left("bert"), left, "it is none of the week's gifts")
	t.eq(marriage.stage_of("bert"), RpgMarriage.COURTING)
	t.ok(RpgCondition.evaluate("courting:bert") and not RpgCondition.evaluate("engaged:bert"))
	t.eq(friends.gift("bert", &"bouquet"), "", "a second bouquet is not taken")
	friends.add_points("bert", 5 * HEARTS)
	t.eq(friends.hearts("bert"), 10, "the two last hearts are open")
	_cleanup()

# ---------------------------------------------------------------- the pendant and the wedding

func test_a_pendant_at_ten_hearts_and_the_wedding_three_days_later(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var events: RpgFarmEvents = game["events"]
	var friends: RpgFriendship = game["friends"]
	var marriage: RpgMarriage = game["marriage"]
	_go_to(calendar, 0, 2)
	state.inventory.add(&"pendant", 1)
	friends.add_points("bert", 8 * HEARTS)
	t.eq(marriage.give("bert", &"pendant"), "", "nobody who is not courted takes it")
	state.inventory.add(&"bouquet", 1)
	marriage.give("bert", &"bouquet")
	friends.add_points("bert", HEARTS)
	t.eq(marriage.give("bert", &"pendant"), "", "nor at nine hearts")
	friends.add_points("bert", HEARTS)
	var today := calendar.today()
	t.eq(friends.gift("bert", &"pendant"), RpgMarriage.ENGAGED)
	t.eq(state.inventory.count(&"pendant"), 0)
	t.eq(marriage.engaged(), "bert")
	t.eq(marriage.wedding_day(), today + RpgMarriage.WEDDING_AFTER)
	t.ok(RpgCondition.evaluate("engaged:bert") and not RpgCondition.evaluate("courting:bert"))
	var wedding := events.events_of(today + RpgMarriage.WEDDING_AFTER)
	t.eq(RpgUtil.to_str(RpgFarmEvents.festival_of(wedding).get("kind", "")), RpgFarmEvents.WEDDING, "the wedding is a day for everybody")
	t.eq(RpgUtil.to_str(RpgFarmEvents.festival_of(wedding).get("person", "")), "bert")
	state.inventory.add(&"pendant", 1)
	t.eq(marriage.give("bert", &"pendant"), "", "one pendant only")
	# the days up to it and its night
	for i in RpgMarriage.WEDDING_AFTER:
		calendar.end_day()
		t.eq(marriage.spouse(), "", "not before the wedding's night")
	t.ok(events.has_kind(RpgFarmEvents.WEDDING) and RpgCondition.evaluate("event:wedding"))
	t.ok(RpgFarmShop.day_off_reason() != "", "the shop is closed on the wedding's day")
	t.eq(RpgUtil.to_str(events.schedule_override("anna", 12).get("place", "")), "square", "the people gather on the square")
	calendar.end_day()
	t.eq(marriage.spouse(), "bert")
	t.eq(marriage.engaged(), "")
	t.ok(RpgCondition.evaluate("spouse:bert") and not RpgCondition.evaluate("engaged:bert") and not RpgCondition.evaluate("courting:bert"))
	_cleanup()

func test_the_wedding_is_on_no_festival(t) -> void:
	var game := _game()
	var calendar: RpgCalendar = game["calendar"]
	var marriage: RpgMarriage = game["marriage"]
	_go_to(calendar, 0, 12 - RpgMarriage.WEDDING_AFTER)
	_courted(game)
	(game["state"] as RpgGameState).inventory.add(&"pendant", 1)
	marriage.give("bert", &"pendant")
	t.eq(marriage.wedding_day(), calendar.today() + RpgMarriage.WEDDING_AFTER + 1, "the egg hunt's day is passed over")
	_cleanup()

# ---------------------------------------------------------------- the spouse's day

func test_the_spouse_has_a_day_of_its_own(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var marriage: RpgMarriage = game["marriage"]
	var map := _house(state)
	_go_to(calendar, 0, 2)
	_married(game)
	t.eq(marriage.house_id(), "test_marriage_house")
	marriage.refresh(map)
	t.eq(marriage.home_cell(), [3, 2], "beside the cell the farmer wakes on, east of it")
	_go_to(calendar, 0, 3)  # weekday 2: no afternoon on the square
	var home := marriage.spouse_entry(7)
	t.eq([home.get("map"), home.get("cell")], ["test_marriage_house", [3, 2]])
	t.eq(marriage.spouse_entry(14), home, "at home in the afternoon too")
	t.ok(RpgUtil.to_str(marriage.spouse_entry(23).get("map", "")).ends_with(RpgMarriage.ASLEEP), "asleep at night")
	t.ok(RpgUtil.to_str(marriage.spouse_entry(1).get("map", "")).ends_with(RpgMarriage.ASLEEP))
	_go_to(calendar, 0, 2)  # weekday 1
	t.eq(RpgUtil.to_str(marriage.spouse_entry(14).get("place", "")), "square_2", "its own spot of the square")
	RpgSchedule.set_weather("rain")
	t.eq(marriage.spouse_entry(14), home, "not in the rain")
	RpgSchedule.set_weather("")
	t.eq(RpgSchedule.override.call("bert", 14), marriage.spouse_entry(14), "the schedules ask it")
	t.eq(RpgSchedule.override.call("anna", 14), {}, "for the spouse only")
	_go_to(calendar, 0, 12)
	t.eq(RpgUtil.to_str(RpgSchedule.override.call("bert", 12).get("place", "")), "square_2", "a festival wins")
	_cleanup()

func test_the_spouse_is_at_home_in_the_farmhouse(t) -> void:
	_npc_scene()
	var game := _game()
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var marriage: RpgMarriage = game["marriage"]
	var map := _house(state)
	_go_to(calendar, 0, 2)
	t.ok(marriage.refresh(map) == null, "nobody before the wedding")
	_married(game)
	var npc := marriage.refresh(map) as RpgNpc
	t.ok(npc != null and npc.get_parent() == map.get_node("YSorted/Entities"))
	t.eq(npc.entity_id, "person_bert")
	var schedule := npc.schedule()
	t.ok(schedule != null and schedule.person == "bert")
	calendar.minute = 8 * 60
	schedule.place_now()
	t.ok(not schedule.away() and npc.visible, "at home in the morning")
	t.eq(npc.position, RpgSchedule.cell_position(map, Vector2i(3, 2)))
	t.ok(npc.dialogue != null and npc.dialogue.lines.size() == 1, "it says a line of its own")
	t.eq(marriage.refresh(map), npc, "made once")
	calendar.minute = 23 * 60
	schedule.place_now()
	t.ok(schedule.away() and not npc.visible, "not seen at night")
	DirAccess.remove_absolute(NPC_PATH)
	_cleanup()

# ---------------------------------------------------------------- the morning's help

func test_the_first_morning_the_spouse_waters_part_of_the_plot(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var marriage: RpgMarriage = game["marriage"]
	_go_to(calendar, 0, 2)
	_courted(game)
	state.inventory.add(&"pendant", 1)
	marriage.give("bert", &"pendant")
	for i in RpgMarriage.WEDDING_AFTER:
		calendar.end_day()
	# the field of the farm: five cells with a crop, two bare
	var cells := {}
	for x in 5:
		cells["%d,0" % x] = {"w": true, "crop": "corn", "grown": 0, "dead": false, "idle": 0}
	cells["0,1"] = {"w": true, "crop": "", "grown": 0, "dead": false, "idle": 0}
	cells["1,1"] = {"w": true, "crop": "", "grown": 0, "dead": false, "idle": 0}
	state.set_flag(RpgField.FLAG_ENTITY, RpgMarriage.FARM_FIELD, cells)
	(game["mode"] as RpgFarmMode).weather.force_tomorrow(RpgFarmWeather.SUN)
	calendar.end_day()  # the wedding's night: married; the soil dries; the morning waters
	t.eq(marriage.spouse(), "bert")
	var help := marriage.help_today()
	t.eq(RpgUtil.to_str(help.get("kind", "")), RpgMarriage.WATER, "the first morning is a watering one")
	t.eq(RpgUtil.to_int(help.get("count", 0)), 4, "half of the seven dry cells")
	var saved := RpgUtil.to_dict(state.get_flag(RpgField.FLAG_ENTITY, RpgMarriage.FARM_FIELD, {}))
	var wet: Array[String] = []
	for key: Variant in saved.keys():
		if RpgUtil.to_bool(RpgUtil.to_dict(saved[key]).get("w", false)):
			wet.append(RpgUtil.to_str(key))
	wet.sort()
	t.eq(wet, ["0,0", "1,0", "2,0", "3,0"] as Array[String], "the cells with a crop first")
	_cleanup()

func test_the_help_goes_round_the_week(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var marriage: RpgMarriage = game["marriage"]
	t.eq(marriage.help_on(10), RpgMarriage.QUIET, "nothing without a spouse")
	_go_to(calendar, 0, 2)
	_married(game)
	var wed := calendar.today() - 1
	t.eq(marriage.help_on(wed + 1), RpgMarriage.WATER)
	var kinds := {}
	for i in range(wed + 2, wed + 9):
		kinds[marriage.help_on(i)] = true
		t.eq(marriage.help_on(i), marriage.help_on(i), "the same day, the same help")
	t.ok(kinds.has(RpgMarriage.WATER) and kinds.has(RpgMarriage.FEED) and kinds.has(RpgMarriage.TABLE) and kinds.has(RpgMarriage.QUIET), "a week has every kind")
	# the table: a produce of the season, taken with interact
	var map := _house(state)
	marriage.refresh(map)
	var done := {}
	for i in range(wed + 2, wed + 9):
		if marriage.help_on(i) == RpgMarriage.TABLE:
			done = marriage.do_help(i)
			break
	t.eq(RpgUtil.to_str(done.get("item", "")), "crop_corn")
	t.eq(marriage.on_table(), &"crop_corn")
	marriage.refresh(map)
	var table := map.get_node("YSorted/Entities").get_node_or_null(RpgSpouseTable.NODE_NAME) as RpgSpouseTable
	t.ok(table != null and table.item_id == &"crop_corn", "it lies on the table of the farmhouse")
	table.interact()
	t.eq(state.inventory.count(&"crop_corn"), 1)
	t.eq(marriage.on_table(), &"")
	marriage.refresh(map)
	var gone: Node = map.get_node("YSorted/Entities").get_node_or_null(RpgSpouseTable.NODE_NAME)
	t.ok(gone == null or gone.is_queued_for_deletion(), "the table goes with it")
	# a farm without animals is fed by nobody: a quiet morning
	for i in range(wed + 2, wed + 9):
		if marriage.help_on(i) == RpgMarriage.FEED:
			t.eq(RpgUtil.to_str(marriage.do_help(i).get("kind", "")), RpgMarriage.QUIET)
			break
	_cleanup()

# ---------------------------------------------------------------- neglect, the shop, the save

func test_neglected_friendship_falls_slowly(t) -> void:
	var game := _game()
	var calendar: RpgCalendar = game["calendar"]
	var friends: RpgFriendship = game["friends"]
	friends.talk("anna")
	friends.talk("clara")
	var anna := friends.points_of("anna")
	var clara := friends.points_of("clara")
	calendar.end_day()
	t.eq(friends.points_of("anna"), anna, "talked to today: nothing lost")
	friends.talk("anna")
	calendar.end_day()
	t.eq(friends.points_of("clara"), clara - RpgMarriage.DECAY_POINTS, "a day without a talk costs a little")
	t.eq(friends.points_of("anna"), anna + RpgFriendship.TALK_POINTS)
	t.eq(friends.points_of("bert"), 0, "nobody who was never met")
	for i in 40:
		calendar.end_day()
	t.eq(friends.points_of("clara"), 0, "and never below nothing")
	_cleanup()

func test_the_shop_sells_the_bouquet_and_the_pendant_until_the_wedding(t) -> void:
	var game := _game()
	var marriage: RpgMarriage = game["marriage"]
	var rows: Array = []
	for row: Dictionary in RpgFarmShop.new().seasonal_stock("spring"):
		rows.append(row["item_id"])
	t.ok(rows.has("bouquet") and rows.has("pendant"))
	_married(game)
	t.eq(marriage.shop_rows("spring"), [], "a married farmer buys neither")
	_cleanup()

func test_the_state_round_trips_through_a_save(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var marriage: RpgMarriage = game["marriage"]
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER) as RpgSaveManager
	save.dir = "user://test_farm_marriage_%d" % Time.get_ticks_usec()
	_go_to(calendar, 0, 2)
	_courted(game)
	state.inventory.add(&"pendant", 1)
	marriage.give("bert", &"pendant")
	var kept := {"courting": marriage.courting(), "engaged": marriage.engaged(), "wedding": marriage.wedding_day(), "spouse": marriage.spouse()}
	t.ok(save.save(1))
	var written: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(save.dir.path_join("slot_1.json")))
	t.ok(not written.has("marriage") and not written.has(RpgMarriage.FLAG_ENTITY), "the save has no new key")
	t.ok(RpgUtil.to_dict(written.get("flags", {})).has(RpgMarriage.FLAG_ENTITY), "the state is in the flags")
	for i in RpgMarriage.WEDDING_AFTER + 1:
		calendar.end_day()
	t.eq(marriage.spouse(), "bert")
	t.ok(save.load(1))
	t.eq({"courting": marriage.courting(), "engaged": marriage.engaged(), "wedding": marriage.wedding_day(), "spouse": marriage.spouse()}, kept)
	state.new_game()
	t.ok(marriage.courting().is_empty() and marriage.spouse() == "" and marriage.engaged() == "", "a new game has none of it")
	for file: String in DirAccess.get_files_at(save.dir):
		DirAccess.remove_absolute(save.dir.path_join(file))
	DirAccess.remove_absolute(save.dir)
	_cleanup()

# ---------------------------------------------------------------- without festivals

func test_a_farm_with_marriage_and_without_festivals_has_its_wedding(t) -> void:
	var game := _game(true, false)
	var events: RpgFarmEvents = game["events"]
	var calendar: RpgCalendar = game["calendar"]
	var marriage: RpgMarriage = game["marriage"]
	t.ok(events.enabled and not events.with_files, "the events are there for the wedding")
	t.ok(RpgFarmEvents.current() == events)
	t.ok(events.events.is_empty() and events.birthday_of("bert").is_empty(), "no festival and no birthday")
	_go_to(calendar, 0, 2)
	_courted(game)
	(game["state"] as RpgGameState).inventory.add(&"pendant", 1)
	marriage.give("bert", &"pendant")
	t.eq(events.added().size(), 1)
	for i in RpgMarriage.WEDDING_AFTER:
		calendar.end_day()
	t.ok(events.has_kind(RpgFarmEvents.WEDDING))
	calendar.end_day()
	t.eq(marriage.spouse(), "bert")
	_cleanup()

# ---------------------------------------------------------------- the atoms and the builder

func test_the_atoms_of_marriage_are_known(t) -> void:
	for atom: String in ["courting:bert", "engaged:bert", "spouse:bert"]:
		t.eq(RpgCondition.atom_problem(atom), "", atom)
	t.ok(RpgCondition.atom_problem("spouse:") != "", "an atom needs an id")
	t.ok(RpgCondition.ATOMS.has("spouse:") and RpgCondition.MARRIAGE_FLAGS == RpgMarriage.FLAG_ENTITY)

func test_the_builder_and_the_game_agree(t) -> void:
	var people := People.new()
	var res: RpgDialogueResource = people._dialogue({"id": "bert", "name": "Bert", "job": "", "courtable": true})
	var conditions: Array[String] = []
	for line in res.lines:
		conditions.append(line.condition)
	t.eq(conditions.slice(0, 3), ["spouse:bert", "engaged:bert", "courting:bert"] as Array[String], "a person to court has its three lines first")
	var plain: RpgDialogueResource = people._dialogue({"id": "anna", "name": "Anna", "job": ""})
	for line in plain.lines:
		t.ok(not line.condition.contains("spouse:"), "and nobody else")
	t.eq(MarriageRecipe.ITEMS, ["bouquet", "pendant"] as Array[String])
	t.eq(StringName(MarriageRecipe.ITEMS[0]), RpgMarriage.BOUQUET)
	t.eq(StringName(MarriageRecipe.ITEMS[1]), RpgMarriage.PENDANT)
	var item := MarriageRecipe.make_item("pendant") as RpgItemDefinition
	t.eq(item.display_name, "ITEM_PENDANT_NAME")
	t.ok(RpgFarmStrings.KEYS.has("ITEM_PENDANT_NAME") and RpgFarmStrings.KEYS.has("ITEM_BOUQUET_DESC"))
	t.ok(item.icon != null and item.value == 2000)

# ---------------------------------------------------------------- children (T18.17)

func test_the_spouse_asks_a_child_is_born_lies_in_the_crib_and_then_walks(t) -> void:
	_npc_scene()
	var game := _game(true, false)
	var mode: RpgFarmMode = game["mode"]
	var calendar: RpgCalendar = game["calendar"]
	var family := mode.family
	family.enabled = true
	family.attach()
	_married(game)
	t.eq((game["marriage"] as RpgMarriage).spouse(), "bert")
	t.ok(not family.should_ask(), "not the week of the wedding")
	for i in RpgFarmChildren.ASK_AFTER_DAYS:
		calendar.end_day()
	t.ok(RpgUtil.to_int(RpgFarmChildren._flag("asked", -1)) >= 0, "asked on the morning a week after the wedding")
	family.agree()
	t.eq(RpgFarmChildren.due(), calendar.today() + RpgFarmChildren.CHILD_DAYS)
	for i in RpgFarmChildren.CHILD_DAYS:
		calendar.end_day()
	var kids := RpgFarmChildren.kids()
	t.eq(kids.size(), 1, "born")
	t.ok(RpgFarmChildren.is_baby(kids[0]))
	var house := _house(game["state"])
	var crib := Node2D.new()
	crib.name = "Crib"
	crib.position = Vector2(88, 80)
	(house.get_node("YSorted/Entities") as Node2D).add_child(crib)
	var shown := family.show_on(house)
	t.eq(shown.size(), 1)
	t.ok((shown[0] as Node2D).position.distance_to(crib.position) < 8.0, "in the crib")
	t.ok(not RpgFarmChildren.walks(shown[0]))
	t.eq(shown[0].scale, Vector2(RpgFarmChildren.STAND_IN_SCALE, RpgFarmChildren.STAND_IN_SCALE), "the spouse's picture, smaller")
	for i in RpgFarmChildren.TODDLER_DAYS:
		calendar.end_day()
	shown = family.show_on(house)
	t.ok(RpgFarmChildren.walks(shown[0]), "a child that walks the farmhouse")
	var saved: Dictionary = JSON.parse_string(JSON.stringify((game["state"] as RpgGameState).to_dict()))
	(game["state"] as RpgGameState).new_game()
	t.eq(RpgFarmChildren.kids().size(), 0)
	(game["state"] as RpgGameState).from_dict(saved)
	t.eq(RpgFarmChildren.kids().size(), 1, "saved")
	var page := RpgPeoplePage.new()
	Fixtures.tree().root.add_child(page)
	t.ok(page.rows().any(func(b: Button) -> bool: return b.text.begins_with(str(kids[0]["name"]))), "in the family list")
	page.free()
	DirAccess.remove_absolute(NPC_PATH)
	_cleanup()

func test_at_most_two_and_none_without_the_option(t) -> void:
	var game := _game(true, false)
	var mode: RpgFarmMode = game["mode"]
	t.ok(not mode.family.enabled, "a farm without the option")
	mode.family.enabled = true
	_married(game)
	mode.family.agree()
	mode.family.born()
	mode.family.agree()
	mode.family.born()
	mode.family.agree()
	t.eq([RpgFarmChildren.kids().size(), RpgFarmChildren.due()], [2, -1], "two at most")
	_cleanup()
