extends RefCounted

const Driver := preload("../../addons/rpg_runtime/actors/animation_driver.gd")

func _frames(names: Array, flip_meta: Array = []) -> SpriteFrames:
	var sf := SpriteFrames.new()
	if sf.has_animation("default"):
		sf.remove_animation("default")
	var img := Image.create(16, 16, false, Image.FORMAT_RGBA8)
	var tex := ImageTexture.create_from_image(img)
	for n in names:
		sf.add_animation(n)
		sf.add_frame(n, tex, 1.0)
		sf.add_frame(n, tex, 1.0)
	for n in flip_meta:
		sf.set_meta("flip_h_" + n, true)
	return sf

func _driver(frames: SpriteFrames) -> RefCounted:
	var d: RefCounted = Driver.new()
	d.sprite = AnimatedSprite2D.new()
	d.sprite.sprite_frames = frames
	return d

func test_dir_to_facing_eight_directions(t) -> void:
	t.eq(Driver.dir_to_facing(Vector2(1, 0)), "right")
	t.eq(Driver.dir_to_facing(Vector2(-1, 0)), "left")
	t.eq(Driver.dir_to_facing(Vector2(0, 1)), "down")
	t.eq(Driver.dir_to_facing(Vector2(0, -1)), "up")
	# exact diagonals are ties: vertical wins
	t.eq(Driver.dir_to_facing(Vector2(1, 1)), "down")
	t.eq(Driver.dir_to_facing(Vector2(1, -1)), "up")
	t.eq(Driver.dir_to_facing(Vector2(-1, 1)), "down")
	t.eq(Driver.dir_to_facing(Vector2(-1, -1)), "up")
	# non-tie diagonals follow the dominant axis
	t.eq(Driver.dir_to_facing(Vector2(1.0, 0.5)), "right")
	t.eq(Driver.dir_to_facing(Vector2(0.5, -1.0)), "up")

func test_direct_animation_is_used(t) -> void:
	var d := _driver(_frames(["walk_down", "walk_right"]))
	d.play("walk", "right")
	t.eq(d.sprite.animation, &"walk_right")
	t.eq(d.sprite.flip_h, false)
	d.sprite.free()

func test_missing_left_mirrors_right(t) -> void:
	var d := _driver(_frames(["walk_down", "walk_right"]))
	d.play("walk", "left")
	t.eq(d.sprite.animation, &"walk_right")
	t.eq(d.sprite.flip_h, true)
	d.sprite.free()

func test_missing_up_falls_back_to_down(t) -> void:
	var d := _driver(_frames(["walk_down", "walk_right"]))
	d.play("walk", "up")
	t.eq(d.sprite.animation, &"walk_down")
	t.eq(d.sprite.flip_h, false)
	d.sprite.free()

func test_idle_falls_back_to_paused_walk_frame_zero(t) -> void:
	var d := _driver(_frames(["walk_down", "walk_right"]))
	d.sprite.frame = 1
	d.play("idle", "down")
	t.eq(d.sprite.animation, &"walk_down")
	t.eq(d.sprite.frame, 0)
	d.play("idle", "left")
	t.eq(d.sprite.animation, &"walk_right")
	t.eq(d.sprite.flip_h, true)
	t.eq(d.sprite.frame, 0)
	d.sprite.free()

func test_flip_meta_is_applied(t) -> void:
	var d := _driver(_frames(["walk_left", "walk_down"], ["walk_left"]))
	d.play("walk", "left")
	t.eq(d.sprite.animation, &"walk_left")
	t.eq(d.sprite.flip_h, true)
	d.play("walk", "down")
	t.eq(d.sprite.flip_h, false)
	d.sprite.free()

func test_dir_to_facing8(t) -> void:
	t.eq(Driver.dir_to_facing8(Vector2(1, 0)), "right")
	t.eq(Driver.dir_to_facing8(Vector2(0, -1)), "up")
	t.eq(Driver.dir_to_facing8(Vector2(1, 1)), "down_right")
	t.eq(Driver.dir_to_facing8(Vector2(-1, 1)), "down_left")
	t.eq(Driver.dir_to_facing8(Vector2(1, -1)), "up_right")
	t.eq(Driver.dir_to_facing8(Vector2(-1, -1)), "up_left")
	# within 22.5 degrees of an axis it is that axis
	t.eq(Driver.dir_to_facing8(Vector2(1.0, 0.3)), "right")
	t.eq(Driver.dir_to_facing8(Vector2(-0.3, 1.0)), "down")
	t.eq(Driver.dir_to_facing8(Vector2(1.0, 0.5)), "down_right")
	t.eq(Driver.dir_to_facing8(Vector2.ZERO), "down")

const EIGHT := ["walk_down", "walk_up", "walk_left", "walk_right", "walk_down_left", "walk_down_right", "walk_up_left", "walk_up_right"]

func test_eight_directions_follow_the_direction_of_travel(t) -> void:
	var d := _driver(_frames(EIGHT))
	d.play("walk", "down", Vector2(1, 1))
	t.eq(d.sprite.animation, &"walk_down_right")
	d.play("walk", "up", Vector2(-1, -1))
	t.eq(d.sprite.animation, &"walk_up_left")
	d.play("walk", "right", Vector2(1.0, 0.5))
	t.eq(d.sprite.animation, &"walk_down_right")
	d.play("walk", "right", Vector2(1.0, 0.2))
	t.eq(d.sprite.animation, &"walk_right")
	# without a direction of travel the facing decides
	d.play("walk", "left")
	t.eq(d.sprite.animation, &"walk_left")
	# a direction that disagrees with the facing (a locked facing) is ignored
	d.play("walk", "down", Vector2(-1, -1))
	t.eq(d.sprite.animation, &"walk_down")
	t.eq(d.sprite.flip_h, false)
	d.sprite.free()

func test_four_direction_sprite_ignores_the_diagonal(t) -> void:
	var d := _driver(_frames(["walk_down", "walk_up", "walk_left", "walk_right"]))
	d.play("walk", "right", Vector2(1.0, 0.5))
	t.eq(d.sprite.animation, &"walk_right")
	d.play("walk", "down", Vector2(1, 1))
	t.eq(d.sprite.animation, &"walk_down")
	d.sprite.free()

func test_missing_diagonal_is_mirrored(t) -> void:
	var d := _driver(_frames(["walk_down", "walk_right", "walk_down_right", "walk_up_right"]))
	d.play("walk", "down", Vector2(-1, 1))
	t.eq(d.sprite.animation, &"walk_down_right")
	t.eq(d.sprite.flip_h, true)
	d.play("walk", "up", Vector2(-1, -1))
	t.eq(d.sprite.animation, &"walk_up_right")
	t.eq(d.sprite.flip_h, true)
	d.play("walk", "down", Vector2(1, 1))
	t.eq(d.sprite.flip_h, false)
	d.sprite.free()

func test_nearest_direction_that_exists(t) -> void:
	# only the diagonals (an isometric-style sprite): a facing shows the one next to it
	var d := _driver(_frames(["walk_down_left", "walk_down_right", "walk_up_left", "walk_up_right"]))
	d.play("walk", "down")
	t.eq(d.sprite.animation, &"walk_down_left")
	d.play("walk", "up")
	t.eq(d.sprite.animation, &"walk_up_left")
	d.play("walk", "right")
	t.eq(d.sprite.animation, &"walk_down_right")
	d.play("walk", "left", Vector2(-1, -1))
	t.eq(d.sprite.animation, &"walk_up_left")
	d.sprite.free()
	# a diagonal asked of a four-direction sprite: the vertical one next to it
	var four := _driver(_frames(["walk_down", "walk_up", "walk_right"]))
	four.play("walk", "down_left")
	t.eq(four.sprite.animation, &"walk_down")
	four.play("walk", "up_right")
	t.eq(four.sprite.animation, &"walk_up")
	four.sprite.free()
	var side := _driver(_frames(["walk_right"]))
	side.play("walk", "down_left")
	t.eq(side.sprite.animation, &"walk_right")
	t.eq(side.sprite.flip_h, true)
	side.sprite.free()

func test_idle_uses_the_diagonal_walk_frame(t) -> void:
	var d := _driver(_frames(EIGHT))
	d.play("idle", "down", Vector2(1, 1))
	t.eq(d.sprite.animation, &"walk_down_right")
	t.eq(d.sprite.frame, 0)
	t.ok(not d.sprite.is_playing(), "the walk frame is held")
	d.sprite.free()
	# an idle of its own wins over a diagonal walk
	var own := _driver(_frames(EIGHT + ["idle_down"]))
	own.play("idle", "down", Vector2(1, 1))
	t.eq(own.sprite.animation, &"idle_down")
	own.sprite.free()

func test_no_sprite_or_frames_does_nothing(t) -> void:
	var d: RefCounted = Driver.new()
	d.play("walk", "down")  # sprite is null: must not crash
	d.sprite = AnimatedSprite2D.new()
	d.play("walk", "down")  # sprite_frames is the default empty set: must not crash
	t.ok(true)
	d.sprite.free()
