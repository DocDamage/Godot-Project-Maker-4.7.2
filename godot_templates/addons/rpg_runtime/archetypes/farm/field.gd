class_name RpgField
extends Node2D
## The field of a farm map (T17.05): the state of every cell that was worked, kept as data and
## shown on two layers of the map. Tilled and watered soil are painted on the TileMapLayer
## `Soil` (under the crops); the crops are scenes (RpgCrop) among the entities of the map, so
## they Y-sort with the farmer.
##
## **What can be tilled** is what the recipe wrote into the tiles: a cell whose tile (on any
## layer of the map) has the bool custom data `tillable`. Nothing is guessed from the art. A
## cell whose tile has `water` fills the watering can.
##
## **The data** is `cells`: cell -> {w (watered), crop (a crop id or ""), grown (watered nights),
## dead (withered), idle (nights tilled with nothing on it)}. It lives in the flags of the game
## state (`farm_field`, one key a field), so it is saved with the game and the save has no new
## key, and a field grows overnight whether its map is shown or not: `grow` and `night_all`
## work on the data alone.
##
## **A night** (RpgFarmMode calls `night_all` from the calendar's `on_night`, NIGHT_CROPS): a
## watered crop grows a day and an unwatered one does not; a crop that does not grow in the
## season that begins withers; soil dries; tilled soil that has had nothing on it and no water
## for IDLE_NIGHTS nights is ground again.

## A cell was tilled, watered, planted, harvested or cleared, or a night passed over it.
signal changed(cell: Vector2i)
signal harvested(crop_id: String, item_id: StringName, qty: int)
## A thing was cleared away from `cell`: `what` is `stump`, `branch` or `grass`. Whoever gives
## something for it listens (cut grass is hay in a farm that keeps animals, T17.07).
signal cleared(cell: Vector2i, what: String)

const GROUP := &"farm_field"
const FLAG_ENTITY := "farm_field"
const TILLABLE := "tillable"
const WATER := "water"
const IDLE_NIGHTS := 3
## What a tool can clear away stands among the entities of the map (`crops_path`) and says
## what it is with this metadata: `stump`, `branch` or `grass`.
const CLEAR_META := &"farm_clear"

const GROUND := "ground"
const SOIL := "soil"
const CROP := "crop"
const RIPE := "ripe"
const WITHERED := "withered"

## What the field is called in the saved game; the id of its map when empty.
@export var field_id: String = ""
@export var soil_path: NodePath = ^"../Soil"
## Where the crops stand: the Y-sorted entities of the map.
@export var crops_path: NodePath = ^"../YSorted/Entities"
## The tiles of tilled and of watered soil in the tile set of the `Soil` layer: the source and
## the cell of each.
@export var tilled_source: int = 0
@export var tilled_tile: Vector2i = Vector2i(1, 0)
@export var watered_source: int = 0
@export var watered_tile: Vector2i = Vector2i(2, 0)
@export var crop_scenes_dir: String = "res://generated/scenes/farm/crops/"
## The size of a cell when the map has no `Soil` layer to ask.
@export var tile_px: int = 16

var cells: Dictionary = {}
## The crops of the game; read from the files when nobody gave them.
var crops: RpgCropData = null

var _soil: TileMapLayer = null
var _layers: Array[TileMapLayer] = []
var _base: Dictionary = {}  # cell -> [source id, atlas coords]: what the Soil layer had there
var _nodes: Dictionary = {}  # cell -> RpgCrop

# ------------------------------------------------------------------ finding it

## The field of the map that is shown, or null.
static func current() -> RpgField:
	var tree := RpgUtil.tree()
	return tree.get_first_node_in_group(GROUP) as RpgField if tree != null else null

func _ready() -> void:
	setup()

## Finds the layers, takes the saved state and shows it. `_ready` calls it.
func setup() -> void:
	add_to_group(GROUP)
	if crops == null:
		crops = RpgCropData.load_default()
	_soil = get_node_or_null(soil_path) as TileMapLayer
	_layers.clear()
	var map := get_parent()
	if map != null:
		for layer in map.find_children("*", "TileMapLayer", true, false):
			_layers.append(layer as TileMapLayer)
	_base.clear()
	if _soil != null:
		if _soil.tile_set != null:
			tile_px = _soil.tile_set.tile_size.x
		for cell in _soil.get_used_cells():
			_base[cell] = [_soil.get_cell_source_id(cell), _soil.get_cell_atlas_coords(cell)]
	load_state()
	refresh()

func resolved_id() -> String:
	if field_id != "":
		return field_id
	var map := get_parent()
	if map != null and map.get("map_id") != null and str(map.get("map_id")) != "":
		return str(map.get("map_id"))
	return "field"

# ------------------------------------------------------------------ cells

## The cell a place in the world lies in.
func cell_at(at: Vector2) -> Vector2i:
	if _soil != null:
		var local := _soil.to_local(at) if _soil.is_inside_tree() else at - _soil.position
		return _soil.local_to_map(local)
	return Vector2i(floori(at.x / tile_px), floori(at.y / tile_px))

## The middle of a cell in the world.
func cell_center(cell: Vector2i) -> Vector2:
	if _soil != null:
		var local := _soil.map_to_local(cell)
		return _soil.to_global(local) if _soil.is_inside_tree() else local + _soil.position
	return (Vector2(cell) + Vector2(0.5, 0.5)) * tile_px

## True when the tile of a layer of the map at `cell` has the bool custom data `data_name`.
func tile_says(cell: Vector2i, data_name: String) -> bool:
	for layer in _layers:
		if layer == null or layer.tile_set == null or layer.tile_set.get_custom_data_layer_by_name(data_name) < 0:
			continue
		var source := layer.get_cell_source_id(cell)
		var coords := layer.get_cell_atlas_coords(cell)
		if layer == _soil and _base.has(cell):  # under what the field painted
			var base: Array = _base[cell]
			source = RpgUtil.to_int(base[0])
			coords = base[1]
		var atlas := layer.tile_set.get_source(source) as TileSetAtlasSource if source >= 0 else null
		if atlas != null and atlas.has_tile(coords) and RpgUtil.to_bool(atlas.get_tile_data(coords, 0).get_custom_data(data_name)):
			return true
	return false

func is_water(cell: Vector2i) -> bool:
	return tile_says(cell, WATER)

## What a cell is: GROUND (it can be tilled), SOIL (tilled, nothing on it), CROP, RIPE,
## WITHERED, or "" for a cell the field has nothing to do with.
func state_of(cell: Vector2i) -> String:
	if not cells.has(cell):
		return GROUND if tile_says(cell, TILLABLE) else ""
	var entry: Dictionary = cells[cell]
	var crop_id := RpgUtil.to_str(entry.get("crop", ""))
	if crop_id == "":
		return SOIL
	if RpgUtil.to_bool(entry.get("dead", false)):
		return WITHERED
	return RIPE if RpgCropData.is_ripe(RpgUtil.to_int(entry.get("grown", 0)), crops.days(crop_id)) else CROP

func is_watered(cell: Vector2i) -> bool:
	return cells.has(cell) and RpgUtil.to_bool(RpgUtil.to_dict(cells[cell]).get("w", false))

## The crop id of a cell, or "".
func crop_at(cell: Vector2i) -> String:
	return RpgUtil.to_str(RpgUtil.to_dict(cells.get(cell, {})).get("crop", ""))

## How many watered nights the crop of a cell has grown.
func grown_at(cell: Vector2i) -> int:
	return RpgUtil.to_int(RpgUtil.to_dict(cells.get(cell, {})).get("grown", 0))

# ------------------------------------------------------------------ what can be cleared

## The thing of the map that stands in `cell` and is one of `kinds` (a stump, a branch, grass),
## or null.
func clearable_at(cell: Vector2i, kinds: Array[String]) -> Node2D:
	var holder := get_node_or_null(crops_path)
	if holder == null:
		return null
	for node in holder.get_children():
		var thing := node as Node2D
		if thing == null or thing.is_queued_for_deletion() or not thing.has_meta(CLEAR_META):
			continue
		if kinds.has(RpgUtil.to_str(thing.get_meta(CLEAR_META))) and cell_at(RpgUtil.world_position(thing)) == cell:
			return thing
	return null

## Takes away what stands in `cell` when it is one of `kinds`, for good (its `collected` flag
## when it has an `entity_id`). False when there is nothing of the kind.
func clear_obstacle(cell: Vector2i, kinds: Array[String]) -> bool:
	var thing := clearable_at(cell, kinds)
	if thing == null:
		return false
	var state := RpgUtil.state()
	var id := RpgUtil.to_str(thing.get("entity_id")) if thing.get("entity_id") != null else ""
	if state != null and id != "":
		state.set_flag(id, "collected", true)
	var what := RpgUtil.to_str(thing.get_meta(CLEAR_META))
	thing.queue_free()
	changed.emit(cell)
	cleared.emit(cell, what)
	return true

# ------------------------------------------------------------------ the work

func can_till(cell: Vector2i) -> bool:
	var none: Array[String] = ["stump", "branch", "grass"]
	return state_of(cell) == GROUND and clearable_at(cell, none) == null

## Tills a cell of ground. False when it cannot be tilled.
func till(cell: Vector2i) -> bool:
	if not can_till(cell):
		return false
	cells[cell] = {"w": false, "crop": "", "grown": 0, "dead": false, "idle": 0}
	_touched(cell)
	return true

func can_water(cell: Vector2i) -> bool:
	return cells.has(cell) and not is_watered(cell)

## Waters tilled soil. False when the cell is not tilled or is wet already.
func water(cell: Vector2i) -> bool:
	if not can_water(cell):
		return false
	var entry: Dictionary = cells[cell]
	entry["w"] = true
	_touched(cell)
	return true

## Waters every tilled cell (rain, T17.11). Returns how many were dry.
func water_all() -> int:
	var count := 0
	for cell: Vector2i in cells.keys():
		if water(cell):
			count += 1
	return count

## True when `crop_id` can be planted in `cell` in the season of this name.
func can_plant(cell: Vector2i, crop_id: String, season_name: String) -> bool:
	return state_of(cell) == SOIL and crops.has(crop_id) and crops.grows_in(crop_id, season_name)

## Plants a crop in tilled soil, in the season the calendar shows (spring without one).
func plant(cell: Vector2i, crop_id: String) -> bool:
	if not can_plant(cell, crop_id, season_now()):
		return false
	var entry: Dictionary = cells[cell]
	entry["crop"] = crop_id
	entry["grown"] = 0
	entry["dead"] = false
	entry["idle"] = 0
	_touched(cell)
	return true

## Harvests the ripe crop of a cell into the inventory of the game. A crop that grows again goes
## back by its `regrow` days; any other leaves tilled soil. False, and the crop stays standing,
## when it is not ripe or the inventory has no room.
func harvest(cell: Vector2i) -> bool:
	if state_of(cell) != RIPE:
		return false
	var crop_id := crop_at(cell)
	var info := crops.crop(crop_id)
	var item := StringName(RpgUtil.to_str(info.get("produce", "")))
	var qty := maxi(1, RpgUtil.to_int(info.get("yield", 1), 1))
	var state := RpgUtil.state()
	if state == null or item == &"" or state.inventory.room_for(item) < qty:
		RpgUtil.notify(RpgFarmStrings.t("FARM_FULL"))
		return false
	state.inventory.add(item, qty)
	var entry: Dictionary = cells[cell]
	var again := crops.regrow(crop_id)
	if again > 0:
		entry["grown"] = crops.days(crop_id) - again
	else:
		entry["crop"] = ""
		entry["grown"] = 0
		entry["idle"] = 0
	_touched(cell)
	harvested.emit(crop_id, item, qty)
	return true

## Takes a crop out of a cell (a withered one is cut away). The soil stays tilled.
func remove_crop(cell: Vector2i) -> bool:
	if crop_at(cell) == "":
		return false
	var entry: Dictionary = cells[cell]
	entry["crop"] = ""
	entry["grown"] = 0
	entry["dead"] = false
	entry["idle"] = 0
	_touched(cell)
	return true

func _touched(cell: Vector2i) -> void:
	store()
	_show(cell)
	changed.emit(cell)

## The name of the season the calendar shows; spring in a game without one.
static func season_now() -> String:
	var calendar := RpgCalendar.current()
	return calendar.season_name() if calendar != null else RpgCalendar.SEASONS[0]

# ------------------------------------------------------------------ the night

## One night over the cells of a field (`cells` is changed in place; the keys may be cells or
## their saved names). `season_next` is the season of the morning after.
static func grow(field_cells: Dictionary, crop_data: RpgCropData, season_next: String) -> void:
	for key: Variant in field_cells.keys():
		var entry := RpgUtil.to_dict(field_cells[key])
		var crop_id := RpgUtil.to_str(entry.get("crop", ""))
		var wet := RpgUtil.to_bool(entry.get("w", false))
		if crop_id != "" and crop_data.has(crop_id):
			if not RpgUtil.to_bool(entry.get("dead", false)):
				if wet:
					entry["grown"] = mini(crop_data.days(crop_id), RpgUtil.to_int(entry.get("grown", 0)) + 1)
				if not crop_data.grows_in(crop_id, season_next):
					entry["dead"] = true
			entry["idle"] = 0
		elif wet:
			entry["idle"] = 0
		else:
			entry["idle"] = RpgUtil.to_int(entry.get("idle", 0)) + 1
		entry["w"] = false
		if crop_id == "" and RpgUtil.to_int(entry.get("idle", 0)) >= IDLE_NIGHTS:
			field_cells.erase(key)
		else:
			field_cells[key] = entry

## One night over every field of the saved game, shown or not, then the field that is shown
## takes its new state. `season_next` is the season of the morning after.
static func night_all(crop_data: RpgCropData, season_next: String) -> void:
	var state := RpgUtil.state()
	if state == null or crop_data == null:
		return
	var fields := RpgUtil.to_dict(state.flags.get(FLAG_ENTITY, {}))
	for id: Variant in fields.keys():
		var saved := RpgUtil.to_dict(fields[id])
		grow(saved, crop_data, season_next)
		state.set_flag(FLAG_ENTITY, RpgUtil.to_str(id), saved)
	var shown := current()
	if shown != null:
		shown.load_state()
		shown.refresh()

# ------------------------------------------------------------------ the saved game

static func cell_name(cell: Vector2i) -> String:
	return "%d,%d" % [cell.x, cell.y]

static func cell_of(saved_name: String) -> Vector2i:
	var parts := saved_name.split(",")
	return Vector2i(int(parts[0]), int(parts[1])) if parts.size() == 2 else Vector2i.ZERO

## What the saved game holds of this field: "x,y" -> the state of the cell.
func to_dict() -> Dictionary:
	var out := {}
	for cell: Vector2i in cells.keys():
		out[cell_name(cell)] = RpgUtil.to_dict(cells[cell]).duplicate()
	return out

func from_dict(saved: Dictionary) -> void:
	cells.clear()
	for key: Variant in saved.keys():
		var entry := RpgUtil.to_dict(saved[key])
		cells[cell_of(RpgUtil.to_str(key))] = {
			"w": RpgUtil.to_bool(entry.get("w", false)),
			"crop": RpgUtil.to_str(entry.get("crop", "")),
			"grown": RpgUtil.to_int(entry.get("grown", 0)),
			"dead": RpgUtil.to_bool(entry.get("dead", false)),
			"idle": RpgUtil.to_int(entry.get("idle", 0)),
		}

## Writes the state into the game state (every change does).
func store() -> void:
	var state := RpgUtil.state()
	if state != null:
		state.set_flag(FLAG_ENTITY, resolved_id(), to_dict())

## Takes the state of the game state: after a load, a new game or a night.
func load_state() -> void:
	var state := RpgUtil.state()
	if state != null:
		from_dict(RpgUtil.to_dict(state.get_flag(FLAG_ENTITY, resolved_id(), {})))

# ------------------------------------------------------------------ showing it

## Paints every cell and puts every crop where the data says.
func refresh() -> void:
	var seen := {}
	for cell: Vector2i in cells.keys():
		seen[cell] = true
	for cell: Vector2i in _nodes.keys():
		seen[cell] = true
	if _soil != null:
		for cell in _soil.get_used_cells():
			seen[cell] = true
	for cell: Vector2i in seen.keys():
		_show(cell)

## The crop node of a cell, or null.
func crop_node(cell: Vector2i) -> RpgCrop:
	var node: RpgCrop = _nodes.get(cell)
	return node if node != null and is_instance_valid(node) else null

func _show(cell: Vector2i) -> void:
	_paint(cell)
	var crop_id := crop_at(cell)
	var node := crop_node(cell)
	if node != null and node.crop_id != crop_id:
		node.queue_free()
		_nodes.erase(cell)
		node = null
	if crop_id == "":
		return
	if node == null:
		node = _make_crop(crop_id, cell)
	var state := state_of(cell)
	var days := crops.days(crop_id)
	var count := crops.stages(crop_id)
	node.show_stage(RpgCropData.stage_of(grown_at(cell), days, count), count, state == RIPE, state == WITHERED)

func _paint(cell: Vector2i) -> void:
	if _soil == null:
		return
	if cells.has(cell):
		if is_watered(cell):
			_soil.set_cell(cell, watered_source, watered_tile)
		else:
			_soil.set_cell(cell, tilled_source, tilled_tile)
	elif _base.has(cell):
		var base: Array = _base[cell]
		var coords: Vector2i = base[1]
		_soil.set_cell(cell, RpgUtil.to_int(base[0]), coords)
	else:
		_soil.erase_cell(cell)

func _make_crop(crop_id: String, cell: Vector2i) -> RpgCrop:
	var path := RpgUtil.to_str(crops.crop(crop_id).get("scene", ""))
	if path == "":
		path = crop_scenes_dir + crop_id + ".tscn"
	var node: RpgCrop = null
	if ResourceLoader.exists(path):
		node = (load(path) as PackedScene).instantiate() as RpgCrop
	if node == null:
		node = RpgCrop.new()
	node.name = "Crop_%d_%d" % [cell.x, cell.y]
	node.crop_id = crop_id
	node.cell = cell
	node.picked.connect(harvest)
	var holder := get_node_or_null(crops_path)
	if holder == null:
		holder = self
	holder.add_child(node)
	# the foot of the crop is the bottom of its cell, so it sorts with what stands there
	var foot := cell_center(cell) + Vector2(0.0, tile_px * 0.5 - 1.0)
	if node.is_inside_tree():
		node.global_position = foot
	else:
		node.position = foot
	_nodes[cell] = node
	return node
