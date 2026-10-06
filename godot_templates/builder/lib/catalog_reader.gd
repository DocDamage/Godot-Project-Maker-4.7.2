extends RefCounted
## Read access to the parsed asset catalog with override merging.

var catalog: Dictionary = {}

func _init(p_catalog: Dictionary = {}) -> void:
	catalog = p_catalog

## Deep merge of `over` onto `base`. A null value in `over` deletes the key. Dictionaries merge
## recursively; every other value (including arrays) replaces.
static func merge(base: Dictionary, over: Dictionary) -> Dictionary:
	var result: Dictionary = base.duplicate(true)
	for key in over.keys():
		var value: Variant = over[key]
		if value == null:
			result.erase(key)
		elif value is Dictionary:
			var existing: Variant = result.get(key)
			result[key] = merge(existing if existing is Dictionary else {}, value)
		else:
			result[key] = value.duplicate(true) if (value is Array) else value
	return result

## Effective facets of an asset: detected merged with overrides.
static func effective(asset: Dictionary) -> Dictionary:
	return merge(asset.get("detected", {}), asset.get("overrides", {}))

func assets() -> Array:
	var list: Array = catalog.get("assets", []).duplicate()
	list.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return String(a["id"]) < String(b["id"]))
	return list

func asset(id: String) -> Dictionary:
	for a in catalog.get("assets", []):
		if a["id"] == id:
			return a
	return {}

## Assets whose effective role is `role`, sorted by id.
func assets_by_role(role: String) -> Array:
	var out: Array = []
	for a in assets():
		if effective(a).get("role", "NONE") == role:
			out.append(a)
	return out

## Tileset definitions sorted by name.
func tileset_defs() -> Array:
	var list: Array = catalog.get("tilesets", []).duplicate()
	list.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return String(a["name"]) < String(b["name"]))
	return list
