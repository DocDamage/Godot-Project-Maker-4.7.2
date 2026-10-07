extends RefCounted
## Helpers for the user_seed recipes (files under game/ that are written once and never again).

## Saves a resource, creating its folder. Returns an Error code.
static func save(res: Resource, path: String) -> int:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	return ResourceSaver.save(res, path)

## Paths from `candidates` that do not exist yet (the recipe's outputs while it is a seed).
static func missing(candidates: Array) -> PackedStringArray:
	var out := PackedStringArray()
	for p in candidates:
		if not FileAccess.file_exists(p):
			out.append(p)
	return out

## A script instance of the runtime addon (no class_name dependency inside the builder).
static func make(script_path: String) -> Resource:
	var script := load(script_path) as Script
	return script.new() as Resource

## Typed Array[Dictionary] from untyped dictionaries.
static func dict_array(items: Array) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for i in items:
		out.append(i)
	return out
