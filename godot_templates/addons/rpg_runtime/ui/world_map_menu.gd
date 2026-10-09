class_name RpgWorldMapMenu
extends Control
## The world map (T12.64), opened from the pause menu: the maps the player has been to, each its
## minimap with the cells not seen yet covered (the fog of GameState.map_fog). Up/down choose a
## map; Back or cancel closes it. A game with a world of areas (rpggen/world_plan.json, T13.20)
## has "World" as its first entry: every area as a box where the plan placed it, the ones the
## player has been to lit, with the doors between them, so the layout shows before it is explored.

const CELL_PX := 4.0
const FOG := Color(0.05, 0.05, 0.08, 1.0)
const WORLD_PLAN := "res://rpggen/world_plan.json"
const WORLD_KEY := "@world"
const AREA_BOX := Vector2i(40, 26)
const AREA_GAP := 10
const AREA_SEEN := Color(0.45, 0.62, 0.42)
const AREA_UNSEEN := Color(0.2, 0.22, 0.28)
const AREA_EDGE := Color(0.85, 0.87, 0.9)
const AREA_DOOR := Color(0.9, 0.78, 0.4)

var _list: ItemList = null
var _picture: TextureRect = null
var _keys: Array[String] = []

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	var list := get_node_or_null("%Maps") as ItemList
	_list = list
	_picture = get_node_or_null("%Picture") as TextureRect
	var back := get_node_or_null("%Back") as Button
	if back != null:
		back.pressed.connect(close)
	refresh()
	if _list != null:
		_list.item_selected.connect(show_map)
		if _list.item_count > 0:
			_list.select(0)
			show_map(0)
		_list.grab_focus.call_deferred()

func refresh() -> void:
	var state := RpgUtil.state()
	_keys = state.visited_maps() if state != null else [] as Array[String]
	var plan := world_plan()
	if not RpgMinimapData.room_list(plan).is_empty():
		_keys = []  # a world of rooms (T14.08) has one map: the room map
	if not plan.is_empty():
		_keys.push_front(WORLD_KEY)
	if _list == null:
		return
	_list.clear()
	for key in _keys:
		if key == WORLD_KEY:
			_list.add_item(tr("UI_WORLD_OVERVIEW"))
			continue
		_list.add_item(area_name(plan, key))

## The stored world plan, or {} (a game without areas, or a file that is not a plan).
static func world_plan(path: String = WORLD_PLAN) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return RpgUtil.to_dict(parsed)

## The name of the map with this key: the area's name in the plan, else its MAP_<ID> text key.
func area_name(plan: Dictionary, map_key: String) -> String:
	for raw: Variant in RpgUtil.to_array(plan.get("areas", [])):
		var area := RpgUtil.to_dict(raw)
		if RpgMinimapData.key_for("res://" + str(area.get("map", ""))) == map_key and str(area.get("id", "")) != "starter_map":
			return str(area.get("name", map_key))
	return tr("MAP_" + map_key.get_slice("__", map_key.get_slice_count("__") - 1).to_upper())

## The world as a picture: a box per area at its place on the plan's grid (lit when `visited` has
## the area's map key), and a mark on the shared edge of two areas that a door joins.
static func overview(plan: Dictionary, visited: Array[String]) -> Image:
	var grid := RpgUtil.to_dict(plan.get("grid", {}))
	var low := Vector2i(0, 0)
	var high := Vector2i(0, 0)
	for raw: Variant in grid.values():
		var at := _cell(raw)
		low = Vector2i(mini(low.x, at.x), mini(low.y, at.y))
		high = Vector2i(maxi(high.x, at.x), maxi(high.y, at.y))
	var pitch := AREA_BOX + Vector2i(AREA_GAP, AREA_GAP)
	var size := (high - low + Vector2i.ONE) * pitch + Vector2i(AREA_GAP, AREA_GAP)
	var image := Image.create(size.x, size.y, false, Image.FORMAT_RGBA8)
	image.fill(FOG)
	var corners := {}
	for raw: Variant in RpgUtil.to_array(plan.get("areas", [])):
		var area := RpgUtil.to_dict(raw)
		var id := str(area.get("id", ""))
		if not grid.has(id):
			continue
		var corner := (_cell(grid[id]) - low) * pitch + Vector2i(AREA_GAP, AREA_GAP)
		corners[id] = corner
		var seen := visited.has(RpgMinimapData.key_for("res://" + str(area.get("map", ""))))
		image.fill_rect(Rect2i(corner, AREA_BOX), AREA_EDGE)
		image.fill_rect(Rect2i(corner + Vector2i.ONE, AREA_BOX - Vector2i(2, 2)), AREA_SEEN if seen else AREA_UNSEEN)
	for raw: Variant in RpgUtil.to_array(plan.get("areas", [])):
		var area := RpgUtil.to_dict(raw)
		var from := str(area.get("id", ""))
		for raw_door: Variant in RpgUtil.to_array(area.get("doors", [])):
			var to := str(RpgUtil.to_dict(raw_door).get("to", ""))
			if corners.has(from) and corners.has(to):
				var a: Vector2i = corners[from]
				var b: Vector2i = corners[to]
				var middle := (a + b + AREA_BOX) / 2
				image.fill_rect(Rect2i(middle - Vector2i(2, 2), Vector2i(4, 4)), AREA_DOOR)
	return image

## The room map of a world of rooms, four times as large as the HUD's: the rooms `state` has
## been in, the current one outlined, exits, save stations and the abilities still to be found.
static func room_overview(plan: Dictionary, state: RpgGameState) -> Image:
	var visited: Dictionary = state.room_fog if state != null else {}
	var held: Array = state.abilities if state != null else []
	var current := str(state.current_map).get_file().get_basename() if state != null else ""
	var picture := RpgMinimapData.room_map(plan, visited, current, held)
	picture.resize(picture.get_width() * 4, picture.get_height() * 4, Image.INTERPOLATE_NEAREST)
	return picture

static func _cell(value: Variant) -> Vector2i:
	var pair := RpgUtil.to_array(value)
	return Vector2i(RpgUtil.to_int(pair[0]), RpgUtil.to_int(pair[1])) if pair.size() == 2 else Vector2i.ZERO

## The picture of map `index`: its minimap, the unseen cells covered.
func show_map(index: int) -> void:
	if _picture == null or index < 0 or index >= _keys.size():
		return
	if _keys[index] == WORLD_KEY:
		var state := RpgUtil.state()
		var plan := world_plan()
		if not RpgMinimapData.room_list(plan).is_empty():
			_picture.texture = ImageTexture.create_from_image(room_overview(plan, state))
			return
		var picture := overview(world_plan(), state.visited_maps() if state != null else [] as Array[String])
		picture.resize(picture.get_width() * 2, picture.get_height() * 2, Image.INTERPOLATE_NEAREST)
		_picture.texture = ImageTexture.create_from_image(picture)
		return
	_picture.texture = fogged(_keys[index], RpgUtil.state())

## The minimap of `map_key` (or `texture`) with the cells `state` has not seen covered, scaled up
## (null without a minimap).
static func fogged(map_key: String, state: RpgGameState, texture: Texture2D = null) -> ImageTexture:
	if texture == null:
		texture = RpgMinimapData.load_texture(map_key)
	if texture == null:
		return null
	var image := texture.get_image()
	image.convert(Image.FORMAT_RGBA8)
	for y in image.get_height():
		for x in image.get_width():
			if state == null or not state.fog_seen(map_key, Vector2i(x, y)):
				image.set_pixel(x, y, FOG)
	var scaled := image.duplicate() as Image
	scaled.resize(int(image.get_width() * CELL_PX), int(image.get_height() * CELL_PX), Image.INTERPOLATE_NEAREST)
	return ImageTexture.create_from_image(scaled)

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel") or (InputMap.has_action("cancel") and event.is_action_pressed("cancel")):
		get_viewport().set_input_as_handled()
		close()

func close() -> void:
	queue_free()
