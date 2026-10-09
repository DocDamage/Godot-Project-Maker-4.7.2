class_name RpgWorldMapMenu
extends Control
## The world map (T12.64), opened from the pause menu: the maps the player has been to, each its
## minimap with the cells not seen yet covered (the fog of GameState.map_fog). Up/down choose a
## map; Back or cancel closes it.

const CELL_PX := 4.0
const FOG := Color(0.05, 0.05, 0.08, 1.0)

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
	if _list == null:
		return
	_list.clear()
	for key in _keys:
		_list.add_item(tr("MAP_" + key.get_slice("__", key.get_slice_count("__") - 1).to_upper()))

## The picture of map `index`: its minimap, the unseen cells covered.
func show_map(index: int) -> void:
	if _picture == null or index < 0 or index >= _keys.size():
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
