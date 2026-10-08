class_name RpgGate
extends StaticBody2D
## A barrier on the map (bars, a portcullis, a locked door that is not a map exit). It opens for good
## when the player interacts holding `key_item` (the flag `<entity_id>.unlocked` remembers it), and
## it is open while `open_when` holds (a dialogue condition such as "flag:cellar_switch_001.on", so
## switches, quests, variables and sequences can open it). An open gate lets everyone through and is
## hidden. Without a CollisionShape2D child it makes a rectangle of `size` standing on its origin; it
## is drawn in code unless it has a child named "Visual". Layers: world (1), and interactables (5)
## when it takes a key.

signal changed(open: bool)

## Unique like every entity id: `unlocked` is stored under it.
@export var entity_id: String = ""
## The item that unlocks it (usually a KEY item); empty = no lock.
@export var key_item: StringName = &""
## The key is used up when it unlocks the gate.
@export var consume_key: bool = true
## Open while this dialogue condition holds; empty = only the key opens it.
@export var open_when: String = ""
@export var size: Vector2 = Vector2(16, 16)

var open := false
var _applied := false

func _ready() -> void:
	collision_layer = 0
	set_collision_layer_value(1, true)
	if key_item != &"":
		set_collision_layer_value(5, true)
	if _shape_count() == 0:
		var shape := CollisionShape2D.new()
		shape.name = "Shape"
		var rect := RectangleShape2D.new()
		rect.size = size
		shape.shape = rect
		shape.position = Vector2(0, -size.y / 2.0)  # the origin is the gate's foot, for Y-sorting
		add_child(shape)
	var bus := RpgUtil.events()
	if bus != null and not bus.entity_state_changed.is_connected(_on_state_changed):
		bus.entity_state_changed.connect(_on_state_changed)
		bus.variable_changed.connect(_on_variable_changed)
	refresh()

func _shape_count() -> int:
	var n := 0
	for child in get_children():
		if child is CollisionShape2D or child is CollisionPolygon2D:
			n += 1
	return n

func is_unlocked() -> bool:
	var state := RpgUtil.state()
	return state != null and entity_id != "" and RpgUtil.to_bool(state.get_flag(entity_id, "unlocked", false))

## True when it should be open now: unlocked, or its condition holds.
func should_open() -> bool:
	return is_unlocked() or (open_when != "" and RpgCondition.evaluate(open_when))

## Opens or closes it to match should_open().
func refresh() -> void:
	set_open(should_open())

func set_open(value: bool) -> void:
	if value == open and _applied:
		return
	var was := open
	open = value
	_applied = true
	for child in get_children():
		if child is CollisionShape2D:
			(child as CollisionShape2D).set_deferred("disabled", value)
		elif child is CollisionPolygon2D:
			(child as CollisionPolygon2D).set_deferred("disabled", value)
	visible = not value
	if value != was:
		changed.emit(value)
		RpgUtil.emit(&"gate_changed", [entity_id, value])
		if value:
			RpgUtil.emit(&"door_used", [entity_id])  # the door sound

## The player interacts with the closed gate: the key unlocks it, else a message says what it needs.
func interact(_actor: Node = null) -> void:
	if open or RpgSequenceRunner.running():
		return
	try_unlock()

## Unlocks with the key when the player holds it. False (and a message) otherwise.
func try_unlock() -> bool:
	var state := RpgUtil.state()
	if state == null:
		return false
	if key_item == &"":
		RpgUtil.notify(String(TranslationServer.translate("UI_LOCKED")))
		return false
	var key_name := item_name(state, key_item)
	if not state.inventory.has(key_item):
		RpgUtil.notify(String(TranslationServer.translate("UI_LOCKED_NEED")) % key_name)
		return false
	if consume_key:
		state.inventory.remove(key_item, 1)
	if entity_id != "":
		state.set_flag(entity_id, "unlocked", true)
	RpgUtil.notify(String(TranslationServer.translate("UI_UNLOCKED")) % key_name)
	refresh()
	return true

## The shown name of an item (its display name, else its id).
static func item_name(state: RpgGameState, item_id: StringName) -> String:
	var def: RpgItemDefinition = state.items.get(item_id)
	if def != null and def.display_name != "":
		return String(TranslationServer.translate(def.display_name))
	return String(item_id).capitalize()

func _on_state_changed(_entity: String, _key: String, _value: Variant) -> void:
	refresh()

func _on_variable_changed(_name: StringName, _value: int) -> void:
	refresh()

func _draw() -> void:
	if get_node_or_null("Visual") != null:
		return
	var rect := Rect2(Vector2(-size.x / 2.0, -size.y), size)
	draw_rect(rect, Color(0.18, 0.16, 0.15))
	var bars := maxi(2, int(size.x / 5.0))
	for i in bars:
		var x := rect.position.x + (i + 0.5) * size.x / bars
		draw_line(Vector2(x, rect.position.y + 1.0), Vector2(x, rect.end.y - 1.0), Color(0.55, 0.55, 0.6), 1.5)
	if key_item != &"":
		draw_circle(rect.get_center(), 2.0, Color(0.9, 0.75, 0.2))
