extends RefCounted
## What marriage needs of a farm's files (T17.26): game/data/items/bouquet.tres and
## pendant.tres, seeded once in a farm that has somebody to court (FarmBuild.courting: the
## option `starter_map.courtable` above 0, and the plan's people chose some). They are the
## user's afterwards. The shop sells them at run time (RpgMarriage adds them to its stock), so
## the shop's file, written once, is not touched, and a farm that switches marriage on later
## sells them too.
##
## Nothing else is built for marriage: who can be courted is the plan's (people_recipes.gd
## writes it into people.json with the rest of a person, and the lines of the dialogue), the bed
## for two is the room's plan (farm_map_recipe.gd), and the spouse at home is put there by the
## game.

const RECIPE_VERSION := 1

const SeedUtil := preload("../../lib/seed_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const FarmBuild := preload("farm_build.gd")

## The items, by id: the price the shop asks (`value`) and the name of the icon.
const ITEMS: Array[String] = ["bouquet", "pendant"]
const PRICES: Dictionary[String, int] = {"bouquet": 200, "pendant": 2000}
const STEM := Color(0.3, 0.55, 0.25)
const PETALS: Array[Color] = [Color(0.92, 0.35, 0.45), Color(0.98, 0.85, 0.35), Color(0.65, 0.5, 0.9)]
const GOLD := Color(0.93, 0.76, 0.3)
const GEM := Color(0.3, 0.6, 0.95)

static func item_path(item_id: String) -> String:
	return FarmBuild.ITEMS_DIR + item_id + ".tres"

func outputs(ctx: BuildContext) -> PackedStringArray:
	if not FarmBuild.courting(ctx):
		return PackedStringArray()
	var wanted: Array = []
	for item_id in ITEMS:
		wanted.append(item_path(item_id))
	return SeedUtil.missing(wanted)

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "courting": FarmBuild.courting(ctx), "prices": PRICES})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	if not FarmBuild.courting(ctx):
		return issues
	for item_id in ITEMS:
		var path := item_path(item_id)
		if FileAccess.file_exists(path):
			continue
		var err := SeedUtil.save(make_item(item_id), path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	return issues

## The item `item_id` (one of ITEMS): one a bag holds, sold at its price, never used up by
## anything but giving it.
static func make_item(item_id: String) -> Resource:
	var item := SeedUtil.make(FarmBuild.ITEM_DEF)
	item.set("id", StringName(item_id))
	item.set("display_name", "ITEM_%s_NAME" % item_id.to_upper())
	item.set("description", "ITEM_%s_DESC" % item_id.to_upper())
	item.set("max_stack", 9)
	item.set("value", PRICES.get(item_id, 0))
	item.set("icon", drawn_icon(item_id))
	return item

## A drawn icon of 16 px: three flowers on their stems in a paper cone, or a pendant on its chain.
static func drawn_icon(item_id: String) -> ImageTexture:
	var image := FarmBuild._blank(16, 16)
	var rects: Array = []
	if item_id == "bouquet":
		rects = [[7, 6, 2, 7, STEM], [5, 7, 1, 5, STEM], [10, 7, 1, 5, STEM], [5, 11, 6, 4, Color(0.95, 0.93, 0.85)], [6, 14, 4, 1, Color(0.85, 0.82, 0.72)]]
		var heads: Array[Vector2i] = [Vector2i(3, 3), Vector2i(6, 1), Vector2i(10, 3)]
		for i in heads.size():
			var at := heads[i]
			rects.append([at.x, at.y, 4, 4, PETALS[i]])
			rects.append([at.x + 1, at.y + 1, 2, 2, PETALS[i].lightened(0.4)])
	else:
		rects = [[3, 2, 1, 6, GOLD], [12, 2, 1, 6, GOLD], [4, 1, 8, 1, GOLD], [4, 8, 2, 1, GOLD], [10, 8, 2, 1, GOLD], [6, 9, 4, 1, GOLD], [6, 10, 4, 4, GEM], [7, 11, 1, 1, GEM.lightened(0.5)], [6, 14, 4, 1, GOLD]]
	FarmBuild._draw(image, Vector2i.ZERO, 16, rects)
	return ImageTexture.create_from_image(image)
