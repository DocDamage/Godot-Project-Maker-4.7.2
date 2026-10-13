extends SceneTree
# Probe (T17.15): can one transform on a parent node turn the flat world of a race into the
# isometric picture, with the physics still exact?
#
# The plan of a track is flat: squares of `PLAN` px, x east and y south. The isometric view lays
# those squares out as diamonds of `FOOT` px. That is one affine map, `view()` below (x axis
# (w/2, h/2) / PLAN, y axis (-w/2, h/2) / PLAN): a shear and a squeeze. Three things are asked:
#
# 1. Drawing under a Node2D with that transform: a Polygon2D square (a piece of road) comes out
#    as the diamond; a Sprite2D comes out sheared, and one whose own transform is the inverse of
#    the linear part of the parent's comes out upright again.
# 2. Physics under it: a CharacterBody2D with a circle drives east in the plan at a wall, once
#    under a plain parent and once under the sheared one. Where it stops in the coordinates of
#    the parent, what `move_and_collide` takes its motion to be, and the normal it reports.
# 3. The other way: the body stays under a plain parent (the flat plan) and only its picture is
#    moved, by `view * position - position`: where the picture is drawn.
#
# Run in any scratch project with a renderer (not --headless):
#   godot --path <scratch> --script <this file> -- <picture.png>

const FOOT := Vector2(60, 34)
const PLAN := 16.0
const AT := Vector2(320, 60)
const BACK := Color8(28, 30, 40)
const ROAD := Color8(90, 90, 100)
const RED := Color8(220, 60, 60)
const BLUE := Color8(60, 90, 220)
const GREEN := Color8(60, 200, 90)

var failed := 0
var checks := 0

func view() -> Transform2D:
	return Transform2D(Vector2(FOOT.x / 2.0, FOOT.y / 2.0) / PLAN, Vector2(-FOOT.x / 2.0, FOOT.y / 2.0) / PLAN, AT)

func check(ok: bool, what: String) -> void:
	checks += 1
	if not ok:
		failed += 1
	print("%s %s" % ["ok  " if ok else "FAIL", what])

func square(size: float, colour: Color) -> ImageTexture:
	var image := Image.create(int(size), int(size), false, Image.FORMAT_RGBA8)
	image.fill(colour)
	return ImageTexture.create_from_image(image)

func near(c: Color, want: Color) -> bool:
	return absf(c.r - want.r) + absf(c.g - want.g) + absf(c.b - want.b) < 0.05

## Drives a body with a circle of 5 px east at a wall whose face is at x = 100 of `parent`, in
## steps of 2 px. Returns [first step in the coordinates of the parent, where it stopped, the
## normal].
func drive(parent: Node2D) -> Array:
	var wall := StaticBody2D.new()
	var box := RectangleShape2D.new()
	box.size = Vector2(10, 200)
	var wall_shape := CollisionShape2D.new()
	wall_shape.shape = box
	wall_shape.position = Vector2(105, 0)
	wall.add_child(wall_shape)
	parent.add_child(wall)
	var body := CharacterBody2D.new()
	body.motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	var circle := CircleShape2D.new()
	circle.radius = 5.0
	var body_shape := CollisionShape2D.new()
	body_shape.shape = circle
	body.add_child(body_shape)
	body.position = Vector2(50, 0)
	parent.add_child(body)
	await physics_frame
	await physics_frame
	var before := body.position
	body.move_and_collide(Vector2(2, 0))
	var first := body.position - before
	var normal := Vector2.ZERO
	for i in 200:
		var hit := body.move_and_collide(Vector2(2, 0))
		if hit != null:
			normal = hit.get_normal()
			break
	return [first, body.position, normal]

func _initialize() -> void:
	DisplayServer.window_set_size(Vector2i(640, 360))
	RenderingServer.set_default_clear_color(BACK)
	_run.call_deferred()

func _run() -> void:
	var t := view()
	# 1. drawing under the transform
	var world := Node2D.new()
	world.transform = t
	root.add_child(world)
	var road := Polygon2D.new()
	road.color = ROAD
	road.polygon = PackedVector2Array([Vector2(0, 0), Vector2(64, 0), Vector2(64, 64), Vector2(0, 64)])
	world.add_child(road)
	var sheared := Sprite2D.new()
	sheared.texture = square(16, RED)
	sheared.position = Vector2(16, 48)
	world.add_child(sheared)
	var upright := Sprite2D.new()
	upright.texture = square(16, BLUE)
	var back := t.affine_inverse()
	upright.transform = Transform2D(back.x, back.y, Vector2(48, 16))
	world.add_child(upright)
	# 3. a body in the flat plan, its picture moved to the screen
	var flat := Node2D.new()
	root.add_child(flat)
	var body := CharacterBody2D.new()
	body.position = Vector2(48, 48)
	flat.add_child(body)
	var picture := Sprite2D.new()
	picture.texture = square(10, GREEN)
	picture.position = t * body.position - body.position
	body.add_child(picture)
	# 2. physics, plain and sheared
	var plain_parent := Node2D.new()
	plain_parent.position = Vector2(2000, 2000)
	root.add_child(plain_parent)
	var plain: Array = await drive(plain_parent)
	var shear_parent := Node2D.new()
	shear_parent.transform = Transform2D(t.x, t.y, Vector2(4000, 4000))
	root.add_child(shear_parent)
	var skew: Array = await drive(shear_parent)
	print("plain parent: first step %s, stopped at %s, normal %s" % plain)
	print("sheared parent: first step %s, stopped at %s, normal %s" % skew)
	var plain_first: Vector2 = plain[0]
	var plain_stop: Vector2 = plain[1]
	var plain_normal: Vector2 = plain[2]
	var skew_first: Vector2 = skew[0]
	var skew_stop: Vector2 = skew[1]
	var skew_normal: Vector2 = skew[2]
	check(plain_first.is_equal_approx(Vector2(2, 0)), "plain: a motion of (2, 0) moves the body (2, 0)")
	check(absf(plain_stop.x - 95.0) < 0.2 and absf(plain_stop.y) < 0.01, "plain: the circle of 5 px stops at x = 95 before the wall at 100 (%.3f)" % plain_stop.x)
	check(plain_normal.is_equal_approx(Vector2(-1, 0)), "plain: the normal is (-1, 0)")
	check(not skew_first.is_equal_approx(Vector2(2, 0)), "sheared: a motion of (2, 0) is not (2, 0) of the plan (it is %s: the motion is the screen's)" % skew_first)
	check(absf(skew_stop.y) > 1.0 or absf(skew_stop.x - 95.0) > 0.5, "sheared: the body does not stop at (95, 0) of the plan (it stops at %s)" % skew_stop)
	check(not skew_normal.is_equal_approx(Vector2(-1, 0)), "sheared: the normal is not (-1, 0) of the plan (it is %s)" % skew_normal)
	await process_frame
	await process_frame
	await process_frame
	var image := root.get_texture().get_image()
	var at := func(plan: Vector2) -> Color:
		var p := t * plan
		return image.get_pixel(int(p.x), int(p.y))
	# the square of road is the diamond of 4 x 4 cells
	var inside: bool = near(at.call(Vector2(4, 4)), ROAD) and near(at.call(Vector2(60, 4)), ROAD) and near(at.call(Vector2(60, 60)), ROAD) and near(at.call(Vector2(4, 60)), ROAD)
	check(inside, "a Polygon2D square under the transform is drawn as the diamond")
	var outside: bool = near(at.call(Vector2(-4, 32)), BACK) and near(at.call(Vector2(68, 32)), BACK)
	check(outside, "and nothing outside it")
	# the sheared sprite of 16 px is the diamond of one cell (60 x 34): 14 px above its middle
	# is still the sprite, where an upright square of 16 px would have ended at 8
	var mid := t * Vector2(16, 48)
	var east: bool = near(at.call(Vector2(16 + 7, 48)), RED)
	check(east, "a Sprite2D under the transform is drawn sheared (7 px east in the plan is the sprite)")
	check(near(image.get_pixel(int(mid.x), int(mid.y - 14)), RED) and not near(image.get_pixel(int(mid.x + 7), int(mid.y - 14)), RED), "... it is the diamond of a cell: 14 px above its middle is the sprite, 7 px to the right of that is not")
	var up := t * Vector2(48, 16)
	var corners := true
	for d: Vector2 in [Vector2(-7, -7), Vector2(7, -7), Vector2(7, 7), Vector2(-7, 7)]:
		corners = corners and near(image.get_pixel(int(up.x + d.x), int(up.y + d.y)), BLUE)
	check(corners, "a Sprite2D whose own transform is the inverse of the parent is an upright square again")
	var shown := t * Vector2(48, 48)
	check(near(image.get_pixel(int(shown.x), int(shown.y)), GREEN) and near(image.get_pixel(int(shown.x) + 4, int(shown.y) - 4), GREEN), "a picture moved by view * p - p is drawn at the place of the screen, upright")
	check(body.position == Vector2(48, 48), "... and its body is still where the plan has it")
	var args := OS.get_cmdline_user_args()
	var out := args[0] if not args.is_empty() else "user://probe_iso_race_view.png"
	image.save_png(out)
	print("%d checks, %d failed; picture: %s" % [checks, failed, out])
	quit(1 if failed > 0 else 0)
