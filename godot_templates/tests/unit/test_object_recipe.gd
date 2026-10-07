extends RefCounted
## object_scenes_recipe: template choice and the geometry of a built building (T4.03).

const Recipe := preload("res://builder/recipes/object_scenes_recipe.gd")
const ObjectIndex := preload("res://builder/lib/object_index.gd")

const OUT := "user://test_object_recipe.tscn"

# The house of the sample pack: a 80 x 64 region, default origin (40, 63), door (40, 63).
func _house() -> Dictionary:
	return {
		"id": "pack.town#house", "name": "house", "role": "BUILDING", "tags": ["house", "door"],
		"texture_path": "res://icon.svg", "region": [16, 16, 80, 64], "origin": [40, 63],
		"footprint": [0, 46, 80, 18], "collision": {"profile": "NONE"}, "door": [40, 63], "sha256": "",
	}

func _entry(role: String, tags: Array, collision: String, footprint: Array) -> Dictionary:
	var e := _house()
	e["role"] = role
	e["tags"] = tags
	e["collision"] = {"profile": collision}
	e["footprint"] = footprint
	return e

func test_template_selection_order(t) -> void:
	var r := Recipe.new()
	t.eq(r.template_for(_house(), 16), "building")
	t.eq(r.template_for(_entry("DECORATION", ["door"], "NONE", []), 16), "building", "door tag beats the role")
	t.eq(r.template_for(_entry("DECORATION", ["chest"], "FULL", []), 16), "chest")
	t.eq(r.template_for(_entry("ITEM", ["sign"], "NONE", []), 16), "sign")
	t.eq(r.template_for(_entry("DECORATION", [], "FULL", []), 16), "obstacle", "a collision profile makes an obstacle")
	t.eq(r.template_for(_entry("DECORATION", [], "NONE", [0, 0, 16, 8]), 16), "obstacle", "footprint of half a tile")
	t.eq(r.template_for(_entry("DECORATION", [], "NONE", [0, 0, 8, 8]), 16), "prop", "small footprint stays a prop")
	t.eq(r.template_for(_entry("ITEM", [], "NONE", [0, 0, 80, 40]), 16), "prop", "only decorations qualify by area")

func test_building_scene_matches_hand_computed_values(t) -> void:
	var r := Recipe.new()
	t.eq(r._build_scene(_house(), OUT, 16), OK)
	var scene := (load(OUT) as PackedScene).instantiate()
	t.ok(scene is StaticBody2D)
	t.eq(scene.get("asset_id"), "pack.town#house")
	t.ok(scene.get_collision_layer_value(1) and scene.collision_mask == 0, "world layer, no mask")
	var sprite := scene.get_node("Sprite") as Sprite2D
	t.eq(sprite.offset, Vector2(-40, -63), "offset = -origin")
	t.ok(not sprite.centered)
	t.eq((sprite.texture as AtlasTexture).region, Rect2(16, 16, 80, 64))
	var poly := (scene.get_node("Footprint") as CollisionPolygon2D).polygon
	t.eq(poly, PackedVector2Array([Vector2(-40, -17), Vector2(40, -17), Vector2(40, 1), Vector2(-40, 1)]), "footprint - origin")
	var entrance := scene.get_node("Entrance") as Area2D
	t.eq(entrance.position, Vector2(0, 4), "(door - origin) + (0, 4)")
	t.eq(entrance.collision_layer, 32, "triggers layer 6")
	t.eq(entrance.collision_mask, 2, "player layer 2")
	t.eq(((entrance.get_node("Shape") as CollisionShape2D).shape as RectangleShape2D).size, Vector2(12, 8))
	var exit_spawn := scene.get_node("ExitSpawn") as Marker2D
	t.eq(exit_spawn.position, Vector2(0, 16), "(door - origin) + (0, tile)")
	t.eq(exit_spawn.get("spawn_id"), &"pack__town__house_exit")
	scene.free()
	DirAccess.remove_absolute(OUT)

func test_a_building_without_a_door_assumes_the_bottom_center(t) -> void:
	var r := Recipe.new()
	var e := _house()
	e["door"] = []
	t.eq(r._build_scene(e, OUT, 16), OK)
	var scene := (load(OUT) as PackedScene).instantiate()
	t.ok((scene.get_meta("tags") as Array).has("door_assumed"))
	t.eq((scene.get_node("Entrance") as Area2D).position, Vector2(0, 4))
	scene.free()
	DirAccess.remove_absolute(OUT)

func test_a_prop_has_no_body_and_no_footprint(t) -> void:
	var r := Recipe.new()
	var e := _entry("ITEM", [], "NONE", [])
	t.eq(r._build_scene(e, OUT, 16), OK)
	var scene := (load(OUT) as PackedScene).instantiate()
	t.ok(scene is Node2D and not (scene is StaticBody2D))
	t.ok(not scene.has_node("Footprint") and not scene.has_node("Entrance"))
	t.eq(scene.get("blocks_movement"), false)
	scene.free()
	DirAccess.remove_absolute(OUT)

func test_object_file_names(t) -> void:
	t.eq(ObjectIndex.stem("pack.town#house"), "pack__town__house")
	t.eq(ObjectIndex.scene_path("a.b#c"), "res://generated/scenes/objects/a__b__c.tscn")
