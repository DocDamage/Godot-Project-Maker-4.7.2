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

# ---- typed conversions of Variant values (strict GDScript, T12.29) -------------------------------
# JSON and Dictionary values arrive as Variant. Passing one to a typed parameter, or converting it
# with int()/float()/bool(), is flagged by the strict warnings; these functions are the one place
# that looks at the type. They return the fallback when the value is not what was expected.

## `int(v)` for a Variant: numbers (JSON numbers are floats), booleans and numeric strings.
static func to_int(v: Variant, fallback: int = 0) -> int:
	match typeof(v):
		TYPE_INT:
			var i: int = v
			return i
		TYPE_FLOAT:
			var f: float = v
			return int(f)
		TYPE_BOOL:
			var b: bool = v
			return int(b)
		TYPE_STRING, TYPE_STRING_NAME:
			var s: String = v
			return s.to_int()
	return fallback

## `float(v)` for a Variant.
static func to_float(v: Variant, fallback: float = 0.0) -> float:
	match typeof(v):
		TYPE_INT, TYPE_FLOAT:
			var f: float = v
			return f
		TYPE_BOOL:
			var b: bool = v
			return float(b)
		TYPE_STRING, TYPE_STRING_NAME:
			var s: String = v
			return s.to_float()
	return fallback

## `bool(v)` for a Variant: booleans and numbers (zero is false).
static func to_bool(v: Variant, fallback: bool = false) -> bool:
	match typeof(v):
		TYPE_BOOL:
			var b: bool = v
			return b
		TYPE_INT, TYPE_FLOAT:
			var f: float = v
			return f != 0.0
	return fallback

## `String(v)` for a Variant (any value prints as text).
static func to_str(v: Variant) -> String:
	return str(v)

## `StringName(v)` for a Variant.
static func to_name(v: Variant) -> StringName:
	return StringName(str(v))

## The Dictionary in `v`, or an empty one.
static func to_dict(v: Variant) -> Dictionary:
	if v is Dictionary:
		var d: Dictionary = v
		return d
	return {}

## The Array in `v`, or an empty one.
static func to_array(v: Variant) -> Array:
	if v is Array:
		var a: Array = v
		return a
	return []
