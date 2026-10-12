class_name RpgMinimap
extends Control
## The HUD minimap (T12.64), in the top-right corner: the part of the map around the player, the
## cells not seen yet darkened, a dot for the player and marks for doors, unopened chests and
## quest targets. Boot adds it; RpgSettings.minimap turns it off. Walking reveals the fog of the
## world map (GameState.fog_mark).

const VIEW := Vector2(112, 84)
const CELL_PX := 3.0
const MARGIN := 8.0
const FOG_RADIUS := 5
const UPDATE_S := 0.2
const FOG := Color(0.05, 0.05, 0.08, 0.85)
const BORDER := Color(1, 1, 1, 0.6)
const MARK_COLORS := {"door": Color(0.4, 0.7, 1.0), "chest": Color(1.0, 0.82, 0.3), "quest": Color(1.0, 0.35, 0.9)}

var _texture: Texture2D = null
var _key := ""
var _player_cell := Vector2i.ZERO
var _marks: Array[Dictionary] = []
var _since := 0.0
## Room mode (T14.08): the picture of the world's rooms, what it was made from, and where the
## current room's box is in it.
var _room_texture: ImageTexture = null
var _room_stamp := ""
var _room_box := Rect2i()
var _plan: Dictionary = {}
var _plan_read := false
const ROOM_ZOOM := 2.0

func _ready() -> void:
	name = "Minimap"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = VIEW
	size = VIEW
	set_anchors_preset(Control.PRESET_TOP_RIGHT)
	# (offsets from the corner: a position is counted from the left edge of the screen)
	offset_left = -VIEW.x - MARGIN
	offset_right = -MARGIN
	offset_top = MARGIN
	offset_bottom = MARGIN + VIEW.y
	visible = false

func _process(delta: float) -> void:
	_since += delta
	if _since < UPDATE_S:
		return
	_since = 0.0
	refresh()

## Reads the map, the player and the markers again; hides itself when there is nothing to show.
func refresh() -> void:
	var settings := RpgUtil.settings()
	var router := RpgUtil.router()
	var map: RpgMapRoot = router.current_map if router != null else null
	# (during a map change the old map has left the tree)
	if (settings != null and not settings.minimap) or map == null or not is_instance_valid(map) or not map.is_inside_tree():
		visible = false
		return
	if RpgUtil.to_bool(map.get("side_view")):
		_refresh_rooms(map)
		return
	_room_texture = null
	var key := RpgMinimapData.key_for(map.scene_file_path)
	if key != _key:
		_key = key
		_texture = RpgMinimapData.load_texture(key)
	var player := map.get_player()
	if _texture == null or player == null:
		visible = false
		return
	visible = true
	_player_cell = RpgMinimapData.cell_at(_texture, map.to_local(player.global_position))
	var state := RpgUtil.state()
	if state != null:
		state.fog_mark(_key, Vector2i(_texture.get_width(), _texture.get_height()), _player_cell, FOG_RADIUS)
	_marks = RpgMinimapData.markers(map, state.quest_targets() if state != null else [] as Array[String])
	queue_redraw()

## Room mode: a side-view room shows the room map (the rooms visited on the world's grid),
## centred on the room the player is in. The picture is made again only when something it shows
## changed.
func _refresh_rooms(map: RpgMapRoot) -> void:
	if not _plan_read:
		_plan_read = true
		_plan = RpgWorldMapMenu.world_plan()
	var state := RpgUtil.state()
	var current := String(map.map_id)
	if state == null or RpgMinimapData.room_list(_plan).is_empty():
		visible = false
		return
	visible = true
	var stamp := "%s|%d|%d" % [current, state.room_fog.size(), state.abilities.size()]
	if stamp != _room_stamp or _room_texture == null:
		_room_stamp = stamp
		_room_texture = ImageTexture.create_from_image(RpgMinimapData.room_map(_plan, state.room_fog, current, state.abilities))
		var boxes := RpgMinimapData.room_boxes(_plan)
		_room_box = boxes.get(current, Rect2i())
		queue_redraw()

## The room map picture shown now, or null outside a side-view room (tests).
func room_texture() -> ImageTexture:
	return _room_texture

## The texture rect (in minimap pixels) the view shows: centred on the player.
func view_rect() -> Rect2:
	var cells := VIEW / CELL_PX
	return Rect2(Vector2(_player_cell) + Vector2(0.5, 0.5) - cells / 2.0, cells)

func _draw() -> void:
	if _room_texture != null:
		draw_rect(Rect2(Vector2.ZERO, VIEW), Color(0, 0, 0, 0.55))
		var centre := Vector2(_room_box.position) + Vector2(_room_box.size) / 2.0
		var source := Rect2(centre - VIEW / ROOM_ZOOM / 2.0, VIEW / ROOM_ZOOM)
		var whole := Rect2(Vector2.ZERO, Vector2(_room_texture.get_size()))
		var part := source.intersection(whole)
		if part.has_area():
			draw_texture_rect_region(_room_texture, Rect2((part.position - source.position) * ROOM_ZOOM, part.size * ROOM_ZOOM), part)
		draw_rect(Rect2(Vector2.ZERO, VIEW), BORDER, false, 1.0)
		return
	if _texture == null:
		return
	draw_rect(Rect2(Vector2.ZERO, VIEW), Color(0, 0, 0, 0.55))
	var src := view_rect()
	var tex_rect := Rect2(Vector2.ZERO, Vector2(_texture.get_size()))
	var shown := src.intersection(tex_rect)
	if shown.has_area():
		var dest := Rect2((shown.position - src.position) * CELL_PX, shown.size * CELL_PX)
		draw_texture_rect_region(_texture, dest, shown)
	var state := RpgUtil.state()
	if state != null:
		for y in range(floori(src.position.y), ceili(src.end.y)):
			for x in range(floori(src.position.x), ceili(src.end.x)):
				if not state.fog_seen(_key, Vector2i(x, y)) and tex_rect.has_point(Vector2(x, y)):
					draw_rect(Rect2((Vector2(x, y) - src.position) * CELL_PX, Vector2(CELL_PX, CELL_PX)), FOG)
	for mark in _marks:
		var spot: Vector2 = mark["position"]
		var colour: Color = MARK_COLORS.get(mark["kind"], Color.WHITE)
		var cell := RpgMinimapData.cell_at(_texture, spot)
		var at := (Vector2(cell) + Vector2(0.5, 0.5) - src.position) * CELL_PX
		if Rect2(Vector2.ZERO, VIEW).has_point(at):
			draw_circle(at, 2.5, colour)
	draw_circle(VIEW / 2.0, 3.0, Color.WHITE)
	draw_circle(VIEW / 2.0, 2.0, Color(0.9, 0.2, 0.2))
	draw_rect(Rect2(Vector2.ZERO, VIEW), BORDER, false, 1.0)

## The minimap's marks now (tests).
func marks() -> Array[Dictionary]:
	return _marks
