extends RefCounted

const ContentChecks := preload("res://addons/rpg_project_tools/tools/content_checks.gd")
const Maps := preload("res://tests/lib/map_fixtures.gd")
const SeedUtil := preload("res://builder/lib/seed_util.gd")

const DIR := "user://m8_content"
const DLG_RES := "res://addons/rpg_runtime/dialogue/dialogue_resource.gd"
const DLG_LINE := "res://addons/rpg_runtime/dialogue/dialogue_line.gd"
const ITEM_DEF := "res://addons/rpg_runtime/data/item_definition.gd"

func _dirs() -> Dictionary:
	return {"maps": DIR + "/maps", "dialogue": DIR + "/dialogue", "items": DIR + "/items", "resources": [DIR + "/res"], "placeholders": DIR + "/res/placeholders/"}

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
