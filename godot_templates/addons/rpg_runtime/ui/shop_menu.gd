class_name RpgShopMenu
extends Control
## A shop: Buy and Sell tabs, one button per item (pressing it buys or sells one), the gold you
## have, and the item's description. Opened by RpgUiController.open_shop (the dialogue event
## `open_shop:<id>`), which sets `shop` before the menu enters the tree. Every control is reachable
## with the gamepad: one vertical ring (tabs, items, Back), left / right switches the tab.

signal closed

const BUY := &"buy"
const SELL := &"sell"

var shop: RpgShopDefinition = null
var mode: StringName = BUY

var _rows: Array[Button] = []
var _row_items: Dictionary = {}  # Button -> item id

func _ready() -> void:
	if shop == null:
		shop = RpgShopDefinition.new()  # the focus check opens the scene bare
	(get_node("%Back") as Button).pressed.connect(close)
	(get_node("%BuyTab") as Button).pressed.connect(set_mode.bind(BUY))
	(get_node("%SellTab") as Button).pressed.connect(set_mode.bind(SELL))
	(get_node("%Heading") as Label).text = tr(shop.title)
	_rebuild()

## The item buttons, in order.
func rows() -> Array[Button]:
	return _rows

func item_of(button: Button) -> StringName:
	var item_id: StringName = _row_items.get(button, &"")
	return item_id

func set_mode(new_mode: StringName) -> void:
	mode = new_mode
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

## Rebuilds the item list for the current tab. `keep_index` (>= 0) refocuses that row, clamped,
## after a purchase or a sale.
func _rebuild(keep_index: int = -1) -> void:
	var list := get_node("%List") as VBoxContainer
	for child in list.get_children():
		list.remove_child(child)
		child.queue_free()
	_rows.clear()
	_row_items.clear()
	var state := RpgUtil.state()
	var buy_tab := get_node("%BuyTab") as Button
	var sell_tab := get_node("%SellTab") as Button
	buy_tab.set_pressed_no_signal(mode == BUY)
	sell_tab.set_pressed_no_signal(mode == SELL)
	var back := get_node("%Back") as Button
	var desc := get_node("%Description") as Label
	if state == null:
		return
	(get_node("%Gold") as Label).text = "%s: %d" % [tr("UI_GOLD"), state.gold]
	for item_id in _item_ids(state):
		var def: RpgItemDefinition = state.items.get(item_id)
		var price := shop.buy_price(item_id, state.items) if mode == BUY else shop.sell_price(item_id, state.items)
		if mode == SELL and price <= 0:
			continue  # the shop does not buy it
		var b := Button.new()
		b.name = "Item_%s" % item_id
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.icon = def.icon
		b.expand_icon = true
		b.custom_minimum_size = Vector2(0, 20)
		b.text = row_text(tr(def.display_name), price, state.inventory.count(item_id) if mode == SELL else -1)
		b.pressed.connect(_on_row_pressed.bind(item_id))
		b.focus_entered.connect(_describe.bind(item_id))
		list.add_child(b)
		_rows.append(b)
		_row_items[b] = item_id
	if _rows.is_empty():
		desc.text = tr("UI_NOTHING_FOR_SALE") if mode == BUY else tr("UI_NOTHING_TO_SELL")
	else:
		desc.text = ""
	var ring: Array = [buy_tab, sell_tab]
	ring.append_array(_rows)
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

## "Potion — 10 G" or, when selling, "Potion x3 — 5 G".
static func row_text(item_name: String, price: int, held: int = -1) -> String:
	var suffix := " x%d" % held if held >= 0 else ""
	return "%s%s — %d %s" % [item_name, suffix, price, TranslationServer.translate("UI_GOLD_SHORT")]

func _describe(item_id: StringName) -> void:
	var state := RpgUtil.state()
	var def: RpgItemDefinition = state.items.get(item_id) if state != null else null
	if def == null:
		return
	(get_node("%Description") as Label).text = "%s\n%s" % [tr(def.display_name), tr(def.description)]

func _on_row_pressed(item_id: StringName) -> void:
	var result := transact(item_id)
	if result == RpgShopDefinition.OK:
		_rebuild(maxi(_rows.find(_focus_owner()), 0))
	else:
		RpgUtil.notify(refusal_text(result))

func _focus_owner() -> Control:
	var viewport := get_viewport()
	return viewport.gui_get_focus_owner() if viewport != null else null

## Buys or sells one of `item_id` (by the current tab) and tells the player what happened. Returns
## the result code of RpgShopDefinition ("" for success).
func transact(item_id: StringName) -> String:
	var state := RpgUtil.state()
	if state == null:
		return RpgShopDefinition.NOT_FOR_SALE
	var def: RpgItemDefinition = state.items.get(item_id)
	var result := shop.buy(state, item_id) if mode == BUY else shop.sell(state, item_id)
	if result == RpgShopDefinition.OK and def != null:
		RpgUtil.notify(tr("UI_BOUGHT" if mode == BUY else "UI_SOLD") % tr(def.display_name))
	return result

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
