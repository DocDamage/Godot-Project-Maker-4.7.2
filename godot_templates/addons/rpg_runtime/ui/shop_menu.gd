class_name RpgShopMenu
extends Control
## A shop: Buy and Sell tabs, one button per item, the gold you have, and the item's description.
## Left / right on an item's row sets how many (T13.11: from 1 to what the gold, the bag or your
## stock allows; the row shows the total), pressing it buys or sells that many. The Sell tab has
## Sell all, which asks once (the button names the gold) and sells on the second press. Opened by
## RpgUiController.open_shop (the dialogue event `open_shop:<id>`), which sets `shop` before the
## menu enters the tree. Every control is reachable with the gamepad: one vertical ring (tabs,
## items, Sell all, Back), left / right switches the tab.

signal closed

const BUY := &"buy"
const SELL := &"sell"

var shop: RpgShopDefinition = null
var mode: StringName = BUY

var _rows: Array[Button] = []
var _row_items: Dictionary = {}  # Button -> item id
var _quantity: Dictionary = {}  # item id -> how many the row is set to (none: 1)
var _sell_all_armed := false

func _ready() -> void:
	if shop == null:
		shop = RpgShopDefinition.new()  # the focus check opens the scene bare
	(get_node("%Back") as Button).pressed.connect(close)
	(get_node("%BuyTab") as Button).pressed.connect(set_mode.bind(BUY))
	(get_node("%SellTab") as Button).pressed.connect(set_mode.bind(SELL))
	(get_node("%Heading") as Label).text = tr(shop.title)
	var sell_all := sell_all_button()
	if sell_all != null:
		sell_all.pressed.connect(_on_sell_all_pressed)
		sell_all.focus_exited.connect(_disarm_sell_all)
	_rebuild()

## The item buttons, in order.
func rows() -> Array[Button]:
	return _rows

func item_of(button: Button) -> StringName:
	var item_id: StringName = _row_items.get(button, &"")
	return item_id

## The Sell all button, or null in a scene built before 1.1 (it gets one on regeneration).
func sell_all_button() -> Button:
	return get_node_or_null("%SellAll") as Button

func set_mode(new_mode: StringName) -> void:
	mode = new_mode
	_quantity.clear()
	_rebuild()

func _item_ids(state: RpgGameState) -> Array[StringName]:
	if mode == BUY:
		return shop.offered(state.items)
	var out: Array[StringName] = []
	for slot in state.inventory.slots:
		var item_id: StringName = slot["item_id"]
		if state.items.has(item_id) and not out.has(item_id):
			out.append(item_id)
	return out

func _unit_price(state: RpgGameState, item_id: StringName) -> int:
	return shop.buy_price(item_id, state.items) if mode == BUY else shop.sell_price(item_id, state.items)

## The most of `item_id` one press can trade on this tab, at least 1 (a row you cannot afford
## still shows 1, and pressing it says why not).
func max_quantity(item_id: StringName) -> int:
	var state := RpgUtil.state()
	if state == null:
		return 1
	if mode == SELL:
		return maxi(1, state.inventory.count(item_id))
	var room := state.inventory.room_for(item_id)
	var price := shop.buy_price(item_id, state.items)
	var affordable := room if price <= 0 else floori(float(state.gold) / float(price))
	return maxi(1, mini(room, affordable))

## How many the row of `item_id` is set to.
func quantity_of(item_id: StringName) -> int:
	return clampi(RpgUtil.to_int(_quantity.get(item_id, 1)), 1, max_quantity(item_id))

func set_quantity(item_id: StringName, qty: int) -> void:
	_quantity[item_id] = clampi(qty, 1, max_quantity(item_id))
	_refresh_row(item_id)

## One step down or up; past either end it wraps (1 <-> the most), so the most is one press away.
func change_quantity(item_id: StringName, step: int) -> void:
	var most := max_quantity(item_id)
	var qty := quantity_of(item_id) + step
	if qty < 1:
		qty = most
	elif qty > most:
		qty = 1
	set_quantity(item_id, qty)

func _row_of(item_id: StringName) -> Button:
	for row in _rows:
		if _row_items.get(row, &"") == item_id:
			return row
	return null

func _refresh_row(item_id: StringName) -> void:
	var state := RpgUtil.state()
	var row := _row_of(item_id)
	if state == null or row == null:
		return
	var def: RpgItemDefinition = state.items.get(item_id)
	row.text = row_text(tr(def.display_name), _unit_price(state, item_id), state.inventory.count(item_id) if mode == SELL else -1, quantity_of(item_id))

## Rebuilds the item list for the current tab. `keep_index` (>= 0) refocuses that row, clamped,
## after a purchase or a sale.
func _rebuild(keep_index: int = -1) -> void:
	var list := get_node("%List") as VBoxContainer
	for child in list.get_children():
		list.remove_child(child)
		child.queue_free()
	_rows.clear()
	_row_items.clear()
	_sell_all_armed = false
	var state := RpgUtil.state()
	var buy_tab := get_node("%BuyTab") as Button
	var sell_tab := get_node("%SellTab") as Button
	buy_tab.set_pressed_no_signal(mode == BUY)
	sell_tab.set_pressed_no_signal(mode == SELL)
	var back := get_node("%Back") as Button
	var desc := get_node("%Description") as Label
	var sell_all := sell_all_button()
	if sell_all != null:
		sell_all.visible = false
	if state == null:
		return
	(get_node("%Gold") as Label).text = "%s: %d" % [tr("UI_GOLD"), state.gold]
	for item_id in _item_ids(state):
		var def: RpgItemDefinition = state.items.get(item_id)
		var price := _unit_price(state, item_id)
		if mode == SELL and price <= 0:
			continue  # the shop does not buy it
		var b := Button.new()
		b.name = "Item_%s" % item_id
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.icon = def.icon
		b.expand_icon = true
		b.custom_minimum_size = Vector2(0, 20)
		b.text = row_text(tr(def.display_name), price, state.inventory.count(item_id) if mode == SELL else -1, quantity_of(item_id))
		b.pressed.connect(_on_row_pressed.bind(item_id))
		b.focus_entered.connect(_describe.bind(item_id))
		b.gui_input.connect(_on_row_input.bind(item_id))
		list.add_child(b)
		_rows.append(b)
		_row_items[b] = item_id
	if _rows.is_empty():
		desc.text = tr("UI_NOTHING_FOR_SALE") if mode == BUY else tr("UI_NOTHING_TO_SELL")
	else:
		desc.text = ""
	var ring: Array = [buy_tab, sell_tab]
	ring.append_array(_rows)
	if sell_all != null:
		sell_all.visible = mode == SELL and shop.sell_all_value(state) > 0
		sell_all.text = tr("UI_SELL_ALL")
		if sell_all.visible:
			ring.append(sell_all)
	ring.append(back)
	RpgMenuUtil.wire_vertical(ring)
	buy_tab.focus_neighbor_left = buy_tab.get_path_to(sell_tab)
	buy_tab.focus_neighbor_right = buy_tab.get_path_to(sell_tab)
	sell_tab.focus_neighbor_left = sell_tab.get_path_to(buy_tab)
	sell_tab.focus_neighbor_right = sell_tab.get_path_to(buy_tab)
	var start: Button = buy_tab if mode == BUY else sell_tab
	if not _rows.is_empty():
		start = _rows[clampi(keep_index, 0, _rows.size() - 1)] if keep_index >= 0 else _rows[0]
	start.grab_focus.call_deferred()

## "Potion — 10 G" or, when selling, "Potion x3 — 5 G" (x3: how many you hold). With a quantity
## above one the row names it and the total: "Potion (3) — 30 G", "Potion x3 (2) — 10 G".
static func row_text(item_name: String, price: int, held: int = -1, qty: int = 1) -> String:
	var suffix := " x%d" % held if held >= 0 else ""
	if qty > 1:
		suffix += " (%d)" % qty
	return "%s%s — %d %s" % [item_name, suffix, price * maxi(1, qty), TranslationServer.translate("UI_GOLD_SHORT")]

func _describe(item_id: StringName) -> void:
	var state := RpgUtil.state()
	var def: RpgItemDefinition = state.items.get(item_id) if state != null else null
	if def == null:
		return
	var text := "%s\n%s" % [tr(def.display_name), tr(def.description)]
	if max_quantity(item_id) > 1:
		text += "\n" + tr("UI_SHOP_QUANTITY_HINT")
	(get_node("%Description") as Label).text = text

## Left and right on a row change its quantity instead of moving the focus.
func _on_row_input(event: InputEvent, item_id: StringName) -> void:
	var step := 0
	if event.is_action_pressed("ui_left", true):
		step = -1
	elif event.is_action_pressed("ui_right", true):
		step = 1
	if step == 0:
		return
	change_quantity(item_id, step)
	var row := _row_of(item_id)
	if row != null:
		row.accept_event()

func _on_row_pressed(item_id: StringName) -> void:
	var result := transact(item_id, quantity_of(item_id))
	if result == RpgShopDefinition.OK:
		_quantity.erase(item_id)
		_rebuild(maxi(_rows.find(_focus_owner()), 0))
	else:
		RpgUtil.notify(refusal_text(result))

func _focus_owner() -> Control:
	var viewport := get_viewport()
	return viewport.gui_get_focus_owner() if viewport != null else null

## Buys or sells `qty` of `item_id` (by the current tab) and tells the player what happened.
## Returns the result code of RpgShopDefinition ("" for success).
func transact(item_id: StringName, qty: int = 1) -> String:
	var state := RpgUtil.state()
	if state == null:
		return RpgShopDefinition.NOT_FOR_SALE
	var def: RpgItemDefinition = state.items.get(item_id)
	var result := shop.buy(state, item_id, qty) if mode == BUY else shop.sell(state, item_id, qty)
	if result == RpgShopDefinition.OK and def != null:
		var what := tr(def.display_name) if qty == 1 else "%s x%d" % [tr(def.display_name), qty]
		RpgUtil.notify(tr("UI_BOUGHT" if mode == BUY else "UI_SOLD") % what)
	return result

## The first press asks (the button names the gold), the second one sells. Moving away from the
## button takes the question back.
func _on_sell_all_pressed() -> void:
	var state := RpgUtil.state()
	var button := sell_all_button()
	if state == null or button == null:
		return
	if not _sell_all_armed:
		_sell_all_armed = true
		button.text = tr("UI_SELL_ALL_CONFIRM") % shop.sell_all_value(state)
		return
	sell_all()

func _disarm_sell_all() -> void:
	var button := sell_all_button()
	if _sell_all_armed and button != null:
		button.text = tr("UI_SELL_ALL")
	_sell_all_armed = false

## Sells everything the shop buys, without asking (the button asks). Returns the gold it paid.
func sell_all() -> int:
	var state := RpgUtil.state()
	if state == null:
		return 0
	var gold := shop.sell_all(state)
	if gold > 0:
		RpgUtil.notify(tr("UI_SOLD_ALL") % gold)
	_quantity.clear()
	_rebuild()
	return gold

func refusal_text(result: String) -> String:
	match result:
		RpgShopDefinition.NOT_ENOUGH_GOLD:
			return tr("UI_NOT_ENOUGH_GOLD")
		RpgShopDefinition.NO_ROOM:
			return tr("UI_NO_ROOM")
		_:
			return tr("UI_CANNOT_TRADE")

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

## Unpauses the tree and removes the menu.
func close() -> void:
	get_tree().paused = false
	RpgUtil.emit(&"game_paused", [false])
	closed.emit()
	queue_free()
