class_name RpgTargetCursor
extends Control
## A blinking arrow that points down at the selected target.

const BLINK_SECONDS := 0.25
const SIZE := 5.0

var _timer := 0.0
var _lit := true
var _active := false

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false

## Shows the arrow with its tip at `tip` (canvas coordinates).
func point_at(tip: Vector2) -> void:
	position = tip
	_active = true
	_lit = true
	_timer = 0.0
	visible = true
	queue_redraw()

func hide_cursor() -> void:
	_active = false
	visible = false

func is_pointing() -> bool:
	return _active

func _process(delta: float) -> void:
	if not _active:
		return
	_timer += delta
	if _timer >= BLINK_SECONDS:
		_timer = 0.0
		_lit = not _lit
		queue_redraw()

func _draw() -> void:
	if not _lit:
		return
	var points := PackedVector2Array([Vector2(0, 0), Vector2(-SIZE, -SIZE * 1.4), Vector2(SIZE, -SIZE * 1.4)])
	draw_colored_polygon(points, Color(1.0, 0.9, 0.3))
	draw_polyline(PackedVector2Array([points[0], points[1], points[2], points[0]]), Color(0.1, 0.1, 0.1), 1.0)
