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
