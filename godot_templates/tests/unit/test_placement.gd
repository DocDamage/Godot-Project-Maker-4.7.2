extends RefCounted

const Placement := preload("res://addons/rpg_project_tools/dock/placement.gd")
const Maps := preload("res://tests/lib/map_fixtures.gd")

func test_snap_position(t) -> void:
	t.eq(Placement.snap_position(Vector2(21, 13), 16), Vector2(16, 16))
	t.eq(Placement.snap_position(Vector2(24, 8), 16), Vector2(32, 16), "halves round up")
	t.eq(Placement.snap_position(Vector2(21, 13), 0), Vector2(21, 13), "snapping off")
	t.eq(Placement.snap_position(Vector2(-7, -9), 8), Vector2(-8, -8))

func test_ysort_parent_is_the_entities_node(t) -> void:
	var root := Maps.map("m")
	t.eq(Placement.ysort_parent(root), Maps.entities_of(root))
	var bare := Node2D.new()
	t.ok(Placement.ysort_parent(bare) == null)
	bare.free()
	root.free()

func test_a_dropped_instance_goes_under_entities_and_snaps(t) -> void:
	var root := Maps.map("m")
	var dropped := Node2D.new()
	dropped.name = "House"
	root.add_child(dropped)  # the editor adds a drop under the edited scene root
	dropped.position = Vector2(21, 13)
	var placement := Placement.new()
	placement.snap = 16
	var plan := placement.plan(dropped, root, {"name": "House", "role": "BUILDING", "tags": []})
	t.eq(plan["parent"], Maps.entities_of(root))
	t.eq(plan["old_parent"], root)
	t.eq(plan["position"], Vector2(16, 16))
	t.eq(plan["old_position"], Vector2(21, 13))
	t.eq(plan["entity_id"], "", "a node without an entity_id property gets none")
	root.free()

func test_snap_uses_global_space_and_the_new_parents_offset(t) -> void:
	var root := Maps.map("m")
	Maps.entities_of(root).position = Vector2(100, 0)
	var dropped := Node2D.new()
	root.add_child(dropped)
	dropped.position = Vector2(121, 13)
	var placement := Placement.new()
	placement.snap = 16
	var plan := placement.plan(dropped, root, {"name": "x", "role": "", "tags": []})
	# global (121, 13) snaps to (128, 16), which is (28, 16) inside the offset parent
	t.eq(plan["position"], Vector2(28, 16))
	root.free()

func test_a_persistent_entity_gets_the_next_id_of_its_kind(t) -> void:
	var root := Maps.map("starter_map")
	var ents := Maps.entities_of(root)
	Maps.entity(ents, "Npc1", "starter_map_npc_001")
	Maps.entity(ents, "Npc2", "starter_map_npc_003")
	var dropped := Maps.entity(ents, "Npc3", "")
	var placement := Placement.new()
	var plan := placement.plan(dropped, root, {"name": "Villager", "role": "NPC", "tags": []})
	t.eq(plan["entity_id"], "starter_map_npc_004")
	t.eq(plan["kind"], "npc")
	t.eq(plan["number"], 4)
	placement.auto_id = false
	t.eq(placement.plan(dropped, root, {"name": "Villager", "role": "NPC", "tags": []})["entity_id"], "", "auto id off")
	root.free()

func test_a_chest_by_tag_uses_the_chest_kind(t) -> void:
	var root := Maps.map("m")
	var dropped := Maps.entity(Maps.entities_of(root), "Chest", "")
	var plan := Placement.new().plan(dropped, root, {"name": "Chest", "role": "DECORATION", "tags": ["chest"]})
	t.eq(plan["entity_id"], "m_chest_001")
	root.free()

func test_a_prop_without_persistence_gets_no_id(t) -> void:
	var root := Maps.map("m")
	var dropped := Maps.entity(Maps.entities_of(root), "Tree", "", false)
	var plan := Placement.new().plan(dropped, root, {"name": "Tree", "role": "DECORATION", "tags": []})
	t.eq(plan["entity_id"], "")
	root.free()

func test_flip_applies_to_the_first_sprite(t) -> void:
	var root := Maps.map("m")
	var dropped := Node2D.new()
	root.add_child(dropped)
	var sprite := Sprite2D.new()
	sprite.name = "Sprite"
	dropped.add_child(sprite)
	var placement := Placement.new()
	placement.flip_h = true
	var plan := placement.plan(dropped, root, {"name": "x", "role": "", "tags": []})
	t.eq(plan["flip_node"], sprite)
	t.eq(plan["flip"], true)
	t.eq(plan["old_flip"], false)
	placement.flip_h = false
	t.ok(placement.plan(dropped, root, {"name": "x", "role": "", "tags": []})["flip_node"] == null)
	root.free()

func test_selected_mode_prefers_a_selected_y_sorted_node(t) -> void:
	var root := Maps.map("m")
	var other := Node2D.new()
	other.name = "Other"
	other.y_sort_enabled = true
	root.add_child(other)
	var plain := Node2D.new()
	plain.name = "Plain"
	root.add_child(plain)
	var placement := Placement.new()
	placement.ysort_mode = "selected"
	t.eq(placement.target_parent(root, root, other), other)
	t.eq(placement.target_parent(root, root, plain), Maps.entities_of(root), "a selected node that does not sort falls back to auto")
	t.eq(placement.target_parent(root, root, null), Maps.entities_of(root))
	placement.ysort_mode = "auto"
	t.eq(placement.target_parent(root, root, other), Maps.entities_of(root))
	root.free()

func test_a_detached_instance_is_planned_at_the_world_position(t) -> void:
	var root := Maps.map("m")
	var inst := Node2D.new()
	var placement := Placement.new()
	placement.snap = 8
	var plan := placement.plan(inst, root, {"name": "x", "role": "", "tags": []}, null, Vector2(37, 52))
	t.eq(plan["parent"], Maps.entities_of(root))
	t.ok(plan["old_parent"] == null)
	t.eq(plan["position"], Vector2(40, 56), "52 / 8 = 6.5 rounds up")
	inst.free()
	root.free()
