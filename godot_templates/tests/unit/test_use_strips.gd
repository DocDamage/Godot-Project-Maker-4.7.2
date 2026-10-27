extends RefCounted
## The strips of a character using a tool (T18.10): added to the owner's SpriteFrames as
## `<tool>_<direction>` in a farm, as the player's `attack_<direction>` in a game of another kind
## when it has none, and nothing changes for a pack without them.

const Recipe := preload("res://builder/recipes/sprite_frames_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")
const Paths := preload("res://builder/lib/paths.gd")

func _walk(id: String, role: String, anims: Array) -> Dictionary:
	var specs := {}
	for anim_name: String in anims:
		specs[anim_name] = {"frames": [[0, 0], [1, 0], [2, 0]], "fps": 8.0}
	return {"id": id, "path": "icon.svg", "status": "OK", "detected": {"role": role, "usage": "sprite", "frame": [16, 24], "animations": specs}}

func _strip(id: String, tool: String, owner_id: String, frame: Array = [16, 16]) -> Dictionary:
	return {"id": id, "path": "icon.svg", "status": "UNUSED", "detected": {"role": "NONE", "usage": "sprite", "frame": frame, "tags": ["unused:use_anim", "use_anim:" + tool, "of:" + owner_id], "animations": {"idle_down": {"frames": [[0, 0], [1, 0], [2, 0]], "fps": 6.0}}}}

func _ctx(kind: String, assets: Array) -> BuildContext:
	var ctx := BuildContext.new("")
	ctx.config = {"archetype": kind}
	ctx.catalog = CatalogReader.new({"assets": assets})
	return ctx

func _frames(ctx: BuildContext, asset_id: String) -> SpriteFrames:
	var recipe := Recipe.new()
	recipe.build(ctx)
	var path := Paths.SPRITE_FRAMES_DIR + asset_id + ".tres"
	return ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_IGNORE) as SpriteFrames

func _clean(ids: Array) -> void:
	for asset_id: String in ids:
		DirAccess.remove_absolute(Paths.SPRITE_FRAMES_DIR + asset_id + ".tres")

func test_a_farmers_strips_are_its_tools_animations(t) -> void:
	var farmer := _walk("ranch.farmer_walk", "PLAYER", ["walk_down", "walk_left", "walk_right", "walk_up"])
	var ctx := _ctx("farm", [farmer, _strip("ranch.farmer_hoe_down", "hoe", "ranch.farmer_walk"), _strip("ranch.farmer_water_down", "water", "ranch.farmer_walk"), _strip("ranch.farmer_axe_down", "axe", "ranch.farmer_walk")])
	var frames := _frames(ctx, "ranch.farmer_walk")
	for anim_name: String in ["hoe_down", "water_down", "axe_down", "walk_down"]:
		t.ok(frames.has_animation(anim_name), anim_name)
	t.eq(frames.get_frame_count("hoe_down"), 3)
	var first := frames.get_frame_texture("hoe_down", 0) as AtlasTexture
	t.eq(first.margin, Rect2(0, 8, 0, 8), "a smaller frame stands on the walk's feet")
	t.eq(Recipe.new().use_strips(ctx).keys(), ["ranch.farmer_walk"])
	_clean(["ranch.farmer_walk", "ranch.farmer_hoe_down", "ranch.farmer_water_down", "ranch.farmer_axe_down"])

func test_the_hero_of_another_kind_swings_with_its_strip(t) -> void:
	var hero := _walk("pk.hero_walk", "PLAYER", ["walk_down", "walk_up"])
	var ctx := _ctx("turn_based", [hero, _strip("pk.hero_axe_down", "axe", "pk.hero_walk")])
	var frames := _frames(ctx, "pk.hero_walk")
	t.ok(frames.has_animation("attack_down") and not frames.has_animation("axe_down"), str(frames.get_animation_names()))
	var fighter := _walk("pk.knight_walk", "PLAYER", ["walk_down", "attack_down"])
	ctx = _ctx("arpg", [fighter, _strip("pk.knight_axe_down", "axe", "pk.knight_walk")])
	frames = _frames(ctx, "pk.knight_walk")
	t.eq(Array(frames.get_animation_names()), ["attack_down", "walk_down"], "a player with an attack keeps its own")
	_clean(["pk.hero_walk", "pk.hero_axe_down", "pk.knight_walk", "pk.knight_axe_down"])

func test_a_pack_without_strips_has_the_hash_it_had(t) -> void:
	var farmer := _walk("ranch.farmer_walk", "PLAYER", ["walk_down"])
	var recipe := Recipe.new()
	var plain := _ctx("farm", [farmer])
	var with_strip := _ctx("farm", [farmer, _strip("ranch.farmer_hoe_down", "hoe", "ranch.farmer_walk")])
	t.eq(recipe.use_strips(plain), {})
	var parts := [{"id": farmer["id"], "sha256": "", "eff": plain.catalog.effective(farmer)}]
	t.eq(recipe.input_hash(plain), plain.stable_hash({"v": Recipe.RECIPE_VERSION, "sprites": parts}), "no key: the hash of before")
	t.ok(recipe.input_hash(with_strip) != recipe.input_hash(plain))
	t.eq(Recipe.direction_of("idle_down_left"), "down_left")
	t.eq(Recipe.direction_of("use_up"), "up")
	t.eq(Recipe.direction_of("idle"), "down")
