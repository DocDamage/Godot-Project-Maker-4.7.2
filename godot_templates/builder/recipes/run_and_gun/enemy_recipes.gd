extends RefCounted
## The enemies of a run and gun and the weapon pickup, as scenes under
## generated/scenes/run_and_gun/: enemies/runner.tscn, sniper.tscn, turret.tscn, jumper.tscn,
## wall_cannon.tscn and weapon_pickup.tscn.
##
## The ENEMY pictures of the packs are shared out: one named a turret (or cannon, tower) is
## the turret and the wall cannon; the others are the runner, the sniper and the jumper, in
## the order of their size and their ids (a pack with one such picture uses it for all three).
## A behaviour without a picture gets a drawn shape. The pickup shows the picture the packs
## name after its weapon (`weapon_pickup_laser`), else a tinted one. The three bosses
## (boss_wall.tscn, boss_walker.tscn, boss_flyer.tscn) are the BOSS picture, else the largest
## ENEMY picture two and a half times as large, else a drawn shape.

const RECIPE_VERSION := 2

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const ActorBuild := preload("../../lib/actor_build.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const MvBuild := preload("../metroidvania/metroidvania_build.gd")
const RngBuild := preload("run_and_gun_build.gd")

const BEHAVIOURS: Array[String] = ["runner", "sniper", "turret", "jumper", "wall_cannon"]
const WALKERS: Array[String] = ["runner", "sniper", "jumper"]
const TURRET_WORDS: Array[String] = ["turret", "cannon", "tower"]
const WEAPONS: Array[String] = ["machine_gun", "spread", "laser", "flame"]
## The words of a file that name a weapon.
const WEAPON_WORDS := {"machine_gun": ["machinegun", "machine_gun", "machine"], "spread": ["spread", "shotgun"],
	"laser": ["laser", "beam"], "flame": ["flame", "fire"]}
## health, points.
const STATS := {
	"runner": [1, 100],
	"sniper": [2, 200],
	"turret": [4, 300],
	"jumper": [1, 150],
	"wall_cannon": [5, 400],
}
const SHAPES := {
	"runner": Color(0.85, 0.3, 0.3),
	"sniper": Color(0.3, 0.6, 0.4),
	"turret": Color(0.6, 0.6, 0.7),
	"jumper": Color(0.85, 0.6, 0.2),
	"wall_cannon": Color(0.5, 0.5, 0.6),
}

static func scene_path(behaviour: String) -> String:
	return RngBuild.ENEMIES + behaviour + ".tscn"

static func _named(ctx: BuildContext, asset: Dictionary, words: Array) -> bool:
	var id := JsonUtil.to_str(asset.get("id", "")).to_lower()
	var tags := JsonUtil.to_array(ctx.catalog.effective(asset).get("tags", []))
	for word: Variant in words:
		if id.contains(JsonUtil.to_str(word)) or tags.has(word):
			return true
	return false

static func _area(ctx: BuildContext, asset: Dictionary) -> int:
	var frame := ArcadeBuild.frame_size(ctx, asset)
	return frame.x * frame.y

## Who is what: behaviour -> asset ({} for one without a picture).
static func roster(ctx: BuildContext) -> Dictionary:
	var out := {}
	for behaviour in BEHAVIOURS:
		out[behaviour] = {}
	var walkers: Array[Dictionary] = []
	for a in ArcadeBuild.assets(ctx, "ENEMY"):
		if _named(ctx, a, TURRET_WORDS):
			if JsonUtil.to_dict(out["turret"]).is_empty():
				out["turret"] = a
				out["wall_cannon"] = a
		else:
			walkers.append(a)
	walkers.sort_custom(func(x: Dictionary, y: Dictionary) -> bool:
		var ax := _area(ctx, x)
		var ay := _area(ctx, y)
		return ax < ay or (ax == ay and JsonUtil.to_str(x["id"]) < JsonUtil.to_str(y["id"])))
	for i in WALKERS.size():
		if not walkers.is_empty():
			out[WALKERS[i]] = walkers[i % walkers.size()]
	return out

## The picture of each weapon's pickup: weapon -> asset, for the weapons the packs name.
static func pickup_assets(ctx: BuildContext) -> Dictionary:
	var out := {}
	for role: String in ["POWERUP", "ITEM"]:
		for a in ArcadeBuild.assets(ctx, role):
			for weapon in WEAPONS:
				if not out.has(weapon) and _named(ctx, a, JsonUtil.to_array(WEAPON_WORDS[weapon])):
					out[weapon] = a
	return out

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	for behaviour in BEHAVIOURS:
		out.append(scene_path(behaviour))
	out.append(RngBuild.PICKUP_PATH)
	for kind in RngBuild.BOSS_KINDS:
		out.append(RngBuild.boss_path(kind))
	return out

func input_hash(ctx: BuildContext) -> String:
	var who := roster(ctx)
	var ids := {}
	for behaviour: String in who:
		ids[behaviour] = JsonUtil.to_dict(who[behaviour]).get("id", "")
	var capsules := {}
	var found := pickup_assets(ctx)
	for weapon: String in found:
		capsules[weapon] = JsonUtil.to_dict(found[weapon]).get("id", "")
	ids["boss"] = boss_asset(ctx).get("id", "")
	return ctx.stable_hash({"v": RECIPE_VERSION, "roster": ids, "pickups": capsules,
		"view": ArcadeBuild.view(ctx), "tile": ArcadeBuild.tile(ctx)})

## The scene of one enemy. `frames` null draws a shape `frame` px large.
static func build_enemy(behaviour: String, frames: SpriteFrames, frame: Vector2i, origin: Vector2i, view: Vector2i,
		tile: int, explosion: PackedScene) -> CharacterBody2D:
	var root := MvBuild.body(behaviour.to_pascal_case(), RngBuild.ENEMY_DIR + behaviour + ".gd", frames, frame, origin, tile)
	MvBuild.set_layers(root, [RngBuild.ENEMY_LAYER], [RngBuild.WORLD_LAYER, RngBuild.ONE_WAY_LAYER])
	var stats: Array = STATS[behaviour]
	root.set("health", JsonUtil.to_int(stats[0]))
	root.set("points", JsonUtil.to_int(stats[1]))
	root.set("view", Vector2(view))
	root.set("explosion_scene", explosion)
	root.z_index = 4
	if frames == null:
		# no picture: a drawn shape the size of the body, standing on its feet
		var size := MvBuild.body_size(frame, tile)
		var shape_color: Color = SHAPES[behaviour]
		var shape := ArcadeBuild.stand_in("Shape", size, shape_color)
		shape.position = Vector2(0.0, -size.y * 0.5)
		SceneUtil.add(root, shape, root, "Shape")
	return root

const BOSS_SHAPES := {"wall": Color(0.45, 0.45, 0.55), "walker": Color(0.75, 0.3, 0.3), "flyer": Color(0.4, 0.55, 0.75)}

## The picture the bosses are made of: the BOSS asset, else the largest ENEMY one ({} for none).
static func boss_asset(ctx: BuildContext) -> Dictionary:
	var own := ArcadeBuild.chosen(ctx, "BOSS", "boss")
	if not own.is_empty():
		return own
	var best := {}
	for a in ArcadeBuild.assets(ctx, "ENEMY"):
		if best.is_empty() or _area(ctx, a) > _area(ctx, best):
			best = a
	return best

## The scene of the boss of `kind`. `frames` null draws a shape; `zoom` enlarges the picture.
## The two that stand have their feet at the origin; the flyer its middle.
static func build_boss(kind: String, frames: SpriteFrames, frame: Vector2i, view: Vector2i, tile: int,
		explosion: PackedScene, zoom: float = 1.0) -> Node2D:
	var root := Node2D.new()
	root.name = "Boss" + kind.to_pascal_case()
	SceneUtil.attach_script(root, RngBuild.BOSS_SCRIPT)
	root.set("kind", kind)
	var size := Vector2(frame) * zoom
	root.set("hit_radius", maxf(8.0, minf(size.x, size.y) * 0.45))
	root.set("bullet_speed", tile * 6.875)
	root.set("explosion_scene", explosion)
	root.set("sweep_px", view.x * 0.22)
	root.set("walk_px", view.x * 0.3)
	root.z_index = 3
	var lift := Vector2.ZERO if kind == "flyer" else Vector2(0.0, -size.y * 0.5)
	if frames == null:
		var shape_color: Color = BOSS_SHAPES[kind]
		var shape := ArcadeBuild.stand_in("Visual", size, shape_color)
		shape.position = lift
		SceneUtil.add(root, shape, root, "Visual")
		return root
	var visual := AnimatedSprite2D.new()
	visual.sprite_frames = frames
	for anim: String in ["idle_left", "idle_side", "idle", "idle_down", "walk_left", "walk_down"]:
		if frames.has_animation(anim):
			visual.animation = anim
			break
	visual.scale = Vector2(zoom, zoom)
	visual.position = lift
	SceneUtil.add(root, visual, root, "Visual")
	return root

## The pickup's scene. `pictures` is weapon -> Texture2D.
static func build_pickup(pictures: Dictionary, view: Vector2i, tile: int) -> Node2D:
	var root := Node2D.new()
	root.name = "WeaponPickup"
	SceneUtil.attach_script(root, RngBuild.PICKUP_SCRIPT)
	root.set("view", Vector2(view))
	root.set("speed", tile * 3.75)
	root.set("sway", float(tile))
	root.set("pick_radius", tile * 0.9)
	root.set("hit_radius", tile * 0.5)
	root.set("textures", pictures)
	root.z_index = 6
	var visual := Sprite2D.new()
	var first: Texture2D = null
	for weapon in WEAPONS:
		if first == null and pictures.has(weapon):
			first = pictures[weapon]
	if first == null:
		var drawn := PlaceholderTexture2D.new()
		drawn.size = Vector2(tile * 0.75, tile * 0.75)
		first = drawn
	visual.texture = first
	SceneUtil.add(root, visual, root, "Visual")
	return root

func _save(ctx: BuildContext, node: Node, path: String, issues: Array) -> void:
	var err := SceneUtil.save_scene(node, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var view := ArcadeBuild.view(ctx)
	var tile := ArcadeBuild.tile(ctx)
	var explosion := load(RngBuild.EXPLOSION_PATH) as PackedScene if ResourceLoader.exists(RngBuild.EXPLOSION_PATH) else null
	var who := roster(ctx)
	for behaviour in BEHAVIOURS:
		var asset := JsonUtil.to_dict(who[behaviour])
		var frame := Vector2i(tile, tile if behaviour in ["turret", "wall_cannon"] else tile * 2)
		var origin := Vector2i(frame.x / 2, frame.y - 1)
		if not asset.is_empty():
			var fo := ActorBuild.frame_and_origin(ctx.catalog.effective(asset))
			frame = fo["frame"]
			origin = fo["origin"]
		_save(ctx, build_enemy(behaviour, ArcadeBuild.frames_of(ctx, asset), frame, origin, view, tile, explosion), scene_path(behaviour), issues)
	var pictures := {}
	var found := pickup_assets(ctx)
	for weapon: String in found:
		var texture := ArcadeBuild.first_frame(ctx, JsonUtil.to_dict(found[weapon]))
		if texture != null:
			pictures[weapon] = texture
	_save(ctx, build_pickup(pictures, view, tile), RngBuild.PICKUP_PATH, issues)
	var chief := boss_asset(ctx)
	var own_boss := not chief.is_empty() and JsonUtil.to_str(ctx.catalog.effective(chief).get("role", "")) == "BOSS"
	var chief_frame := ArcadeBuild.frame_size(ctx, chief) if not chief.is_empty() else Vector2i(tile * 3, tile * 3)
	for kind in RngBuild.BOSS_KINDS:
		_save(ctx, build_boss(kind, ArcadeBuild.frames_of(ctx, chief), chief_frame, view, tile, explosion,
			1.0 if chief.is_empty() else (2.0 if own_boss else 2.5)), RngBuild.boss_path(kind), issues)
	return issues
