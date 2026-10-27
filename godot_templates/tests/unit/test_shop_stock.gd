extends RefCounted
## Shops of 1.5.0: limited stock that restocks by the clock of play or by the calendar, a shop's
## gold, wares rolled from a loot table, buying back what was sold, the save, and the menu's rows
## and Buy back tab.

const Fixtures := preload("../lib/fixtures.gd")
const UiRecipes := preload("res://builder/recipes/ui_recipes.gd")
const SceneUtil := preload("res://builder/lib/scene_util.gd")

const MENU_TMP := "user://test_shop_stock_menu.tscn"

func _item(id: StringName, value: int, max_stack: int = 99) -> RpgItemDefinition:
	var def := Fixtures.item(id, max_stack)
	def.value = value
	def.display_name = String(id).capitalize()
	return def

func _state() -> Node:
	var state := Fixtures.install_state({
		&"potion": _item(&"potion", 10),
		&"elixir": _item(&"elixir", 40),
		&"herb": _item(&"herb", 4),
	})
	state.new_game()
	state.inventory.slots.clear()
	state.gold = 100
	return state

func _shop(rows: Array = [{"item_id": "potion", "price": -1, "qty": 3}, {"item_id": "elixir", "price": -1}]) -> RpgShopDefinition:
	var shop := RpgShopDefinition.new()
	shop.id = &"corner"
	var stock: Array[Dictionary] = []
	for row: Dictionary in rows:
		stock.append(row)
	shop.stock = stock
	return shop

func test_a_limited_row_sells_out_until_the_shop_restocks(t) -> void:
	var state := _state()
	var shop := _shop()
	shop.restock_minutes = 10
	t.eq(shop.left_of(state, &"potion"), 3)
	t.eq(shop.left_of(state, &"elixir"), -1, "a row without qty never runs out")
	t.eq(shop.buy(state, &"potion", 2), RpgShopDefinition.OK)
	t.eq(shop.left_of(state, &"potion"), 1)
	t.eq(shop.buy(state, &"potion", 2), RpgShopDefinition.SOLD_OUT, "only one left")
	t.eq([state.gold, state.inventory.count(&"potion")], [80, 2], "and nothing changed")
	t.eq(shop.buy(state, &"potion"), RpgShopDefinition.OK)
	t.eq(shop.buy(state, &"potion"), RpgShopDefinition.SOLD_OUT)
	state.playtime_s = 9.0 * 60.0
	t.eq(shop.left_of(state, &"potion"), 0, "not yet ten minutes")
	state.playtime_s = 10.0 * 60.0
	t.eq(shop.left_of(state, &"potion"), 3, "restocked")
	_end()

func test_a_shop_that_never_restocks_stays_sold_out(t) -> void:
	var state := _state()
	var shop := _shop([{"item_id": "potion", "price": -1, "qty": 1}])
	shop.buy(state, &"potion")
	state.playtime_s = 1.0e6
	t.eq(shop.left_of(state, &"potion"), 0)
	_end()

func test_a_shop_restocks_each_morning_of_a_calendar(t) -> void:
	var state := _state()
	var calendar := RpgCalendar.ensure()
	var shop := _shop([{"item_id": "potion", "price": -1, "qty": 1}])
	shop.restock_each_day = true
	shop.buy(state, &"potion")
	t.eq(shop.left_of(state, &"potion"), 0)
	calendar.day += 1
	t.eq(shop.left_of(state, &"potion"), 1, "a new day, a new potion")
	calendar.get_parent().remove_child(calendar)
	calendar.free()
	_end()

func test_a_shop_pays_out_of_its_gold(t) -> void:
	var state := _state()
	var shop := _shop()
	shop.funds = 12
	state.inventory.add(&"elixir", 2)  # 20 each
	t.eq(shop.funds_of(state), 12)
	t.eq(shop.sell(state, &"elixir"), RpgShopDefinition.SHOP_CANNOT_PAY)
	t.eq(state.inventory.count(&"elixir"), 2, "nothing changed")
	t.eq(shop.buy(state, &"potion"), RpgShopDefinition.OK)
	t.eq(shop.funds_of(state), 22, "what you pay adds to its gold")
	t.eq(shop.sell(state, &"elixir"), RpgShopDefinition.OK)
	t.eq([shop.funds_of(state), state.gold], [2, 110])
	t.eq(shop.sell_all_value(state), 2, "no more than it has")
	t.eq(_shop().funds_of(state), -1, "a shop without a purse never runs out")
	_end()

func test_wares_are_rolled_at_each_restock(t) -> void:
	var state := _state()
	var shop := _shop([{"item_id": "potion", "price": -1}])
	shop.restock_minutes = 5
	var table := RpgLootTable.new()
	var entries: Array[Dictionary] = [{"item_id": "herb", "chance": 1.0, "min": 2, "max": 2}]
	table.entries = entries
	shop.wares = table
	t.eq(shop.offered_now(state), [&"potion", &"herb"] as Array[StringName])
	t.eq(shop.offered(state.items), [&"potion"] as Array[StringName], "offered() is still the stock")
	t.eq(shop.left_of(state, &"herb"), 2)
	t.eq(shop.buy_price(&"herb", state.items), 4, "at its own value")
	t.eq(shop.buy(state, &"herb", 2), RpgShopDefinition.OK)
	t.eq(shop.buy(state, &"herb"), RpgShopDefinition.SOLD_OUT)
	state.playtime_s = 300.0
	t.eq(shop.left_of(state, &"herb"), 2, "rolled again")
	t.eq(shop.buy(state, &"elixir"), RpgShopDefinition.NOT_FOR_SALE, "neither stock nor wares")
	_end()

func test_what_was_sold_can_be_bought_back_until_the_restock(t) -> void:
	var state := _state()
	var shop := _shop()
	shop.restock_minutes = 10
	state.inventory.add(&"elixir", 3)
	shop.sell(state, &"elixir", 2)
	shop.sell(state, &"elixir")
	t.eq(state.gold, 160)
	var rows := shop.buyback_rows(state)
	t.eq(rows.size(), 2)
	t.eq([rows[0]["item_id"], rows[0]["qty"], rows[0]["price"]], ["elixir", 1, 20], "the latest first")
	t.eq(shop.buy_back(state, 1), RpgShopDefinition.OK)
	t.eq([state.gold, state.inventory.count(&"elixir")], [120, 2], "for what the shop paid")
	t.eq(shop.buyback_rows(state).size(), 1)
	t.eq(shop.buy_back(state, 5), RpgShopDefinition.NOT_FOR_SALE)
	state.gold = 0
	t.eq(shop.buy_back(state, 0), RpgShopDefinition.NOT_ENOUGH_GOLD)
	state.playtime_s = 600.0
	t.eq(shop.buyback_rows(state).size(), 0, "the shop sold it on")
	var none := _shop()
	none.buyback = false
	state.inventory.add(&"potion")
	none.sell(state, &"potion")
	t.eq(none.buyback_rows(state).size(), 0, "a shop that does not buy back")
	_end()

func test_buyback_keeps_the_latest_sales(t) -> void:
	var state := _state()
	var shop := _shop()
	state.inventory.add(&"herb", 20)
	for i in RpgShopDefinition.BUYBACK_MAX + 3:
		shop.sell(state, &"herb")
	t.eq(shop.buyback_rows(state).size(), RpgShopDefinition.BUYBACK_MAX)
	_end()

func test_the_shops_survive_a_save(t) -> void:
	var state := _state()
	var shop := _shop()
	shop.buy(state, &"potion", 2)
	state.inventory.add(&"elixir")
	shop.sell(state, &"elixir")
	var back: Dictionary = JSON.parse_string(JSON.stringify(state.to_dict()))
	state.new_game()
	t.eq(shop.left_of(state, &"potion"), 3, "a new game: every shop as stocked")
	state.from_dict(back)
	t.eq(shop.left_of(state, &"potion"), 1)
	t.eq(shop.buyback_rows(state).size(), 1)
	state.new_game()
	t.ok(not state.to_dict().has("shops"), "nothing kept, nothing saved")
	back.erase("shops")
	state.from_dict(back)
	t.eq(shop.left_of(state, &"potion"), 3, "an older save")
	_end()

# ------------------------------------------------------------------ the menu

func _menu(shop: RpgShopDefinition) -> RpgShopMenu:
	var root: Node = UiRecipes.new().call("_build_shop_menu")
	SceneUtil.save_scene(root, MENU_TMP)
	var menu := (load(MENU_TMP) as PackedScene).instantiate() as RpgShopMenu
	menu.shop = shop
	Fixtures.tree().root.add_child(menu)
	if not menu.is_node_ready():
		menu._ready()
	return menu

func test_the_menu_shows_what_is_left_and_the_shops_gold(t) -> void:
	var english := Fixtures.install_english()
	var state := _state()
	var shop := _shop([{"item_id": "potion", "price": -1, "qty": 2}])
	shop.funds = 50
	var menu := _menu(shop)
	t.eq(menu.rows()[0].text, "Potion — 10 G · 2 left")
	t.eq((menu.get_node("%Gold") as Label).text, "Gold: 100 · Shop's gold: 50")
	menu.change_quantity(&"potion", 1)
	menu.change_quantity(&"potion", 1)
	t.eq(menu.quantity_of(&"potion"), 1, "no more than are left: it wraps")
	menu.set_quantity(&"potion", 2)
	menu.rows()[0].pressed.emit()
	t.eq(menu.rows()[0].text, "Potion — 10 G · Sold out")
	t.eq((menu.get_node("%Gold") as Label).text, "Gold: 80 · Shop's gold: 70")
	menu.free()
	_end()
	Fixtures.uninstall_english(english)

func test_the_buy_back_tab(t) -> void:
	var english := Fixtures.install_english()
	var state := _state()
	var shop := _shop()
	state.inventory.add(&"elixir", 2)
	var menu := _menu(shop)
	t.ok(menu.buyback_tab() != null)
	menu.set_mode(RpgShopMenu.BUYBACK)
	t.eq(menu.rows().size(), 0)
	t.eq((menu.get_node("%Description") as Label).text, "Nothing to buy back")
	menu.set_mode(RpgShopMenu.SELL)
	menu.set_quantity(&"elixir", 2)
	menu.rows()[0].pressed.emit()
	menu.set_mode(RpgShopMenu.BUYBACK)
	t.eq(menu.rows().size(), 1)
	t.eq(menu.rows()[0].text, "Elixir x2 — 40 G")
	menu.rows()[0].pressed.emit()
	t.eq([state.inventory.count(&"elixir"), state.gold], [2, 100])
	t.eq(menu.rows().size(), 0)
	var all := RpgMenuUtil.focusables(menu)
	var first: Control = all[0]
	t.eq(String(first.get_node(first.focus_neighbor_left).name), "BuybackTab", "left from Buy wraps to Buy back")
	menu.free()
	var none := _shop()
	none.buyback = false
	menu = _menu(none)
	t.ok(menu.buyback_tab() == null, "a shop that does not buy back has no tab")
	menu.free()
	_end()
	Fixtures.uninstall_english(english)

# ------------------------------------------------------------------ repair (T18.04)

func _worn_state() -> Node:
	var state := _state()
	var sword := _item(&"sword", 40, 1)
	sword.category = RpgItemDefinition.Category.WEAPON
	sword.durability = 20
	state.items[&"sword"] = sword
	var shield := _item(&"shield", 30, 1)
	shield.category = RpgItemDefinition.Category.ARMOR
	shield.durability = 10
	state.items[&"shield"] = shield
	state.equipment.clear()
	state.inventory.add(&"sword")
	state.equip(&"hero", &"sword")
	state.wear(&"hero", &"weapon", 10)
	state.inventory.add_with(&"shield", {"wear": 5})
	return state

func test_a_shop_that_repairs_mends_worn_gear_for_gold(t) -> void:
	var state := _worn_state()
	var shop := _shop()
	t.eq(shop.repair_rows(state), [] as Array[Dictionary], "a shop that does not repair")
	shop.repairs = true
	shop.funds = 50
	var rows := shop.repair_rows(state)
	t.eq(rows.size(), 2)
	t.eq([rows[0]["item_id"], rows[0]["wear"], rows[0]["durability"], rows[0]["price"]], ["sword", 10, 20, 10], "half worn: a quarter of its value")
	t.eq([rows[1]["item_id"], rows[1]["price"], rows[1]["bag_index"]], ["shield", 8, 0], "the bag's, rounded up")
	state.gold = 5
	t.eq(shop.repair(state, 0), RpgShopDefinition.NOT_ENOUGH_GOLD)
	t.eq(state.wear_of(&"hero", &"weapon"), [10, 20] as Array[int], "nothing changed")
	state.gold = 100
	t.eq(shop.repair(state, 0), RpgShopDefinition.OK)
	t.eq(state.wear_of(&"hero", &"weapon"), [0, 20] as Array[int])
	t.eq([state.gold, shop.funds_of(state)], [90, 60], "paid to the shop")
	t.eq(shop.repair(state, 0), RpgShopDefinition.OK, "the shield is the first row now")
	t.eq(state.inventory.data_at(0), {}, "mended: a plain slot")
	t.eq(shop.repair_rows(state), [] as Array[Dictionary])
	t.eq(shop.repair(state, 0), RpgShopDefinition.NOT_WORN)
	_end()

func test_the_repair_tab(t) -> void:
	var english := Fixtures.install_english()
	var state := _worn_state()
	var shop := _shop()
	var menu := _menu(shop)
	t.ok(menu.repair_tab() == null, "no tab for a shop that does not repair")
	menu.free()
	shop.repairs = true
	menu = _menu(shop)
	t.ok(menu.repair_tab() != null, "made by the script: the scene has none")
	menu.set_mode(RpgShopMenu.REPAIR)
	t.eq(menu.rows().size(), 2)
	t.eq(menu.rows()[0].text, "Sword · Wear 10/20 — 10 G")
	menu.rows()[0].pressed.emit()
	t.eq(state.wear_of(&"hero", &"weapon"), [0, 20] as Array[int])
	t.eq(menu.rows().size(), 1)
	menu.rows()[0].pressed.emit()
	t.eq((menu.get_node("%Description") as Label).text, "Nothing to repair")
	var all := RpgMenuUtil.focusables(menu)
	var first: Control = all[0]
	t.eq(String(first.get_node(first.focus_neighbor_left).name), "RepairTab", "left from Buy wraps to Repair")
	menu.free()
	_end()
	Fixtures.uninstall_english(english)

func _end() -> void:
	Fixtures.uninstall_state()
