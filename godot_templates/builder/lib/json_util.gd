extends RefCounted
## JSON helpers. NOTE: Godot parses every JSON number as float, so convert with int() where an
## integer is needed (ids, sizes, pixel coordinates).

## Reads and parses a JSON file. Returns null (and pushes an error) on failure.
static func read(path: String) -> Variant:
	if not FileAccess.file_exists(path):
		push_error("[RPG-JSON] file not found: %s" % path)
		return null
	var text := FileAccess.get_file_as_string(path)
	var parser := JSON.new()
	var err := parser.parse(text)
	if err != OK:
		push_error("[RPG-JSON] %s: parse error at line %d: %s" % [path, parser.get_error_line(), parser.get_error_message()])
		return null
	return parser.data

## Writes pretty-printed JSON with sorted keys and a trailing newline, through a temp file.
## Returns an Error code (OK on success).
static func write(path: String, data: Variant) -> int:
	var text := JSON.stringify(data, "  ", true) + "\n"
	var abs_dir := path.get_base_dir()
	if not DirAccess.dir_exists_absolute(abs_dir):
		DirAccess.make_dir_recursive_absolute(abs_dir)
	var tmp := path + ".tmp"
	var f := FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return FileAccess.get_open_error()
	f.store_string(text)
	f.close()
	var err := DirAccess.rename_absolute(tmp, path)
	if err != OK:
		# Some platforms refuse to rename over an existing file: remove the target and retry.
		if FileAccess.file_exists(path):
			DirAccess.remove_absolute(path)
		err = DirAccess.rename_absolute(tmp, path)
	return err
