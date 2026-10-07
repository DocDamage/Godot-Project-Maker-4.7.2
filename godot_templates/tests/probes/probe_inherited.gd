extends SceneTree
# Can a headless script save an inherited scene? Run:
#   godot --headless --path godot_templates --script res://tests/probes/probe_inherited.gd
# Result on 4.7.1: NO. instantiate(GEN_EDIT_STATE_MAIN_INHERITED) returns a root whose
# scene_file_path is the base, but pack() writes a flat scene (no ext_resource of the base, no
# instance= root). The actor scenes are therefore built by one shared function instead.
func _initialize() -> void:
	var base := Node2D.new()
	base.name = "Base"
	var child := Node2D.new()
	child.name = "Child"
	base.add_child(child)
	child.owner = base
	var packed := PackedScene.new()
	packed.pack(base)
	ResourceSaver.save(packed, "user://probe_base.tscn")
	base.free()
	var inherited := (load("user://probe_base.tscn") as PackedScene).instantiate(PackedScene.GEN_EDIT_STATE_MAIN_INHERITED)
	inherited.name = "Derived"
	var packed2 := PackedScene.new()
	packed2.pack(inherited)
	ResourceSaver.save(packed2, "user://probe_derived.tscn")
	var text := FileAccess.get_file_as_string("user://probe_derived.tscn")
	print("inherited scene saved with an ext_resource of the base: ", text.contains("probe_base.tscn"))
	inherited.free()
	quit()
