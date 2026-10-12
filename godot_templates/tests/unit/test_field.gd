extends RefCounted
## T17.05: soil and crops. A crop from seed to harvest over as many watered nights as its entry
## says, a night without water, soil that dries and goes back to ground, withering when the
## season changes, a crop that grows again, the harvest into the inventory, the pictures, the
## night of a field that is not shown, and the save.

const Fixtures := preload("../lib/fixtures.gd")
const Farmer := preload("test_farmer.gd")

const TILE := 16
const CORN := Vector2i(2, 2)
const CROPS := [
	{"id": "corn", "name": "Corn", "seed": "seed_corn", "produce": "crop_corn", "seasons": ["spring", "summer"], "days": 4, "stages": 5, "regrow": 0, "seed_price": 20, "price": 40, "energy": 16},
	{"id": "bean", "name": "Bean", "seed": "seed_bean", "produce": "crop_bean", "seasons": ["spring"], "days": 6, "stages": 4, "regrow": 2, "seed_price": 30, "price": 20, "energy": 20},
	{"id": "leek", "name": "Leek", "seed": "seed_leek", "produce": "crop_leek", "seasons": ["spring", "summer", "autumn", "winter"], "days": 2, "stages": 12, "regrow": 0, "seed_price": 10, "price": 20, "energy": 12},
]

var _roots: Array[Node] = []

func _crops() -> RpgCropData:
	var data := RpgCropData.new()
	data.add_list(CROPS)
	return data

## A game and a map `map_id` with a plot of 4 by 3 cells at (2, 2). {root, soil, field, entities}
func _map(map_id: String = "farm", install: bool = true) -> Dictionary:
	if install:
		var registry := {}
		for crop: Dictionary in CROPS:
			registry[StringName(str(crop["produce"]))] = Fixtures.item(StringName(str(crop["produce"])))
		var state := Fixtures.install_state(registry) as RpgGameState
		state.inventory.registry = state.items
	var root := Node2D.new()
	root.name = map_id.capitalize()
	var soil := TileMapLayer.new()
	soil.name = "Soil"
	soil.tile_set = Farmer.tile_set()
	root.add_child(soil)
	for y in range(2, 5):
		for x in range(2, 6):
			soil.set_cell(Vector2i(x, y), 0, Vector2i(0, 0))
	var ysorted := Node2D.new()
	ysorted.name = "YSorted"
	root.add_child(ysorted)
	var entities := Node2D.new()
	entities.name = "Entities"
	ysorted.add_child(entities)
	var field := RpgField.new()
	field.name = "Field"
	field.field_id = map_id
	field.crops = _crops()
	root.add_child(field)
	field.setup()
	_roots.append(root)
	return {"root": root, "soil": soil, "field": field, "entities": entities}

## One night over the field, as the mode runs it: the data in the game state grows, and the
## field that is shown takes it.
func _night(field: RpgField, season_next: String = "spring") -> void:
	RpgField.night_all(field.crops, season_next)
	field.load_state()
	field.refresh()

func _cleanup() -> void:
	for node in _roots:
		if is_instance_valid(node):
			node.free()
	_roots.clear()
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- growing

func test_a_crop_watered_every_day_is_ripe_after_its_days_and_not_before(t) -> void:
	var map := _map()
	var field: RpgField = map["field"]
	t.ok(field.till(CORN) and field.plant(CORN, "corn"))
	t.eq(field.state_of(CORN), RpgField.CROP)
	for night in 4:
		t.eq(field.grown_at(CORN), night)
		t.ok(not field.harvest(CORN), "not ripe after %d nights" % night)
		t.ok(field.water(CORN))
		_night(field)
		t.ok(not field.is_watered(CORN), "the soil is dry in the morning")
	t.eq(field.state_of(CORN), RpgField.RIPE, "ripe after as many nights as its entry says")
	t.ok(field.water(CORN))
	_night(field)
	t.eq(field.grown_at(CORN), 4, "a ripe crop waits")
	t.eq(field.state_of(CORN), RpgField.RIPE)
	_cleanup()

func test_a_day_without_water_does_not_count(t) -> void:
	var map := _map()
	var field: RpgField = map["field"]
	field.till(CORN)
	field.plant(CORN, "corn")
	_night(field)
	_night(field)
	t.eq(field.grown_at(CORN), 0, "two dry nights")
	t.eq(field.crop_at(CORN), "corn", "it does not die of thirst")
	field.water(CORN)
	_night(field)
	_night(field)
	field.water(CORN)
	_night(field)
	t.eq(field.grown_at(CORN), 2, "two of five nights were watered")
	t.eq(field.state_of(CORN), RpgField.CROP)
	_cleanup()

func test_soil_dries_and_bare_soil_goes_back_to_ground(t) -> void:
	var map := _map()
	var field: RpgField = map["field"]
	var soil: TileMapLayer = map["soil"]
	var bare := Vector2i(3, 2)
	var outside := Vector2i(9, 9)
	t.ok(not field.till(outside), "a cell whose tile does not say tillable")
	t.ok(field.till(bare) and field.till(CORN))
	field.plant(CORN, "corn")
	t.eq(soil.get_cell_atlas_coords(bare), field.tilled_tile)
	field.water(bare)
	t.eq(soil.get_cell_atlas_coords(bare), field.watered_tile)
	_night(field)
	t.eq(soil.get_cell_atlas_coords(bare), field.tilled_tile, "dry again")
	for night in RpgField.IDLE_NIGHTS - 1:
		_night(field)
		t.eq(field.state_of(bare), RpgField.SOIL, "still tilled after %d dry nights" % (night + 1))
	_night(field)
	t.eq(field.state_of(bare), RpgField.GROUND, "after %d nights with nothing on it and no water it is ground" % RpgField.IDLE_NIGHTS)
	t.eq(soil.get_cell_atlas_coords(bare), Vector2i(0, 0), "and the layer shows the ground it had")
	t.ok(field.till(bare), "which can be tilled again")
	t.eq(field.state_of(CORN), RpgField.CROP, "soil with a crop on it stays")
	t.eq(field.water_all(), 2, "rain waters every tilled cell")
	t.ok(field.is_watered(bare) and field.is_watered(CORN))
	_cleanup()

func test_a_crop_out_of_season_withers_when_the_season_changes(t) -> void:
	var map := _map()
	var field: RpgField = map["field"]
	var bean := Vector2i(3, 2)
	var leek := Vector2i(4, 2)
	for cell: Vector2i in [CORN, bean, leek]:
		field.till(cell)
	field.plant(CORN, "corn")
	field.plant(bean, "bean")
	field.plant(leek, "leek")
	_night(field, "spring")
	t.eq([field.state_of(CORN), field.state_of(bean)], [RpgField.CROP, RpgField.CROP], "the season goes on")
	_night(field, "summer")
	t.eq(field.state_of(CORN), RpgField.CROP, "corn grows in summer too")
	t.eq(field.state_of(bean), RpgField.WITHERED, "a bean does not")
	t.eq(field.state_of(leek), RpgField.CROP)
	field.water(bean)
	_night(field, "summer")
	t.eq(field.grown_at(bean), 0, "a withered crop does not grow")
	t.ok(not field.harvest(bean))
	t.ok(field.remove_crop(bean), "it is cut away")
	t.eq(field.state_of(bean), RpgField.SOIL)
	t.ok(not field.can_plant(bean, "bean", "summer"), "and is not planted out of its season")
	t.ok(field.can_plant(bean, "corn", "summer"))
	_night(field, "autumn")
	t.eq(field.state_of(CORN), RpgField.WITHERED)
	t.eq(field.state_of(leek), RpgField.CROP, "a crop of every season never withers")
	_cleanup()

func test_the_night_of_the_calendar_grows_the_field_and_the_last_night_of_a_season_withers(t) -> void:
	var map := _map()
	var field: RpgField = map["field"]
	var mode := RpgFarmMode.new()
	mode.crops = _crops()
	mode._ready()
	var calendar := RpgCalendar.current()
	t.ok(calendar != null)
	var bean := Vector2i(3, 2)
	field.till(CORN)
	field.till(bean)
	t.ok(field.plant(CORN, "corn") and field.plant(bean, "bean"))
	field.water(CORN)
	field.water(bean)
	calendar.end_day()
	field.load_state()
	t.eq([field.grown_at(CORN), field.grown_at(bean)], [1, 1], "the mode's night listener ran")
	calendar.day = calendar.days_per_season  # the last day of spring
	field.water(bean)
	calendar.end_day()
	field.load_state()
	t.eq(calendar.season_name(), "summer")
	t.eq(field.grown_at(bean), 2, "the last night counts")
	t.eq(field.state_of(bean), RpgField.WITHERED, "and the morning of summer finds the bean withered")
	t.eq(field.state_of(CORN), RpgField.CROP)
	field.till(Vector2i(4, 2))
	t.ok(not field.plant(Vector2i(4, 2), "bean"), "no bean is planted in summer")
	t.ok(field.plant(Vector2i(4, 2), "corn"), "corn is")
	mode.free()
	_cleanup()

func test_a_crop_that_grows_again_does(t) -> void:
	var map := _map()
	var field: RpgField = map["field"]
	var state := RpgUtil.state()
	var bean := Vector2i(3, 2)
	field.till(bean)
	field.plant(bean, "bean")
	for night in 6:
		field.water(bean)
		_night(field)
	t.eq(field.state_of(bean), RpgField.RIPE)
	t.ok(field.harvest(bean))
	t.eq(state.inventory.count(&"crop_bean"), 1)
	t.eq(field.crop_at(bean), "bean", "the plant stays")
	t.eq(field.state_of(bean), RpgField.CROP)
	t.eq(field.grown_at(bean), 4, "two days from the next harvest")
	field.water(bean)
	_night(field)
	t.ok(not field.harvest(bean), "one night is not enough")
	field.water(bean)
	_night(field)
	t.ok(field.harvest(bean), "two are")
	t.eq(state.inventory.count(&"crop_bean"), 2)
	_cleanup()

# ---------------------------------------------------------------- the harvest

func test_a_harvest_goes_into_the_inventory_and_a_full_one_leaves_the_crop_standing(t) -> void:
	var map := _map()
	var field: RpgField = map["field"]
	var state := RpgUtil.state()
	var events: Array = []
	field.harvested.connect(func(crop_id: String, item_id: StringName, qty: int) -> void: events.append([crop_id, item_id, qty]))
	field.till(CORN)
	field.plant(CORN, "corn")
	field.cells[CORN]["grown"] = 4
	state.inventory.capacity = 0
	t.ok(not field.harvest(CORN), "no room")
	t.eq(field.state_of(CORN), RpgField.RIPE, "the crop stands")
	t.eq(events.size(), 0)
	state.inventory.capacity = 40
	var node := field.crop_node(CORN)
	field.refresh()
	t.ok(node != null and node.ripe, "a ripe crop can be picked")
	node.interact()
	t.eq(state.inventory.count(&"crop_corn"), 1, "`interact` on it harvests")
	t.eq(events, [["corn", &"crop_corn", 1]])
	t.eq(field.state_of(CORN), RpgField.SOIL, "a crop of one harvest leaves tilled soil")
	t.ok(not field.harvest(CORN))
	_cleanup()

# ---------------------------------------------------------------- the pictures

func test_the_stages_are_spread_evenly_over_the_days(t) -> void:
	# the same numbers as tests/unit/test_crop_plan.py (crop_plan.stage_of)
	var cases := [[0, 4, 5, 0], [1, 4, 5, 1], [3, 4, 5, 3], [4, 4, 5, 4], [0, 6, 4, 0], [1, 6, 4, 0], [2, 6, 4, 1], [5, 6, 4, 2], [6, 6, 4, 3],
		[1, 2, 12, 5], [2, 2, 12, 11], [9, 2, 12, 11], [7, 14, 29, 14], [0, 1, 1, 0], [1, 1, 1, 0]]
	for case: Array in cases:
		t.eq(RpgCropData.stage_of(case[0], case[1], case[2]), case[3], str(case))
	t.ok(not RpgCropData.is_ripe(3, 4) and RpgCropData.is_ripe(4, 4))
	var map := _map()
	var field: RpgField = map["field"]
	var entities: Node2D = map["entities"]
	var leek := Vector2i(4, 3)
	field.till(leek)
	field.plant(leek, "leek")
	var node := field.crop_node(leek)
	t.ok(node != null and node.get_parent() == entities, "a crop is a scene among the entities of the map")
	t.eq(node.position, Vector2(4.5 * TILE, 4 * TILE - 1), "its foot at the bottom of its cell, so it sorts with the farmer")
	t.eq(node.stage, 0)
	t.ok(not node.ripe)
	field.water(leek)
	_night(field)
	t.eq(field.crop_node(leek), node, "the same node goes on")
	t.eq(node.stage, 5, "the sixth of twelve pictures after one of two days")
	field.water(leek)
	_night(field)
	t.eq(node.stage, 11, "the last picture is the ripe one")
	t.ok(node.ripe)
	_night(field, "winter")
	field.harvest(leek)
	t.ok(field.crop_node(leek) == null or field.crop_node(leek).is_queued_for_deletion(), "a harvested crop is gone from the map")
	_cleanup()

# ---------------------------------------------------------------- the data

func test_a_field_that_is_not_shown_grows_overnight(t) -> void:
	var here := _map("farm")
	var there := _map("far_field", false)
	var near: RpgField = here["field"]
	var far: RpgField = there["field"]
	for field: RpgField in [near, far]:
		field.till(CORN)
		field.plant(CORN, "corn")
		field.water(CORN)
	var saved: Dictionary = RpgUtil.state().flags[RpgField.FLAG_ENTITY]
	t.eq(saved.keys(), ["farm", "far_field"], "one key a field in the game state")
	var root: Node = there["root"]
	root.free()  # the player left that map
	RpgField.night_all(near.crops, "spring")
	var back := _map("far_field", false)
	var again: RpgField = back["field"]
	t.eq(again.grown_at(CORN), 1, "it grew while nobody looked")
	t.ok(again.crop_node(CORN) != null, "and is shown as it is when the map comes back")
	_cleanup()

func test_the_field_round_trips_through_a_save(t) -> void:
	var map := _map()
	var field: RpgField = map["field"]
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER) as RpgSaveManager
	save.dir = "user://test_field_saves_%d" % Time.get_ticks_usec()
	var bean := Vector2i(3, 2)
	var bare := Vector2i(5, 4)
	for cell: Vector2i in [CORN, bean, bare]:
		field.till(cell)
	field.plant(CORN, "corn")
	field.plant(bean, "bean")
	field.water(CORN)
	_night(field)
	_night(field, "summer")
	field.water(bean)
	var before := field.to_dict()
	t.eq(before.size(), 3)
	t.ok(save.save(1))
	var written: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(save.dir.path_join("slot_1.json")))
	t.eq(RpgUtil.to_int(written["save_version"]), 1, "the save version stays 1")
	field.remove_crop(CORN)
	field.till(Vector2i(4, 4))
	RpgUtil.state().new_game()
	field.load_state()
	t.eq(field.cells.size(), 0, "a new game has an untouched field")
	t.ok(save.load(1))
	field.load_state()
	field.refresh()
	t.eq(field.to_dict(), before, "the field is what it was")
	t.eq([field.grown_at(CORN), field.state_of(bean), field.is_watered(bean), field.state_of(bare)], [1, RpgField.WITHERED, true, RpgField.SOIL])
	t.ok(field.crop_node(CORN) != null and field.crop_node(bean).withered)
	for file: String in DirAccess.get_files_at(save.dir):
		DirAccess.remove_absolute(save.dir.path_join(file))
	DirAccess.remove_absolute(save.dir)
	Fixtures.uninstall("SaveManager")
	_cleanup()

func test_the_crops_of_the_user_come_first_and_the_planned_ones_fill_in(t) -> void:
	var data := RpgCropData.new()
	data.add_list([{"id": "corn", "days": 9, "seed": "my_seed", "produce": "my_corn", "seasons": ["winter"]}])
	data.add_list(CROPS)
	t.eq(data.order, ["corn", "bean", "leek"] as Array[String])
	t.eq(data.days("corn"), 9, "the user's entry is not replaced")
	t.eq(data.crop_of_seed(&"my_seed"), "corn")
	t.eq(data.crop_of_seed(&"seed_corn"), "")
	t.eq(data.crop_of_produce(&"crop_bean"), "bean")
	t.ok(data.grows_in("corn", "winter") and not data.grows_in("corn", "spring"))
	t.eq(data.of_season("spring"), ["bean", "leek"] as Array[String])
	t.eq(data.regrow("bean"), 2)
	t.eq(data.stages("nothing"), 1, "a crop that is not there is harmless")
	data.add_file("res://no/such/crops.json")
	t.eq(data.order.size(), 3)
