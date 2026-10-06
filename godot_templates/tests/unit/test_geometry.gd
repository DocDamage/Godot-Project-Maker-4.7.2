extends RefCounted

const Geometry := preload("../../builder/lib/geometry.gd")

func test_full_16x16_has_four_corners(t) -> void:
	var pts := Geometry.profile_polygon("FULL", Vector2i(16, 16))
	t.eq(pts.size(), 4)
	t.eq(pts[0], Vector2(0, 0))
	t.eq(pts[1], Vector2(16, 0))
	t.eq(pts[2], Vector2(16, 16))
	t.eq(pts[3], Vector2(0, 16))

func test_full_in_tile_space_is_plus_minus_half(t) -> void:
	var pts := Geometry.to_tile_space(Geometry.profile_polygon("FULL", Vector2i(16, 16)), Vector2i(16, 16))
	t.eq(pts[0], Vector2(-8, -8))
	t.eq(pts[2], Vector2(8, 8))

func test_bottom_half_16x24_range(t) -> void:
	var pts := Geometry.profile_polygon("BOTTOM_HALF", Vector2i(16, 24))
	var min_y := 1000.0
	var max_y := -1000.0
	for p in pts:
		min_y = minf(min_y, p.y)
		max_y = maxf(max_y, p.y)
	t.near(min_y, 12.0)
	t.near(max_y, 24.0)

func test_edge_profiles(t) -> void:
	var bottom := Geometry.profile_polygon("BOTTOM_EDGE", Vector2i(16, 16))
	t.eq(bottom[0], Vector2(0, 12))
	t.eq(bottom[2], Vector2(16, 16))
	var top := Geometry.profile_polygon("TOP_EDGE", Vector2i(16, 16))
	t.eq(top[2], Vector2(16, 4))
	var left := Geometry.profile_polygon("LEFT_EDGE", Vector2i(16, 16))
	t.eq(left[2], Vector2(4, 16))
	var right := Geometry.profile_polygon("RIGHT_EDGE", Vector2i(16, 16))
	t.eq(right[0], Vector2(12, 0))
	# very small cells keep a 2px minimum edge
	var tiny := Geometry.profile_polygon("BOTTOM_EDGE", Vector2i(8, 8))
	t.eq(tiny[0], Vector2(0, 6))

func test_none_and_alpha_are_empty(t) -> void:
	t.eq(Geometry.profile_polygon("NONE", Vector2i(16, 16)).size(), 0)
	t.eq(Geometry.profile_polygon("ALPHA_POLYGON", Vector2i(16, 16)).size(), 0)

func test_custom_points(t) -> void:
	var pts := Geometry.profile_polygon("CUSTOM", Vector2i(16, 16), [[0, 8], [16, 8], [16, 16.0]])
	t.eq(pts.size(), 3)
	t.eq(pts[0], Vector2(0, 8))
	t.eq(pts[2], Vector2(16, 16))
