class_name RpgLevels
extends Node2D
## Height on diamonds (T18.20): the levels of an isometric map whose height layers (the dock's
## *Add height layer*, a TileMapLayer with the meta `rpg_height`) stack blocks, storeys and
## ramps on its ground. Before, an actor walked through them as if the ground were flat.
##
## **Levels.** A cell is as high as the highest top of what stands on it: a layer's height and
## the `lift` of its tile (a block, a storey, a roof; a floor painted up there lifts nothing more);
## 0 on the ground. A ramp or a stair (the
## tile data `stack` "ramp:<from>:<to>:<side>", from the layer's height, rising towards `side`
## of the grid; a plain "ramp" rises from the layer's height by its `lift` towards n) is as high
## as its two ends and between them along its side. An actor has a level (0
## on the ground): its picture is drawn that many px up and sorts with the cell it stands on, as
## a placed thing on a raised cell does.
##
## **Blocking.** For each level there is a wall of diamonds, on a physics layer of its own
## (`FIRST_LAYER` on), around the cells that can be walked on at that level: the side of a block
## blocks an actor below it, and the edge of a raised area one that stands on it, except where a
## ramp leads down. A ramp is walked onto only at its two ends: its sides are walls. An actor's mask has the layer of its level (RpgActor asks `follow` each
## physics step), and a shot the layer of its shooter's.
##
## **The way.** `path` finds a way over the cells from one level to another, up and down the
## ramps (a villager's schedule and a chasing enemy ask it); `same_level` says whether a shot
## or a swing reaches (on the same level, or one below: it falls).
##
## The node is the child `Levels` of a map that has height layers, made by RpgMapRoot when the
## map is entered (`ensure`). A map without height layers has none, and nothing changes for it.

const NODE_NAME := "Levels"
const HEIGHT_META := "rpg_height"
## The physics layers of the levels: the lowest level the first. Eight at most; a map with more
## levels shares the last.
const FIRST_LAYER := 17
const MOST := 8
## What on a height layer raises nothing: it hangs on a wall or a storey's face, stands on a
## roof, or lies over another tile. Everything else does (a block, a storey, a roof, a ramp, and
## the ground painted on a height layer: a floor up there is a raised floor).
const NOT_LIFTING: Array[String] = ["on_wall", "on_storey", "on_roof", "overlay"]
## How far apart two levels may be and count as one (px): a shot reaches, an encounter starts.
const TOLERANCE := 4.0
## How many cells the way looks through at most.
const PATH_MOST := 4096

var map: Node = null
var footprint := Vector2i.ZERO
## The height of every raised cell (cells that are not here are on the ground, 0).
var tops := {}
## The ramps: cell -> [low, high, side] (px from the ground).
var ramps := {}
## The levels of the map, the ground first.
var levels: Array[int] = [0]
var _walls: Array[StaticBody2D] = []

## The levels of `map` (null when it has no height layer, or is no isometric map).
static func of(the_map: Node) -> RpgLevels:
	if the_map == null:
		return null
	return the_map.get_node_or_null(NODE_NAME) as RpgLevels

## The levels of the map `node` is on (a child `Levels` of it or of one of its parents), or null.
static func near(node: Node) -> RpgLevels:
	var at := node
	while at != null:
		var found := at.get_node_or_null(NODE_NAME)
		if found is RpgLevels:
			return found as RpgLevels
		at = at.get_parent()
	return null

## Gives `the_map` its levels when it has height layers on diamonds. Returns them, or null.
static func ensure(the_map: Node) -> RpgLevels:
	var existing := of(the_map)
	if existing != null:
		return existing
	if RpgIso.footprint_of(the_map) == Vector2i.ZERO or height_layers(the_map).is_empty():
		return null
	var made := RpgLevels.new()
	made.name = NODE_NAME
	the_map.add_child(made)
	made.build(the_map)
	return made

## The height layers of a map, as the dock marks them.
static func height_layers(the_map: Node) -> Array[TileMapLayer]:
	var out: Array[TileMapLayer] = []
	for node in the_map.find_children("*", "TileMapLayer", true, false):
		if node.has_meta(HEIGHT_META):
			out.append(node as TileMapLayer)
	return out

static func _data(layer: TileMapLayer, cell: Vector2i, key: String) -> Variant:
	var tile := layer.get_cell_tile_data(cell)
	if tile == null or layer.tile_set.get_custom_data_layer_by_name(key) == -1:
		return null
	return tile.get_custom_data(key)

## Reads the heights of `the_map` and makes the walls of its levels.
func build(the_map: Node) -> void:
	map = the_map
	footprint = RpgIso.footprint_of(map)
	tops.clear()
	ramps.clear()
	var seen := {0: true}
	for layer in height_layers(map):
		var base := RpgUtil.to_int(layer.get_meta(HEIGHT_META, 0))
		for cell in layer.get_used_cells():
			var said := RpgUtil.to_str(_data(layer, cell, "stack")).split(":")
			var stack := said[0]
			if NOT_LIFTING.has(stack):
				continue
			var lift := RpgUtil.to_int(_data(layer, cell, "lift"))
			if stack == "ramp":
				var ends := said.size() == 4
				var low := base + (said[1].to_int() if ends else 0)
				var high := base + (said[2].to_int() if ends else lift)
				var side := said[3] if ends else "n"
				ramps[cell] = [low, high, side if RpgIso.STEPS.has(side) else "n"]
				seen[low] = true
				seen[high] = true
				continue
			var top := base + lift
			if top > RpgUtil.to_int(tops.get(cell, 0)):
				tops[cell] = top
				seen[top] = true
	levels.clear()
	for level: int in seen:
		levels.append(level)
	levels.sort()
	_make_walls()

# ------------------------------------------------------------------ what is where

## How high the cell is (a ramp: its high end).
func top_of(cell: Vector2i) -> int:
	if ramps.has(cell):
		var ramp: Array = ramps[cell]
		return RpgUtil.to_int(ramp[1])
	return RpgUtil.to_int(tops.get(cell, 0))

## True when an actor at `level` can stand on `cell`: it is that high, or a ramp with an end there.
func walkable(cell: Vector2i, level: int) -> bool:
	if ramps.has(cell):
		var ramp: Array = ramps[cell]
		return RpgUtil.to_int(ramp[0]) == level or RpgUtil.to_int(ramp[1]) == level
	return RpgUtil.to_int(tops.get(cell, 0)) == level

## How high the ground is at a point of the world: the cell's height, on a ramp between its ends.
func height_at(world: Vector2) -> float:
	var cell := RpgIso.cell_at(map, world)
	if not ramps.has(cell):
		return float(top_of(cell))
	var ramp: Array = ramps[cell]
	var layer := RpgIso.ground_layer(map)
	var local := RpgEncounterZone.to_local_of(layer, world) if layer != null else world
	var grid := RpgIso.grid_point(local, footprint) - Vector2(cell) - Vector2(0.5, 0.5)
	var up: Vector2i = RpgIso.STEPS[RpgUtil.to_str(ramp[2])]
	var along := clampf(grid.dot(Vector2(up)) + 0.5, 0.0, 1.0)
	return lerpf(RpgUtil.to_float(ramp[0]), RpgUtil.to_float(ramp[1]), along)

## The level an actor at a point of the world is on: the nearest of the map's levels.
func level_near(height: float) -> int:
	var best := levels[0]
	for level in levels:
		if absf(level - height) < absf(best - height):
			best = level
	return best

## The physics layer (1..32) of a level.
func layer_of(level: int) -> int:
	return FIRST_LAYER + mini(maxi(0, levels.find(level)), MOST - 1)

## Every level's physics layers as a mask.
func all_layers_mask() -> int:
	var mask := 0
	for i in mini(levels.size(), MOST):
		mask |= 1 << (FIRST_LAYER + i - 1)
	return mask

## True when what is at `at_level` reaches what is at `target_level`: on the same level, or
## below it (a shot falls; a swing reaches down).
static func reaches(at_level: float, target_level: float) -> bool:
	return target_level <= at_level + TOLERANCE

## True when two actors stand on one level (an encounter starts only then).
static func same_level(a: Node, b: Node) -> bool:
	return absf(level_of(a) - level_of(b)) <= TOLERANCE

## The level of a node: an actor's own, else 0.
static func level_of(node: Node) -> float:
	if node != null and node.has_meta(&"rpg_level"):
		return RpgUtil.to_float(node.get_meta(&"rpg_level"))
	return 0.0

# ------------------------------------------------------------------ actors

## Keeps an actor on its level: how high the ground under it is (smoothly up a ramp), its
## picture drawn that much higher, and the wall of its level in its mask. Called each physics
## step by RpgActor.
func follow(body: CollisionObject2D, visual: Node2D) -> void:
	var height := height_at(RpgUtil.world_position(body))
	var level := level_near(height)
	var before := RpgUtil.to_float(body.get_meta(&"rpg_level", 0.0))
	if not body.has_meta(&"rpg_level"):
		body.set_meta(&"rpg_mask", body.collision_mask)
	body.set_meta(&"rpg_level", height)
	body.set_meta(&"rpg_on_level", level)
	body.collision_mask = (RpgUtil.to_int(body.get_meta(&"rpg_mask")) & ~all_layers_mask()) | (1 << (layer_of(level) - 1))
	if visual != null:
		if not visual.has_meta(&"rpg_base_y"):
			visual.set_meta(&"rpg_base_y", visual.position.y)
		visual.position.y = RpgUtil.to_float(visual.get_meta(&"rpg_base_y")) - height
	if absf(before - height) > 0.01:
		body.set_meta(&"rpg_moved_level", true)

# ------------------------------------------------------------------ the walls

## For each level, a body on its layer with a diamond on every cell beside the cells that can be
## walked on at that level that cannot (the side of a block, the edge of a raised area).
func _make_walls() -> void:
	for wall in _walls:
		wall.queue_free()
	_walls.clear()
	var ground := RpgIso.ground_layer(map)
	if ground == null:
		return
	var walkable_cells: Array[Vector2i] = []
	var all := {}
	for cell in ground.get_used_cells():
		all[cell] = true
	for cell: Vector2i in tops:
		all[cell] = true
	for cell: Vector2i in ramps:
		all[cell] = true
	for cell: Vector2i in all:
		walkable_cells.append(cell)
	var shape := RpgIso.cell_shape(footprint)
	for level in levels:
		var body := StaticBody2D.new()
		body.name = "Level%d" % level
		body.collision_layer = 1 << (layer_of(level) - 1)
		body.collision_mask = 0
		var blocked := {}
		for cell in walkable_cells:
			if not walkable(cell, level):
				continue
			for dy in range(-1, 2):
				for dx in range(-1, 2):
					var near := cell + Vector2i(dx, dy)
					if not blocked.has(near) and not walkable(near, level) and (all.has(near) or level > 0):
						blocked[near] = true
		for cell: Vector2i in blocked:
			var holder := CollisionShape2D.new()
			holder.shape = shape
			holder.position = RpgIso.cell_position(map, cell) - RpgUtil.world_position(self)
			body.add_child(holder)
		_ramp_sides(body)
		add_child(body)
		_walls.append(body)

## A ramp is gone up and down by its ends: its two other sides are walls on every level (a thin
## edge, so the cells beside it are walked as before).
func _ramp_sides(body: StaticBody2D) -> void:
	for cell: Vector2i in ramps:
		var ramp: Array = ramps[cell]
		var up := RpgIso.SIDES.find(RpgUtil.to_str(ramp[2]))
		var corners := RpgIso.diamond(cell, footprint)
		var shift := RpgIso.cell_position(map, cell) - RpgIso.cell_to_screen(cell, footprint) - RpgUtil.world_position(self)
		# the edge of side i runs from corner i to corner i + 1 (n: top to right, e: right to bottom, ...)
		for side: int in [(up + 1) % 4, (up + 3) % 4]:
			var edge := SegmentShape2D.new()
			edge.a = corners[side] + shift
			edge.b = corners[(side + 1) % 4] + shift
			var holder := CollisionShape2D.new()
			holder.shape = edge
			body.add_child(holder)

## The cells a level's wall stands on (tests).
func wall_cells(level: int) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	var index := levels.find(level)
	if index < 0 or index >= _walls.size():
		return out
	for holder in _walls[index].get_children():
		if (holder as CollisionShape2D).shape is SegmentShape2D:
			continue  # the side of a ramp
		out.append(RpgIso.cell_at(map, RpgUtil.world_position(holder as Node2D)))
	return out

# ------------------------------------------------------------------ the way

## True when one step leads from `from` (at `level`) to its neighbour `to`, and the level there.
## -1 when it does not: a flat cell of another height, or off the map.
func _step_level(from: Vector2i, level: int, to: Vector2i) -> int:
	if walkable(to, level):
		if ramps.has(to):
			return level
		return level
	if ramps.has(from):  # off the other end of a ramp
		var ramp: Array = ramps[from]
		for end: int in [RpgUtil.to_int(ramp[0]), RpgUtil.to_int(ramp[1])]:
			if end != level and walkable(to, end):
				return end
	return -1

## A way over the cells from `from_world` to `to_world` that keeps to the levels (up and down
## the ramps): the middles of its cells, the last the target itself. Empty when there is none.
## `free` (a Callable taking a cell) can rule out cells (the navigation's own).
func path(from_world: Vector2, to_world: Vector2, free: Callable = Callable()) -> PackedVector2Array:
	var start := RpgIso.cell_at(map, from_world)
	var goal := RpgIso.cell_at(map, to_world)
	var start_level := level_near(height_at(from_world))
	var goal_level := level_near(height_at(to_world))
	var ground := RpgIso.ground_layer(map)
	var key := func(cell: Vector2i, level: int) -> Vector3i: return Vector3i(cell.x, cell.y, level)
	var came := {key.call(start, start_level): null}
	var queue: Array[Vector3i] = [key.call(start, start_level)]
	var found: Variant = null
	var looked := 0
	while not queue.is_empty() and looked < PATH_MOST:
		var at: Vector3i = queue.pop_front()
		looked += 1
		var cell := Vector2i(at.x, at.y)
		if cell == goal and (at.z == goal_level or ramps.has(goal)):
			found = at
			break
		for side: String in RpgIso.SIDES:
			var next: Vector2i = cell + RpgIso.STEPS[side]
			if ground != null and ground.get_cell_source_id(next) == -1 and not tops.has(next) and not ramps.has(next):
				continue
			if free.is_valid() and next != goal and not free.call(next):
				continue
			var level := _step_level(cell, at.z, next)
			if level < 0:
				continue
			var k: Vector3i = key.call(next, level)
			if came.has(k):
				continue
			came[k] = at
			queue.append(k)
	var out := PackedVector2Array()
	if found == null:
		return out
	var cells: Array[Vector2i] = []
	var step: Variant = found
	while step != null:
		var v: Vector3i = step
		cells.push_front(Vector2i(v.x, v.y))
		step = came[v]
	for i in range(1, cells.size() - 1):
		out.append(RpgIso.cell_position(map, cells[i]))
	out.append(to_world)
	return out
