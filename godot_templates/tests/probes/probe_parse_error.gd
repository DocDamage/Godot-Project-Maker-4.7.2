extends SceneTree
# Probe: how does load() report a script with a parse error? The deliberately broken source lives
# in tests/probes/broken/ (ignored by Godot via .gdignore, stored as .txt); it is copied to
# user:// before loading.

func _initialize() -> void:
	var src := FileAccess.get_file_as_string("res://tests/probes/broken/broken_script.gd.txt")
	var dst := "user://probe_broken.gd"
	var f := FileAccess.open(dst, FileAccess.WRITE)
	f.store_string(src)
	f.close()
	var s: Variant = load(dst)
	print("PROBE broken_load_is_null: ", s == null)
	if s != null:
		print("PROBE broken_is_gdscript: ", s is GDScript)
		print("PROBE broken_can_instantiate: ", (s as GDScript).can_instantiate())
	var good: Variant = load("res://builder/lib/log.gd")
	print("PROBE good_can_instantiate: ", (good as GDScript).can_instantiate())
	var scn: Variant = load("res://builder/build.gd")
	print("PROBE scenetree_script_can_instantiate: ", (scn as GDScript).can_instantiate(), " base=", (scn as GDScript).get_instance_base_type())
	DirAccess.remove_absolute(dst)
	quit(0)
