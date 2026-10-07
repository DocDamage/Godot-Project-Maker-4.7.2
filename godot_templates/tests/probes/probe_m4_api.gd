extends SceneTree
# Probes the M4 API assumptions (T4.01 UID, T4.02 scene_changed, T4.04 instance overrides,
# T4.05 TileMapLayer.collision_enabled, T4.06 TileSet patterns).

func _initialize() -> void:
	print("scene_changed signal: ", ClassDB.class_has_signal("SceneTree", "scene_changed"))
	print("tree_changed signal: ", ClassDB.class_has_signal("SceneTree", "tree_changed"))
	var props := ClassDB.class_get_property_list("TileMapLayer")
	var names := []
	for p in props:
		names.append(p["name"])
	print("TileMapLayer.collision_enabled: ", names.has("collision_enabled"))
	print("TileMapLayer.y_sort_enabled via CanvasItem: ", ClassDB.class_has_method("CanvasItem", "set_y_sort_enabled"))

	# UID preservation across two saves
	DirAccess.make_dir_recursive_absolute("user://m4")
	var path := "user://m4/uid_test.tscn"
	var root := Node2D.new()
	root.name = "R"
	var packed := PackedScene.new()
	packed.pack(root)
	print("save1: ", ResourceSaver.save(packed, path))
	var uid1 := ResourceLoader.get_resource_uid(path)
	print("uid after first save: ", uid1, " valid=", uid1 != ResourceUID.INVALID_ID)
	var root2 := Node2D.new()
	root2.name = "R"
	root2.position = Vector2(1, 2)
	var packed2 := PackedScene.new()
	packed2.pack(root2)
	print("save2: ", ResourceSaver.save(packed2, path))
	var uid2 := ResourceLoader.get_resource_uid(path)
	print("uid after second save (no set_uid): ", uid2, " same=", uid1 == uid2)
	if uid1 != ResourceUID.INVALID_ID:
		print("set_uid: ", ResourceSaver.set_uid(path, uid1))
		print("uid after set_uid: ", ResourceLoader.get_resource_uid(path), " same=", ResourceLoader.get_resource_uid(path) == uid1)
	print("file head: ", FileAccess.get_file_as_string(path).substr(0, 60).replace("\n", "|"))

	# instance overrides on a child inside an instanced scene
	var inner := Node2D.new()
	inner.name = "Inner"
	var area := Area2D.new()
	area.name = "Entrance"
	inner.add_child(area)
	area.owner = inner
	var inner_packed := PackedScene.new()
	inner_packed.pack(inner)
	ResourceSaver.save(inner_packed, "user://m4/inner.tscn")
	var outer := Node2D.new()
	outer.name = "Outer"
	var inst := (load("user://m4/inner.tscn") as PackedScene).instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
	outer.add_child(inst)
	inst.owner = outer
	outer.set_editable_instance(inst, true)
	inst.get_node("Entrance").position = Vector2(7, 8)
	inst.get_node("Entrance").set_meta("target", "x")
	var outer_packed := PackedScene.new()
	print("pack outer: ", outer_packed.pack(outer))
	ResourceSaver.save(outer_packed, "user://m4/outer.tscn")
	var text := FileAccess.get_file_as_string("user://m4/outer.tscn")
	print("outer.tscn:\n", text)
	var re := (load("user://m4/outer.tscn") as PackedScene).instantiate()
	print("reloaded entrance position: ", re.get_node("Inner/Entrance").position)

	# tile set patterns
	var ts := TileSet.new()
	var pat := TileMapPattern.new()
	pat.set_cell(Vector2i(0, 0), 0, Vector2i(1, 1), 0)
	print("add_pattern index: ", ts.add_pattern(pat))
	print("patterns count: ", ts.get_patterns_count())
	ts.remove_pattern(0)
	print("after remove: ", ts.get_patterns_count())
	quit(0)
