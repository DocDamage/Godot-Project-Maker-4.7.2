extends RefCounted
## T14.04: the side-view NPC, chests and signs used from beside them, the room camera and the
## dock's drop onto the floor.

const Fixtures := preload("../lib/fixtures.gd")
const PlatformTests := preload("test_platform_actor.gd")
const PlayerRecipe := preload("res://builder/recipes/metroidvania/player_recipe.gd")
const ObjectsRecipe := preload("res://builder/recipes/metroidvania/objects_recipe.gd")
const Placement := preload("res://addons/rpg_project_tools/dock/placement.gd")

const TILE := 16
const FRAME := Vector2i(24, 24)
const FLOOR_Y := 10

## Stands in for the dialogue box: it remembers what was opened.
class Box extends Node:
	var opened: Array = []

	func open(dialogue: Resource, actor: Node = null) -> void:
		opened.append([dialogue, actor])

class Room:
	var root: Node2D
	var layer: TileMapLayer
	var player: RpgPlatformPlayer

	func frames(count: int) -> void:
		for i in count:
			await root.get_tree().physics_frame

	func close() -> void:
		root.get_parent().remove_child(root)
		root.free()

func _room() -> Room:
	var tree := Fixtures.tree()
	await tree.process_frame
	var room := Room.new()
	room.root = Node2D.new()
	room.root.name = "SideRoom"
	room.layer = TileMapLayer.new()
	room.layer.tile_set = PlatformTests.tileset()
	room.root.add_child(room.layer)
	for x in 40:
		room.layer.set_cell(Vector2i(x, FLOOR_Y), 0, PlatformTests.GROUND)
	room.player = PlayerRecipe.build_player("Player", null, FRAME, Vector2i(12, 23), TILE) as RpgPlatformPlayer
	room.player.position = Vector2(5.5 * TILE, FLOOR_Y * TILE)
	room.root.add_child(room.player)
	tree.root.add_child(room.root)
	(room.player.component("PlatformInput") as RpgPlatformInput).enabled = false
	await room.frames(20)
	return room

func _body(script: GDScript, at: Vector2) -> StaticBody2D:
	var body := StaticBody2D.new()
	body.set_script(script)
	body.collision_layer = 0
	body.collision_mask = 0
	body.set_collision_layer_value(5, true)  # as the recipe builds it for a side-view room
	body.set("side_view", true)
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(12, 12)
	shape.shape = rect
	shape.position = Vector2(0, -6)
	body.add_child(shape)
	body.position = at
	return body

# ---------------------------------------------------------------- the NPC

func test_the_side_npc_stands_on_the_floor_and_turns_to_the_player(t) -> void:
	var room: Room = await _room()
	var box := Box.new()
	box.add_to_group("rpg_dialogue_box")
	room.root.add_child(box)
	var npc := PlayerRecipe.build_npc("Hermit", null, FRAME, Vector2i(12, 23), TILE) as RpgSideNpc
	t.ok(npc != null and npc.get_collision_layer_value(4), "an RpgSideNpc on the npcs layer")
	npc.dialogue = RpgDialogueResource.new()
	npc.start_facing = 1
	npc.position = Vector2(7.0 * TILE, (FLOOR_Y - 3) * TILE)  # dropped from above
	room.root.add_child(npc)
	await room.frames(50)
	t.ok(npc.is_on_floor(), "it fell to the floor and stands")
	t.near(npc.position.y, float(FLOOR_Y * TILE), 1.0)
	t.eq(npc.facing, 1)
	t.eq(room.player.find_target(), npc, "the player finds it beside itself")
	t.ok(room.player.try_interact())
	t.eq(npc.facing, -1, "it turned to the player on its left")
	t.eq(room.player.facing, 1, "and the player looks at it")
	t.eq(box.opened.size(), 1, "the dialogue runs")
	t.ok(box.opened[0][0] == npc.dialogue and box.opened[0][1] == room.player)
	room.player.position.x = 8.5 * TILE  # the other side
	await room.frames(4)
	room.player.try_interact()
	t.eq(npc.facing, 1)
	t.eq(room.player.facing, -1)
	room.close()

func test_a_top_down_actor_shows_a_side_view_sheet_instead_of_nothing(t) -> void:
	var driver := RpgAnimationDriver.new()
	driver.sprite = AnimatedSprite2D.new()
	var frames := SpriteFrames.new()
	for anim: String in ["idle_side", "walk"]:
		frames.add_animation(anim)
		frames.add_frame(anim, PlaceholderTexture2D.new())
	driver.sprite.sprite_frames = frames
	driver.play("idle", "down")
	t.eq(String(driver.sprite.animation), "idle_side")
	t.eq(driver.sprite.flip_h, false)
	driver.play("walk", "left")
	t.eq(String(driver.sprite.animation), "walk")
	t.eq(driver.sprite.flip_h, true, "mirrored for the left")
	driver.sprite.free()

# ---------------------------------------------------------------- chests and signs

func test_a_side_view_chest_opens_from_either_side_and_never_from_above(t) -> void:
	var state := Fixtures.install_state({&"potion": Fixtures.item(&"potion")}) as RpgGameState
	var english := Fixtures.install_english()
	var room: Room = await _room()
	for x in range(9, 13):
		room.layer.set_cell(Vector2i(x, FLOOR_Y - 3), 0, PlatformTests.ONE_WAY)  # a platform over the chest
	var chest := _body(load("res://addons/rpg_runtime/world/chest.gd") as GDScript, Vector2(10.5 * TILE, FLOOR_Y * TILE)) as RpgChest
	chest.loot = [{"item_id": "potion", "qty": 1}]
	room.root.add_child(chest)
	t.ok(not chest.get_collision_layer_value(1), "it does not block the way")
	room.player.position = Vector2(10.5 * TILE, (FLOOR_Y - 3) * TILE)  # on the platform above
	await room.frames(20)
	t.ok(room.player.is_on_floor())
	t.eq(room.player.find_target(), null, "not from above")
	t.ok(not room.player.try_interact())
	t.ok(not chest.opened)
	room.player.position = Vector2(9.6 * TILE, FLOOR_Y * TILE)  # on its left
	await room.frames(6)
	t.eq(room.player.find_target(), chest)
	t.ok(room.player.try_interact())
	t.ok(chest.opened and state.inventory.count(&"potion") == 1, "opened from the left")
	var second := _body(load("res://addons/rpg_runtime/world/chest.gd") as GDScript, Vector2(20.5 * TILE, FLOOR_Y * TILE)) as RpgChest
	room.root.add_child(second)
	room.player.position = Vector2(21.4 * TILE, FLOOR_Y * TILE)  # on its right
	await room.frames(6)
	t.ok(room.player.try_interact())
	t.ok(second.opened, "opened from the right")
	t.eq(room.player.facing, -1, "the player turned to it")
	# the top-down chest is what it was: no check of its own
	var plain := RpgChest.new()
	t.ok(plain.can_interact(room.player), "a top-down chest refuses nobody")
	plain.free()
	room.close()
	Fixtures.uninstall_english(english)
	Fixtures.uninstall_state()

func test_a_side_view_sign_is_read_from_beside_it(t) -> void:
	var room: Room = await _room()
	var box := Box.new()
	box.add_to_group("rpg_dialogue_box")
	room.root.add_child(box)
	var sign_node := _body(load("res://addons/rpg_runtime/world/sign.gd") as GDScript, Vector2(6.5 * TILE, FLOOR_Y * TILE)) as RpgSign
	sign_node.dialogue = RpgDialogueResource.new()
	room.root.add_child(sign_node)
	await room.frames(6)
	t.ok(room.player.try_interact())
	t.eq(box.opened.size(), 1)
	var above := Node2D.new()
	above.position = sign_node.position + Vector2(0, -3 * TILE)
	room.root.add_child(above)
	t.ok(not sign_node.can_interact(above), "not from three tiles above")
	t.ok(sign_node.can_interact(room.player))
	room.close()

func test_side_view_spawns_and_doors(t) -> void:
	var spawn := RpgSpawnPoint.new()
	spawn.facing = "left"
	t.eq(spawn.side(), -1)
	spawn.facing = "down"
	t.eq(spawn.side(), 1, "a top-down direction means nothing in a room")
	spawn.free()
	var player := PlayerRecipe.build_player("Player", null, FRAME, Vector2i(12, 23), TILE) as RpgPlatformPlayer
	RpgSceneRouter._set_facing(player, "left")
	t.eq(player.facing, -1)
	RpgSceneRouter._set_facing(player, "1")
	t.eq(player.facing, 1, "a saved facing is its number as text")
	RpgSceneRouter._set_facing(player, "-1")
	t.eq(player.facing, -1)
	RpgSceneRouter._set_facing(player, "down")
	t.eq(player.facing, -1, "an unknown word changes nothing")
	player.free()
	var top_down := RpgActor.new()
	RpgSceneRouter._set_facing(top_down, "up")
	t.eq(top_down.facing, "up", "a top-down actor is set as before")
	top_down.free()
	var door := RpgDoor.new()
	door.side_view = true
	door._ready()
	t.ok(door.require_interact, "a side-view door is entered on purpose")
	door.free()

# ---------------------------------------------------------------- the camera

func test_a_room_has_one_enabled_camera_and_it_keeps_inside_the_room(t) -> void:
	var room: Room = await _room()
	var camera := ObjectsRecipe.build_camera(TILE) as RpgSideCamera
	room.root.add_child(camera)
	var bounds := Rect2(0, 0, 40 * TILE, 23 * TILE)
	camera.set_limits(bounds)
	camera.snap_to_target()
	var enabled := 0
	for node in room.root.find_children("*", "Camera2D", true, false):
		if (node as Camera2D).enabled:
			enabled += 1
	t.eq(enabled, 1, "exactly one enabled camera: the room's")
	t.eq(room.player.find_children("*", "Camera2D", true, false).size(), 0)
	t.eq(camera.limits(), bounds, "its limits are the room's")
	t.eq(camera.find_target(), room.player)
	t.eq(camera.global_position, room.player.global_position + Vector2(1.5 * TILE, -1.5 * TILE), "ahead of the facing, above the feet")
	room.player.set_facing(-1)
	var before := camera.global_position.x
	await room.frames(30)
	t.ok(camera.global_position.x < before - TILE, "it follows the look to the left")
	camera.slide_from(Vector2(900, 100), 0.1)
	t.ok(camera.sliding())
	t.eq(camera.global_position, Vector2(900, 100))
	await room.frames(12)
	t.ok(not camera.sliding() and camera.global_position.distance_to(camera.wanted()) < 2.0, "the slide ends on the target")
	room.close()

# ---------------------------------------------------------------- the dock

class SideRoot extends Node2D:
	var side_view := true

func test_the_dock_drops_an_object_onto_the_floor_of_a_side_view_room(t) -> void:
	var root := SideRoot.new()
	var layer := TileMapLayer.new()
	layer.tile_set = PlatformTests.tileset()
	root.add_child(layer)
	for x in 20:
		layer.set_cell(Vector2i(x, FLOOR_Y), 0, PlatformTests.GROUND)
	layer.set_cell(Vector2i(4, 6), 0, PlatformTests.ONE_WAY)
	layer.set_cell(Vector2i(8, 7), 0, PlatformTests.LADDER)
	t.ok(Placement.is_side_view(root))
	t.eq(Placement.floor_below(root, Vector2(50, 20)), Vector2(50, FLOOR_Y * TILE), "down to the floor")
	t.eq(Placement.floor_below(root, Vector2(70, 20)), Vector2(70, 6 * TILE), "a platform is a floor too")
	t.eq(Placement.floor_below(root, Vector2(70, 120)), Vector2(70, FLOOR_Y * TILE), "from under the platform: the ground")
	t.eq(Placement.floor_below(root, Vector2(130, 20)), Vector2(130, FLOOR_Y * TILE), "a ladder is not a floor")
	t.eq(Placement.floor_below(root, Vector2(900, 20)), Vector2(900, 20), "nothing below: where it was dropped")
	var placement := Placement.new()
	var thing := Node2D.new()
	var plan: Dictionary = placement.plan(thing, root, {}, null, Vector2(50, 20))
	t.eq(plan["position"], Vector2(50, FLOOR_Y * TILE))
	var top_down := Node2D.new()
	top_down.add_child(layer.duplicate())
	t.ok(not Placement.is_side_view(top_down))
	t.eq(placement.plan(thing, top_down, {}, null, Vector2(50, 20))["position"], Vector2(50, 20), "a top-down map is as before")
	thing.free()
	top_down.free()
	root.free()
