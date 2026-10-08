extends RefCounted
## Collision polygon helpers. Profile polygons are in top-left pixel space of the cell; tile
## collision polygons are centered on the tile, so use to_tile_space() before assigning them.

const JsonUtil := preload("json_util.gd")

static func rect_poly(x: float, y: float, w: float, h: float) -> PackedVector2Array:
	return PackedVector2Array([Vector2(x, y), Vector2(x + w, y), Vector2(x + w, y + h), Vector2(x, y + h)])

## Thickness of the *_EDGE profiles: a quarter of the relevant cell side, clamped to 2..4 px.
static func edge_thickness(side: int) -> float:
	return float(clampi(side / 4, 2, 4))

static func profile_polygon(profile: String, cell: Vector2i, custom: Array = []) -> PackedVector2Array:
	var w := float(cell.x)
	var h := float(cell.y)
	match profile:
		"FULL":
			return rect_poly(0, 0, w, h)
		"BOTTOM_HALF":
			return rect_poly(0, h / 2.0, w, h / 2.0)
		"BOTTOM_EDGE":
			var tb := edge_thickness(cell.y)
			return rect_poly(0, h - tb, w, tb)
		"TOP_EDGE":
			return rect_poly(0, 0, w, edge_thickness(cell.y))
		"LEFT_EDGE":
			return rect_poly(0, 0, edge_thickness(cell.x), h)
		"RIGHT_EDGE":
			var tr := edge_thickness(cell.x)
			return rect_poly(w - tr, 0, tr, h)
		"CUSTOM":
			var pts := PackedVector2Array()
			for p: Array in custom:
				pts.append(Vector2(JsonUtil.to_float(p[0]), JsonUtil.to_float(p[1])))
			return pts
		_:
			# NONE, and ALPHA_POLYGON (traced from pixels by the tileset recipe).
			return PackedVector2Array()

## Converts top-left pixel space to Godot's tile-centered space.
static func to_tile_space(points: PackedVector2Array, cell: Vector2i) -> PackedVector2Array:
	var half := Vector2(cell) / 2.0
	var out := PackedVector2Array()
	for p in points:
		out.append(p - half)
	return out
