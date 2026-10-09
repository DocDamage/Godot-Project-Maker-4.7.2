class_name RpgMetroidvaniaHud
extends CanvasLayer
## The metroidvania's HUD (layer 20): health as pips (one per HP_PER_PIP hit points; the last one
## is drawn part full), the abilities of the world as icons that light up when they are granted,
## the weapon worn and the gold. Refreshed by Events, shown only while a map is active. Pickup
## toasts are the shared notification's.

const HP_PER_PIP := 4
const PIP := Vector2(9, 9)
const PIP_GAP := 2.0
const ICON := Vector2(12, 12)
const MARGIN := Vector2(8, 8)
const FULL := Color(0.9, 0.25, 0.3)
const EMPTY := Color(0.2, 0.18, 0.24)
const RIM := Color(0.05, 0.04, 0.08)
const DIM := Color(1, 1, 1, 0.25)

## The abilities this world has, in order (set by the recipe from the stored plan).
@export var abilities: PackedStringArray = PackedStringArray()
## The icon of each ability, in the same order; a missing one is a generated glyph.
@export var icons: Array[Texture2D] = []
## A picture for one pip (the UI pack's); null draws a square.
@export var pip_texture: Texture2D = null

var _canvas: Control = null
var _gold: Label = null
var _weapon: Label = null
var _glyphs: Dictionary = {}

func _ready() -> void:
	layer = 20
	_canvas = Control.new()
	_canvas.name = "Canvas"
	_canvas.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_canvas.set_anchors_preset(Control.PRESET_FULL_RECT)
	_canvas.draw.connect(_draw_canvas)
	add_child(_canvas)
	_gold = _label("Gold", Vector2(MARGIN.x, MARGIN.y + PIP.y + ICON.y + 10.0))
	_weapon = _label("Weapon", Vector2(MARGIN.x, MARGIN.y + PIP.y + ICON.y + 24.0))
	var bus := RpgUtil.events()
	if bus != null:
		for signal_name: StringName in [&"player_damaged", &"player_healed", &"gold_changed", &"level_up",
				&"equipment_changed", &"map_entered", &"game_loaded", &"ability_granted"]:
			if bus.has_signal(signal_name):
				bus.connect(signal_name, _on_event)
	var router := RpgUtil.router()
	if router != null:
		router.map_changed.connect(_on_event)
	refresh()

func _label(label_name: String, at: Vector2) -> Label:
	var label := Label.new()
	label.name = label_name
	label.position = at
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_canvas.add_child(label)
	return label

func _on_event(_a: Variant = null, _b: Variant = null) -> void:
	refresh()

## How many pips a maximum of `max_hp` shows.
static func pip_count(max_hp: int) -> int:
	return ceili(maxf(0.0, max_hp) / HP_PER_PIP)

## How full pip `index` is (0..1) at `hp` hit points.
static func pip_fill(hp: int, index: int) -> float:
	return clampf((hp - index * HP_PER_PIP) / float(HP_PER_PIP), 0.0, 1.0)

## The abilities shown and whether each is granted: [[id, granted], ...].
func ability_states() -> Array:
	var out: Array = []
	var state := RpgUtil.state()
	for id in abilities:
		out.append([id, state != null and state.has_ability(StringName(id))])
	return out

## The text of the weapon worn, or "" without one.
static func weapon_text(state: RpgGameState) -> String:
	if state == null:
		return ""
	var worn := state.equipped_in(state.player_actor_id, &"weapon")
	if worn == &"":
		return ""
	var def: RpgItemDefinition = state.items.get(worn)
	return RpgRealtimeText.item_name(def, worn)

func refresh() -> void:
	var state := RpgUtil.state()
	var router := RpgUtil.router()
	visible = router != null and router.get("current_map") != null
	if state == null or _canvas == null:
		return
	_gold.text = "%s: %d" % [tr("UI_GOLD"), RpgUtil.to_int(state.gold)]
	_weapon.text = weapon_text(state)
	_weapon.visible = _weapon.text != ""
	_canvas.queue_redraw()

func _icon(index: int) -> Texture2D:
	if index < icons.size() and icons[index] != null:
		return icons[index]
	var id := abilities[index]
	if not _glyphs.has(id):
		_glyphs[id] = RpgAbilities.glyph_texture(StringName(id), int(ICON.x))
	return _glyphs[id]

func _draw_canvas() -> void:
	var state := RpgUtil.state()
	if state == null:
		return
	var stats: RpgStats = state.player_stats
	var at := MARGIN
	for i in pip_count(RpgUtil.max_hp(stats)):
		var box := Rect2(at + Vector2(i * (PIP.x + PIP_GAP), 0.0), PIP)
		var fill := pip_fill(stats.hp, i)
		if pip_texture != null:
			_canvas.draw_texture_rect(pip_texture, box, false, DIM)
			if fill > 0.0:
				var part := Rect2(box.position, Vector2(box.size.x * fill, box.size.y))
				_canvas.draw_texture_rect_region(pip_texture, part, Rect2(Vector2.ZERO, Vector2(pip_texture.get_width() * fill, pip_texture.get_height())))
			continue
		_canvas.draw_rect(box, RIM)
		_canvas.draw_rect(box.grow(-1.0), EMPTY)
		if fill > 0.0:
			var inner := box.grow(-1.0)
			_canvas.draw_rect(Rect2(inner.position, Vector2(inner.size.x * fill, inner.size.y)), FULL)
	var row := MARGIN + Vector2(0.0, PIP.y + 5.0)
	var states := ability_states()
	for i in states.size():
		var granted: bool = states[i][1]
		_canvas.draw_texture_rect(_icon(i), Rect2(row + Vector2(i * (ICON.x + 3.0), 0.0), ICON), false, Color.WHITE if granted else DIM)
