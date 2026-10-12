extends RefCounted
## T17.04: the farmer. The tile ahead, the four tools and the cells each may change, what a use
## costs, the hotbar, the energy, seeds and food, and the farm's mode.

const Fixtures := preload("../lib/fixtures.gd")

const TILE := 16
const MOVEMENT := "res://addons/rpg_runtime/actors/components/movement.gd"
const CROPS := [
	{"id": "corn", "name": "Corn", "seed": "seed_corn", "produce": "crop_corn", "seasons": ["spring", "summer"], "days": 3, "stages": 4, "regrow": 0, "seed_price": 15, "price": 30, "energy": 14},
	{"id": "pumpkin", "name": "Pumpkin", "seed": "seed_pumpkin", "produce": "crop_pumpkin", "seasons": ["autumn"], "days": 2, "stages": 3, "regrow": 0, "seed_price": 10, "price": 20, "energy": 12},
]
const ITEMS: Array[StringName] = [&"hoe", &"watering_can", &"sickle", &"farm_axe", &"seed_corn", &"seed_pumpkin", &"crop_corn"]

var _made: Array[Node] = []

## A tile set of four tiles: ground that can be tilled, tilled soil, watered soil, water.
static func tile_set() -> TileSet:
	var tiles := TileSet.new()
	tiles.tile_size = Vector2i(TILE, TILE)
	for data_name: String in ["tillable", "water"]:
		tiles.add_custom_data_layer()
		tiles.set_custom_data_layer_name(tiles.get_custom_data_layers_count() - 1, data_name)
		tiles.set_custom_data_layer_type(tiles.get_custom_data_layers_count() - 1, TYPE_BOOL)
	var source := TileSetAtlasSource.new()
	source.texture = ImageTexture.create_from_image(Image.create_empty(TILE * 4, TILE, false, Image.FORMAT_RGBA8))
	source.texture_region_size = Vector2i(TILE, TILE)
	tiles.add_source(source, 0)
	for x in 4:
		source.create_tile(Vector2i(x, 0))
	source.get_tile_data(Vector2i(0, 0), 0).set_custom_data("tillable", true)
	source.get_tile_data(Vector2i(3, 0), 0).set_custom_data("water", true)
	return tiles

## A map with a plot of 4 by 3 cells of tillable ground at (2, 2), a cell of water at (7, 2),
## and its field. {root, soil, field, entities}
func _map() -> Dictionary:
	var root := Node2D.new()
	root.name = "Farm"
	var soil := TileMapLayer.new()
	soil.name = "Soil"
	soil.tile_set = tile_set()
	root.add_child(soil)
	for y in range(2, 5):
		for x in range(2, 6):
			soil.set_cell(Vector2i(x, y), 0, Vector2i(0, 0))
	soil.set_cell(Vector2i(7, 2), 0, Vector2i(3, 0))
	var ysorted := Node2D.new()
	ysorted.name = "YSorted"
	root.add_child(ysorted)
	var entities := Node2D.new()
	entities.name = "Entities"
	ysorted.add_child(entities)
	var field := RpgField.new()
	field.name = "Field"
	field.field_id = "farm"
	field.crops = _crops()
	root.add_child(field)
	field.setup()
	_made.append(root)
	return {"root": root, "soil": soil, "field": field, "entities": entities}

func _crops() -> RpgCropData:
	var data := RpgCropData.new()
	data.add_list(CROPS)
	return data

## A game with the farm's items, the mode and a farmer on `map`, standing in the cell (3, 1)
## above the plot and looking down at (3, 2).
func _farm(map: Dictionary) -> Dictionary:
	var registry := {}
	for id in ITEMS:
		registry[id] = Fixtures.item(id)
	var state := Fixtures.install_state(registry) as RpgGameState
	state.inventory.registry = state.items
	for id: StringName in [&"hoe", &"watering_can", &"sickle", &"farm_axe"]:
		state.inventory.add(id, 1)
	state.inventory.add(&"seed_corn", 5)
	var mode := RpgFarmMode.new()
	mode.crops = _crops()
	mode.ensure_parts()
	_made.append(mode)
	var farmer := RpgFarmer.new()
	farmer.name = "Player"
	farmer.mode = mode
	farmer.field = map["field"]
	var entities: Node2D = map["entities"]
	entities.add_child(farmer)
	_stand(farmer, Vector2i(3, 1), "down")
	return {"state": state, "mode": mode, "farmer": farmer}

func _stand(farmer: RpgFarmer, cell: Vector2i, facing: String) -> void:
	farmer.position = (Vector2(cell) + Vector2(0.5, 0.5)) * TILE
	farmer.facing = facing

## Uses the held item and lets the use end.
func _use(farmer: RpgFarmer) -> bool:
	var done := farmer.use_held()
	farmer._end_use()
	return done

func _clearable(map: Dictionary, kind: String, cell: Vector2i) -> Node2D:
	var thing := Node2D.new()
	thing.name = kind.capitalize()
	thing.set_meta(RpgField.CLEAR_META, kind)
	thing.position = (Vector2(cell) + Vector2(0.5, 0.5)) * TILE
	var entities: Node2D = map["entities"]
	entities.add_child(thing)
	return thing

func _cleanup() -> void:
	for node in _made:
		if is_instance_valid(node):
			node.free()
	_made.clear()
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- the tile ahead

func test_the_tile_ahead_for_four_facings(t) -> void:
	t.eq(RpgFarmer.ahead_of(Vector2i(4, 4), "up"), Vector2i(4, 3))
	t.eq(RpgFarmer.ahead_of(Vector2i(4, 4), "down"), Vector2i(4, 5))
	t.eq(RpgFarmer.ahead_of(Vector2i(4, 4), "left"), Vector2i(3, 4))
	t.eq(RpgFarmer.ahead_of(Vector2i(4, 4), "right"), Vector2i(5, 4))
	var map := _map()
	var farm := _farm(map)
	var farmer: RpgFarmer = farm["farmer"]
	t.eq(farmer.cell(), Vector2i(3, 1), "the cell under its feet")
	for facing: String in ["up", "down", "left", "right"]:
		farmer.facing = facing
		t.eq(farmer.tile_ahead(), Vector2i(3, 1) + RpgFarmer.step_of(facing), facing)
	farmer.facing = "up"
	farmer.position += Vector2(7, 7)  # anywhere in the cell
	t.eq(farmer.tile_ahead(), Vector2i(3, 0), "the cell counts, not the pixel")
	farmer.field = null
	farmer.tile_px = 32
	farmer.position = Vector2(40, 40)
	farmer.facing = "right"
	t.eq(farmer.tile_ahead(), Vector2i(2, 1), "without a field the farmer counts in its own tile size")
	_cleanup()

# ---------------------------------------------------------------- the tools

func test_the_hoe_tills_ground_and_nothing_else(t) -> void:
	var map := _map()
	var farm := _farm(map)
	var farmer: RpgFarmer = farm["farmer"]
	var mode: RpgFarmMode = farm["mode"]
	var field: RpgField = map["field"]
	var soil: TileMapLayer = map["soil"]
	t.ok(mode.hotbar.hold_item(&"hoe"))
	t.eq(field.state_of(Vector2i(3, 2)), RpgField.GROUND, "the recipe marked the plot as tillable")
	t.eq(field.state_of(Vector2i(3, 0)), "", "and nothing outside it")
	t.ok(_use(farmer), "ground is tilled")
	t.eq(field.state_of(Vector2i(3, 2)), RpgField.SOIL)
	t.eq(soil.get_cell_atlas_coords(Vector2i(3, 2)), field.tilled_tile, "painted on the Soil layer")
	t.ok(not _use(farmer), "tilled soil is not tilled again")
	_stand(farmer, Vector2i(3, 1), "up")
	t.ok(not _use(farmer), "a cell whose tile does not say tillable is left alone")
	t.eq(field.cells.size(), 1, "one cell was worked")
	_stand(farmer, Vector2i(6, 2), "right")
	t.ok(not _use(farmer), "water is not tilled")
	var stump := _clearable(map, "stump", Vector2i(4, 2))
	_stand(farmer, Vector2i(4, 1), "down")
	t.ok(not _use(farmer), "ground under a stump is not tilled")
	stump.free()
	t.ok(_use(farmer), "and is once the stump is gone")
	_cleanup()

func test_the_watering_can_waters_soil_and_is_filled_at_water(t) -> void:
	var map := _map()
	var farm := _farm(map)
	var farmer: RpgFarmer = farm["farmer"]
	var mode: RpgFarmMode = farm["mode"]
	var field: RpgField = map["field"]
	var soil: TileMapLayer = map["soil"]
	mode.hotbar.hold_item(&"watering_can")
	t.ok(not _use(farmer), "ground that is not tilled is not watered")
	t.eq(RpgFarmWateringCan.charges(), RpgFarmWateringCan.SIZE, "and the can is as full as it was")
	field.till(Vector2i(3, 2))
	t.ok(_use(farmer))
	t.ok(field.is_watered(Vector2i(3, 2)))
	t.eq(soil.get_cell_atlas_coords(Vector2i(3, 2)), field.watered_tile)
	t.eq(RpgFarmWateringCan.charges(), RpgFarmWateringCan.SIZE - 1)
	t.ok(not _use(farmer), "wet soil is not watered again")
	t.eq(RpgFarmWateringCan.charges(), RpgFarmWateringCan.SIZE - 1)
	field.plant(Vector2i(3, 2), "corn")
	field.cells[Vector2i(3, 2)]["w"] = false
	t.ok(_use(farmer), "soil with a crop on it is watered")
	# an empty can waters nothing, and is filled at water for no energy
	RpgFarmWateringCan.set_charges(0)
	field.till(Vector2i(4, 2))
	_stand(farmer, Vector2i(4, 1), "down")
	var before := mode.energy.value
	t.ok(not _use(farmer), "an empty can")
	t.ok(not field.is_watered(Vector2i(4, 2)))
	_stand(farmer, Vector2i(6, 2), "right")
	t.ok(field.is_water(Vector2i(7, 2)), "the tile says it is water")
	t.ok(_use(farmer), "filled at water")
	t.eq(RpgFarmWateringCan.charges(), RpgFarmWateringCan.SIZE)
	t.eq(mode.energy.value, before, "filling costs nothing")
	t.ok(not _use(farmer), "a full can is not filled")
	_cleanup()

func test_the_sickle_cuts_what_is_ripe_what_withered_and_grass(t) -> void:
	var map := _map()
	var farm := _farm(map)
	var farmer: RpgFarmer = farm["farmer"]
	var mode: RpgFarmMode = farm["mode"]
	var state: RpgGameState = farm["state"]
	var field: RpgField = map["field"]
	mode.hotbar.hold_item(&"sickle")
	t.ok(not _use(farmer), "ground")
	field.till(Vector2i(3, 2))
	t.ok(not _use(farmer), "bare soil")
	field.plant(Vector2i(3, 2), "corn")
	t.ok(not _use(farmer), "a crop that still grows")
	t.eq(field.crop_at(Vector2i(3, 2)), "corn")
	field.cells[Vector2i(3, 2)]["dead"] = true
	t.ok(_use(farmer), "a withered crop is cut away")
	t.eq(field.state_of(Vector2i(3, 2)), RpgField.SOIL, "and leaves tilled soil")
	t.eq(state.inventory.count(&"crop_corn"), 0, "and nothing to eat")
	var grass := _clearable(map, "grass", Vector2i(4, 2))
	var stump := _clearable(map, "stump", Vector2i(5, 2))
	_stand(farmer, Vector2i(5, 1), "down")
	t.ok(not _use(farmer), "a stump is not for the sickle")
	t.ok(not stump.is_queued_for_deletion())
	_stand(farmer, Vector2i(4, 1), "down")
	t.ok(_use(farmer), "grass is")
	t.ok(grass.is_queued_for_deletion())
	_cleanup()

func test_the_axe_clears_a_stump_and_a_branch(t) -> void:
	var map := _map()
	var farm := _farm(map)
	var farmer: RpgFarmer = farm["farmer"]
	var mode: RpgFarmMode = farm["mode"]
	var field: RpgField = map["field"]
	mode.hotbar.hold_item(&"farm_axe")
	t.ok(not _use(farmer), "ground")
	field.till(Vector2i(3, 2))
	field.plant(Vector2i(3, 2), "corn")
	t.ok(not _use(farmer), "a crop")
	t.eq(field.crop_at(Vector2i(3, 2)), "corn", "the crop stands")
	var stump := _clearable(map, "stump", Vector2i(4, 2))
	var branch := _clearable(map, "branch", Vector2i(5, 2))
	var grass := _clearable(map, "grass", Vector2i(2, 2))
	_stand(farmer, Vector2i(4, 1), "down")
	t.ok(_use(farmer))
	t.ok(stump.is_queued_for_deletion())
	_stand(farmer, Vector2i(5, 1), "down")
	t.ok(_use(farmer))
	t.ok(branch.is_queued_for_deletion())
	_stand(farmer, Vector2i(2, 1), "down")
	t.ok(not _use(farmer), "grass is not for the axe")
	t.ok(not grass.is_queued_for_deletion())
	_cleanup()

# ---------------------------------------------------------------- energy

func test_a_tool_costs_its_energy_and_none_without_effect(t) -> void:
	var map := _map()
	var farm := _farm(map)
	var farmer: RpgFarmer = farm["farmer"]
	var mode: RpgFarmMode = farm["mode"]
	var seen: Array[int] = []
	mode.energy.changed.connect(func(value: int, _maximum: int) -> void: seen.append(value))
	t.eq(mode.energy.value, RpgEnergy.MAX_ENERGY, "a new game starts rested")
	mode.hotbar.hold_item(&"hoe")
	var hoe := mode.tool_for(&"hoe")
	t.ok(_use(farmer))
	t.eq(mode.energy.value, RpgEnergy.MAX_ENERGY - hoe.energy_cost)
	t.ok(not _use(farmer), "the cell is tilled already")
	t.eq(mode.energy.value, RpgEnergy.MAX_ENERGY - hoe.energy_cost, "a use without effect costs nothing")
	t.eq(seen, [RpgEnergy.MAX_ENERGY - hoe.energy_cost] as Array[int])
	t.ok(mode.tool_for(&"farm_axe").energy_cost > hoe.energy_cost, "the axe is heavier")
	t.eq(mode.tool_for(&"seed_corn"), null, "a seed is no tool")
	# while a tool is used the farmer stands and no second use begins
	_stand(farmer, Vector2i(4, 1), "down")
	t.ok(farmer.use_held())
	t.ok(farmer.is_busy() and farmer.move_locked)
	_stand(farmer, Vector2i(5, 1), "down")
	t.ok(not farmer.use_held(), "one use at a time")
	farmer._physics_process(hoe.use_time_s + 0.01)
	t.ok(not farmer.is_busy() and not farmer.move_locked, "the use takes its time and ends")
	t.eq(RpgUtil.to_int(RpgUtil.state().get_flag("farm", "energy")), mode.energy.value, "the energy is in the saved game")
	_cleanup()

func test_at_zero_energy_a_tool_does_nothing_and_the_farmer_is_slow(t) -> void:
	var map := _map()
	var farm := _farm(map)
	var farmer: RpgFarmer = farm["farmer"]
	var mode: RpgFarmMode = farm["mode"]
	var field: RpgField = map["field"]
	var components := Node.new()
	components.name = "Components"
	farmer.add_child(components)
	var movement := Node.new()
	movement.name = "Movement"
	movement.set_script(load(MOVEMENT))
	components.add_child(movement)
	movement.set("speed", 80.0)
	farmer._pace()
	t.near(movement.get("speed"), 80.0)
	mode.energy.value = 1
	mode.hotbar.hold_item(&"hoe")
	t.ok(_use(farmer), "the last of the energy")
	t.eq(mode.energy.value, 0, "it does not go below nothing")
	t.ok(mode.energy.is_exhausted())
	_stand(farmer, Vector2i(4, 1), "down")
	t.ok(not _use(farmer), "no tool works at zero")
	t.eq(field.state_of(Vector2i(4, 2)), RpgField.GROUND)
	farmer._pace()
	t.near(movement.get("speed"), 80.0 * RpgFarmer.SLOW, 0.001, "and the farmer walks slowly")
	# food brings it back
	var state: RpgGameState = farm["state"]
	state.inventory.add(&"crop_corn", 2)
	mode.hotbar.hold_item(&"crop_corn")
	t.ok(_use(farmer), "food is eaten")
	t.eq(mode.energy.value, 14, "it restores what crops.json says")
	t.eq(state.inventory.count(&"crop_corn"), 1)
	farmer._pace()
	t.near(movement.get("speed"), 80.0)
	mode.hotbar.hold_item(&"hoe")
	t.ok(_use(farmer), "and the hoe works again")
	mode.energy.fill()
	mode.hotbar.hold_item(&"crop_corn")
	t.ok(not _use(farmer), "a rested farmer does not eat")
	t.eq(state.inventory.count(&"crop_corn"), 1)
	_cleanup()

# ---------------------------------------------------------------- the hotbar

func test_the_hotbar_holds_and_cycles(t) -> void:
	var map := _map()
	var farm := _farm(map)
	var mode: RpgFarmMode = farm["mode"]
	var state: RpgGameState = farm["state"]
	var bar := mode.hotbar
	var changes: Array[int] = []
	bar.changed.connect(func() -> void: changes.append(bar.held))
	t.eq(bar.held, 0)
	t.eq(bar.held_item(), &"hoe", "the first stack of the inventory is the first slot")
	t.eq([bar.item_at(1), bar.item_at(2), bar.item_at(3), bar.item_at(4)], [&"watering_can", &"sickle", &"farm_axe", &"seed_corn"])
	t.eq(bar.qty_at(4), 5)
	t.eq(bar.item_at(5), &"", "an empty slot")
	bar.next()
	t.eq(bar.held_item(), &"watering_can")
	bar.prev()
	bar.prev()
	t.eq(bar.held, RpgHotbar.SLOTS - 1, "before the first is the last")
	t.eq(bar.held_item(), &"")
	bar.next()
	t.eq(bar.held, 0, "and after the last the first")
	bar.select(4)
	t.eq(bar.held_item(), &"seed_corn", "a number key")
	bar.select(4)
	t.eq(changes, [1, 0, 9, 0, 4] as Array[int], "a slot that is held already changes nothing")
	t.ok(not bar.hold_item(&"crop_corn"), "an item the farmer does not have")
	t.eq(RpgUtil.to_int(state.get_flag("farm", "held")), 4, "the held slot is in the saved game")
	# the eleventh stack is in the bag, not in the bar
	for i in 8:
		state.items[StringName("thing_%d" % i)] = Fixtures.item(StringName("thing_%d" % i))
		state.inventory.add(StringName("thing_%d" % i), 1)
	t.eq(bar.item_at(RpgHotbar.SLOTS - 1), &"thing_4")
	t.ok(not bar.hold_item(&"thing_7"), "ten slots")
	_cleanup()

# ---------------------------------------------------------------- seeds and a harvest

func test_a_seed_is_planted_in_soil_in_its_season(t) -> void:
	var map := _map()
	var farm := _farm(map)
	var farmer: RpgFarmer = farm["farmer"]
	var mode: RpgFarmMode = farm["mode"]
	var state: RpgGameState = farm["state"]
	var field: RpgField = map["field"]
	state.inventory.add(&"seed_pumpkin", 2)
	mode.hotbar.hold_item(&"seed_corn")
	var energy := mode.energy.value
	t.ok(not _use(farmer), "ground that is not tilled takes no seed")
	t.eq(state.inventory.count(&"seed_corn"), 5)
	field.till(Vector2i(3, 2))
	t.ok(_use(farmer))
	t.eq(field.crop_at(Vector2i(3, 2)), "corn")
	t.eq(state.inventory.count(&"seed_corn"), 4, "one seed is in the ground")
	t.eq(mode.energy.value, energy, "planting costs no energy")
	t.ok(not _use(farmer), "a cell holds one crop")
	t.eq(state.inventory.count(&"seed_corn"), 4)
	field.till(Vector2i(4, 2))
	_stand(farmer, Vector2i(4, 1), "down")
	mode.hotbar.hold_item(&"seed_pumpkin")
	t.ok(not _use(farmer), "a pumpkin does not grow in spring (there is no calendar: it is spring)")
	t.eq(state.inventory.count(&"seed_pumpkin"), 2, "and the seed is kept")
	t.eq(field.state_of(Vector2i(4, 2)), RpgField.SOIL)
	_cleanup()

func test_use_harvests_a_ripe_crop_whatever_is_held(t) -> void:
	var map := _map()
	var farm := _farm(map)
	var farmer: RpgFarmer = farm["farmer"]
	var mode: RpgFarmMode = farm["mode"]
	var state: RpgGameState = farm["state"]
	var field: RpgField = map["field"]
	field.till(Vector2i(3, 2))
	field.plant(Vector2i(3, 2), "corn")
	field.cells[Vector2i(3, 2)]["grown"] = 3
	t.eq(field.state_of(Vector2i(3, 2)), RpgField.RIPE)
	mode.hotbar.hold_item(&"hoe")
	var energy := mode.energy.value
	t.ok(_use(farmer))
	t.eq(state.inventory.count(&"crop_corn"), 1)
	t.eq(field.state_of(Vector2i(3, 2)), RpgField.SOIL)
	t.eq(mode.energy.value, energy, "picking costs nothing")
	_cleanup()

# ---------------------------------------------------------------- the mode

func test_a_mode_that_is_only_made_has_no_parts_and_one_that_is_ready_has_the_calendar(t) -> void:
	Fixtures.install_state()
	var mode := RpgFarmMode.new()
	t.eq(mode.get_child_count(), 0, "the scene the builder saves holds no parts")
	t.eq(RpgCalendar.current(), null, "no calendar before a mode asks for one")
	mode._ready()
	t.ok(RpgCalendar.current() != null, "the mode asks for the calendar")
	t.ok(mode.energy != null and mode.hotbar != null and mode.day_end != null)
	t.eq(mode.get_child_count(), 3, "the energy, the hotbar and the end of the day")
	mode._ready()
	t.eq(mode.get_child_count(), 3, "made once")
	t.ok(not mode.is_in_combat())
	for id: StringName in [&"hoe", &"watering_can", &"sickle", &"farm_axe"]:
		t.ok(mode.tool_for(id) != null and mode.tool_for(id).id == id, String(id))
	# the morning after a day that nobody stayed up to the end of: rested (RpgDayEnd, T17.08),
	# and the can is full (a stand-in until the map has water, T17.06)
	mode.energy.value = 3
	RpgFarmWateringCan.set_charges(2)
	RpgCalendar.current().end_day()
	t.eq(mode.energy.value, mode.energy.max_energy)
	t.eq(RpgFarmWateringCan.charges(), RpgFarmWateringCan.SIZE)
	mode.free()
	Fixtures.uninstall_state()
