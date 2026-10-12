extends RefCounted
## The farm's smoke steps (T17.04, T17.05, T17.08), appended after the shared sequence (which
## ends in the starter map): the map has its field and the game its farmer, calendar and tools
## -> a cell is tilled, planted and watered with the real input actions (`hotbar_<n>` chooses,
## `use` works) -> a night passes and the crop is a day further -> the nights to ripeness -> the
## crop is picked with `interact` -> it is put into the shipping bin, taken back out and put in
## again (`interact`) -> the farmer sleeps in the bed (`interact`): the day ends once, the
## energy is full, the game is saved -> the morning's summary names the crop and what it
## earned, and `confirm` closes it -> the shop is closed before 9:00 and on its closed day, and
## sells the seeds of the season in its hours.
##
## The nights of the growing are the calendar's `end_day()`, run in full (a day that nobody
## slept through); the night after the harvest is slept in the bed. The farm's whole day, from
## waking to the people, is T17.18.

## What a failed step of this sequence is reported as (docs/spec/03_ERROR_CODES.md).
const CODE := "SMOKE-013"

var _box := {}  # values remembered between steps

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	return [
		_step("farm_is_there", _farm_is_there, 20.0),
		_step("till_a_cell", _till_a_cell, 20.0),
		_step("plant_a_seed", _plant_a_seed, 20.0),
		_step("water_it", _water_it, 20.0),
		_step("a_night_grows_it", _a_night_grows_it, 20.0),
		_step("crop_ripens", _crop_ripens, 30.0),
		_step("harvest", _harvest, 30.0),
		_step("ship_the_crop", _ship_the_crop, 30.0),
		_step("sleep_in_the_bed", _sleep_in_the_bed, 40.0),
		_step("morning_summary", _morning_summary, 30.0),
		_step("buy_seeds_at_the_shop", _buy_seeds_at_the_shop, 40.0),
	]

func _step(step_name: String, fn: Callable, timeout_s: float) -> Dictionary:
	return {"name": step_name, "fn": fn, "timeout_s": timeout_s, "code": CODE}

# ---------------------------------------------------------------- helpers

func _farmer() -> RpgFarmer:
	var players := _tree().get_nodes_in_group("player")
	return players[0] as RpgFarmer if players.size() == 1 else null

func _state() -> RpgGameState:
	return RpgUtil.state()

func _frames(count: int) -> void:
	for i in count:
		await _tree().physics_frame

func _wait_for(check: Callable, frames: int) -> bool:
	for i in frames:
		if check.call():
			return true
		await _tree().physics_frame
	return check.call()

## Holds an action for a few frames (a "just pressed" is seen at least once).
func _tap(action: String) -> void:
	Input.action_press(action)
	await _frames(3)
	Input.action_release(action)
	await _frames(2)

## Chooses the slot of `item_id` with its number key. "" when it is held afterwards.
func _hold(item_id: StringName) -> String:
	var bar := RpgFarmMode.current().hotbar
	for i in RpgHotbar.SLOTS:
		if bar.item_at(i) == item_id:
			await _tap("hotbar_%d" % (i + 1))
			return "" if bar.held_item() == item_id else "hotbar_%d did not hold %s (held: %s)" % [i + 1, item_id, bar.held_item()]
	return "%s is not among the ten slots of the hotbar" % item_id

## Puts the farmer in the cell above the cell that is worked, looking down at it, and waits
## until it can act.
func _stand_at_cell() -> String:
	var farmer := _farmer()
	var field := RpgField.current()
	if farmer == null or field == null:
		return "the farmer or the field is gone"
	var cell: Vector2i = _box["cell"]
	farmer.global_position = field.cell_center(cell + Vector2i.UP)
	farmer.set_facing("down")
	await _frames(3)
	if not await _wait_for(func() -> bool: return not farmer.is_busy(), 120):
		return "the farmer never finished using its tool"
	if farmer.tile_ahead() != cell:
		return "the tile ahead is %s, expected %s" % [farmer.tile_ahead(), cell]
	return ""

func _crop() -> Dictionary:
	return RpgFarmMode.current().crops.crop(str(_box["crop"]))

# ---------------------------------------------------------------- steps

func _farm_is_there() -> String:
	var scene := _tree().current_scene
	if scene == null or scene.name != "StarterMap":
		return "not in the starter map"
	var mode := RpgFarmMode.current()
	if mode == null:
		return "SceneRouter.combat is not the farm's mode"
	if RpgCalendar.current() == null:
		return "the game has no calendar"
	if _farmer() == null:
		return "the player is not an RpgFarmer"
	var field := RpgField.current()
	if field == null:
		return "the starter map has no Field"
	var soil := scene.get_node_or_null("Soil") as TileMapLayer
	if soil == null:
		return "the starter map has no Soil layer"
	var plot: Array[Vector2i] = []
	for cell in soil.get_used_cells():
		if field.state_of(cell) == RpgField.GROUND:
			plot.append(cell)
	if plot.size() < 12:
		return "the plot has %d cells that can be tilled, at least 12 are needed" % plot.size()
	plot.sort()
	_box["cell"] = plot[0]
	if field.state_of(plot[0] + Vector2i.UP) != "":
		return "the cell above the plot is part of it"
	for item: StringName in [&"hoe", &"watering_can", &"sickle", &"farm_axe"]:
		if mode.tool_for(item) == null or not _state().items.has(item):
			return "the game has no %s" % item
	# a new game starts with a hoe and a can (T17.08); the sickle and the axe are bought
	for item: StringName in [&"hoe", &"watering_can"]:
		if not _state().inventory.has(item):
			return "a new game has no %s" % item
	if mode.crops.order.is_empty():
		return "game/data/crops.json has no crop"
	var first := mode.crops.order[0]
	_box["crop"] = first
	var seed := StringName(str(mode.crops.crop(first).get("seed", "")))
	if not mode.crops.grows_in(first, RpgField.season_now()):
		return "the first crop (%s) does not grow in %s" % [first, RpgField.season_now()]
	if not _state().inventory.has(seed):
		return "a new game has no seeds of the first crop (%s)" % seed
	_box["seed"] = seed
	if not ResourceLoader.exists(str(mode.crops.crop(first).get("scene", ""))):
		return "the scene of %s is missing" % first
	return ""

func _till_a_cell() -> String:
	var failure: String = await _stand_at_cell()
	if failure != "":
		return failure
	var field := RpgField.current()
	var mode := RpgFarmMode.current()
	var cell: Vector2i = _box["cell"]
	mode.energy.fill()
	failure = await _hold(&"hoe")
	if failure != "":
		return failure
	var before := mode.energy.value
	await _tap("use")
	if not await _wait_for(func() -> bool: return field.state_of(cell) == RpgField.SOIL, 60):
		return "`use` with the hoe did not till %s (it is %s)" % [cell, field.state_of(cell)]
	var cost := mode.tool_for(&"hoe").energy_cost
	if mode.energy.value != before - cost:
		return "the hoe cost %d energy, expected %d" % [before - mode.energy.value, cost]
	var soil := _tree().current_scene.get_node("Soil") as TileMapLayer
	if soil.get_cell_atlas_coords(cell) != field.tilled_tile:
		return "the Soil layer does not show tilled soil at %s" % cell
	if field.cells.size() != 1:
		return "%d cells were worked, expected 1" % field.cells.size()
	return ""

func _plant_a_seed() -> String:
	var failure: String = await _stand_at_cell()
	if failure != "":
		return failure
	var field := RpgField.current()
	var cell: Vector2i = _box["cell"]
	var seed: StringName = _box["seed"]
	failure = await _hold(seed)
	if failure != "":
		return failure
	var before := _state().inventory.count(seed)
	await _tap("use")
	if not await _wait_for(func() -> bool: return field.crop_at(cell) == str(_box["crop"]), 60):
		return "`use` with %s did not plant %s (the cell is %s)" % [seed, cell, field.state_of(cell)]
	if _state().inventory.count(seed) != before - 1:
		return "planting took %d seeds, expected 1" % (before - _state().inventory.count(seed))
	var node := field.crop_node(cell)
	if node == null or node.stage != 0 or node.ripe:
		return "the crop is not shown as a seedling"
	if node.get_parent() != _farmer().get_parent():
		return "the crop does not stand among the entities the farmer Y-sorts with"
	return ""

func _water_it() -> String:
	var failure: String = await _stand_at_cell()
	if failure != "":
		return failure
	var field := RpgField.current()
	var cell: Vector2i = _box["cell"]
	failure = await _hold(&"watering_can")
	if failure != "":
		return failure
	RpgFarmWateringCan.fill()
	await _tap("use")
	if not await _wait_for(func() -> bool: return field.is_watered(cell), 60):
		return "`use` with the can did not water %s" % cell
	if RpgFarmWateringCan.charges() != RpgFarmWateringCan.SIZE - 1:
		return "the can holds %d, expected %d" % [RpgFarmWateringCan.charges(), RpgFarmWateringCan.SIZE - 1]
	var soil := _tree().current_scene.get_node("Soil") as TileMapLayer
	if soil.get_cell_atlas_coords(cell) != field.watered_tile:
		return "the Soil layer does not show watered soil at %s" % cell
	return ""

func _a_night_grows_it() -> String:
	var field := RpgField.current()
	var calendar := RpgCalendar.current()
	var cell: Vector2i = _box["cell"]
	var today := calendar.today()
	calendar.end_day()
	await _frames(2)
	if calendar.today() != today + 1 or calendar.minute != RpgCalendar.DAY_START:
		return "the day did not end: day %d at minute %d" % [calendar.today(), calendar.minute]
	if field.grown_at(cell) != 1:
		return "the watered crop grew %d days in one night" % field.grown_at(cell)
	if field.is_watered(cell):
		return "the soil is still wet in the morning"
	var crop := _crop()
	var wanted := RpgCropData.stage_of(1, RpgUtil.to_int(crop.get("days", 1)), RpgUtil.to_int(crop.get("stages", 1)))
	var node := field.crop_node(cell)
	if node == null or node.stage != wanted:
		return "the crop shows stage %d, expected %d" % [node.stage if node != null else -1, wanted]
	# a night without water does not count
	calendar.end_day()
	await _frames(2)
	if field.grown_at(cell) != 1:
		return "an unwatered crop grew: %d days" % field.grown_at(cell)
	return ""

func _crop_ripens() -> String:
	var field := RpgField.current()
	var calendar := RpgCalendar.current()
	var cell: Vector2i = _box["cell"]
	var days := RpgUtil.to_int(_crop().get("days", 1))
	var failure: String = await _hold(&"watering_can")
	if failure != "":
		return failure
	for night in range(1, days):
		if field.state_of(cell) != RpgField.CROP:
			return "the crop is %s after %d of %d days" % [field.state_of(cell), night, days]
		failure = await _stand_at_cell()
		if failure != "":
			return failure
		await _tap("use")
		if not await _wait_for(func() -> bool: return field.is_watered(cell), 60):
			return "the can did not water the crop on day %d (it holds %d)" % [night + 1, RpgFarmWateringCan.charges()]
		calendar.end_day()
		await _frames(2)
	if field.state_of(cell) != RpgField.RIPE:
		return "the crop is %s after %d watered nights, expected ripe" % [field.state_of(cell), days]
	var node := field.crop_node(cell)
	if node == null or not node.ripe or node.stage != RpgUtil.to_int(_crop().get("stages", 1)) - 1:
		return "the ripe crop does not show its last picture"
	return ""

func _harvest() -> String:
	var failure: String = await _stand_at_cell()
	if failure != "":
		return failure
	var field := RpgField.current()
	var cell: Vector2i = _box["cell"]
	var produce := StringName(str(_crop().get("produce", "")))
	var before := _state().inventory.count(produce)
	for attempt in 3:
		await _tap("interact")
		if await _wait_for(func() -> bool: return _state().inventory.count(produce) > before, 30):
			break
	if _state().inventory.count(produce) != before + 1:
		return "`interact` on the ripe crop put %d %s into the inventory, expected 1" % [_state().inventory.count(produce) - before, produce]
	var regrow := RpgUtil.to_int(_crop().get("regrow", 0))
	var wanted := RpgField.CROP if regrow > 0 else RpgField.SOIL
	if field.state_of(cell) != wanted:
		return "after the harvest the cell is %s, expected %s" % [field.state_of(cell), wanted]
	var saved := RpgUtil.to_dict(_state().get_flag(RpgField.FLAG_ENTITY, field.resolved_id(), {}))
	if not saved.has(RpgField.cell_name(cell)):
		return "the field is not in the saved game"
	return ""

# ---------------------------------------------------------------- money (T17.08)

func _controller() -> RpgUiController:
	var router := RpgUtil.router()
	return router.get_node_or_null("UiController") as RpgUiController if router != null else null

func _open_menu() -> Node:
	var controller := _controller()
	var menu: Node = controller.get("_menu") if controller != null else null
	return menu if menu != null and is_instance_valid(menu) else null

## Puts the farmer at `at`, looking `facing`, and waits until it can act.
func _stand(at: Vector2, facing: String) -> String:
	var farmer := _farmer()
	if farmer == null:
		return "the farmer is gone"
	farmer.global_position = at
	farmer.set_facing(facing)
	await _frames(4)
	if not await _wait_for(func() -> bool: return not farmer.is_busy(), 120):
		return "the farmer never finished using its tool"
	return ""

## `interact` until `done` says so (the first press may come before the bodies are known).
func _interact_until(done: Callable) -> bool:
	for attempt in 3:
		await _tap("interact")
		if await _wait_for(done, 30):
			return true
	return false

func _ship_the_crop() -> String:
	var scene := _tree().current_scene
	var field := RpgField.current()
	var bin := scene.find_child("ShippingBin", true, false) as RpgShippingBin
	if bin == null:
		return "the starter map has no shipping bin"
	if not ResourceLoader.exists("res://generated/scenes/farm/shipping_bin.tscn"):
		return "generated/scenes/farm/shipping_bin.tscn is missing"
	# the bin stands beside the plot: the farmer works it from the cell of the plot next to it
	var bin_cell := field.cell_at(bin.global_position + Vector2(0.0, -field.tile_px * 0.5))
	var failure := "no cell of the plot is next to the bin at %s" % bin_cell
	for entry: Array in [[Vector2i.RIGHT, "left"], [Vector2i.LEFT, "right"], [Vector2i.UP, "down"], [Vector2i.DOWN, "up"]]:
		var step: Vector2i = entry[0]
		if field.state_of(bin_cell + step) != "":
			failure = await _stand(field.cell_center(bin_cell + step), str(entry[1]))
			break
	if failure != "":
		return failure
	var produce := StringName(str(_crop().get("produce", "")))
	var had := _state().inventory.count(produce)
	if had < 1:
		return "the farmer has no %s to ship" % produce
	if RpgShippingBin.price_of(produce) <= 0:
		return "%s has no price" % produce
	failure = await _hold(produce)
	if failure != "":
		return failure
	if not await _interact_until(func() -> bool: return RpgShippingBin.count(produce) == had):
		return "`interact` with the bin put %d of %d %s into it" % [RpgShippingBin.count(produce), had, produce]
	if _state().inventory.count(produce) != 0:
		return "the held stack did not leave the inventory"
	# a mistake can be undone: with a tool in the hand the stack comes back out
	failure = await _hold(&"hoe")
	if failure != "":
		return failure
	if not await _interact_until(func() -> bool: return _state().inventory.count(produce) == had):
		return "`interact` with a tool in the hand did not take the stack back out"
	if not RpgShippingBin.is_empty():
		return "the bin still holds something"
	failure = await _hold(produce)
	if failure != "":
		return failure
	if not await _interact_until(func() -> bool: return RpgShippingBin.count(produce) == had):
		return "the stack did not go into the bin again"
	_box["shipped"] = had
	_box["produce"] = produce
	return ""

func _sleep_in_the_bed() -> String:
	var scene := _tree().current_scene
	var mode := RpgFarmMode.current()
	var calendar := RpgCalendar.current()
	var save := RpgUtil.save_manager()
	var bed := scene.find_child("Bed", true, false) as RpgBed
	if bed == null:
		return "the starter map has no bed"
	if mode.day_end == null or RpgDayEnd.current() != mode.day_end:
		return "the mode has no end of the day"
	var home := RpgBed.home(_state())
	if home.is_empty() or str(home.get("map", "")) != scene.scene_file_path:
		return "the bed of the map is not where the farmer wakes: %s" % home
	var failure: String = await _stand(bed.wake_position(), "up")
	if failure != "":
		return failure
	mode.energy.value = 30
	save.delete(RpgSaveManager.AUTOSAVE_SLOT)
	var today := calendar.today()
	var gold: int = _state().gold
	var ended: Array[int] = []
	var count := func(day: int) -> void: ended.append(day)
	calendar.day_ended.connect(count)
	var slept: bool = await _interact_until(func() -> bool: return calendar.today() > today)
	await _frames(3)
	calendar.day_ended.disconnect(count)
	if not slept:
		return "`interact` with the bed did not end the day"
	if ended.size() != 1 or calendar.today() != today + 1:
		return "sleeping ended %d days" % ended.size()
	if mode.day_end.last_night != RpgDayEnd.SLEPT:
		return "the night was '%s', expected a sleep" % mode.day_end.last_night
	if mode.energy.value != mode.energy.max_energy:
		return "the energy is %d in the morning, expected %d" % [mode.energy.value, mode.energy.max_energy]
	var produce: StringName = _box["produce"]
	var earned := RpgShippingBin.price_of(produce) * RpgUtil.to_int(_box["shipped"])
	if _state().gold != gold + earned:
		return "the night paid %d, expected %d" % [_state().gold - gold, earned]
	if not RpgShippingBin.is_empty():
		return "the bin is not empty in the morning"
	if not mode.day_end.saved or not save.has_save(RpgSaveManager.AUTOSAVE_SLOT):
		return "sleeping did not save into the autosave slot"
	if RpgUtil.to_int(save.header(RpgSaveManager.AUTOSAVE_SLOT).get("gold", -1)) != gold + earned:
		return "the save of the morning does not hold the money of the night"
	_box["earned"] = earned
	_box["gold"] = gold + earned
	return ""

func _morning_summary() -> String:
	var tree := _tree()
	var day_end := RpgFarmMode.current().day_end
	var summary := day_end.summary()
	if summary == null:
		return "the morning shows no summary"
	if not tree.paused:
		return "the game is not paused behind the summary"
	var produce: StringName = _box["produce"]
	var lines := RpgDaySummary.lines(summary.sale)
	var wanted := "%s x%d" % [RpgFarmStrings.item_name(produce), RpgUtil.to_int(_box["shipped"])]
	if lines.size() != 1 or not lines[0].begins_with(wanted) or not lines[0].contains(str(_box["earned"])):
		return "the summary lists %s, expected one line of %s for %s" % [lines, wanted, _box["earned"]]
	var total := summary.get_node_or_null("%Total") as Label
	if total == null or total.text != RpgDaySummary.total_text(summary.sale) or not total.text.contains(str(_box["earned"])):
		return "the summary does not show the total"
	await _frames(3)
	await _tap("confirm")
	if not await _wait_for(func() -> bool: return day_end.summary() == null, 60):
		return "`confirm` did not close the summary"
	await _frames(3)
	# a game that has no slot of its own yet is offered the save screen: it is closed again
	var menu := _open_menu()
	if menu != null:
		if not (menu is RpgSaveLoadMenu) or day_end.chosen_slot() != RpgSaveManager.NO_SLOT:
			return "a menu that is not the offered save screen is open after the summary"
		menu.call(&"close")
		await _frames(3)
	if tree.paused:
		return "the game is still paused after the summary"
	if _state().gold != RpgUtil.to_int(_box["gold"]):
		return "the money changed while the summary was shown"
	# the next night sells nothing and shows nothing
	RpgCalendar.current().end_day()
	await _frames(3)
	if day_end.summary() != null or tree.paused:
		return "a night in which nothing was sold shows a summary"
	return ""

## Asks for the village shop as the keeper's `open_shop:village_shop` does and waits for it.
func _ask_for_shop() -> RpgShopMenu:
	RpgUtil.emit(&"shop_requested", [&"village_shop"])
	for i in 30:
		await _tree().physics_frame
		var menu := _open_menu() as RpgShopMenu
		if menu != null:
			return menu
	return null

func _buy_seeds_at_the_shop() -> String:
	var tree := _tree()
	var mode := RpgFarmMode.current()
	var calendar := RpgCalendar.current()
	var shop := RpgShopDefinition.load_shop(&"village_shop") as RpgFarmShop
	if shop == null:
		return "game/data/shops/village_shop.tres is not the shop of a farm"
	if calendar.clock()[0] >= shop.opens:
		return "the morning is at %s, later than the shop opens" % [calendar.clock()]
	# the morning, before 9:00: closed, and it says so
	if shop.is_open() or shop.closed_reason() == "":
		return "the shop is open at %s" % [calendar.clock()]
	var early: RpgShopMenu = await _ask_for_shop()
	if early != null:
		return "the shop opened before its hours"
	# its closed day: closed at noon too
	var guard := 0
	while calendar.weekday() != shop.closed_weekday and guard < RpgCalendar.WEEK_DAYS:
		calendar.end_day()
		guard += 1
	await _frames(2)
	calendar.pass_minutes(12 * 60 - calendar.minute)
	if shop.is_open():
		return "the shop is open at noon of its closed day (weekday %d)" % calendar.weekday()
	var on_closed_day: RpgShopMenu = await _ask_for_shop()
	if on_closed_day != null:
		return "the shop opened on its closed day"
	calendar.end_day()
	await _frames(2)
	# opening time
	calendar.pass_minutes(shop.opens * 60 - calendar.minute)
	if calendar.clock() != ([shop.opens, 0] as Array[int]) or not shop.is_open():
		return "the shop is closed at %s on weekday %d" % [calendar.clock(), calendar.weekday()]
	var in_season := mode.crops.of_season(calendar.season_name())
	if in_season.is_empty():
		return "no crop grows in %s" % calendar.season_name()
	var seeds: Array[StringName] = []
	for crop_id in in_season:
		seeds.append(StringName(str(mode.crops.crop(crop_id).get("seed", ""))))
	var offered := shop.offered(_state().items)
	for seed_id in seeds:
		if not offered.has(seed_id):
			return "the shop does not offer %s in %s: %s" % [seed_id, calendar.season_name(), offered]
	for crop_id in mode.crops.order:
		var other := StringName(str(mode.crops.crop(crop_id).get("seed", "")))
		if not in_season.has(crop_id) and offered.has(other):
			return "the shop offers %s out of its season" % other
	for tool: StringName in [&"sickle", &"farm_axe"]:
		if not offered.has(tool):
			return "the shop does not sell the %s" % tool
	var menu: RpgShopMenu = await _ask_for_shop()
	if menu == null:
		return "the shop did not open in its hours"
	var failure := ""
	var wanted := seeds[0]
	var price := shop.buy_price(wanted, _state().items)
	var gold: int = _state().gold
	var had := _state().inventory.count(wanted)
	var row: Button = null
	for candidate in menu.rows():
		if menu.item_of(candidate) == wanted:
			row = candidate
	if not tree.paused:
		failure = "the game was not paused behind the shop"
	elif row == null:
		failure = "%s is not a row of the shop" % wanted
	elif price <= 0 or gold < price:
		failure = "%s costs %d and the farmer has %d" % [wanted, price, gold]
	else:
		row.pressed.emit()
		await _frames(2)
		if _state().inventory.count(wanted) != had + 1 or _state().gold != gold - price:
			failure = "buying %s left %d of them and %d money (was %d and %d)" % [wanted, _state().inventory.count(wanted), _state().gold, had, gold]
	if is_instance_valid(menu):
		menu.close()
	await _frames(2)
	if failure == "" and tree.paused:
		failure = "closing the shop did not unpause the game"
	tree.paused = false
	return failure
