@tool
extends RefCounted
## Reads and edits the asset catalog (res://rpggen/asset_catalog.json) from the editor.
## `effective` and `recompute_status` port rpggen.core.catalog; tests/fixtures/status_cases.json
## is checked by both implementations.

const JsonIo := preload("json_io.gd")

const CATALOG_PATH := "res://rpggen/asset_catalog.json"
const CONFIRMED_CONFIDENCE := 0.999
const AUTO_CONFIDENCE := 0.75

static func load_catalog(path: String = CATALOG_PATH) -> Dictionary:
	var data: Variant = JsonIo.read(path)
	return data if data is Dictionary else {}

## Returns an Error code (OK on success).
static func save_catalog(catalog: Dictionary, path: String = CATALOG_PATH) -> int:
	return JsonIo.write(path, catalog)

## Deep merge of `over` onto `base`; a null value deletes the key, dictionaries merge, every other
## value (arrays too) replaces.
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
		else:
			if value is Array:
				var items: Array = value
				result[key] = items.duplicate(true)
			else:
				result[key] = value
	return result

## detected <- rule <- overrides.
static func effective(asset: Dictionary) -> Dictionary:
	var detected: Dictionary = asset.get("detected", {})
	var rule: Dictionary = asset.get("rule", {})
	var overrides: Dictionary = asset.get("overrides", {})
	return merge(merge(detected, rule), overrides)

## Status of an asset (02_SCHEMAS.md section 4.3). CONFLICT stays until the user resolves it.
static func recompute_status(asset: Dictionary, file_missing: bool = false, user_confirmed: bool = false) -> String:
	if file_missing:
		return "MISSING"
	if asset.get("status", "") == "CONFLICT":
		return "CONFLICT"
	if effective(asset).get("role", "") == "NONE":
		return "UNUSED"
	var overrides: Variant = asset.get("overrides", {})
	var has_overrides := false
	if overrides is Dictionary:
		var override_dict: Dictionary = overrides
		has_overrides = not override_dict.is_empty()
	var confidence := JsonIo.to_float(asset.get("confidence", 0.0))
	if has_overrides or confidence >= CONFIRMED_CONFIDENCE or user_confirmed:
		return "CONFIRMED"
	if confidence >= AUTO_CONFIDENCE:
		return "AUTO_DETECTED"
	return "NEEDS_REVIEW"

static func find_asset(catalog: Dictionary, id: String) -> Dictionary:
	var list: Array = catalog.get("assets", [])
	for a: Dictionary in list:
		if a["id"] == id:
			return a
	return {}

## Index of the sheet object with this id in catalog["objects"], or -1.
static func object_index(catalog: Dictionary, id: String) -> int:
	var objects: Array = catalog.get("objects", [])
	for i in objects.size():
		if objects[i]["id"] == id:
			return i
	return -1

## Writes `changes` (a partial facet dictionary) into the asset's overrides and recomputes its
## status. A null value removes that override again (the detected value applies). Returns the asset's new status, or "" when the asset is unknown.
static func apply_overrides(catalog: Dictionary, asset_id: String, changes: Dictionary) -> String:
	var asset := find_asset(catalog, asset_id)
	if asset.is_empty():
		return ""
	var current: Dictionary = asset.get("overrides", {})
	var merged := merge(current, changes)
	asset["overrides"] = merged
	asset["status"] = recompute_status(asset)
	return JsonIo.to_str(asset["status"])

## Replaces fields of a sheet object (role, tags, collision, origin, footprint ...). An edited
## object is the user's: source "user", status CONFIRMED. Returns false for an unknown object.
static func apply_object_changes(catalog: Dictionary, object_id: String, changes: Dictionary) -> bool:
	var index := object_index(catalog, object_id)
	if index < 0:
		return false
	var obj: Dictionary = catalog["objects"][index]
	for key: Variant in changes.keys():
		if changes[key] == null:
			obj.erase(key)
		else:
			obj[key] = changes[key]
	obj["source"] = "user"
	obj["status"] = "CONFIRMED" if obj.get("role", "NONE") != "NONE" else "UNUSED"
	return true

## Entity id allocations of a map (kind -> last number), created on demand.
static func entity_allocations(catalog: Dictionary, map_id: String) -> Dictionary:
	if not (catalog.get("id_allocations") is Dictionary):
		catalog["id_allocations"] = {"tilesets": {}, "entities": {}}
	var alloc: Dictionary = catalog["id_allocations"]
	if not (alloc.get("entities") is Dictionary):
		alloc["entities"] = {}
	var by_map: Dictionary = alloc["entities"]
	if not (by_map.get(map_id) is Dictionary):
		by_map[map_id] = {}
	var allocation: Dictionary = by_map[map_id]
	return allocation
