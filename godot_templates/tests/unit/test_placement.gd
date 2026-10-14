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

# ---------------------------------------------------------------- names and instances

func test_a_taken_name_gets_the_number_the_editor_would_give(t) -> void:
	var parent := Node2D.new()
	for child_name: String in ["treeoak", "rock", "rock2", "house3", "Npc1"]:
		var child := Node2D.new()
		child.name = child_name
		parent.add_child(child)
	t.eq(Placement.free_name(parent, "chest"), "chest", "a free name is kept")
	t.eq(Placement.free_name(parent, "treeoak"), "treeoak2")
	t.eq(Placement.free_name(parent, "rock"), "rock3", "rock2 is taken too")
	t.eq(Placement.free_name(parent, "house3"), "house4", "a number goes on counting")
	t.eq(Placement.free_name(parent, "Npc1"), "Npc2")
	t.eq(Placement.free_name(parent, "treeoak", parent.get_node("treeoak")), "treeoak", "the node itself is not in the way")
	parent.free()

func test_a_second_copy_dropped_into_the_entities_gets_a_readable_name(t) -> void:
	var root := Maps.map("m")
	var entities := Maps.entities_of(root)
	var first := Node2D.new()
	first.name = "treeoak"
	entities.add_child(first)
	var dropped := Node2D.new()
	dropped.name = "treeoak"
	root.add_child(dropped)  # the editor drops it under the root, where the name is free
	var placement := Placement.new()
	var plan := placement.plan(dropped, root, {"name": "treeoak", "role": "", "tags": []})
	t.eq(plan["name"], "treeoak2", "not @Node2D@<n>, which reparent would give")
	t.eq(plan["old_name"], "treeoak")
	var detached := Node2D.new()
	detached.name = "treeoak"
	t.eq(placement.plan(detached, root, {"name": "treeoak", "role": "", "tags": []}, null, Vector2(8, 8))["name"], "treeoak2", "a double click too")
	var inside := Node2D.new()
	inside.name = "treeoak3"
	entities.add_child(inside)  # dropped onto the entities: it does not move
	t.eq(placement.plan(inside, root, {"name": "treeoak", "role": "", "tags": []})["name"], "treeoak3", "its own name")
	detached.free()
	root.free()

## A library scene as the builder writes one: a root with a script-like set of properties of its
## own (a collision mask, metadata) that a map must not copy.
func _library_scene(path: String) -> PackedScene:
	var body := StaticBody2D.new()
	body.name = "treeoak"
	body.collision_mask = 5
	body.set_meta("stands_on", [1, 1])
	body.set_meta("kind", "tree")
	var sprite := Sprite2D.new()
	sprite.name = "Sprite"
	body.add_child(sprite)
	sprite.owner = body
	var packed := PackedScene.new()
	packed.pack(body)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	ResourceSaver.save(packed, path)
	body.free()
	return load(path) as PackedScene

## How a map packs `node` (its name is unique in the map): [its type ("" for an instance of a scene), whether it is an instance,
## the names of the properties it saves].
func _packed_as(root: Node, node: Node) -> Array:
	var packed := PackedScene.new()
	packed.pack(root)
	var state := packed.get_state()
	for i in state.get_node_count():
		if state.get_node_name(i) == node.name:
			var props: Array[String] = []
			for p in state.get_node_property_count(i):
				props.append(String(state.get_node_property_name(i, p)))
			return [String(state.get_node_type(i)), state.get_node_instance(i) != null, props]
	return []

func test_a_double_click_is_saved_as_an_instance_of_its_scene(t) -> void:
	var path := "user://placement_scene/treeoak.tscn"
	var packed := _library_scene(path)
	var root := Maps.map("m")
	for part in root.find_children("*", "", true, false):
		part.owner = root  # as in a saved map: what the root owns is packed
	var entities := Maps.entities_of(root)
	var node := Placement.instance_for_edit(packed) as Node2D
	t.ok(node != null and node.scene_file_path == path)
	entities.add_child(node, true)
	node.owner = root
	node.position = Vector2(24, 40)
	var seen := _packed_as(root, node)
	t.eq(seen[0], "", "no type=: an instance")
	t.ok(seen[1], "instance=ExtResource(...)")
	t.eq(seen[2], ["position"] as Array[String], "only what the map changed, no metadata/ and no mask")
	# what the double click did before: a copy of the scene's root
	var copy := packed.instantiate() as Node2D
	entities.add_child(copy, true)
	copy.owner = root
	t.eq(_packed_as(root, copy)[0], "StaticBody2D", "a plain instantiate() is saved with type=")
	root.free()
	Maps.remove_tree("user://placement_scene")

# ---------------------------------------------------------------- trigger areas (T12.54)

func test_a_trigger_plan_numbers_the_id_and_names_the_sequence_file(t) -> void:
	var root := Maps.map("town")
	var triggers := Node2D.new()
	triggers.name = "Triggers"
	root.add_child(triggers)
	var old := RpgTriggerArea.new()
	old.entity_id = "town_trigger_002"
	triggers.add_child(old)
	var plan := Placement.plan_trigger(root, Vector2(37, 21), 16, 16, true, "user://seq_test")
	t.eq(plan["parent"], triggers, "triggers go under the map's Triggers node")
	t.eq(plan["entity_id"], "town_trigger_003")
	t.eq(plan["sequence_path"], "user://seq_test/town_trigger_003.tres")
	t.eq(plan["position"], Vector2(32, 16), "snapped to the tile grid")
	var area := Placement.build_trigger(plan)
	t.ok(area is RpgTriggerArea)
	t.eq(area.get("sequence_id"), &"town_trigger_003")
	t.ok(area.get("on_interact"))
	t.eq(((area.get_node("Shape") as CollisionShape2D).shape as RectangleShape2D).size, Vector2(16, 16))
	t.eq(Placement.make_sequence_file("user://seq_test/town_trigger_003.tres", "town_trigger_003"), OK)
	var made := load("user://seq_test/town_trigger_003.tres") as RpgSequence
	t.ok(made != null and made.id == &"town_trigger_003" and made.problems().is_empty(), "an empty but valid sequence")
	DirAccess.remove_absolute("user://seq_test/town_trigger_003.tres")
	area.free()
	root.free()

# ---------------------------------------------------------------- encounter zones (T12.53)

func test_a_zone_plan_covers_the_selection_and_lists_the_enemies(t) -> void:
	var root := Maps.map("field")
	DirAccess.make_dir_recursive_absolute("user://zone_test/enemies")
	for id: String in ["slime", "bat"]:
		var def := RpgEnemyDefinition.new()
		def.id = StringName(id)
		ResourceSaver.save(def, "user://zone_test/enemies/%s.tres" % id)
	var a := Node2D.new()
	a.position = Vector2(100, 100)
	var b := Node2D.new()
	b.position = Vector2(110, 104)
	root.add_child(a)
	root.add_child(b)
	var plan := Placement.plan_zone(root, [a, b], Vector2.ZERO, 16, "user://zone_test/enemies", "user://zone_test/encounters")
	var poly: PackedVector2Array = plan["polygon"]
	t.eq(poly.size(), 4)
	t.eq(poly[0], Vector2(81, 78), "at least 3 tiles wide and high, centred on the selection")
	t.eq(poly[2], Vector2(129, 126))
	t.eq(plan["table_id"], "field_zone_1")
	t.eq(plan["enemies"], ["bat", "slime"] as Array[String], "every enemy, sorted")
	var table := Placement.make_table_file(plan)
	t.ok(table is RpgEncounterTable)
	t.eq((table as RpgEncounterTable).groups.size(), 2)
	var zone := Placement.build_zone(plan, table)
	t.ok(zone is RpgEncounterZone)
	t.ok((zone as RpgEncounterZone).contains(Vector2(105, 102)))
	zone.free()
	var nothing := Placement.plan_zone(root, [], Vector2(160, 160), 16, "user://zone_test/enemies", "user://zone_test/encounters")
	var square: PackedVector2Array = nothing["polygon"]
	t.eq(square[0], Vector2(112, 112), "6x6 tiles around the view centre")
	t.eq(nothing["table_id"], "field_zone_2", "the first table file exists, so the next number")
	var layer := TileMapLayer.new()
	layer.name = "Encounters"
	root.add_child(layer)
	var cells := Placement.plan_zone(root, [layer], Vector2.ZERO, 16, "user://zone_test/enemies", "user://zone_test/encounters")
	t.eq(cells["cells_layer"], NodePath("../Encounters"))
	t.eq((cells["polygon"] as PackedVector2Array).size(), 0)
	Maps.remove_tree("user://zone_test")
	root.free()
