extends RefCounted
## Read access to the parsed asset catalog with override merging.

const JsonUtil := preload("json_util.gd")

const TOP_DOWN := "top_down"
const ISOMETRIC := "isometric"
## The usage of a picture rpggen packed isometric tiles into: the tile set's, nobody's choice.
const ISO_ATLAS_USAGE := "iso_atlas"

var catalog: Dictionary = {}
## asset id -> asset, of the list `_indexed` (`asset`)
var _index: Dictionary = {}
var _indexed: Array = []
var _indexed_size := -1
## How the project is seen (the config's `projection`, T17.13): the build context sets it.
## `assets()` and everything built on it leave out what was drawn for the other view.
var projection: String = TOP_DOWN

func _init(p_catalog: Dictionary = {}, p_projection: String = TOP_DOWN) -> void:
	catalog = p_catalog
	projection = p_projection if p_projection == ISOMETRIC else TOP_DOWN

## Whether an asset with the effective facets `eff` can be used by a project seen in
## `p_projection`: a top-down project uses nothing that was drawn for the isometric view (no
## isometric tile, no tree, house or car drawn at that angle), and an isometric project paints
## with no sheet of square tiles. Keep equal to `rpggen.core.catalog.fits_projection`.
static func fits(eff: Dictionary, p_projection: String) -> bool:
	var usage := JsonUtil.to_str(eff.get("usage", ""))
	if usage == ISO_ATLAS_USAGE:
		return false
	if p_projection == ISOMETRIC:
		return usage != "tiles"
	return JsonUtil.to_str(eff.get("projection", "")) != ISOMETRIC

## One effective facet of an asset without merging the three layers: the override's, else the
## rule's, else the detected one (a null in a layer deletes the key, as `merge` has it).
static func facet(asset: Dictionary, key: String) -> Variant:
	for layer: String in ["overrides", "rule", "detected"]:
		var part: Variant = asset.get(layer)
		if part is Dictionary:
			var facets: Dictionary = part
			if facets.has(key):
				return facets[key]
	return null

## The same for an asset of this project. (Asked of every asset on every lookup, so it reads
## the two facets it needs and merges nothing.)
func fits_projection(asset: Dictionary) -> bool:
	return fits({"usage": facet(asset, "usage"), "projection": facet(asset, "projection")}, projection)

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

## The assets a recipe may pick from, sorted by id: every asset of the catalog that fits the
## project's projection. Every lookup by role, tag or usage goes through here, so no recipe of
## a top-down or an arcade game picks an isometric tile for its ground or an isometric tree for
## its scenery. `asset(id)` still finds any asset by its id (the tile set recipe needs the
## tiles it was told to use).
func assets() -> Array[Dictionary]:
	var list: Array[Dictionary] = []
	for a in _list("assets"):
		if fits_projection(a):
			list.append(a)
	list.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return JsonUtil.to_str(a["id"]) < JsonUtil.to_str(b["id"]))
	return list

func asset(id: String) -> Dictionary:
	var raw: Array = catalog.get("assets", [])
	# an index by id (2026-10-26: a recipe that asks for 935 tiles of a catalog of 100,000
	# assets once an actor took 40 s an actor), made again when the list is another or grew
	if not is_same(raw, _indexed) or raw.size() != _indexed_size:
		_index.clear()
		for a: Dictionary in raw:
			if not _index.has(a["id"]):
				_index[a["id"]] = a
		_indexed = raw
		_indexed_size = raw.size()
	if _index.has(id):
		var found: Dictionary = _index[id]
		if found.get("id") == id:
			return found
	for a: Dictionary in raw:  # an entry changed in place since the index was made
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
