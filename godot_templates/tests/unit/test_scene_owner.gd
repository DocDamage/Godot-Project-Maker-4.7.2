extends RefCounted
## Children without `owner` are NOT saved into a PackedScene (the most common recipe bug).

const SCENE := "user://test_scene_owner.tscn"

func test_child_without_owner_is_dropped(t) -> void:
	var root := Node2D.new()
	root.name = "Root"
	var kept := Node2D.new()
	kept.name = "Kept"
	root.add_child(kept)
	kept.owner = root
	var dropped := Node2D.new()
	dropped.name = "Dropped"
	root.add_child(dropped)
	var packed := PackedScene.new()
	t.eq(packed.pack(root), OK)
	t.eq(ResourceSaver.save(packed, SCENE), OK)
	var inst := (load(SCENE) as PackedScene).instantiate()
	t.ok(inst.has_node("Kept"), "owned child is saved")
	t.ok(not inst.has_node("Dropped"), "child without owner is not saved")
	inst.free()
	root.free()
	DirAccess.remove_absolute(SCENE)
