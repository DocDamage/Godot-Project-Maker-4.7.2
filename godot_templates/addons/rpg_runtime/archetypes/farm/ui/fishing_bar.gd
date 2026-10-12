class_name RpgFishingBar
extends Control
## The bar of a cast (T17.10), drawn beside the farmer on a layer of its own (RpgFishing makes
## it at the first bite). At the bite it shows a mark over the farmer; then the bar: the fish's
## mark moves along it, the zone rises while `use` is held and sinks when it is let go, and the
## meter beside it fills while the zone is over the mark. It only shows what RpgFishing says.

const BACK := Color(0.08, 0.08, 0.1, 0.85)
const WATER := Color(0.2, 0.36, 0.55, 0.95)
const ZONE_COLOR := Color(0.45, 0.85, 0.4, 0.9)
const ZONE_OFF := Color(0.45, 0.85, 0.4, 0.45)
const MARK_COLOR := Color(1.0, 0.9, 0.5)
const METER_COLOR := Color(0.95, 0.8, 0.25)
const BITE_COLOR := Color(1.0, 0.9, 0.2)
const WIDTH := 10.0
const METER_WIDTH := 4.0
const GAP := 2.0
const PAD := 2.0

var fishing: RpgFishing = null
## How far over the farmer's feet the mark of a bite stands, in px of the world (RpgFishing
## sets it from the size of a tile).
var lift := 28.0

var _farmer: Node2D = null

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)

## The bar stands beside this farmer (the middle of the screen without one).
func follow(farmer: Node2D) -> void:
	_farmer = farmer

func _process(_delta: float) -> void:
	if visible:
		queue_redraw()

## How long the bar is on a screen of this height.
static func length_for(screen_height: float) -> float:
	return clampf(screen_height * 0.4, 48.0, 128.0)

## Where on a bar of `length` px a place of the bar (0 at its bottom, 1 at its top) is, from
## its top.
static func offset_of(place: float, length: float) -> float:
	return (1.0 - clampf(place, 0.0, 1.0)) * length

func _draw() -> void:
	if fishing == null or not is_instance_valid(fishing):
		return
	var view := get_viewport_rect().size
	var feet := view * 0.5
	var zoom := 1.0
	if _farmer != null and is_instance_valid(_farmer) and _farmer.is_inside_tree():
		var on_screen := _farmer.get_global_transform_with_canvas()
		feet = on_screen.origin
		zoom = on_screen.get_scale().y
	if fishing.state == RpgFishing.BITE:
		# an exclamation mark in a dark box, over the farmer's head
		var box := Rect2(feet + Vector2(-5.0, -lift * zoom - 16.0), Vector2(10.0, 16.0))
		draw_rect(box, BACK)
		draw_rect(Rect2(box.position + Vector2(3.5, 2.0), Vector2(3.0, 8.0)), BITE_COLOR)
		draw_rect(Rect2(box.position + Vector2(3.5, 11.5), Vector2(3.0, 3.0)), BITE_COLOR)
		return
	if fishing.state != RpgFishing.REELING:
		return
	var length := length_for(view.y)
	var whole := Vector2(WIDTH + GAP + METER_WIDTH + PAD * 2.0, length + PAD * 2.0)
	var at := feet + Vector2(lift * zoom * 0.5 + 6.0, -length * 0.5 - 8.0)
	at.x = clampf(at.x, 0.0, maxf(0.0, view.x - whole.x))
	at.y = clampf(at.y, 0.0, maxf(0.0, view.y - whole.y))
	draw_rect(Rect2(at, whole), BACK)
	var top := at + Vector2(PAD, PAD)
	draw_rect(Rect2(top, Vector2(WIDTH, length)), WATER)
	var zone_px := RpgFishing.ZONE * length
	var zone_top := offset_of(fishing.zone + RpgFishing.ZONE * 0.5, length)
	draw_rect(Rect2(top + Vector2(0.0, zone_top), Vector2(WIDTH, zone_px)), ZONE_COLOR if fishing.is_on_mark() else ZONE_OFF)
	var mark_y := clampf(offset_of(fishing.mark, length) - 1.5, 0.0, length - 3.0)
	draw_rect(Rect2(top + Vector2(1.0, mark_y), Vector2(WIDTH - 2.0, 3.0)), MARK_COLOR)
	var filled := clampf(fishing.meter, 0.0, 1.0) * length
	var meter_at := top + Vector2(WIDTH + GAP, 0.0)
	draw_rect(Rect2(meter_at, Vector2(METER_WIDTH, length)), WATER.darkened(0.5))
	draw_rect(Rect2(meter_at + Vector2(0.0, length - filled), Vector2(METER_WIDTH, filled)), METER_COLOR)
