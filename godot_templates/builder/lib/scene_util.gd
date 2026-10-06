extends RefCounted
## Scene-building helpers shared by scene recipes (pattern from 01_CONVENTIONS §6.2).

## Sets owners, packs and saves `root` to `path`, then frees it. Returns an Error code.
static func save_scene(root: Node, path: String) -> int:
	set_owner_recursive(root, root)
	var packed := PackedScene.new()
	var err := packed.pack(root)
	if err == OK:
		DirAccess.make_dir_recursive_absolute(path.get_base_dir())
		err = ResourceSaver.save(packed, path)
	root.free()
	return err

## Children without an owner are NOT saved, so every recipe node must go through this.
## Instanced sub-scenes are not descended into: their children belong to them.
static func set_owner_recursive(node: Node, scene_owner: Node) -> void:
	for child in node.get_children():
		child.owner = scene_owner
		if child.scene_file_path == "":
			set_owner_recursive(child, scene_owner)
