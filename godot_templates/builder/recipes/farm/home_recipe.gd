extends RefCounted
## The shipping bin and the bed of a farm (T17.08):
## * generated/scenes/farm/shipping_bin.tscn, an RpgShippingBin, and generated/scenes/farm/bed.tscn,
##   an RpgBed: a solid thing of the map that is used with `interact`, with the picture of the
##   packs (FarmBuild.bin_asset, bed_asset), else the one of the drawn farm kit, else a drawn box.
## * `build_bin(ctx)` and `build_bed(ctx)` make the nodes; the farm's map recipe (T17.06)
##   instances the two scenes and puts them where its plan says: the bin on the farm, beside
##   the house, the bed in the farmhouse. The origin of both is
##   the middle of their lower edge; the bed says which cells it lies on (`footprint`) and where
##   the farmer wakes (`wake_offset`, the cell under its foot unless the recipe sets another).
##
## **On an isometric farm** (T17.14) both stand on diamonds: the origin of each is the middle of
## the cell of its footprint nearest the camera, it blocks the diamonds it stands on, and what
## nobody drew is a box on them (the bin a crate with a lid; the bed a frame, a mattress and a
## pillow over two cells, its head to the north). The drawn farm kit has neither for this view
## (its bin and its bed lie flat on squares). A pack's own picture is used as it is: one drawn
## for the isometric view with the middle of its diamond on the origin, any other standing on it.

const RECIPE_VERSION := 1
## The version of what the recipe does for an isometric project only (T17.14): in the hash of
## such a project and of no other.
const ISO_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const MapGeo := preload("../../lib/map_geo.gd")
const FarmBuild := preload("farm_build.gd")

const OUT_DIR := "res://generated/scenes/farm/"
const BIN_SCENE := OUT_DIR + "shipping_bin.tscn"
const BED_SCENE := OUT_DIR + "bed.tscn"
const BIN_NAME := "ShippingBin"
const BED_NAME := "Bed"
const BIN_COLOR := Color(0.55, 0.36, 0.2)
const BED_COLOR := Color(0.35, 0.45, 0.75)
const BED_WOOD := Color(0.5, 0.33, 0.18)
const PILLOW := Color(0.93, 0.93, 0.88)
## The cells a drawn bed lies on in the isometric view: one wide and two long, as the plan's.
const ISO_BED_CELLS := Vector2i(1, 2)

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([BIN_SCENE, BED_SCENE])

func input_hash(ctx: BuildContext) -> String:
	var art := {}
	for entry: Array in [["bin", FarmBuild.bin_asset(ctx)], ["bed", FarmBuild.bed_asset(ctx)]]:
		var asset: Dictionary = entry[1]
		art[entry[0]] = {"sha256": asset.get("sha256", ""), "eff": ctx.catalog.effective(asset) if not asset.is_empty() else {}}
	var hashed := {"v": RECIPE_VERSION, "tile": FarmBuild.tile(ctx), "art": art}
	if MapGeo.is_isometric(ctx):  # only an isometric project's hash has the keys (T17.14)
		var footprint := MapGeo.new(ctx).footprint
		hashed["iso"] = [footprint.x, footprint.y]
		hashed["iso_v"] = ISO_VERSION
	return ctx.stable_hash(hashed)

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	for entry: Array in [[build_bin(ctx), BIN_SCENE], [build_bed(ctx), BED_SCENE]]:
		var node: Node = entry[0]
		var path: String = entry[1]
		var err := SceneUtil.save_scene(node, path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	return issues

# ---------------------------------------------------------------- the two scenes

## The shipping bin (RpgShippingBin), not yet on a map.
static func build_bin(ctx: BuildContext) -> StaticBody2D:
	if MapGeo.is_isometric(ctx):
		return _iso_bin(ctx, MapGeo.new(ctx).footprint)
	var tile := FarmBuild.tile(ctx)
	var texture := FarmBuild.first_frame(ctx, FarmBuild.bin_asset(ctx))
	var size := Vector2(texture.get_size()) if texture != null else Vector2(tile, tile)
	var body := _body(BIN_NAME, FarmBuild.BIN)
	# its base blocks, a tile deep at most: the farmer walks behind a tall bin
	_add_shape(body, Vector2(size.x * 0.9, minf(size.y, tile) * 0.8))
	_add_picture(body, texture, size, BIN_COLOR)
	return body

## The bed (RpgBed), not yet on a map: all of it blocks (it is seen from above).
static func build_bed(ctx: BuildContext) -> StaticBody2D:
	if MapGeo.is_isometric(ctx):
		return _iso_bed(ctx, MapGeo.new(ctx).footprint)
	var tile := FarmBuild.tile(ctx)
	var texture := FarmBuild.first_frame(ctx, FarmBuild.bed_asset(ctx))
	var size := Vector2(texture.get_size()) if texture != null else Vector2(tile, tile * 2.0)
	var body := _body(BED_NAME, FarmBuild.BED)
	body.set("footprint", Vector2i(maxi(1, ceili(size.x / tile)), maxi(1, ceili(size.y / tile))))
	body.set("wake_offset", Vector2(0.0, tile * 0.5))  # the middle of the cell under its foot
	_add_shape(body, size * 0.9)
	_add_picture(body, texture, size, BED_COLOR)
	return body

## A solid thing that is found by `interact`: the world (1) and the interactables (5).
static func _body(node_name: String, script: String) -> StaticBody2D:
	var body := StaticBody2D.new()
	body.name = node_name
	SceneUtil.attach_script(body, script)
	body.collision_layer = 0
	body.collision_mask = 0
	body.set_collision_layer_value(1, true)
	body.set_collision_layer_value(5, true)
	return body

## A rectangle that stands on the origin.
static func _add_shape(body: StaticBody2D, size: Vector2) -> void:
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var rect := RectangleShape2D.new()
	rect.size = size
	shape.shape = rect
	shape.position = Vector2(0.0, -size.y * 0.5)
	body.add_child(shape)

## The picture with the middle of its lower edge on the origin, or a box of `colour`.
static func _add_picture(body: StaticBody2D, texture: Texture2D, size: Vector2, colour: Color) -> void:
	if texture == null:
		body.add_child(FarmBuild.stand_in("Sprite", size * 0.9, colour))
		return
	var sprite := Sprite2D.new()
	sprite.name = "Sprite"
	sprite.texture = texture
	sprite.centered = false
	sprite.position = Vector2(-size.x * 0.5, -size.y)
	body.add_child(sprite)

# ---------------------------------------------------------------- on diamonds (T17.14)

## The picture of a pack's own asset on a diamond: one drawn for the isometric view with its
## `origin` (the middle of the diamond it stands on) on the origin, any other standing on it
## with the middle of its lower edge. Null when the project has no picture of its own.
static func _iso_picture(ctx: BuildContext, asset: Dictionary) -> Sprite2D:
	var texture := FarmBuild.first_frame(ctx, asset)
	if texture == null:
		return null
	var eff: Dictionary = ctx.catalog.effective(asset)
	var sprite := Sprite2D.new()
	sprite.name = "Sprite"
	sprite.texture = texture
	sprite.centered = false
	var origin := JsonUtil.to_array(eff.get("origin", []))
	if JsonUtil.to_str(eff.get("projection", "")) == "isometric" and origin.size() == 2:
		sprite.offset = -Vector2(JsonUtil.to_float(origin[0]), JsonUtil.to_float(origin[1]))
	else:
		sprite.position = Vector2(-texture.get_width() * 0.5, -texture.get_height())
	return sprite

## The cells a pack's own picture stands on in the isometric view: its `stands_on`, or one.
static func _iso_cells(ctx: BuildContext, asset: Dictionary) -> Vector2i:
	if asset.is_empty():
		return Vector2i.ONE
	var eff: Dictionary = ctx.catalog.effective(asset)
	if JsonUtil.to_str(eff.get("projection", "")) != "isometric":
		return Vector2i.ONE
	return MapGeo.entry_cells(eff)

## What blocks the `cells` a thing stands on, around the middle of the one nearest the camera.
static func _add_iso_shape(body: StaticBody2D, cells: Vector2i, footprint: Vector2i) -> void:
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var outline := ConvexPolygonShape2D.new()
	outline.points = RpgFarmIso.outline(1.0 - cells.x, 1.0 - cells.y, 1.0, 1.0, footprint)
	shape.shape = outline
	body.add_child(shape)

## The shipping bin of an isometric farm: it stands on the middle of its cell and blocks it.
static func _iso_bin(ctx: BuildContext, footprint: Vector2i) -> StaticBody2D:
	var tile := float(FarmBuild.tile(ctx))
	var asset := FarmBuild.bin_asset(ctx)
	var body := _body(BIN_NAME, FarmBuild.BIN)
	_add_iso_shape(body, _iso_cells(ctx, asset), footprint)
	var sprite := _iso_picture(ctx, asset)
	if sprite != null:
		body.add_child(sprite)
		return body
	var drawn := Node2D.new()
	drawn.name = "Sprite"
	drawn.add_child(RpgFarmIso.box("Crate", 0.18, 0.18, 0.82, 0.82, 0.0, tile * 0.55, BIN_COLOR, footprint))
	drawn.add_child(RpgFarmIso.box("Lid", 0.12, 0.12, 0.88, 0.88, tile * 0.55, tile * 0.1, BIN_COLOR.darkened(0.3), footprint))
	body.add_child(drawn)
	return body

## The bed of an isometric farm: its origin is the middle of the cell of its foot (the one of
## its cells nearest the camera), its head lies to the north, it blocks its cells, and the
## farmer wakes on the cell east of its foot unless the map recipe says another.
static func _iso_bed(ctx: BuildContext, footprint: Vector2i) -> StaticBody2D:
	var tile := float(FarmBuild.tile(ctx))
	var asset := FarmBuild.bed_asset(ctx)
	var sprite := _iso_picture(ctx, asset)
	var cells := _iso_cells(ctx, asset) if sprite != null else ISO_BED_CELLS
	var body := _body(BED_NAME, FarmBuild.BED)
	body.set("footprint", cells)
	body.set("wake_offset", RpgIso.step("e", footprint))
	_add_iso_shape(body, cells, footprint)
	if sprite != null:
		body.add_child(sprite)
		return body
	# the two halves sort apart, as an isometric object of two cells does
	var parts := RpgFarmIso.halves(body, cells, footprint)
	RpgFarmIso.add_box(parts, "Frame", 0.06, -0.94, 0.94, 0.94, 0.0, tile * 0.14, BED_WOOD, footprint)
	RpgFarmIso.add_box(parts, "Mattress", 0.12, -0.88, 0.88, 0.88, tile * 0.14, tile * 0.16, BED_COLOR, footprint)
	RpgFarmIso.add_box(parts, "Pillow", 0.22, -0.8, 0.78, -0.42, tile * 0.3, tile * 0.08, PILLOW, footprint)
	return body

# ---------------------------------------------------------------- on a map

## Where a thing stands whose lower edge lies on the lower edge of `cell`.
static func foot_of(cell: Vector2i, tile_px: int) -> Vector2:
	return Vector2(cell) * tile_px + Vector2(tile_px * 0.5, tile_px)
