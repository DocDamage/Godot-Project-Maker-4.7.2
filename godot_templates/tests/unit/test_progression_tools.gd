extends RefCounted
## The dock's Skills, Achievements and Item sets tabs (1.5.0), and what the generator seeds with
## the feature `progression`: the adventurer's tree, the achievements, the traveler's set.

const SkillTreeTab := preload("res://addons/rpg_project_tools/dock/skill_tree_tab.gd")
const AchievementTab := preload("res://addons/rpg_project_tools/dock/achievement_tab.gd")
const ItemSetTab := preload("res://addons/rpg_project_tools/dock/item_set_tab.gd")
const ProgressionRecipe := preload("res://builder/recipes/progression_recipe.gd")
const DataRecipe := preload("res://builder/recipes/data_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")

func _folder(label: String) -> String:
	var folder := "user://test_%s_%d" % [label, Time.get_ticks_usec()]
	DirAccess.make_dir_recursive_absolute(folder)
	return folder

func _remove(folder: String) -> void:
	for file_name in DirAccess.get_files_at(folder):
		DirAccess.remove_absolute(folder.path_join(file_name))
	DirAccess.remove_absolute(folder)

# ---------------------------------------------------------------- the Skills tab

func test_the_skills_tab_edits_a_tree_in_undo_steps(t) -> void:
	var folder := _folder("skills_tab")
	ResourceSaver.save(ProgressionRecipe.tree("turn_based"), folder + "/adventurer.tres")
	var undo := UndoRedo.new()
	var tab: VBoxContainer = SkillTreeTab.new()
	tab.set("trees_dir", folder)
	tab.set("undo_redo", undo)
	tab.call("rescan")
	var tree: RpgSkillTree = tab.get("tree")
	t.eq(tree.id, &"adventurer", "the first file is opened")
	t.eq(tab.call("skill_label", 0), "vigor (0, 0)")
	tab.call("edit_skill", 0, "max_rank", 5)
	t.eq(RpgSkillTree.max_rank_of(tree.skills[0]), 5)
	t.ok(undo.undo())
	t.eq(RpgSkillTree.max_rank_of(tree.skills[0]), 3, "one undo step")
	tab.call("select_skill", 3)
	tab.call("_edit_cell", 2, -1)
	t.eq(RpgSkillTree.cell_of(tree.skills[3]), Vector2i(2, 1), "the column moves, the row stays")
	t.ok(str(tab.call("skill_label", 3)).begins_with("⚠ "), "now on the cell of swift")
	undo.undo()
	tab.call("edit_skill", 1, "requires", SkillTreeTab.parse_requires("vigor 2, guard"))
	t.eq(tree.skills[1]["requires"], {"vigor": 2, "guard": 1})
	tab.call("edit_skill", 1, "requires", SkillTreeTab.parse_requires(""))
	t.ok(not tree.skills[1].has("requires"), "nothing required takes the key away")
	tab.call("add_skill")
	t.eq([tree.skills.size(), tree.skills[6]["id"], tree.skills[6]["cell"]], [7, "skill_7", [3, 1]], "on the first free cell of the bottom row")
	tab.call("remove_skill")
	t.eq(tree.skills.size(), 6)
	tab.call("set_tree_property", "points_per_row", 3)
	t.eq(tree.points_per_row, 3)
	t.ok(tab.call("save"))
	var json_path: String = tab.call("export_json")
	var imported: String = tab.call("import_json", json_path)
	var back := load(imported) as RpgSkillTree
	t.eq(back.to_dict(), tree.to_dict(), "JSON round trip")
	tab.free()
	_remove(folder)

func test_bonus_and_requirement_texts(t) -> void:
	var bonuses := [{"stat": "attack", "add": 2}, {"stat": "speed", "mul": 1.1}, {"stat": "defense", "add": -1}]
	t.eq(SkillTreeTab.bonuses_text(bonuses), "attack +2\nspeed x1.1\ndefense -1")
	t.eq(SkillTreeTab.parse_bonuses("attack +2\nspeed x1.1, defense -1\nnonsense"), bonuses)
	t.eq(SkillTreeTab.requires_text({"blade": 2, "guard": 1}), "blade 2, guard")
	t.eq(ItemSetTab.parse_bonuses("2: defense +5, attack +1\n3: speed x1.5\nbad line"), [
		{"pieces": 2, "modifiers": [{"stat": "defense", "add": 5}, {"stat": "attack", "add": 1}]},
		{"pieces": 3, "modifiers": [{"stat": "speed", "mul": 1.5}]},
	] as Array[Dictionary])
	t.eq(ItemSetTab.bonuses_text(ItemSetTab.parse_bonuses("2: defense +5, attack +1")), "2: defense +5, attack +1")

# ---------------------------------------------------------------- the Achievements tab

func test_the_achievements_tab_edits_and_tests(t) -> void:
	var folder := _folder("achievements_tab")
	var undo := UndoRedo.new()
	var tab: VBoxContainer = AchievementTab.new()
	tab.set("achievements_dir", folder)
	tab.set("undo_redo", undo)
	tab.call("rescan")
	var made: String = tab.call("new_achievement")
	t.eq(made.get_file(), "new_achievement.tres")
	var achievement: RpgAchievement = tab.get("achievement")
	t.eq(achievement.when, "count:defeated>=1")
	tab.call("set_property", "when", "count:defeated>=10")
	tab.call("set_property", "rewards", RpgUtil.to_dict(load("res://addons/rpg_project_tools/dock/quest_tab.gd").call("parse_rewards", "gold 20")))
	t.eq([achievement.when, achievement.rewards], ["count:defeated>=10", {"gold": 20}])
	undo.undo()
	t.eq(achievement.rewards, {}, "one undo step")
	t.ok(not tab.call("run_test"))
	(tab.get("_test_counter") as LineEdit).text = "defeated"
	(tab.get("_test_count") as SpinBox).value = 10
	t.ok(tab.call("run_test"), "ten defeated unlock it")
	tab.call("set_icon", "res://nothing_here.png")
	t.eq(achievement.icon, null, "a path that is no texture is refused")
	tab.call("set_property", "when", "count:nope")
	t.ok(tab.call("problems").size() > 0)
	tab.free()
	_remove(folder)

# ---------------------------------------------------------------- the Item sets tab

func test_the_item_sets_tab_puts_items_in_the_set(t) -> void:
	var sets := _folder("sets_tab")
	var items := _folder("sets_items")
	ResourceSaver.save(ProgressionRecipe.gear_set(), sets + "/traveler.tres")
	for word: String in ["sword", "armor", "potion"]:
		var item := RpgItemDefinition.new()
		item.id = StringName(word)
		ResourceSaver.save(item, "%s/%s.tres" % [items, word])
	var undo := UndoRedo.new()
	var tab: VBoxContainer = ItemSetTab.new()
	tab.set("sets_dir", sets)
	tab.set("items_dir", items)
	tab.set("undo_redo", undo)
	tab.call("rescan")
	t.eq(tab.call("members"), [] as Array[String])
	t.ok(tab.call("problems").has("fewer items name the set than its first bonus needs (2)"))
	tab.call("add_member", "sword")
	tab.call("add_member", "armor")
	t.eq(tab.call("members"), ["armor", "sword"] as Array[String])
	t.eq((ResourceLoader.load(items + "/sword.tres", "", ResourceLoader.CACHE_MODE_REPLACE) as RpgItemDefinition).set_id, &"traveler", "the item's file is saved")
	undo.undo()
	t.eq(tab.call("members"), ["sword"] as Array[String], "one undo step")
	tab.call("set_durability", "sword", 30)
	t.eq((ResourceLoader.load(items + "/sword.tres", "", ResourceLoader.CACHE_MODE_REPLACE) as RpgItemDefinition).durability, 30)
	tab.call("remove_member", "sword")
	t.eq(tab.call("members"), [] as Array[String])
	tab.free()
	_remove(sets)
	_remove(items)

func test_the_dock_has_the_three_tabs(t) -> void:
	var source := FileAccess.get_file_as_string("res://addons/rpg_project_tools/dock/asset_dock.gd")
	t.ok(source.contains("SkillTreeTab.new()") and source.contains("AchievementTab.new()") and source.contains("ItemSetTab.new()"))
	for pair: Array in [[SkillTreeTab, "Skills"], [AchievementTab, "Achievements"], [ItemSetTab, "Item sets"]]:
		var tab: Node = (pair[0] as GDScript).new()
		t.eq(String(tab.name), pair[1])
		tab.free()

# ---------------------------------------------------------------- what the generator seeds

func _ctx(kind: String, features: Dictionary) -> BuildContext:
	var ctx := BuildContext.new("")
	ctx.config = {"archetype": kind, "features": features}
	return ctx

func test_nothing_is_seeded_without_the_feature(t) -> void:
	var recipe := ProgressionRecipe.new()
	t.eq(recipe.outputs(_ctx("turn_based", {"demo": true})), PackedStringArray(), "a config from before 1.5.0")
	t.eq(recipe.outputs(_ctx("shmup", {"progression": true})), PackedStringArray(), "an arcade kind has none")
	t.eq(recipe.input_hash(_ctx("turn_based", {})), recipe.input_hash(_ctx("arpg", {})), "the same hash whatever the kind")
	t.ok(not ProgressionRecipe.on(_ctx("assets", {"progression": true})))

func test_the_seeded_tree_and_achievements(t) -> void:
	for kind: String in ["turn_based", "arpg", "metroidvania"]:
		var tree := ProgressionRecipe.tree(kind) as RpgSkillTree
		t.eq(tree.problems(), [], kind)
		t.eq(tree.skill_ids().size(), 6, kind)
	var turn_based := ProgressionRecipe.tree("turn_based") as RpgSkillTree
	t.eq(turn_based.skill(&"healing")["skill"], "cure", "turn-based: the Cure spell")
	t.ok(turn_based.skill(&"toughness").is_empty())
	var arpg := ProgressionRecipe.tree("arpg") as RpgSkillTree
	t.eq(arpg.skill(&"swift")["bonuses"], [{"stat": "move_speed", "mul": 1.1}], "walking speed in real time")
	var fighting := ProgressionRecipe.achievements(_ctx("turn_based", {"progression": true, "combat": true, "demo": true}))
	t.ok(fighting.has("errand") and fighting.has("hunter") and fighting.has("seasoned") and fighting.has("savings"), str(fighting.keys()))
	var farm := ProgressionRecipe.achievements(_ctx("farm", {"progression": true, "combat": false, "demo": true}))
	t.eq(farm.keys(), ["errand", "savings"], "a farm that does not fight")
	t.eq(farm["savings"]["when"], "gold>=2000")
	var rooms := ProgressionRecipe.achievements(_ctx("metroidvania", {"progression": true, "combat": true, "demo": true}))
	t.ok(not rooms.has("errand"), "a metroidvania has no village errand")
	for achievement_id: String in fighting:
		var made := ProgressionRecipe.achievement(achievement_id, fighting[achievement_id]) as RpgAchievement
		t.eq(made.problems(), [], achievement_id)
		t.ok(ProgressionRecipe.SEED_STRINGS.has(made.title) and ProgressionRecipe.SEED_STRINGS.has(made.description), achievement_id)
	for row in turn_based.skills:
		t.ok(ProgressionRecipe.SEED_STRINGS.has(str(row["title"])) and ProgressionRecipe.SEED_STRINGS.has(str(row["description"])), str(row["id"]))
	var traveler := ProgressionRecipe.gear_set() as RpgItemSet
	t.eq(traveler.problems(), [])
	t.ok(ProgressionRecipe.SEED_STRINGS.has(traveler.title))

func test_the_starter_gear_names_its_set_only_with_the_feature(t) -> void:
	var recipe := DataRecipe.new()
	var both := {"sword": {}, "armor": {}}
	t.ok(recipe._gear_set(_ctx("turn_based", {"progression": true}), both))
	t.ok(not recipe._gear_set(_ctx("turn_based", {}), both), "a config from before 1.5.0")
	t.ok(not recipe._gear_set(_ctx("turn_based", {"progression": true}), {"sword": {}}), "a weapon alone is no set")

# ---------------------------------------------------------------- the TileSet's patterns (found with the 1.1 regeneration test)

func test_a_rebuild_keeps_the_patterns_it_would_make_again(t) -> void:
	var TilesetRecipe: GDScript = load("res://builder/recipes/tileset_recipe.gd")
	var a := TileMapPattern.new()
	a.set_cell(Vector2i(0, 0), 3, Vector2i(4, 5), 0)
	a.set_cell(Vector2i(1, 0), 3, Vector2i(5, 5), 0)
	var b := TileMapPattern.new()
	b.set_cell(Vector2i(0, 0), 3, Vector2i(4, 5), 0)
	b.set_cell(Vector2i(1, 0), 3, Vector2i(5, 5), 0)
	t.ok(TilesetRecipe.call("patterns_equal", a, b))
	b.set_cell(Vector2i(1, 0), 3, Vector2i(6, 5), 0)
	t.ok(not TilesetRecipe.call("patterns_equal", a, b), "another atlas cell")
	b.set_cell(Vector2i(1, 0), 3, Vector2i(5, 5), 1)
	t.ok(not TilesetRecipe.call("patterns_equal", a, b), "another alternative")
	var c := TileMapPattern.new()
	c.set_cell(Vector2i(0, 0), 3, Vector2i(4, 5), 0)
	t.ok(not TilesetRecipe.call("patterns_equal", a, c), "fewer cells")
	t.ok(not TilesetRecipe.call("patterns_equal", a, null))

func test_terrains_are_completed_only_in_a_source_this_version_made(t) -> void:
	var TilesetRecipe: GDScript = load("res://builder/recipes/tileset_recipe.gd")
	var src := TileSetAtlasSource.new()
	src.texture = PlaceholderTexture2D.new()
	(src.texture as PlaceholderTexture2D).size = Vector2(32, 16)
	src.texture_region_size = Vector2i(16, 16)
	src.create_tile(Vector2i(0, 0))
	src.create_tile(Vector2i(1, 0))
	t.ok(not TilesetRecipe.call("completes", src), "a source of an older version: no alternatives, no mark")
	src.create_alternative_tile(Vector2i(1, 0))
	t.ok(TilesetRecipe.call("completes", src), "alternatives: a source of 1.5.0")
	var marked := TileSetAtlasSource.new()
	marked.set_meta(TilesetRecipe.get("COMPLETE_META"), true)
	t.ok(TilesetRecipe.call("completes", marked), "the mark")
