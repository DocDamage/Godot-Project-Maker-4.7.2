extends RefCounted

const Index := preload("res://addons/rpg_project_tools/dock/index.gd")
const DemoTools := preload("res://addons/rpg_project_tools/dock/demo_tools.gd")
const Rebuild := preload("res://addons/rpg_project_tools/tools/rebuild.gd")
const FileHash := preload("res://addons/rpg_project_tools/tools/file_hash.gd")
const Maps := preload("res://tests/lib/map_fixtures.gd")

func test_every_tools_script_loads(t) -> void:
	for dir_path in ["res://addons/rpg_project_tools", "res://addons/rpg_project_tools/tools", "res://addons/rpg_project_tools/dock"]:
		var dir := DirAccess.open(dir_path)
		for f in dir.get_files():
			if f.get_extension() == "gd":
				t.ok(load(dir_path + "/" + f) is GDScript, "%s/%s loads" % [dir_path, f])

func test_categories(t) -> void:
	t.eq(Index.category_of("BUILDING", ["door"], "object"), "Buildings")
	t.eq(Index.category_of("DECORATION", ["chest"], "object"), "Interactables")
	t.eq(Index.category_of("DECORATION", [], "object"), "Decorations")
	t.eq(Index.category_of("INTERIOR", [], "object"), "Interior")
	t.eq(Index.category_of("ITEM", [], "object"), "Items")
	t.eq(Index.category_of("NPC", [], "character"), "Characters")
	t.eq(Index.category_of("ENEMY", [], "character"), "Enemies")
	t.eq(Index.category_of("", [], "enemy"), "Enemies")
	t.eq(Index.category_of("GROUND", [], "object"), "")

func test_filter_searches_name_id_and_tags_case_insensitively(t) -> void:
	var entries := [
		{"id": "p.town#red_house", "name": "Red House", "category": "Buildings", "tags": ["door"]},
		{"id": "p.props#barrel", "name": "Barrel", "category": "Decorations", "tags": ["container"]},
		{"id": "p.props#chest", "name": "Chest", "category": "Interactables", "tags": ["chest"]},
	]
	t.eq(Index.filter(entries, "", "All").size(), 3)
	t.eq(Index.filter(entries, "HOUSE", "All").size(), 1)
	t.eq(Index.filter(entries, "props", "All").size(), 2, "ids are searched")
	t.eq(Index.filter(entries, "contain", "All").size(), 1, "tags are searched")
	t.eq(Index.filter(entries, "", "Buildings").size(), 1)
	t.eq(Index.filter(entries, "chest", "Buildings").size(), 0)

func test_rebuild_arguments(t) -> void:
	var args := Rebuild.build_arguments()
	t.ok(args.has("--headless"))
	t.ok(args.has("res://generated/builder/build.gd"))
	t.ok(args.find("--") > args.find("--script"), "the flag follows the user-args separator")
	t.eq(args[args.size() - 1], "--update-ledger")
	t.eq(Rebuild.generator_command("", "C:/p"), PackedStringArray())
	t.eq(Rebuild.generator_command("rpggen.exe", "C:/p"), PackedStringArray(["rpggen.exe", "--target", "C:/p"]))
	t.ok(Rebuild.has_errors([{"severity": "error"}]))
	t.ok(not Rebuild.has_errors([{"severity": "warning"}]))

func test_demo_ids_from_the_recipe_file_or_the_defaults(t) -> void:
	t.eq(DemoTools.demo_ids({"entities": ["a_npc_001"]}), ["a_npc_001"])
	t.eq(DemoTools.demo_ids({}), DemoTools.DEFAULT_IDS)

func test_demo_nodes_and_doors(t) -> void:
	var root := Maps.map("starter_map")
	var ents := Maps.entities_of(root)
	Maps.entity(ents, "Npc", "starter_map_npc_001")
	Maps.entity(ents, "Mine", "starter_map_npc_002")
	Maps.door(root, "Door", DemoTools.INTERIOR_PATH)
	Maps.door(root, "Other", "res://game/maps/elsewhere.tscn")
	var nodes := DemoTools.demo_nodes(root, ["starter_map_npc_001"])
	t.eq(nodes.size(), 1)
	t.eq(nodes[0].name, &"Npc")
	var doors := DemoTools.doors_targeting(root, DemoTools.INTERIOR_PATH)
	t.eq(doors.size(), 1)
	t.eq(doors[0].name, &"Door")
	root.free()

func test_ledger_after_removal(t) -> void:
	var ledger := {"ledger_version": 1, "files": {"game/maps/interior_1.tscn": {"sha256": "x"}}, "deleted_by_user": ["b.tscn"]}
	var out := DemoTools.updated_ledger(ledger, ["game/maps/interior_1.tscn", "b.tscn"])
	t.eq(out["demo_removed"], true)
	t.eq(out["deleted_by_user"], ["b.tscn", "game/maps/interior_1.tscn"])
	t.ok(not ledger.has("demo_removed"), "the input is not changed")
	t.eq(out["files"], ledger["files"])

func test_untouched_compares_with_the_ledger_hash(t) -> void:
	var path := "user://m8_untouched.tscn"
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string("[gd_scene]\n")
	f.close()
	var key := "user://m8_untouched.tscn".trim_prefix("res://")
	var ledger := {"files": {key: {"sha256": FileHash.file_hash(path)}}}
	t.ok(DemoTools.untouched(ledger, path))
	ledger["files"][key]["sha256"] = "0".repeat(64)
	t.ok(not DemoTools.untouched(ledger, path), "a changed file is the user's")
	t.ok(not DemoTools.untouched({}, path), "unknown to the ledger")
	DirAccess.remove_absolute(path)

# ---------------------------------------------------------------- the Dialogue tab (T12.61)

const DialogueTab := preload("res://addons/rpg_project_tools/dock/dialogue_tab.gd")

static func _dialogue() -> RpgDialogueResource:
	return RpgDialogueJson.from_json(JSON.stringify({"lines": [
		{"id": "hi", "speaker": "Ana", "text": "Hello [b]traveller[/b]."},
		{"text": "You have the key!", "condition": "item:key", "next": "end"},
		{"text": "Come back with the key.", "choices": [{"text": "Bye", "next": "end"}]},
		{"id": "end", "text": "Farewell.", "events": ["set_flag:ana.met=true"]},
	]}))

func test_an_edit_round_trip_saves_the_resource(t) -> void:
	var path := "user://test_dialogue_tab_%d.tres" % Time.get_ticks_usec()
	t.eq(ResourceSaver.save(_dialogue(), path), OK)
	var tab := DialogueTab.new()  # no editor: edits apply directly, as without undo
	t.ok(tab.open(path))
	tab.edit_line(0, "speaker", "Bo")
	tab.edit_line(2, "choices", DialogueTab.parse_choices("Wait | hi\nBye | end | flag:ana.met"))
	tab.edit_line(1, "events", DialogueTab.parse_events("give_gold:5\n\n"))
	t.ok(tab.dirty)
	t.ok(tab.save())
	var again := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_IGNORE) as RpgDialogueResource
	t.eq(again.lines[0].speaker, "Bo")
	t.eq(DialogueTab.choices_text(again.lines[2].choices), "Wait | hi\nBye | end | flag:ana.met")
	t.eq(again.lines[1].events, PackedStringArray(["give_gold:5"]))
	tab.free()
	DirAccess.remove_absolute(path)

func test_the_condition_preview_and_inline_problems(t) -> void:
	var state := RpgGameState.new()
	t.eq(DialogueTab.condition_preview("", state), "")
	t.eq(DialogueTab.condition_preview("flag:ana.met", state), "with the test state: skipped")
	DialogueTab.set_test_atom(state, "flag:ana.met", true)
	t.eq(DialogueTab.condition_preview("flag:ana.met", state), "with the test state: shown")
	t.ok(DialogueTab.condition_preview("banana:split", state).contains("unknown condition 'banana:split'"))
	t.ok(DialogueTab.condition_preview("gold>=x and", state).begins_with("⚠"))
	var line := RpgDialogueLine.new()
	line.events = PackedStringArray(["explode", "give_gold:many", "give_item:potion:2"])
	line.next = &"nowhere"
	var found := DialogueTab.line_problems(line, [&"hi"])
	t.eq(found.size(), 3, str(found))
	t.ok(found[0].contains("unknown event 'explode'") and found[2].contains("nowhere"))
	state.free()

func test_the_tab_marks_a_line_that_names_an_unknown_id(t) -> void:
	var folder := "user://test_dialogue_ids_%d" % Time.get_ticks_usec()
	DirAccess.make_dir_recursive_absolute(folder + "/shops")
	t.eq(ResourceSaver.save(Resource.new(), folder + "/shops/village_shop.tres"), OK)
	var path := folder + "/talk.tres"
	t.eq(ResourceSaver.save(_dialogue(), path), OK)
	var tab := DialogueTab.new()
	tab.data_dirs = {"shops": folder + "/shops", "quests": folder + "/quests", "actors": folder + "/actors"}
	tab.rescan()
	t.eq(tab.data_ids["shop"], ["village_shop"])
	t.ok(tab.open(path))
	tab.edit_line(0, "events", DialogueTab.parse_events("open_shop:village_shop"))
	t.ok(not tab.line_label(0).begins_with("⚠"), tab.line_label(0))
	tab.edit_line(0, "events", DialogueTab.parse_events("open_shop:vilage_shop"))
	t.ok(tab.line_label(0).begins_with("⚠"), "the typo is marked in the list")
	var found := DialogueTab.line_problems(tab.dialogue.lines[0], DialogueTab.line_ids(tab.dialogue), tab.data_ids)
	t.ok("unknown shop 'vilage_shop'" in found, str(found))
	tab.free()
	DirAccess.remove_absolute(path)
	DirAccess.remove_absolute(folder + "/shops/village_shop.tres")
	DirAccess.remove_absolute(folder + "/shops")
	DirAccess.remove_absolute(folder)

func test_json_export_and_import_round_trip(t) -> void:
	var res := _dialogue()
	var text := RpgDialogueJson.to_json(res)
	var back := RpgDialogueJson.from_json(text)
	t.eq(RpgDialogueJson.to_dict(back), RpgDialogueJson.to_dict(res))
	t.eq(back.lines[3].events, PackedStringArray(["set_flag:ana.met=true"]))
	t.eq(String(back.lines[2].choices[0].next), "end")

func test_the_test_player_follows_the_toggled_state(t) -> void:
	var path := "user://test_dialogue_play_%d.tres" % Time.get_ticks_usec()
	ResourceSaver.save(_dialogue(), path)
	var tab := DialogueTab.new()
	tab.open(path)
	t.eq(DialogueTab.test_atoms(tab.dialogue), ["item:key"])
	t.ok(tab.test_text().contains("Hello"))
	tab._player.advance()
	tab._show_player()
	t.ok(tab.test_text().contains("Come back"), "no key: the key line is skipped")
	DialogueTab.set_test_atom(tab.test_state, "item:key", true)
	tab.play_from_start()
	tab._player.advance()
	tab._show_player()
	t.ok(tab.test_text().contains("You have the key"), tab.test_text())
	tab._player.advance()  # jumps to "end", whose event sets the flag on the test state only
	t.eq(tab.test_state.get_flag("ana", "met", false), true)
	tab.test_state.free()
	tab.free()
	DirAccess.remove_absolute(path)

# ---------------------------------------------------------------- the Quests tab (T13.19)

const QuestTab := preload("res://addons/rpg_project_tools/dock/quest_tab.gd")
const SequenceTab := preload("res://addons/rpg_project_tools/dock/sequence_tab.gd")

static func _quest() -> RpgQuestDefinition:
	return RpgQuestDefinition.from_dict({
		"id": "errand", "title": "QUEST_ERRAND_TITLE",
		"stages": [
			{"id": "talk", "description": "QUEST_TALK", "complete_when": "flag:npc.talked", "target": "town_npc_001"},
			{"id": "chest", "description": "QUEST_CHEST", "complete_when": "item:key"},
			{"id": "return", "description": "QUEST_RETURN", "complete_when": "gold>=10"},
		],
		"rewards": {"gold": 25, "experience": 5},
	})

func _folder(label: String) -> String:
	var folder := "user://test_%s_%d" % [label, Time.get_ticks_usec()]
	DirAccess.make_dir_recursive_absolute(folder)
	return folder

func _remove(folder: String) -> void:
	for file_name in DirAccess.get_files_at(folder):
		DirAccess.remove_absolute(folder.path_join(file_name))
	DirAccess.remove_absolute(folder)

func _quest_tab(folder: String, undo: UndoRedo = null) -> VBoxContainer:
	t_save(_quest(), folder + "/errand.tres")
	var tab: VBoxContainer = QuestTab.new()
	tab.set("quests_dir", folder)
	tab.set("undo_redo", undo)
	tab.call("rescan")
	return tab

func t_save(res: Resource, path: String) -> void:
	ResourceSaver.save(res, path)

func test_a_stage_edit_round_trips_and_is_one_undo_step(t) -> void:
	var folder := _folder("quest_tab")
	var undo := UndoRedo.new()
	var tab := _quest_tab(folder, undo)
	var quest: RpgQuestDefinition = tab.get("quest")
	t.eq(String(quest.id), "errand", "the first file is opened")
	t.eq(tab.call("stage_label", 0), "1. talk · QUEST_TALK")
	# one key of one stage
	tab.call("edit_stage", 1, "complete_when", "flag:chest.opened")
	t.eq(quest.stages[1]["complete_when"], "flag:chest.opened")
	t.ok(tab.get("dirty"))
	t.ok(undo.undo(), "the change is in the undo history")
	t.eq(quest.stages[1]["complete_when"], "item:key")
	t.ok(undo.redo())
	t.eq(quest.stages[1]["complete_when"], "flag:chest.opened")
	# an optional key comes and goes; the same value again is no step
	var version := undo.get_version()
	tab.call("edit_stage", 0, "target", "town_npc_001")
	t.eq(undo.get_version(), version, "nothing changed")
	tab.call("edit_stage", 0, "title", "QUEST_TALK_TITLE")
	tab.call("edit_stage", 0, "target", "")
	t.ok(not quest.stages[0].has("target") and quest.stages[0]["title"] == "QUEST_TALK_TITLE")
	tab.call("edit_stage", 0, "rewards", QuestTab.parse_rewards("gold 3\npotion x2"))
	t.eq(quest.stages[0]["rewards"], {"gold": 3, "items": [{"item_id": "potion", "qty": 2}]})
	# the quest's own fields
	tab.call("set_quest_property", "title", "QUEST_NEW_TITLE")
	tab.call("set_quest_property", "rewards", QuestTab.parse_rewards("experience 9"))
	t.eq(quest.rewards, {"experience": 9})
	undo.undo()
	t.eq(quest.rewards, {"gold": 25, "experience": 5})
	undo.redo()
	# stages are added, moved and removed
	tab.call("add_stage")
	t.eq(quest.stages.size(), 4)
	t.eq(quest.stages[3]["id"], "stage_4")
	tab.call("move_stage", -1)
	t.eq(quest.stages[2]["id"], "stage_4")
	tab.call("remove_stage")
	t.eq(quest.stages.size(), 3)
	undo.undo()
	t.eq(quest.stages.size(), 4, "removing is undone")
	undo.redo()
	# save and load again
	t.ok(tab.call("save"))
	var again := ResourceLoader.load(folder + "/errand.tres", "", ResourceLoader.CACHE_MODE_IGNORE) as RpgQuestDefinition
	t.eq(again.stages[1]["complete_when"], "flag:chest.opened")
	t.eq(again.title, "QUEST_NEW_TITLE")
	t.eq(again.rewards, {"experience": 9})
	tab.free()
	undo.free()
	_remove(folder)

func test_the_graph_has_a_node_per_stage_and_an_edge_per_next(t) -> void:
	var folder := _folder("quest_graph")
	var tab := _quest_tab(folder)
	t.eq(tab.call("graph_nodes"), ["talk", "chest", "return"])
	t.eq(tab.call("graph_edges"), [["chest", "return"], ["return", "done"], ["talk", "chest"]])
	# `next` moves an edge: talk now leads straight to return, chest finishes the quest
	tab.call("edit_stage", 0, "next", "return")
	tab.call("edit_stage", 1, "next", "done")
	t.eq(tab.call("graph_edges"), [["chest", "done"], ["return", "done"], ["talk", "return"]])
	# a `next` that names no stage has no edge, and the stage is marked
	tab.call("edit_stage", 0, "next", "nowhere")
	t.eq(tab.call("graph_edges"), [["chest", "done"], ["return", "done"]])
	t.ok(str(tab.call("stage_label", 0)).begins_with("⚠"))
	var found: Array[String] = tab.call("problems")
	t.ok(found.has("stage 1 (talk) leads to the unknown stage 'nowhere'"), str(found))
	tab.free()
	_remove(folder)

func test_the_quest_test_shows_the_stage_it_reaches(t) -> void:
	var folder := _folder("quest_test")
	var tab := _quest_tab(folder)
	t.eq(tab.call("test_atoms"), ["flag:npc.talked", "item:key"])
	t.eq(tab.call("run_test"), "talk", "nothing holds yet")
	tab.call("set_test_atom", "flag:npc.talked", true)
	t.eq(tab.call("run_test"), "chest")
	tab.call("set_test_atom", "item:key", true)
	t.eq(tab.call("run_test"), "return")
	var state: RpgGameState = tab.get("test_state")
	state.gold = 10
	t.eq(tab.call("run_test"), "done")
	tab.call("set_test_atom", "item:key", false)
	t.eq(tab.call("run_test"), "chest", "the quest stops where its condition fails")
	tab.free()
	_remove(folder)

func test_a_quest_target_is_checked_against_the_open_map(t) -> void:
	var folder := _folder("quest_target")
	var tab := _quest_tab(folder)
	t.eq(tab.call("problems"), [], "no map is open: targets are not checked")
	var root := Maps.map("town")
	Maps.entity(Maps.entities_of(root), "Npc", "town_npc_002")
	tab.set("map_root", root)
	t.eq(tab.call("map_entities"), ["town_npc_002"])
	var found: Array[String] = tab.call("problems")
	t.eq(found, ["stage 1 (talk) points at the unknown entity 'town_npc_001'"])
	tab.call("edit_stage", 0, "target", "town_npc_002")
	t.eq(tab.call("problems"), [])
	tab.free()
	root.free()
	_remove(folder)

func test_quest_json_round_trips_and_new_makes_a_file(t) -> void:
	var folder := _folder("quest_json")
	var tab := _quest_tab(folder)
	var json_path: String = tab.call("export_json")
	t.eq(json_path, folder + "/errand.json")
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(json_path))
	t.eq(data["id"], "errand")
	t.eq(data["stages"].size(), 3)
	DirAccess.rename_absolute(json_path, folder + "/copy.json")
	var made: String = tab.call("import_json", folder + "/copy.json")
	t.eq(made, folder + "/copy.tres")
	var copy: RpgQuestDefinition = tab.get("quest")
	t.eq(copy.to_dict()["stages"][0]["target"], "town_npc_001")
	t.eq(copy.rewards["gold"], 25.0)
	var bad := FileAccess.open(folder + "/bad.json", FileAccess.WRITE)
	bad.store_string("[1, 2]")
	bad.close()
	t.eq(tab.call("import_json", folder + "/bad.json"), "")
	var fresh: String = tab.call("new_quest")
	t.eq(fresh, folder + "/new_quest.tres")
	t.eq(tab.call("new_quest"), folder + "/new_quest_2.tres")
	t.eq((tab.get("quest") as RpgQuestDefinition).problems(), [])
	tab.free()
	_remove(folder)

func test_reward_text(t) -> void:
	var rewards := {"gold": 25, "experience": 5, "items": [{"item_id": "potion", "qty": 2}, {"item_id": "old key", "qty": 1}]}
	t.eq(QuestTab.rewards_text(rewards), "gold 25\nexperience 5\npotion x2\nold key x1")
	t.eq(QuestTab.parse_rewards(QuestTab.rewards_text(rewards)), rewards)
	t.eq(QuestTab.parse_rewards("\n  \n"), {})
	t.eq(QuestTab.parse_rewards("gold"), {"items": [{"item_id": "gold", "qty": 1}]}, "a bare word is an item")

# ---------------------------------------------------------------- the Cutscenes tab (T13.19)

static func _sequence() -> RpgSequence:
	return SequenceTab.from_json(JSON.stringify({"id": "arrival", "skippable": true, "commands": [
		{"cmd": "move_actor", "entity": "town_npc_001", "tiles": [2, 0]},
		{"cmd": "face", "entity": "player", "toward": "town_npc_001"},
		{"cmd": "show_dialogue", "lines": ["HELLO"], "speaker": "Ana"},
		{"cmd": "set_flag", "entity": "story", "key": "arrived"},
		{"cmd": "label", "name": "end"},
	]}))

func _sequence_tab(folder: String, undo: UndoRedo = null) -> VBoxContainer:
	t_save(_sequence(), folder + "/arrival.tres")
	var tab: VBoxContainer = SequenceTab.new()
	tab.set("sequences_dir", folder)
	tab.set("undo_redo", undo)
	tab.call("rescan")
	return tab

func test_the_step_kinds_cover_the_forms_of_the_tab(t) -> void:
	var kinds: Array[String] = []
	for entry in RpgSequence.STEP_KINDS:
		kinds.append(str(entry["kind"]))
		t.ok(RpgSequence.REQUIRED.has(entry["cmd"]), "%s is a command" % entry["cmd"])
		var step := RpgSequence.new_step(str(entry["kind"]))
		t.eq(RpgSequence.problems_of([step]), [], "a new '%s' step is complete" % entry["kind"])
	t.eq(kinds, ["move", "face", "say", "wait", "camera", "flag", "give", "play sound", "fade out", "fade in"])
	t.eq(RpgSequence.step_kind("move_actor")["kind"], "move")
	t.eq(RpgSequence.step_kind("goto"), {}, "every other command is edited as JSON")
	t.eq(RpgSequence.new_step("dance"), {})

func test_a_step_with_an_unknown_entity_is_marked(t) -> void:
	var folder := _folder("sequence_entities")
	var tab := _sequence_tab(folder)
	t.eq(tab.call("problems"), [], "no map is open: the actors are not checked")
	var root := Maps.map("town")
	Maps.entity(Maps.entities_of(root), "Npc", "town_npc_002")
	tab.set("map_root", root)
	var found: Array[String] = tab.call("problems")
	t.eq(found, [
		"command 1 (move_actor) names the unknown entity 'town_npc_001'",
		"command 2 (face) names the unknown entity 'town_npc_001'",
	], "the player is always known, and a flag's owner is not an actor")
	t.ok(str(tab.call("step_label", 0)).begins_with("⚠ 1. move"))
	t.ok(str(tab.call("step_label", 1)).begins_with("⚠ 2. face"))
	t.eq(tab.call("step_label", 2), "3. say")
	t.eq(tab.call("step_problems", 2), [])
	t.eq(tab.call("run_test"), "problems")
	tab.call("set_step_text", 0, "entity", "entity", "town_npc_002")
	tab.call("set_step_text", 1, "toward", "entity", "town_npc_002")
	t.eq(tab.call("problems"), [])
	t.eq(tab.call("step_label", 0), "1. move · town_npc_002")
	tab.free()
	root.free()
	_remove(folder)

func test_step_edits_are_undo_steps_and_the_form_writes_typed_values(t) -> void:
	var folder := _folder("sequence_edit")
	var undo := UndoRedo.new()
	var tab := _sequence_tab(folder, undo)
	var sequence: RpgSequence = tab.get("sequence")
	t.eq(sequence.commands[0]["tiles"], [2, 0], "whole numbers of JSON are integers again")
	tab.call("set_step_text", 0, "tiles", "pair", "3, -1")
	t.eq(sequence.commands[0]["tiles"], [3, -1])
	tab.call("set_step_text", 0, "speed", "float", "2.5")
	t.eq(sequence.commands[0]["speed"], 2.5)
	tab.call("set_step_value", 0, "wait", false)
	t.eq(sequence.commands[0]["wait"], false)
	undo.undo()
	t.ok(not sequence.commands[0].has("wait"))
	undo.undo()
	t.ok(not sequence.commands[0].has("speed"))
	undo.redo()
	tab.call("set_step_text", 0, "speed", "float", "")
	t.ok(not sequence.commands[0].has("speed"), "an empty field takes the argument away")
	var version := undo.get_version()
	tab.call("set_step_text", 0, "tiles", "pair", "3, -1")
	t.eq(undo.get_version(), version, "the same value is no step")
	# the kind, the JSON of a step, adding, moving, removing
	tab.call("set_step_kind", 3, "wait")
	t.eq(sequence.commands[3], {"cmd": "wait", "seconds": 1.0})
	t.ok(tab.call("set_step_json", 3, "{\"cmd\": \"goto\", \"label\": \"end\"}"))
	t.eq(sequence.commands[3], {"cmd": "goto", "label": "end"})
	t.ok(not tab.call("set_step_json", 3, "not json"))
	t.eq(sequence.commands[3]["cmd"], "goto")
	tab.call("select_step", 3)
	tab.call("add_step", "play sound")
	t.eq(sequence.commands.size(), 6)
	t.eq(sequence.commands[4]["cmd"], "play_sound", "after the selected step")
	tab.call("move_step", 1)
	t.eq(sequence.commands[5]["cmd"], "play_sound")
	tab.call("remove_step")
	t.eq(sequence.commands.size(), 5)
	tab.call("set_skippable", false)
	t.ok(not sequence.skippable)
	undo.undo()
	t.ok(sequence.skippable)
	t.ok(tab.call("save"))
	var again := ResourceLoader.load(folder + "/arrival.tres", "", ResourceLoader.CACHE_MODE_IGNORE) as RpgSequence
	t.eq(again.commands[0]["tiles"], [3, -1])
	t.eq(again.commands[3], {"cmd": "goto", "label": "end"})
	tab.free()
	undo.free()
	_remove(folder)

func test_fields_as_text(t) -> void:
	t.eq(SequenceTab.parse_field("pair", " 2 , -3 "), [2, -3])
	t.eq(SequenceTab.parse_field("pair", "2"), null)
	t.eq(SequenceTab.parse_field("float", "0.5"), 0.5)
	t.eq(SequenceTab.parse_field("int", "x"), null)
	t.eq(SequenceTab.parse_field("lines", "A\n\n B "), ["A", "B"])
	t.eq(SequenceTab.parse_field("value", "true"), true)
	t.eq(SequenceTab.parse_field("value", "3"), 3)
	t.eq(SequenceTab.parse_field("value", "red"), "red")
	t.eq(SequenceTab.parse_field("text", "  "), null)
	t.eq(SequenceTab.field_text("pair", [2, -3]), "2, -3")
	t.eq(SequenceTab.field_text("lines", ["A", "B"]), "A\nB")
	t.eq(SequenceTab.field_text("value", true), "true")
	t.eq(SequenceTab.field_text("float", null), "")

class FakeLink extends RefCounted:
	var sent: Array = []
	var running := true
	func send(message: String, data: Array) -> bool:
		if running:
			sent.append([message, data])
		return running

func test_the_cutscene_test_plays_in_a_running_game_or_only_checks(t) -> void:
	var folder := _folder("sequence_test")
	var tab := _sequence_tab(folder)
	t.eq(tab.call("run_test"), "checked", "no game runs: the sequence is only checked")
	t.ok(str(tab.call("status_text")).begins_with("No problems"))
	var link := FakeLink.new()
	tab.set("debug_link", link)
	t.eq(tab.call("run_test"), "played")
	t.eq(link.sent.size(), 1)
	t.eq(link.sent[0][0], "rpg_sequence:run")
	var commands: Array = link.sent[0][1][0]
	t.eq(commands.size(), 5)
	t.eq(commands[0]["cmd"], "move_actor")
	link.running = false
	t.eq(tab.call("run_test"), "checked")
	# a sequence with a problem is never sent
	link.running = true
	tab.call("set_step_json", 4, "{\"cmd\": \"goto\", \"label\": \"nowhere\"}")
	t.eq(tab.call("run_test"), "problems")
	t.eq(link.sent.size(), 1)
	# what the game does with the message: a sequence that is not a file
	var made := RpgSequenceRunner.sequence_from(commands, true)
	t.eq(made.commands.size(), 5)
	t.ok(made.skippable)
	t.eq(String(made.id), "editor_test")
	tab.free()
	_remove(folder)

func test_sequence_json_round_trips(t) -> void:
	var folder := _folder("sequence_json")
	var tab := _sequence_tab(folder)
	var json_path: String = tab.call("export_json")
	t.eq(json_path, folder + "/arrival.json")
	var back := SequenceTab.from_json(FileAccess.get_file_as_string(json_path))
	t.eq(SequenceTab.to_dict(back), SequenceTab.to_dict(_sequence()))
	DirAccess.rename_absolute(json_path, folder + "/copy.json")
	t.eq(tab.call("import_json", folder + "/copy.json"), folder + "/copy.tres")
	t.eq((tab.get("sequence") as RpgSequence).commands.size(), 5)
	# a bare list of commands is a sequence too; its id is the file's name
	var bare := FileAccess.open(folder + "/short.json", FileAccess.WRITE)
	bare.store_string("[{\"cmd\": \"wait\", \"seconds\": 1}]")
	bare.close()
	t.eq(tab.call("import_json", folder + "/short.json"), folder + "/short.tres")
	t.eq(String((tab.get("sequence") as RpgSequence).id), "short")
	t.eq(SequenceTab.from_json("{\"id\": \"x\"}"), null)
	t.eq(tab.call("new_sequence"), folder + "/new_cutscene.tres")
	t.eq(tab.call("problems"), [])
	tab.free()
	_remove(folder)

func test_the_dock_has_the_two_new_tabs(t) -> void:
	var source := FileAccess.get_file_as_string("res://addons/rpg_project_tools/dock/asset_dock.gd")
	t.ok(source.contains("QuestTab.new()") and source.contains("SequenceTab.new()"))
	var quests: VBoxContainer = QuestTab.new()
	var cutscenes: VBoxContainer = SequenceTab.new()
	t.eq(String(quests.name), "Quests")
	t.eq(String(cutscenes.name), "Cutscenes")
	quests.free()
	cutscenes.free()
