class_name RpgFarmIso
extends RefCounted
## What the things of an isometric farm are made of (T17.14): the diamond a thing blocks or is
## found on, and boxes that stand on a diamond, for what nobody drew. The farm's recipes draw
## their stand-ins with it when the map is isometric (a fence, a tree, the bed, the bin, a
## building), and so does the game for what it makes itself (the trough of an animal house).
## Seen from above the same things are flat rectangles, as they were before.
##
## A place on a cell is given in the cell's own coordinates: `u` east and `v` south, each from 0
## to 1 across the cell, so (0, 0) is the top corner of its diamond, (1, 1) the bottom one and
## (0.5, 0.5) its middle. Values outside 0 to 1 lie on the neighbouring cells (a bed of two
## cells, a house of six). `point` turns such a place into px from the middle of the cell.

## A place of a cell in px from the middle of the cell (IsoTileset.on_diamond).
static func point(u: float, v: float, footprint: Vector2i) -> Vector2:
	return Vector2((u - v) * footprint.x / 2.0, (u + v - 1.0) * footprint.y / 2.0)

## The diamond of a cell around its middle, `scale` of its size: the top, the right, the bottom
## and the left corner.
static func diamond(footprint: Vector2i, scale: float = 1.0) -> PackedVector2Array:
	var half := Vector2(footprint) * 0.5 * scale
	return PackedVector2Array([Vector2(0.0, -half.y), Vector2(half.x, 0.0), Vector2(0.0, half.y), Vector2(-half.x, 0.0)])

## The diamond as a collision shape: what blocks a cell, or what `interact` finds on it.
static func diamond_shape(footprint: Vector2i, scale: float = 1.0) -> ConvexPolygonShape2D:
	var shape := ConvexPolygonShape2D.new()
	shape.points = diamond(footprint, scale)
	return shape

## The outline of the cells from (u0, v0) to (u1, v1), in px from the middle of the cell (0, 0)
## to (1, 1): the top, the right, the bottom and the left corner.
static func outline(u0: float, v0: float, u1: float, v1: float, footprint: Vector2i) -> PackedVector2Array:
	return PackedVector2Array([point(u0, v0, footprint), point(u1, v0, footprint), point(u1, v1, footprint), point(u0, v1, footprint)])

## The three faces of a box one can see: its base is the cells from (u0, v0) to (u1, v1), its
## underside `lift` px above the ground, and it is `height` px high. `{top, left, right}`, each
## a polygon in px from the middle of the cell: the left face is the one that looks south, the
## right one the one that looks east.
static func box_faces(u0: float, v0: float, u1: float, v1: float, lift: float, height: float, footprint: Vector2i) -> Dictionary:
	var base := outline(u0, v0, u1, v1, footprint)
	var low := Vector2(0.0, -lift)
	var high := Vector2(0.0, -lift - height)
	return {
		"top": PackedVector2Array([base[0] + high, base[1] + high, base[2] + high, base[3] + high]),
		"left": PackedVector2Array([base[3] + high, base[2] + high, base[2] + low, base[3] + low]),
		"right": PackedVector2Array([base[2] + high, base[1] + high, base[1] + low, base[2] + low]),
	}

## The colours of the three faces of a box of `colour`: lit from above, the east face in shade.
static func shades(colour: Color) -> Dictionary:
	return {"top": colour.lightened(0.18), "left": colour, "right": colour.darkened(0.22)}

## A box as a node: three Polygon2D (`Left`, `Right`, `Top`) under a Node2D called `node_name`.
static func box(node_name: String, u0: float, v0: float, u1: float, v1: float, lift: float, height: float, colour: Color, footprint: Vector2i) -> Node2D:
	var node := Node2D.new()
	node.name = node_name
	var faces := box_faces(u0, v0, u1, v1, lift, height, footprint)
	var colours := shades(colour)
	for face: String in ["left", "right", "top"]:
		var polygon: PackedVector2Array = faces[face]
		var shade: Color = colours[face]
		var part := Polygon2D.new()
		part.name = face.capitalize()
		part.polygon = polygon
		part.color = shade
		node.add_child(part)
	return node

## The part of a convex polygon left of the line x = `at` (`keep_left`) or right of it.
static func clip_x(polygon: PackedVector2Array, at: float, keep_left: bool) -> PackedVector2Array:
	var out := PackedVector2Array()
	var count := polygon.size()
	for i in count:
		var a := polygon[i]
		var b := polygon[(i + 1) % count]
		var a_in := a.x <= at if keep_left else a.x >= at
		var b_in := b.x <= at if keep_left else b.x >= at
		if a_in:
			_append_new(out, a)
		if a_in != b_in and not is_equal_approx(a.x, b.x):
			_append_new(out, a.lerp(b, (at - a.x) / (b.x - a.x)))
	if out.size() > 1 and out[0].is_equal_approx(out[out.size() - 1]):
		out.remove_at(out.size() - 1)
	return out

## Appends a point unless it is the one that was appended last.
static func _append_new(points: PackedVector2Array, at: Vector2) -> void:
	if points.is_empty() or not points[points.size() - 1].is_equal_approx(at):
		points.append(at)

## A thing of several cells is drawn in two halves that sort apart, as an isometric object of the
## packs is (object_scenes_recipe.gd, RpgIso.sort_keys): `root` stands on the middle of the cell
## of its `cells` nearest the camera, and gets the children `Left` and `Right`, which lie on the
## lines the left and the right corner of what it stands on sort by. `add_face` then puts every
## polygon into the half it belongs to. Returns `{left, right}`.
static func halves(root: Node2D, cells: Vector2i, footprint: Vector2i) -> Dictionary:
	root.y_sort_enabled = true
	var out := {}
	var lines := {"left": (1 - cells.x) * footprint.y / 2.0, "right": (1 - cells.y) * footprint.y / 2.0}
	for side: String in ["left", "right"]:
		var line: float = lines[side]
		var half := Node2D.new()
		half.name = side.capitalize()
		half.position = Vector2(0.0, line)
		root.add_child(half)
		out[side] = half
	return out

## Adds a polygon (px from the middle of the nearest cell) to the two halves of `halves`: what
## lies left of the corner nearest the camera to the left one, the rest to the right one.
static func add_face(parts: Dictionary, face_name: String, polygon: PackedVector2Array, colour: Color) -> void:
	for side: String in ["left", "right"]:
		var half: Node2D = parts[side]
		var clipped := clip_x(polygon, 0.0, side == "left")
		if clipped.size() < 3:
			continue
		var moved := PackedVector2Array()
		for at in clipped:
			moved.append(at - half.position)
		var part := Polygon2D.new()
		part.name = face_name
		part.polygon = moved
		part.color = colour
		half.add_child(part)

## Adds the three faces of a box to the two halves of `halves`, each face under the name
## `<box_name><Face>`.
static func add_box(parts: Dictionary, box_name: String, u0: float, v0: float, u1: float, v1: float, lift: float, height: float, colour: Color, footprint: Vector2i) -> void:
	var faces := box_faces(u0, v0, u1, v1, lift, height, footprint)
	var colours := shades(colour)
	for face: String in ["left", "right", "top"]:
		var polygon: PackedVector2Array = faces[face]
		var shade: Color = colours[face]
		add_face(parts, box_name + face.capitalize(), polygon, shade)

# ------------------------------------------------------------------ a place on a layer

## A place of the world in the grid's own coordinates on a layer of diamonds: the cell (x, y) is
## the square from (x, y) to (x + 1, y + 1).
static func grid_of(layer: TileMapLayer, world: Vector2) -> Vector2:
	var local := layer.to_local(world) if layer.is_inside_tree() else world - RpgUtil.world_position(layer)
	return RpgIso.grid_point(local, layer.tile_set.tile_size)

## The place of the world a point of the grid of a layer of diamonds lies at.
static func world_of(layer: TileMapLayer, grid: Vector2) -> Vector2:
	var footprint := layer.tile_set.tile_size
	var local := Vector2((grid.x - grid.y + 1.0) * footprint.x / 2.0, (grid.x + grid.y) * footprint.y / 2.0)
	return layer.to_global(local) if layer.is_inside_tree() else RpgUtil.world_position(layer) + local
