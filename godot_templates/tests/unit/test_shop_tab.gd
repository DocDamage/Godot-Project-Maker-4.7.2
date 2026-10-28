extends RefCounted
## The dock's Shops tab (T18.02): the starter shop edited in undo steps, saved and read back; a
## row whose item has no file; the JSON round trip; the validator's VAL-034 for such a row.

const ShopTab := preload("res://addons/rpg_project_tools/dock/shop_tab.gd")
const DataRecipe := preload("res://builder/recipes/data_recipe.gd")
const ContentChecks := preload("res://addons/rpg_project_tools/tools/content_checks.gd")

func _folder(label: String) -> String:
	var folder := "user://test_%s_%d" % [label, Time.get_ticks_usec()]
	DirAccess.make_dir_recursive_absolute(folder)
	return folder

func _remove(folder: String) -> void:
	for file_name in DirAccess.get_files_at(folder):
		DirAccess.remove_absolute(folder.path_join(file_name))
	DirAccess.remove_absolute(folder)

## A folder of shops holding the starter shop, and one of items holding what it sells.
func _project(t, label: String) -> Array[String]:
	var shops := _folder(label + "_shops")
	var items := _folder(label + "_items")
	var starter: Resource = DataRecipe.new().call("_shop", ["sword"], false)
	t.eq(ResourceSaver.save(starter, shops + "/village_shop.tres"), OK)
	for word: String in ["potion", "sword", "herb"]:
		var item := RpgItemDefinition.new()
		item.id = StringName(word)
		ResourceSaver.save(item, "%s/%s.tres" % [items, word])
	return [shops, items]

func _tab(folders: Array[String], undo: UndoRedo) -> VBoxContainer:
	var tab: VBoxContainer = ShopTab.new()
	tab.set("shops_dir", folders[0])
	tab.set("items_dir", folders[1])
	tab.set("enemies_dir", "user://no_enemies")
	tab.set("loot_dir", "user://no_loot")
	tab.set("undo_redo", undo)
	tab.call("rescan")
	return tab

func _reload(path: String) -> RpgShopDefinition:
	return ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgShopDefinition

func test_the_tab_edits_the_starter_shop_saves_and_undoes(t) -> void:
	var folders := _project(t, "shop_tab")
	var undo := UndoRedo.new()
	var tab := _tab(folders, undo)
	var shop := tab.get("shop") as RpgShopDefinition
	t.ok(shop != null and shop.id == &"village_shop", "the starter shop is open")
	t.eq(tab.call("problems"), [] as Array[String])
	tab.call("set_row", 0, "qty", 3)
	tab.call("set_property", "restock_each_day", true)
	tab.call("set_property", "funds", 400)
	t.ok(tab.call("save"))
	var back := _reload(folders[0] + "/village_shop.tres")
	t.eq(RpgUtil.to_int(back.stock[0]["qty"]), 3, "the quantity is in the file")
	t.ok(back.restock_each_day)
	t.eq(back.funds, 400)
	undo.undo()
	t.eq(shop.funds, -1, "one undo step takes back the gold")
	undo.undo()
	t.ok(not shop.restock_each_day)
	undo.undo()
	t.ok(not shop.stock[0].has("qty"), "and the quantity: no limit again")
	t.ok(tab.call("save"))
	back = _reload(folders[0] + "/village_shop.tres")
	t.eq([back.funds, back.restock_each_day, back.stock[0].has("qty")], [-1, false, false], "the old values are saved back")
	undo.redo()
	t.eq(RpgUtil.to_int(shop.stock[0]["qty"]), 3, "redo")
	tab.call("set_row", 0, "qty", -1)
	t.ok(not shop.stock[0].has("qty"), "-1 is no limit: the key goes")
	tab.free()
	_remove(folders[0])
	_remove(folders[1])

func test_rows_are_added_and_removed_and_a_missing_item_is_red(t) -> void:
	var folders := _project(t, "shop_rows")
	var undo := UndoRedo.new()
	var tab := _tab(folders, undo)
	var shop := tab.get("shop") as RpgShopDefinition
	var before := shop.stock.size()
	tab.call("add_row", "herb")
	t.eq(shop.stock.size(), before + 1)
	t.eq(str(shop.stock[before]["item_id"]), "herb")
	tab.call("set_row", before, "item_id", "elixir")
	t.eq(tab.call("row_note", before), "row %d sells 'elixir', which has no file in res://game/data/items" % (before + 1))
	t.eq(tab.call("problems"), [tab.call("row_note", before)] as Array[String])
	var picker := (tab.find_child("Row%d" % before, true, false) as HBoxContainer).get_child(0) as OptionButton
	t.ok(picker.has_theme_color_override("font_color"), "the row is shown in red")
	t.eq(picker.tooltip_text, tab.call("row_note", before), "with the reason")
	tab.call("remove_row", before)
	t.eq(shop.stock.size(), before)
	undo.undo()
	t.eq(shop.stock.size(), before + 1, "removing a row is one undo step")
	tab.free()
	_remove(folders[0])
	_remove(folders[1])

func test_the_json_round_trip_keeps_every_field(t) -> void:
	var shop := RpgShopDefinition.new()
	shop.id = &"smith"
	shop.title = "SHOP_SMITH"
	var rows: Array[Dictionary] = [{"item_id": "sword", "price": 40, "qty": 2}]
	shop.stock = rows
	shop.sell_ratio = 0.25
	var buys: Array[String] = ["WEAPON", "ARMOR"]
	shop.buys = buys
	shop.restock_minutes = 30
	shop.funds = 900
	shop.buyback = false
	shop.repairs = true
	shop.wares = RpgLootTable.new()
	var entries: Array[Dictionary] = [{"item_id": "herb", "chance": 0.5, "min": 1, "max": 3}]
	shop.wares.entries = entries
	var text := JSON.stringify(shop.to_dict())
	var back := RpgShopDefinition.from_dict(RpgUtil.to_dict(RpgUtil.restore_numbers(JSON.parse_string(text))))
	t.eq(back.to_dict(), shop.to_dict())
	t.eq(back.wares.entries, entries)

func test_the_validator_names_a_row_whose_item_has_no_file(t) -> void:
	var folders := _project(t, "shop_val")
	var shop := _reload(folders[0] + "/village_shop.tres")
	shop.stock.append({"item_id": "elixir", "price": -1})
	ResourceSaver.save(shop, folders[0] + "/village_shop.tres")
	var findings: Array = []
	ContentChecks._check_game_data({"shops": folders[0], "items": folders[1], "quests": "user://none", "skill_trees": "user://none", "achievements": "user://none", "item_sets": "user://none"}, findings)
	var said: Array = []
	for f: Dictionary in findings:
		if f["code"] == "VAL-034":
			said.append(str(f["detail"]["problem"]))
	t.eq(said, ["shop: row %d sells 'elixir', which has no file in res://game/data/items" % shop.stock.size()])
	_remove(folders[0])
	_remove(folders[1])

func test_the_dock_has_the_shops_tab(t) -> void:
	var source := FileAccess.get_file_as_string("res://addons/rpg_project_tools/dock/asset_dock.gd")
	t.ok(source.contains("ShopTab.new()"))
	var tab: Node = ShopTab.new()
	t.eq(String(tab.name), "Shops")
	tab.free()
