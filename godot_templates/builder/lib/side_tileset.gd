extends RefCounted
## The side-view parts of a TileSet (T14.03), built only when the project's archetype is
## metroidvania: a second physics layer for one-way platforms and the bool custom data `ladder`,
## `hazard` and `breakable`. The other archetypes never call this, so their TileSets are what
## they were in 1.1.
##
## What a tile is comes from the catalog: its collision profile (`ONE_WAY`, `LADDER`; a tile's own
## in `tile_overrides`, else the sheet's), the `custom` of its tile override (`hazard`,
## `breakable`, `ladder`) and the sheet's tags (`one_way`, `ladder`, `hazard`, `breakable`).

const JsonUtil := preload("json_util.gd")
const Geometry := preload("geometry.gd")

const ARCHETYPE := "metroidvania"
## The kinds of game that are seen from the side: their TileSets get the side-view parts.
const SIDE_VIEW_KINDS: Array[String] = ["metroidvania", "run_and_gun"]
## A project of the packs' assets and no game (T17.33).
const ASSETS_KIND := "assets"
## Index of the one-way physics layer in the TileSet (0 is the solid world).
const ONE_WAY_PHYSICS := 1
## Collision layer 11, "one_way": the player takes it out of its mask to drop through.
const ONE_WAY_BITS := 1 << 10
const DATA_LAYERS: Array[String] = ["ladder", "hazard", "breakable"]
## Roles whose tiles are solid in a side-view room unless the catalog says otherwise.
const SOLID_ROLES: Array[String] = ["GROUND", "WALL", "CLIFF"]
## The String custom data the Metroidvania Developer System (MDS) reads to tell decoration tiles
## apart: its Generate cave, Auto-decorate and kind fills paint with the tiles of a kind. Added
## only to a TileSet that has a tile of a kind, so the others are what they were.
const KIND_LAYER := "mds_kind"
## The kinds MDS knows (its tile palette's KNOWN_KINDS): grass to mushroom stand on floors,
## vines, stalactites and moss hang from ceilings, foliage fills the background.
const KNOWN_KINDS: Array[String] = ["foliage", "grass", "fern", "flower", "mushroom", "vine_top", "vine_mid", "vine_end", "stalactite_small", "stalactite_large", "hanging_moss"]
## Roles of the sheets whose name may say the kind of all their tiles. A GROUND sheet called
## grass is the ground, not tufts of it.
const KIND_ROLES: Array[String] = ["DECORATION", "BACKGROUND"]
## Words of a sheet's file name -> the kind of its tiles. Vines are not here: a vine sheet is a
## ladder (the classifier's ladder words), and a ladder gets no kind.
const KIND_WORDS := {
	"grass": "grass", "grasses": "grass", "tuft": "grass", "tufts": "grass", "weed": "grass", "weeds": "grass",
	"fern": "fern", "ferns": "fern", "plant": "fern", "plants": "fern",
	"flower": "flower", "flowers": "flower", "bloom": "flower", "blooms": "flower", "blossom": "flower", "blossoms": "flower",
	"mushroom": "mushroom", "mushrooms": "mushroom", "shroom": "mushroom", "shrooms": "mushroom", "fungus": "mushroom", "fungi": "mushroom", "toadstool": "mushroom", "toadstools": "mushroom",
	"stalactite": "stalactite_small", "stalactites": "stalactite_small", "icicle": "stalactite_small", "icicles": "stalactite_small",
	"foliage": "foliage", "leaves": "foliage", "leaf": "foliage", "bush": "foliage", "bushes": "foliage", "shrub": "foliage", "shrubs": "foliage", "hedge": "foliage", "hedges": "foliage",
}
## With a stalactite word, these make it the large one.
const LARGE_WORDS: Array[String] = ["large", "big", "huge", "long"]

static func wanted(config: Dictionary) -> bool:
	return side_view(config)

## True for a project seen from the side: a side-view kind, or an assets-only project whose view
## is the side's (T17.33: config.ASSETS_KIND, `view`).
static func side_view(config: Dictionary) -> bool:
	var kind := JsonUtil.to_str(config.get("archetype", ""))
	return SIDE_VIEW_KINDS.has(kind) or (kind == ASSETS_KIND and JsonUtil.to_str(config.get("view", "")) == "side")

## Adds the one-way physics layer and the custom data layers the TileSet does not have yet.
## Nothing that exists is removed, reordered or retyped.
static func ensure_layers(ts: TileSet) -> void:
	while ts.get_physics_layers_count() <= ONE_WAY_PHYSICS:
		var index := ts.get_physics_layers_count()
		ts.add_physics_layer()
		if index == ONE_WAY_PHYSICS:
			ts.set_physics_layer_collision_layer(index, ONE_WAY_BITS)
			ts.set_physics_layer_collision_mask(index, 0)
	for layer_name in DATA_LAYERS:
		if ts.get_custom_data_layer_by_name(layer_name) == -1:
			ts.add_custom_data_layer()
			var index := ts.get_custom_data_layers_count() - 1
			ts.set_custom_data_layer_name(index, layer_name)
			ts.set_custom_data_layer_type(index, TYPE_BOOL)

static func _tags(eff: Dictionary) -> Array:
	var tags: Variant = eff.get("tags", [])
	if tags is Array:
		var list: Array = tags
		return list
	return []

## The collision of a sheet that names none: by its tags, else solid for ground and walls.
static func sheet_collision(eff: Dictionary) -> Dictionary:
	var given: Variant = eff.get("collision")
	# the stand-in for a pack without ground tiles is made for a top-down map (no collision);
	# in a room it is the floor
	if _tags(eff).has("debug_placeholder") and SOLID_ROLES.has(JsonUtil.to_str(eff.get("role", ""))):
		return {"profile": "FULL"}
	if given is Dictionary:
		var spec: Dictionary = given
		return spec
	var tags := _tags(eff)
	if tags.has("one_way"):
		return {"profile": "ONE_WAY"}
	if tags.has("ladder"):
		return {"profile": "LADDER"}
	if tags.has("hazard"):
		return {"profile": "NONE"}
	if tags.has("platform") or SOLID_ROLES.has(JsonUtil.to_str(eff.get("role", ""))):
		return {"profile": "FULL"}
	return {"profile": "NONE"}

## How thick a one-way platform's surface is: 5 px of a 16 px tile.
static func one_way_thickness(cell: Vector2i) -> float:
	return maxf(2.0, floorf(cell.y * 5.0 / 16.0))

## What a tile is in a side-view room: {one_way, ladder, hazard, breakable}.
static func kinds(eff: Dictionary, tile_override: Dictionary, collision: Dictionary) -> Dictionary:
	var tags := _tags(eff)
	var custom: Dictionary = {}
	var given: Variant = tile_override.get("custom")
	if given is Dictionary:
		custom = given
	var profile := JsonUtil.to_str(collision.get("profile", "NONE"))
	var own_collision := tile_override.has("collision")
	return {
		"one_way": profile == "ONE_WAY",
		"ladder": profile == "LADDER" or JsonUtil.to_bool(custom.get("ladder", false)),
		"hazard": JsonUtil.to_bool(custom.get("hazard", tags.has("hazard") and not own_collision)),
		"breakable": JsonUtil.to_bool(custom.get("breakable", tags.has("breakable") and not own_collision)),
	}

## The small-letter words of a file name, camel case split and numbers dropped
## (`mushroomRed2.png` is mushroom, red).
static func name_words(file: String) -> Array[String]:
	var stem := file.get_file().get_basename()
	var spaced := ""
	for i in stem.length():
		var ch := stem[i]
		if i > 0 and ch != ch.to_lower() and stem[i - 1] == stem[i - 1].to_lower() and stem[i - 1] != stem[i - 1].to_upper():
			spaced += " "
		spaced += ch
	var out: Array[String] = []
	var word := ""
	for ch in spaced.to_lower() + " ":
		if (ch >= "a" and ch <= "z"):
			word += ch
		else:
			if not word.is_empty():
				out.append(word)
			word = ""
	return out

## The kind MDS reads off a sheet's file name (KIND_WORDS), "" when it says none or more than one.
static func sheet_kind(eff: Dictionary, file: String) -> String:
	if not KIND_ROLES.has(JsonUtil.to_str(eff.get("role", ""))):
		return ""
	var words := name_words(file)
	var found := ""
	for w in words:
		var kind := JsonUtil.to_str(KIND_WORDS.get(w, ""))
		if kind.is_empty() or kind == found:
			continue
		if not found.is_empty():
			return ""  # flowers_and_mushrooms: a mixed sheet, no kind
		found = kind
	if found == "stalactite_small":
		for w in LARGE_WORDS:
			if words.has(w):
				return "stalactite_large"
	return found

## The MDS kind of a tile: its own `custom.mds_kind` (anything the user wrote), else its sheet's
## (`sheet_kind`). A tile that collides, is a ladder, a hazard or breakable, or is part of a
## terrain has none from its sheet: a decoration is drawn, never stood on.
static func tile_kind(eff: Dictionary, tile_override: Dictionary, collision: Dictionary, file: String) -> String:
	var own := JsonUtil.to_str(JsonUtil.to_dict(tile_override.get("custom", {})).get(KIND_LAYER, ""))
	if not own.is_empty():
		return own
	if JsonUtil.to_str(collision.get("profile", "NONE")) != "NONE" or tile_override.get("terrain") is Dictionary:
		return ""
	var what := kinds(eff, tile_override, collision)
	if what["ladder"] or what["hazard"] or what["breakable"]:
		return ""
	return sheet_kind(eff, file)

## Gives a tile its side-view parts. The one-way polygon is added once (a polygon that is there,
## maybe edited in Godot, is left alone); the custom data follows the catalog on every build, but
## for the MDS kind, which is written only where the tile has none (a kind set in Godot stays).
## `file` is the sheet's path, whose name may say the kind of its decorations.
static func configure_tile(td: TileData, eff: Dictionary, tile_override: Dictionary, collision: Dictionary, cell: Vector2i, ts: TileSet = null, file: String = "") -> void:
	var what := kinds(eff, tile_override, collision)
	if what["one_way"] and td.get_collision_polygons_count(ONE_WAY_PHYSICS) == 0:
		var points := Geometry.to_tile_space(Geometry.rect_poly(0.0, 0.0, float(cell.x), one_way_thickness(cell)), cell)
		td.add_collision_polygon(ONE_WAY_PHYSICS)
		td.set_collision_polygon_points(ONE_WAY_PHYSICS, 0, points)
		td.set_collision_polygon_one_way(ONE_WAY_PHYSICS, 0, true)
	for layer_name in DATA_LAYERS:
		var value: bool = what[layer_name]
		if JsonUtil.to_bool(td.get_custom_data(layer_name)) != value:
			td.set_custom_data(layer_name, value)
	var kind := tile_kind(eff, tile_override, collision, file)
	if ts != null and not kind.is_empty():
		_ensure_string_layer(ts, KIND_LAYER)
		var own := tile_override.has("custom") and JsonUtil.to_dict(tile_override["custom"]).has(KIND_LAYER)
		if own or JsonUtil.to_str(td.get_custom_data(KIND_LAYER)).is_empty():
			td.set_custom_data(KIND_LAYER, kind)
	# a hill's side and the earth under its foot (T17.33): their layers are added only to a
	# TileSet that has such a tile, so the TileSets of packs without hills are what they were
	var custom := JsonUtil.to_dict(tile_override.get("custom", {}))
	var slope := JsonUtil.to_str(custom.get("slope", ""))
	var under := JsonUtil.to_str(custom.get("under_slope", ""))
	for pair: Array in [["slope_", slope], ["under_slope_", under]]:
		var which := JsonUtil.to_str(pair[1])
		if which != "up" and which != "down":
			continue
		var layer_name := JsonUtil.to_str(pair[0]) + which
		if ts == null:
			continue
		_ensure_bool_layer(ts, layer_name)
		td.set_custom_data(layer_name, true)

## The String custom data layer `layer_name` of a TileSet, added when it is missing (one MDS
## made, of the same name, is used as it is).
static func _ensure_string_layer(ts: TileSet, layer_name: String) -> void:
	if ts.get_custom_data_layer_by_name(layer_name) == -1:
		ts.add_custom_data_layer()
		var index := ts.get_custom_data_layers_count() - 1
		ts.set_custom_data_layer_name(index, layer_name)
		ts.set_custom_data_layer_type(index, TYPE_STRING)

## The bool custom data layer `layer_name` of a TileSet, added when it is missing.
static func _ensure_bool_layer(ts: TileSet, layer_name: String) -> void:
	if ts.get_custom_data_layer_by_name(layer_name) == -1:
		ts.add_custom_data_layer()
		var index := ts.get_custom_data_layers_count() - 1
		ts.set_custom_data_layer_name(index, layer_name)
		ts.set_custom_data_layer_type(index, TYPE_BOOL)
