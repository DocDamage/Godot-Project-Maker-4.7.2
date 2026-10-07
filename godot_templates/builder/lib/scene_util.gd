extends RefCounted
## Scene-building helpers shared by scene recipes (pattern from 01_CONVENTIONS §6.2).

## Sets owners, packs and saves `root` to `path`, then frees it. Returns an Error code.
## An existing scene keeps its UID (when it has one), so references to it stay valid. Headless
## saves write no `uid=` header (probe_uid.gd), so the UID lives in the ResourceUID cache.
static func save_scene(root: Node, path: String) -> int:
	var old_uid := ResourceUID.INVALID_ID
	if FileAccess.file_exists(path):
		old_uid = ResourceLoader.get_resource_uid(path)
	set_owner_recursive(root, root)
	var packed := PackedScene.new()
	var err := packed.pack(root)
	if err == OK:
		DirAccess.make_dir_recursive_absolute(path.get_base_dir())
		err = ResourceSaver.save(packed, path)
		if err == OK and old_uid != ResourceUID.INVALID_ID:
			ResourceSaver.set_uid(path, old_uid)
	root.free()
	return err

## Children without an owner are NOT saved, so every recipe node must go through this.
## Instanced sub-scenes are not descended into: their children belong to them.
static func set_owner_recursive(node: Node, scene_owner: Node) -> void:
	for child in node.get_children():
		child.owner = scene_owner
		if child.scene_file_path == "":
			set_owner_recursive(child, scene_owner)

## Instances the scene at `path`. GEN_EDIT_STATE_INSTANCE keeps the base-scene state so that
## packing the result saves only real overrides (position, target_map, ...). Returns null when
## the scene cannot be loaded.
static func instance(path: String) -> Node:
	if not ResourceLoader.exists(path):
		return null
	var packed := load(path) as PackedScene
	if packed == null:
		return null
	return packed.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)

## Adds `child` under `parent`, names it and makes `root` its owner. Returns the child.
static func add(parent: Node, child: Node, root: Node, child_name: String) -> Node:
	child.name = child_name
	parent.add_child(child)
	child.owner = root
	return child

## Attaches a script. Do this BEFORE setting exported properties.
static func attach_script(node: Node, path: String) -> bool:
	if not ResourceLoader.exists(path):
		return false
	var script := load(path) as Script
	if script == null:
		return false
	node.set_script(script)
	return true
