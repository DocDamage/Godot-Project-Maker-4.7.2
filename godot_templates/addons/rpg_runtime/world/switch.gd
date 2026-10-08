class_name RpgSwitch
extends Area2D
## A floor plate the player steps on, or a lever the player pulls (interact). Its state is the flag
## `<entity_id>.on`, saved like any other flag, so gates (RpgGate.open_when), dialogue conditions and
## sequences can all react to it. Without a CollisionShape2D child it makes a square of `size`.
## Drawn in code (a plate or a lever) unless it has a child named "Visual".
## Layers: a plate watches the player (2); a lever sits on interactables (5).

enum Kind { PLATE, LEVER }

signal toggled(on: bool)

## Unique like every entity id: the flag is stored under it.
@export var entity_id: String = ""
@export var kind: Kind = Kind.PLATE
## A plate that is on only while the player stands on it (otherwise it stays on once pressed).
@export var hold: bool = false
## A lever that stays on after the first pull.
@export var once: bool = false
@export var size: Vector2 = Vector2(12, 12)

func _ready() -> void:
	collision_layer = 0
	collision_mask = 0
	if kind == Kind.LEVER:
		set_collision_layer_value(5, true)
		monitorable = true
		monitoring = false
	else:
		set_collision_mask_value(2, true)
		monitorable = false
		if not body_entered.is_connected(_on_body_entered):
			body_entered.connect(_on_body_entered)
			body_exited.connect(_on_body_exited)
	if _shape_count() == 0:
		var shape := CollisionShape2D.new()
		shape.name = "Shape"
		var rect := RectangleShape2D.new()
		rect.size = size
		shape.shape = rect
		add_child(shape)
	queue_redraw()

func _shape_count() -> int:
	var n := 0
	for child in get_children():
		if child is CollisionShape2D or child is CollisionPolygon2D:
			n += 1
	return n

func is_on() -> bool:
	var state := RpgUtil.state()
	return state != null and entity_id != "" and RpgUtil.to_bool(state.get_flag(entity_id, "on", false))

## Sets the flag (and tells everyone through Events.switch_toggled). False when nothing changed.
func set_on(on: bool) -> bool:
	var state := RpgUtil.state()
	if state == null or entity_id == "" or is_on() == on:
		return false
	state.set_flag(entity_id, "on", on)
	toggled.emit(on)
	RpgUtil.emit(&"switch_toggled", [entity_id, on])
	queue_redraw()
	return true

## A lever flips (a `once` lever only goes on).
func interact(_actor: Node = null) -> void:
	if kind != Kind.LEVER or RpgSequenceRunner.running():
		return
	if once and is_on():
		return
	set_on(not is_on())

func _on_body_entered(body: Node) -> void:
	if body.is_in_group("player"):
		set_on(true)

func _on_body_exited(body: Node) -> void:
	if hold and body.is_in_group("player"):
		set_on(false)

func _draw() -> void:
	if get_node_or_null("Visual") != null:
		return
	var on := is_on()
	if kind == Kind.PLATE:
		var rect := Rect2(-size / 2.0, size)
		draw_rect(rect, Color(0.25, 0.25, 0.28))
		draw_rect(rect.grow(-2.0), Color(0.55, 0.75, 0.55) if on else Color(0.6, 0.6, 0.62))
	else:
		draw_rect(Rect2(Vector2(-size.x / 4.0, -2.0), Vector2(size.x / 2.0, 4.0)), Color(0.3, 0.3, 0.32))
		var tip := Vector2(size.x / 3.0 if on else -size.x / 3.0, -size.y * 0.6)
		draw_line(Vector2(0, -1), tip, Color(0.55, 0.4, 0.25), 2.0)
		draw_circle(tip, 2.0, Color(0.85, 0.3, 0.3) if on else Color(0.8, 0.8, 0.8))
