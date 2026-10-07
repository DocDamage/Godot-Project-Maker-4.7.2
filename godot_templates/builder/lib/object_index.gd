extends RefCounted
## Names of generated object scenes. Mirrors `object_id -> scene path` in
## res://rpggen/object_index.json.

const OBJECTS_DIR := "res://generated/scenes/objects/"
const INDEX_PATH := "res://rpggen/object_index.json"

## File stem of an object id: `#` and `.` become `__`.
static func stem(id: String) -> String:
	return id.replace("#", "__").replace(".", "__")

static func scene_path(id: String) -> String:
	return OBJECTS_DIR + stem(id) + ".tscn"

## Spawn id of the exit of a building scene.
static func exit_spawn_id(id: String) -> StringName:
	return StringName(stem(id) + "_exit")
