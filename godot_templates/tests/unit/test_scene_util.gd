extends RefCounted
## scene_util / texture_util (T4.01).

const SceneUtil := preload("res://builder/lib/scene_util.gd")
const TextureUtil := preload("res://builder/lib/texture_util.gd")

const DIR := "user://test_scene_util/"

func _cleanup() -> void:
	var dir := DirAccess.open("user://")
	if dir != null and dir.dir_exists("test_scene_util"):
		var inner := DirAccess.open(DIR)
		for f in inner.get_files():
			inner.remove(f)
		DirAccess.remove_absolute(DIR)

func test_nested_children_and_an_instance_round_trip(t) -> void:
	_cleanup()
	var inner := Node2D.new()
	inner.name = "Inner"
	var part := Sprite2D.new()
	part.name = "Part"
	inner.add_child(part)
	part.owner = inner
	t.eq(SceneUtil.save_scene(inner, DIR + "inner.tscn"), OK)

	var root := Node2D.new()
	root.name = "Root"
	var group := SceneUtil.add(root, Node2D.new(), root, "Group")
	var leaf := Node2D.new()
	group.add_child(leaf)  # no owner yet: save_scene must set it
	leaf.name = "Leaf"
	var inst := SceneUtil.instance(DIR + "inner.tscn")
	t.ok(inst != null, "instance loads")
	SceneUtil.add(group, inst, root, "InnerInstance")
	t.eq(SceneUtil.save_scene(root, DIR + "outer.tscn"), OK)

	var reloaded := (load(DIR + "outer.tscn") as PackedScene).instantiate()
	t.ok(reloaded.has_node("Group/Leaf"), "nested child survives")
	t.ok(reloaded.has_node("Group/InnerInstance/Part"), "instance is present")
	t.eq(reloaded.get_node("Group/InnerInstance").scene_file_path, DIR + "inner.tscn")
	var text := FileAccess.get_file_as_string(DIR + "outer.tscn")
	t.ok(not text.contains('name="Part"'), "the instanced child's internals are not duplicated")
	reloaded.free()
	_cleanup()

func test_save_keeps_an_existing_uid(t) -> void:
	_cleanup()
	var path := DIR + "uid.tscn"
	var first := Node2D.new()
	first.name = "A"
	t.eq(SceneUtil.save_scene(first, path), OK)
	var uid := ResourceUID.create_id()
	ResourceUID.add_id(uid, path)  # how a scene gets its UID in the ResourceUID cache
	t.eq(ResourceLoader.get_resource_uid(path), uid)
	var second := Node2D.new()
	second.name = "A"
	second.position = Vector2(3, 4)
	t.eq(SceneUtil.save_scene(second, path), OK)
	t.eq(ResourceLoader.get_resource_uid(path), uid, "UID preserved across two saves")
	var back := (load(path) as PackedScene).instantiate() as Node2D
	t.eq(back.position, Vector2(3, 4), "the second save wrote the new content")
	back.free()
	_cleanup()

func test_attach_script_then_properties(t) -> void:
	var node := Node2D.new()
	t.ok(SceneUtil.attach_script(node, "res://addons/rpg_runtime/world/world_object.gd"))
	node.set("asset_id", "x.y")
	t.eq(node.get("asset_id"), "x.y")
	t.ok(not SceneUtil.attach_script(node, "res://does/not/exist.gd"))
	node.free()

func test_region_textures_are_cached_and_embedded(t) -> void:
	_cleanup()
	TextureUtil.clear_cache()
	var a := TextureUtil.region_texture("res://icon.svg", Rect2i(0, 0, 16, 16))
	var b := TextureUtil.region_texture("res://icon.svg", Rect2i(0, 0, 16, 16))
	var c := TextureUtil.region_texture("res://icon.svg", Rect2i(16, 0, 16, 16))
	t.ok(a != null and a == b, "same (path, region) returns the same texture")
	t.ok(c != a, "another region is another texture")
	t.eq(a.region, Rect2(0, 0, 16, 16))
	t.ok(a.resource_path == "", "no per-region .tres file")
	var root := Node2D.new()
	var sprite := Sprite2D.new()
	sprite.texture = a
	root.add_child(sprite)
	t.eq(SceneUtil.save_scene(root, DIR + "tex.tscn"), OK)
	t.ok(FileAccess.get_file_as_string(DIR + "tex.tscn").contains("sub_resource type=\"AtlasTexture\""), "embedded as a sub-resource")
	t.ok(TextureUtil.region_texture("res://missing.png", Rect2i(0, 0, 1, 1)) == null)
	_cleanup()
	TextureUtil.clear_cache()
