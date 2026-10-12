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

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const FarmBuild := preload("farm_build.gd")

const OUT_DIR := "res://generated/scenes/farm/"
const BIN_SCENE := OUT_DIR + "shipping_bin.tscn"
const BED_SCENE := OUT_DIR + "bed.tscn"
const BIN_NAME := "ShippingBin"
const BED_NAME := "Bed"
const BIN_COLOR := Color(0.55, 0.36, 0.2)
const BED_COLOR := Color(0.35, 0.45, 0.75)

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([BIN_SCENE, BED_SCENE])

func input_hash(ctx: BuildContext) -> String:
	var art := {}
	for entry: Array in [["bin", FarmBuild.bin_asset(ctx)], ["bed", FarmBuild.bed_asset(ctx)]]:
		var asset: Dictionary = entry[1]
		art[entry[0]] = {"sha256": asset.get("sha256", ""), "eff": ctx.catalog.effective(asset) if not asset.is_empty() else {}}
	return ctx.stable_hash({"v": RECIPE_VERSION, "tile": FarmBuild.tile(ctx), "art": art})

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

# ---------------------------------------------------------------- on a map

## Where a thing stands whose lower edge lies on the lower edge of `cell`.
static func foot_of(cell: Vector2i, tile_px: int) -> Vector2:
	return Vector2(cell) * tile_px + Vector2(tile_px * 0.5, tile_px)
