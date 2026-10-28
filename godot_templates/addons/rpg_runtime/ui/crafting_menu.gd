class_name RpgCraftingMenu
extends Control
## The crafting window (1.5.0, T18.14). Built in code. A tab *By hand* and, when it was opened at a
## station (RpgStation.interact), one for that station. The recipes of the tab are a grid: the
## known ones by their first result's icon and name, the others as a silhouette ("???") whose
## description is their hint. *Craftable now* shows only what the bag makes now. The recipe in
## focus is described under the grid: what it makes, its ingredients had and lacking ("Herb
## 1/2"), and its time. Left and right on a recipe set how many; pressing it crafts (by hand) or
## queues (at a station). A station's tab lists its queue with the progress of each craft
## (pressing one cancels it) and has Collect all for its tray. Keyboard, mouse and gamepad: one
## vertical ring, left and right on the tabs switch the tab. Pause → Crafting opens it by hand.

signal closed

const HAND := ""
const GRID_COLUMNS := 4
const OPEN_NAME := "CraftingMenu"
const LAYER := 60

## The station it was opened at, or null (by hand).
var station: RpgStation = null
## The tab shown: HAND, or the station's `station_id`.
var tab := HAND
var only_craftable := false

var _tabs: HBoxContainer
var _filter: CheckButton
var _grid: GridContainer
var _detail: Label
var _queue_box: VBoxContainer
var _collect: Button
var _back: Button
var _cells: Array[Button] = []
var _cell_recipes: Dictionary = {}  # Button -> RpgRecipe
var _amount: Dictionary = {}  # recipe id -> how many
var _queue_rows: Array[Button] = []
var _layer: CanvasLayer = null

## Opens the window over the game, paused, at `at` (a station) or by hand (null). Returns it.
static func open(at: RpgStation = null) -> RpgCraftingMenu:
	var tree := RpgUtil.tree()
	if tree == null:
		return null
	var layer := CanvasLayer.new()
	layer.layer = LAYER
	layer.name = OPEN_NAME
	layer.process_mode = Node.PROCESS_MODE_ALWAYS
	var menu := RpgCraftingMenu.new()
	menu.station = at
	menu.tab = String(at.station_id) if at != null else HAND
	menu._layer = layer
	layer.add_child(menu)
	tree.root.add_child(layer)
	tree.paused = true
	RpgUtil.emit(&"game_paused", [true])
	return menu

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.85)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var panel := PanelContainer.new()
	center.add_child(panel)
	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(320, 0)
	panel.add_child(box)
	var heading := Label.new()
	heading.text = tr("UI_CRAFTING")
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(heading)
	_tabs = HBoxContainer.new()
	_tabs.name = "Tabs"
	box.add_child(_tabs)
	_tab_button("Hand", tr("UI_CRAFT_BY_HAND"), HAND)
	if station != null:
		_tab_button("Station", station.tab_title(), String(station.station_id))
	_filter = CheckButton.new()
	_filter.name = "Craftable"
	_filter.text = tr("UI_CRAFTABLE_NOW")
	_filter.toggled.connect(func(on: bool) -> void:
		only_craftable = on
		rebuild())
	box.add_child(_filter)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(310, 90)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	box.add_child(scroll)
	_grid = GridContainer.new()
	_grid.name = "Grid"
	_grid.columns = GRID_COLUMNS
	scroll.add_child(_grid)
	_detail = Label.new()
	_detail.name = "Detail"
	_detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail.custom_minimum_size = Vector2(300, 48)
	box.add_child(_detail)
	_queue_box = VBoxContainer.new()
	_queue_box.name = "Queue"
	box.add_child(_queue_box)
	_collect = Button.new()
	_collect.name = "CollectAll"
	_collect.text = tr("UI_COLLECT_ALL")
	_collect.pressed.connect(collect_all)
	box.add_child(_collect)
	_back = Button.new()
	_back.name = "Back"
	_back.text = tr("UI_BACK")
	_back.pressed.connect(close)
	box.add_child(_back)
	rebuild()

func _tab_button(node_name: String, text: String, which: String) -> void:
	var b := Button.new()
	b.name = node_name
	b.text = text
	b.toggle_mode = true
	b.pressed.connect(set_tab.bind(which))
	_tabs.add_child(b)

func set_tab(which: String) -> void:
	tab = which
	rebuild()

func _state() -> RpgGameState:
	return RpgUtil.state()

## The recipe buttons of the grid, in order.
func cells() -> Array[Button]:
	return _cells

func recipe_of(cell: Button) -> RpgRecipe:
	var found: RpgRecipe = _cell_recipes.get(cell)
	return found

func queue_rows() -> Array[Button]:
	return _queue_rows

func amount_of(made: RpgRecipe) -> int:
	var state := _state()
	var most := RpgCrafting.most(state, made) if state != null else 1
	return clampi(RpgUtil.to_int(_amount.get(made.id, 1)), 1, maxi(1, most))

func set_amount(made: RpgRecipe, amount: int) -> void:
	_amount[made.id] = amount
	describe(made)

func rebuild(keep_index: int = -1) -> void:
	for child in _grid.get_children():
		_grid.remove_child(child)
		child.queue_free()
	_cells.clear()
	_cell_recipes.clear()
	for b in _tabs.get_children():
		var button := b as Button
		button.set_pressed_no_signal((button.name == "Hand") == (tab == HAND))
	var state := _state()
	if state == null:
		return
	var at: Variant = StringName(tab)
	for made in RpgCrafting.recipes(at):
		var is_known := RpgCrafting.known(state, made)
		if only_craftable and (not is_known or RpgCrafting.check(state, made) != RpgCrafting.OK):
			continue
		var cell := Button.new()
		cell.name = "Recipe_%s" % made.id
		cell.custom_minimum_size = Vector2(72, 22)
		cell.clip_text = true
		var first := _first_result(state, made)
		if is_known:
			cell.text = tr(made.title) if made.title != "" else String(made.id)
			cell.icon = first.icon if first != null else null
		else:
			cell.text = "???"
			if first != null and first.icon != null:
				cell.icon = first.icon
				cell.self_modulate = Color(0, 0, 0, 0.8)  # a silhouette
		cell.expand_icon = true
		cell.pressed.connect(_on_cell_pressed.bind(made))
		cell.focus_entered.connect(describe.bind(made))
		cell.gui_input.connect(_on_cell_input.bind(made))
		_grid.add_child(cell)
		_cells.append(cell)
		_cell_recipes[cell] = made
	_build_queue(state)
	_detail.text = tr("UI_NO_RECIPES") if _cells.is_empty() else ""
	var ring: Array = []
	ring.append_array(_tabs.get_children())
	ring.append(_filter)
	ring.append_array(_cells)
	ring.append_array(_queue_rows)
	if _collect.visible:
		ring.append(_collect)
	ring.append(_back)
	RpgMenuUtil.wire_vertical(ring)
	var tabs := _tabs.get_children()
	for i in tabs.size():
		var t := tabs[i] as Control
		t.focus_neighbor_left = t.get_path_to(tabs[(i - 1 + tabs.size()) % tabs.size()])
		t.focus_neighbor_right = t.get_path_to(tabs[(i + 1) % tabs.size()])
	var start: Control = _cells[clampi(keep_index, 0, _cells.size() - 1)] if not _cells.is_empty() else (tabs[0] as Control)
	if start.is_inside_tree():
		start.grab_focus.call_deferred()
	if not _cells.is_empty():
		describe(recipe_of(_cells[clampi(keep_index, 0, _cells.size() - 1)]))

func _first_result(state: RpgGameState, made: RpgRecipe) -> RpgItemDefinition:
	var keys := made.results.keys()
	keys.sort()
	var def: RpgItemDefinition = state.items.get(StringName(str(keys[0]))) if not keys.is_empty() else null
	return def

func _build_queue(state: RpgGameState) -> void:
	for child in _queue_box.get_children():
		_queue_box.remove_child(child)
		child.queue_free()
	_queue_rows.clear()
	var at_station := station != null and tab != HAND
	_collect.visible = at_station
	if not at_station:
		return
	RpgCrafting.update(state, station.key())
	var mine := RpgCrafting.station_state(state, station.key())
	var jobs: Array = mine["queue"]
	for i in jobs.size():
		var job := RpgUtil.to_dict(jobs[i])
		var made := RpgCrafting.recipe(StringName(str(job["recipe"])))
		var b := Button.new()
		b.name = "Job_%d" % i
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.text = queue_text(made.title if made != null else str(job["recipe"]), RpgUtil.to_int(job.get("amount", 1)), RpgCrafting.progress(state, job))
		b.pressed.connect(cancel.bind(i))
		_queue_box.add_child(b)
		_queue_rows.append(b)
	var tray: Array = mine["tray"]
	_collect.disabled = tray.is_empty()
	_collect.text = tr("UI_COLLECT_ALL") + (" (%d)" % tray.size() if not tray.is_empty() else "")

## "Potion x2 — 40%".
func queue_text(title: String, amount: int, done: float) -> String:
	var what := tr(title) + (" x%d" % amount if amount > 1 else "")
	return "%s — %d%%" % [what, roundi(done * 100.0)]

## What the recipe makes, its ingredients had and lacking, its time; the hint of one not known.
func describe(made: RpgRecipe) -> void:
	_detail.text = detail_text(made)

func detail_text(made: RpgRecipe) -> String:
	var state := _state()
	if state == null or made == null:
		return ""
	if not RpgCrafting.known(state, made):
		return tr(made.hint) if made.hint != "" else tr("UI_RECIPE_UNKNOWN")
	var amount := amount_of(made)
	var lines: PackedStringArray = []
	var makes: PackedStringArray = []
	for row: Variant in RpgRecipe.rows(made.results, amount):
		makes.append(_item_text(state, RpgUtil.to_dict(row)))
	lines.append(tr("UI_RECIPE_MAKES") % ", ".join(makes))
	var needs: PackedStringArray = []
	for row: Variant in RpgRecipe.rows(made.ingredients, amount):
		var wanted := RpgUtil.to_dict(row)
		var item_id := StringName(str(wanted["item_id"]))
		needs.append("%s %d/%d" % [_name(state, item_id), mini(state.inventory.count(item_id), RpgUtil.to_int(wanted["qty"])), RpgUtil.to_int(wanted["qty"])])
	lines.append(tr("UI_RECIPE_NEEDS") % ", ".join(needs))
	if made.minutes > 0 and made.station != &"":
		lines.append(tr("UI_RECIPE_TIME") % (made.minutes * amount))
	if RpgCrafting.most(state, made) > 1:
		lines.append(tr("UI_SHOP_QUANTITY_HINT"))
	return "\n".join(lines)

func _item_text(state: RpgGameState, row: Dictionary) -> String:
	var qty := RpgUtil.to_int(row["qty"])
	var item_name := _name(state, StringName(str(row["item_id"])))
	return item_name if qty == 1 else "%s x%d" % [item_name, qty]

func _name(state: RpgGameState, item_id: StringName) -> String:
	var def: RpgItemDefinition = state.items.get(item_id)
	return tr(def.display_name) if def != null else String(item_id)

## Left and right on a recipe change how many.
func _on_cell_input(event: InputEvent, made: RpgRecipe) -> void:
	var step := 0
	if event.is_action_pressed("ui_left", true):
		step = -1
	elif event.is_action_pressed("ui_right", true):
		step = 1
	if step == 0:
		return
	var state := _state()
	var most := maxi(1, RpgCrafting.most(state, made)) if state != null else 1
	var next := amount_of(made) + step
	set_amount(made, most if next < 1 else (1 if next > most else next))
	get_viewport().set_input_as_handled()

func _on_cell_pressed(made: RpgRecipe) -> void:
	var index := _cells.find(_focus_owner())
	var result := make(made, amount_of(made))
	if result == RpgCrafting.OK:
		_amount.erase(made.id)
		rebuild(maxi(index, 0))
	else:
		RpgUtil.notify(refusal_text(result))

## Crafts (by hand) or queues (at the station of the tab) `amount` of a recipe and says so.
func make(made: RpgRecipe, amount: int = 1) -> String:
	var state := _state()
	if state == null:
		return RpgCrafting.UNKNOWN
	var result := ""
	if tab == HAND:
		result = RpgCrafting.craft(state, made, amount)
		if result == RpgCrafting.OK:
			RpgUtil.notify(tr("UI_CRAFTED") % _item_text(state, RpgUtil.to_dict(RpgRecipe.rows(made.results, amount)[0])))
	else:
		result = RpgCrafting.queue(state, station.key(), station.station_id, made, amount)
		if result == RpgCrafting.OK:
			RpgUtil.notify(tr("UI_QUEUED") % (tr(made.title) if made.title != "" else String(made.id)))
	return result

## Cancels craft `index` of the station's queue (its ingredients come back).
func cancel(index: int) -> bool:
	var state := _state()
	if state == null or station == null:
		return false
	var done := RpgCrafting.cancel(state, station.key(), index)
	rebuild()
	return done

func collect_all() -> int:
	var state := _state()
	if state == null or station == null:
		return 0
	var taken := RpgCrafting.collect_all(state, station.key())
	rebuild()
	return taken

func refusal_text(result: String) -> String:
	match result:
		RpgCrafting.NO_ROOM:
			return tr("UI_NO_ROOM")
		RpgCrafting.MISSING:
			return tr("UI_RECIPE_MISSING")
		RpgCrafting.NOT_KNOWN:
			return tr("UI_RECIPE_UNKNOWN")
	return tr("UI_CANNOT_TRADE")

func _focus_owner() -> Control:
	var viewport := get_viewport()
	return viewport.gui_get_focus_owner() if viewport != null else null

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

## Closes the window; one opened over the game unpauses it (one opened from the pause menu
## leaves the menu paused).
func close() -> void:
	if _layer != null:
		get_tree().paused = false
		RpgUtil.emit(&"game_paused", [false])
		_layer.queue_free()
	else:
		queue_free()
	closed.emit()
