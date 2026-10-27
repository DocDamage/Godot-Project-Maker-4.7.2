class_name RpgFarmWorkshop
extends Node
## Crafting on a farm (1.5.0, T18.15). A child of the farm's mode (`Workshop`), at work when the
## mode's `crafting` is on (the feature *Crafting* of a farm built since the card); in any other
## farm it does nothing.
##
## * **Materials**: clearing a stump or a branch gives wood, a rock stone (the field's `cleared`).
## * **Placing**: a thing the workbench made (a fence piece, a chest, a sprinkler, a scarecrow, a
##   path stone, a preserves jar) is put on the tile ahead with `use` while it is held
##   (`place`). What stands where is kept in the flags of the game state (`farm_workshop`:
##   `placed`, [{id, kind, map, x, y, data}], `map` the id of the map's field, as the field's own
##   saved state is kept), so it is saved, and it is shown on its map when the map is entered
##   (RpgPlacedThing).
## * **A sprinkler** waters the four cells round it each morning (the saved field, shown or not).
## * **A chest** keeps what is put into it (its `data.items`): `interact` with something held puts
##   the stack in, with nothing (or a tool) held takes everything out that fits.
## * **A preserves jar** takes a crop held with `interact` and gives a jar of preserves (worth more
##   than the crop) the morning after.
## * **A scarecrow** keeps crows off the cells within SCARECROW_RADIUS (`protects`); the farm has
##   no crows yet, so it stands as a thing of the farm.
## * **Cooking** (T18.16, the mode's `cooking`): the dishes of the kitchen (recipes made at the
##   station `kitchen`) that are taught are learned one at a time, from a person whose hearts
##   reach a new level and on the morning of a festival. A farm whose farmhouse was built
##   before it cooked has no kitchen: the shop sells a stove (`stove_for_sale`), placed like the
##   things of the workbench, which is a kitchen.

const NODE_NAME := "Workshop"
const FLAG_ENTITY := "farm_workshop"
const PLACED_KEY := "placed"
## What clearing gives: kind -> [item, how many].
const MATERIALS := {"stump": ["wood", 2], "branch": ["wood", 1], "rock": ["stone", 1]}
## The things that are placed, by their item id; a fence piece and a chest block, a path stone
## does not.
const PLACEABLE: Array[String] = ["fence_piece", "chest", "sprinkler", "scarecrow", "path_stone", "preserves_jar", "stove"]
const STOVE := "stove"
const STOVE_PRICE := 400
## The flags of what the friends taught: person -> the hearts they last taught at.
const TAUGHT_KEY := "taught_at"
const WALKABLE: Array[String] = ["path_stone"]
const SCARECROW_RADIUS := 4
const PRESERVES := "preserves"

## True: the farm crafts (the mode sets it).
var enabled := false
## True: the farm cooks (T18.16), and its farmhouse has no kitchen: the shop sells a stove.
var cooking := false
var stove_for_sale := false

var _field: RpgField = null
var _nodes: Array[Node] = []

## The workshop of the running game, or null in a game that is no farm.
static func current() -> RpgFarmWorkshop:
	var mode := RpgFarmMode.current()
	return mode.workshop if mode != null else null

## Listens to the maps and the calendar. The mode calls it once the calendar exists.
func attach() -> void:
	if cooking:
		_attach_cooking()
	if not enabled and not cooking:
		return
	var calendar := RpgCalendar.current()
	if calendar != null and not calendar.day_began.is_connected(_on_morning):
		calendar.day_began.connect(_on_morning)
	var bus := RpgUtil.events()
	if bus != null and not bus.map_entered.is_connected(_on_map):
		bus.map_entered.connect(_on_map)

# ------------------------------------------------------------------ cooking (T18.16)

func _attach_cooking() -> void:
	var friends := RpgFriendship.current()
	if friends != null and not friends.changed.is_connected(_on_friend):
		friends.changed.connect(_on_friend)
	var calendar := RpgCalendar.current()
	if calendar != null and not calendar.day_began.is_connected(_on_morning):
		calendar.day_began.connect(_on_morning)
	if stove_for_sale:
		RpgFarmShop.add_stock_source(stove_rows)

## The rows the farm's shop adds: a stove while the farm has none.
func stove_rows(_season_name: String = "") -> Array:
	var state := RpgUtil.state()
	if not stove_for_sale or state == null or state.inventory.has(StringName(STOVE)):
		return []
	for row in placed():
		if RpgUtil.to_str(row["kind"]) == STOVE:
			return []
	return [{"item_id": STOVE, "price": STOVE_PRICE}]

## The next dish of the kitchen that is taught and not yet known, or null.
static func next_dish() -> RpgRecipe:
	var state := RpgUtil.state()
	if state == null:
		return null
	for made in RpgCrafting.recipes(&"kitchen"):
		if made.learn == RpgRecipe.TAUGHT and not RpgCrafting.known(state, made):
			return made
	return null

## A person whose hearts reach a level they never taught at teaches the next dish.
func _on_friend(person: String) -> void:
	var friends := RpgFriendship.current()
	var state := RpgUtil.state()
	if not cooking or friends == null or state == null:
		return
	var hearts := friends.hearts(person)
	var taught := RpgUtil.to_dict(state.get_flag(FLAG_ENTITY, TAUGHT_KEY, {})).duplicate()
	if hearts <= RpgUtil.to_int(taught.get(person, 0)):
		return
	taught[person] = hearts
	state.set_flag(FLAG_ENTITY, TAUGHT_KEY, taught)
	var dish := next_dish()
	if dish != null and RpgCrafting.learn(state, dish.id, false):
		RpgUtil.notify(RpgFarmStrings.t("FARM_TAUGHT_DISH", [friends.display_name(person), tr(dish.title)]))

# ------------------------------------------------------------------ materials

## The field of the map that is shown gives wood and stone when it is cleared.
func watch_field(field: RpgField) -> void:
	if field == _field:
		return
	if _field != null and is_instance_valid(_field) and _field.cleared.is_connected(_on_cleared):
		_field.cleared.disconnect(_on_cleared)
	_field = field
	if _field != null:
		_field.cleared.connect(_on_cleared)

func _on_cleared(_cell: Vector2i, what: String) -> void:
	if not enabled or not MATERIALS.has(what):
		return
	var state := RpgUtil.state()
	var given: Array = MATERIALS[what]
	var item := StringName(str(given[0]))
	var qty := RpgUtil.to_int(given[1])
	if state == null or not state.items.has(item):
		return
	if state.inventory.room_for(item) < qty:
		RpgUtil.notify(RpgFarmStrings.t("FARM_FULL"))
		return
	state.inventory.add(item, qty)
	RpgUtil.notify(RpgFarmStrings.t("FARM_GOT", [qty, RpgFarmStrings.item_name(item)]))

# ------------------------------------------------------------------ what is placed

static func placed() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var state := RpgUtil.state()
	if state == null:
		return out
	for raw: Variant in RpgUtil.to_array(state.get_flag(FLAG_ENTITY, PLACED_KEY, [])):
		out.append(RpgUtil.to_dict(raw).duplicate(true))
	return out

static func _store(rows: Array[Dictionary]) -> void:
	var state := RpgUtil.state()
	if state != null:
		state.set_flag(FLAG_ENTITY, PLACED_KEY, rows)

## The thing placed at `cell` of map `map_key`, or {}.
static func thing_at(map_key: String, cell: Vector2i) -> Dictionary:
	for row in placed():
		if RpgUtil.to_str(row["map"]) == map_key and RpgUtil.to_int(row["x"]) == cell.x and RpgUtil.to_int(row["y"]) == cell.y:
			return row
	return {}

static func is_placeable(item_id: StringName) -> bool:
	return PLACEABLE.has(String(item_id))

## Why `item_id` cannot be placed at `cell` of `field`'s map, or "": a thing stands there, the
## soil is tilled, or something of the map is in the way.
func refusal(field: RpgField, map: Node, cell: Vector2i) -> String:
	if field == null or map == null:
		return "FARM_CANNOT_PLACE"
	if not thing_at(field.resolved_id(), cell).is_empty() or field.cells.has(cell):
		return "FARM_CANNOT_PLACE"
	var none: Array[String] = ["stump", "branch", "grass", "rock"]
	if field.clearable_at(cell, none) != null:
		return "FARM_CANNOT_PLACE"
	return ""

## Puts one `item_id` (held) on `cell` of the map that is shown: it leaves the bag, is kept and is
## shown. False (and a toast) when it cannot be.
func place(item_id: StringName, cell: Vector2i, field: RpgField = null, map: Node = null) -> bool:
	var state := RpgUtil.state()
	var allowed := enabled or (cooking and String(item_id) == STOVE)
	if not allowed or state == null or not is_placeable(item_id) or not state.inventory.has(item_id):
		return false
	field = field if field != null else RpgField.current()
	if map == null:
		var router := RpgUtil.router()
		map = router.current_map if router != null else (field.get_parent() if field != null else null)
	var why := refusal(field, map, cell)
	if why != "":
		RpgUtil.notify(RpgFarmStrings.t(why))
		return false
	state.inventory.remove(item_id, 1)
	var rows := placed()
	var next := 1
	for row in rows:
		next = maxi(next, RpgUtil.to_int(row["id"]) + 1)
	var made := {"id": next, "kind": String(item_id), "map": field.resolved_id(), "x": cell.x, "y": cell.y, "data": {}}
	rows.append(made)
	_store(rows)
	_show(made, field)
	return true

static func _update(id: int, data: Dictionary) -> void:
	var rows := placed()
	for row in rows:
		if RpgUtil.to_int(row["id"]) == id:
			row["data"] = data.duplicate(true)
	_store(rows)

# ------------------------------------------------------------------ the morning

## Each morning: a sprinkler waters the four cells round it (of the field of its map, in the saved
## game), and a jar that was filled yesterday has its preserves.
func _on_morning(_day: int) -> void:
	var state := RpgUtil.state()
	if cooking and state != null and RpgFarmEvents.current() != null and RpgFarmEvents.current().is_festival():
		var dish := next_dish()  # a festival teaches a dish (T18.16)
		if dish != null and RpgCrafting.learn(state, dish.id, false):
			RpgUtil.notify(RpgFarmStrings.t("FARM_FESTIVAL_DISH", [tr(dish.title)]))
	if not enabled or state == null:
		return
	var today := RpgCalendar.current().today() if RpgCalendar.current() != null else 0
	for row in placed():
		var kind := RpgUtil.to_str(row["kind"])
		var cell := Vector2i(RpgUtil.to_int(row["x"]), RpgUtil.to_int(row["y"]))
		if kind == "sprinkler":
			water_round(RpgUtil.to_str(row["map"]), cell)
		elif kind == "preserves_jar":
			var data := RpgUtil.to_dict(row["data"])
			if RpgUtil.to_str(data.get("crop", "")) != "" and RpgUtil.to_int(data.get("ready_day", 0)) <= today:
				data["ready"] = true
				_update(RpgUtil.to_int(row["id"]), data)
	var shown := RpgField.current()
	if shown != null:
		shown.load_state()
		shown.refresh()

## Waters the tilled cells round `cell` in the saved field `map_key` (a field's id).
static func water_round(map_key: String, cell: Vector2i) -> int:
	var state := RpgUtil.state()
	if state == null:
		return 0
	var saved := RpgUtil.to_dict(state.get_flag(RpgField.FLAG_ENTITY, map_key, {})).duplicate(true)
	var count := 0
	for step: Vector2i in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var key := RpgField.cell_name(cell + step)
		if saved.has(key):
			var entry := RpgUtil.to_dict(saved[key])
			if not RpgUtil.to_bool(entry.get("w", false)):
				entry["w"] = true
				saved[key] = entry
				count += 1
	if count > 0:
		state.set_flag(RpgField.FLAG_ENTITY, map_key, saved)
	return count

## True when a scarecrow of the map stands within SCARECROW_RADIUS of `cell`.
static func protects(map_key: String, cell: Vector2i) -> bool:
	for row in placed():
		if RpgUtil.to_str(row["kind"]) == "scarecrow" and RpgUtil.to_str(row["map"]) == map_key:
			var at := Vector2i(RpgUtil.to_int(row["x"]), RpgUtil.to_int(row["y"]))
			if absi(at.x - cell.x) <= SCARECROW_RADIUS and absi(at.y - cell.y) <= SCARECROW_RADIUS:
				return true
	return false

# ------------------------------------------------------------------ using a thing

## `interact` with a placed thing (RpgPlacedThing calls it): a chest stores or gives back, a jar
## takes a crop or gives its preserves. Returns true when something happened.
func use_thing(id: int) -> bool:
	var row := {}
	for each in placed():
		if RpgUtil.to_int(each["id"]) == id:
			row = each
	var state := RpgUtil.state()
	if row.is_empty() or state == null:
		return false
	var data := RpgUtil.to_dict(row["data"]).duplicate(true)
	var mode := get_parent() as RpgFarmMode
	var held: StringName = mode.hotbar.held_item() if mode != null and mode.hotbar != null else &""
	match RpgUtil.to_str(row["kind"]):
		"chest":
			return _use_chest(state, id, data, held, mode)
		"preserves_jar":
			return _use_jar(state, id, data, held, mode)
	return false

func _use_chest(state: RpgGameState, id: int, data: Dictionary, held: StringName, mode: RpgFarmMode) -> bool:
	var kept := RpgUtil.to_array(data.get("items", []))
	var def: RpgItemDefinition = state.items.get(held)
	var is_tool := mode != null and mode.tool_for(held) != null
	if held != &"" and def != null and def.category != RpgItemDefinition.Category.KEY and not is_tool:
		var qty := state.inventory.count(held)
		state.inventory.remove(held, qty)
		kept.append({"item_id": String(held), "qty": qty})
		data["items"] = kept
		_update(id, data)
		RpgUtil.notify(RpgFarmStrings.t("FARM_CHEST_PUT", [RpgFarmStrings.item_name(held)]))
		return true
	var left: Array = []
	var taken := 0
	for raw: Variant in kept:
		var stack := RpgUtil.to_dict(raw)
		if state.inventory.transact([stack], []):
			taken += 1
		else:
			left.append(stack)
	data["items"] = left
	_update(id, data)
	RpgUtil.notify(RpgFarmStrings.t("FARM_CHEST_TOOK" if taken > 0 else "FARM_CHEST_EMPTY"))
	return taken > 0

func _use_jar(state: RpgGameState, id: int, data: Dictionary, held: StringName, mode: RpgFarmMode) -> bool:
	if RpgUtil.to_bool(data.get("ready", false)):
		if not state.items.has(StringName(PRESERVES)) or state.inventory.room_for(StringName(PRESERVES)) < 1:
			RpgUtil.notify(RpgFarmStrings.t("FARM_FULL"))
			return false
		state.inventory.add(StringName(PRESERVES), 1)
		_update(id, {})
		RpgUtil.notify(RpgFarmStrings.t("FARM_GOT", [1, RpgFarmStrings.item_name(StringName(PRESERVES))]))
		return true
	if RpgUtil.to_str(data.get("crop", "")) != "":
		RpgUtil.notify(RpgFarmStrings.t("FARM_JAR_BUSY"))
		return false
	var is_crop := mode != null and mode.crops != null and mode.crops.crop_of_produce(held) != ""
	if not is_crop or not state.inventory.has(held):
		RpgUtil.notify(RpgFarmStrings.t("FARM_JAR_NEEDS_CROP"))
		return false
	state.inventory.remove(held, 1)
	var calendar := RpgCalendar.current()
	_update(id, {"crop": String(held), "ready_day": (calendar.today() if calendar != null else 0) + 1})
	RpgUtil.notify(RpgFarmStrings.t("FARM_JAR_FILLED", [RpgFarmStrings.item_name(held)]))
	return true

# ------------------------------------------------------------------ the map that is shown

func _on_map(_map_id: StringName) -> void:
	_forget()
	var field := RpgField.current()
	watch_field(field)
	for row in placed():
		_show(row, field)

func _forget() -> void:
	for node in _nodes:
		if is_instance_valid(node):
			node.queue_free()
	_nodes.clear()

## Shows a placed thing on the map that is shown, when it is its map.
func _show(row: Dictionary, field: RpgField) -> void:
	if field == null or not field.is_inside_tree():
		return
	if field.resolved_id() != RpgUtil.to_str(row["map"]):
		return
	var cell := Vector2i(RpgUtil.to_int(row["x"]), RpgUtil.to_int(row["y"]))
	var node := RpgPlacedThing.make(RpgUtil.to_int(row["id"]), RpgUtil.to_str(row["kind"]), field.tile_px, not WALKABLE.has(RpgUtil.to_str(row["kind"])))
	var holder := field.get_node_or_null(field.crops_path)
	if holder == null:
		holder = field
	holder.add_child(node)
	node.global_position = field.foot_of(cell)
	_nodes.append(node)
