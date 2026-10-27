class_name RpgShopMenu
extends Control
## A shop: Buy and Sell tabs, one button per item, the gold you have, and the item's description.
## Left / right on an item's row sets how many (T13.11: from 1 to what the gold, the bag or your
## stock allows; the row shows the total), pressing it buys or sells that many. The Sell tab has
## Sell all, which asks once (the button names the gold) and sells on the second press. Opened by
## RpgUiController.open_shop (the dialogue event `open_shop:<id>`), which sets `shop` before the
## menu enters the tree. Every control is reachable with the gamepad: one vertical ring (tabs,
## items, Sell all, Back), left / right switches the tab.
##
## 1.5.0: a row of limited stock says how many are left ("Sold out" at none), the gold line names
## the shop's gold when it has a purse, and a Buy back tab (in a scene that has one) lists what
## was sold here, the latest first, for what the shop paid.
##
## 1.5.0 (T18.04): a shop that `repairs` has a Repair tab (made by this script, so the scene of an
## older game has it too) listing worn gear, worn or in the bag, with its wear and what mending it
## costs; pressing a row mends it.

signal closed

const BUY := &"buy"
const SELL := &"sell"
const BUYBACK := &"buyback"
const REPAIR := &"repair"

var shop: RpgShopDefinition = null
var mode: StringName = BUY

var _rows: Array[Button] = []
var _row_items: Dictionary = {}  # Button -> item id
var _quantity: Dictionary = {}  # item id -> how many the row is set to (none: 1)
var _row_sales: Dictionary = {}  # Button -> the index of its sale (the Buy back tab)
var _row_repairs: Dictionary = {}  # Button -> the index of its row of repair_rows (the Repair tab)
var _repair_tab: Button = null
var _sell_all_armed := false

func _ready() -> void:
	if shop == null:
		shop = RpgShopDefinition.new()  # the focus check opens the scene bare
	(get_node("%Back") as Button).pressed.connect(close)
	(get_node("%BuyTab") as Button).pressed.connect(set_mode.bind(BUY))
	(get_node("%SellTab") as Button).pressed.connect(set_mode.bind(SELL))
	var buyback_tab := buyback_tab()
	if buyback_tab != null:
		buyback_tab.pressed.connect(set_mode.bind(BUYBACK))
	if shop.repairs:
		_repair_tab = _make_repair_tab()
		_repair_tab.pressed.connect(set_mode.bind(REPAIR))
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

## The Buy back tab, or null in a scene built before 1.5 (it gets one on regeneration) or for a
## shop that does not buy back.
func buyback_tab() -> Button:
	var tab := get_node_or_null("%BuybackTab") as Button
	if tab != null and shop != null and not shop.buyback:
		tab.visible = false
		return null
	return tab

## The Repair tab, or null for a shop that does not repair.
func repair_tab() -> Button:
	return _repair_tab

## The Repair tab beside the others (the scene has none: it is the script's, T18.04).
func _make_repair_tab() -> Button:
	var sell_tab := get_node("%SellTab") as Button
	var tab := sell_tab.duplicate(0) as Button
	tab.name = "RepairTab"
	tab.unique_name_in_owner = false
	tab.text = "UI_REPAIR"
	sell_tab.get_parent().add_child(tab)
	return tab

## The Sell all button, or null in a scene built before 1.1 (it gets one on regeneration).
func sell_all_button() -> Button:
	return get_node_or_null("%SellAll") as Button

func set_mode(new_mode: StringName) -> void:
	mode = new_mode
	_quantity.clear()
	_rebuild()

func _item_ids(state: RpgGameState) -> Array[StringName]:
	if mode == BUYBACK or mode == REPAIR:
		return []  # their rows are sales (_add_buyback_rows) and worn gear (_add_repair_rows)
	if mode == BUY:
		return shop.offered_now(state)
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
	var most := mini(room, affordable)
	var left := shop.left_of(state, item_id)
	return maxi(1, mini(most, left) if left >= 0 else most)

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
	row.text = row_text(tr(def.display_name), _unit_price(state, item_id), state.inventory.count(item_id) if mode == SELL else -1, quantity_of(item_id), shop.left_of(state, item_id) if mode == BUY else -1)

## Rebuilds the item list for the current tab. `keep_index` (>= 0) refocuses that row, clamped,
## after a purchase or a sale.
func _rebuild(keep_index: int = -1) -> void:
	var list := get_node("%List") as VBoxContainer
	for child in list.get_children():
		list.remove_child(child)
		child.queue_free()
	_rows.clear()
	_row_items.clear()
	_row_sales.clear()
	_row_repairs.clear()
	_sell_all_armed = false
	var state := RpgUtil.state()
	var buy_tab := get_node("%BuyTab") as Button
	var sell_tab := get_node("%SellTab") as Button
	var back_tab := buyback_tab()
	buy_tab.set_pressed_no_signal(mode == BUY)
	sell_tab.set_pressed_no_signal(mode == SELL)
	if back_tab != null:
		back_tab.set_pressed_no_signal(mode == BUYBACK)
	if _repair_tab != null:
		_repair_tab.set_pressed_no_signal(mode == REPAIR)
	var back := get_node("%Back") as Button
	var desc := get_node("%Description") as Label
	var sell_all := sell_all_button()
	if sell_all != null:
		sell_all.visible = false
	if state == null:
		return
	(get_node("%Gold") as Label).text = gold_text(state)
	if mode == BUYBACK:
		_add_buyback_rows(state, list)
	elif mode == REPAIR:
		_add_repair_rows(state, list)
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
		b.text = row_text(tr(def.display_name), price, state.inventory.count(item_id) if mode == SELL else -1, quantity_of(item_id), shop.left_of(state, item_id) if mode == BUY else -1)
		b.pressed.connect(_on_row_pressed.bind(item_id))
		b.focus_entered.connect(_describe.bind(item_id))
		b.gui_input.connect(_on_row_input.bind(item_id))
		list.add_child(b)
		_rows.append(b)
		_row_items[b] = item_id
	if _rows.is_empty():
		var none: String = {BUY: "UI_NOTHING_FOR_SALE", SELL: "UI_NOTHING_TO_SELL", BUYBACK: "UI_NOTHING_TO_BUY_BACK", REPAIR: "UI_NOTHING_TO_REPAIR"}.get(mode, "UI_NOTHING_FOR_SALE")
		desc.text = tr(none)
	else:
		desc.text = ""
	var tabs: Array[Button] = [buy_tab, sell_tab]
	if back_tab != null:
		tabs.append(back_tab)
	if _repair_tab != null:
		tabs.append(_repair_tab)
	var ring: Array = []
	ring.append_array(tabs)
	ring.append_array(_rows)
	if sell_all != null:
		sell_all.visible = mode == SELL and shop.sell_all_value(state) > 0
		sell_all.text = tr("UI_SELL_ALL")
		if sell_all.visible:
			ring.append(sell_all)
	ring.append(back)
	RpgMenuUtil.wire_vertical(ring)
	for i in tabs.size():
		tabs[i].focus_neighbor_left = tabs[i].get_path_to(tabs[(i - 1 + tabs.size()) % tabs.size()])
		tabs[i].focus_neighbor_right = tabs[i].get_path_to(tabs[(i + 1) % tabs.size()])
	var start: Button = buy_tab if mode == BUY else (sell_tab if mode == SELL or back_tab == null else back_tab)
	if mode == REPAIR and _repair_tab != null:
		start = _repair_tab
	if not _rows.is_empty():
		start = _rows[clampi(keep_index, 0, _rows.size() - 1)] if keep_index >= 0 else _rows[0]
	start.grab_focus.call_deferred()

## "Potion — 10 G" or, when selling, "Potion x3 — 5 G" (x3: how many you hold). With a quantity
## above one the row names it and the total: "Potion (3) — 30 G", "Potion x3 (2) — 10 G". A row of
## limited stock (`left` 0 or more) says how many are left: "Potion — 10 G · 2 left", or "Sold out".
static func row_text(item_name: String, price: int, held: int = -1, qty: int = 1, left: int = -1) -> String:
	var suffix := " x%d" % held if held >= 0 else ""
	if qty > 1:
		suffix += " (%d)" % qty
	var text := "%s%s — %d %s" % [item_name, suffix, price * maxi(1, qty), TranslationServer.translate("UI_GOLD_SHORT")]
	if left == 0:
		return "%s · %s" % [text, TranslationServer.translate("UI_SOLD_OUT")]
	if left > 0:
		return "%s · %s" % [text, TranslationServer.translate("UI_SHOP_LEFT") % left]
	return text

## "Gold: 120", and the shop's own when it has a purse: "Gold: 120 · Shop's gold: 300".
func gold_text(state: RpgGameState) -> String:
	var text := "%s: %d" % [tr("UI_GOLD"), state.gold]
	var purse := shop.funds_of(state)
	if purse >= 0:
		text += " · %s: %d" % [tr("UI_SHOP_FUNDS"), purse]
	return text

## The rows of the Buy back tab: "Potion x3 — 15 G", the latest sale first.
func _add_buyback_rows(state: RpgGameState, list: VBoxContainer) -> void:
	var sales := shop.buyback_rows(state)
	for i in sales.size():
		var item_id := StringName(str(sales[i].get("item_id", "")))
		var def: RpgItemDefinition = state.items.get(item_id)
		if def == null:
			continue
		var b := Button.new()
		b.name = "Sale_%d" % i
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.icon = def.icon
		b.expand_icon = true
		b.custom_minimum_size = Vector2(0, 20)
		b.text = row_text(tr(def.display_name), RpgUtil.to_int(sales[i].get("price", 0)), RpgUtil.to_int(sales[i].get("qty", 1)))
		b.pressed.connect(_on_sale_pressed.bind(i))
		b.focus_entered.connect(_describe.bind(item_id))
		list.add_child(b)
		_rows.append(b)
		_row_items[b] = item_id
		_row_sales[b] = i

## The rows of the Repair tab: "Sword · Wear 5/40 — 3 G", worn gear first.
func _add_repair_rows(state: RpgGameState, list: VBoxContainer) -> void:
	var rows := shop.repair_rows(state)
	for i in rows.size():
		var item_id := StringName(str(rows[i].get("item_id", "")))
		var def: RpgItemDefinition = state.items.get(item_id)
		if def == null:
			continue
		var b := Button.new()
		b.name = "Repair_%d" % i
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.icon = def.icon
		b.expand_icon = true
		b.custom_minimum_size = Vector2(0, 20)
		b.text = repair_text(tr(def.display_name), RpgUtil.to_int(rows[i]["wear"]), RpgUtil.to_int(rows[i]["durability"]), RpgUtil.to_int(rows[i]["price"]))
		b.pressed.connect(_on_repair_pressed.bind(i))
		b.focus_entered.connect(_describe.bind(item_id))
		list.add_child(b)
		_rows.append(b)
		_row_items[b] = item_id
		_row_repairs[b] = i

## "Sword · Wear 5/40 — 3 G".
static func repair_text(item_name: String, wear: int, durability: int, price: int) -> String:
	return "%s · %s — %d %s" % [item_name, TranslationServer.translate("UI_WEAR") % [wear, durability], price, TranslationServer.translate("UI_GOLD_SHORT")]

## Mends row `index` of the Repair tab and says so, or why not.
func repair(index: int) -> String:
	var state := RpgUtil.state()
	if state == null:
		return RpgShopDefinition.NOT_WORN
	var rows := shop.repair_rows(state)
	var result := shop.repair(state, index)
	if result == RpgShopDefinition.OK:
		var def: RpgItemDefinition = state.items.get(StringName(str(rows[index].get("item_id", ""))))
		if def != null:
			RpgUtil.notify(tr("UI_REPAIRED") % tr(def.display_name))
	return result

func _on_repair_pressed(index: int) -> void:
	var result := repair(index)
	if result == RpgShopDefinition.OK:
		_rebuild(maxi(_rows.find(_focus_owner()), 0))
	else:
		RpgUtil.notify(refusal_text(result))

## Buys back sale `index` (the Buy back tab) and says so, or why not.
func buy_back(index: int) -> String:
	var state := RpgUtil.state()
	if state == null:
		return RpgShopDefinition.NOT_FOR_SALE
	var sales := shop.buyback_rows(state)
	var result := shop.buy_back(state, index)
	if result == RpgShopDefinition.OK:
		var def: RpgItemDefinition = state.items.get(StringName(str(sales[index].get("item_id", ""))))
		var qty := RpgUtil.to_int(sales[index].get("qty", 1))
		if def != null:
			RpgUtil.notify(tr("UI_BOUGHT") % (tr(def.display_name) if qty == 1 else "%s x%d" % [tr(def.display_name), qty]))
	return result

func _on_sale_pressed(index: int) -> void:
	var result := buy_back(index)
	if result == RpgShopDefinition.OK:
		_rebuild(maxi(_rows.find(_focus_owner()), 0))
	else:
		RpgUtil.notify(refusal_text(result))

func _describe(item_id: StringName) -> void:
	var state := RpgUtil.state()
	var def: RpgItemDefinition = state.items.get(item_id) if state != null else null
	if def == null:
		return
	var text := "%s\n%s" % [tr(def.display_name), tr(def.description)]
	if mode != BUYBACK and mode != REPAIR and max_quantity(item_id) > 1:
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
		RpgShopDefinition.SOLD_OUT:
			return tr("UI_SOLD_OUT")
		RpgShopDefinition.SHOP_CANNOT_PAY:
			return tr("UI_SHOP_CANNOT_PAY")
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
