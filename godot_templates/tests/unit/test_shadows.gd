extends RefCounted
## The shadow a pack draws under a thing or a character (2026-10-26, `ActorBuild.add_shadow`):
## a Sprite2D `Shadow` drawn first, at 35 %; a thing's lies at the thing's offset whatever the
## size of its picture (Gridwright's altar: a shadow of 48 x 48 under a picture of 32 x 48), a
## character's is centred on its feet; no facet or no file, no shadow.

const ActorBuild := preload("res://builder/lib/actor_build.gd")

const PICTURE := "res://tests/fixtures/iso_tiles/house.png"

func _root() -> Node2D:
	var root := Node2D.new()
	var picture := Sprite2D.new()
	picture.name = "Sprite"
	root.add_child(picture)
	return root

func test_a_things_shadow_lies_with_its_anchor(t) -> void:
	var root := _root()
	ActorBuild.add_shadow(root, {"shadow": PICTURE}, Vector2(-16, -40), true)
	var shadow := root.get_node_or_null("Shadow") as Sprite2D
	t.ok(shadow != null, "a shadow")
	t.eq(root.get_child(0), shadow, "drawn first, under the picture")
	t.eq(shadow.centered, false)
	t.eq(shadow.offset, Vector2(-16, -40), "the thing's offset, whatever its size")
	t.ok(is_equal_approx(shadow.modulate.a, ActorBuild.SHADOW_ALPHA), "35 %")
	root.free()

func test_a_characters_shadow_is_centred_on_its_feet(t) -> void:
	var root := _root()
	ActorBuild.add_shadow(root, {"shadow": PICTURE})
	var shadow := root.get_node_or_null("Shadow") as Sprite2D
	t.ok(shadow != null and shadow.centered and shadow.position == Vector2.ZERO, "centred on the feet")
	ActorBuild.add_shadow(root, {"shadow": PICTURE})
	t.eq(root.get_children().filter(func(n: Node) -> bool: return n.name.begins_with("Shadow")).size(), 1, "one shadow")
	root.free()

func test_no_shadow_without_one(t) -> void:
	var root := _root()
	ActorBuild.add_shadow(root, {})
	ActorBuild.add_shadow(root, {"shadow": "res://tests/fixtures/no_such_shadow.png"})
	t.ok(root.get_node_or_null("Shadow") == null, "no shadow")
	root.free()
