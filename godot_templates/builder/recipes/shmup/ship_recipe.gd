extends RefCounted
## The ship of a shoot-em-up (generated/scenes/shmup/ship.tscn) from the PLAYER sprite, and
## the explosion (generated/scenes/shmup/explosion.tscn) from the EXPLOSION sprite. The ship is
## an RpgShmupShip with its picture ("Visual"), a one-pixel body, a weapon, its bombs and its
## input. A ship (an asset tagged `ship`) is drawn looking up and is turned to the right for a
## game that scrolls sideways; any other picture (the hero of an RPG pack) is left as it stands.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ShmupBuild := preload("shmup_build.gd")

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([ShmupBuild.EXPLOSION_PATH, ShmupBuild.SHIP_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"ship": ShmupBuild.chosen(ctx, "PLAYER", "player").get("id", ""),
		"turn": is_ship(ctx, ShmupBuild.chosen(ctx, "PLAYER", "player")),
		"explosion": ShmupBuild.chosen(ctx, "EXPLOSION", "explosion").get("id", ""),
		"orientation": ShmupBuild.orientation(ctx),
		"view": ShmupBuild.view(ctx),
		"tile": ShmupBuild.tile(ctx),
	})

## True for an asset the packs call a ship (the tag `ship`): its picture looks up.
static func is_ship(ctx: BuildContext, asset: Dictionary) -> bool:
	if asset.is_empty():
		return false
	return JsonUtil.to_array(ctx.catalog.effective(asset).get("tags", [])).has("ship")

## The explosion scene: the animation plays once and the node is gone.
static func build_explosion(frames: SpriteFrames) -> AnimatedSprite2D:
	var root := AnimatedSprite2D.new()
	root.name = "Explosion"
	SceneUtil.attach_script(root, ShmupBuild.EXPLOSION_SCRIPT)
	root.sprite_frames = frames
	root.z_index = 5
	return root

## The ship scene. `frame` is the size of one frame of its picture, `view` the screen in px.
static func build_ship(frames: SpriteFrames, frame: Vector2i, way: String, view: Vector2i, tile: int, explosion: PackedScene, turn: bool = true) -> CharacterBody2D:
	var root := CharacterBody2D.new()
	root.name = "Ship"
	root.motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	SceneUtil.attach_script(root, ShmupBuild.SHIP_SCRIPT)
	root.collision_layer = 0
	root.collision_mask = 0
	root.set_collision_layer_value(ShmupBuild.PLAYER_LAYER, true)
	root.set("orientation", way)
	root.set("speed", tile * ShmupBuild.SHIP_TILES_PER_S)
	root.set("play_area", RpgShmupMath.play_area(Vector2(view), way))
	root.set("half_size", Vector2(frame) * 0.5)
	root.set("explosion_scene", explosion)
	var visual := AnimatedSprite2D.new()
	visual.sprite_frames = frames
	if frames != null:
		var first := RpgShmupShip.bank_animation(frames, 0.0, way)
		if first != &"":
			visual.animation = first
	if way == "horizontal" and turn:
		visual.rotation = PI * 0.5  # the picture looks up; the ship flies to the right
	SceneUtil.add(root, visual, root, "Visual")
	var body := CollisionShape2D.new()
	var point := CircleShape2D.new()
	point.radius = 1.0
	body.shape = point
	SceneUtil.add(root, body, root, "Body")
	for part: Array in [["Weapon", ShmupBuild.WEAPON_SCRIPT], ["Bomb", ShmupBuild.BOMB_SCRIPT], ["Input", ShmupBuild.INPUT_SCRIPT]]:
		var node := Node.new()
		SceneUtil.attach_script(node, JsonUtil.to_str(part[1]))
		SceneUtil.add(root, node, root, JsonUtil.to_str(part[0]))
	(root.get_node("Weapon") as RpgShmupWeapon).bullet_speed = tile * 16.0
	return root

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var burst := ShmupBuild.chosen(ctx, "EXPLOSION", "explosion")
	var err := SceneUtil.save_scene(build_explosion(ShmupBuild.frames_of(ctx, burst)), ShmupBuild.EXPLOSION_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": ShmupBuild.EXPLOSION_PATH, "err": err}, ShmupBuild.EXPLOSION_PATH))
	var player := ShmupBuild.chosen(ctx, "PLAYER", "player")
	var explosion := load(ShmupBuild.EXPLOSION_PATH) as PackedScene if ResourceLoader.exists(ShmupBuild.EXPLOSION_PATH) else null
	var ship := build_ship(ShmupBuild.frames_of(ctx, player), ShmupBuild.frame_size(ctx, player) if not player.is_empty() else Vector2i(16, 16),
		ShmupBuild.orientation(ctx), ShmupBuild.view(ctx), ShmupBuild.tile(ctx), explosion, is_ship(ctx, player))
	err = SceneUtil.save_scene(ship, ShmupBuild.SHIP_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": ShmupBuild.SHIP_PATH, "err": err}, ShmupBuild.SHIP_PATH))
	return issues
