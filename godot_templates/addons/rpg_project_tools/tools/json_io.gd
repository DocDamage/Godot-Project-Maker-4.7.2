@tool
extends RefCounted
## JSON read/write for the editor tools. Same format as builder/lib/json_util.gd (sorted keys,
## two-space indent, trailing newline, temp file then rename); kept here because the builder
## library lives at a different res:// path in a generated project and in the template project.
## Godot parses every JSON number as a float: convert with int() where an integer is needed.

## Parsed JSON, or null when the file is missing or invalid.
static func read(path: String) -> Variant:
	if not FileAccess.file_exists(path):
		return null
	var parser := JSON.new()
	if parser.parse(FileAccess.get_file_as_string(path)) != OK:
		push_error("[RPG-TOOLS] %s: parse error at line %d: %s" % [path, parser.get_error_line(), parser.get_error_message()])
		return null
	return parser.data

## Returns an Error code (OK on success).
static func write(path: String, data: Variant) -> int:
	var text := JSON.stringify(data, "  ", true) + "\n"
	if not DirAccess.dir_exists_absolute(path.get_base_dir()):
		DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var tmp := path + ".tmp"
	var f := FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return FileAccess.get_open_error()
	f.store_string(text)
	f.close()
	var err := DirAccess.rename_absolute(tmp, path)
	if err != OK:
		if FileAccess.file_exists(path):
			DirAccess.remove_absolute(path)
		err = DirAccess.rename_absolute(tmp, path)
	return err
