extends RefCounted
## The quest journal (T12.48): definitions, the events and conditions, automatic stages, rewards,
## the journal menu and the save.

const Fixtures := preload("../lib/fixtures.gd")
const UiRecipes := preload("res://builder/recipes/ui_recipes.gd")
const SceneUtil := preload("res://builder/lib/scene_util.gd")
const DataRecipe := preload("res://builder/recipes/data_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")

const MENU_TMP := "user://test_journal_menu.tscn"

func _quest() -> RpgQuestDefinition:
	var def := RpgQuestDefinition.new()
	def.id = &"errand"
	def.title = "Errand"
	var stages: Array[Dictionary] = [
		{"id": "talk", "description": "Talk to the villager", "complete_when": "flag:npc.talked"},
		{"id": "chest", "description": "Open the chest", "complete_when": "flag:chest.opened"},
		{"id": "return", "description": "Go back", "complete_when": ""},
	]
	def.stages = stages
	def.rewards = {"gold": 25, "experience": 4, "items": [{"item_id": "potion", "qty": 2}]}
	return def

func _state() -> Node:
	var state := Fixtures.install_state({&"potion": Fixtures.item(&"potion")})
	state.new_game()
	state.inventory.slots.clear()
	state.gold = 0
	state.quest_defs[&"errand"] = _quest()
	return state

func _toasts() -> Array:
	var seen := []
	RpgUtil.events().notify.connect(func(text: String) -> void: seen.append(text))
	return seen

func test_conditions_read_the_stage(t) -> void:
	var state := _state()
	t.ok(not RpgCondition.evaluate("quest_active:errand"))
	t.ok(not RpgCondition.evaluate("quest_done:errand"))
	state.quest_start(&"errand")
	t.ok(RpgCondition.evaluate("quest_active:errand"))
	t.ok(RpgCondition.evaluate("quest_stage:errand:talk"))
	t.ok(not RpgCondition.evaluate("quest_stage:errand:chest"))
	t.ok(RpgCondition.evaluate("quest_active:errand and not quest_done:errand"))
	state.quest_complete(&"errand")
	t.ok(RpgCondition.evaluate("quest_done:errand"))
	t.ok(not RpgCondition.evaluate("quest_active:errand"), "a finished quest is not active")
	t.ok(RpgCondition.evaluate("quest:errand=done"), "the older quest: atom sees the same state")
	Fixtures.uninstall_state()

func test_the_events_start_move_and_finish_a_quest(t) -> void:
	var state := _state()
	t.ok(RpgDialogueRunner.execute_event("quest_start:errand"))
	t.eq(state.quest_state(&"errand"), "talk")
	t.ok(RpgDialogueRunner.execute_event("quest_stage:errand:return"))
	t.eq(state.quest_state(&"errand"), "return")
	t.ok(RpgDialogueRunner.execute_event("quest_complete:errand"))
	t.ok(state.quest_is_done(&"errand"))
	t.ok(not RpgDialogueRunner.execute_event("quest_start:"))
	t.ok(not RpgDialogueRunner.execute_event("quest_stage:errand"))
	t.ok(not RpgDialogueRunner.execute_event("quest_complete:"))
	Fixtures.uninstall_state()

func test_a_stage_that_does_not_exist_or_a_quest_not_started_is_refused(t) -> void:
	var state := _state()
	t.ok(not state.quest_set_stage(&"errand", &"chest"), "not started")
	state.quest_start(&"errand")
	t.ok(not state.quest_set_stage(&"errand", &"nowhere"))
	t.ok(not state.quest_set_stage(&"errand", &"done"))
	t.ok(not state.quest_start(&"errand"), "starting twice does nothing")
	t.eq(state.quest_state(&"errand"), "talk")
	Fixtures.uninstall_state()

func test_stages_move_on_by_themselves_and_the_last_one_completes(t) -> void:
	var state := _state()
	state.quest_start(&"errand")
	t.eq(state.quest_state(&"errand"), "talk")
	state.set_flag("npc", "talked", true)
	t.eq(state.quest_state(&"errand"), "chest")
	state.set_flag("chest", "opened", true)
	t.eq(state.quest_state(&"errand"), "return", "the last stage has no condition: an event finishes it")
	state.quest_complete(&"errand")
	t.ok(state.quest_is_done(&"errand"))
	Fixtures.uninstall_state()

func test_conditions_that_already_hold_skip_ahead_at_the_start(t) -> void:
	var state := _state()
	state.set_flag("npc", "talked", true)
	state.set_flag("chest", "opened", true)
	state.quest_start(&"errand")
	t.eq(state.quest_state(&"errand"), "return")
	Fixtures.uninstall_state()

func test_rewards_are_given_once_on_completion(t) -> void:
	var state := _state()
	var level: int = state.player_stats.level
	state.quest_start(&"errand")
	t.eq(state.gold, 0)
	state.quest_complete(&"errand")
	t.eq(state.gold, 25)
	t.eq(state.inventory.count(&"potion"), 2)
	t.eq(state.player_stats.experience + (state.player_stats.level - level) * 10, 4 + 0, "4 experience (level 1 needs 10)")
	t.ok(not state.quest_complete(&"errand"), "a second completion gives nothing")
	t.eq(state.gold, 25)
	t.eq(state.inventory.count(&"potion"), 2)
	Fixtures.uninstall_state()

func test_every_change_shows_a_toast(t) -> void:
	var english := Fixtures.install_english()
	var state := _state()
	var toasts := _toasts()
	state.quest_start(&"errand")
	state.set_flag("npc", "talked", true)
	state.quest_set_stage(&"errand", &"return")
	state.quest_complete(&"errand")
	t.eq(toasts, [
		"New quest: Errand", "Quest updated: Errand", "Quest updated: Errand", "Quest complete: Errand",
	])
	Fixtures.uninstall_state()
	Fixtures.uninstall_english(english)

func test_quests_survive_a_save_round_trip(t) -> void:
	var state := _state()
	state.quest_start(&"errand")
	state.set_flag("npc", "talked", true)
	state.quests["other"] = "done"
	var back: Dictionary = JSON.parse_string(JSON.stringify(state.to_dict()))
	state.new_game()
	t.eq(state.quests.size(), 0)
	state.from_dict(back)
	t.eq(state.quest_state(&"errand"), "chest")
	t.ok(state.quest_is_done(&"other"))
	state.set_flag("chest", "opened", true)
	t.eq(state.quest_state(&"errand"), "return", "the loaded quest keeps progressing")
	Fixtures.uninstall_state()

# ------------------------------------------------------------------ the journal

func _menu() -> RpgJournalMenu:
	var root: Node = UiRecipes.new().call("_build_journal_menu")
	SceneUtil.save_scene(root, MENU_TMP)
	var menu := (load(MENU_TMP) as PackedScene).instantiate() as RpgJournalMenu
	Fixtures.tree().root.add_child(menu)
	if not menu.is_node_ready():
		menu._ready()
	return menu

func test_the_journal_lists_active_and_completed_quests(t) -> void:
	var english := Fixtures.install_english()
	var state := _state()
	var other := _quest()
	other.id = &"side"
	other.title = "Side job"
	state.quest_defs[&"side"] = other
	var menu := _menu()
	t.eq(menu.rows().size(), 0)
	t.eq((menu.get_node("%Description") as Label).text, "No active quests")
	menu.free()
	state.quest_start(&"errand")
	state.quest_start(&"side")
	state.quest_complete(&"side")
	menu = _menu()
	t.eq(menu.rows().size(), 1)
	t.eq(menu.quest_of(menu.rows()[0]), &"errand")
	t.eq(menu.rows()[0].text, "Errand")
	menu.rows()[0].pressed.emit()
	t.eq((menu.get_node("%Description") as Label).text, "Errand\n> Talk to the villager")
	state.set_flag("npc", "talked", true)
	t.eq(RpgJournalMenu.detail_text(state, &"errand"), "Errand\n[x] Talk to the villager\n> Open the chest")
	menu.set_tab(RpgJournalMenu.FINISHED)
	t.eq(menu.rows().size(), 1)
	t.eq(menu.quest_of(menu.rows()[0]), &"side")
	t.eq(RpgJournalMenu.detail_text(state, &"side"), "Side job\n[x] Talk to the villager\n[x] Open the chest\n[x] Go back")
	menu.free()
	Fixtures.uninstall_state()
	Fixtures.uninstall_english(english)

func test_the_journal_focus_chain_covers_both_tabs(t) -> void:
	var english := Fixtures.install_english()
	var state := _state()
	state.quest_start(&"errand")
	var menu := _menu()
	for tab in [RpgJournalMenu.ACTIVE, RpgJournalMenu.FINISHED]:
		menu.set_tab(tab)
		var all := RpgMenuUtil.focusables(menu)
		var reached: Array = []
		var current: Control = all[0]
		while current != null and not reached.has(current) and reached.size() < 50:
			reached.append(current)
			current = current.get_node_or_null(current.focus_neighbor_bottom) as Control
		t.eq(reached.size(), all.size(), "tab %s" % tab)
	menu.free()
	Fixtures.uninstall_state()
	Fixtures.uninstall_english(english)

# ------------------------------------------------------------------ the demo

func test_the_demo_quest_and_the_villagers_lines(t) -> void:
	var recipe := DataRecipe.new()
	var quest: RpgQuestDefinition = recipe._quest()
	t.eq(quest.id, &"errand")
	t.eq(quest.stage_ids(), [&"talk", &"chest", &"return"] as Array[StringName])
	t.eq(quest.stage(0)["complete_when"], "flag:starter_npc.talked")
	t.eq(quest.stage(1)["complete_when"], "flag:starter_map_chest_001.opened")
	t.eq(quest.stage(2)["complete_when"], "flag:starter_npc.reported")
	t.eq(RpgUtil.to_int(quest.rewards["gold"]), 25)
	for key in [quest.title, quest.stage(0)["description"], quest.stage(1)["description"], quest.stage(2)["description"]]:
		t.ok(DataRecipe.SEED_STRINGS.has(key), key)
	var no_chest: RpgQuestDefinition = recipe._quest(false)
	t.eq(no_chest.stage_ids(), [&"talk", &"return"] as Array[StringName], "no chest, no chest stage")
	var greeting: RpgDialogueResource = recipe._greeting()
	t.eq(Array(greeting.lines[0].events), ["quest_start:errand"])
	var report: RpgDialogueLine = null
	for line in greeting.lines:
		if line.id == &"report":
			report = line
	t.ok(report != null)
	t.eq(Array(report.events), ["set_flag:starter_npc.reported=true"])
	var conditions: Array = []
	for choice in greeting.lines[1].choices:
		conditions.append(choice.condition)
	t.ok(conditions.has("quest_stage:errand:return"), "the report is offered only at the last stage")
	t.ok(recipe.outputs(BuildContext.new("")).has(DataRecipe.QUEST_PATH) or FileAccess.file_exists(DataRecipe.QUEST_PATH))
	var demo_free := BuildContext.new("")
	demo_free.demo_removed = true
	t.ok(not recipe.outputs(demo_free).has(DataRecipe.QUEST_PATH))
