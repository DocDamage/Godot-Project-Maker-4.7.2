extends RefCounted
## Read access to the parsed asset catalog with override merging.

const JsonUtil := preload("json_util.gd")

var catalog: Dictionary = {}

func _init(p_catalog: Dictionary = {}) -> void:
	catalog = p_catalog

## Deep merge of `over` onto `base`. A null value in `over` deletes the key. Dictionaries merge
## recursively; every other value (including arrays) replaces.
static func merge(base: Dictionary, over: Dictionary) -> Dictionary:
	var result: Dictionary = base.duplicate(true)
	for key: Variant in over.keys():
		var value: Variant = over[key]
		if value == null:
			result.erase(key)
		elif value is Dictionary:
			var existing: Variant = result.get(key)
			var base_child: Dictionary = {}
			if existing is Dictionary:
				base_child = existing
			var over_child: Dictionary = value
			result[key] = merge(base_child, over_child)
		elif value is Array:
			var items: Array = value
			result[key] = items.duplicate(true)
		else:
			result[key] = value
	return result

## Effective facets of an asset: detected <- rule (folder rules) <- overrides.
static func effective(asset: Dictionary) -> Dictionary:
	var detected: Dictionary = asset.get("detected", {})
	var rule: Dictionary = asset.get("rule", {})
	var overrides: Dictionary = asset.get("overrides", {})
	return merge(merge(detected, rule), overrides)

## A typed copy of one list of the catalog (the parsed JSON gives plain arrays).
func _list(key: String) -> Array[Dictionary]:
	var raw: Array = catalog.get(key, [])
	var out: Array[Dictionary] = []
	out.assign(raw)
	return out

func assets() -> Array[Dictionary]:
	var list := _list("assets")
	list.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return JsonUtil.to_str(a["id"]) < JsonUtil.to_str(b["id"]))
	return list

func asset(id: String) -> Dictionary:
	var raw: Array = catalog.get("assets", [])
	for a: Dictionary in raw:
		if a["id"] == id:
			return a
	return {}

## Assets whose effective role is `role`, sorted by id.
func assets_by_role(role: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for a in assets():
		if effective(a).get("role", "NONE") == role:
			out.append(a)
	return out

## Tileset definitions sorted by name.
func tileset_defs() -> Array[Dictionary]:
	var list := _list("tilesets")
	list.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return JsonUtil.to_str(a["name"]) < JsonUtil.to_str(b["name"]))
	return list

## Sheet objects sorted by id.
func objects() -> Array[Dictionary]:
	var list := _list("objects")
	list.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return JsonUtil.to_str(a["id"]) < JsonUtil.to_str(b["id"]))
	return list

func object(id: String) -> Dictionary:
	var raw: Array = catalog.get("objects", [])
	for o: Dictionary in raw:
		if o["id"] == id:
			return o
	return {}

## The recolour variant (T13.18) whose effective asset is `asset_id`: {id, source, name, op,
## params, stats?}, or {} when the asset is not a variant.
func recolour(asset_id: String) -> Dictionary:
	var raw: Array = catalog.get("variants", [])
	for v: Variant in raw:
		var entry := JsonUtil.to_dict(v)
		if JsonUtil.to_str(entry.get("id", "")) == asset_id:
			return entry
	return {}

## Maps imported from Tiled and LDtk files (T12.49), sorted by id.
func map_defs() -> Array[Dictionary]:
	var list := _list("maps")
	list.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return JsonUtil.to_str(a["id"]) < JsonUtil.to_str(b["id"]))
	return list

## One imported map by id, or {}.
func map_def(map_id: String) -> Dictionary:
	var raw: Array = catalog.get("maps", [])
	for m: Dictionary in raw:
		if m["id"] == map_id:
			return m
	return {}

## Tileset definition by name, or {}.
func tileset_def(tileset_name: String) -> Dictionary:
	var raw: Array = catalog.get("tilesets", [])
	for def: Dictionary in raw:
		if def["name"] == tileset_name:
			return def
	return {}
