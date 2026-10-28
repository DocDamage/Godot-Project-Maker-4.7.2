extends RefCounted
## Crafting on a farm (T18.15): wood and stone from clearing, placing what the workbench made with
## `use`, a sprinkler that waters round it in the morning, a chest that keeps things, a preserves
## jar, and a farm that does not craft.

const Fixtures := preload("../lib/fixtures.gd")
const CraftingRecipe := preload("res://builder/recipes/crafting_recipe.gd")

const CROPS := [
	{"id": "corn", "name": "Corn", "seed": "seed_corn", "produce": "crop_corn", "seasons": ["spring", "summer"], "days": 3, "stages": 4, "regrow": 0, "seed_price": 15, "price": 30, "energy": 14},
]

var _made: Array[Node] = []

## A farm's game with the workshop on (or off) and a farmer on the map of test_farmer.gd, standing
## at (3, 1) looking down at (3, 2). {state, mode, farmer, field, map}
func _farm(crafting: bool = true) -> Dictionary:
	var registry := {}
	for id: String in CraftingRecipe.FARM_ITEMS:
		registry[StringName(id)] = CraftingRecipe.farm_item(id)
	for id: StringName in [&"hoe", &"farm_axe", &"crop_corn"]:
		registry[id] = Fixtures.item(id)
	var state := Fixtures.install_state(registry) as RpgGameState
	state.inventory.registry = state.items
	var mode := RpgFarmMode.new()
	var crops := RpgCropData.new()
	crops.add_list(CROPS)
	mode.crops = crops
	mode.crafting = crafting
	mode._ready()
	_made.append(mode)
	var builder: RefCounted = (load("res://tests/unit/test_farmer.gd") as GDScript).new()
	var map: Dictionary = builder.call("_map")
	_made.append(map["root"])
	(map["root"] as Node2D).name = "Farm"
	var farmer := RpgFarmer.new()
	farmer.name = "Player"
	farmer.mode = mode
	farmer.field = map["field"]
	(map["entities"] as Node2D).add_child(farmer)
	farmer.position = (Vector2(3, 1) + Vector2(0.5, 0.5)) * 16.0
	farmer.facing = "down"
	Fixtures.tree().root.add_child(map["root"])
	mode.workshop.watch_field(map["field"])
	return {"state": state, "mode": mode, "farmer": farmer, "field": map["field"], "map": map}

func _use(farmer: RpgFarmer) -> bool:
	var done := farmer.use_held()
	farmer._end_use()
	return done

func _cleanup() -> void:
	for node in _made:
		if is_instance_valid(node):
			if node.is_inside_tree():
				node.get_parent().remove_child(node)
			node.free()
	_made.clear()
	Fixtures.uninstall_state()

func test_clearing_gives_wood_and_stone(t) -> void:
	var farm := _farm()
	var state: RpgGameState = farm["state"]
	var field: RpgField = farm["field"]
	field.cleared.emit(Vector2i(1, 1), "stump")
	field.cleared.emit(Vector2i(1, 1), "branch")
	field.cleared.emit(Vector2i(1, 1), "rock")
	field.cleared.emit(Vector2i(1, 1), "grass")
	t.eq([state.inventory.count(&"wood"), state.inventory.count(&"stone")], [3, 1], "a stump 2, a branch 1, a rock 1, grass none")
	t.ok(RpgFarmAxe.new().clears.has("rock"), "the axe breaks a rock that carries the mark")
	_cleanup()

func test_a_sprinkler_is_placed_with_use_and_waters_round_it_in_the_morning(t) -> void:
	var farm := _farm()
	var state: RpgGameState = farm["state"]
	var mode: RpgFarmMode = farm["mode"]
	var field: RpgField = farm["field"]
	var farmer: RpgFarmer = farm["farmer"]
	for cell: Vector2i in [Vector2i(2, 2), Vector2i(4, 2), Vector2i(3, 3), Vector2i(3, 4)]:
		field.till(cell)
	state.inventory.add(&"sprinkler")
	mode.hotbar.hold_item(&"sprinkler")
	field.till(Vector2i(3, 2))
	t.ok(not _use(farmer), "not on tilled soil")
	field.cells.erase(Vector2i(3, 2))
	field.store()
	t.ok(_use(farmer), "put on the tile ahead")
	t.eq(state.inventory.count(&"sprinkler"), 0)
	var row := RpgFarmWorkshop.thing_at("farm", Vector2i(3, 2))
	t.eq(row["kind"], "sprinkler")
	var shown := (farm["map"]["entities"] as Node2D).get_node_or_null("Placed_%d" % RpgUtil.to_int(row["id"]))
	t.ok(shown != null, "it stands on the map")
	t.ok(not field.is_watered(Vector2i(2, 2)))
	RpgCalendar.current().end_day()
	field.load_state()
	for cell: Vector2i in [Vector2i(2, 2), Vector2i(4, 2), Vector2i(3, 3), Vector2i(3, 4)]:
		t.eq(field.is_watered(cell), _beside(cell), "%s in the morning" % cell)
	_cleanup()

static func _beside(cell: Vector2i) -> bool:
	return absi(cell.x - 3) + absi(cell.y - 2) == 1

func test_a_chest_keeps_what_is_put_in_and_a_jar_makes_preserves(t) -> void:
	var farm := _farm()
	var state: RpgGameState = farm["state"]
	var mode: RpgFarmMode = farm["mode"]
	var workshop := mode.workshop
	state.inventory.add(&"chest")
	t.ok(workshop.place(&"chest", Vector2i(6, 1), farm["field"], farm["map"]["root"]))
	var chest := RpgUtil.to_int(RpgFarmWorkshop.thing_at("farm", Vector2i(6, 1))["id"])
	state.inventory.add(&"wood", 5)
	mode.hotbar.hold_item(&"wood")
	t.ok(workshop.use_thing(chest))
	t.eq(state.inventory.count(&"wood"), 0, "put in")
	mode.hotbar.hold_item(&"hoe")
	t.ok(workshop.use_thing(chest))
	t.eq(state.inventory.count(&"wood"), 5, "taken out")
	state.inventory.add(&"preserves_jar")
	t.ok(workshop.place(&"preserves_jar", Vector2i(7, 1), farm["field"], farm["map"]["root"]))
	var jar := RpgUtil.to_int(RpgFarmWorkshop.thing_at("farm", Vector2i(7, 1))["id"])
	state.inventory.add(&"crop_corn")
	mode.hotbar.hold_item(&"crop_corn")
	t.ok(workshop.use_thing(jar), "a crop goes in")
	t.ok(not workshop.use_thing(jar), "it works through the day")
	RpgCalendar.current().end_day()
	t.ok(workshop.use_thing(jar))
	t.eq(state.inventory.count(&"preserves"), 1)
	t.ok(state.items[&"preserves"].value > 30, "worth more than the corn")
	_cleanup()

func test_a_farm_that_does_not_craft_has_nothing_of_it(t) -> void:
	var farm := _farm(false)
	var state: RpgGameState = farm["state"]
	var field: RpgField = farm["field"]
	field.cleared.emit(Vector2i(1, 1), "stump")
	t.eq(state.inventory.count(&"wood"), 0)
	state.inventory.add(&"sprinkler")
	(farm["mode"] as RpgFarmMode).hotbar.hold_item(&"sprinkler")
	t.ok(not (farm["mode"] as RpgFarmMode).workshop.place(&"sprinkler", Vector2i(3, 2)))
	_cleanup()

func test_the_workbenchs_recipes(t) -> void:
	for recipe_id: String in CraftingRecipe.FARM_RECIPES:
		var made := CraftingRecipe.farm_recipe(recipe_id) as RpgRecipe
		t.eq(made.problems(), [] as Array[String], recipe_id)
		t.eq(made.station, &"workbench")
		for item_id in made.items():
			t.ok(CraftingRecipe.FARM_ITEMS.has(item_id), "%s names %s" % [recipe_id, item_id])
