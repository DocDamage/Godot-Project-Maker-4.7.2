extends RefCounted
## T17.08: money. The shipping bin and its night, the morning's summary, the shop's seasonal
## stock and its hours, sleeping, and staying up to 2:00.

const Fixtures := preload("../lib/fixtures.gd")

const SAVE_DIR := "user://test_farm_money"
const CROPS := [
	{"id": "corn", "name": "Corn", "seed": "seed_corn", "produce": "crop_corn", "seasons": ["spring", "summer"], "days": 3, "stages": 4, "regrow": 0, "seed_price": 15, "price": 30, "energy": 14},
	{"id": "pumpkin", "name": "Pumpkin", "seed": "seed_pumpkin", "produce": "crop_pumpkin", "seasons": ["autumn"], "days": 2, "stages": 3, "regrow": 0, "seed_price": 10, "price": 20, "energy": 12},
]
## Item id -> its price; the tools are key items without one.
const PRICES := {&"crop_corn": 30, &"seed_corn": 15, &"seed_pumpkin": 10, &"potion": 10, &"feed": 4, &"hoe": 0, &"sickle": 0}
const TOOLS: Array[StringName] = [&"hoe", &"sickle"]

var _made: Array[Node] = []

func _crops() -> RpgCropData:
	var data := RpgCropData.new()
	data.add_list(CROPS)
	return data

## A farm's game: the items, the mode with its calendar and the end of its day, and a save
## manager that writes into a folder of its own. {state, mode, calendar, day_end, save}
func _game(pass_out_loss: bool = true) -> Dictionary:
	var registry := {}
	for id: StringName in PRICES.keys():
		var def := Fixtures.item(id)
		def.value = PRICES[id]
		if TOOLS.has(id):
			def.category = RpgItemDefinition.Category.KEY
			def.max_stack = 1
		registry[id] = def
	var state := Fixtures.install_state(registry) as RpgGameState
	state.inventory.registry = state.items
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER) as RpgSaveManager
	save.dir = SAVE_DIR
	for slot in range(RpgSaveManager.AUTOSAVE_SLOT, RpgSaveManager.SLOTS + 1):
		save.delete(slot)
	var mode := RpgFarmMode.new()
	mode.crops = _crops()
	mode.pass_out_loss = pass_out_loss
	mode._ready()
	_made.append(mode)
	return {"state": state, "mode": mode, "calendar": RpgCalendar.current(), "day_end": mode.day_end, "save": save}

## A bed at (100, 50) and somebody to wake at it, standing far away.
func _bed_and_farmer(game: Dictionary) -> Dictionary:
	var bed := RpgBed.new()
	bed.position = Vector2(100, 50)
	bed.wake_offset = Vector2(0, 8)
	var farmer := Node2D.new()
	farmer.position = Vector2(400, 300)
	_made.append(bed)
	_made.append(farmer)
	var day_end: RpgDayEnd = game["day_end"]
	day_end.farmer = farmer
	return {"bed": bed, "farmer": farmer}

func _cleanup() -> void:
	var tree := Fixtures.tree()
	tree.paused = false
	for node in _made:
		if is_instance_valid(node):
			node.free()
	_made.clear()
	var save := tree.root.get_node_or_null("SaveManager") as RpgSaveManager
	if save != null:
		for slot in range(RpgSaveManager.AUTOSAVE_SLOT, RpgSaveManager.SLOTS + 1):
			save.delete(slot)
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- the shipping bin

func test_the_held_stack_goes_into_the_bin_and_comes_back_out(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	state.inventory.add(&"hoe", 1)
	state.inventory.add(&"crop_corn", 5)
	var bin := RpgShippingBin.new()
	_made.append(bin)
	t.ok(RpgShippingBin.is_empty())
	t.eq(bin.use_with(&"crop_corn", 5), 5, "the whole held stack")
	t.eq([state.inventory.count(&"crop_corn"), RpgShippingBin.count(&"crop_corn")], [0, 5])
	t.eq(RpgUtil.to_array(state.get_flag(RpgShippingBin.FLAG_ENTITY, RpgShippingBin.FLAG_KEY, [])).size(), 1, "kept in the flags of the saved game")
	t.eq(bin.use_with(&"hoe", 1), -5, "with a tool in the hand the last stack comes back out")
	t.eq([state.inventory.count(&"crop_corn"), RpgShippingBin.count(&"crop_corn")], [5, 0])
	t.eq(bin.use_with(&"", 0), 0, "an empty bin gives nothing")
	t.eq(RpgShippingBin.put(&"hoe", 1), 0, "a tool is not sold")
	t.eq(RpgShippingBin.put(&"crop_corn", 9), 0, "nor more than the farmer has")
	t.eq(RpgShippingBin.put(&"crop_corn", 2), 2)
	t.eq(RpgShippingBin.put(&"crop_corn", 3), 3)
	t.eq(RpgShippingBin.contents(), [{"item_id": "crop_corn", "qty": 5}], "one row an item")
	_cleanup()

func test_what_is_in_the_bin_is_paid_for_overnight_and_listed_in_the_summary(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var day_end: RpgDayEnd = game["day_end"]
	state.gold = 10
	state.inventory.add(&"crop_corn", 5)
	state.inventory.add(&"seed_corn", 3)
	RpgShippingBin.put(&"crop_corn", 5)
	RpgShippingBin.put(&"seed_corn", 3)
	t.eq(state.gold, 10, "nothing is paid before the night")
	var woke: Array[String] = []
	day_end.woke.connect(func(how: String) -> void: woke.append(how))
	calendar.end_day()
	t.eq(state.gold, 10 + 5 * 30 + 3 * 15, "each at its price")
	t.ok(RpgShippingBin.is_empty(), "the bin is empty in the morning")
	t.eq(RpgUtil.to_int(day_end.last_sale.get("total", 0)), 195)
	var summary := day_end.summary()
	t.ok(summary != null, "the morning begins with the summary")
	t.ok(Fixtures.tree().paused, "over the paused game")
	t.eq(woke, [] as Array[String], "the morning is not done while it is shown")
	if summary != null:
		t.eq(Array(RpgDaySummary.lines(summary.sale)), ["Crop Corn x5 — 150 G", "Seed Corn x3 — 45 G"], "what was sold and what each earned")
		t.eq(RpgDaySummary.total_text(summary.sale), "Total: 195 G")
		t.eq(summary.get_node("Center/Panel/Box/Rows").get_child_count(), 2)
		t.eq((summary.get_node("Center/Panel/Box/Total") as Label).text, "Total: 195 G")
		summary.close()
	t.ok(not Fixtures.tree().paused and day_end.summary() == null, "closed, and the game goes on")
	t.eq(woke, [RpgDayEnd.ENDED] as Array[String])
	# a night in which nothing was sold shows nothing
	calendar.end_day()
	t.eq(state.gold, 205)
	t.ok(day_end.summary() == null and not Fixtures.tree().paused, "nothing was sold: nothing is shown")
	t.ok(not RpgDaySummary.worth_showing(day_end.last_sale))
	t.eq(woke.size(), 2)
	_cleanup()

func test_the_bin_is_sold_after_the_crops_of_the_night(t) -> void:
	var game := _game()
	var calendar: RpgCalendar = game["calendar"]
	var order: Array[String] = []
	calendar.on_night(RpgCalendar.NIGHT_ANIMALS, func(_day: int) -> void: order.append("bin empty" if RpgShippingBin.is_empty() else "bin full"))
	calendar.on_night(RpgCalendar.NIGHT_WEATHER, func(_day: int) -> void: order.append("bin empty" if RpgShippingBin.is_empty() else "bin full"))
	var state: RpgGameState = game["state"]
	state.inventory.add(&"potion", 1)
	RpgShippingBin.put(&"potion", 1)
	calendar.end_day()
	t.eq(order, ["bin full", "bin empty"] as Array[String], "NIGHT_SHOP: after the animals, before the weather")
	var day_end: RpgDayEnd = game["day_end"]
	day_end.summary().close()
	_cleanup()

# ---------------------------------------------------------------- the shop

func _shop() -> RpgFarmShop:
	var shop := RpgFarmShop.new()
	shop.id = &"village_shop"
	shop.crops = _crops()
	shop.sell_ratio = 1.0
	var stock: Array[Dictionary] = [{"item_id": "potion", "price": -1}, {"item_id": "sickle", "price": 50}]
	shop.stock = stock
	return shop

func test_the_stock_of_the_shop_changes_with_the_season(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var calendar: RpgCalendar = game["calendar"]
	var shop := _shop()
	t.eq(shop.offered(state.items), [&"potion", &"sickle", &"seed_corn"] as Array[StringName], "spring: the corn")
	t.eq(shop.buy_price(&"seed_corn", state.items), 15, "at the seed's price")
	state.gold = 100
	t.eq(shop.buy(state, &"seed_pumpkin", 1), RpgShopDefinition.NOT_FOR_SALE, "no pumpkin seeds in spring")
	t.eq(shop.buy(state, &"seed_corn", 2), RpgShopDefinition.OK)
	t.eq([state.gold, state.inventory.count(&"seed_corn")], [70, 2])
	calendar.season = 2
	t.eq(shop.offered(state.items), [&"potion", &"sickle", &"seed_pumpkin"] as Array[StringName], "autumn: the pumpkin")
	t.eq(shop.buy(state, &"seed_corn", 1), RpgShopDefinition.NOT_FOR_SALE)
	calendar.season = 3
	t.eq(shop.offered(state.items), [&"potion", &"sickle"] as Array[StringName], "winter: no seeds")
	# a tool that was bought is not offered again; selling at the counter pays at once
	t.eq(shop.buy(state, &"sickle", 1), RpgShopDefinition.OK)
	t.eq(state.gold, 20)
	t.eq(shop.offered(state.items), [&"potion"] as Array[StringName])
	state.inventory.add(&"crop_corn", 2)
	t.eq(shop.sell(state, &"crop_corn", 2), RpgShopDefinition.OK)
	t.eq(state.gold, 80, "the price the bin pays, at once")
	t.eq(shop.sell(state, &"sickle", 1), RpgShopDefinition.WORTHLESS, "a tool is never bought back")
	# more stock comes from a source (the animals' feed), by the season
	var feed := func(season_name: String) -> Array: return [{"item_id": "feed", "price": 6}] if season_name == "winter" else []
	RpgFarmShop.add_stock_source(feed)
	t.eq(shop.offered(state.items), [&"potion", &"feed"] as Array[StringName])
	t.eq(shop.buy_price(&"feed", state.items), 6)
	calendar.season = 0
	t.ok(not shop.offered(state.items).has(&"feed"))
	RpgFarmShop.remove_stock_source(feed)
	t.ok(RpgFarmShop.stock_sources.is_empty())
	shop.seasonal = false
	t.eq(shop.offered(state.items), [&"potion"] as Array[StringName], "a shop that sells its stock only")
	_cleanup()

func test_the_shop_is_closed_outside_its_hours_and_on_its_closed_day(t) -> void:
	var game := _game()
	var calendar: RpgCalendar = game["calendar"]
	var shop := _shop()
	t.eq([shop.opens, shop.closes, shop.closed_weekday], [9, 17, 6])
	t.ok(not RpgFarmShop.open_at(539, 0, 9, 17, 6), "8:59")
	t.ok(RpgFarmShop.open_at(540, 0, 9, 17, 6), "9:00")
	t.ok(RpgFarmShop.open_at(1019, 0, 9, 17, 6), "16:59")
	t.ok(not RpgFarmShop.open_at(1020, 0, 9, 17, 6), "17:00")
	t.ok(not RpgFarmShop.open_at(720, 6, 9, 17, 6), "noon of the closed day")
	t.ok(RpgFarmShop.open_at(720, 6, 9, 17, -1), "a shop without a closed day")
	t.ok(not shop.is_open(), "a new game begins at 6:00")
	t.ok(shop.closed_reason().contains("9:00") and shop.closed_reason().contains("17:00") and shop.closed_reason().contains("Sunday"), shop.closed_reason())
	calendar.pass_minutes(180)
	t.eq(calendar.clock(), [9, 0] as Array[int])
	t.ok(shop.is_open() and shop.closed_reason() == "", "open at 9:00")
	calendar.pass_minutes(480)
	t.ok(not shop.is_open(), "closed at 17:00")
	calendar.minute = 720
	calendar.day = 7
	t.eq(calendar.weekday(), 6)
	t.ok(not shop.is_open(), "closed all day on the seventh day of the week")
	calendar.day = 8
	t.ok(shop.is_open())
	shop.closed_weekday = -1
	calendar.minute = 300
	t.eq(shop.closed_reason(), "The shop is closed. It is open from 9:00 to 17:00.")
	# every other shop has no hours
	t.eq(RpgShopDefinition.new().closed_reason(), "")
	_cleanup()

# ---------------------------------------------------------------- sleeping

func test_sleeping_ends_the_day_once_fills_the_energy_and_saves(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var mode: RpgFarmMode = game["mode"]
	var calendar: RpgCalendar = game["calendar"]
	var day_end: RpgDayEnd = game["day_end"]
	var save: RpgSaveManager = game["save"]
	var home := _bed_and_farmer(game)
	var bed: RpgBed = home["bed"]
	var farmer: Node2D = home["farmer"]
	var ended: Array[int] = []
	calendar.day_ended.connect(func(day: int) -> void: ended.append(day))
	state.gold = 205
	mode.energy.value = 10
	calendar.minute = 1000
	t.ok(not save.has_save(RpgSaveManager.AUTOSAVE_SLOT))
	t.eq(day_end.chosen_slot(), RpgSaveManager.NO_SLOT, "a new game has no slot of its own")
	t.ok(day_end.sleep(bed))
	t.eq(ended, [1] as Array[int], "the day ended once")
	t.eq([calendar.day, calendar.minute], [2, RpgCalendar.DAY_START])
	t.eq(mode.energy.value, mode.energy.max_energy, "rested")
	t.eq(state.gold, 205, "sleeping costs nothing")
	t.eq(day_end.last_night, RpgDayEnd.SLEPT)
	t.ok(day_end.saved and save.has_save(RpgSaveManager.AUTOSAVE_SLOT), "saved into the autosave slot")
	t.ok(not save.has_save(1) and not save.has_save(2))
	t.eq(RpgUtil.to_int(save.header(RpgSaveManager.AUTOSAVE_SLOT).get("gold", 0)), 205)
	t.eq(farmer.position, Vector2(100, 58), "the farmer wakes at the bed")
	t.eq(RpgBed.home(state).get("position"), Vector2(100, 58))
	# the slot the player saved into by hand is the slot a night is saved into as well
	t.ok(save.save(2))
	t.eq(day_end.chosen_slot(), 2)
	save.delete(2)
	mode.energy.value = 40
	t.ok(day_end.sleep(bed))
	t.ok(save.has_save(2), "and into the slot the player chose")
	t.eq([calendar.day, mode.energy.value], [3, mode.energy.max_energy])
	# a day that something else ends: rested, nothing saved, nobody moved
	save.delete(RpgSaveManager.AUTOSAVE_SLOT)
	farmer.position = Vector2(7, 7)
	mode.energy.value = 3
	calendar.end_day()
	t.eq(day_end.last_night, RpgDayEnd.ENDED)
	t.eq(mode.energy.value, mode.energy.max_energy)
	t.ok(not day_end.saved and not save.has_save(RpgSaveManager.AUTOSAVE_SLOT))
	t.eq(farmer.position, Vector2(7, 7))
	_cleanup()

func test_passing_out_costs_half_the_energy_and_a_tenth_of_the_money(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var mode: RpgFarmMode = game["mode"]
	var calendar: RpgCalendar = game["calendar"]
	var day_end: RpgDayEnd = game["day_end"]
	var save: RpgSaveManager = game["save"]
	var home := _bed_and_farmer(game)
	var bed: RpgBed = home["bed"]
	var farmer: Node2D = home["farmer"]
	bed.remember()
	var ended: Array[int] = []
	calendar.day_ended.connect(func(day: int) -> void: ended.append(day))
	state.gold = 205
	mode.energy.value = 80
	calendar.pass_minutes(RpgCalendar.DAY_MINUTES - 1)
	t.eq([ended.size(), calendar.clock()], [0, [1, 59] as Array[int]], "1:59: still up")
	calendar.pass_minutes(1)
	t.eq(ended, [1] as Array[int], "2:00: the clock ends the day")
	t.eq(day_end.last_night, RpgDayEnd.PASSED_OUT)
	t.eq(mode.energy.value, 50, "half the energy")
	t.eq([state.gold, day_end.money_lost], [185, 20], "a tenth of the money, rounded down")
	t.eq(farmer.position, Vector2(100, 58), "the farmer wakes at the bed")
	t.ok(save.has_save(RpgSaveManager.AUTOSAVE_SLOT), "the morning is saved")
	_cleanup()

func test_the_option_turns_the_loss_of_money_off(t) -> void:
	var game := _game(false)
	var state: RpgGameState = game["state"]
	var mode: RpgFarmMode = game["mode"]
	var calendar: RpgCalendar = game["calendar"]
	var day_end: RpgDayEnd = game["day_end"]
	t.ok(not day_end.pass_out_loss, "the mode hands its option on")
	state.gold = 205
	mode.energy.value = 100
	calendar.pass_minutes(RpgCalendar.DAY_MINUTES)
	t.eq(day_end.last_night, RpgDayEnd.PASSED_OUT)
	t.eq([state.gold, day_end.money_lost], [205, 0], "no money is gone")
	t.eq(mode.energy.value, 50, "the energy still is")
	_cleanup()

func test_a_bed_is_remembered_and_a_new_game_has_none(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	t.eq(RpgBed.home(state), {}, "no bed was seen yet")
	var bed := RpgBed.new()
	bed.position = Vector2(64, 32)
	bed.wake_offset = Vector2(0, 8)
	bed.wake_facing = "down"
	_made.append(bed)
	bed._ready()
	t.eq(RpgBed.home(state), {"map": "", "position": Vector2(64, 40), "facing": "down"}, "the first bed a game sees")
	var other := RpgBed.new()
	other.position = Vector2(200, 200)
	_made.append(other)
	other._ready()
	t.eq(RpgBed.home(state).get("position"), Vector2(64, 40), "a second bed does not take its place")
	other.remember()
	t.eq(RpgBed.home(state).get("position"), Vector2(200, 208), "until it is slept in")
	_cleanup()
