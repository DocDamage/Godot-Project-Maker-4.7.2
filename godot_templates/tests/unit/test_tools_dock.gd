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
