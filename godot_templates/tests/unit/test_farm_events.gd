extends RefCounted
## T17.25: festivals and birthdays. The year's four festivals and their days, the shop's day
## off, the people on the square, the four things to do and their prizes, the birthday gift,
## the calendar page, the day before, the save, and an event added at run time (a wedding).

const Fixtures := preload("../lib/fixtures.gd")
const People := preload("../../builder/recipes/farm/people_recipes.gd")
const EventsRecipe := preload("../../builder/recipes/farm/events_recipe.gd")
const MapBuild := preload("../../builder/lib/map_build.gd")

const CROPS := [
	{"id": "corn", "name": "Corn", "seed": "seed_corn", "produce": "crop_corn", "seasons": ["spring", "summer", "autumn"], "days": 3, "stages": 4, "regrow": 0, "seed_price": 15, "price": 30, "energy": 14},
	{"id": "pumpkin", "name": "Pumpkin", "seed": "seed_pumpkin", "produce": "crop_pumpkin", "seasons": ["autumn"], "days": 2, "stages": 3, "regrow": 0, "seed_price": 40, "price": 90, "energy": 12},
]
## Item id -> its price; the hoe is a key item without one.
const PRICES := {&"crop_corn": 30, &"crop_pumpkin": 90, &"seed_corn": 15, &"stone": 2, &"hoe": 0}
const VILLAGE := "starter_map"
const PEOPLE := [
	{
		"id": "anna", "name": "Anna", "home": 1, "job": "shopkeeper", "birthday": {"season": "spring", "day": 9},
		"loves": ["crop_corn"], "likes": ["crop_pumpkin"], "dislikes": ["stone"],
		"schedule": [{"hour": 6, "map": VILLAGE, "place": "home_1"}, {"hour": 8, "map": VILLAGE, "place": "work"}, {"hour": 10, "days": [6], "map": VILLAGE, "place": "square"}, {"hour": 18, "map": VILLAGE, "place": "home_1"}],
	},
	{
		"id": "bert", "name": "Bert", "home": 2, "job": "", "birthday": {"season": "summer", "day": 20},
		"loves": ["stone"], "likes": [], "dislikes": ["crop_corn"],
		"schedule": [{"hour": 6, "map": VILLAGE, "place": "home_2"}, {"hour": 9, "map": VILLAGE, "place": "square_2"}, {"hour": 19, "map": VILLAGE, "place": "home_2"}, {"hour": 9, "weather": "rain", "map": VILLAGE, "place": "home_2"}],
	},
	{"id": "clara", "name": "Clara", "home": 1, "job": "", "loves": [], "likes": [], "dislikes": [], "schedule": [{"hour": 6, "map": VILLAGE, "place": "home_1_2"}]},
]
const EGGS: Array[String] = ["festival_egg_1", "festival_egg_2", "festival_egg_3"]
## What rpggen/core/event_plan.py plans for a season of 28 days, with three eggs.
const EVENTS := [
	{"id": "egg_hunt", "kind": "egg_hunt", "name": "Egg hunt", "season": "spring", "day": 12, "from": 9, "to": 20, "map": VILLAGE, "place": "square", "spots": EGGS, "each": 20, "goal": 3, "prize": {"gold": 150}},
	{"id": "fishing_day", "kind": "fishing_count", "name": "Fishing day", "season": "summer", "day": 12, "from": 9, "to": 20, "map": VILLAGE, "place": "square", "goal": 3, "prize": {"gold": 200}},
	{"id": "harvest_fair", "kind": "produce_contest", "name": "Harvest fair", "season": "autumn", "day": 26, "from": 9, "to": 20, "map": VILLAGE, "place": "square", "table": "festival_table", "judge": "price", "goal": 90, "prize": {"gold": 300}},
	{"id": "winter_feast", "kind": "feast", "name": "Winter feast", "season": "winter", "day": 26, "from": 9, "to": 20, "map": VILLAGE, "place": "square", "table": "festival_table", "points": 60},
]

var _made: Array[Node] = []

func _crops() -> RpgCropData:
	var data := RpgCropData.new()
	data.add_list(CROPS)
	return data

## A farm's game with festivals: the items, the mode with its calendar, the people and the
## events of the plan. {state, mode, calendar, events, friends}
func _game(festivals: bool = true, events: Array = EVENTS) -> Dictionary:
	var registry := {}
	for id: StringName in PRICES.keys():
		var def := Fixtures.item(id)
		def.value = PRICES[id]
		if id == &"hoe":
			def.category = RpgItemDefinition.Category.KEY
			def.max_stack = 1
		registry[id] = def
	var state := Fixtures.install_state(registry) as RpgGameState
	state.inventory.registry = state.items
	var mode := RpgFarmMode.new()
	mode.crops = _crops()
	mode.festivals = festivals
	mode._ready()
	_made.append(mode)
	var friends := RpgFriendship.current()
	friends.add_list(PEOPLE)
	mode.events.add_list(events)
	return {"state": state, "mode": mode, "calendar": RpgCalendar.current(), "events": mode.events, "friends": friends}

## A village: a map with the places of the people and, with `markers`, those of the festivals.
func _village(markers: bool = true) -> Node2D:
	var map := RpgMapRoot.new()
	map.name = "StarterMap"
	map.map_id = VILLAGE
	var names: Array[String] = ["square", "square_2", "home_1", "home_2", "work"]
	if markers:
		names.append("festival_table")
		names.append_array(EGGS)
	for i in names.size():
		var marker := RpgSchedule.make_place(names[i])
		marker.position = Vector2(32 + i * 48, 64)
		map.add_child(marker)
	_made.append(map)
	return map

func _go_to(calendar: RpgCalendar, season: int, day: int, year: int = 1) -> void:
	calendar.season = season
	calendar.day = day
	calendar.year = year
	calendar.minute = 12 * 60

func _cleanup() -> void:
	var tree := Fixtures.tree()
	tree.paused = false
	for node in _made:
		if is_instance_valid(node):
			node.free()
	_made.clear()
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()
	RpgSchedule.source = Callable()

# ---------------------------------------------------------------- finding it

func test_a_farm_without_festivals_has_no_events(t) -> void:
	var game := _game(false)
	var mode: RpgFarmMode = game["mode"]
	var calendar: RpgCalendar = game["calendar"]
	t.ok(mode.events != null and not mode.events.enabled, "the part is there and does nothing")
	t.ok(RpgFarmEvents.current() == null, "nobody finds it")
	t.ok(not RpgSchedule.override.is_valid() and not RpgFarmShop.day_off.is_valid())
	_go_to(calendar, 0, 12)
	t.eq(RpgFarmShop.day_off_reason(), "", "a festival's day is a day like any other")
	t.ok(not RpgCondition.evaluate("festival") and not RpgCondition.evaluate("birthday:anna"), "the atoms are false, not unknown")
	# a birthday is a day like any other too
	_go_to(calendar, 0, 9)
	var friends: RpgFriendship = game["friends"]
	var state: RpgGameState = game["state"]
	state.inventory.add(&"crop_corn", 2)
	t.eq(friends.gift("anna", &"crop_corn"), RpgFriendship.LOVES)
	t.eq([friends.points_of("anna"), friends.gifts_left("anna")], [RpgFriendship.LOVE_POINTS, 1])
	t.ok(not RpgPeoplePage.detail_text(friends, "anna").contains("Birthday"))
	t.eq(mode.weather.forecast_text(), "Tomorrow's weather: Sunny.")
	_cleanup()

func test_the_mode_makes_the_events_and_lets_go_of_them(t) -> void:
	var game := _game()
	var mode: RpgFarmMode = game["mode"]
	t.ok(RpgFarmEvents.current() == mode.events and mode.events.get_parent() == mode)
	t.eq(mode.events.events.size(), 4)
	t.ok(RpgSchedule.override.is_valid() and RpgFarmShop.day_off.is_valid())
	mode.events.add_list(EVENTS)
	t.eq(mode.events.events.size(), 4, "an id is there once")
	mode.free()
	t.ok(RpgFarmEvents.current() == null, "gone with its mode")
	t.ok(not RpgSchedule.override.is_valid() and not RpgFarmShop.day_off.is_valid(), "what it set is as it was")
	_cleanup()

func test_the_users_file_takes_an_event_away_and_changes_one(t) -> void:
	var game := _game(true, [{"id": "egg_hunt", "removed": true}, {"id": "fishing_day", "kind": "gathering", "name": "Summer dance", "season": "summer", "day": 3, "map": VILLAGE, "place": "square"}, {"id": "nowhen", "kind": "feast", "name": "Nowhen"}])
	var events: RpgFarmEvents = game["events"]
	events.add_list(EVENTS)  # the planned list, after the user's
	var ids: Array[String] = []
	for entry in events.events:
		ids.append(RpgUtil.to_str(entry["id"]))
	t.eq(ids, ["fishing_day", "harvest_fair", "winter_feast"] as Array[String], "the removed one stays out, one without a date is left out")
	t.eq(RpgUtil.to_int(events.event("fishing_day")["day"]), 3, "the user's entry counts")
	t.eq(events.events_on(12, 0, 1).size(), 0)
	t.eq(RpgFarmEvents.event_name(events.events_on(3, 1, 1)[0]), "Summer dance")
	_cleanup()

# ---------------------------------------------------------------- the year

func test_a_year_of_days_has_four_festivals_on_their_days_and_none_on_others(t) -> void:
	var game := _game()
	var calendar: RpgCalendar = game["calendar"]
	var events: RpgFarmEvents = game["events"]
	var began: Array[String] = []
	var ended: Array[String] = []
	events.festival_began.connect(func(entry: Dictionary) -> void: began.append("%s %d %s" % [calendar.season_name(), calendar.day, entry["id"]]))
	events.festival_ended.connect(func(entry: Dictionary) -> void: ended.append("%s %d %s" % [calendar.season_name(), calendar.day, entry["id"]]))
	var days: Array[String] = []
	for i in 4 * 28:
		if events.is_festival():
			days.append("%s %d %s" % [calendar.season_name(), calendar.day, events.festival()["kind"]])
			t.eq(calendar.weekday(), 4, "a festival is a Friday")
		calendar.end_day()
	var wanted: Array[String] = ["spring 12 egg_hunt", "summer 12 fishing_count", "autumn 26 produce_contest", "winter 26 feast"]
	t.eq(days, wanted)
	t.eq(began, ["spring 12 egg_hunt", "summer 12 fishing_day", "autumn 26 harvest_fair", "winter 26 winter_feast"] as Array[String], "each begins in its morning")
	t.eq(ended, began, "and ends in its night, the calendar still on its day")
	t.eq([calendar.day, calendar.season, calendar.year], [1, 0, 2], "a year went by")
	t.ok(not events.is_festival() and events.festival().is_empty())
	_cleanup()

func test_a_day_the_season_no_longer_has_is_folded_into_it(t) -> void:
	t.eq([RpgFarmEvents.day_in(26, 28), RpgFarmEvents.day_in(26, 14), RpgFarmEvents.day_in(26, 7), RpgFarmEvents.day_in(12, 7), RpgFarmEvents.day_in(5, 7)], [26, 12, 5, 5, 5])
	t.eq(RpgFarmEvents.day_in(0, 28), 1)
	t.eq([RpgFarmEvents.season_index("autumn"), RpgFarmEvents.season_index(3), RpgFarmEvents.season_index(2.0), RpgFarmEvents.season_index("monsoon"), RpgFarmEvents.season_index(7), RpgFarmEvents.season_index(null)], [2, 3, 2, -1, -1, -1])
	var game := _game()
	var mode: RpgFarmMode = game["mode"]
	var calendar: RpgCalendar = game["calendar"]
	var events: RpgFarmEvents = game["events"]
	calendar.days_per_season = 7
	var days: Array[String] = []
	for i in 4 * 7:
		if events.is_festival():
			days.append("%s %d" % [calendar.season_name(), calendar.day])
		calendar.end_day()
	t.eq(days, ["spring 5", "summer 5", "autumn 5", "winter 5"] as Array[String], "a year of four weeks keeps its four festivals")
	t.eq(events.birthday_of("bert"), {"season": 1, "day": 6}, "and a birthday on the 20th is on the 6th")
	t.ok(mode != null)
	_cleanup()

# ---------------------------------------------------------------- the shop and the people

func test_the_shop_is_closed_on_a_festival_and_says_why(t) -> void:
	var game := _game()
	var calendar: RpgCalendar = game["calendar"]
	var shop := RpgFarmShop.new()
	_go_to(calendar, 0, 11)
	t.ok(shop.is_open() and shop.closed_reason() == "" and not shop.closed_all_day(), "the day before, at noon")
	_go_to(calendar, 0, 12)
	t.ok(not shop.is_open() and shop.closed_all_day(), "closed at noon of the festival")
	t.eq(shop.closed_reason(), "The shop is closed today: it is the Egg hunt.")
	calendar.minute = 7 * 60
	t.eq(shop.closed_reason(), "The shop is closed today: it is the Egg hunt.", "in the morning too: the day, not the hour")
	_go_to(calendar, 0, 13)
	t.ok(shop.is_open(), "open again the day after")
	calendar.minute = 7 * 60
	t.ok(shop.closed_reason().contains("9:00"), "and closed for its hours as ever")
	_go_to(calendar, 0, 14)
	t.ok(shop.closed_all_day() and shop.closed_reason().contains("Sunday"), "its own closed day is still its own")
	# an event that leaves the shop alone
	var events: RpgFarmEvents = game["events"]
	events.add_event({"kind": "gathering", "name": "Market", "season": "spring", "day": 16, "shop_closed": false})
	_go_to(calendar, 0, 16)
	t.ok(events.is_festival() and shop.is_open())
	_cleanup()

func test_everybody_is_on_the_square_on_a_festival_and_where_they_usually_are_the_day_after(t) -> void:
	var game := _game()
	var calendar: RpgCalendar = game["calendar"]
	var friends: RpgFriendship = game["friends"]
	var schedules := {}
	for id in friends.order:
		var schedule := RpgSchedule.new()
		schedule.person = id
		for raw: Variant in friends.schedule_of(id):
			schedule.entries.append(RpgUtil.to_dict(raw))
		_made.append(schedule)
		schedules[id] = schedule
	var places := func(hour: int) -> Array:
		calendar.minute = hour * 60
		var out: Array = []
		for id in friends.order:
			var schedule: RpgSchedule = schedules[id]
			out.append(RpgUtil.to_str(schedule.entry_in_force().get("place", "")))
		return out
	_go_to(calendar, 0, 12)
	t.eq(places.call(12), ["square", "square_2", "square"], "each at the spot of the square their own schedule names, else on the square")
	var anna: RpgSchedule = schedules["anna"]
	t.eq(anna.entry_in_force(), {"hour": 9, "map": VILLAGE, "place": "square", "facing": "down"})
	t.eq(anna.resolve(12, calendar.weekday(), ""), PEOPLE[0]["schedule"][1], "`resolve` still says what the entries say")
	t.eq(places.call(8), ["work", "home_2", "home_1_2"], "before it begins everybody is where they are every morning")
	t.eq(places.call(9), ["square", "square_2", "square"], "from 9:00")
	t.eq(places.call(19), ["square", "square_2", "square"], "to 20:00")
	t.eq(places.call(20), ["home_1", "home_2", "home_1_2"], "then home")
	RpgSchedule.set_weather("rain")
	t.eq(places.call(12), ["square", "square_2", "square"], "a festival wins over the rain")
	_go_to(calendar, 0, 13)
	t.eq(places.call(12), ["work", "home_2", "home_1_2"], "the day after, in the rain")
	RpgSchedule.set_weather("")
	t.eq(places.call(12), ["work", "square_2", "home_1_2"], "the day after: the usual places")
	_cleanup()

# ---------------------------------------------------------------- what there is to do

func test_the_egg_hunt_pays_for_each_egg_and_a_prize_for_all(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var events: RpgFarmEvents = game["events"]
	var map := _village()
	state.gold = 0
	_go_to(calendar, 0, 11)
	t.eq(events.refresh(map), 0, "nothing lies about on another day")
	_go_to(calendar, 0, 12)
	t.eq(events.refresh(map), 3, "an egg at every spot")
	var first := events.thing_at("festival_egg_1")
	t.ok(first != null and first.kind == RpgFestivalThing.EGG and first.get_parent() == map)
	var marker := RpgSchedule.find_place(map, "festival_egg_1")
	t.eq(first.position, marker.position + Vector2(0, 7), "its foot on the lower edge of the marker's cell")
	t.ok(first.get_collision_layer_value(5) and not first.monitoring, "found by `interact`, walked over")
	t.ok(not events.find_egg("square"), "a marker that is no spot of the hunt")
	first.interact()
	t.eq([state.gold, events.count(), events.found(), events.is_done()], [20, 1, ["festival_egg_1"] as Array[String], false])
	t.ok(first.is_queued_for_deletion() and events.thing_at("festival_egg_1") == null, "the egg is gone")
	t.ok(not events.find_egg("festival_egg_1"), "an egg is found once")
	t.eq(events.use_table(), "You have found 1 of 3 eggs.")
	# the map is left and entered again: what was found stays found
	t.eq(events.refresh(map), 2)
	events.thing_at("festival_egg_2").interact()
	t.eq(state.gold, 40)
	events.thing_at("festival_egg_3").interact()
	t.eq([state.gold, events.count(), events.is_done()], [60 + 150, 3, true], "the last egg pays the prize too")
	t.eq(events.things().size(), 0)
	t.eq(RpgUtil.to_dict(state.get_flag(RpgFarmEvents.FLAG_ENTITY, RpgFarmEvents.TODAY_KEY, {})).get("id"), "egg_hunt", "kept in the flags of the saved game")
	# the day after nothing lies there, and next year's hunt begins anew
	calendar.end_day()
	t.eq([events.refresh(map), events.count(), events.is_done()], [0, 0, false])
	_go_to(calendar, 0, 12, 2)
	t.eq([events.refresh(map), events.found().size()], [3, 0])
	_cleanup()

func test_a_village_without_the_markers_has_its_eggs_round_the_square(t) -> void:
	var game := _game()
	var calendar: RpgCalendar = game["calendar"]
	var events: RpgFarmEvents = game["events"]
	var old := _village(false)
	_go_to(calendar, 0, 12)
	t.eq(events.refresh(old), 3, "a village from before the card")
	var square := RpgSchedule.find_place(old, "square").position
	var seen := {}
	for thing in events.things():
		seen[thing.position] = true
		t.ok(thing.position.distance_to(square) <= 16.0 * 5.0 and thing.position != square, "near the square, not on it")
	t.eq(seen.size(), 3, "each at a place of its own")
	var elsewhere := Node2D.new()
	elsewhere.name = "Farm"
	_made.append(elsewhere)
	t.eq(events.refresh(elsewhere), 0, "not on another map")
	_cleanup()

func test_the_fishing_count_counts_the_fish_of_the_day(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var mode: RpgFarmMode = game["mode"]
	var calendar: RpgCalendar = game["calendar"]
	var events: RpgFarmEvents = game["events"]
	state.gold = 0
	_go_to(calendar, 1, 11)
	mode.fishing.caught.emit(&"fish_carp")
	t.eq(events.count(), 0, "a fish of another day does not count")
	_go_to(calendar, 1, 12)
	mode.fishing.caught.emit(&"fish_carp")
	mode.fishing.caught.emit(&"fish_carp")
	t.eq([events.count(), events.is_done(), state.gold], [2, false, 0])
	t.eq(events.use_table(), "Fish caught today: 2 of 3.")
	mode.fishing.caught.emit(&"fish_carp")
	t.eq([events.count(), events.is_done(), state.gold], [3, true, 200], "the third wins the prize")
	mode.fishing.caught.emit(&"fish_carp")
	t.eq([events.count(), state.gold], [4, 200], "once")
	_cleanup()

func test_the_contest_is_judged_on_what_the_season_shipped(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var events: RpgFarmEvents = game["events"]
	var map := _village()
	state.inventory.add(&"crop_corn", 5)
	state.inventory.add(&"crop_pumpkin", 2)
	# summer's corn is not autumn's
	_go_to(calendar, 1, 27)
	RpgShippingBin.put(&"crop_corn", 2)
	calendar.end_day()
	t.eq(RpgShippingBin.shipped(), {"crop_corn": 2})
	calendar.end_day()
	t.eq([calendar.season, calendar.day], [2, 1])
	t.eq(RpgShippingBin.shipped(), {}, "another season: nothing yet")
	RpgShippingBin.put(&"crop_corn", 3)
	calendar.end_day()
	t.eq(RpgShippingBin.shipped_best(), {"count": 3, "best": "crop_corn", "price": 30})
	_go_to(calendar, 2, 26)
	state.gold = 0
	t.eq(events.refresh(map), 1, "the judges' table")
	var table := events.thing_at("festival_table")
	t.ok(table != null and table.kind == RpgFestivalThing.TABLE)
	t.eq(RpgFarmEvents.score_of(events.festival()), 30)
	t.eq(events.use_table(), "The judges looked at what you shipped this season. It was not enough for a prize.")
	t.eq([state.gold, events.is_done()], [0, true])
	t.eq(events.use_table(), "That is done for this year.", "judged once")
	# next year a pumpkin is shipped in autumn
	_go_to(calendar, 2, 3, 2)
	RpgShippingBin.put(&"crop_pumpkin", 1)
	calendar.end_day()
	_go_to(calendar, 2, 26, 2)
	state.gold = 0
	table.interact()
	t.eq([state.gold, events.is_done()], [300, true], "`interact` with the table has it judged: the pumpkin wins")
	t.eq(events.use_table(), "That is done for this year.")
	_cleanup()

func test_a_contest_by_the_count_and_one_with_nothing_shipped(t) -> void:
	var by_count := [{"id": "summer_fair", "kind": "produce_contest", "name": "Summer fair", "season": "summer", "day": 12, "map": VILLAGE, "place": "square", "table": "festival_table", "judge": "count", "goal": 4, "prize": {"gold": 200, "item": "seed_corn", "qty": 5}}]
	var game := _game(true, by_count)
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var events: RpgFarmEvents = game["events"]
	_go_to(calendar, 1, 12)
	state.gold = 0
	t.eq(events.use_table(), "You shipped nothing this season: there is nothing to judge.")
	state.inventory.add(&"crop_corn", 4)
	_go_to(calendar, 1, 3, 2)
	RpgShippingBin.put(&"crop_corn", 4)
	calendar.end_day()
	_go_to(calendar, 1, 12, 2)
	state.gold = 0
	t.eq(events.use_table(), "You shipped 4 things this season. You win 200 G, Seed Corn x5!")
	t.eq([state.gold, state.inventory.count(&"seed_corn")], [200, 5], "money and an item")
	_cleanup()

func test_a_dish_brought_to_the_feast_is_shared_with_everybody(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var events: RpgFarmEvents = game["events"]
	var friends: RpgFriendship = game["friends"]
	_go_to(calendar, 3, 26)
	state.inventory.add(&"crop_corn", 2)
	state.inventory.add(&"stone", 1)
	t.ok(events.is_dish(&"crop_corn") and not events.is_dish(&"stone") and not events.is_dish(&""))
	t.eq(events.use_table(), "Bring a dish to the table: hold any food.", "with nothing in the hand")
	t.eq(events.use_table(&"stone"), "Bring a dish to the table: hold any food.", "a stone is no dish")
	t.eq(events.use_table(&"crop_pumpkin"), "Bring a dish to the table: hold any food.", "nor a dish the bag does not hold")
	t.ok(not events.is_done() and friends.points_of("anna") == 0)
	t.eq(events.use_table(&"crop_corn"), "Everybody shares your Crop Corn. The whole village likes you a little more.")
	t.eq(state.inventory.count(&"crop_corn"), 1, "one of it")
	t.eq([friends.points_of("anna"), friends.points_of("bert"), friends.points_of("clara")], [60, 60, 60])
	t.eq(events.use_table(&"crop_corn"), "That is done for this year.")
	t.eq([state.inventory.count(&"crop_corn"), friends.points_of("anna")], [1, 60], "once")
	_cleanup()

# ---------------------------------------------------------------- birthdays

func test_a_birthday_gift_counts_five_times_and_is_none_of_the_weeks_two(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var events: RpgFarmEvents = game["events"]
	var friends: RpgFriendship = game["friends"]
	state.inventory.add(&"crop_corn", 9)
	state.inventory.add(&"crop_pumpkin", 9)
	state.inventory.add(&"stone", 9)
	t.eq(RpgFriendship.BIRTHDAY_FACTOR, 5)
	t.eq([RpgFriendship.birthday_points(RpgFriendship.LOVES), RpgFriendship.birthday_points(RpgFriendship.LIKES), RpgFriendship.birthday_points(RpgFriendship.NEUTRAL), RpgFriendship.birthday_points(RpgFriendship.DISLIKES)], [400, 225, 100, -20], "a disliked gift is not made worse")
	t.eq(events.birthday_of("anna"), {"season": 0, "day": 9})
	t.eq(events.birthday_of("clara"), {}, "somebody without one")
	_go_to(calendar, 0, 8)
	t.ok(not events.is_birthday("anna"))
	t.eq(friends.gift("anna", &"crop_corn"), RpgFriendship.LOVES)
	t.eq([friends.points_of("anna"), friends.gifts_left("anna")], [80, 1], "the day before: a gift like any other")
	_go_to(calendar, 0, 9)
	t.ok(events.is_birthday("anna") and events.birthday_gift_open("anna") and not events.is_birthday("bert"))
	t.eq(events.birthdays_on(9, 0), ["anna"] as Array[String])
	t.eq(friends.gift("anna", &"crop_corn"), RpgFriendship.LOVES)
	t.eq([friends.points_of("anna"), friends.gifts_left("anna")], [80 + 400, 1], "five times, and the week still has its gift")
	t.ok(not events.birthday_gift_open("anna"), "one such gift a birthday")
	t.eq(friends.gift("anna", &"crop_pumpkin"), RpgFriendship.LIKES)
	t.eq([friends.points_of("anna"), friends.gifts_left("anna")], [480 + 45, 0], "the second is a gift like any other")
	t.eq(friends.gift("anna", &"crop_corn"), "", "and the week is full")
	# a week of two gifts, then the birthday: it is still given
	_go_to(calendar, 1, 15)
	friends.gifts["bert"] = 2
	_go_to(calendar, 1, 20)
	t.eq(friends.gifts_left("bert"), 0)
	t.eq(friends.gift("bert", &"crop_corn"), RpgFriendship.DISLIKES)
	t.eq([friends.points_of("bert"), events.birthday_gift_open("bert")], [0, false], "a disliked one takes what it takes (none are left to take), and was the day's gift")
	# the People page and the atom
	t.eq(RpgPeoplePage.detail_text(friends, "bert"), "Bert   0 of 10 hearts\nBirthday: summer 20\nDislikes: Crop Corn")
	t.eq(RpgPeoplePage.detail_text(friends, "clara"), "Clara   0 of 10 hearts\nNothing is known of their taste yet.")
	t.ok(RpgCondition.evaluate("birthday:bert") and not RpgCondition.evaluate("birthday:anna") and not RpgCondition.evaluate("birthday:nobody"))
	_cleanup()

func test_a_person_of_an_older_file_has_the_planned_birthday(t) -> void:
	var game := _game()
	var events: RpgFarmEvents = game["events"]
	events.planned_birthdays["clara"] = {"season": "winter", "day": 2}
	events.planned_birthdays["anna"] = {"season": "winter", "day": 3}
	t.eq(events.birthday_of("clara"), {"season": 3, "day": 2}, "the entry of people.json has none: the plan's")
	t.eq(events.birthday_of("anna"), {"season": 0, "day": 9}, "the entry of people.json counts")
	t.eq(events.birthdays_on(2, 3), ["clara"] as Array[String])
	_cleanup()

# ---------------------------------------------------------------- the calendar and the day before

func test_the_calendar_page_lists_the_season(t) -> void:
	var game := _game()
	var calendar: RpgCalendar = game["calendar"]
	var events: RpgFarmEvents = game["events"]
	_go_to(calendar, 0, 9)
	t.eq(events.season_rows(0, 1), [{"day": 9, "kind": "birthday", "text": "Anna's birthday"}, {"day": 12, "kind": "egg_hunt", "text": "Egg hunt"}] as Array[Dictionary])
	var page := RpgCalendarPage.new()
	page.events = events
	_made.append(page)
	page.build()
	page.build()
	t.eq(page.find_children("Back", "Button", true, false).size(), 1, "built once")
	page.show_today()
	t.eq(page.heading(), "Spring, year 1")
	t.eq(page.day_count(), 28)
	t.eq(page.listed(), "9  Anna's birthday\n12  Egg hunt")
	t.eq([page.mark_of(9), page.mark_of(12), page.mark_of(10), page.mark_of(1)], ["birthday+today", "festival", "", ""])
	t.eq(page.find_children("Weekday*", "Label", true, false).size(), 7)
	t.eq((page.find_children("Weekday0", "Label", true, false)[0] as Label).text, "Mo")
	_go_to(calendar, 0, 10)
	page.show_today()
	t.eq([page.mark_of(9), page.mark_of(10)], ["birthday", "today"], "today is marked")
	page.turn(1)
	t.eq([page.heading(), page.listed()], ["Summer, year 1", "12  Fishing day\n20  Bert's birthday"])
	t.eq(page.mark_of(10), "", "today is of another season")
	page.turn(3)
	t.eq(page.heading(), "Spring, year 2")
	page.turn(-9)
	t.eq(page.heading(), "Spring, year 1", "never before the first spring")
	events.add_event({"kind": "gathering", "name": "Midsummer", "season": "summer", "day": 12, "year": 1})
	page.show_season(1, 1)
	t.eq(page.listed(), "12  Fishing day\n12  Midsummer\n20  Bert's birthday")
	calendar.days_per_season = 7
	page.show_season(3, 1)
	t.eq([page.day_count(), page.listed()], [7, "5  Winter feast"])
	# a season with nothing
	var bare := RpgCalendarPage.new()
	_made.append(bare)
	events.events.clear()
	bare.events = events
	bare.show_season(2, 1)
	t.eq(bare.listed(), "Nothing is marked this season.")
	# in the pause menu: a Calendar button after People
	var menu := Control.new()
	var box := VBoxContainer.new()
	menu.add_child(box)
	for button_name: String in ["Resume", "Status", "Save"]:
		var button := Button.new()
		button.name = button_name
		box.add_child(button)
		button.owner = menu
		button.unique_name_in_owner = true
	_made.append(menu)
	RpgPeoplePage.add_to(menu)
	var added := RpgCalendarPage.add_to(menu)
	t.ok(added != null and added.text == "Calendar" and RpgCalendarPage.add_to(menu) == added, "added once")
	t.eq(added.get_index(), box.get_node("People").get_index() + 1, "after People")
	_cleanup()

func test_the_day_before_a_festival_is_announced(t) -> void:
	var game := _game()
	var mode: RpgFarmMode = game["mode"]
	var calendar: RpgCalendar = game["calendar"]
	var events: RpgFarmEvents = game["events"]
	_go_to(calendar, 0, 10)
	t.eq(events.tomorrow_text(), "")
	t.eq(mode.weather.forecast_text(), "Tomorrow's weather: Sunny.")
	t.ok(not RpgCondition.evaluate("festival_tomorrow") and not RpgCondition.evaluate("festival"))
	_go_to(calendar, 0, 11)
	t.eq(events.tomorrow_text(), "Tomorrow is the Egg hunt. The shop will be closed.")
	t.eq(mode.weather.forecast_text(), "Tomorrow's weather: Sunny.\nTomorrow is the Egg hunt. The shop will be closed.", "on the weather's sign")
	var sign := RpgWeatherSign.new()
	_made.append(sign)
	t.ok(sign.reading() == "" or sign.reading() == mode.weather.forecast_text())
	t.ok(RpgCondition.evaluate("festival_tomorrow") and not RpgCondition.evaluate("festival"), "and the people say so")
	t.eq(RpgUtil.to_str(events.festival_tomorrow()["id"]), "egg_hunt")
	_go_to(calendar, 0, 12)
	t.ok(RpgCondition.evaluate("festival") and not RpgCondition.evaluate("festival_tomorrow"))
	t.ok(RpgCondition.evaluate("event:egg_hunt") and not RpgCondition.evaluate("event:wedding"))
	t.eq(events.tomorrow_text(), "")
	# the last day of a year announces the first of the next
	events.add_event({"kind": "gathering", "name": "New year", "season": "spring", "day": 1})
	_go_to(calendar, 3, 28)
	t.eq(events.tomorrow_text(), "Tomorrow is the New year. The shop will be closed.")
	# the atoms are known to the editor's checks
	for atom: String in ["festival", "festival_tomorrow", "birthday:anna", "event:wedding"]:
		t.eq(RpgCondition.atom_problem(atom), "", atom)
	t.ok(RpgCondition.atom_problem("birthday:") != "" and RpgCondition.atom_problem("event:") != "")
	t.ok(RpgCondition.ATOMS.has("birthday:") and RpgCondition.ATOMS.has("festival") and RpgCondition.ATOMS.has("event:"), "the dock's completion knows them")
	_cleanup()

# ---------------------------------------------------------------- the save, and an added event

func test_the_state_round_trips_through_a_save(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var events: RpgFarmEvents = game["events"]
	var friends: RpgFriendship = game["friends"]
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER) as RpgSaveManager
	save.dir = "user://test_farm_events_%d" % Time.get_ticks_usec()
	var map := _village()
	state.inventory.add(&"crop_corn", 3)
	state.inventory.add(&"crop_pumpkin", 3)
	_go_to(calendar, 0, 5)
	RpgShippingBin.put(&"crop_pumpkin", 2)
	calendar.end_day()
	var wedding := events.add_event({"kind": "wedding", "name": "Wedding", "season": "spring", "day": 15, "year": 1, "person": "anna"})
	_go_to(calendar, 0, 12)
	events.refresh(map)
	events.find_egg("festival_egg_2")
	var kept := {"found": events.found(), "count": events.count(), "done": events.is_done(), "added": events.added(), "shipped": RpgShippingBin.shipped(), "gold": state.gold}
	t.ok(save.save(1))
	var written: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(save.dir.path_join("slot_1.json")))
	t.ok(not written.has("events") and not written.has("farm_events"), "the save has no new key")
	t.ok(RpgUtil.to_dict(written.get("flags", {})).has(RpgFarmEvents.FLAG_ENTITY), "the state is in the flags")
	# everything changes
	events.find_egg("festival_egg_1")
	events.find_egg("festival_egg_3")
	events.remove_event(wedding)
	_go_to(calendar, 0, 9)
	friends.gift("anna", &"crop_corn")
	t.ok(not events.birthday_gift_open("anna"))
	calendar.end_day()
	t.ok(events.is_done() == false and events.count() == 0 and events.added().is_empty())
	t.ok(save.load(1))
	t.eq([calendar.season, calendar.day], [0, 12])
	t.eq({"found": events.found(), "count": events.count(), "done": events.is_done(), "added": events.added(), "shipped": RpgShippingBin.shipped(), "gold": state.gold}, kept)
	t.eq(events.refresh(map), 2, "the egg that was found before the save is not there, the others are")
	t.ok(events.thing_at("festival_egg_2") == null and events.thing_at("festival_egg_1") != null)
	# a new game has none of it
	state.new_game()
	t.ok(events.added().is_empty() and events.count() == 0 and RpgShippingBin.shipped().is_empty())
	for file: String in DirAccess.get_files_at(save.dir):
		DirAccess.remove_absolute(save.dir.path_join(file))
	DirAccess.remove_absolute(save.dir)
	_cleanup()

func test_an_event_added_at_run_time_is_a_day_of_the_calendar(t) -> void:
	var game := _game()
	var calendar: RpgCalendar = game["calendar"]
	var events: RpgFarmEvents = game["events"]
	var friends: RpgFriendship = game["friends"]
	var shop := RpgFarmShop.new()
	t.eq(events.add_event({"season": "spring", "day": 4}), "", "an event has a kind")
	t.eq(events.add_event({"kind": "wedding", "season": "monsoon", "day": 4}), "", "and a date")
	t.eq(events.add_event({"kind": "birthday", "season": "spring", "day": 4}), "", "a birthday is a person's, not an event")
	var seen := [0]
	events.changed.connect(func() -> void: seen[0] += 1)
	var id := events.add_event({"kind": RpgFarmEvents.WEDDING, "name": "Wedding", "season": 1, "day": 4, "year": 2, "person": "anna"})
	t.eq(id, "wedding_2_summer_4")
	t.ok(seen[0] >= 1, "whoever shows the calendar hears of it")
	var added := events.added()
	t.eq(added.size(), 1)
	t.eq([added[0]["season"], added[0]["day"], added[0]["year"], added[0]["person"]], ["summer", 4, 2, "anna"], "what it was given is kept")
	t.eq([added[0]["map"], added[0]["place"]], [VILLAGE, "square"], "it gathers where the festivals do")
	t.eq(RpgUtil.to_dict(RpgUtil.state().flags.get(RpgFarmEvents.FLAG_ENTITY, {})).has(RpgFarmEvents.ADDED_KEY), true, "kept in the flags")
	_go_to(calendar, 1, 4, 1)
	t.ok(not events.is_festival(), "not in another year")
	_go_to(calendar, 1, 3, 2)
	t.eq(events.tomorrow_text(), "Tomorrow is the Wedding. The shop will be closed.")
	_go_to(calendar, 1, 4, 2)
	t.ok(events.is_festival() and events.has_kind("wedding") and RpgCondition.evaluate("event:wedding"))
	t.eq(RpgUtil.to_str(events.festival()["person"]), "anna")
	t.eq(shop.closed_reason(), "The shop is closed today: it is the Wedding.")
	t.eq(RpgUtil.to_str(events.schedule_override("bert", 12)["place"]), "square_2", "the people gather as on a festival")
	t.eq(events.schedule_override("bert", 21), {})
	t.eq(events.season_rows(1, 2)[0], {"day": 4, "kind": "wedding", "text": "Wedding"})
	t.eq(events.use_table(), "Today is the Wedding on the village square.", "nothing to do but to be there")
	# the same id again replaces it; taking it away
	t.eq(events.add_event({"id": id, "kind": "wedding", "name": "Wedding", "season": "summer", "day": 6, "year": 2}), id)
	t.eq(events.added().size(), 1)
	t.ok(not events.is_festival())
	t.ok(events.remove_event(id) and not events.remove_event(id))
	t.ok(events.added().is_empty())
	# an event of every year
	events.add_event({"id": "market", "kind": "gathering", "name": "Market", "season": "winter", "day": 2})
	_go_to(calendar, 3, 2, 1)
	t.ok(events.is_festival())
	_go_to(calendar, 3, 2, 5)
	t.ok(events.is_festival())
	t.ok(friends != null)
	_cleanup()

func test_the_wall_calendar_opens_the_page_over_the_paused_game(t) -> void:
	var game := _game()
	var mode: RpgFarmMode = game["mode"]
	var events: RpgFarmEvents = game["events"]
	var tree := Fixtures.tree()
	tree.root.add_child(mode)
	var wall := RpgWallCalendar.new()
	_made.append(wall)
	t.ok(not events.is_calendar_open())
	wall.interact()
	t.ok(events.is_calendar_open() and tree.paused, "the page is shown and the game stands still")
	var page := events.open_calendar()
	t.ok(page != null and page.get_parent() is CanvasLayer and page.heading() == "Spring, year 1")
	t.eq(events.find_children(RpgCalendarPage.PAGE_NAME, "Control", true, false).size(), 1, "one page, however often it is asked for")
	page.close()
	await tree.process_frame
	await tree.process_frame
	t.ok(not events.is_calendar_open() and not tree.paused, "closed, and the game goes on")
	tree.root.remove_child(mode)
	t.ok(RpgFarmEvents.current() == null and not RpgSchedule.override.is_valid() and not RpgFarmShop.day_off.is_valid(), "a mode that leaves the tree lets go of what it set")
	_cleanup()

# ---------------------------------------------------------------- the builder

func test_the_markers_of_the_festivals_are_free_cells_away_from_the_square(t) -> void:
	var building := {"size": [5, 4], "door": [2, 4]}
	var layout := MapBuild.plan({}, 12345, building, "farm")
	var none: Array[Vector2i] = []
	var names: Array[String] = ["festival_table", "festival_egg_1", "festival_egg_2", "festival_egg_3", "festival_egg_4", "festival_egg_5"]
	var plain := People.village_spots(layout, Vector2i(5, 4), none)
	var spots := People.village_spots(layout, Vector2i(5, 4), none, names)
	t.eq(spots.size(), plain.size() + names.size())
	for place: String in plain.keys():
		t.eq(spots[place], plain[place], "%s is where it is in a village without festivals" % place)
	var taken := People.occupied(layout, Vector2i(5, 4), none)
	var square: Array[Vector2i] = []
	var others := {}
	for place: String in plain.keys():
		others[plain[place]] = true
		if place.begins_with("square"):
			square.append(plain[place])
	var seen := {}
	for marker in names:
		var cell: Vector2i = spots[marker]
		t.ok(not taken.has(cell) and not others.has(cell) and not seen.has(cell), "%s has a free cell of its own" % marker)
		seen[cell] = true
		if marker == "festival_table":
			continue
		for spot in square:
			t.ok(maxi(absi(cell.x - spot.x), absi(cell.y - spot.y)) > 2, "%s lies among the people on the square" % marker)
	var table: Vector2i = spots["festival_table"]
	var first: Vector2i = plain["square"]
	t.ok(absi(table.x - first.x) + absi(table.y - first.y) <= 4, "the table stands by the square")
	t.eq(spots, People.village_spots(layout, Vector2i(5, 4), none, names), "the same every time")

func test_the_calendar_hangs_over_the_cell_farthest_from_the_bed(t) -> void:
	t.eq(EventsRecipe.calendar_cell(Vector2i(8, 6), Vector2i(1, 1)), Vector2i(6, 1))
	t.eq(EventsRecipe.calendar_cell(Vector2i(8, 6), Vector2i(6, 1)), Vector2i(1, 1))
	t.eq(EventsRecipe.calendar_cell(Vector2i(3, 3), Vector2i(1, 1)), Vector2i(1, 1), "a room of one cell")
	var wall := EventsRecipe.wall_calendar(16)
	t.ok(wall is RpgWallCalendar and wall.name == "WallCalendar")
	t.ok(wall.get_collision_layer_value(5) and wall.collision_mask == 0 and not wall.monitoring, "found by `interact`, in nobody's way")
	var shape := wall.get_node("Shape") as CollisionShape2D
	t.eq((shape.shape as RectangleShape2D).size, Vector2(12.8, 19.2))
	t.ok(shape.position.y < 0.0 and shape.position.y - 9.6 < -8.0 and shape.position.y + 9.6 > 4.0, "over the wall above the cell and into the cell")
	for part: String in ["Picture/Sheet", "Picture/Head", "Picture/Row1", "Picture/Row3"]:
		t.ok(wall.get_node_or_null(part) is Polygon2D, part)
	wall.free()
	var board := EventsRecipe.wall_calendar(16, Vector2i(64, 32))
	t.ok((board.get_node("Shape") as CollisionShape2D).shape is ConvexPolygonShape2D, "on diamonds: its cell")
	t.ok(board.get_node_or_null("Post") is Polygon2D, "a board on a post")
	board.free()
	# without a plan (the template project has none) nothing is planned for the village
	t.eq(EventsRecipe.markers(), [] as Array[String])
	t.eq(EventsRecipe.entries(), [])
	t.ok(not People.festive())
