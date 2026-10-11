extends RefCounted
## The soldier of a run and gun (generated/scenes/run_and_gun/soldier.tscn) from the PLAYER
## sprite, with its gun, its input and a muzzle flash; the grenade it throws (grenade.tscn, a
## drawn one) and the explosion (explosion.tscn, from the EXPLOSION sprite).

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const ActorBuild := preload("../../lib/actor_build.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const MvBuild := preload("../metroidvania/metroidvania_build.gd")
const RngBuild := preload("run_and_gun_build.gd")

const FLASH := Color(1.0, 0.95, 0.5)
const GRENADE := Color(0.25, 0.4, 0.2)

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([RngBuild.EXPLOSION_PATH, RngBuild.GRENADE_PATH, RngBuild.SOLDIER_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"soldier": ArcadeBuild.chosen(ctx, "PLAYER", "player").get("id", ""),
		"explosion": ArcadeBuild.chosen(ctx, "EXPLOSION", "explosion").get("id", ""),
		"view": ArcadeBuild.view(ctx),
		"tile": ArcadeBuild.tile(ctx),
		"health": RngBuild.health(ctx),
		"left_edge_kills": RngBuild.left_edge_kills(ctx),
	})

static func build_explosion(frames: SpriteFrames) -> AnimatedSprite2D:
	var root := AnimatedSprite2D.new()
	root.name = "Explosion"
	SceneUtil.attach_script(root, ArcadeBuild.EXPLOSION_SCRIPT)
	root.sprite_frames = frames
	root.z_index = 6
	return root

## The grenade: a drawn one, with the blast of `explosion`.
static func build_grenade(tile: int, explosion: PackedScene) -> Node2D:
	var root := Node2D.new()
	root.name = "Grenade"
	SceneUtil.attach_script(root, RngBuild.GRENADE_SCRIPT)
	root.set("gravity", tile * 37.5)
	root.set("blast_radius", tile * 2.5)
	root.set("explosion_scene", explosion)
	root.z_index = 6
	var size := maxf(4.0, tile * 0.3)
	SceneUtil.add(root, ArcadeBuild.stand_in("Visual", Vector2(size, size), GRENADE), root, "Visual")
	return root

## The soldier scene. `frame` and `origin` are those of its sprite, `view` the screen in px.
static func build_soldier(frames: SpriteFrames, frame: Vector2i, origin: Vector2i, view: Vector2i, tile: int,
		explosion: PackedScene, grenade: PackedScene, health: int = 1, left_edge_kills: bool = true) -> CharacterBody2D:
	var root := MvBuild.body("Soldier", RngBuild.SOLDIER_SCRIPT, frames, frame, origin, tile)
	MvBuild.set_layers(root, [RngBuild.PLAYER_LAYER], [RngBuild.WORLD_LAYER, RngBuild.ONE_WAY_LAYER])
	root.set("max_health", health)
	root.set("left_edge_kills", left_edge_kills)
	root.set("view", Vector2(view))
	root.set("explosion_scene", explosion)
	root.set("grenade_scene", grenade)
	root.z_index = 5
	var gun := Node.new()
	SceneUtil.attach_script(gun, RngBuild.GUN_SCRIPT)
	gun.set("bullet_speed", tile * 15.0)
	SceneUtil.add(root, gun, root, "Gun")
	var input := Node.new()
	SceneUtil.attach_script(input, RngBuild.INPUT_SCRIPT)
	SceneUtil.add(root, input, root, "Input")
	var flash := ArcadeBuild.stand_in("Muzzle", Vector2(maxf(4.0, tile * 0.4), maxf(2.0, tile * 0.2)), FLASH)
	flash.visible = false
	SceneUtil.add(root, flash, root, "Muzzle")
	return root

func _save(ctx: BuildContext, node: Node, path: String, issues: Array) -> PackedScene:
	var err := SceneUtil.save_scene(node, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
		return null
	return load(path) as PackedScene

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var tile := ArcadeBuild.tile(ctx)
	var burst := ArcadeBuild.chosen(ctx, "EXPLOSION", "explosion")
	var explosion := _save(ctx, build_explosion(ArcadeBuild.frames_of(ctx, burst)), RngBuild.EXPLOSION_PATH, issues)
	var grenade := _save(ctx, build_grenade(tile, explosion), RngBuild.GRENADE_PATH, issues)
	var player := ArcadeBuild.chosen(ctx, "PLAYER", "player")
	var frame := Vector2i(tile, tile * 2)
	var origin := Vector2i(tile / 2, tile * 2 - 1)
	if not player.is_empty():
		var fo := ActorBuild.frame_and_origin(ctx.catalog.effective(player))
		frame = fo["frame"]
		origin = fo["origin"]
	var soldier := build_soldier(ArcadeBuild.frames_of(ctx, player), frame, origin, ArcadeBuild.view(ctx), tile,
		explosion, grenade, RngBuild.health(ctx), RngBuild.left_edge_kills(ctx))
	_save(ctx, soldier, RngBuild.SOLDIER_PATH, issues)
	return issues
