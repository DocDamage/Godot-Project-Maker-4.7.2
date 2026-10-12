extends RefCounted
## The farm's smoke steps (T17.04, T17.05), appended after the shared sequence (which ends in
## the starter map): the map has its field and the game its farmer, calendar and tools -> a cell
## is tilled, planted and watered with the real input actions (`hotbar_<n>` chooses, `use`
## works) -> a night passes and the crop is a day further -> the nights to ripeness -> the crop
## is picked with `interact`.
##
## Nobody can sleep yet (T17.08), so the night is the calendar's `end_day()`, run in full. The
## farm's whole day, from waking to the shop and the people, is T17.18.

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
		if mode.tool_for(item) == null or not _state().inventory.has(item):
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
