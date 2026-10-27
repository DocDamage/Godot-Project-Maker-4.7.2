extends RefCounted
## Skill trees (1.5.0): ranks bought with points, requirements, rows that open, unlearning that
## never breaks what is learned, resets, the bonuses on the stats, the battle skills, levels that
## give points, the save and the menu.

const Fixtures := preload("../lib/fixtures.gd")

var _english: Translation = null

## Warrior: blade (row 0, 3 ranks, +2 attack each) -> cleave (row 1, needs blade 2, cost 2,
## teaches the battle skill "cleave"); guard (row 0, +1 defense). A row opens every 2 points.
func _tree() -> RpgSkillTree:
	var tree := RpgSkillTree.new()
	tree.id = &"warrior"
	tree.title = "Warrior"
	tree.points_per_row = 2
	tree.reset_gold = 30
	var skills: Array[Dictionary] = [
		{"id": "blade", "title": "Blade", "cell": [0, 0], "max_rank": 3, "bonuses": [{"stat": "attack", "add": 2}]},
		{"id": "guard", "title": "Guard", "cell": [1, 0], "bonuses": [{"stat": "defense", "add": 1}]},
		{"id": "cleave", "title": "Cleave", "cell": [0, 1], "cost": 2, "requires": {"blade": 2}, "skill": "cleave"},
	]
	tree.skills = skills
	return tree

func _state() -> Node:
	if _english == null:
		_english = Fixtures.install_english()
	var state := Fixtures.install_state()
	state.new_game()
	state.skill_trees[&"warrior"] = _tree()
	state.gold = 100
	return state

func _end() -> void:
	Fixtures.uninstall_state()
	if _english != null:
		Fixtures.uninstall_english(_english)
		_english = null

func test_the_rules_of_learning(t) -> void:
	var tree := _tree()
	t.eq(tree.problems(), [])
	t.eq(tree.learn_problem({}, 0, &"blade"), RpgSkillTree.NO_POINTS)
	t.eq(tree.learn_problem({}, 5, &"cleave"), RpgSkillTree.NEEDS)
	t.eq(tree.missing({"blade": 1}, &"cleave"), {"blade": 2})
	t.eq(tree.learn_problem({"blade": 3}, 5, &"blade"), RpgSkillTree.MAX_RANK)
	t.eq(tree.learn_problem({"blade": 2}, 5, &"cleave"), RpgSkillTree.OK, "two points spent open row 1")
	tree.points_per_row = 3
	t.eq(tree.learn_problem({"blade": 2}, 5, &"cleave"), RpgSkillTree.ROW_LOCKED, "now it takes three")
	t.eq(tree.learn_problem({}, 5, &"nope"), RpgSkillTree.UNKNOWN)

func test_unlearning_never_breaks_what_is_learned(t) -> void:
	var tree := _tree()
	var ranks := {"blade": 2, "cleave": 1}
	t.eq(tree.unlearn_problem(ranks, &"blade"), RpgSkillTree.NEEDED, "cleave needs blade 2")
	t.eq(tree.unlearn_problem(ranks, &"cleave"), RpgSkillTree.OK)
	t.eq(tree.unlearn_problem({"blade": 3, "cleave": 1}, &"blade"), RpgSkillTree.OK, "blade 3 to 2 still holds")
	t.eq(tree.unlearn_problem({}, &"guard"), RpgSkillTree.NOT_LEARNED)
	# a row that would close: guard and blade paid for row 1; cleave stands on it
	var gated := _tree()
	var skills: Array[Dictionary] = [
		{"id": "a", "cell": [0, 0]}, {"id": "b", "cell": [1, 0]}, {"id": "c", "cell": [0, 1]},
	]
	gated.skills = skills
	t.eq(gated.unlearn_problem({"a": 1, "b": 1, "c": 1}, &"b"), RpgSkillTree.NEEDED, "row 1 would close")
	t.eq(gated.unlearn_problem({"a": 1, "b": 1}, &"b"), RpgSkillTree.OK)

func test_tree_problems(t) -> void:
	var tree := RpgSkillTree.new()
	var skills: Array[Dictionary] = [
		{"id": "a", "cell": [0, 1], "requires": {"b": 1, "ghost": 1}},
		{"id": "b", "cell": [0, 1]},
		{"id": "a", "cell": [2, 2]},
	]
	tree.skills = skills
	var found := tree.problems()
	t.ok(found.has("the tree has no id"), str(found))
	t.ok(found.has("skill 2 (b) is on the cell of another skill"), str(found))
	t.ok(found.has("skill 3 (a) repeats the id of an earlier skill"), str(found))
	t.ok(found.has("skill 1 (a) requires the unknown skill 'ghost'"), str(found))
	t.ok(found.has("skill 1 (a) requires 'b', which is not on an earlier row"), str(found))

func test_learning_spends_points_and_the_bonuses_reach_the_stats(t) -> void:
	var state := _state()
	var attack: float = state.stat_of(&"hero", &"attack")
	t.eq(state.learn_skill(&"hero", &"warrior", &"blade"), RpgSkillTree.NO_POINTS)
	state.give_skill_points(&"hero", 5)
	t.eq(state.learn_skill(&"hero", &"warrior", &"blade"), RpgSkillTree.OK)
	t.eq(state.learn_skill(&"hero", &"warrior", &"blade"), RpgSkillTree.OK)
	t.eq(state.points_of(&"hero"), 3)
	t.eq(state.stat_of(&"hero", &"attack"), attack + 4.0, "two ranks of +2")
	t.eq(state.learn_skill(&"hero", &"warrior", &"cleave"), RpgSkillTree.OK)
	t.eq(state.points_of(&"hero"), 1, "cleave costs two")
	t.eq(state.learned_battle_skills(&"hero"), [&"cleave"] as Array[StringName])
	t.eq(state.unlearn_skill(&"hero", &"warrior", &"blade"), RpgSkillTree.NEEDED)
	t.eq(state.unlearn_skill(&"hero", &"warrior", &"cleave"), RpgSkillTree.OK)
	t.eq(state.points_of(&"hero"), 3, "its points came back")
	t.eq(state.learned_battle_skills(&"hero"), [] as Array[StringName])
	_end()

func test_a_reset_gives_every_point_back_for_its_price(t) -> void:
	var state := _state()
	state.give_skill_points(&"hero", 4)
	t.eq(state.reset_skill_tree(&"hero", &"warrior"), RpgSkillTree.NOT_LEARNED)
	state.learn_skill(&"hero", &"warrior", &"blade")
	state.learn_skill(&"hero", &"warrior", &"blade")
	state.learn_skill(&"hero", &"warrior", &"cleave")
	t.eq(state.points_of(&"hero"), 0)
	state.gold = 10
	t.eq(state.reset_skill_tree(&"hero", &"warrior"), RpgShopDefinition.NOT_ENOUGH_GOLD)
	state.gold = 40
	t.eq(state.reset_skill_tree(&"hero", &"warrior"), RpgSkillTree.OK)
	t.eq([state.points_of(&"hero"), state.gold, state.ranks_of(&"hero", &"warrior")], [4, 10, {}])
	state.skill_tree_of(&"warrior").reset_gold = -1
	state.learn_skill(&"hero", &"warrior", &"guard")
	t.eq(state.reset_skill_tree(&"hero", &"warrior"), RpgSkillTree.UNKNOWN, "a tree that cannot be reset")
	_end()

func test_levels_give_points_and_the_save_keeps_them(t) -> void:
	var state := _state()
	state.give_experience_to(&"hero", 10)  # level 1 to 2
	t.eq(state.points_of(&"hero"), 1)
	state.learn_skill(&"hero", &"warrior", &"guard")
	var back: Dictionary = JSON.parse_string(JSON.stringify(state.to_dict()))
	t.eq(RpgUtil.restore_numbers(back["skill_ranks"]), {"hero": {"warrior": {"guard": 1}}})
	state.new_game()
	t.ok(not state.to_dict().has("skill_ranks") and not state.to_dict().has("skill_points"), "a new game has none")
	state.skill_trees[&"warrior"] = _tree()
	state.from_dict(back)
	t.eq(state.ranks_of(&"hero", &"warrior"), {"guard": 1})
	t.eq(state.points_of(&"hero"), 0)
	state.skill_trees.clear()
	var points: int = state.points_of(&"hero")
	state.give_experience_to(&"hero", 1000)
	t.eq(state.points_of(&"hero"), points, "a game without trees gives no points")
	_end()

func test_the_menu_learns_and_describes(t) -> void:
	var state := _state()
	state.give_skill_points(&"hero", 1)
	var menu := RpgSkillTreeMenu.new()
	Fixtures.tree().root.add_child(menu)
	t.eq(menu.tree_id, &"warrior", "the first tree")
	t.ok(menu.skill_button(&"blade") != null and menu.skill_button(&"cleave") != null)
	t.eq(menu.skill_button(&"cleave").position, Vector2(0, 1) * RpgSkillTreeMenu.CELL, "on its cell")
	t.eq(RpgSkillTreeMenu.detail_text(state, state.skill_tree_of(&"warrior"), &"hero", &"cleave"), "Cleave  rank 0/1\nNeeds Blade 2")
	t.eq(RpgSkillTreeMenu.detail_text(state, state.skill_tree_of(&"warrior"), &"hero", &"blade"), "Blade  rank 0/3\n+2 Attack")
	menu.skill_button(&"blade").pressed.emit()
	t.eq(state.ranks_of(&"hero", &"warrior"), {"blade": 1}, "confirming a skill learns a rank")
	t.eq(menu.skill_button(&"blade").text, "Blade 1/3")
	menu.selected = &"blade"
	t.eq(menu.learn(), RpgSkillTree.NO_POINTS)
	t.eq(menu.unlearn(), RpgSkillTree.OK)
	t.eq(state.points_of(&"hero"), 1)
	t.eq(RpgSkillTreeMenu.bonus_text([{"stat": "defense", "add": -1}, {"stat": "speed", "mul": 1.5}]), "-1 Defense, x1.5 Speed")
	menu.free()
	_end()

func test_the_validator_reports_what_is_wrong_with_game_data(t) -> void:
	var ContentChecks: GDScript = load("res://addons/rpg_project_tools/tools/content_checks.gd")
	var dir := "user://test_game_data_%d" % Time.get_ticks_usec()
	for sub: String in ["skill_trees", "achievements", "quests", "items", "item_sets", "none"]:
		DirAccess.make_dir_recursive_absolute(dir + "/" + sub)
	var tree := _tree()
	tree.id = &""
	ResourceSaver.save(tree, dir + "/skill_trees/broken.tres")
	var achievement := RpgAchievement.new()
	achievement.id = &"a"
	achievement.when = "count:nothing"
	ResourceSaver.save(achievement, dir + "/achievements/a.tres")
	var quest := RpgQuestDefinition.new()
	quest.id = &"q"
	ResourceSaver.save(quest, dir + "/quests/q.tres")
	var helm := Fixtures.item(&"helm", 1)
	helm.set_id = &"knight"
	ResourceSaver.save(helm, dir + "/items/helm.tres")
	var found: Array[String] = []
	var none := dir + "/none"
	for f: Dictionary in ContentChecks.call("run", {"maps": none, "items": dir + "/items", "dialogue": none, "skills": none, "actors": none, "enemies": none, "resources": [none], "placeholders": none + "/", "quests": dir + "/quests", "skill_trees": dir + "/skill_trees", "achievements": dir + "/achievements", "item_sets": dir + "/item_sets"}):
		if f["code"] == "VAL-034":
			found.append("%s: %s" % [str(f["file"]).get_file(), f["detail"]["problem"]])
	found.sort()
	t.eq(found, [
		"a.tres: achievement: what unlocks it: count needs <name>>=N: 'count:nothing'",
		"broken.tres: skill tree: the tree has no id",
		"helm.tres: the item belongs to the set 'knight', which has no file in %s/item_sets" % dir,
		"q.tres: quest: the quest has no stages",
	])
	for sub: String in ["skill_trees", "achievements", "quests", "items", "item_sets", "none"]:
		for file_name in DirAccess.get_files_at(dir + "/" + sub):
			DirAccess.remove_absolute(dir + "/" + sub + "/" + file_name)
		DirAccess.remove_absolute(dir + "/" + sub)
	DirAccess.remove_absolute(dir)
