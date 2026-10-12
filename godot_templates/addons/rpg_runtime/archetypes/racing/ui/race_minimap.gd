class_name RpgRaceMinimap
extends RpgMinimap
## The minimap of a race, in the bottom-right corner of the HUD: the minimap of the other
## kinds (its size, its frame, the setting that turns it off) showing the whole track, not a
## part of a map round the player. The road is drawn from the track's cells (RpgTrackSurfaces),
## a pixel a cell, fitted into the view; every car is a dot, the player's a larger one.

const ROAD := Color(200 / 255.0, 200 / 255.0, 215 / 255.0)
const LINE := Color(1, 1, 1)
const RIVAL_DOT := Color(0.45, 0.75, 1.0)
const PLAYER_DOT := Color(1.0, 0.25, 0.2)
## The frame of the view that is left free round the track.
const PAD := 4.0

var _track: ImageTexture = null
var _track_rows := PackedStringArray()
var _area := Rect2()
var _dots: Array[Dictionary] = []

## The picture of a track: a pixel a cell, the road light, its start line white, the rest clear.
static func picture(rows: PackedStringArray) -> Image:
	var width := 1
	for row in rows:
		width = maxi(width, row.length())
	var image := Image.create(width, maxi(1, rows.size()), false, Image.FORMAT_RGBA8)
	for y in rows.size():
		for x in rows[y].length():
			var letter := rows[y][x]
			if letter == "s":
				image.set_pixel(x, y, LINE)
			elif letter != "g" and letter != ".":
				image.set_pixel(x, y, ROAD)
	return image

## Where a track of `cells` cells is drawn in a view of `view` px: as large as fits inside its
## frame with the shape kept, in the middle.
static func fit(cells: Vector2i, view: Vector2) -> Rect2:
	if cells.x <= 0 or cells.y <= 0:
		return Rect2(view / 2.0, Vector2.ZERO)
	var room := view - Vector2(PAD, PAD) * 2.0
	var scale_px := minf(room.x / cells.x, room.y / cells.y)
	var drawn := Vector2(cells) * scale_px
	return Rect2((view - drawn) / 2.0, drawn)

## Where a point of the track (px from its top-left corner) is in the view.
static func spot(at: Vector2, track_px: Vector2, area: Rect2) -> Vector2:
	if track_px.x <= 0.0 or track_px.y <= 0.0:
		return area.position
	return area.position + at / track_px * area.size

func _ready() -> void:
	super._ready()
	set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	offset_left = -VIEW.x - MARGIN
	offset_top = -VIEW.y - MARGIN
	offset_right = -MARGIN
	offset_bottom = -MARGIN

func _process(_delta: float) -> void:
	refresh()  # every frame: the cars are fast

## Reads the track that is driven and its cars again; hides itself outside a race.
func refresh() -> void:
	var settings := RpgUtil.settings()
	var mode := RpgArcadeMode.current()
	var race: RpgRace = (mode as RpgRacingMode).current_race() if mode is RpgRacingMode else null
	if (settings != null and not settings.minimap) or race == null or race.get_parent() == null:
		visible = false
		return
	show_track(race.get_parent().get_node_or_null("Surfaces") as RpgTrackSurfaces, race.cars, race.player)

## Shows `surfaces` with a dot for each of `cars` (none: hidden).
func show_track(surfaces: RpgTrackSurfaces, cars: Array[RpgCar], player: RpgCar) -> void:
	if surfaces == null or surfaces.rows.is_empty():
		visible = false
		return
	visible = true
	if _track == null or surfaces.rows != _track_rows:
		_track_rows = surfaces.rows.duplicate()
		_track = ImageTexture.create_from_image(picture(surfaces.rows))
	var cells := surfaces.size_cells()
	_area = fit(cells, VIEW)
	var track_px := Vector2(cells) * surfaces.cell
	var origin := RpgUtil.world_position(surfaces)
	_dots.clear()
	for car in cars:
		if not is_instance_valid(car) or not car.visible:
			continue
		var at := RpgUtil.world_position(car) - origin
		if not Rect2(Vector2.ZERO, track_px).has_point(at):
			continue  # a car that was taken off the track
		_dots.append({"position": spot(at, track_px, _area), "player": car == player})
	queue_redraw()

## The dots of the cars now: `position` in the view and whether it is the `player` (tests).
func dots() -> Array[Dictionary]:
	return _dots

## The picture of the track that is shown, or null (tests).
func track_texture() -> ImageTexture:
	return _track

func _draw() -> void:
	if _track == null:
		return
	draw_rect(Rect2(Vector2.ZERO, VIEW), Color(0, 0, 0, 0.55))
	draw_texture_rect(_track, _area, false)
	for dot in _dots:
		if not RpgUtil.to_bool(dot["player"]):
			var at: Vector2 = dot["position"]
			draw_circle(at, 2.0, RIVAL_DOT)
	for dot in _dots:
		if RpgUtil.to_bool(dot["player"]):
			var mine: Vector2 = dot["position"]
			draw_circle(mine, 3.0, Color.WHITE)
			draw_circle(mine, 2.0, PLAYER_DOT)
	draw_rect(Rect2(Vector2.ZERO, VIEW), BORDER, false, 1.0)
