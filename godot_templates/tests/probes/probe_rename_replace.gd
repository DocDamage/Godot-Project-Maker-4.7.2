extends SceneTree
# Probe (T12.08): does DirAccess.rename_absolute replace an existing file? Run on every platform
# the generator supports; the result is recorded in docs/godot_api_verified.md.

func _initialize() -> void:
	var dir := "user://probe_rename_replace"
	DirAccess.make_dir_recursive_absolute(dir)
	var old_path := dir + "/slot.json"
	var new_path := dir + "/slot.tmp"
	var f := FileAccess.open(old_path, FileAccess.WRITE)
	f.store_string("old")
	f.close()
	var g := FileAccess.open(new_path, FileAccess.WRITE)
	g.store_string("new")
	g.close()
	var err := DirAccess.rename_absolute(new_path, old_path)
	var text := FileAccess.get_file_as_string(old_path)
	print("PROBE rename_replace: os=", OS.get_name(), " err=", err, " (OK=", OK, ") content=", text, " tmp_left=", FileAccess.file_exists(new_path))
	for p in [old_path, new_path]:
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(p)
	DirAccess.remove_absolute(dir)
	quit(0 if (err == OK and text == "new") else 1)
