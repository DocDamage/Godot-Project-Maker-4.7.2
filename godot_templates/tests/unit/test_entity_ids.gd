extends RefCounted

const EntityIds := preload("res://addons/rpg_project_tools/tools/entity_ids.gd")
const Maps := preload("res://tests/lib/map_fixtures.gd")

func test_make_id_pads_to_three_digits(t) -> void:
	t.eq(EntityIds.make_id("starter_map", "npc", 2), "starter_map_npc_002")
	t.eq(EntityIds.make_id("m", "chest", 123), "m_chest_123")
	t.eq(EntityIds.make_id("m", "chest", 1234), "m_chest_1234")

func test_number_of(t) -> void:
	t.eq(EntityIds.number_of("starter_map_npc_007", "starter_map", "npc"), 7)
	t.eq(EntityIds.number_of("starter_map_npc_007", "starter_map", "enemy"), -1)
	t.eq(EntityIds.number_of("other_npc_007", "starter_map", "npc"), -1)
	t.eq(EntityIds.number_of("starter_map_npc_x", "starter_map", "npc"), -1)
	t.eq(EntityIds.number_of("starter_map_npc_-3", "starter_map", "npc"), -1)

func test_next_number_is_one_more_than_the_highest_in_the_map(t) -> void:
	var ids := ["starter_map_npc_001", "starter_map_npc_004", "starter_map_chest_009", "other_npc_050"]
	t.eq(EntityIds.next_number(ids, "starter_map", "npc"), 5, "a gap is not refilled, a stale allocation cannot matter")
	t.eq(EntityIds.next_number(ids, "starter_map", "chest"), 10)
	t.eq(EntityIds.next_number(ids, "starter_map", "enemy"), 1)
	t.eq(EntityIds.next_number([], "starter_map", "npc"), 1)

func test_kind_comes_from_tags_then_role(t) -> void:
	t.eq(EntityIds.kind_of("DECORATION", ["chest"]), "chest")
	t.eq(EntityIds.kind_of("ITEM", ["sign", "x"]), "sign")
	t.eq(EntityIds.kind_of("NPC", []), "npc")
	t.eq(EntityIds.kind_of("ENEMY", []), "enemy")
	t.eq(EntityIds.kind_of("", []), "object")

func test_map_id_of(t) -> void:
	var root := Maps.map("starter_map")
	t.eq(EntityIds.map_id_of(root), "starter_map")
	root.set("map_id", &"")
	root.name = "StarterMap"
	t.eq(EntityIds.map_id_of(root), "starter_map", "falls back to the snake-cased name")
	root.free()

func test_persistence_decides_whether_an_empty_id_matters(t) -> void:
	var root := Maps.map("m")
	var chest := Maps.entity(Maps.entities_of(root), "Chest", "", true)
	var prop := Maps.entity(Maps.entities_of(root), "Prop", "", false)
	t.ok(EntityIds.has_entity_id(chest))
	t.ok(EntityIds.is_persistent(chest))
	t.ok(EntityIds.has_entity_id(prop))
	t.ok(not EntityIds.is_persistent(prop))
	var plain := Node2D.new()
	t.ok(not EntityIds.has_entity_id(plain))
	plain.free()
	t.eq(EntityIds.entity_nodes(root).size(), 2, "chest and prop; the map root has no entity_id")
	root.free()

func test_plan_fixes_assigns_empty_ids_and_renames_later_duplicates(t) -> void:
	var root := Maps.map("starter_map")
	var ents := Maps.entities_of(root)
	Maps.entity(ents, "A", "starter_map_npc_001")
	Maps.entity(ents, "B", "starter_map_npc_001")  # duplicate of A: renamed
	Maps.entity(ents, "C", "")  # persistent, empty: gets an id
	Maps.entity(ents, "Prop", "", false)  # not persistent: left alone
	var fixes := EntityIds.plan_fixes(root)
	var changes: Array = fixes["changes"]
	t.eq(changes.size(), 2)
	t.eq(changes[0]["node"].name, &"B")
	t.eq(changes[0]["old"], "starter_map_npc_001")
	t.eq(changes[1]["node"].name, &"C")
	t.ok(changes[0]["new"] != changes[1]["new"])
	for c in changes:
		t.ok(String(c["new"]).begins_with("starter_map_"), "id has the map prefix: %s" % c["new"])
	t.ok(fixes["allocations"].size() > 0)
	root.free()

func test_plan_fixes_counts_ids_of_other_maps_as_taken(t) -> void:
	var root := Maps.map("m")
	Maps.entity(Maps.entities_of(root), "A", "m_npc_001")
	var fixes := EntityIds.plan_fixes(root, {"m_npc_001": true})
	t.eq(fixes["changes"].size(), 1, "the same id in another map is a duplicate")
	t.ok(fixes["changes"][0]["new"] != "m_npc_001")
	root.free()

func test_plan_fixes_leaves_a_clean_scene_alone(t) -> void:
	var root := Maps.map("m")
	Maps.entity(Maps.entities_of(root), "A", "m_npc_001")
	Maps.entity(Maps.entities_of(root), "B", "m_chest_001")
	t.eq(EntityIds.plan_fixes(root)["changes"].size(), 0)
	root.free()
