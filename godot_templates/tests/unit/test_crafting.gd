extends RefCounted
## Crafting (T18.14): by hand all or nothing, a full bag refused before anything is taken, a
## station's queue that takes its time and keeps what the bag cannot hold in its tray,
## cancelling, recipes found by themselves and taught, the counters, the save, the window and the
## dock's Recipes tab.

const Fixtures := preload("../lib/fixtures.gd")
const RecipeTab := preload("res://addons/rpg_project_tools/dock/recipe_tab.gd")
const CraftingRecipe := preload("res://builder/recipes/crafting_recipe.gd")
const ContentChecks := preload("res://addons/rpg_project_tools/tools/content_checks.gd")

var _dir := ""

func _recipe(id: String, ingredients: Dictionary, results: Dictionary, station: String = "", minutes: int = 0, learn: String = "known") -> RpgRecipe:
	var made := RpgRecipe.new()
	made.id = StringName(id)
	made.title = id.capitalize()
	made.ingredients = ingredients
	made.results = results
	made.station = StringName(station)
	made.minutes = minutes
	made.learn = learn
	return made

## A game with herbs, wood and what they make, and a folder of recipes.
func _game() -> RpgGameState:
	var registry := {}
	for word: String in ["herb", "potion", "wood", "plank", "stone", "wall", "salve"]:
		var def := Fixtures.item(StringName(word))
		def.display_name = word.capitalize()
		registry[StringName(word)] = def
	var state := Fixtures.install_state(registry) as RpgGameState
	state.new_game()
	state.inventory.slots.clear()
	state.inventory.registry = state.items
	_dir = "user://test_recipes_%d" % Time.get_ticks_usec()
	DirAccess.make_dir_recursive_absolute(_dir)
	for made in [
		_recipe("potion", {"herb": 2}, {"potion": 1}),
		_recipe("plank", {"wood": 1}, {"plank": 2}, "workbench", 30),
		_recipe("wall", {"plank": 2, "stone": 1}, {"wall": 1}, "", 0, "found"),
		_recipe("salve", {"herb": 1, "potion": 1}, {"salve": 1}, "", 0, "taught"),
	]:
		ResourceSaver.save(made, "%s/%s.tres" % [_dir, made.id])
	RpgCrafting.recipes_dir = _dir
	RpgCrafting.reload_book()
	return state

func _end() -> void:
	for file_name in DirAccess.get_files_at(_dir):
		DirAccess.remove_absolute(_dir.path_join(file_name))
	DirAccess.remove_absolute(_dir)
	RpgCrafting.recipes_dir = RpgCrafting.RECIPES_DIR
	RpgCrafting.reload_book()
	Fixtures.uninstall_state()

func test_by_hand_is_all_or_nothing(t) -> void:
	var state := _game()
	var potion := RpgCrafting.recipe(&"potion")
	t.eq(RpgCrafting.craft(state, potion), RpgCrafting.MISSING, "no herbs")
	state.inventory.add(&"herb", 3)
	t.eq(RpgCrafting.lacking(state, potion, 2), {"herb": 1})
	t.eq(RpgCrafting.most(state, potion), 1)
	t.eq(RpgCrafting.craft(state, potion), RpgCrafting.OK)
	t.eq([state.inventory.count(&"herb"), state.inventory.count(&"potion")], [1, 1])
	t.eq(state.counter("crafted"), 1)
	t.eq(state.counter("crafted:potion"), 1)
	t.ok(RpgCondition.evaluate_on("crafted:potion", state) and not RpgCondition.evaluate_on("crafted:potion>=2", state))
	t.eq(RpgCrafting.craft(state, RpgCrafting.recipe(&"plank")), RpgCrafting.WRONG_STATION, "a station's recipe is not made by hand")
	_end()

func test_a_full_bag_is_refused_before_anything_is_taken(t) -> void:
	var state := _game()
	state.inventory.capacity = 1
	state.inventory.add(&"herb", 3)  # one stack: after two are taken one is left, and no slot for the potion
	var potion := RpgCrafting.recipe(&"potion")
	t.eq(RpgCrafting.craft(state, potion), RpgCrafting.NO_ROOM)
	t.eq([state.inventory.count(&"herb"), state.inventory.count(&"potion")], [3, 0], "nothing was taken")
	_end()

func test_a_station_takes_its_time_and_keeps_what_the_bag_cannot_hold(t) -> void:
	var state := _game()
	var plank := RpgCrafting.recipe(&"plank")
	state.inventory.add(&"wood", 3)
	state.playtime_s = 0.0
	t.eq(RpgCrafting.queue(state, "bench", &"forge", plank), RpgCrafting.WRONG_STATION)
	t.eq(RpgCrafting.queue(state, "bench", &"workbench", plank, 2), RpgCrafting.OK)
	t.eq(state.inventory.count(&"wood"), 1, "the ingredients are taken when it is queued")
	t.eq(RpgCrafting.queue(state, "bench", &"workbench", plank), RpgCrafting.OK)
	var jobs: Array = RpgCrafting.station_state(state, "bench")["queue"]
	t.eq(jobs.size(), 2)
	t.eq([RpgUtil.to_int(jobs[0]["done"]), RpgUtil.to_int(jobs[1]["start"]), RpgUtil.to_int(jobs[1]["done"])], [60, 60, 90], "one after the other")
	state.playtime_s = 59.0
	t.eq(RpgCrafting.update(state, "bench"), 0, "not yet")
	t.near(RpgCrafting.progress(state, jobs[0]), 59.0 / 60.0, 0.001)
	state.playtime_s = 60.0
	t.eq(RpgCrafting.update(state, "bench"), 1)
	t.eq(state.inventory.count(&"plank"), 4, "into the bag")
	# a full bag: the next waits in the tray
	state.inventory.capacity = state.inventory.slots.size()
	(state.items[&"plank"] as RpgItemDefinition).max_stack = 4  # the stack of planks is full
	state.playtime_s = 95.0
	t.eq(RpgCrafting.update(state, "bench"), 1)
	t.eq(RpgCrafting.station_state(state, "bench")["tray"], [{"item_id": "plank", "qty": 2}])
	t.eq(RpgCrafting.collect_all(state, "bench"), 0, "still no room")
	(state.items[&"plank"] as RpgItemDefinition).max_stack = 99
	t.eq(RpgCrafting.collect_all(state, "bench"), 1, "a stack of planks takes the two")
	t.eq(state.inventory.count(&"plank"), 6)
	t.eq(state.get_flag(RpgCrafting.FLAG_ENTITY, "stations", {}), {}, "nothing is kept of an idle station")
	_end()

func test_cancelling_gives_the_ingredients_back(t) -> void:
	var state := _game()
	var plank := RpgCrafting.recipe(&"plank")
	state.inventory.add(&"wood", 2)
	state.playtime_s = 0.0
	RpgCrafting.queue(state, "bench", &"workbench", plank)
	RpgCrafting.queue(state, "bench", &"workbench", plank)
	t.ok(RpgCrafting.cancel(state, "bench", 0))
	t.eq(state.inventory.count(&"wood"), 1, "the first is cancelled: its wood comes back")
	var jobs: Array = RpgCrafting.station_state(state, "bench")["queue"]
	t.eq([RpgUtil.to_int(jobs[0]["start"]), RpgUtil.to_int(jobs[0]["done"])], [0, 30], "the next moves up")
	t.ok(not RpgCrafting.cancel(state, "bench", 3))
	_end()

func test_a_recipe_is_found_or_taught(t) -> void:
	var state := _game()
	var wall := RpgCrafting.recipe(&"wall")
	var salve := RpgCrafting.recipe(&"salve")
	t.ok(not RpgCrafting.known(state, wall) and not RpgCrafting.known(state, salve))
	state.inventory.add(&"plank", 2)
	t.ok(not RpgCrafting.known(state, wall), "the plank alone")
	state.inventory.add(&"stone", 1)
	t.ok(RpgCrafting.known(state, wall), "found once every ingredient was held")
	t.eq(RpgCrafting.craft(state, salve), RpgCrafting.NOT_KNOWN)
	t.ok(RpgDialogueRunner.execute_event("learn_recipe:salve"))
	t.ok(RpgCrafting.known(state, salve), "taught")
	_end()

func test_what_crafting_keeps_is_saved(t) -> void:
	var state := _game()
	state.inventory.add(&"wood", 1)
	state.playtime_s = 0.0
	RpgCrafting.queue(state, "bench", &"workbench", RpgCrafting.recipe(&"plank"))
	RpgCrafting.learn(state, &"salve", false)
	var saved: Dictionary = JSON.parse_string(JSON.stringify(state.to_dict()))
	state.new_game()
	t.ok(not RpgCrafting.known(state, RpgCrafting.recipe(&"salve")), "a new game knows nothing")
	state.from_dict(saved)
	t.ok(RpgCrafting.known(state, RpgCrafting.recipe(&"salve")))
	t.eq(RpgUtil.to_array(RpgCrafting.station_state(state, "bench")["queue"]).size(), 1, "the queue is saved")
	_end()

func test_the_window_crafts_by_hand(t) -> void:
	var english := Fixtures.install_english()
	var state := _game()
	state.inventory.add(&"herb", 4)
	var menu := RpgCraftingMenu.new()
	Fixtures.tree().root.add_child(menu)
	t.eq(menu.cells().size(), 3, "the recipes made by hand: potion, salve, wall")
	var potion_cell: Button = null
	for cell in menu.cells():
		if menu.recipe_of(cell).id == &"potion":
			potion_cell = cell
		if menu.recipe_of(cell).id == &"salve":
			t.eq(cell.text, "???", "one not known is a silhouette")
	menu.set_amount(RpgCrafting.recipe(&"potion"), 2)
	t.ok(menu.detail_text(RpgCrafting.recipe(&"potion")).contains("Herb 4/4"), menu.detail_text(RpgCrafting.recipe(&"potion")))
	potion_cell.pressed.emit()
	t.eq([state.inventory.count(&"herb"), state.inventory.count(&"potion")], [0, 2])
	menu._filter.button_pressed = true
	t.eq(menu.cells().size(), 0, "nothing can be made now")
	menu.free()
	_end()
	Fixtures.uninstall_english(english)

func test_the_starter_recipe_and_the_dock(t) -> void:
	var made := CraftingRecipe.potion_recipe() as RpgRecipe
	t.eq(made.problems(), [] as Array[String])
	t.eq(made.ingredients, {"herb": 2})
	var dir := "user://test_recipe_tab_%d" % Time.get_ticks_usec()
	DirAccess.make_dir_recursive_absolute(dir + "/recipes")
	DirAccess.make_dir_recursive_absolute(dir + "/items")
	ResourceSaver.save(made, dir + "/recipes/potion.tres")
	for word: String in ["herb", "potion"]:
		ResourceSaver.save(Fixtures.item(StringName(word)), "%s/items/%s.tres" % [dir, word])
	var undo := UndoRedo.new()
	var tab: VBoxContainer = RecipeTab.new()
	tab.set("recipes_dir", dir + "/recipes")
	tab.set("items_dir", dir + "/items")
	tab.set("undo_redo", undo)
	tab.call("rescan")
	t.eq(tab.call("problems"), [] as Array[String])
	tab.call("set_qty", "ingredients", "herb", 3)
	tab.call("add_item", "results", "herb")
	var recipe := tab.get("recipe") as RpgRecipe
	t.eq(recipe.ingredients, {"herb": 3})
	t.eq(recipe.results, {"potion": 1, "herb": 1})
	tab.call("rename_item", "ingredients", "herb", "elixir")
	t.ok((tab.call("problems") as Array).has("'elixir' has no file in res://game/data/items"))
	undo.undo()
	t.eq(recipe.ingredients, {"herb": 3}, "one undo step")
	t.ok(tab.call("save"))
	t.eq((ResourceLoader.load(dir + "/recipes/potion.tres", "", ResourceLoader.CACHE_MODE_REPLACE) as RpgRecipe).ingredients, {"herb": 3})
	tab.free()
	for sub: String in ["recipes", "items"]:
		for file_name in DirAccess.get_files_at(dir + "/" + sub):
			DirAccess.remove_absolute(dir + "/" + sub + "/" + file_name)
		DirAccess.remove_absolute(dir + "/" + sub)
	DirAccess.remove_absolute(dir)

func test_the_validator_names_what_a_recipe_lacks(t) -> void:
	var dir := "user://test_recipe_val_%d" % Time.get_ticks_usec()
	for sub: String in ["recipes", "items", "maps"]:
		DirAccess.make_dir_recursive_absolute(dir + "/" + sub)
	ResourceSaver.save(_recipe("plank", {"wood": 1}, {"plank": 2}, "workbench", 30), dir + "/recipes/plank.tres")
	ResourceSaver.save(Fixtures.item(&"wood"), dir + "/items/wood.tres")
	var findings: Array = []
	var none := dir + "/none"
	ContentChecks._check_game_data({"recipes": dir + "/recipes", "items": dir + "/items", "maps": dir + "/maps", "world_plan": none, "shops": none, "quests": none, "skill_trees": none, "achievements": none, "item_sets": none}, findings)
	var said: Array = []
	for f: Dictionary in findings:
		said.append(str(f["detail"]["problem"]))
	said.sort()
	t.eq(said, ["recipe: 'plank' has no file in %s/items" % dir, "recipe: it is made at the station 'workbench', which no map has"])
	var f := FileAccess.open(dir + "/maps/farm.tscn", FileAccess.WRITE)
	f.store_string("[node name=\"Workbench\" type=\"Area2D\"]\nstation_id = &\"workbench\"\n")
	f.close()
	t.eq(ContentChecks.station_ids({"maps": dir + "/maps", "world_plan": none}), ["workbench"] as Array[String])
	for sub: String in ["recipes", "items", "maps"]:
		for file_name in DirAccess.get_files_at(dir + "/" + sub):
			DirAccess.remove_absolute(dir + "/" + sub + "/" + file_name)
		DirAccess.remove_absolute(dir + "/" + sub)
	DirAccess.remove_absolute(dir)
