extends RefCounted
## The enemies of a shoot-em-up and the power-up capsule, as scenes under
## generated/scenes/shmup/: enemies/popcorn_NN.tscn (one per small enemy picture, four at
## most), enemies/turret.tscn, enemies/asteroid.tscn, enemies/carrier.tscn and powerup.tscn.
##
## The ENEMY pictures of the packs are shared out over the behaviours: one named a turret (or
## cannon, tower) is the turret, the largest of the others is the carrier when there are two
## sizes, and the rest are the small ones. The asteroid is a HAZARD (or an ENEMY) named
## asteroid, rock or meteor. A behaviour without a picture gets a drawn shape; a carrier
## without one is the small enemy, twice as large.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const ShmupBuild := preload("shmup_build.gd")

const DIR := "res://generated/scenes/shmup/enemies/"
const POWERUP_PATH := "res://generated/scenes/shmup/powerup.tscn"
const ENEMY_DIR := ShmupBuild.DIR + "enemies/"
const SCRIPTS := {
	"popcorn": ENEMY_DIR + "popcorn.gd",
	"turret": ENEMY_DIR + "turret.gd",
	"asteroid": ENEMY_DIR + "asteroid.gd",
	"carrier": ENEMY_DIR + "carrier.gd",
}
const POWERUP_SCRIPT := ShmupBuild.DIR + "powerup.gd"
const MAX_POPCORN := 4
const TURRET_WORDS: Array[String] = ["turret", "cannon", "tower"]
const ROCK_WORDS: Array[String] = ["asteroid", "rock", "meteor"]
## health, points, tiles a second.
const STATS := {
	"popcorn": [1, 100, 3.5],
	"turret": [3, 300, 0.0],
	"asteroid": [4, 50, 0.0],
	"carrier": [12, 800, 1.5],
}
## The colours of the drawn shapes.
const SHAPES := {
	"popcorn": Color(0.9, 0.3, 0.35),
	"turret": Color(0.6, 0.6, 0.7),
	"asteroid": Color(0.55, 0.45, 0.4),
	"carrier": Color(0.7, 0.3, 0.6),
}
## The kinds the POWERUP pictures of the packs are given to, in this order.
const POWERUP_ORDER: Array[String] = ["weapon_up", "bomb", "shield", "life", "points"]

static func popcorn_path(number: int) -> String:
	return DIR + "popcorn_%02d.tscn" % (number + 1)

static func scene_path(behaviour: String) -> String:
	return popcorn_path(0) if behaviour == "popcorn" else DIR + behaviour + ".tscn"

static func _named(ctx: BuildContext, asset: Dictionary, words: Array[String]) -> bool:
	var id := JsonUtil.to_str(asset.get("id", "")).to_lower()
	var tags := JsonUtil.to_array(ctx.catalog.effective(asset).get("tags", []))
	for word in words:
		if id.contains(word) or tags.has(word):
			return true
	return false

static func _area(ctx: BuildContext, asset: Dictionary) -> int:
	var frame := ShmupBuild.frame_size(ctx, asset)
	return frame.x * frame.y

## Who is what: {"popcorn": [asset, ...] (may be empty), "turret": asset, "asteroid": asset,
## "carrier": asset}; {} for a behaviour without a picture of its own.
static func roster(ctx: BuildContext) -> Dictionary:
	var out := {"popcorn": [], "turret": {}, "asteroid": {}, "carrier": {}}
	var rest: Array[Dictionary] = []
	for a in ShmupBuild.assets(ctx, "ENEMY"):
		if _named(ctx, a, ROCK_WORDS) and JsonUtil.to_dict(out["asteroid"]).is_empty():
			out["asteroid"] = a
		elif _named(ctx, a, TURRET_WORDS) and JsonUtil.to_dict(out["turret"]).is_empty():
			out["turret"] = a
		else:
			rest.append(a)
	for a in ShmupBuild.assets(ctx, "HAZARD"):
		if _named(ctx, a, ROCK_WORDS) and JsonUtil.to_dict(out["asteroid"]).is_empty():
			out["asteroid"] = a
	rest.sort_custom(func(x: Dictionary, y: Dictionary) -> bool:
		var ax := _area(ctx, x)
		var ay := _area(ctx, y)
		return ax < ay or (ax == ay and JsonUtil.to_str(x["id"]) < JsonUtil.to_str(y["id"])))
	if rest.size() >= 2 and _area(ctx, rest[rest.size() - 1]) > _area(ctx, rest[0]):
		out["carrier"] = rest.pop_back()
	out["popcorn"] = rest.slice(0, MAX_POPCORN)
	return out

## How many small-enemy scenes there are (one at least: the drawn one).
static func popcorn_count(ctx: BuildContext) -> int:
	return maxi(1, JsonUtil.to_array(roster(ctx)["popcorn"]).size())

func outputs(ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	for i in popcorn_count(ctx):
		out.append(popcorn_path(i))
	for behaviour: String in ["turret", "asteroid", "carrier"]:
		out.append(scene_path(behaviour))
	out.append(POWERUP_PATH)
	return out

func input_hash(ctx: BuildContext) -> String:
	var who := roster(ctx)
	var ids := {}
	for behaviour: String in who:
		var entry: Variant = who[behaviour]
		if entry is Array:
			var list: Array = entry
			ids[behaviour] = list.map(func(a: Dictionary) -> String: return JsonUtil.to_str(a["id"]))
		else:
			ids[behaviour] = JsonUtil.to_dict(entry).get("id", "")
	var capsules: Array = []
	for a in ShmupBuild.assets(ctx, "POWERUP"):
		capsules.append(a["id"])
	return ctx.stable_hash({"v": RECIPE_VERSION, "roster": ids, "powerups": capsules,
		"orientation": ShmupBuild.orientation(ctx), "view": ShmupBuild.view(ctx), "tile": ShmupBuild.tile(ctx)})

## The picture of an enemy: its sprite, or a drawn shape `size` px large. A pack draws an enemy
## ship as it comes at the player in a game that scrolls up, looking down; for a game that
## scrolls right it is turned a quarter, like the player's ship, and looks left.
static func _visual(frames: SpriteFrames, is_ship: bool, way: String, shape: Color, size: Vector2) -> Node2D:
	if frames == null:
		return ArcadeBuild.stand_in("Visual", size, shape)
	var visual := AnimatedSprite2D.new()
	visual.sprite_frames = frames
	var first := RpgShmupShip.bank_animation(frames, 0.0, way)
	if first != &"":
		visual.animation = first
	if is_ship and way == "horizontal":
		visual.rotation = PI * 0.5
	return visual

## The scene of one enemy. `frames` null draws a shape; `zoom` enlarges the picture (a carrier
## made of the small enemy's).
static func build_enemy(behaviour: String, frames: SpriteFrames, frame: Vector2i, is_ship: bool, way: String,
		view: Vector2i, tile: int, explosion: PackedScene, powerup: PackedScene, zoom: float = 1.0) -> Node2D:
	var root := Node2D.new()
	root.name = behaviour.to_pascal_case()
	SceneUtil.attach_script(root, JsonUtil.to_str(SCRIPTS[behaviour]))
	var stats: Array = STATS[behaviour]
	root.set("health", JsonUtil.to_int(stats[0]))
	root.set("points", JsonUtil.to_int(stats[1]))
	root.set("speed", tile * JsonUtil.to_float(stats[2]))
	root.set("orientation", way)
	root.set("view", Vector2(view))
	root.set("bullet_speed", tile * 5.5)
	root.set("hit_radius", maxf(3.0, minf(frame.x, frame.y) * 0.4 * zoom))
	root.set("explosion_scene", explosion)
	root.set("powerup_scene", powerup)
	var shape: Color = SHAPES[behaviour]
	var visual := _visual(frames, is_ship, way, shape, Vector2(frame))
	visual.scale = Vector2(zoom, zoom)
	SceneUtil.add(root, visual, root, "Visual")
	return root

## The capsule's scene. `pictures` are the POWERUP textures of the packs, given to the kinds in
## POWERUP_ORDER; with none a drawn square is tinted by the kind.
static func build_powerup(pictures: Array[Texture2D], way: String, view: Vector2i, tile: int) -> Node2D:
	var root := Node2D.new()
	root.name = "Powerup"
	SceneUtil.attach_script(root, POWERUP_SCRIPT)
	root.set("orientation", way)
	root.set("view", Vector2(view))
	root.set("speed", tile * 2.0)
	root.set("pick_radius", tile * 0.9)
	root.z_index = 3
	var visual := Sprite2D.new()
	var by_kind := {}
	if pictures.is_empty():
		visual.texture = PlaceholderTexture2D.new()
		(visual.texture as PlaceholderTexture2D).size = Vector2(tile * 0.75, tile * 0.75)
	else:
		visual.texture = pictures[0]
		for i in mini(pictures.size(), POWERUP_ORDER.size()):
			by_kind[POWERUP_ORDER[i]] = pictures[i]
	root.set("textures", by_kind)
	SceneUtil.add(root, visual, root, "Visual")
	return root

func _save(ctx: BuildContext, node: Node, path: String, issues: Array) -> void:
	var err := SceneUtil.save_scene(node, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

func _is_ship(ctx: BuildContext, asset: Dictionary) -> bool:
	return not asset.is_empty() and JsonUtil.to_array(ctx.catalog.effective(asset).get("tags", [])).has("ship")

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var way := ShmupBuild.orientation(ctx)
	var view := ShmupBuild.view(ctx)
	var tile := ShmupBuild.tile(ctx)
	var pictures: Array[Texture2D] = []
	for a in ShmupBuild.assets(ctx, "POWERUP"):
		var texture := ShmupBuild.first_frame(ctx, a)
		if texture != null:
			pictures.append(texture)
	_save(ctx, build_powerup(pictures, way, view, tile), POWERUP_PATH, issues)
	var explosion := load(ShmupBuild.EXPLOSION_PATH) as PackedScene if ResourceLoader.exists(ShmupBuild.EXPLOSION_PATH) else null
	var powerup := load(POWERUP_PATH) as PackedScene if ResourceLoader.exists(POWERUP_PATH) else null
	var who := roster(ctx)
	var small: Array = who["popcorn"]
	var plain := Vector2i(tile, tile)
	for i in popcorn_count(ctx):
		var asset: Dictionary = small[i] if i < small.size() else {}
		var frame := ShmupBuild.frame_size(ctx, asset) if not asset.is_empty() else plain
		_save(ctx, build_enemy("popcorn", ShmupBuild.frames_of(ctx, asset), frame, _is_ship(ctx, asset), way, view, tile, explosion, powerup), popcorn_path(i), issues)
	for behaviour: String in ["turret", "asteroid"]:
		var asset := JsonUtil.to_dict(who[behaviour])
		var frame := ShmupBuild.frame_size(ctx, asset) if not asset.is_empty() else plain * (2 if behaviour == "asteroid" else 1)
		_save(ctx, build_enemy(behaviour, ShmupBuild.frames_of(ctx, asset), frame, _is_ship(ctx, asset), way, view, tile, explosion, powerup), scene_path(behaviour), issues)
	# the carrier: its own picture, else the small enemy's twice as large, else a drawn shape
	var big := JsonUtil.to_dict(who["carrier"])
	var zoom := 1.0
	if big.is_empty() and not small.is_empty():
		big = small[0]
		zoom = 2.0
	var big_frame := ShmupBuild.frame_size(ctx, big) if not big.is_empty() else plain * 3
	var carrier := build_enemy("carrier", ShmupBuild.frames_of(ctx, big), big_frame, _is_ship(ctx, big), way, view, tile, explosion, powerup, zoom)
	carrier.set("escort_scene", load(popcorn_path(0)) as PackedScene if ResourceLoader.exists(popcorn_path(0)) else null)
	carrier.set("drop", "weapon:spread")
	_save(ctx, carrier, scene_path("carrier"), issues)
	return issues
