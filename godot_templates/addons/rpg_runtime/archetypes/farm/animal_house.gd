class_name RpgAnimalHouse
extends Node
## The animal houses of a farm and the animals that live in them (T17.07). A child of the
## farm's mode (`Animals`), made by it like the weather and the end of the day. In a farm
## without an animal house (`RpgAnimalData.is_empty()`) it does nothing at all.
##
## * **The herd is data.** Every animal of the game is a row in the flags of the game state
##   (`farm_animals.herd`): `{id, kind, name, house, stall, variant, friendship, fed, petted,
##   ready}`. So it is saved with the game, the save has no new key, and the night works on the
##   animals whether or not their map is shown (the static functions need no node). The trough
##   of a house is `farm_animals.trough` (house -> full).
## * **Where an animal is**: out in the yard of its house from 6:00 to EVENING in fair weather
##   (`RpgFarmWeather.keeps_animals_in()`), in its stall in the house at night and on a day of
##   rain, storm or snow. Nothing walks from one to the other: when a map is entered, and when
##   the hour or the weather changes the place, the animals that are on the map that is shown
##   are made from the data (`populate`), as RpgFarmAnimal scenes among the entities of the map.
##   With them come the trough of the room (RpgFarmTrough, at `Markers/Trough`) and what lies
##   there (RpgAnimalProduct).
## * **Feed**: one portion of the feed (`animals.json`, `feed.item`: hay) in the trough of a
##   house feeds **every animal of that house for the day** (`fill_trough`). The feed is sold at
##   the shop, and cut grass gives HAY_PER_GRASS of it (the field's `cleared`).
## * **Petting**: once a day, PET_POINTS of friendship (`pet`).
## * **The night** (the calendar's `on_night`, NIGHT_ANIMALS): a fed animal that holds no
##   product has one in the morning and gains FED_POINTS; one that was not fed gives nothing and
##   loses HUNGRY_POINTS. The troughs are empty again and nobody is petted. Animals do not die.
## * **The product**: of a kind whose `collect` is `floor` it lies beside the animal's stall and
##   is picked up; of any other, `interact` with the animal takes it. From LARGE_HEARTS hearts on
##   it is the kind's `large` product, an item of its own with a higher price: a stack of the
##   inventory carries nothing but its item and its count, so the quality is an item.
## * **Buying**: the farm's shop lists the feed and, while its house has room, one row for each
##   kind (`shop_rows`, a stock source of RpgFarmShop). The row is the kind's `ticket` item; it
##   never reaches the bag: the row's `deliver` puts the animal into its house (`buy`). It gets
##   the next name of the list and the next picture of its kind, both in turn.

## An animal was bought, fed, petted or relieved of its product, or a night passed.
signal changed

const NODE_NAME := "Animals"
const FLAG_ENTITY := "farm_animals"
const HERD_KEY := "herd"
const TROUGH_KEY := "trough"
## How many animals the game has bought (the next id and name), and `bought_<kind>` of a kind
## (the next picture).
const BOUGHT_KEY := "bought"
const HEARTS := 10
const HEART_POINTS := 100
const MAX_POINTS := HEARTS * HEART_POINTS
const PET_POINTS := 15
const FED_POINTS := 5
const HUNGRY_POINTS := -20
## From this many hearts on an animal gives the `large` product of its kind.
const LARGE_HEARTS := 5
## From this minute of the day on the animals are in their houses, asleep (18:00).
const EVENING := 18 * 60
const HAY_PER_GRASS := 1
const YARDS := "Yards"
const MARKERS := "Markers"
const ENTITIES := "YSorted/Entities"

## The kinds, the houses and the feed of the game; read from the files when nobody gave them.
var data: RpgAnimalData = null

## What `populate` made. Untyped: a map that was left has freed its nodes, and a freed node is
## asked `is_instance_valid` before it is anything else.
var _shown: Array = []
var _field: RpgField = null
var _outside := true

# ------------------------------------------------------------------ finding it

## The animal houses of the running game, or null in a game that is no farm.
static func current() -> RpgAnimalHouse:
	var mode := RpgFarmMode.current()
	return mode.animals if mode != null else null

## Reads the animals of the game, and listens to the calendar, the maps, the weather and the
## saves and offers its rows to the shop. The mode calls it once the calendar and the weather
## exist; a second call changes nothing. A farm without an animal house listens to nothing.
func attach() -> void:
	if data == null:
		data = RpgAnimalData.load_default()
	if data.is_empty():
		return
	var calendar := RpgCalendar.current()
	if calendar != null:
		calendar.on_night(RpgCalendar.NIGHT_ANIMALS, _on_night)
		if not calendar.day_began.is_connected(_on_morning):
			calendar.day_began.connect(_on_morning)
		if not calendar.hour_passed.is_connected(_on_hour):
			calendar.hour_passed.connect(_on_hour)
	var bus := RpgUtil.events()
	if bus != null:
		if not bus.map_entered.is_connected(_on_map):
			bus.map_entered.connect(_on_map)
		if not bus.game_loaded.is_connected(_on_loaded):
			bus.game_loaded.connect(_on_loaded)
	var weather := _weather()
	if weather != null and not weather.changed.is_connected(_on_weather):
		weather.changed.connect(_on_weather)
	RpgFarmShop.add_stock_source(shop_rows)
	_outside = is_outside()

func _exit_tree() -> void:
	RpgFarmShop.remove_stock_source(shop_rows)

func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE:
		RpgFarmShop.remove_stock_source(shop_rows)

func _weather() -> RpgFarmWeather:
	var mode := get_parent() as RpgFarmMode
	return mode.weather if mode != null else RpgFarmWeather.current()

# ------------------------------------------------------------------ the herd (no node needed)

static func _row(raw: Variant) -> Dictionary:
	var entry := RpgUtil.to_dict(raw)
	return {
		"id": RpgUtil.to_int(entry.get("id", 0)),
		"kind": RpgUtil.to_str(entry.get("kind", "")),
		"name": RpgUtil.to_str(entry.get("name", "")),
		"house": RpgUtil.to_str(entry.get("house", "")),
		"stall": RpgUtil.to_int(entry.get("stall", 0)),
		"variant": RpgUtil.to_int(entry.get("variant", 0)),
		"friendship": clampi(RpgUtil.to_int(entry.get("friendship", 0)), 0, MAX_POINTS),
		"fed": RpgUtil.to_bool(entry.get("fed", false)),
		"petted": RpgUtil.to_bool(entry.get("petted", false)),
		"ready": RpgUtil.to_str(entry.get("ready", "")),
	}

## Every animal of the game, in the order they were bought.
static func herd() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var state := RpgUtil.state()
	if state == null:
		return out
	for raw: Variant in RpgUtil.to_array(state.get_flag(FLAG_ENTITY, HERD_KEY, [])):
		var row := _row(raw)
		if RpgUtil.to_int(row["id"]) > 0 and row["kind"] != "":
			out.append(row)
	return out

static func _store(rows: Array[Dictionary]) -> void:
	var state := RpgUtil.state()
	if state != null:
		var plain: Array = []
		plain.assign(rows)
		state.set_flag(FLAG_ENTITY, HERD_KEY, plain)

## The row of an animal, or {}.
static func animal(id: int) -> Dictionary:
	for row in herd():
		if RpgUtil.to_int(row["id"]) == id:
			return row
	return {}

## The animals that live in a house, by their stalls.
static func of_house(house_id: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for row in herd():
		if row["house"] == house_id:
			out.append(row)
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return RpgUtil.to_int(a["stall"]) < RpgUtil.to_int(b["stall"]))
	return out

## Writes `changes` into the row of an animal. False for an animal the game does not have.
static func _update(id: int, changes: Dictionary) -> bool:
	var rows := herd()
	for row in rows:
		if RpgUtil.to_int(row["id"]) == id:
			row.merge(changes, true)
			_store(rows)
			return true
	return false

## The hearts of this many points of friendship (0 to HEARTS).
static func hearts_of(points: int) -> int:
	return clampi(points, 0, MAX_POINTS) / HEART_POINTS

static func friendship(id: int) -> int:
	return RpgUtil.to_int(animal(id).get("friendship", 0))

static func hearts(id: int) -> int:
	return hearts_of(friendship(id))

## True when the trough of a house was filled today.
static func trough_full(house_id: String) -> bool:
	var state := RpgUtil.state()
	return state != null and RpgUtil.to_bool(RpgUtil.to_dict(state.get_flag(FLAG_ENTITY, TROUGH_KEY, {})).get(house_id, false))

static func _set_trough(house_id: String, full: bool) -> void:
	var state := RpgUtil.state()
	if state == null:
		return
	var troughs := RpgUtil.to_dict(state.get_flag(FLAG_ENTITY, TROUGH_KEY, {})).duplicate()
	troughs[house_id] = full
	state.set_flag(FLAG_ENTITY, TROUGH_KEY, troughs)

# ------------------------------------------------------------------ buying

## How many more animals a house has room for.
func room_in(house_id: String) -> int:
	return maxi(0, data.stalls(house_id) - of_house(house_id).size()) if data != null else 0

## True while an animal of this kind can be bought: the game has the kind, a picture of it and
## its house, and the house has a free stall.
func can_buy(kind_id: String) -> bool:
	return data != null and data.has(kind_id) and room_in(data.house_of(kind_id)) > 0

## What an animal is called that is the `count`-th the game buys: the names of the list in
## turn, with a number from the second round on.
func name_for(count: int) -> String:
	if data == null or data.names.is_empty():
		return "%s %d" % [RpgFarmStrings.t("FARM_ANIMAL"), count + 1]
	var size := data.names.size()
	var base := data.names[count % size]
	return base if count < size else "%s %d" % [base, count / size + 1]

## Puts a new animal of a kind into the first free stall of its house: named in turn, with the
## next picture of its kind, and fed when the trough of the house is full today. Returns its
## row, or {} when the house has no room. Money is the shop's business, not this function's.
func buy(kind_id: String) -> Dictionary:
	var state := RpgUtil.state()
	if state == null or not can_buy(kind_id):
		return {}
	var house_id := data.house_of(kind_id)
	var taken := {}
	for row in of_house(house_id):
		taken[RpgUtil.to_int(row["stall"])] = true
	var stall := 0
	while taken.has(stall):
		stall += 1
	var count := RpgUtil.to_int(state.get_flag(FLAG_ENTITY, BOUGHT_KEY, 0))
	var of_kind := RpgUtil.to_int(state.get_flag(FLAG_ENTITY, BOUGHT_KEY + "_" + kind_id, 0))
	var made := {
		"id": count + 1,
		"kind": kind_id,
		"name": name_for(count),
		"house": house_id,
		"stall": stall,
		"variant": of_kind,
		"friendship": 0,
		"fed": trough_full(house_id),
		"petted": false,
		"ready": "",
	}
	var rows := herd()
	rows.append(made)
	_store(rows)
	state.set_flag(FLAG_ENTITY, BOUGHT_KEY, count + 1)
	state.set_flag(FLAG_ENTITY, BOUGHT_KEY + "_" + kind_id, of_kind + 1)
	RpgUtil.notify(RpgFarmStrings.t("FARM_ANIMAL_BOUGHT", [made["name"], RpgFarmStrings.t("FARM_HOUSE_" + house_id.to_upper())]))
	changed.emit()
	populate()
	return made

## The rows the farm's shop lists for the animals (a stock source of RpgFarmShop): the feed,
## and every kind whose house has room. A kind's row names `deliver`, so buying it puts an
## animal into the house and nothing into the bag.
func shop_rows(_season_name: String = "") -> Array:
	var rows: Array = []
	if data == null or data.is_empty():
		return rows
	if data.feed_item != &"":
		rows.append({"item_id": String(data.feed_item), "price": data.feed_price})
	for kind_id in data.order:
		var ticket := RpgUtil.to_str(data.kind(kind_id).get("ticket", ""))
		if ticket != "" and can_buy(kind_id):
			rows.append({"item_id": ticket, "price": RpgUtil.to_int(data.kind(kind_id).get("cost", -1), -1), "deliver": deliver})
	return rows

## What a row of the shop calls when it is bought (RpgFarmShop.buy): `qty` animals of the kind
## the item stands for move in. Returns "" or why not (the codes of RpgShopDefinition).
func deliver(item_id: StringName, qty: int = 1) -> String:
	var kind_id := data.kind_of_ticket(item_id) if data != null else ""
	if kind_id == "" or qty <= 0:
		return RpgShopDefinition.NOT_FOR_SALE
	if room_in(data.house_of(kind_id)) < qty:
		return RpgShopDefinition.NO_ROOM
	for i in qty:
		buy(kind_id)
	return RpgShopDefinition.OK

# ------------------------------------------------------------------ care

## Fills the trough of a house: every animal of it is fed for the day. False when it is full
## already or nobody lives there.
func fill_trough(house_id: String) -> bool:
	var rows := herd()
	var anybody := false
	for row in rows:
		if row["house"] == house_id:
			row["fed"] = true
			anybody = true
	if not anybody or trough_full(house_id):
		return false
	_store(rows)
	_set_trough(house_id, true)
	changed.emit()
	return true

## What `interact` with the trough of a house does while `item_id` is held: one portion of the
## feed goes in. False, with a line that says why, when nothing went in.
func feed_with(house_id: String, item_id: StringName) -> bool:
	var state := RpgUtil.state()
	if state == null or data == null:
		return false
	if of_house(house_id).is_empty():
		RpgUtil.notify(RpgFarmStrings.t("FARM_TROUGH_NOBODY"))
		return false
	if trough_full(house_id):
		RpgUtil.notify(RpgFarmStrings.t("FARM_TROUGH_FULL"))
		return false
	if item_id == &"" or item_id != data.feed_item or not state.inventory.has(item_id):
		RpgUtil.notify(RpgFarmStrings.t("FARM_TROUGH_EMPTY", [RpgFarmStrings.item_name(data.feed_item)]))
		return false
	state.inventory.remove(item_id, 1)
	fill_trough(house_id)
	RpgUtil.notify(RpgFarmStrings.t("FARM_TROUGH_FILLED", [RpgFarmStrings.t("FARM_HOUSE_" + house_id.to_upper())]))
	return true

## Pets an animal: PET_POINTS of friendship, once a day. False when it was petted already.
func pet(id: int) -> bool:
	var row := animal(id)
	if row.is_empty() or RpgUtil.to_bool(row["petted"]):
		return false
	_update(id, {"petted": true, "friendship": mini(MAX_POINTS, RpgUtil.to_int(row["friendship"]) + PET_POINTS)})
	changed.emit()
	return true

## Takes what an animal has ready into the inventory. Returns the item, or &"" when it has
## nothing ready or the bag has no room (the product then stays).
func take_product(id: int) -> StringName:
	var row := animal(id)
	var state := RpgUtil.state()
	var item := StringName(RpgUtil.to_str(row.get("ready", "")))
	if state == null or item == &"":
		return &""
	if not state.items.has(item) or state.inventory.room_for(item) < 1:
		RpgUtil.notify(RpgFarmStrings.t("FARM_FULL"))
		return &""
	state.inventory.add(item, 1)
	_update(id, {"ready": ""})
	changed.emit()
	return item

## `interact` with an animal: its product is taken when it is one that is taken from the
## animal, and it is petted when it was not yet today. Returns `{product, petted}`.
func touch(id: int) -> Dictionary:
	var row := animal(id)
	if row.is_empty():
		return {"product": &"", "petted": false}
	var who := RpgUtil.to_str(row["name"])
	var item := &""
	if row["ready"] != "" and not (data != null and data.on_the_floor(RpgUtil.to_str(row["kind"]))):
		item = take_product(id)
		if item != &"":
			RpgUtil.notify(RpgFarmStrings.t("FARM_ANIMAL_GAVE", [who, RpgFarmStrings.item_name(item)]))
	var petted := pet(id)
	if petted:
		RpgUtil.notify(RpgFarmStrings.t("FARM_ANIMAL_PETTED", [who]))
	elif item == &"":
		RpgUtil.notify(RpgFarmStrings.t("FARM_ANIMAL_HEARTS", [who, hearts(id), HEARTS]))
	return {"product": item, "petted": petted}

## What a product of a kind is sold for by an animal with this much friendship: the `value` of
## the item it gives then (0 for an item the game does not know).
func product_price(kind_id: String, points: int) -> int:
	var item := product_for(kind_id, points)
	var state := RpgUtil.state()
	var def: RpgItemDefinition = state.items.get(item) if state != null else null
	return maxi(0, def.value) if def != null else 0

## The item an animal of a kind gives with this much friendship.
func product_for(kind_id: String, points: int) -> StringName:
	return data.product(kind_id, hearts_of(points) >= LARGE_HEARTS) if data != null else &""

# ------------------------------------------------------------------ the night

## One night over every animal of the game (see the top of the file).
func night() -> void:
	var state := RpgUtil.state()
	if state == null or data == null:
		return
	var rows := herd()
	for row in rows:
		var points := RpgUtil.to_int(row["friendship"])
		if RpgUtil.to_bool(row["fed"]):
			if row["ready"] == "":
				row["ready"] = String(product_for(RpgUtil.to_str(row["kind"]), points))
			row["friendship"] = mini(MAX_POINTS, points + FED_POINTS)
		else:
			row["friendship"] = maxi(0, points + HUNGRY_POINTS)
		row["fed"] = false
		row["petted"] = false
	_store(rows)
	state.set_flag(FLAG_ENTITY, TROUGH_KEY, {})
	changed.emit()

func _on_night(_day: int) -> void:
	night()

func _on_morning(_day: int) -> void:
	_outside = is_outside()
	populate()

func _on_hour(_hour: int) -> void:
	if is_outside() != _outside:
		_outside = is_outside()
		populate()

func _on_weather(_kind: String) -> void:
	_outside = is_outside()
	populate()

func _on_map(_id: StringName) -> void:
	_outside = is_outside()
	populate()

func _on_loaded(_slot: int) -> void:
	_outside = is_outside()
	populate()

# ------------------------------------------------------------------ where the animals are

## True from EVENING to the morning: the animals sleep.
func is_night() -> bool:
	var calendar := RpgCalendar.current()
	return calendar != null and calendar.minute >= EVENING

## True while the animals are out in their yards: by day, in fair weather.
func is_outside() -> bool:
	if is_night():
		return false
	var weather := _weather()
	return weather == null or not weather.keeps_animals_in()

## The node of an animal on the map that is shown, or null (it is on another map).
func node_of(id: int) -> RpgFarmAnimal:
	for raw: Variant in _shown:
		if not is_instance_valid(raw):
			continue
		var node: Node = raw
		var found := node as RpgFarmAnimal
		if found != null and found.animal_id == id and not found.is_queued_for_deletion():
			return found
	return null

## What `populate` made and is still there: the animals, the trough and what lies in the room.
func shown() -> Array[Node]:
	var out: Array[Node] = []
	for raw: Variant in _shown:
		if not is_instance_valid(raw):
			continue
		var node: Node = raw
		if not node.is_queued_for_deletion():
			out.append(node)
	return out

func _forget() -> void:
	for raw: Variant in _shown:
		if not is_instance_valid(raw):
			continue
		var node: Node = raw
		if node.get_parent() != null:
			node.get_parent().remove_child(node)
		node.queue_free()
	_shown.clear()

## Makes what the data says is on `map` (the map that is shown when null): for a room of an
## animal house the trough, the animals that are indoors and the products on its floor; for
## the map of a yard the animals that are out. What an earlier call made is taken away first.
func populate(map: Node = null) -> void:
	_forget()
	if data == null or data.is_empty():
		return
	if map == null:
		var router := RpgUtil.router()
		map = router.current_map if router != null else null
	if map == null:
		return
	watch_field(RpgField.current())
	var path := map.scene_file_path
	if path == "":
		return
	for house_id in data.house_order:
		var house := data.house(house_id)
		if RpgUtil.to_str(house.get("map", "")) == path:
			show_room(map, house_id)
		if RpgUtil.to_str(house.get("yard_map", "")) == path:
			show_yard(map, house_id)

func _holder(map: Node) -> Node:
	var holder := map.get_node_or_null(ENTITIES)
	return holder if holder != null else map

## Adds `node` to `holder` so that it stands at `at` of the world.
func _put(holder: Node, node: Node2D, at: Vector2) -> void:
	holder.add_child(node)
	var origin := RpgUtil.world_position(holder as Node2D) if holder is Node2D else Vector2.ZERO
	node.position = at - origin
	_shown.append(node)

## The scene of an animal's picture, as an RpgFarmAnimal that knows which animal it is.
func _make_animal(row: Dictionary) -> RpgFarmAnimal:
	var path := data.scene_of(RpgUtil.to_str(row["kind"]), RpgUtil.to_int(row["variant"]))
	var node: RpgFarmAnimal = null
	if path != "" and ResourceLoader.exists(path):
		node = (load(path) as PackedScene).instantiate() as RpgFarmAnimal
	if node == null:
		node = RpgFarmAnimal.new()
	node.name = "Animal_%d" % RpgUtil.to_int(row["id"])
	node.animal_id = RpgUtil.to_int(row["id"])
	node.kind = RpgUtil.to_str(row["kind"])
	node.herd = self
	return node

## The room of a house on `map`: its trough at `Markers/Trough`, and, while the animals are
## indoors, each in its stall (`Markers/Stall<n>`), asleep at night. A product that lies on the
## floor lies a cell below the stall of the animal that gave it, wherever the animal is.
func show_room(map: Node, house_id: String) -> void:
	var tile := float(RpgUtil.map_tile_px(map))
	var holder := _holder(map)
	var markers := map.get_node_or_null(MARKERS)
	var trough_at := markers.get_node_or_null("Trough") as Node2D if markers != null else null
	var first := Vector2(tile * 3.5, tile * 1.5)
	if trough_at != null:
		var trough := RpgFarmTrough.make(house_id, tile)
		trough.herd = self
		_put(holder, trough, RpgUtil.world_position(trough_at) + Vector2(0.0, tile * 0.5))
		trough.refresh()
		first = RpgUtil.world_position(trough_at) + Vector2(tile * 2.0, 0.0)
	var indoors := not is_outside()
	var asleep := is_night()
	for row in of_house(house_id):
		var stall := RpgUtil.to_int(row["stall"])
		var marker := markers.get_node_or_null("Stall%d" % (stall + 1)) as Node2D if markers != null else null
		var at := RpgUtil.world_position(marker) if marker != null else first + Vector2(tile * stall, 0.0)
		if indoors:
			var node := _make_animal(row)
			_put(holder, node, at + Vector2(0.0, tile * 0.4))
			if asleep:
				node.sleep()
		if row["ready"] != "" and data.on_the_floor(RpgUtil.to_str(row["kind"])):
			var product := RpgAnimalProduct.make(RpgUtil.to_int(row["id"]), StringName(RpgUtil.to_str(row["ready"])), tile)
			product.herd = self
			_put(holder, product, at + Vector2(0.0, tile))

## The yard of a house on `map` (`Yards/<House>`, whose metadata `yard` is its ground in
## cells): while the animals are out, each stands in it and wanders.
func show_yard(map: Node, house_id: String) -> void:
	if not is_outside():
		return
	var yard := map.get_node_or_null("%s/%s" % [YARDS, house_id.capitalize()]) as Node2D
	if yard == null or not (yard.get_meta(&"yard", null) is Rect2i):
		return
	var cells: Rect2i = yard.get_meta(&"yard")
	if cells.size.x <= 0 or cells.size.y <= 0:
		return
	var tile := float(RpgUtil.map_tile_px(map))
	var ground := Rect2(RpgUtil.world_position(yard), Vector2(cells.size) * tile)
	var holder := _holder(map)
	for row in of_house(house_id):
		var stall := RpgUtil.to_int(row["stall"])
		var cell := Vector2i((1 + stall * 2) % cells.size.x, (stall * 2 / cells.size.x + cells.size.y / 2) % cells.size.y)
		var node := _make_animal(row)
		_put(holder, node, ground.position + (Vector2(cell) + Vector2(0.5, 0.75)) * tile)
		node.roam(ground.grow(-tile * 0.25))

# ------------------------------------------------------------------ hay

## Cut grass of `field` gives hay from now on (the field of the map that is shown is watched
## by itself).
func watch_field(field: RpgField) -> void:
	if field == _field:
		return
	if _field != null and is_instance_valid(_field) and _field.cleared.is_connected(_on_cleared):
		_field.cleared.disconnect(_on_cleared)
	_field = field
	if _field != null:
		_field.cleared.connect(_on_cleared)

func _on_cleared(_cell: Vector2i, what: String) -> void:
	var state := RpgUtil.state()
	if what != "grass" or state == null or data == null or data.is_empty() or data.feed_item == &"":
		return
	if not state.items.has(data.feed_item) or state.inventory.room_for(data.feed_item) < HAY_PER_GRASS:
		return
	state.inventory.add(data.feed_item, HAY_PER_GRASS)
	RpgUtil.notify(RpgFarmStrings.t("FARM_HAY_CUT", [RpgFarmStrings.item_name(data.feed_item)]))
