extends RefCounted
## The dock's Items tab (T18.03): the starter sword given a durability and the traveler's set from
## the tab, saved, and the game's bag wearing it; modifiers as rows; a new item's keys in
## strings.tsv; the JSON round trip; the battle fields shown only in a turn-based game.

const Fixtures := preload("../lib/fixtures.gd")
const ItemTab := preload("res://addons/rpg_project_tools/dock/item_tab.gd")
const ProgressionRecipe := preload("res://builder/recipes/progression_recipe.gd")
const StringsTsv := preload("res://addons/rpg_project_tools/tools/strings_tsv.gd")

func _folder(label: String) -> String:
	var folder := "user://test_%s_%d" % [label, Time.get_ticks_usec()]
	DirAccess.make_dir_recursive_absolute(folder)
	return folder

func _remove(folder: String) -> void:
	for file_name in DirAccess.get_files_at(folder):
		DirAccess.remove_absolute(folder.path_join(file_name))
	DirAccess.remove_absolute(folder)

## The starter gear as data_recipe makes it (a weapon and an armour, 25 gold, +2).
func _gear(word: String, weapon: bool) -> RpgItemDefinition:
	var item := RpgItemDefinition.new()
	item.id = StringName(word)
	item.display_name = "ITEM_%s_NAME" % word.to_upper()
	item.description = "ITEM_%s_DESC" % word.to_upper()
	item.category = RpgItemDefinition.Category.WEAPON if weapon else RpgItemDefinition.Category.ARMOR
	item.max_stack = 1
	item.value = 25
	var mods: Array[Dictionary] = [{"stat": "attack" if weapon else "defense", "add": 2, "mul": 1.0}]
	item.modifiers = mods
	return item

func _tab(items: String, sets: String, strings: String, undo: UndoRedo) -> VBoxContainer:
	var tab: VBoxContainer = ItemTab.new()
	tab.set("items_dir", items)
	tab.set("sets_dir", sets)
	tab.set("strings_path", strings)
	tab.set("turn_based", true)
	tab.set("undo_redo", undo)
	tab.call("rescan")
	return tab

func test_the_sword_gets_a_durability_and_the_set_and_the_bag_reports_both(t) -> void:
	var items := _folder("item_tab_items")
	var sets := _folder("item_tab_sets")
	var strings := items + "/strings.tsv"
	ResourceSaver.save(_gear("sword", true), items + "/sword.tres")
	ResourceSaver.save(_gear("armor", false), items + "/armor.tres")
	ResourceSaver.save(ProgressionRecipe.gear_set(), sets + "/traveler.tres")
	var undo := UndoRedo.new()
	var tab := _tab(items, sets, strings, undo)
	tab.call("open", items + "/sword.tres")
	tab.call("set_property", "durability", 30)
	tab.call("set_property", "set_id", &"traveler")
	t.ok(tab.call("save"))
	tab.call("open", items + "/armor.tres")
	tab.call("set_property", "set_id", &"traveler")
	t.ok(tab.call("save"))
	var sword := ResourceLoader.load(items + "/sword.tres", "", ResourceLoader.CACHE_MODE_REPLACE) as RpgItemDefinition
	var armor := ResourceLoader.load(items + "/armor.tres", "", ResourceLoader.CACHE_MODE_REPLACE) as RpgItemDefinition
	t.eq([sword.durability, sword.set_id, armor.set_id], [30, &"traveler", &"traveler"], "both are in the files")
	# the game's bag, with what the files say
	var state := Fixtures.install_state({&"sword": sword, &"armor": armor})
	state.new_game()
	state.inventory.slots.clear()
	state.equipment.clear()
	state.item_sets[&"traveler"] = ResourceLoader.load(sets + "/traveler.tres") as RpgItemSet
	var base_hp: float = state.stat_of(&"hero", &"max_hp")
	state.inventory.add(&"sword")
	state.inventory.add(&"armor")
	t.ok(state.equip(&"hero", &"sword") and state.equip(&"hero", &"armor"))
	t.eq(state.stat_of(&"hero", &"max_hp"), base_hp + 5.0, "the traveler's bonus: two pieces worn")
	t.eq(state.worn_sets(&"hero"), [{"set_id": &"traveler", "worn": 2, "bonus_at": 2}] as Array[Dictionary])
	state.wear(&"hero", &"weapon", 4)
	t.eq(state.wear_of(&"hero", &"weapon"), [4, 30] as Array[int], "the sword wears")
	t.ok(state.unequip(&"hero", &"weapon"))
	var index := -1
	for i in state.inventory.slots.size():
		if state.inventory.slots[i]["item_id"] == &"sword":
			index = i
	t.eq(state.inventory.data_at(index), {"wear": 4}, "the slot of the bag carries the wear")
	Fixtures.uninstall_state()
	undo.undo()
	t.eq((tab.get("item") as RpgItemDefinition).set_id, &"", "one undo step: the armour's set")
	tab.free()
	_remove(items)
	_remove(sets)

func test_modifiers_are_rows_in_undo_steps(t) -> void:
	var items := _folder("item_mods")
	ResourceSaver.save(_gear("sword", true), items + "/sword.tres")
	var undo := UndoRedo.new()
	var tab := _tab(items, "user://no_sets", items + "/strings.tsv", undo)
	var item := tab.get("item") as RpgItemDefinition
	tab.call("add_modifier", "speed")
	t.eq(item.modifiers.size(), 2)
	tab.call("set_modifier", 1, "add", 3)
	t.eq(item.modifiers[1], {"stat": "speed", "add": 3, "mul": 1.0})
	t.ok(tab.find_child("Modifier1", true, false) != null, "a row each")
	tab.call("remove_modifier", 0)
	t.eq(item.modifiers.size(), 1)
	undo.undo()
	t.eq(str(item.modifiers[0]["stat"]), "attack", "removing is one undo step")
	tab.free()
	_remove(items)

func test_a_new_item_adds_its_keys_to_the_strings_file(t) -> void:
	var items := _folder("item_new")
	var strings := items + "/strings.tsv"
	var f := FileAccess.open(strings, FileAccess.WRITE)
	f.store_string("keys\ten\tde\nUI_OK\tOK\tOK\n")
	f.close()
	var tab := _tab(items, "user://no_sets", strings, UndoRedo.new())
	var path: String = tab.call("new_item")
	t.ok(path.ends_with("new_item.tres"))
	var item := tab.get("item") as RpgItemDefinition
	t.eq([item.display_name, item.description], ["ITEM_NEW_ITEM_NAME", "ITEM_NEW_ITEM_DESC"])
	var text := FileAccess.get_file_as_string(strings)
	t.ok(text.begins_with("keys\ten\tde\nUI_OK\tOK\tOK\n"), "the rows that were there stay")
	t.ok(text.contains("ITEM_NEW_ITEM_NAME\tNew Item\t\n"), text)
	t.eq(StringsTsv.english("ITEM_NEW_ITEM_NAME", strings), "New Item")
	t.eq(tab.call("problems"), [] as Array[String])
	tab.free()
	_remove(items)

static func _plain(data: Dictionary) -> Variant:
	return RpgUtil.restore_numbers(JSON.parse_string(JSON.stringify(data)))

func test_the_json_round_trip_and_the_battle_fields(t) -> void:
	var item := _gear("sword", true)
	item.durability = 12
	item.set_id = &"traveler"
	item.element = &"fire"
	item.element_rates = {"ice": 0.5}
	var cures: Array[StringName] = [&"poison"]
	item.cures = cures
	var back := RpgItemDefinition.from_dict(RpgUtil.to_dict(RpgUtil.restore_numbers(JSON.parse_string(JSON.stringify(item.to_dict())))))
	t.eq(_plain(back.to_dict()), _plain(item.to_dict()), "through JSON (1.0 reads back as 1)")
	var items := _folder("item_battle")
	ResourceSaver.save(item, items + "/sword.tres")
	var tab := _tab(items, "user://no_sets", items + "/strings.tsv", UndoRedo.new())
	t.ok((tab.get("_battle") as Control).visible, "a turn-based game shows them")
	tab.set("turn_based", false)
	tab.call("open", items + "/sword.tres")
	t.ok(not (tab.get("_battle") as Control).visible, "another kind does not")
	tab.free()
	_remove(items)

func test_the_dock_has_the_items_tab(t) -> void:
	var source := FileAccess.get_file_as_string("res://addons/rpg_project_tools/dock/asset_dock.gd")
	t.ok(source.contains("ItemTab.new()"))
	var tab: Node = ItemTab.new()
	t.eq(String(tab.name), "Items")
	tab.free()
