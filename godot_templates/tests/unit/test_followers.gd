extends RefCounted
## Party followers (T12.69): the trail, the point a follower stands on, its facing and animation.

func _trail(points: Array) -> Array[Vector2]:
	var out: Array[Vector2] = []
	for p: Vector2 in points:
		out.append(p)
	return out

func test_the_trail_records_moves_newest_first_and_stays_short(t) -> void:
	var trail: Array[Vector2] = []
	t.ok(RpgFollowers.record(trail, Vector2(0, 0), 1.0, 5))
	t.ok(not RpgFollowers.record(trail, Vector2(0.5, 0), 1.0, 5), "less than a pixel is no move")
	for x in range(1, 10):
		RpgFollowers.record(trail, Vector2(x, 0), 1.0, 5)
	t.eq(trail.size(), 5, "at most max_points")
	t.eq(trail[0], Vector2(9, 0), "the newest first")
	t.eq(RpgFollowers.trail_points_needed(2, 16.0), 50)

func test_a_point_along_the_trail_follows_the_corners(t) -> void:
	# The player walked right from (0, 0) to (20, 0), then down to (20, 10): newest first.
	var trail := _trail([Vector2(20, 10), Vector2(20, 0), Vector2(0, 0)])
	t.eq(RpgFollowers.point_along(trail, 0.0), Vector2(20, 10))
	t.eq(RpgFollowers.point_along(trail, 4.0), Vector2(20, 6), "back up the vertical leg")
	t.eq(RpgFollowers.point_along(trail, 16.0), Vector2(14, 0), "round the corner")
	t.eq(RpgFollowers.point_along(trail, 99.0), Vector2(0, 0), "a short trail ends at its oldest point")
	t.eq(RpgFollowers.point_along([] as Array[Vector2], 5.0), Vector2.ZERO)

func test_a_follower_faces_the_way_the_path_goes_and_walks_while_the_player_does(t) -> void:
	var player := Node2D.new()
	var visual := AnimatedSprite2D.new()
	visual.name = "Visual"
	var frames := SpriteFrames.new()
	for anim in ["idle_down", "walk_down", "walk_right", "idle_right"]:
		frames.add_animation(anim)
		frames.add_frame(anim, PlaceholderTexture2D.new())
	visual.sprite_frames = frames
	visual.offset = Vector2(-8, -15)
	visual.centered = false
	player.add_child(visual)
	var follower := RpgFollowers.make_follower(null, player)
	var shown := follower.get_node("Visual") as AnimatedSprite2D
	t.eq(shown.sprite_frames, frames, "without a definition of its own it looks like the player")
	t.eq(shown.offset, Vector2(-8, -15))
	var trail := _trail([Vector2(40, 0), Vector2(0, 0)])
	RpgFollowers.place(follower, trail, 16.0, true)
	t.eq(follower.position, Vector2(24, 0))
	t.eq(follower.get_meta("facing"), "right")
	t.eq(String(shown.animation), "walk_right")
	RpgFollowers.place(follower, trail, 16.0, false)
	t.eq(String(shown.animation), "idle_right", "it stands when the player stands")
	follower.free()
	player.free()

func test_a_member_with_frames_of_its_own_stands_on_its_feet(t) -> void:
	var player := Node2D.new()
	var def := RpgActorDefinition.new()
	var frames := SpriteFrames.new()
	frames.add_animation("idle_down")
	var image := Image.create(24, 32, false, Image.FORMAT_RGBA8)
	frames.add_frame("idle_down", ImageTexture.create_from_image(image))
	def.sprite_frames = frames
	var follower := RpgFollowers.make_follower(def, player)
	var shown := follower.get_node("Visual") as AnimatedSprite2D
	t.eq(shown.sprite_frames, frames)
	t.ok(not shown.centered)
	t.eq(shown.offset, Vector2(-12, -31), "bottom centre on the feet")
	follower.free()
	player.free()
