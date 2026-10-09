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
## Index of the one-way physics layer in the TileSet (0 is the solid world).
const ONE_WAY_PHYSICS := 1
## Collision layer 11, "one_way": the player takes it out of its mask to drop through.
const ONE_WAY_BITS := 1 << 10
const DATA_LAYERS: Array[String] = ["ladder", "hazard", "breakable"]
## Roles whose tiles are solid in a side-view room unless the catalog says otherwise.
const SOLID_ROLES: Array[String] = ["GROUND", "WALL", "CLIFF"]

static func wanted(config: Dictionary) -> bool:
	return JsonUtil.to_str(config.get("archetype", "")) == ARCHETYPE

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

## Gives a tile its side-view parts. The one-way polygon is added once (a polygon that is there,
## maybe edited in Godot, is left alone); the custom data follows the catalog on every build.
static func configure_tile(td: TileData, eff: Dictionary, tile_override: Dictionary, collision: Dictionary, cell: Vector2i) -> void:
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
