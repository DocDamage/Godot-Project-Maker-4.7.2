class_name RpgFarmHud
extends CanvasLayer
## What the farm adds to the HUD (T17.04): the hotbar with the held slot and the energy as a
## bar. A child of the farm's mode, beside the basic HUD (the money). The time, the day, the
## season and the weather are T17.11.
##
## The scene (recipes/farm/mode_recipe.gd) has `%EnergyBar` and `%Slots` with a child a slot,
## each with an `Icon` (TextureRect) and a `Qty` (Label).

## Under the dialogue box (10) and the menus: the hotbar lies at the bottom, where they open.
const LAYER := 5
const HELD := Color(1.0, 1.0, 1.0, 1.0)
const NOT_HELD := Color(0.6, 0.6, 0.65, 0.85)

var _mode: RpgFarmMode = null

func _ready() -> void:
	layer = LAYER
	_mode = get_parent() as RpgFarmMode
	if _mode != null:  # its parts are made in its `_ready`, which runs after this one
		if _mode.is_node_ready():
			_bind()
		else:
			_mode.ready.connect(_bind)
	var bus := RpgUtil.events()
	if bus != null:
		bus.map_entered.connect(_on_map)
	var router := RpgUtil.router()
	if router != null:
		router.map_changed.connect(_on_map)
	refresh()

func _bind() -> void:
	_mode.ensure_parts()
	_mode.hotbar.changed.connect(refresh)
	_mode.energy.changed.connect(_on_energy)
	refresh()

func _on_energy(_value: int, _maximum: int) -> void:
	refresh()

func _on_map(_id: StringName) -> void:
	refresh()

## Shows the energy and the ten slots as they are now. Hidden while no map is shown.
func refresh() -> void:
	var router := RpgUtil.router()
	visible = router != null and router.get("current_map") != null
	if _mode == null or _mode.energy == null or _mode.hotbar == null:
		return
	var bar := get_node_or_null("%EnergyBar") as ProgressBar
	if bar != null:
		bar.max_value = _mode.energy.max_energy
		bar.value = _mode.energy.value
	var slots := get_node_or_null("%Slots")
	if slots == null:
		return
	var state := RpgUtil.state()
	for i in slots.get_child_count():
		var slot := slots.get_child(i) as Control
		if slot == null:
			continue
		var item := _mode.hotbar.item_at(i)
		var def: RpgItemDefinition = state.items.get(item) if state != null else null
		var icon := slot.get_node_or_null("Icon") as TextureRect
		if icon != null:
			icon.texture = def.icon if def != null else null
		var qty := slot.get_node_or_null("Qty") as Label
		if qty != null:
			var count := _mode.hotbar.qty_at(i)
			qty.text = str(count) if count > 1 else ""
		slot.modulate = HELD if i == _mode.hotbar.held else NOT_HELD
