class_name RpgIso
extends RefCounted
## The arithmetic of the isometric view (T17.14): where a cell of a map is on the screen, which
## cell a point lies in, what is drawn in front of what, and where the pad moves an actor.
##
## A map is planned on cells (x, y), x east and y south, whatever the view. In the isometric view
## a cell is a diamond `footprint` wide and high (the diamond of the pack: 60 x 34, 180 x 104,
## never assumed 2:1) laid out as Godot lays out TILE_LAYOUT_DIAMOND_DOWN: the middle of the cell
## (x, y) is at ((x - y + 1) * w / 2, (x + y + 1) * h / 2), so the cell (0, 0) is the top corner
## of the map, east runs down and to the right and south down and to the left. The four sides of
## a diamond are, by the grid: n the upper right, e the lower right, s the lower left, w the
## upper left.
##
## The first part is pure arithmetic, the same as rpggen/core/iso_math.py: both are tested
## against one table of cases (tests/unit/iso_math_cases.json). The second part asks a map: it
## answers for a map of squares too, so what is written with it holds in both views.

const SIDES: Array[String] = ["n", "e", "s", "w"]
## The neighbour of a cell on each side, by the grid.
const STEPS: Dictionary = {"n": Vector2i(0, -1), "e": Vector2i(1, 0), "s": Vector2i(0, 1), "w": Vector2i(-1, 0)}
## The side a facing looks to when nothing says more: a quarter turn clockwise brings each of the
## four directions of the screen onto the side of the diamond next to it.
const FACING_SIDES: Dictionary = {"up": "n", "right": "e", "down": "s", "left": "w"}
const CONTROLS_SCREEN := "screen"
const CONTROLS_GRID := "grid"
## The project setting the builder writes for an isometric project (`iso_controls` of the config).
const CONTROLS_SETTING := "rpg/iso_controls"

# ---------------------------------------------------------------- the arithmetic

## The middle of the cell on the screen (in the px of the map's layer).
static func cell_to_screen(cell: Vector2i, footprint: Vector2i) -> Vector2:
	return Vector2((cell.x - cell.y + 1) * footprint.x / 2.0, (cell.x + cell.y + 1) * footprint.y / 2.0)

## A point of the screen in the grid's own coordinates: the cell (cx, cy) is the square from
## (cx, cy) to (cx + 1, cy + 1).
static func grid_point(at: Vector2, footprint: Vector2i) -> Vector2:
	var a := 2.0 * at.x / footprint.x - 1.0
	var b := 2.0 * at.y / footprint.y
	return Vector2((a + b) / 2.0, (b - a) / 2.0)

## The cell a point of the screen lies in.
static func screen_to_cell(at: Vector2, footprint: Vector2i) -> Vector2i:
	var g := grid_point(at, footprint)
	return Vector2i(floori(g.x), floori(g.y))

## The sort key of a cell: the y of its middle. A greater one is drawn later, in front.
static func depth(cell: Vector2i, footprint: Vector2i) -> float:
	return (cell.x + cell.y + 1) * footprint.y / 2.0

## The corners of a cell on the screen: the top, the right, the bottom, the left.
static func diamond(cell: Vector2i, footprint: Vector2i) -> PackedVector2Array:
	var at := cell_to_screen(cell, footprint)
	var half := Vector2(footprint) / 2.0
	return PackedVector2Array([at + Vector2(0, -half.y), at + Vector2(half.x, 0), at + Vector2(0, half.y), at + Vector2(-half.x, 0)])

## The four neighbours of a cell, in the order n, e, s, w.
static func neighbours(cell: Vector2i) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for side in SIDES:
		var by: Vector2i = STEPS[side]
		out.append(cell + by)
	return out

## How far the middle of the neighbour on `side` is on the screen.
static func step(side: String, footprint: Vector2i) -> Vector2:
	var by: Vector2i = STEPS.get(side, Vector2i.ZERO)
	return Vector2((by.x - by.y) * footprint.x / 2.0, (by.x + by.y) * footprint.y / 2.0)

## The length of one step from a cell to its neighbour, in whole px: what a recipe or the runtime
## takes where a square map has its tile size (a reach, a spacing, a range).
static func unit(footprint: Vector2i) -> int:
	return maxi(1, floori(Vector2(footprint.x / 2.0, footprint.y / 2.0).length() + 0.5))

## The side of the diamond a direction of the screen points to. The four neighbours lie in the
## four quadrants of the screen; a direction along an axis goes to the side a quarter turn
## clockwise brings it to (up to n, right to e, down to s, left to w), and no direction at all is
## s (an actor that has not moved faces down).
static func side_of(dir: Vector2) -> String:
	if dir.x > 0 and dir.y < 0:
		return "n"
	if dir.x > 0 and dir.y > 0:
		return "e"
	if dir.x < 0 and dir.y > 0:
		return "s"
	if dir.x < 0 and dir.y < 0:
		return "w"
	if dir.y < 0:
		return "n"
	if dir.x > 0:
		return "e"
	if dir.x < 0:
		return "w"
	return "s"

## The one of four facings a direction of the screen is nearest to (the vertical wins a tie):
## RpgAnimationDriver.dir_to_facing.
static func facing_of(dir: Vector2) -> String:
	if absf(dir.x) > absf(dir.y):
		return "right" if dir.x > 0.0 else "left"
	return "down" if dir.y >= 0.0 else "up"

## The side an actor faces: where it last went (`look`) while that still agrees with its facing,
## else the side of the facing alone (a spawn point turned it).
static func faced_side(facing: String, look: Vector2) -> String:
	if look != Vector2.ZERO and facing_of(look) == facing:
		return side_of(look)
	return str(FACING_SIDES.get(facing, "s"))

## The cell in front of an actor that stands on `cell`.
static func faced_cell(cell: Vector2i, facing: String, look: Vector2) -> Vector2i:
	var by: Vector2i = STEPS[faced_side(facing, look)]
	return cell + by

## Where the pad moves an actor on the screen. "screen": up is up. "grid": the four directions
## follow the diamond's axes (up to n, right to e, down to s, left to w), so one direction held
## walks along a row of cells. Never longer than 1.
static func pad_vector(input: Vector2, controls: String, footprint: Vector2i) -> Vector2:
	if controls != CONTROLS_GRID:
		return input
	var half := Vector2(footprint.x / 2.0, footprint.y / 2.0)
	var length := half.length()
	if length <= 0.0:
		return Vector2.ZERO
	var east := Vector2(half.x, half.y) / length
	var south := Vector2(-half.x, half.y) / length
	var out := input.x * east + input.y * south
	if out.length() > 1.0:
		out = out / out.length()
	return out

## The neighbour one press of the pad steps to (the stronger axis wins, the vertical a tie): by
## the grid with "grid" controls, and with "screen" controls the side the direction of the screen
## points to. "" for no press.
static func pad_side(input: Vector2, controls: String) -> String:
	if input == Vector2.ZERO:
		return ""
	var dir := Vector2(0.0, 1.0 if input.y > 0.0 else -1.0)
	if absf(input.x) > absf(input.y):
		dir = Vector2(1.0 if input.x > 0.0 else -1.0, 0.0)
	if controls == CONTROLS_GRID:
		return str(FACING_SIDES[facing_of(dir)])
	return side_of(dir)

## The rectangle around a map of `size` cells whose first cell is (0, 0).
static func bounds(size: Vector2i, footprint: Vector2i) -> Rect2:
	return Rect2(-(size.y - 1) * footprint.x / 2.0, 0.0, (size.x + size.y) * footprint.x / 2.0, (size.x + size.y) * footprint.y / 2.0)

## How a thing that stands on the cells of `cells` sorts: [split x, key of the left half, key of
## the right half]. The halves meet at the x of the corner nearest the camera; the left one sorts
## by the y of the left corner of what it stands on, the right one by the y of the right corner.
## On a square of cells the two are one line, the one through the middle.
static func sort_keys(cells: Rect2i, footprint: Vector2i) -> Array[float]:
	var split := (cells.position.x + cells.size.x - (cells.position.y + cells.size.y) + 1) * footprint.x / 2.0
	var left := (cells.position.x + cells.position.y + cells.size.y) * footprint.y / 2.0
	var right := (cells.position.x + cells.size.x + cells.position.y) * footprint.y / 2.0
	return [split, left, right]

## Whether a point of the ground is in front of a thing on the cells of `cells` (1), behind it
## (-1) or on it or beside it, where neither hides the other (0). By the grid: in front is south
## or east of all of it, behind is north or west of all of it.
static func in_front(at: Vector2, cells: Rect2i, footprint: Vector2i) -> int:
	var g := grid_point(at, footprint)
	var ahead := g.y >= cells.end.y or g.x >= cells.end.x
	var back := g.y <= cells.position.y or g.x <= cells.position.x
	if ahead and not back:
		return 1
	if back and not ahead:
		return -1
	return 0

# ---------------------------------------------------------------- asking a map

## The first tile layer of a map that has a tile set (its Ground), or null.
static func ground_layer(map: Node) -> TileMapLayer:
	if map == null:
		return null
	if map is TileMapLayer and (map as TileMapLayer).tile_set != null:
		return map as TileMapLayer
	for node in map.find_children("*", "TileMapLayer", true, false):
		var layer := node as TileMapLayer
		if layer.tile_set != null:
			return layer
	return null

## True for a tile set of diamonds.
static func is_iso(tile_set: TileSet) -> bool:
	return tile_set != null and tile_set.tile_shape == TileSet.TILE_SHAPE_ISOMETRIC

## The diamond of an isometric map; Vector2i.ZERO for a map of squares (or without tiles).
static func footprint_of(map: Node) -> Vector2i:
	var layer := ground_layer(map)
	if layer == null or not is_iso(layer.tile_set):
		return Vector2i.ZERO
	return layer.tile_set.tile_size

## The length of one step of a map in px: the tile of a map of squares, `unit` of the diamond of
## an isometric one, 16 for a map without tiles.
static func map_unit(map: Node) -> int:
	var layer := ground_layer(map)
	if layer == null:
		return 16
	if is_iso(layer.tile_set):
		return unit(layer.tile_set.tile_size)
	return layer.tile_set.tile_size.x

## The cell of a map a point of the world lies in (both views: the layer is asked).
static func cell_at(map: Node, world: Vector2) -> Vector2i:
	var layer := ground_layer(map)
	if layer == null:
		return Vector2i(floori(world.x / 16.0), floori(world.y / 16.0))
	return layer.local_to_map(RpgEncounterZone.to_local_of(layer, world))

## The middle of a cell of a map in the world (both views).
static func cell_position(map: Node, cell: Vector2i) -> Vector2:
	var layer := ground_layer(map)
	if layer == null:
		return (Vector2(cell) + Vector2(0.5, 0.5)) * 16.0
	var local := layer.map_to_local(cell)
	if layer.is_inside_tree():
		return layer.to_global(local)
	return RpgUtil.world_position(layer) + local

## How the pad moves an actor on an isometric map: "screen" (up is up) or "grid" (the four
## directions follow the diamond's axes). The builder writes the project setting.
static func controls() -> String:
	var value := str(ProjectSettings.get_setting(CONTROLS_SETTING, CONTROLS_SCREEN))
	return CONTROLS_GRID if value == CONTROLS_GRID else CONTROLS_SCREEN

## Where the pad's `input` moves an actor on `map`: itself on a map of squares.
static func move_vector(map: Node, input: Vector2) -> Vector2:
	var footprint := footprint_of(map)
	if footprint == Vector2i.ZERO:
		return input
	return pad_vector(input, controls(), footprint)

## The cell in front of an actor on `map`, by its facing and where it last went. On a map of
## squares it is the cell the facing points to.
static func cell_ahead(map: Node, world: Vector2, facing: String, look: Vector2 = Vector2.ZERO) -> Vector2i:
	var cell := cell_at(map, world)
	if footprint_of(map) == Vector2i.ZERO:
		var by: Vector2i = STEPS[str(FACING_SIDES.get(facing, "s"))]
		return cell + by
	return faced_cell(cell, facing, look)

## The direction on the screen an actor on `map` reaches to (its interaction, a tool): the
## facing itself on a map of squares and with "screen" controls, and with "grid" controls the
## way to the neighbour it faces. A unit vector.
static func reach_dir(map: Node, facing: String, look: Vector2 = Vector2.ZERO) -> Vector2:
	var footprint := footprint_of(map)
	if footprint != Vector2i.ZERO and controls() == CONTROLS_GRID:
		return step(faced_side(facing, look), footprint).normalized()
	match facing:
		"up":
			return Vector2.UP
		"left":
			return Vector2.LEFT
		"right":
			return Vector2.RIGHT
	return Vector2.DOWN

## The rectangle around the painted cells `cells` of a layer, in the layer's px: squares or
## diamonds.
static func used_rect(layer: TileMapLayer, cells: Rect2i) -> Rect2:
	var tile := Vector2(layer.tile_set.tile_size)
	if not is_iso(layer.tile_set):
		return Rect2(Vector2(cells.position) * tile, Vector2(cells.size) * tile)
	var rect := bounds(cells.size, layer.tile_set.tile_size)
	rect.position += cell_to_screen(cells.position, layer.tile_set.tile_size) - cell_to_screen(Vector2i.ZERO, layer.tile_set.tile_size)
	return rect
