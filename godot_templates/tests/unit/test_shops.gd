extends RefCounted
## Shops (T12.46): the definition's prices, buying and selling, the dialogue event, the menu and its
## focus chain.

const Fixtures := preload("../lib/fixtures.gd")
const UiRecipes := preload("res://builder/recipes/ui_recipes.gd")
const SceneUtil := preload("res://builder/lib/scene_util.gd")
const DataRecipe := preload("res://builder/recipes/data_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")

const MENU_TMP := "user://test_shop_menu.tscn"

func _item(id: StringName, value: int, category: RpgItemDefinition.Category = RpgItemDefinition.Category.CONSUMABLE, max_stack: int = 99) -> RpgItemDefinition:
	var def := Fixtures.item(id, max_stack)
	def.value = value
	def.category = category
	def.display_name = String(id).capitalize()
	return def

func _state() -> Node:
	var state := Fixtures.install_state({
		&"potion": _item(&"potion", 10),
		&"elixir": _item(&"elixir", 40),
		&"sword": _item(&"sword", 25, RpgItemDefinition.Category.WEAPON, 1),
		&"key": _item(&"key", 100, RpgItemDefinition.Category.KEY, 1),
		&"junk": _item(&"junk", 0),
		&"cheap": _item(&"cheap", 1),
	})
	state.new_game()
	state.inventory.slots.clear()
	state.gold = 50
	return state

func _shop() -> RpgShopDefinition:
	var shop := RpgShopDefinition.new()
	shop.id = &"village"
	var stock: Array[Dictionary] = [
		{"item_id": "potion", "price": -1},
		{"item_id": "elixir", "price": 30},  # cheaper than its value
		{"item_id": "sword", "price": -1},
		{"item_id": "missing", "price": 5},
	]
	shop.stock = stock
	return shop

func test_prices_are_listed_or_the_item_value(t) -> void:
	var state := _state()
	var shop := _shop()
	t.eq(shop.buy_price(&"potion", state.items), 10)
	t.eq(shop.buy_price(&"elixir", state.items), 30)
	t.ok(shop.sells(&"potion") and not shop.sells(&"cheap"))
	t.eq(shop.offered(state.items), [&"potion", &"elixir", &"sword"] as Array[StringName], "an unknown item id is skipped")
	Fixtures.uninstall_state()

func test_buying_takes_gold_and_adds_the_item(t) -> void:
	var state := _state()
	var shop := _shop()
	t.eq(shop.buy(state, &"potion"), RpgShopDefinition.OK)
	t.eq(state.gold, 40)
	t.eq(state.inventory.count(&"potion"), 1)
	t.eq(shop.buy(state, &"potion", 2), RpgShopDefinition.OK)
	t.eq(state.gold, 20)
	t.eq(state.inventory.count(&"potion"), 3)
	Fixtures.uninstall_state()

func test_buying_without_enough_gold_changes_nothing(t) -> void:
	var state := _state()
	var shop := _shop()
	state.gold = 9
	t.eq(shop.buy(state, &"potion"), RpgShopDefinition.NOT_ENOUGH_GOLD)
	t.eq(state.gold, 9)
	t.eq(state.inventory.count(&"potion"), 0)
	state.gold = 25
	t.eq(shop.buy(state, &"potion", 3), RpgShopDefinition.NOT_ENOUGH_GOLD, "the whole order is refused")
	t.eq(state.inventory.count(&"potion"), 0)
	t.eq(shop.buy(state, &"cheap"), RpgShopDefinition.NOT_FOR_SALE, "not in the stock")
	Fixtures.uninstall_state()

func test_buying_respects_the_bag_and_the_stack_limit(t) -> void:
	var state := _state()
	var shop := _shop()
	state.gold = 1000
	state.inventory.capacity = 1
	t.eq(shop.buy(state, &"sword"), RpgShopDefinition.OK)  # a stack of one fills the only slot
	t.eq(shop.buy(state, &"sword"), RpgShopDefinition.NO_ROOM, "the stack limit is 1 and no slot is free")
	t.eq(state.gold, 1000 - 25)
	t.eq(shop.buy(state, &"potion"), RpgShopDefinition.NO_ROOM)
	state.inventory.capacity = 2
	t.eq(state.inventory.room_for(&"potion"), 99)
	state.inventory.add(&"potion", 98)
	t.eq(state.inventory.room_for(&"potion"), 1)
	t.eq(shop.buy(state, &"potion", 2), RpgShopDefinition.NO_ROOM, "all or nothing")
	t.eq(state.inventory.count(&"potion"), 98)
	t.eq(shop.buy(state, &"potion", 1), RpgShopDefinition.OK)
	Fixtures.uninstall_state()

func test_selling_pays_the_ratio_and_removes_the_item(t) -> void:
	var state := _state()
	var shop := _shop()
	state.inventory.add(&"potion", 3)
	t.eq(shop.sell_price(&"potion", state.items), 5)
	t.eq(shop.sell(state, &"potion"), RpgShopDefinition.OK)
	t.eq(state.gold, 55)
	t.eq(state.inventory.count(&"potion"), 2)
	t.eq(shop.sell(state, &"potion", 2), RpgShopDefinition.OK)
	t.eq(state.gold, 65)
	t.eq(shop.sell(state, &"potion"), RpgShopDefinition.NOT_HELD)
	shop.sell_ratio = 0.75
	t.eq(shop.sell_price(&"elixir", state.items), 30)
	t.eq(shop.sell_price(&"cheap", state.items), 1, "never less than 1 for something with a value")
	Fixtures.uninstall_state()

func test_what_the_shop_will_not_buy(t) -> void:
	var state := _state()
	var shop := _shop()
	state.inventory.add(&"key")
	state.inventory.add(&"junk")
	t.eq(shop.sell(state, &"key"), RpgShopDefinition.WORTHLESS, "key items are never bought")
	t.eq(shop.sell(state, &"junk"), RpgShopDefinition.WORTHLESS, "no value, no price")
	t.eq(state.inventory.count(&"key"), 1)
	t.eq(state.gold, 50)
	Fixtures.uninstall_state()

func test_the_dialogue_event_asks_for_the_shop(t) -> void:
	var state := _state()
	var seen := []
	RpgUtil.events().shop_requested.connect(func(shop_id: StringName) -> void: seen.append(shop_id))
	t.ok(RpgDialogueRunner.execute_event("open_shop:village_shop"))
	t.eq(seen, [&"village_shop"])
	t.ok(not RpgDialogueRunner.execute_event("open_shop:"), "an event without an id is malformed")
	t.eq(seen.size(), 1)
	Fixtures.uninstall_state()

func test_a_missing_shop_file_is_null(t) -> void:
	t.ok(RpgShopDefinition.load_shop(&"no_such_shop") == null)
	t.ok(RpgShopDefinition.load_shop(&"") == null)

# ------------------------------------------------------------------ the menu

func _menu(shop: RpgShopDefinition) -> RpgShopMenu:
	var recipe := UiRecipes.new()
	var root: Node = recipe.call("_build_shop_menu")
	SceneUtil.save_scene(root, MENU_TMP)
	var menu := (load(MENU_TMP) as PackedScene).instantiate() as RpgShopMenu
	menu.shop = shop
	Fixtures.tree().root.add_child(menu)
	if not menu.is_node_ready():
		menu._ready()
	return menu

## Every control of `menu` that can take focus, and the ones a walk of focus_neighbor_bottom reaches.
func _walk_down(menu: Control) -> Dictionary:
	var all := RpgMenuUtil.focusables(menu)
	var reached: Array = []
	var current: Control = all[0] if not all.is_empty() else null
	while current != null and not reached.has(current) and reached.size() < 50:
		reached.append(current)
		current = current.get_node_or_null(current.focus_neighbor_bottom) as Control
	return {"all": all, "reached": reached}

func test_the_focus_chain_reaches_every_control_in_both_tabs(t) -> void:
	var english := Fixtures.install_english()
	var state := _state()
	state.inventory.add(&"potion", 2)
	state.inventory.add(&"elixir")
	var menu := _menu(_shop())
	var walk := _walk_down(menu)
	t.eq(menu.rows().size(), 3)
	t.eq(walk["reached"].size(), walk["all"].size(), "three tabs, 3 items and Back")
	t.eq(walk["all"].size(), 7)
	menu.set_mode(RpgShopMenu.SELL)
	walk = _walk_down(menu)
	t.eq(menu.rows().size(), 2, "potion and elixir are sellable")
	t.eq(walk["reached"].size(), walk["all"].size())
	# going up from the first control wraps to Back, and left / right switches the tab
	var all: Array = walk["all"]
	var first: Control = all[0]
	var up := first.get_node(first.focus_neighbor_top) as Control
	t.eq(String(up.name), "Back")
	t.eq(String(first.get_node(first.focus_neighbor_right).name), "SellTab")
	menu.free()
	Fixtures.uninstall_state()
	Fixtures.uninstall_english(english)

func test_the_menu_buys_and_sells_with_the_tab_and_the_gold_label(t) -> void:
	var english := Fixtures.install_english()
	var state := _state()
	var menu := _menu(_shop())
	var potion := menu.rows()[0]
	t.eq(menu.item_of(potion), &"potion")
	t.eq(potion.text, "Potion — 10 G")
	potion.pressed.emit()
	t.eq(state.gold, 40)
	t.eq(state.inventory.count(&"potion"), 1)
	t.eq((menu.get_node("%Gold") as Label).text, "Gold: 40")
	state.gold = 3
	menu.rows()[0].pressed.emit()
	t.eq(state.inventory.count(&"potion"), 1, "refused: no gold")
	menu.set_mode(RpgShopMenu.SELL)
	t.eq(menu.rows()[0].text, "Potion x1 — 5 G")
	menu.rows()[0].pressed.emit()
	t.eq(state.gold, 8)
	t.eq(state.inventory.count(&"potion"), 0)
	t.eq(menu.rows().size(), 0)
	t.eq((menu.get_node("%Description") as Label).text, "Nothing to sell")
	menu.free()
	Fixtures.uninstall_state()
	Fixtures.uninstall_english(english)

# ------------------------------------------------------------------ quantities and sell all (T13.11)

func test_buying_three_takes_three_times_the_price_and_respects_the_stack_limit(t) -> void:
	var english := Fixtures.install_english()
	var state := _state()
	var menu := _menu(_shop())
	var potion := menu.rows()[0]
	t.eq(menu.max_quantity(&"potion"), 5, "50 gold, 10 each")
	menu.change_quantity(&"potion", 1)
	menu.change_quantity(&"potion", 1)
	t.eq(menu.quantity_of(&"potion"), 3)
	t.eq(potion.text, "Potion (3) — 30 G", "the total before you press")
	potion.pressed.emit()
	t.eq(state.gold, 20)
	t.eq(state.inventory.count(&"potion"), 3)
	t.eq(menu.rows()[0].text, "Potion — 10 G", "back to one after the purchase")
	t.eq(menu.max_quantity(&"potion"), 2)
	# down from one wraps to the most, up from the most wraps to one
	menu.change_quantity(&"potion", -1)
	t.eq(menu.quantity_of(&"potion"), 2)
	menu.change_quantity(&"potion", 1)
	t.eq(menu.quantity_of(&"potion"), 1)
	# the stack limit: a sword stacks to 1 and the bag has one free slot
	state.gold = 1000
	state.inventory.capacity = state.inventory.slots.size() + 1
	t.eq(menu.max_quantity(&"sword"), 1)
	menu.set_quantity(&"sword", 9)
	t.eq(menu.quantity_of(&"sword"), 1)
	t.eq(menu.max_quantity(&"potion"), 100, "what the gold allows")
	state.gold = 100000
	t.eq(menu.max_quantity(&"potion"), 96 + 99, "the rest of the stack and the free slot")
	state.gold = 1000
	t.eq(menu.transact(&"sword", 2), RpgShopDefinition.NO_ROOM)
	t.eq(state.gold, 1000)
	# with no gold the row still offers one, and pressing it is refused
	state.gold = 0
	t.eq(menu.max_quantity(&"potion"), 1)
	menu.free()
	Fixtures.uninstall_state()
	Fixtures.uninstall_english(english)

func test_left_and_right_on_a_row_change_the_quantity(t) -> void:
	var english := Fixtures.install_english()
	var state := _state()
	state.inventory.add(&"potion", 4)
	var menu := _menu(_shop())
	menu.set_mode(RpgShopMenu.SELL)
	var row := menu.rows()[0]
	var right := InputEventAction.new()
	right.action = &"ui_right"
	right.pressed = true
	row.gui_input.emit(right)
	row.gui_input.emit(right)
	t.eq(menu.quantity_of(&"potion"), 3)
	t.eq(row.text, "Potion x4 (3) — 15 G")
	var left := InputEventAction.new()
	left.action = &"ui_left"
	left.pressed = true
	row.gui_input.emit(left)
	t.eq(menu.quantity_of(&"potion"), 2)
	row.pressed.emit()
	t.eq(state.gold, 60)
	t.eq(state.inventory.count(&"potion"), 2)
	t.eq(menu.rows()[0].text, "Potion x2 — 5 G")
	menu.free()
	Fixtures.uninstall_state()
	Fixtures.uninstall_english(english)

func test_sell_all_skips_equipped_gear_and_quest_items(t) -> void:
	var english := Fixtures.install_english()
	var state := _state()
	state.items[&"letter"] = _item(&"letter", 30, RpgItemDefinition.Category.QUEST, 1)
	state.items[&"blade"] = _item(&"blade", 60, RpgItemDefinition.Category.WEAPON, 1)
	for id: StringName in [&"potion", &"potion", &"potion", &"elixir", &"sword", &"blade", &"key", &"letter", &"junk"]:
		state.inventory.add(id)
	t.ok(state.equip(state.player_actor_id, &"blade"), "worn: no longer in the bag")
	var shop := _shop()
	t.eq(shop.sell_all_items(state), {&"potion": 3, &"elixir": 1, &"sword": 1})
	t.eq(shop.sell_all_value(state), 15 + 20 + 12)
	var menu := _menu(shop)
	var button := menu.sell_all_button()
	t.ok(button != null and not button.visible, "not on the Buy tab")
	menu.set_mode(RpgShopMenu.SELL)
	t.ok(button.visible)
	var walk := _walk_down(menu)
	t.eq(walk["reached"].size(), walk["all"].size(), "Sell all is in the ring")
	t.ok(walk["all"].has(button))
	# the first press asks and names the gold, the second one sells
	button.pressed.emit()
	t.eq(button.text, "Sell everything for 47 G? Press again")
	t.eq(state.gold, 50)
	button.focus_exited.emit()
	t.eq(button.text, "Sell all", "moving away takes the question back")
	button.pressed.emit()
	button.pressed.emit()
	t.eq(state.gold, 97)
	t.eq(state.inventory.count(&"potion") + state.inventory.count(&"elixir") + state.inventory.count(&"sword"), 0)
	t.eq(state.inventory.count(&"key"), 1)
	t.eq(state.inventory.count(&"letter"), 1)
	t.eq(state.inventory.count(&"junk"), 1)
	t.eq(state.equipped_in(state.player_actor_id, &"weapon"), &"blade")
	t.ok(not button.visible, "nothing left to sell")
	menu.free()
	Fixtures.uninstall_state()
	Fixtures.uninstall_english(english)

func test_a_shop_buys_only_the_categories_it_lists(t) -> void:
	var state := _state()
	var shop := _shop()
	state.inventory.add(&"potion", 2)
	state.inventory.add(&"sword")
	t.eq(shop.buys, [] as Array[String], "a 1.0 shop has no list and buys everything")
	t.eq(shop.sell_price(&"sword", state.items), 12)
	var only: Array[String] = ["consumable"]
	shop.buys = only
	t.eq(shop.sell_price(&"sword", state.items), 0)
	t.eq(shop.sell(state, &"sword"), RpgShopDefinition.WORTHLESS)
	t.eq(shop.sell_all_items(state), {&"potion": 2})
	t.eq(shop.sell_all(state), 10)
	t.eq(state.inventory.count(&"sword"), 1)
	var with_keys: Array[String] = ["KEY", "QUEST"]
	shop.buys = with_keys
	state.inventory.add(&"key")
	t.eq(shop.sell_price(&"key", state.items), 0, "never, whatever the list says")
	Fixtures.uninstall_state()

func test_a_scene_from_1_0_without_the_sell_all_button_still_works(t) -> void:
	var english := Fixtures.install_english()
	var state := _state()
	state.inventory.add(&"potion", 2)
	var recipe := UiRecipes.new()
	var root: Node = recipe.call("_build_shop_menu")
	var old_button := root.find_child("SellAll", true, false)
	old_button.get_parent().remove_child(old_button)
	old_button.free()
	SceneUtil.save_scene(root, MENU_TMP)
	var menu := (load(MENU_TMP) as PackedScene).instantiate() as RpgShopMenu
	menu.shop = _shop()
	Fixtures.tree().root.add_child(menu)
	if not menu.is_node_ready():
		menu._ready()
	t.ok(menu.sell_all_button() == null)
	menu.set_mode(RpgShopMenu.SELL)
	menu.set_quantity(&"potion", 2)
	menu.rows()[0].pressed.emit()
	t.eq(state.gold, 60)
	var walk := _walk_down(menu)
	t.eq(walk["reached"].size(), walk["all"].size())
	menu.free()
	Fixtures.uninstall_state()
	Fixtures.uninstall_english(english)

func test_a_bare_menu_still_has_a_working_focus_chain(t) -> void:
	var english := Fixtures.install_english()
	var state := _state()
	var menu := _menu(null)  # what the project validator opens
	var walk := _walk_down(menu)
	t.eq(walk["reached"].size(), walk["all"].size())
	t.eq(walk["all"].size(), 4, "Buy, Sell, Buy back and Back")
	menu.free()
	Fixtures.uninstall_state()
	Fixtures.uninstall_english(english)

# ------------------------------------------------------------------ the seeded demo

func test_the_demo_shop_and_the_villagers_offer(t) -> void:
	var recipe := DataRecipe.new()
	var shop: RpgShopDefinition = recipe._shop(["sword", "armor"])
	t.eq(shop.id, &"village_shop")
	var ids: Array = []
	for entry in shop.stock:
		ids.append(entry["item_id"])
	t.eq(ids, ["potion", "sword", "armor"])
	var greeting: RpgDialogueResource = recipe._greeting()
	var offer: RpgDialogueLine = null
	for line in greeting.lines:
		if line.id == &"shop":
			offer = line
	t.ok(offer != null)
	t.eq(Array(offer.events), ["open_shop:village_shop"])
	var ask: RpgDialogueLine = greeting.lines[1]
	var wares: RpgDialogueChoice = null
	for choice in ask.choices:
		if choice.next == &"shop":
			wares = choice
	t.ok(wares != null)
	t.eq(wares.condition, "flag:starter_npc.talked", "offered after the first talk")
	t.ok(recipe.outputs(BuildContext.new("")).has(DataRecipe.SHOP_PATH) or FileAccess.file_exists(DataRecipe.SHOP_PATH))
	var demo_free := BuildContext.new("")
	demo_free.demo_removed = true
	t.ok(not recipe.outputs(demo_free).has(DataRecipe.SHOP_PATH), "no demo, no village shop")
