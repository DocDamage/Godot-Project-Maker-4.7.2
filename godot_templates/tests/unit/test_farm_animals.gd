extends RefCounted
## T17.07: animals. The herd as data, the trough, petting, the night and its product, where an
## animal is by the clock and the weather, buying at the shop, the price by friendship, hay
## from cut grass, the save, and the scene of an animal.

const Fixtures := preload("../lib/fixtures.gd")
const AnimalRecipes := preload("../../builder/recipes/farm/animal_recipes.gd")

const TILE := 16
const COOP_MAP := "res://test_animals/farm_coop.tscn"
const BARN_MAP := "res://test_animals/farm_barn.tscn"
const FARM_MAP := "res://test_animals/farm.tscn"
const YARD := Rect2i(4, 6, 6, 3)
const ANIMALS := {
	"animals": [
		{"id": "hen", "name": "Hen", "house": "coop", "ticket": "animal_hen", "cost": 150, "product": "egg", "product_name": "Egg", "price": 25, "large": "egg_large", "large_price": 37, "collect": "floor", "variants": [{"id": "hen_black", "colour": "black", "scene": ""}, {"id": "hen_white", "colour": "white", "scene": ""}]},
		{"id": "cow", "name": "Cow", "house": "barn", "ticket": "animal_cow", "cost": 360, "product": "milk", "product_name": "Milk", "price": 60, "large": "milk_large", "large_price": 90, "collect": "hand", "variants": [{"id": "cow_brown", "colour": "brown", "scene": ""}]},
	],
	"feed": {"item": "hay", "name": "Hay", "price": 10},
	"names": ["Dot", "Bess", "Pip"],
	"houses": [
		{"kind": "coop", "map": COOP_MAP, "yard_map": FARM_MAP, "stalls": 2},
		{"kind": "barn", "map": BARN_MAP, "yard_map": FARM_MAP, "stalls": 1},
	],
}
## Item id -> its price; the rows the shop lists the animals as are key items.
const PRICES := {&"egg": 25, &"egg_large": 37, &"milk": 60, &"milk_large": 90, &"hay": 10, &"animal_hen": 150, &"animal_cow": 360, &"hoe": 0}
const KEYS: Array[StringName] = [&"animal_hen", &"animal_cow", &"hoe"]

var _made: Array[Node] = []

func _data(table: Dictionary = ANIMALS) -> RpgAnimalData:
	var data := RpgAnimalData.new()
	data.add(table.duplicate(true))
	return data

## A farm's game with the animals of `table`: {state, mode, calendar, herd, weather}
func _game(table: Dictionary = ANIMALS) -> Dictionary:
	var registry := {}
	for id: StringName in PRICES.keys():
		var def := Fixtures.item(id)
		def.value = PRICES[id]
		if KEYS.has(id):
			def.category = RpgItemDefinition.Category.KEY
			def.max_stack = 1
		registry[id] = def
	var state := Fixtures.install_state(registry) as RpgGameState
	state.inventory.registry = state.items
	var mode := RpgFarmMode.new()
	mode.ensure_parts()
	mode.animals.data = _data(table)
	mode._ready()
	_made.append(mode)
	return {"state": state, "mode": mode, "calendar": RpgCalendar.current(), "herd": mode.animals, "weather": mode.weather}

## A map with the entities of a map, the markers of a room with `stalls` stalls, and the yard
## of a coop: what the farm's map recipe writes. Its scene file is `path`.
func _map(path: String, stalls: int = 2) -> Node2D:
	var root := Node2D.new()
	root.name = "Map"
	root.scene_file_path = path
	var ysorted := Node2D.new()
	ysorted.name = "YSorted"
	root.add_child(ysorted)
	var entities := Node2D.new()
	entities.name = "Entities"
	ysorted.add_child(entities)
	var markers := Node2D.new()
	markers.name = "Markers"
	root.add_child(markers)
	var trough := Marker2D.new()
	trough.name = "Trough"
	trough.position = Vector2(1.5, 1.5) * TILE
	markers.add_child(trough)
	for i in stalls:
		var stall := Marker2D.new()
		stall.name = "Stall%d" % (i + 1)
		stall.position = Vector2(3.5 + i, 1.5) * TILE
		markers.add_child(stall)
	var yards := Node2D.new()
	yards.name = "Yards"
	root.add_child(yards)
	var yard := Node2D.new()
	yard.name = "Coop"
	yard.position = Vector2(YARD.position) * TILE
	yard.set_meta(&"kind", "coop")
	yard.set_meta(&"yard", YARD)
	yards.add_child(yard)
	_made.append(root)
	return root

func _animals_shown(herd: RpgAnimalHouse) -> Array[RpgFarmAnimal]:
	var out: Array[RpgFarmAnimal] = []
	for node in herd.shown():
		if node is RpgFarmAnimal:
			out.append(node as RpgFarmAnimal)
	return out

func _products_shown(herd: RpgAnimalHouse) -> Array[RpgAnimalProduct]:
	var out: Array[RpgAnimalProduct] = []
	for node in herd.shown():
		if node is RpgAnimalProduct:
			out.append(node as RpgAnimalProduct)
	return out

func _trough_shown(herd: RpgAnimalHouse) -> RpgFarmTrough:
	for node in herd.shown():
		if node is RpgFarmTrough:
			return node as RpgFarmTrough
	return null

func _cleanup() -> void:
	var tree := Fixtures.tree()
	tree.paused = false
	for node in _made:
		if is_instance_valid(node):
			node.free()
	_made.clear()
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- the night

func test_a_fed_hen_lays_an_egg_overnight_and_an_unfed_one_does_not(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var herd: RpgAnimalHouse = game["herd"]
	var calendar: RpgCalendar = game["calendar"]
	var hen := herd.buy("hen")
	var cow := herd.buy("cow")
	t.eq([hen["id"], hen["name"], hen["house"], hen["fed"], hen["ready"]], [1, "Dot", "coop", false, ""])
	t.eq(RpgUtil.to_array(state.get_flag(RpgAnimalHouse.FLAG_ENTITY, RpgAnimalHouse.HERD_KEY, [])).size(), 2, "the herd is kept in the flags of the saved game")
	# feed goes into the trough of the house, a portion a day for everybody in it
	state.inventory.add(&"hay", 2)
	state.inventory.add(&"hoe", 1)
	var trough := RpgFarmTrough.make("coop", TILE)
	trough.herd = herd
	_made.append(trough)
	t.eq(trough.use_with(&"hoe"), false, "a hoe is no feed")
	t.eq(trough.use_with(&""), false, "nor is an empty hand")
	t.eq(trough.use_with(&"hay"), true)
	t.eq([state.inventory.count(&"hay"), RpgAnimalHouse.trough_full("coop"), trough.is_full()], [1, true, true], "one portion fills it")
	t.ok((trough.get_node("Feed") as CanvasItem).visible, "and it shows")
	t.eq(trough.use_with(&"hay"), false, "a full trough takes no more")
	t.eq(state.inventory.count(&"hay"), 1)
	t.eq([RpgAnimalHouse.animal(1)["fed"], RpgAnimalHouse.animal(2)["fed"]], [true, false], "the hen of the coop is fed, the cow of the barn is not")
	t.eq([RpgAnimalHouse.animal(1)["ready"], RpgAnimalHouse.animal(2)["ready"]], ["", ""], "nothing before the night")
	calendar.end_day()
	t.eq(RpgAnimalHouse.animal(1)["ready"], "egg", "a fed hen has an egg in the morning")
	t.eq(RpgAnimalHouse.animal(2)["ready"], "", "an unfed cow gives nothing")
	t.eq([RpgAnimalHouse.animal(1)["fed"], RpgAnimalHouse.trough_full("coop")], [false, false], "the trough is empty again")
	t.eq(herd.animal(RpgUtil.to_int(cow["id"]))["kind"], "cow", "and the cow is still there: animals do not die")
	# an egg that is not picked up stays one egg; a hungry night gives none
	herd.fill_trough("coop")
	calendar.end_day()
	t.eq(RpgAnimalHouse.animal(1)["ready"], "egg")
	t.eq(herd.take_product(1), &"egg")
	t.eq([state.inventory.count(&"egg"), RpgAnimalHouse.animal(1)["ready"]], [1, ""])
	calendar.end_day()
	t.eq(RpgAnimalHouse.animal(1)["ready"], "", "not fed, no egg")
	t.eq(herd.take_product(1), &"", "and nothing to take")
	_cleanup()

func test_friendship_rises_with_petting_and_falls_with_hunger(t) -> void:
	var game := _game()
	var herd: RpgAnimalHouse = game["herd"]
	var calendar: RpgCalendar = game["calendar"]
	herd.buy("hen")
	t.eq(RpgAnimalHouse.friendship(1), 0)
	t.ok(herd.pet(1))
	t.eq(RpgAnimalHouse.friendship(1), RpgAnimalHouse.PET_POINTS)
	t.eq(herd.pet(1), false, "once a day")
	t.eq(RpgAnimalHouse.friendship(1), RpgAnimalHouse.PET_POINTS)
	herd.fill_trough("coop")
	calendar.end_day()
	var fed := RpgAnimalHouse.PET_POINTS + RpgAnimalHouse.FED_POINTS
	t.eq(RpgAnimalHouse.friendship(1), fed, "a fed night adds a little")
	t.ok(herd.pet(1), "and the next day it is petted again")
	t.eq(RpgAnimalHouse.friendship(1), fed + RpgAnimalHouse.PET_POINTS)
	calendar.end_day()
	t.eq(RpgAnimalHouse.friendship(1), fed + RpgAnimalHouse.PET_POINTS + RpgAnimalHouse.HUNGRY_POINTS, "a hungry night costs friendship")
	t.ok(RpgAnimalHouse.HUNGRY_POINTS < 0)
	for night in 5:
		calendar.end_day()
	t.eq(RpgAnimalHouse.friendship(1), 0, "never below nothing")
	RpgAnimalHouse._update(1, {"friendship": RpgAnimalHouse.MAX_POINTS - 5})
	herd.pet(1)
	t.eq([RpgAnimalHouse.friendship(1), RpgAnimalHouse.hearts(1)], [RpgAnimalHouse.MAX_POINTS, RpgAnimalHouse.HEARTS], "nor above ten hearts")
	# `interact` pets, and says how things stand when it was petted already
	var said: Array[String] = []
	RpgUtil.events().notify.connect(func(text: String) -> void: said.append(text))
	calendar.end_day()
	var node := RpgFarmAnimal.new()
	node.animal_id = 1
	node.herd = herd
	_made.append(node)
	node.interact()
	t.ok(RpgUtil.to_bool(RpgAnimalHouse.animal(1)["petted"]), "`interact` with the animal pets it")
	t.eq(said, [RpgFarmStrings.t("FARM_ANIMAL_PETTED", ["Dot"])])
	node.interact()
	t.eq(said.size(), 2)
	t.ok(said[1].contains("Dot") and said[1].contains("hearts"), said[1])
	_cleanup()

# ---------------------------------------------------------------- where an animal is

func test_an_animal_is_in_its_yard_by_day_and_inside_at_night_and_in_the_rain(t) -> void:
	var game := _game()
	var herd: RpgAnimalHouse = game["herd"]
	var calendar: RpgCalendar = game["calendar"]
	var weather: RpgFarmWeather = game["weather"]
	herd.buy("hen")
	herd.buy("hen")
	var farm := _map(FARM_MAP)
	var coop := _map(COOP_MAP)
	# a fair morning: out in the yard, wandering inside it
	t.ok(herd.is_outside() and not herd.is_night())
	herd.populate(farm)
	var out := _animals_shown(herd)
	t.eq(out.size(), 2, "both hens are in the yard")
	var ground := Rect2(Vector2(YARD.position) * TILE, Vector2(YARD.size) * TILE)
	for hen in out:
		t.ok(ground.has_point(RpgUtil.world_position(hen)), "inside the fence: %s" % RpgUtil.world_position(hen))
		t.ok(hen.is_roaming() and not hen.asleep)
		t.eq(hen.get_parent(), farm.get_node("YSorted/Entities"), "among the entities of the map")
		for step in 600:
			hen.wander(0.1)
		t.ok(ground.has_point(RpgUtil.world_position(hen)), "and it stays there")
	t.ok(out[0].position != out[1].position, "each in a place of its own")
	t.eq(herd.node_of(2), out[1])
	herd.populate(coop)
	t.eq(_animals_shown(herd).size(), 0, "nobody is in the coop by day")
	t.ok(_trough_shown(herd) != null, "but its trough is")
	t.eq(_trough_shown(herd).house, "coop")
	t.ok(not is_instance_valid(out[0]) or out[0].get_parent() == null, "what the last map showed is gone")
	# the evening: in their stalls, asleep
	calendar.pass_minutes(RpgAnimalHouse.EVENING - calendar.minute)
	t.ok(herd.is_night() and not herd.is_outside(), "from 18:00 on")
	herd.populate(farm)
	t.eq(herd.shown().size(), 0, "the yard is empty at night")
	herd.populate(coop)
	var indoors := _animals_shown(herd)
	t.eq(indoors.size(), 2)
	for i in 2:
		var stall := coop.get_node("Markers/Stall%d" % (i + 1)) as Node2D
		t.ok(RpgUtil.world_position(indoors[i]).distance_to(stall.position) < TILE, "hen %d is in its stall" % (i + 1))
		t.ok(indoors[i].asleep and not indoors[i].is_roaming(), "asleep")
	# the next morning it rains: indoors, awake
	calendar.end_day()
	t.ok(herd.is_outside(), "a fair morning")
	weather.force(RpgFarmWeather.RAIN)
	t.ok(weather.keeps_animals_in() and not herd.is_outside(), "the rain keeps them in")
	herd.populate(farm)
	t.eq(herd.shown().size(), 0, "nobody is out in the rain")
	herd.populate(coop)
	t.eq(_animals_shown(herd).size(), 2)
	t.ok(not _animals_shown(herd)[0].asleep, "awake by day")
	weather.force(RpgFarmWeather.SNOW)
	t.ok(not herd.is_outside(), "nor in the snow")
	weather.force(RpgFarmWeather.SUN)
	t.ok(herd.is_outside())
	_cleanup()

func test_the_egg_lies_in_the_coop_and_the_cow_is_milked(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var herd: RpgAnimalHouse = game["herd"]
	var calendar: RpgCalendar = game["calendar"]
	herd.buy("hen")
	herd.buy("cow")
	herd.fill_trough("coop")
	herd.fill_trough("barn")
	calendar.end_day()
	var coop := _map(COOP_MAP)
	herd.populate(coop)
	t.eq(_animals_shown(herd).size(), 0, "the hen is out")
	var eggs := _products_shown(herd)
	t.eq(eggs.size(), 1, "her egg lies in the coop")
	var stall := coop.get_node("Markers/Stall1") as Node2D
	t.eq(eggs[0].position, stall.position + Vector2(0, TILE), "a cell below her stall")
	t.eq([eggs[0].item_id, eggs[0].animal_id], [&"egg", 1])
	var hen := RpgFarmAnimal.new()
	hen.animal_id = 1
	hen.herd = herd
	_made.append(hen)
	hen.interact()
	t.eq([state.inventory.count(&"egg"), RpgAnimalHouse.animal(1)["ready"]], [0, "egg"], "petting the hen does not take the egg")
	eggs[0].interact()
	t.eq([state.inventory.count(&"egg"), RpgAnimalHouse.animal(1)["ready"]], [1, ""], "`interact` picks it up")
	t.eq(_products_shown(herd).size(), 0)
	herd.populate(coop)
	t.eq(_products_shown(herd).size(), 0, "and it does not lie there again")
	# the cow: `interact` with her takes the milk, and pets her
	herd.populate(_map(BARN_MAP, 1))
	t.eq(_products_shown(herd).size(), 0, "milk does not lie on the floor")
	var cow := RpgFarmAnimal.new()
	cow.animal_id = 2
	cow.herd = herd
	_made.append(cow)
	cow.interact()
	t.eq([state.inventory.count(&"milk"), RpgAnimalHouse.animal(2)["ready"], RpgAnimalHouse.animal(2)["petted"]], [1, "", true])
	cow.interact()
	t.eq(state.inventory.count(&"milk"), 1, "once")
	_cleanup()

# ---------------------------------------------------------------- the shop

func test_buying_needs_room_in_the_house(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var herd: RpgAnimalHouse = game["herd"]
	var shop := RpgFarmShop.new()
	shop.seasonal = false
	state.gold = 1000
	t.eq([herd.room_in("coop"), herd.room_in("barn"), herd.room_in("stable")], [2, 1, 0])
	var offered := shop.offered(state.items)
	for wanted: StringName in [&"hay", &"animal_hen", &"animal_cow"]:
		t.ok(offered.has(wanted), "the shop offers %s" % wanted)
	t.eq([shop.buy_price(&"animal_hen", state.items), shop.buy_price(&"hay", state.items)], [150, 10])
	t.eq(shop.buy(state, &"animal_hen"), RpgShopDefinition.OK)
	t.eq([state.gold, state.inventory.count(&"animal_hen"), RpgAnimalHouse.herd().size()], [850, 0, 1], "paid for, in the coop, and not in the bag")
	t.eq(shop.buy(state, &"animal_hen"), RpgShopDefinition.OK)
	var hens := RpgAnimalHouse.of_house("coop")
	t.eq([hens[0]["name"], hens[1]["name"]], ["Dot", "Bess"], "named in turn")
	t.eq([hens[0]["variant"], hens[1]["variant"]], [0, 1], "a colour in turn")
	t.eq([hens[0]["stall"], hens[1]["stall"]], [0, 1], "each in a stall")
	t.eq(herd.room_in("coop"), 0)
	# the coop is full: no row, and no sale
	t.ok(not shop.offered(state.items).has(&"animal_hen"), "a full house sells no more")
	t.ok(shop.offered(state.items).has(&"animal_cow"), "the barn has room")
	t.eq(shop.buy(state, &"animal_hen"), RpgShopDefinition.NOT_FOR_SALE)
	t.eq(herd.deliver(&"animal_hen", 1), RpgShopDefinition.NO_ROOM)
	t.eq(herd.buy("hen"), {}, "nor does it move in by itself")
	t.eq([state.gold, RpgAnimalHouse.herd().size()], [700, 2])
	state.gold = 100
	t.eq(shop.buy(state, &"animal_cow"), RpgShopDefinition.NOT_ENOUGH_GOLD)
	t.eq([state.gold, herd.room_in("barn")], [100, 1], "nothing is paid for what did not come")
	state.gold = 400
	t.eq(shop.buy(state, &"animal_cow"), RpgShopDefinition.OK)
	t.eq([state.gold, RpgAnimalHouse.animal(3)["name"], RpgAnimalHouse.animal(3)["house"]], [40, "Pip", "barn"])
	t.eq(herd.name_for(3), "Dot 2", "a second round of the names is numbered")
	# feed is a thing for the bag, like any other
	t.eq(shop.buy(state, &"hay", 3), RpgShopDefinition.OK)
	t.eq([state.gold, state.inventory.count(&"hay")], [10, 3])
	_cleanup()

func test_friendship_raises_the_price_of_the_product(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var herd: RpgAnimalHouse = game["herd"]
	var calendar: RpgCalendar = game["calendar"]
	herd.buy("hen")
	var friend := RpgAnimalHouse.LARGE_HEARTS * RpgAnimalHouse.HEART_POINTS
	t.eq([herd.product_for("hen", 0), herd.product_for("hen", friend - 1), herd.product_for("hen", friend)], [&"egg", &"egg", &"egg_large"])
	t.eq([herd.product_price("hen", 0), herd.product_price("hen", friend), herd.product_price("cow", friend)], [25, 37, 90])
	herd.fill_trough("coop")
	calendar.end_day()
	t.eq(herd.take_product(1), &"egg", "a stranger's egg")
	RpgAnimalHouse._update(1, {"friendship": friend})
	herd.fill_trough("coop")
	calendar.end_day()
	t.eq(herd.take_product(1), &"egg_large", "a friend's egg is a large one")
	# the bin pays each at its own price
	state.gold = 0
	t.eq([RpgShippingBin.put(&"egg", 1), RpgShippingBin.put(&"egg_large", 1)], [1, 1])
	t.eq(RpgShippingBin.put(&"animal_hen", 1), 0, "the row of the shop is nothing to sell")
	calendar.end_day()
	t.eq(state.gold, 25 + 37)
	_cleanup()

# ---------------------------------------------------------------- hay

func test_cut_grass_gives_hay_in_a_farm_that_keeps_animals(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var herd: RpgAnimalHouse = game["herd"]
	var root := Node2D.new()
	_made.append(root)
	var ysorted := Node2D.new()
	ysorted.name = "YSorted"
	root.add_child(ysorted)
	var entities := Node2D.new()
	entities.name = "Entities"
	ysorted.add_child(entities)
	var field := RpgField.new()
	field.name = "Field"
	field.crops = RpgCropData.new()
	root.add_child(field)
	for entry: Array in [["grass", Vector2i(2, 2)], ["stump", Vector2i(3, 2)]]:
		var thing := Node2D.new()
		var cell: Vector2i = entry[1]
		thing.set_meta(RpgField.CLEAR_META, entry[0])
		thing.position = (Vector2(cell) + Vector2(0.5, 0.5)) * TILE
		entities.add_child(thing)
	var cleared: Array = []
	field.cleared.connect(func(cell: Vector2i, what: String) -> void: cleared.append([cell, what]))
	herd.watch_field(field)
	var grass: Array[String] = ["grass"]
	var stump: Array[String] = ["stump"]
	t.ok(field.clear_obstacle(Vector2i(2, 2), grass))
	t.eq(cleared, [[Vector2i(2, 2), "grass"]], "the field says what was cleared")
	t.eq(state.inventory.count(&"hay"), RpgAnimalHouse.HAY_PER_GRASS, "cut grass is hay")
	t.ok(field.clear_obstacle(Vector2i(3, 2), stump))
	t.eq(state.inventory.count(&"hay"), RpgAnimalHouse.HAY_PER_GRASS, "a stump is not")
	_cleanup()
	# a farm without an animal house: its grass is grass
	var plain := _game({})
	var none: RpgAnimalHouse = plain["herd"]
	var other := RpgField.new()
	_made.append(other)
	none.watch_field(other)
	other.cleared.emit(Vector2i.ZERO, "grass")
	t.eq((plain["state"] as RpgGameState).inventory.count(&"hay"), 0)
	_cleanup()

# ---------------------------------------------------------------- no animals

func test_a_farm_without_an_animal_house_has_nothing_of_this(t) -> void:
	var before := RpgFarmShop.stock_sources.size()
	var game := _game({})
	var state: RpgGameState = game["state"]
	var herd: RpgAnimalHouse = game["herd"]
	var calendar: RpgCalendar = game["calendar"]
	t.ok(herd.data.is_empty())
	t.eq(RpgFarmShop.stock_sources.size(), before, "it offers the shop nothing")
	t.eq(herd.shop_rows("spring"), [])
	var shop := RpgFarmShop.new()
	shop.seasonal = false
	t.eq(shop.offered(state.items).size(), 0)
	t.eq([herd.can_buy("hen"), herd.buy("hen"), RpgAnimalHouse.herd().size()], [false, {}, 0])
	calendar.end_day()
	t.ok(not state.flags.has(RpgAnimalHouse.FLAG_ENTITY), "and a night writes nothing of it into the game")
	herd.populate(_map(COOP_MAP))
	t.eq(herd.shown().size(), 0, "nor does a map get a trough")
	_cleanup()
	# the files of a farm that has none are not there, and that is an empty table
	t.ok(RpgAnimalData.load_default().is_empty())

# ---------------------------------------------------------------- the save

func test_the_herd_round_trips_through_a_save(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var herd: RpgAnimalHouse = game["herd"]
	var calendar: RpgCalendar = game["calendar"]
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER) as RpgSaveManager
	save.dir = "user://test_farm_animals_%d" % Time.get_ticks_usec()
	herd.buy("hen")
	herd.buy("cow")
	herd.buy("hen")
	herd.fill_trough("coop")
	calendar.end_day()
	herd.pet(1)
	herd.fill_trough("barn")
	var before := RpgAnimalHouse.herd()
	t.eq(before.size(), 3)
	t.eq([before[0]["ready"], before[0]["petted"], before[1]["fed"], before[2]["ready"], before[2]["variant"]], ["egg", true, true, "egg", 1])
	t.ok(save.save(1))
	var written: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(save.dir.path_join("slot_1.json")))
	t.eq(RpgUtil.to_int(written["save_version"]), 1, "the save version stays 1")
	herd.take_product(1)
	state.new_game()
	t.eq(RpgAnimalHouse.herd().size(), 0, "a new game has no animals")
	t.eq(herd.room_in("coop"), 2)
	t.ok(save.load(1))
	t.eq(RpgAnimalHouse.herd(), before, "the herd is what it was")
	t.eq([RpgAnimalHouse.trough_full("barn"), RpgAnimalHouse.trough_full("coop")], [true, false], "and so are the troughs")
	t.eq(herd.room_in("coop"), 0)
	t.eq(herd.buy("cow"), {}, "the barn is as full as it was")
	herd.populate(_map(COOP_MAP))
	t.eq(_products_shown(herd).size(), 2, "the eggs of the saved morning lie in the coop")
	for file: String in DirAccess.get_files_at(save.dir):
		DirAccess.remove_absolute(save.dir.path_join(file))
	DirAccess.remove_absolute(save.dir)
	Fixtures.uninstall("SaveManager")
	_cleanup()

# ---------------------------------------------------------------- the scene and the data

static func _frames(names: Array[String]) -> SpriteFrames:
	var frames := SpriteFrames.new()
	frames.remove_animation(&"default")
	var texture := ImageTexture.create_from_image(Image.create_empty(TILE, TILE, false, Image.FORMAT_RGBA8))
	for anim in names:
		frames.add_animation(anim)
		frames.add_frame(anim, texture)
	return frames

func test_the_scene_of_an_animal_sleeps_in_its_sleep_animation(t) -> void:
	var walk_only: Array[String] = ["walk_down"]
	var with_sleep: Array[String] = ["walk_down", "sleep_down"]
	var hen := AnimalRecipes.build_animal("hen", _frames(with_sleep), Vector2i(TILE, TILE), Vector2i(8, 15), TILE) as RpgFarmAnimal
	_made.append(hen)
	t.ok(hen != null, "the recipe builds an RpgFarmAnimal")
	t.eq(hen.kind, "hen")
	t.ok(hen.get_collision_layer_value(5) and not hen.get_collision_layer_value(4) and not hen.get_collision_layer_value(1), "on the layer of the interactables alone: `interact` finds it, the farmer walks through")
	t.ok(hen.get_collision_mask_value(1), "and a fence holds it")
	t.eq((hen.get_node("Components/Movement") as RpgMovement).speed, TILE * AnimalRecipes.SPEED_TILES, "it walks slowly")
	t.eq((hen.get_node("Visual") as AnimatedSprite2D).animation, &"walk_down", "a sheet without an idle shows its walk")
	hen._ready()
	t.ok(hen.has_sleep())
	t.ok(not hen.animation_locked)
	hen.sleep()
	t.ok(hen.asleep and hen.animation_locked)
	t.eq((hen.get_node("Visual") as AnimatedSprite2D).animation, &"sleep_down", "asleep in the animation of its sheet")
	var plain := AnimalRecipes.build_animal("hen", _frames(walk_only), Vector2i(TILE, TILE), Vector2i(8, 15), TILE) as RpgFarmAnimal
	_made.append(plain)
	plain._ready()
	plain.sleep()
	t.ok(plain.asleep and not plain.has_sleep() and not plain.animation_locked, "a sheet without one stands still")
	plain.roam(Rect2(0, 0, 64, 64))
	t.ok(not plain.is_roaming(), "and a sleeper does not wander")
	for node in _made:
		node.free()
	_made.clear()

func test_the_data_of_the_animals(t) -> void:
	var data := _data()
	t.eq([data.order, data.house_order], [["hen", "cow"], ["coop", "barn"]])
	t.eq([data.house_of("hen"), data.house_of("cow"), data.house_of("cat")], ["coop", "barn", ""])
	t.eq([data.stalls("coop"), data.stalls("barn"), data.stalls("stable")], [2, 1, 0])
	t.eq([data.kinds_of("coop"), data.kinds_of("barn")], [["hen"], ["cow"]])
	t.eq([data.kind_of_ticket(&"animal_cow"), data.kind_of_ticket(&"hay")], ["cow", ""])
	t.eq([data.on_the_floor("hen"), data.on_the_floor("cow")], [true, false])
	t.eq([data.product("hen"), data.product("hen", true), data.feed_item, data.feed_price], [&"egg", &"egg_large", &"hay", 10])
	t.eq(data.variants("hen").size(), 2)
	t.eq(data.names, ["Dot", "Bess", "Pip"])
	# the user's file first: what a later table has of the same id does not count
	data.add({"animals": [{"id": "hen", "house": "barn"}, {"id": "duck", "house": "coop", "variants": [{"id": "duck", "scene": "res://duck.tscn"}]}], "houses": [{"kind": "coop", "stalls": 9}], "feed": {"item": "grain", "price": 1}, "names": ["X"]})
	t.eq([data.house_of("hen"), data.stalls("coop"), data.feed_item, data.names.size()], ["coop", 2, &"hay", 3])
	t.eq([data.order, data.scene_of("duck", 0), data.scene_of("duck", 5), data.scene_of("cat", 0)], [["hen", "cow", "duck"], "res://duck.tscn", "res://duck.tscn", ""])
