extends SceneTree
# Probe: JSON.stringify(data, indent, sort_keys) and atomic-ish write via DirAccess.rename_absolute
# over an existing file (Windows may refuse to overwrite).

func _initialize() -> void:
	var data := {"b": 1, "a": [1, 2.5, {"z": true, "y": null}], "empty": [], "d": {}}
	var text := JSON.stringify(data, "  ", true)
	print("PROBE json_stringify:\n", text)
	var path := "user://probe_json.json"
	var tmp := path + ".tmp"
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string("old")
	f.close()
	var f2 := FileAccess.open(tmp, FileAccess.WRITE)
	f2.store_string(text + "\n")
	f2.close()
	var err := DirAccess.rename_absolute(tmp, path)
	print("PROBE rename_over_existing: err=", err, " (OK=", OK, ")")
	if err != OK:
		DirAccess.remove_absolute(path)
		err = DirAccess.rename_absolute(tmp, path)
		print("PROBE rename_after_remove: err=", err)
	print("PROBE json_roundtrip: ", FileAccess.get_file_as_string(path).length() > 10)
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
	print("PROBE json_parse_int_type: ", typeof(parsed["b"]), " (TYPE_FLOAT=", TYPE_FLOAT, ", TYPE_INT=", TYPE_INT, ")")
	print("PROBE sha256_text: ", "abc".sha256_text())
	DirAccess.remove_absolute(path)
	quit(0)
