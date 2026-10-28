extends RefCounted
## Cooking on a farm (T18.16): the dishes of what the farm grows and keeps, each restoring more
## than its parts and worth more; one known, the others taught by a friend's heart; the kitchen of
## a new farmhouse and the stove of an older one.

const Fixtures := preload("../lib/fixtures.gd")
const CraftingRecipe := preload("res://builder/recipes/crafting_recipe.gd")

const PARTS := {
	"crop:0": {"item": "crop_corn", "energy": 14, "value": 30},
	"crop:1": {"item": "crop_bean", "energy": 20, "value": 20},
	"egg": {"item": "egg", "energy": 10, "value": 25},
}

func test_only_the_dishes_the_farm_can_make_are_seeded(t) -> void:
	var dishes := CraftingRecipe.dishes(PARTS)
	var ids: Array = dishes.map(func(dish: Dictionary) -> String: return str(dish["id"]))
	t.eq(ids, ["salad", "vegetable_soup", "omelette"], "no third crop, no fish, no milk, nothing to forage")
	t.eq(dishes[0]["learn"], "known", "the first is known")
	t.ok(dishes.slice(1).all(func(dish: Dictionary) -> bool: return dish["learn"] == "taught"))
	var soup: Dictionary = dishes[1]
	t.eq(soup["ingredients"], {"crop_corn": 1, "crop_bean": 1})
	t.ok(RpgUtil.to_int(soup["energy"]) > 14 + 20, "more energy than its parts eaten raw")
	t.ok(RpgUtil.to_int(soup["value"]) > 30 + 20, "and worth more")
	var recipe := CraftingRecipe.dish_recipe(soup) as RpgRecipe
	t.eq([recipe.id, recipe.station, recipe.learn], [&"cook_vegetable_soup", &"kitchen", "taught"])
	t.eq(recipe.problems(), [] as Array[String])
	var item := CraftingRecipe.dish_item(soup) as RpgItemDefinition
	t.eq([item.use_effect, item.effect_amount], [&"heal", RpgUtil.to_int(soup["energy"])], "eating it gives its energy")

func test_a_friend_teaches_a_dish_at_a_new_heart(t) -> void:
	var registry := {&"crop_corn": Fixtures.item(&"crop_corn"), &"crop_bean": Fixtures.item(&"crop_bean"), &"salad": Fixtures.item(&"salad"), &"vegetable_soup": Fixtures.item(&"vegetable_soup")}
	var state := Fixtures.install_state(registry) as RpgGameState
	state.new_game()
	var dir := "user://test_cooking_%d" % Time.get_ticks_usec()
	DirAccess.make_dir_recursive_absolute(dir)
	for dish in CraftingRecipe.dishes(PARTS).slice(0, 2):
		ResourceSaver.save(CraftingRecipe.dish_recipe(dish), "%s/cook_%s.tres" % [dir, dish["id"]])
	RpgCrafting.recipes_dir = dir
	RpgCrafting.reload_book()
	var mode := RpgFarmMode.new()
	mode.cooking = true
	mode._ready()
	var soup := RpgCrafting.recipe(&"cook_vegetable_soup")
	t.ok(RpgCrafting.known(state, RpgCrafting.recipe(&"cook_salad")) and not RpgCrafting.known(state, soup))
	t.eq(RpgFarmWorkshop.next_dish(), soup)
	var friends := RpgFriendship.current()
	t.ok(friends != null, "the farm keeps friendships")
	friends.add_points("anna", RpgFriendship.HEART_POINTS)
	t.ok(RpgCrafting.known(state, soup), "a heart taught the soup")
	# the kitchen's window lists the dishes made at the stove
	var menu_recipes := RpgCrafting.recipes(&"kitchen")
	t.eq(menu_recipes.size(), 2)
	mode.free()
	for file_name in DirAccess.get_files_at(dir):
		DirAccess.remove_absolute(dir.path_join(file_name))
	DirAccess.remove_absolute(dir)
	RpgCrafting.recipes_dir = RpgCrafting.RECIPES_DIR
	RpgCrafting.reload_book()
	Fixtures.uninstall_state()

func test_a_stove_is_a_kitchen_and_is_sold_where_the_farmhouse_has_none(t) -> void:
	var stove := RpgPlacedThing.make(3, "stove", 16, true)
	var station := stove.get_node("Station") as RpgStation
	t.eq([station.station_id, station.entity_id], [&"kitchen", "placed_stove_3"])
	stove.free()
	var state := Fixtures.install_state({&"stove": CraftingRecipe.stove_item()}) as RpgGameState
	state.new_game()
	var workshop := RpgFarmWorkshop.new()
	workshop.cooking = true
	workshop.stove_for_sale = true
	t.eq(workshop.stove_rows(), [{"item_id": "stove", "price": RpgFarmWorkshop.STOVE_PRICE}])
	state.inventory.add(&"stove")
	t.eq(workshop.stove_rows(), [], "one is enough")
	workshop.stove_for_sale = false
	state.inventory.remove(&"stove")
	t.eq(workshop.stove_rows(), [], "a farmhouse with a kitchen")
	workshop.free()
	Fixtures.uninstall_state()
