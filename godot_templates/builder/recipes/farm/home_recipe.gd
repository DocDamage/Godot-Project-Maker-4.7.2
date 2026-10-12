extends RefCounted
## The shipping bin and the bed of a farm (T17.08):
## * generated/scenes/farm/shipping_bin.tscn, an RpgShippingBin, and generated/scenes/farm/bed.tscn,
##   an RpgBed: a solid thing of the map that is used with `interact`, with the picture of the
##   packs (FarmBuild.bin_asset, bed_asset), else the one of the drawn farm kit, else a drawn box.
## * `build_bin(ctx)` and `build_bed(ctx)` make the nodes: the farm's map recipe (T17.06) calls
##   them, or instances the two scenes, and puts them where its plan says. The origin of both is
##   the middle of their lower edge; the bed says which cells it lies on (`footprint`) and where
##   the farmer wakes (`wake_offset`, the cell under its foot unless the recipe sets another).
## * `place_stand_ins`, which field_recipe.augment_map calls. **A stand-in until T17.06**, like
##   the plot: on the top-down starter map the bin stands beside the plot and the bed beside the
##   place a new game starts at, out of doors. The planned farm places both itself.

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
## How far from the place a new game starts at the stand-in bed is looked for, in cells.
const BED_REACH := 12

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

# ---------------------------------------------------------------- the stand-in map (until T17.06)

## What the starter map's hash holds of the placement.
static func map_hash() -> Dictionary:
	return {"v": RECIPE_VERSION, "reach": BED_REACH}

## Where a thing stands whose lower edge lies on the lower edge of `cell`.
static func foot_of(cell: Vector2i, tile_px: int) -> Vector2:
	return Vector2(cell) * tile_px + Vector2(tile_px * 0.5, tile_px)

## Puts the bin beside the plot and the bed beside the spawn of a starter map that is being
## built. `entities` is where the things of the map stand, `blocked` the cells nothing may lie
## on (field_recipe.blocked_cells), `plot` the plot (an empty rectangle for none).
static func place_stand_ins(root: Node2D, entities: Node, layout: Dictionary, blocked: Dictionary, plot: Rect2i, tile_px: int) -> void:
	var size: Vector2i = layout["size"]
	var spawn: Vector2i = layout["spawn"]
	var taken := blocked.duplicate()
	for y in range(plot.position.y, plot.end.y):
		for x in range(plot.position.x, plot.end.x):
			taken[Vector2i(x, y)] = true
	var bin_cell := bin_cell_for(plot, size, taken)
	if bin_cell.x < 0:
		print("[rpggen] INFO starter_map: no room for the shipping bin")
	else:
		var bin := SceneUtil.instance(BIN_SCENE) as Node2D
		if bin != null:
			bin.position = foot_of(bin_cell, tile_px)
			entities.add_child(bin)
			bin.owner = root
			taken[bin_cell] = true
	var bed := SceneUtil.instance(BED_SCENE) as Node2D
	if bed == null:
		return
	var footprint: Vector2i = bed.get("footprint")
	var bed_cell := bed_cell_for(spawn, size, taken, footprint)
	if bed_cell.x < 0:
		print("[rpggen] INFO starter_map: no room for the bed")
		bed.free()
		return
	# its foot is the lowest row of its cells, and the middle of their width
	bed.position = Vector2(bed_cell.x * tile_px + footprint.x * tile_px * 0.5, (bed_cell.y + 1) * tile_px)
	entities.add_child(bed)
	bed.owner = root

static func _inside(cell: Vector2i, size: Vector2i) -> bool:
	return cell.x >= 1 and cell.y >= 1 and cell.x < size.x - 1 and cell.y < size.y - 1

## The cell of the bin: the first free one along the left side of the plot, then the right
## side, then below it (never above its first cell, where the farmer stands to work it).
## (-1, -1) when there is none, or no plot.
static func bin_cell_for(plot: Rect2i, size: Vector2i, taken: Dictionary) -> Vector2i:
	if plot.size == Vector2i.ZERO:
		return Vector2i(-1, -1)
	var candidates: Array[Vector2i] = []
	for y in range(plot.position.y, plot.end.y):
		candidates.append(Vector2i(plot.position.x - 1, y))
	for y in range(plot.position.y, plot.end.y):
		candidates.append(Vector2i(plot.end.x, y))
	for x in range(plot.position.x, plot.end.x):
		candidates.append(Vector2i(x, plot.end.y))
	for cell in candidates:
		if _inside(cell, size) and not taken.has(cell):
			return cell
	return Vector2i(-1, -1)

## The lower left cell of the bed: the nearest to the spawn where the cells of the bed and the
## row under it (where the farmer wakes) are free; of two as near, the upper, then the left one.
## (-1, -1) when there is none within BED_REACH.
static func bed_cell_for(spawn: Vector2i, size: Vector2i, taken: Dictionary, footprint: Vector2i) -> Vector2i:
	var best := Vector2i(-1, -1)
	var best_distance := -1
	for y in range(spawn.y - BED_REACH, spawn.y + BED_REACH + 1):
		for x in range(spawn.x - BED_REACH, spawn.x + BED_REACH + 1):
			var cell := Vector2i(x, y)
			var distance := absi(x - spawn.x) + absi(y - spawn.y)
			if best_distance >= 0 and distance >= best_distance:
				continue
			if _bed_fits(cell, size, taken, footprint):
				best = cell
				best_distance = distance
	return best

static func _bed_fits(cell: Vector2i, size: Vector2i, taken: Dictionary, footprint: Vector2i) -> bool:
	for dx in footprint.x:
		for dy in range(-footprint.y + 1, 2):  # its rows, and the row under its foot
			var at := cell + Vector2i(dx, dy)
			if not _inside(at, size) or taken.has(at):
				return false
	return true
