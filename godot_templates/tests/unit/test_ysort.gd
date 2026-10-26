extends RefCounted
## Logical Y-sort checks of validate.gd (T4.07): a visual's bottom edge sits on the node origin.

const Validate := preload("res://builder/validate.gd")

func _sprite(offset: Vector2, centered: bool, size: Vector2i = Vector2i(16, 24)) -> Sprite2D:
	var s := Sprite2D.new()
	var tex := AtlasTexture.new()
	tex.atlas = load("res://icon.svg")
	tex.region = Rect2(0, 0, size.x, size.y)
	s.texture = tex
	s.offset = offset
	s.centered = centered
	return s

func test_origin_at_the_feet_is_aligned(t) -> void:
	var root := Node2D.new()
	var s := _sprite(Vector2(-8, -23), false)  # origin (8, 23) of a 16 x 24 frame
	root.add_child(s)
	t.near(Validate.visual_bottom(s, root), 1.0)
	root.free()

func test_a_wrong_origin_is_far_from_zero(t) -> void:
	var root := Node2D.new()
	var s := _sprite(Vector2(-8, -94), false)  # origin taken from the whole sheet
	root.add_child(s)
	t.near(Validate.visual_bottom(s, root), -70.0)
	root.free()

func test_centered_sprites_and_parent_offsets_count(t) -> void:
	var root := Node2D.new()
	var holder := Node2D.new()
	holder.position = Vector2(0, 5)
	root.add_child(holder)
	var s := _sprite(Vector2.ZERO, true)  # centered: top = -12, bottom = +12
	holder.add_child(s)
	t.near(Validate.visual_bottom(s, root), 17.0)
	root.free()

func test_feet_above_empty_rows_are_the_bottom(t) -> void:
	# a 32 px cell whose figure stands on row 23 (Super Retro Ranch), the origin at its feet
	var img := Image.create(32, 32, false, Image.FORMAT_RGBA8)
	img.fill_rect(Rect2i(8, 4, 16, 20), Color.WHITE)
	var s := Sprite2D.new()
	s.texture = ImageTexture.create_from_image(img)
	s.centered = false
	s.offset = Vector2(-16, -24)
	var root := Node2D.new()
	root.add_child(s)
	t.near(Validate.visual_bottom(s, root, true), 0.0)
	t.near(Validate.visual_bottom(s, root), 8.0, 0.001, "the frame goes on below the feet")
	root.free()

func test_node_without_a_texture_is_skipped(t) -> void:
	var root := Node2D.new()
	var s := Sprite2D.new()
	root.add_child(s)
	t.ok(is_nan(Validate.visual_bottom(s, root)))
	root.free()
