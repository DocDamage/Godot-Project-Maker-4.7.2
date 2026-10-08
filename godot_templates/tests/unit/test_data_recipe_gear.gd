extends RefCounted
## The starter equipment that data_recipe seeds from ITEM assets by name (T12.45).

const Recipe := preload("res://builder/recipes/data_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")

func _asset(name: String, role: String = "ITEM", status: String = "OK") -> Dictionary:
	return {
		"id": "pack.items#%s" % name, "path": "icon.svg", "status": status,
		"detected": {"role": role, "usage": "sprite", "size": [16, 16]},
	}

func _ctx(assets: Array) -> BuildContext:
	var ctx := BuildContext.new("")
	ctx.catalog = CatalogReader.new({"assets": assets})
	return ctx

func test_the_first_matching_item_asset_of_each_group_is_chosen(t) -> void:
	var recipe := Recipe.new()
	var gear: Dictionary = recipe._gear(_ctx([
		_asset("potion_red"), _asset("iron_sword"), _asset("battle_axe"),
		_asset("wooden_shield"), _asset("helmet_gold"),
	]))
	t.eq(gear.keys(), ["sword", "shield"], "sword before axe, shield before helmet")

func test_unusable_and_non_item_assets_are_skipped(t) -> void:
	var recipe := Recipe.new()
	var gear: Dictionary = recipe._gear(_ctx([
		_asset("iron_sword", "ITEM", "UNUSED"), _asset("long_bow", "DECORATION"), _asset("short_bow"),
	]))
	t.eq(gear.keys(), ["bow"])
	t.eq(recipe._gear(_ctx([_asset("potion")])).size(), 0, "no names, no gear")

func test_the_seeded_items_carry_the_slot_the_bonus_and_the_names(t) -> void:
	var recipe := Recipe.new()
	var ctx := _ctx([_asset("iron_sword"), _asset("steel_armor")])
	var sword := recipe._gear_item(ctx, "sword", recipe._gear(ctx)["sword"]) as RpgItemDefinition
	t.eq(sword.id, &"sword")
	t.eq(sword.category, RpgItemDefinition.Category.WEAPON)
	t.eq(sword.display_name, "ITEM_SWORD_NAME")
	t.eq(sword.modifiers.size(), 1)
	t.eq(sword.modifiers[0]["stat"], "attack")
	t.near(RpgUtil.to_float(sword.modifiers[0]["add"]), 2.0)
	t.ok(sword.icon != null)
	var armor := recipe._gear_item(ctx, "armor", recipe._gear(ctx)["armor"]) as RpgItemDefinition
	t.eq(armor.category, RpgItemDefinition.Category.ARMOR)
	t.eq(armor.modifiers[0]["stat"], "defense")
	for word in Recipe.WEAPON_WORDS + Recipe.ARMOR_WORDS:
		t.ok(Recipe.SEED_STRINGS.has("ITEM_%s_NAME" % word.to_upper()), word)
		t.ok(Recipe.SEED_STRINGS.has("ITEM_%s_DESC" % word.to_upper()), word)

func test_the_new_game_data_starts_with_the_gear_in_the_bag(t) -> void:
	var recipe := Recipe.new()
	var ng: Resource = recipe._new_game(false, ["sword", "armor"])
	var ids: Array = []
	for entry: Dictionary in ng.get("items"):
		ids.append(entry["item_id"])
	t.eq(ids, ["potion", "sword", "armor"])
	var bare: Resource = recipe._new_game(true, [])
	t.eq((bare.get("items") as Array).size(), 0)
