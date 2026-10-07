extends SceneTree
func _initialize() -> void:
	var path := "user://m4/uid2.tscn"
	DirAccess.make_dir_recursive_absolute("user://m4")
	var root := Node2D.new()
	var packed := PackedScene.new()
	packed.pack(root)
	ResourceSaver.save(packed, path)
	var uid := ResourceUID.create_id()
	print("created: ", uid, " text=", ResourceUID.id_to_text(uid))
	print("set_uid: ", ResourceSaver.set_uid(path, uid))
	print("get after set_uid: ", ResourceLoader.get_resource_uid(path))
	print("head: ", FileAccess.get_file_as_string(path).substr(0, 80).replace("\n", "|"))
	# alternative: save with uid assigned through ResourceUID before saving
	var path2 := "user://m4/uid3.tscn"
	var uid2 := ResourceUID.create_id()
	ResourceUID.add_id(uid2, path2)
	var root2 := Node2D.new()
	var packed2 := PackedScene.new()
	packed2.pack(root2)
	ResourceSaver.save(packed2, path2)
	print("get after add_id+save: ", ResourceLoader.get_resource_uid(path2), " expected ", uid2)
	print("head2: ", FileAccess.get_file_as_string(path2).substr(0, 80).replace("\n", "|"))
	# re-save existing path keeps?
	var root3 := Node2D.new()
	root3.position = Vector2(1, 1)
	var packed3 := PackedScene.new()
	packed3.pack(root3)
	ResourceSaver.save(packed3, path2)
	print("after resave: ", ResourceLoader.get_resource_uid(path2))
	quit(0)
