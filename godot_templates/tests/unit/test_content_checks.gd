extends RefCounted

const ContentChecks := preload("res://addons/rpg_project_tools/tools/content_checks.gd")
const Maps := preload("res://tests/lib/map_fixtures.gd")
const SeedUtil := preload("res://builder/lib/seed_util.gd")

const DIR := "user://m8_content"
const DLG_RES := "res://addons/rpg_runtime/dialogue/dialogue_resource.gd"
const DLG_LINE := "res://addons/rpg_runtime/dialogue/dialogue_line.gd"
const ITEM_DEF := "res://addons/rpg_runtime/data/item_definition.gd"

func _dirs() -> Dictionary:
	return {"maps": DIR + "/maps", "dialogue": DIR + "/dialogue", "items": DIR + "/items", "shops": DIR + "/shops", "quests": DIR + "/quests", "actors": DIR + "/actors", "resources": [DIR + "/res"], "placeholders": DIR + "/res/placeholders/"}

func _codes(findings: Array) -> Array:
	var out: Array = []
	for f in findings:
		out.append(f["code"])
	return out

func _setup() -> void:
	Maps.remove_tree(DIR)
	DirAccess.make_dir_recursive_absolute(DIR + "/maps")

func _finish() -> void:
	Maps.remove_tree(DIR)

func test_a_clean_project_has_no_findings(t) -> void:
	_setup()
	var a := Maps.map("a")
	Maps.entity(Maps.entities_of(a), "Npc", "a_npc_001")
	Maps.spawn(a, "Spawn", "default")
	Maps.save(a, DIR + "/maps/a.tscn")
	t.eq(ContentChecks.run(_dirs()), [])
	_finish()

func test_duplicate_ids_across_maps_val_008(t) -> void:
	_setup()
	var a := Maps.map("a")
	Maps.entity(Maps.entities_of(a), "Npc", "shared_npc_001")
	Maps.save(a, DIR + "/maps/a.tscn")
	var b := Maps.map("b")
	Maps.entity(Maps.entities_of(b), "Npc", "shared_npc_001")
	Maps.save(b, DIR + "/maps/b.tscn")
	var findings := ContentChecks.run(_dirs())
	t.eq(_codes(findings), ["VAL-008"])
	t.eq(findings[0]["detail"]["id"], "shared_npc_001")
	t.ok(String(findings[0]["detail"]["files"]).contains("a.tscn") and String(findings[0]["detail"]["files"]).contains("b.tscn"))
	_finish()

func test_duplicate_ids_inside_one_map_val_008(t) -> void:
	_setup()
	var a := Maps.map("a")
	Maps.entity(Maps.entities_of(a), "One", "a_npc_001")
	Maps.entity(Maps.entities_of(a), "Two", "a_npc_001")
	Maps.save(a, DIR + "/maps/a.tscn")
	t.eq(_codes(ContentChecks.run(_dirs())), ["VAL-008"])
	_finish()

func test_an_empty_id_on_a_persistent_entity_val_009_but_not_on_a_prop(t) -> void:
	_setup()
	var a := Maps.map("a")
	Maps.entity(Maps.entities_of(a), "Chest", "", true)
	Maps.entity(Maps.entities_of(a), "Tree", "", false)
	Maps.save(a, DIR + "/maps/a.tscn")
	var findings := ContentChecks.run(_dirs())
	t.eq(_codes(findings), ["VAL-009"])
	t.ok(String(findings[0]["node"]).ends_with("Chest"))
	_finish()

func test_doors_to_a_missing_map_val_016(t) -> void:
	_setup()
	var a := Maps.map("a")
	Maps.door(a, "Door", DIR + "/maps/gone.tscn")
	Maps.save(a, DIR + "/maps/a.tscn")
	var findings := ContentChecks.run(_dirs())
	t.eq(_codes(findings), ["VAL-016"])
	t.eq(findings[0]["detail"]["target"], DIR + "/maps/gone.tscn")
	_finish()

func test_a_door_without_a_target_is_not_an_error(t) -> void:
	_setup()
	var a := Maps.map("a")
	Maps.door(a, "Door", "")
	Maps.save(a, DIR + "/maps/a.tscn")
	t.eq(ContentChecks.run(_dirs()), [])
	_finish()

func test_doors_to_an_unknown_spawn_val_017(t) -> void:
	_setup()
	var a := Maps.map("a")
	Maps.door(a, "Good", DIR + "/maps/b.tscn", "inside")
	Maps.door(a, "Bad", DIR + "/maps/b.tscn", "nowhere")
	Maps.save(a, DIR + "/maps/a.tscn")
	var b := Maps.map("b")
	var holder := Node2D.new()
	holder.name = "Holder"
	b.add_child(holder)
	Maps.spawn(holder, "Spawn", "inside")
	Maps.save(b, DIR + "/maps/b.tscn")
	var findings := ContentChecks.run(_dirs())
	t.eq(_codes(findings), ["VAL-017"])
	t.eq(findings[0]["detail"]["spawn"], "nowhere")
	t.ok(String(findings[0]["node"]).ends_with("Bad"))
	_finish()

func _dialogue(lines: Array) -> Resource:
	var res := SeedUtil.make(DLG_RES)
	var typed: Array = []
	for l in lines:
		var line := SeedUtil.make(DLG_LINE)
		line.set("text", "x")
		line.set("condition", l.get("condition", ""))
		line.set("events", PackedStringArray(l.get("events", [])))
		typed.append(line)
	res.get("lines").assign(typed)
	return res

func _item(item_id: String) -> Resource:
	var item := SeedUtil.make(ITEM_DEF)
	item.set("id", StringName(item_id))
	return item

func test_dialogue_mixing_and_or_val_018(t) -> void:
	_setup()
	SeedUtil.save(_dialogue([{}, {"condition": "flag:a.b and flag:c.d"}, {"condition": "flag:a.b and flag:c.d or flag:e.f"}]), DIR + "/dialogue/d.tres")
	var findings := ContentChecks.run(_dirs())
	t.eq(_codes(findings), ["VAL-018"])
	t.eq(findings[0]["detail"]["n"], 3, "line numbers count from 1")
	_finish()

func test_unknown_items_in_events_and_conditions_val_019(t) -> void:
	_setup()
	SeedUtil.save(_item("potion"), DIR + "/items/potion.tres")
	SeedUtil.save(_dialogue([
		{"events": ["give_item:potion:1", "give_item:elixir"], "condition": "item:potion>=1"},
		{"condition": "item:ghost_key", "events": ["take_item:elixir:2", "set_flag:a.b=true"]},
	]), DIR + "/dialogue/d.tres")
	var findings := ContentChecks.run(_dirs())
	var items: Array = []
	for f in findings:
		t.eq(f["code"], "VAL-019")
		items.append(f["detail"]["item"])
	items.sort()
	t.eq(items, ["elixir", "ghost_key"], "each unknown item once per dialogue")
	_finish()

func test_unknown_shop_quest_and_actor_ids_val_019(t) -> void:
	_setup()
	# a shop and an actor are found by their file name, a quest by its id
	SeedUtil.save(_item("anything"), DIR + "/shops/village_shop.tres")
	SeedUtil.save(_item("errand"), DIR + "/quests/first_quest.tres")
	SeedUtil.save(_item("anyone"), DIR + "/actors/companion.tres")
	t.eq(ContentChecks.known_ids(_dirs()), {"shop": ["village_shop"], "quest": ["errand"], "actor": ["companion"]})
	SeedUtil.save(_dialogue([
		{"events": ["open_shop:village_shop", "quest_start:errand", "quest_stage:errand:talk", "quest_complete:errand", "join_party:companion"]},
		{"events": ["open_shop:vilage_shop"]},
		{"events": ["quest_start:erand", "quest_stage:erand:talk", "quest_complete:lost"]},
		{"events": ["join_party:nobody", "leave_party:nobody", "open_shop:"]},
	]), DIR + "/dialogue/d.tres")
	var findings := ContentChecks.run(_dirs())
	var rows: Array = []
	for f in findings:
		t.eq(f["code"], "VAL-019")
		t.eq(f["file"], DIR + "/dialogue/d.tres")
		rows.append("%s %s line %d" % [f["detail"]["kind"], f["detail"]["item"], f["detail"]["n"]])
	rows.sort()
	t.eq(rows, ["actor nobody line 4", "quest erand line 3", "quest lost line 3", "shop vilage_shop line 2"], "each unknown id once, with its line")
	_finish()

func test_event_problem_with_the_ids_that_exist(t) -> void:
	var ids := {"shop": ["village_shop"], "quest": ["errand"], "actor": ["companion"]}
	for known: String in ["open_shop:village_shop", "quest_start:errand", "quest_stage:errand:talk", "quest_complete:errand", "join_party:companion", "give_gold:5", "leave_party:nobody"]:
		t.eq(RpgDialogueRunner.event_problem(known, ids), "", known)
	t.eq(RpgDialogueRunner.event_problem("open_shop:bazaar", ids), "unknown shop 'bazaar'")
	t.eq(RpgDialogueRunner.event_problem("quest_start:lost", ids), "unknown quest 'lost'")
	t.eq(RpgDialogueRunner.event_problem("quest_stage:lost:talk", ids), "unknown quest 'lost'")
	t.eq(RpgDialogueRunner.event_problem("quest_complete:lost", ids), "unknown quest 'lost'")
	t.eq(RpgDialogueRunner.event_problem("join_party:nobody", ids), "unknown actor 'nobody'")
	# without the ids (the game itself, an older caller) only the form is checked
	t.eq(RpgDialogueRunner.event_problem("open_shop:bazaar"), "")
	t.eq(RpgDialogueRunner.event_problem("open_shop:bazaar", {"quest": ["errand"]}), "", "a kind without a list is not checked")
	# a malformed event keeps its own message
	t.eq(RpgDialogueRunner.event_problem("quest_stage:lost", ids), "quest_stage needs <id>:<stage>")
	t.eq(RpgDialogueRunner.event_refs("give_item:potion:2"), [])
	t.eq(RpgDialogueRunner.event_refs("quest_stage:errand:talk"), [["quest", "errand"]])

func test_debug_placeholders_val_012(t) -> void:
	_setup()
	DirAccess.make_dir_recursive_absolute(DIR + "/res/placeholders")
	ResourceSaver.save(GradientTexture1D.new(), DIR + "/res/placeholders/p.tres")
	ResourceSaver.save(GradientTexture1D.new(), DIR + "/res/plain.tres")
	var holder := AtlasTexture.new()
	holder.atlas = ResourceLoader.load(DIR + "/res/placeholders/p.tres", "", ResourceLoader.CACHE_MODE_IGNORE) as Texture2D
	ResourceSaver.save(holder, DIR + "/res/uses.tres")
	var findings := ContentChecks.run(_dirs())
	t.eq(_codes(findings), ["VAL-012"])
	if not findings.is_empty():
		t.ok(String(findings[0]["file"]).ends_with("uses.tres"))
	_finish()

func test_findings_are_sorted_and_repeatable(t) -> void:
	_setup()
	for map_name in ["b", "a", "c"]:
		var m := Maps.map(map_name)
		Maps.entity(Maps.entities_of(m), "Chest", "", true)
		Maps.save(m, DIR + "/maps/%s.tscn" % map_name)
	var first := ContentChecks.run(_dirs())
	var second := ContentChecks.run(_dirs())
	t.eq(first, second)
	var files: Array = []
	for f in first:
		files.append(f["file"])
	var sorted := files.duplicate()
	sorted.sort()
	t.eq(files, sorted)
	_finish()

func test_event_and_condition_item_parsing(t) -> void:
	t.eq(ContentChecks.condition_items("item:potion>=2 and not flag:a.b"), ["potion"])
	t.eq(ContentChecks.condition_items("gold>=5"), [])
	t.eq(ContentChecks.event_items("give_item:potion:3"), ["potion"])
	t.eq(ContentChecks.event_items("take_item:potion"), ["potion"])
	t.eq(ContentChecks.event_items("give_gold:5"), [])

# ---------------------------------------------------------------- sequences and triggers (VAL-023)

func _sequence_dirs() -> Dictionary:
	var dirs := _dirs()
	dirs["sequences"] = DIR + "/sequences"
	dirs["enemies"] = DIR + "/enemies"
	return dirs

func test_sequence_problems_and_missing_references_val_023(t) -> void:
	_setup()
	DirAccess.make_dir_recursive_absolute(DIR + "/sequences")
	var good := RpgSequence.new()
	good.id = &"good"
	good.commands.assign([{"cmd": "wait", "seconds": 1}])
	ResourceSaver.save(good, DIR + "/sequences/good.tres")
	var bad := RpgSequence.new()
	bad.id = &"bad"
	bad.commands.assign([
		{"cmd": "fly"},
		{"cmd": "call", "sequence": "good"},
		{"cmd": "call", "sequence": "nope"},
		{"cmd": "show_dialogue", "dialogue": "missing_talk"},
		{"cmd": "start_battle", "enemies": ["ghost"]},
		{"cmd": "change_map", "map": "res://game/maps/nowhere.tscn"},
	])
	ResourceSaver.save(bad, DIR + "/sequences/bad.tres")
	var findings := ContentChecks.run(_sequence_dirs())
	t.eq(_codes(findings), ["VAL-023", "VAL-023", "VAL-023", "VAL-023", "VAL-023"], str(findings))
	var problems: Array = []
	for f in findings:
		t.eq(f["file"], DIR + "/sequences/bad.tres")
		problems.append(f["detail"]["problem"])
	var text := " | ".join(PackedStringArray(problems))
	for part in ["'fly'", "'nope'", "'missing_talk'", "'ghost'", "nowhere.tscn"]:
		t.ok(text.contains(part) or text.contains(part.trim_prefix("'").trim_suffix("'")), "%s in %s" % [part, text])
	_finish()

func test_triggers_need_a_sequence_and_an_id_when_once_val_023(t) -> void:
	_setup()
	DirAccess.make_dir_recursive_absolute(DIR + "/sequences")
	var intro := RpgSequence.new()
	intro.id = &"intro"
	ResourceSaver.save(intro, DIR + "/sequences/intro.tres")
	var a := Maps.map("a")
	for spec: Array in [["Fine", "intro", "a_trigger_001"], ["NoSequence", "", "a_trigger_002"], ["Missing", "outro", "a_trigger_003"], ["NoId", "intro", ""]]:
		var trigger := RpgTriggerArea.new()
		trigger.name = spec[0]
		trigger.sequence_id = StringName(spec[1])
		trigger.entity_id = spec[2]
		a.add_child(trigger)
	Maps.save(a, DIR + "/maps/a.tscn")
	var findings := ContentChecks.run(_sequence_dirs())
	var nodes: Array = []
	for f in findings:
		if f["code"] == "VAL-023":
			nodes.append(f["node"])
	nodes.sort()
	t.eq(nodes, ["Missing", "NoId", "NoSequence"])
	_finish()

# ---------------------------------------------------------------- encounter zones (VAL-024)

func test_zones_need_a_table_with_known_enemies_and_a_shape_val_024(t) -> void:
	_setup()
	DirAccess.make_dir_recursive_absolute(DIR + "/enemies")
	var bat := RpgEnemyDefinition.new()
	bat.id = &"bat"
	ResourceSaver.save(bat, DIR + "/enemies/bat.tres")
	var good_table := RpgEncounterTable.new()
	good_table.groups.assign([{"enemies": [DIR + "/enemies/bat.tres"], "weight": 1}])
	var bad_table := RpgEncounterTable.new()
	bad_table.groups.assign([{"enemies": ["ghost"], "weight": 1}])
	var a := Maps.map("a")
	for spec: Array in [["Fine", good_table, true], ["NoTable", null, true], ["Ghost", bad_table, true], ["NoShape", good_table, false]]:
		var zone := RpgEncounterZone.new()
		zone.name = spec[0]
		zone.table = spec[1]
		if spec[2]:
			var poly := CollisionPolygon2D.new()
			poly.name = "Shape"
			poly.polygon = PackedVector2Array([Vector2(0, 0), Vector2(32, 0), Vector2(32, 32)])
			zone.add_child(poly)
		a.add_child(zone)
	Maps.save(a, DIR + "/maps/a.tscn")
	var nodes: Array = []
	for f in ContentChecks.run(_dirs()):
		if f["code"] == "VAL-024":
			nodes.append(f["node"])
	nodes.sort()
	t.eq(nodes, ["Ghost", "NoShape", "NoTable"])
	_finish()

# ---------------------------------------------------------------- the world of maps (T13.20)

const MapGraph := preload("res://addons/rpg_project_tools/tools/map_graph.gd")
const WorldPlan := preload("res://builder/lib/world_plan.gd")

## Three maps: a <-> b joined by a door pair, c on its own. Returns the three paths.
func _three_maps() -> Array[String]:
	var a := Maps.map("a")
	Maps.door(a, "ToB", DIR + "/maps/b.tscn", "from_a")
	Maps.spawn(a, "FromB", "from_b")
	Maps.save(a, DIR + "/maps/a.tscn")
	var b := Maps.map("b")
	Maps.door(b, "ToA", DIR + "/maps/a.tscn", "from_b")
	Maps.spawn(b, "FromA", "from_a")
	Maps.save(b, DIR + "/maps/b.tscn")
	var c := Maps.map("c")
	Maps.save(c, DIR + "/maps/c.tscn")
	return [DIR + "/maps/a.tscn", DIR + "/maps/b.tscn", DIR + "/maps/c.tscn"]

func _world_dirs(plan_maps: Array = []) -> Dictionary:
	var dirs := _dirs()
	dirs["start"] = DIR + "/maps/a.tscn"
	dirs["world_plan"] = DIR + "/world_plan.json"
	if not plan_maps.is_empty():
		var areas: Array = []
		for path: String in plan_maps:
			areas.append({"map": path})
		var f := FileAccess.open(DIR + "/world_plan.json", FileAccess.WRITE)
		f.store_string(JSON.stringify({"areas": areas}))
		f.close()
	return dirs

func test_the_map_graph_reads_doors_and_spawns(t) -> void:
	_setup()
	var paths := _three_maps()
	var roots: Array[Node] = []
	var graph := MapGraph.read(paths, func(path: String) -> Node:
		var root := (load(path) as PackedScene).instantiate()
		roots.append(root)
		return root)
	t.eq(graph[paths[0]]["doors"], [{"node": "ToB", "target": paths[1], "spawn": "from_a"}])
	t.eq(graph[paths[0]]["spawns"], ["from_b"])
	t.eq(MapGraph.reachable(graph, paths[0]), [paths[0], paths[1]])
	t.eq(MapGraph.unreachable(graph, paths[0]), [paths[2]])
	t.eq(MapGraph.unreachable(graph, DIR + "/maps/none.tscn"), [], "without a start map nothing is said")
	t.ok(MapGraph.has_door(graph, paths[0], paths[1]) and not MapGraph.has_door(graph, paths[2], paths[0]))
	t.eq(MapGraph.dangling(graph, func(path: String) -> bool: return FileAccess.file_exists(path)), [])
	for root in roots:
		root.free()
	_finish()

func test_a_map_that_cannot_be_reached_is_val_027(t) -> void:
	_setup()
	_three_maps()
	var findings := ContentChecks.run(_world_dirs())
	t.eq(_codes(findings), ["VAL-027"])
	t.eq(findings[0]["detail"]["map"], "c")
	t.eq(findings[0]["file"], DIR + "/maps/c.tscn")
	# a door to it from a reachable map is enough (the way back is the player's business)
	var b := (load(DIR + "/maps/b.tscn") as PackedScene).instantiate()
	Maps.door(b, "ToC", DIR + "/maps/c.tscn", "default").owner = b
	Maps.save(b, DIR + "/maps/b.tscn")
	var c := Maps.map("c")
	Maps.spawn(c, "Default", "default")
	Maps.save(c, DIR + "/maps/c.tscn")
	t.eq(ContentChecks.run(_world_dirs()), [])
	_finish()

func test_the_library_of_imported_maps_is_not_an_island(t) -> void:
	_setup()
	_three_maps()
	DirAccess.make_dir_recursive_absolute(DIR + "/maps/imported/pack")
	DirAccess.rename_absolute(DIR + "/maps/c.tscn", DIR + "/maps/imported/pack/c.tscn")
	t.eq(ContentChecks.run(_world_dirs()), [])
	_finish()

func test_a_broken_door_of_the_world_is_the_warning_val_028(t) -> void:
	_setup()
	var a := Maps.map("a")
	Maps.door(a, "ToB", DIR + "/maps/b.tscn", "nowhere")
	Maps.door(a, "ToGone", DIR + "/maps/gone.tscn", "default")
	Maps.save(a, DIR + "/maps/a.tscn")
	var b := Maps.map("b")
	Maps.door(b, "ToA", DIR + "/maps/a.tscn", "from_b")
	Maps.save(b, DIR + "/maps/b.tscn")
	# without a world plan these are the errors they always were
	t.eq(_codes(ContentChecks.run(_world_dirs())), ["VAL-017", "VAL-016", "VAL-017"])
	# the plan names a and b: rpggen can mend its world, so the same doors only warn
	var findings := ContentChecks.run(_world_dirs([DIR + "/maps/a.tscn", DIR + "/maps/b.tscn"]))
	t.eq(_codes(findings), ["VAL-028", "VAL-028", "VAL-028"])
	t.eq(findings[0]["detail"]["what"], "the spawn point 'nowhere' in b.tscn")
	t.eq(findings[1]["detail"]["what"], "the map gone.tscn")
	t.eq(findings[2]["detail"]["what"], "the spawn point 'from_b' in a.tscn")
	t.eq(ContentChecks.world_maps(DIR + "/no_plan.json"), [])
	_finish()

func test_dangling_doors_are_listed_for_the_repair(t) -> void:
	_setup()
	var a := Maps.map("a")
	Maps.door(a, "ToB", DIR + "/maps/b.tscn", "nowhere")
	Maps.door(a, "ToGone", DIR + "/maps/gone.tscn", "default")
	Maps.save(a, DIR + "/maps/a.tscn")
	Maps.save(Maps.map("b"), DIR + "/maps/b.tscn")
	var roots: Array[Node] = []
	var paths: Array[String] = [DIR + "/maps/a.tscn", DIR + "/maps/b.tscn"]
	var graph := MapGraph.read(paths, func(path: String) -> Node:
		var root := (load(path) as PackedScene).instantiate()
		roots.append(root)
		return root)
	var found := MapGraph.dangling(graph, func(path: String) -> bool: return FileAccess.file_exists(path))
	t.eq(found.size(), 2)
	t.eq([found[0]["node"], found[0]["missing"]], ["ToB", "spawn"])
	t.eq([found[1]["node"], found[1]["missing"]], ["ToGone", "map"])
	for root in roots:
		root.free()
	_finish()

func test_a_village_door_moves_along_the_wall_to_free_floor(t) -> void:
	var size := Vector2i(40, 30)
	t.eq(WorldPlan.inside("N", Vector2i(20, 0)), Vector2i(20, 1))
	t.eq(WorldPlan.inside("E", Vector2i(39, 15)), Vector2i(38, 15))
	t.eq(WorldPlan.free_edge_cell(Vector2i(20, 0), "N", size, {}), Vector2i(20, 0), "free: where the plan wants it")
	var blocked := {Vector2i(20, 1): true, Vector2i(21, 2): true}
	t.eq(WorldPlan.free_edge_cell(Vector2i(20, 0), "N", size, blocked), Vector2i(19, 0), "the nearest cell with two free cells in front")
	var west := {Vector2i(1, 15): true, Vector2i(1, 16): true, Vector2i(1, 14): true}
	t.eq(WorldPlan.free_edge_cell(Vector2i(0, 15), "W", size, west), Vector2i(0, 17))
	t.eq(WorldPlan.cell([3, 4]), Vector2i(3, 4))
	t.eq(WorldPlan.cell("x"), Vector2i.ZERO)
	var plan := {"areas": [{"id": "starter_map", "map": "game/maps/starter_map.tscn", "doors": [{"id": "d1"}], "gates": [{"id": "g", "door": "d1"}]}]}
	t.eq(WorldPlan.areas(plan).size(), 1)
	t.eq(WorldPlan.map_path(WorldPlan.area(plan, "starter_map")), "res://game/maps/starter_map.tscn")
	t.eq(WorldPlan.gate_of(WorldPlan.area(plan, "starter_map"), "d1")["id"], "g")
	t.eq(WorldPlan.gate_of(WorldPlan.area(plan, "starter_map"), "d2"), {})
	t.eq(WorldPlan.area(plan, "nowhere"), {})
