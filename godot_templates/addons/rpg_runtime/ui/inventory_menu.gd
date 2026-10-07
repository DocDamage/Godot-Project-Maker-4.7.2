class_name RpgInventoryMenu
extends Control
## A grid of item slots (icon + quantity), a description panel and a Use button.

const COLUMNS := 6

var _selected: StringName = &""
var _buttons: Array = []
var _extra_buttons: Array[Button] = []  # added by the archetype's combat mode (customize_inventory_menu)

func _ready() -> void:
	(get_node("%Use") as Button).pressed.connect(_on_use)
	(get_node("%Back") as Button).pressed.connect(close)
	_refresh()
	_focus_first.call_deferred()
	var router := RpgUtil.router()
	var mode: Variant = router.get("combat") if router != null else null
	if mode != null and mode.has_method("customize_inventory_menu"):
		mode.call("customize_inventory_menu", self)

## The item the player has selected (focused or pressed) in the grid, or &"".
func selected_item() -> StringName:
	return _selected

## Adds a button to the Use / Back row (after Use) and includes it in the focus ring.
func add_extra_button(button: Button) -> void:
	var use_button := get_node("%Use") as Button
	var row := use_button.get_parent()
	row.add_child(button)
	row.move_child(button, use_button.get_index() + 1 + _extra_buttons.size())
	_extra_buttons.append(button)
	_wire_extra_buttons()

func _wire_extra_buttons() -> void:
	var use_button := get_node("%Use") as Button
	var back_button := get_node("%Back") as Button
	var ring: Array[Button] = [use_button]
	ring.append_array(_extra_buttons)
	ring.append(back_button)
	for i in ring.size():
		var b := ring[i]
		b.focus_neighbor_left = b.get_path_to(ring[(i - 1 + ring.size()) % ring.size()])
		b.focus_neighbor_right = b.get_path_to(ring[(i + 1) % ring.size()])
	for b in _extra_buttons:
		b.focus_neighbor_top = use_button.focus_neighbor_top  # siblings: the same relative path
		b.focus_neighbor_bottom = b.get_path_to(back_button)
		b.disabled = use_button.disabled

func _refresh() -> void:
	var grid := get_node("%Grid") as GridContainer
	grid.columns = COLUMNS
	for child in grid.get_children():
		grid.remove_child(child)
		child.queue_free()
	_buttons.clear()
	var state := RpgUtil.state()
	if state != null:
		for slot in state.inventory.slots:
			var id: StringName = slot["item_id"]
			var def: RpgItemDefinition = state.items.get(id)
			if def == null:
				push_error("[RPG-DATA] unknown item %s" % id)
				continue
			var b := Button.new()
			b.name = "Slot_%s" % id
			b.custom_minimum_size = Vector2(40, 40)
			b.icon = def.icon
			b.expand_icon = true
			b.text = "x%d" % int(slot["qty"])
			b.alignment = HORIZONTAL_ALIGNMENT_RIGHT
			b.pressed.connect(_select.bind(id))
			b.focus_entered.connect(_select.bind(id))
			grid.add_child(b)
			_buttons.append(b)
	RpgMenuUtil.wire_grid(_buttons, COLUMNS)
	var use_button := get_node("%Use") as Button
	var back_button := get_node("%Back") as Button
	# Use and Back sit below the grid; the grid's last row leads down to Use.
	if not _buttons.is_empty():
		for b in _buttons:
			(b as Button).focus_neighbor_bottom = (b as Button).get_path_to(use_button)
		use_button.focus_neighbor_top = use_button.get_path_to(_buttons[0])
	else:
		use_button.focus_neighbor_top = use_button.get_path_to(back_button)
	use_button.focus_neighbor_bottom = use_button.get_path_to(back_button)
	back_button.focus_neighbor_top = back_button.get_path_to(use_button)
	back_button.focus_neighbor_bottom = back_button.get_path_to(_buttons[0] if not _buttons.is_empty() else use_button)
	use_button.focus_neighbor_left = use_button.get_path_to(back_button)
	use_button.focus_neighbor_right = use_button.get_path_to(back_button)
	back_button.focus_neighbor_left = back_button.get_path_to(use_button)
	back_button.focus_neighbor_right = back_button.get_path_to(use_button)
	use_button.disabled = _buttons.is_empty()
	_wire_extra_buttons()
	var desc := get_node("%Description") as Label
	desc.text = tr("UI_NO_ITEMS") if _buttons.is_empty() else tr("UI_SELECT_ITEM")
	_selected = &""

func _focus_first() -> void:
	if not _buttons.is_empty():
		(_buttons[0] as Button).grab_focus()
	else:
		(get_node("%Back") as Button).grab_focus()

func _select(id: StringName) -> void:
	_selected = id
	var state := RpgUtil.state()
	var def: RpgItemDefinition = state.items.get(id) if state != null else null
	if def == null:
		return
	(get_node("%Description") as Label).text = "%s\n%s" % [tr(def.display_name), tr(def.description)]

func _on_use() -> void:
	var state := RpgUtil.state()
	if state == null or _selected == &"":
		return
	if not state.inventory.use(_selected, state.player_stats):
		RpgUtil.notify("Cannot use that now")
		return
	_refresh()
	_focus_first.call_deferred()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

func close() -> void:
	queue_free()
