class_name RpgWeatherOverlay
extends Control
## What falls over the screen in the farm's weather (T17.11): a child of a CanvasLayer of
## RpgFarmWeather, as large as the screen. It draws one of two things:
##
## * `fall(texture, frames, fps, passes)`: a picture of `frames` cells in a row, one cell at a
##   time, repeated over the whole screen in both directions; `passes` 2 draws it once more,
##   half a cell off, for a storm.
## * `flakes()`: snow without a picture, as white dots that drift down.

const FALL := "fall"
const FLAKES := "flakes"
const FLAKE_COUNT := 70
const FLAKE_COLOR := Color(1.0, 1.0, 1.0, 0.85)
const SECOND_PASS := Color(1.0, 1.0, 1.0, 0.6)

## What is drawn: FALL, FLAKES, or "" for nothing.
var mode := ""
var texture: Texture2D = null
var frames := 1
var fps := 9.0
var passes := 1

var _time := 0.0

func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	set_process(false)

## Lets a picture fall. Nothing is drawn without one.
func fall(picture: Texture2D, frame_count: int, speed: float, pass_count: int = 1) -> void:
	texture = picture
	frames = maxi(1, frame_count)
	fps = maxf(0.0, speed)
	passes = clampi(pass_count, 1, 2)
	_start(FALL if picture != null else "")

## Lets drawn snow fall.
func flakes() -> void:
	texture = null
	_start(FLAKES)

func stop() -> void:
	_start("")

func _start(what: String) -> void:
	mode = what
	set_process(mode != "")
	queue_redraw()

func _process(delta: float) -> void:
	_time += delta
	queue_redraw()

## The cell of the picture that is shown now.
func frame() -> int:
	return int(_time * fps) % maxi(1, frames)

## The size of one cell of the picture.
func cell_size() -> Vector2:
	if texture == null:
		return Vector2.ZERO
	var whole := texture.get_size()
	return Vector2(whole.x / maxi(1, frames), whole.y)

func _draw() -> void:
	if mode == FALL:
		_draw_fall(Vector2.ZERO, Color.WHITE)
		if passes > 1:
			_draw_fall(cell_size() * 0.5, SECOND_PASS)
	elif mode == FLAKES:
		_draw_flakes()

func _draw_fall(shift: Vector2, colour: Color) -> void:
	var cell := cell_size()
	if cell.x < 1.0 or cell.y < 1.0:
		return
	var source := Rect2(Vector2(cell.x * frame(), 0.0), cell)
	var y := -shift.y
	while y < size.y:
		var x := -shift.x
		while x < size.x:
			draw_texture_rect_region(texture, Rect2(Vector2(x, y), cell), source, colour)
			x += cell.x
		y += cell.y

func _draw_flakes() -> void:
	if size.x < 1.0 or size.y < 1.0:
		return
	for i in FLAKE_COUNT:
		var speed := 14.0 + (i % 5) * 5.0
		var sway := sin(_time * 0.8 + i) * 6.0
		var x := fposmod(i * 97.0 + sway, size.x)
		var y := fposmod(i * 53.0 + _time * speed, size.y)
		var dot := 2.0 if i % 3 == 0 else 1.0
		draw_rect(Rect2(x, y, dot, dot), FLAKE_COLOR)
