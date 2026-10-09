extends RefCounted
## The side-view characters of the metroidvania. Not a recipe of its own: actor_recipes.gd builds
## every actor scene and asks this helper for the node tree when the archetype is metroidvania
## (ACTOR_BUILDERS), so the scenes keep their paths (generated/scenes/actors/player.tscn, ...).

const SceneUtil := preload("../../lib/scene_util.gd")
const MvBuild := preload("metroidvania_build.gd")

const PLAYER_SCRIPT := MvBuild.DIR + "platform_player.gd"
const INPUT_SCRIPT := MvBuild.DIR + "platform_input.gd"

## The root of an actor scene, or null for a kind this archetype builds like the top-down one.
static func build_actor(kind: String, root_name: String, frames: SpriteFrames, frame: Vector2i, origin: Vector2i, tile: int) -> CharacterBody2D:
	if kind == "player":
		return build_player(root_name, frames, frame, origin, tile)
	return null

## The player: the platform body with its input, health, hurtbox, attack area and the area that
## finds what is beside it. It has no camera: the room owns the camera.
static func build_player(root_name: String, frames: SpriteFrames, frame: Vector2i, origin: Vector2i, tile: int) -> CharacterBody2D:
	var root := MvBuild.body(root_name, PLAYER_SCRIPT, frames, frame, origin, tile)
	MvBuild.set_layers(root, [2], [1, MvBuild.ONE_WAY_LAYER])  # player; world and one-way platforms
	root.add_to_group("player", true)
	var input := Node.new()
	input.name = "PlatformInput"
	SceneUtil.attach_script(input, INPUT_SCRIPT)
	root.get_node("Components").add_child(input)
	MvBuild.add_health(root)
	MvBuild.add_hurtbox(root, "player", 9, MvBuild.PLAYER_INVULN_S, frame, tile)
	var body := MvBuild.body_size(frame, tile)
	MvBuild.add_hitbox(root, "player", 7, 10, frame, tile, Vector2(tile * 1.1, maxf(tile * 0.9, body.y * 0.8)), body.x * 0.5 + tile * 0.5)
	var interaction := Area2D.new()
	interaction.name = "Interaction"
	MvBuild.set_layers(interaction, [], [4, 5])  # npcs and interactables
	interaction.monitorable = true  # static bodies (chests, signs) are only found by monitorable areas
	interaction.position = MvBuild.body_center(frame, tile)
	interaction.add_child(MvBuild.rect_shape(Vector2(body.x + tile * 2.0, body.y)))
	root.add_child(interaction)
	return root
