extends RefCounted
## What the farm's recipes share (T17.04, T17.05): the parts the farmer has beside the top-down
## player, the stored plan of the crops, and the pictures the recipes use: a pack's own (by its
## role, its tag and a word of its file name), else the one of the drawn farm kit
## (`rpggen/core/farm_kit.py`, T17.02: the pack `rpggen_farm_kit`, which a run adds to the
## catalog for what the packs lack).
##
## Three things are still drawn here, in GDScript: the tiles of the `Soil` layer the kit lacks
## (ground that can be tilled, water), the bag of seeds of a crop (one in the colour of each crop,
## where the kit has one bag for all), and a last resort for a picture that is in neither the
## packs nor the kit (a catalog whose kit asset was switched off, a crop whose strip is gone).

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const TextureUtil := preload("../../lib/texture_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const MapGeo := preload("../../lib/map_geo.gd")

const DIR := "res://addons/rpg_runtime/archetypes/farm/"
const FARMER := DIR + "farmer.gd"
const MODE := DIR + "farm_mode.gd"
const HUD := DIR + "ui/farm_hud.gd"
const FIELD := DIR + "field.gd"
const BIN := DIR + "shipping_bin.gd"
const BED := DIR + "bed.gd"
const SHOP := DIR + "farm_shop.gd"
const CROP := DIR + "crop.gd"
const WATER_SOURCE := DIR + "water_source.gd"
const ITEM_DEF := "res://addons/rpg_runtime/data/item_definition.gd"

const MODE_PATH := "res://generated/scenes/combat/combat_mode.tscn"
const WORLD_PLAN := "res://rpggen/world_plan.json"
const SOIL_TILESET := "res://generated/tilesets/farm_soil.tres"
const CROPS_DIR := "res://generated/scenes/farm/crops/"
const ITEMS_DIR := "res://game/data/items/"
const HOTBAR_SLOTS := 10

const KIT_PACK := "rpggen_farm_kit"
## The tools: item id -> the words a pack's tool picture is known by (role TOOL, tag `tool`;
## farm_kit.TOOL_WORDS).
const TOOLS := {
	"hoe": ["hoe"],
	"watering_can": ["watering", "water", "can", "wateringcan"],
	"sickle": ["sickle", "scythe"],
	"farm_axe": ["axe", "hatchet"],
	"fishing_rod": ["rod", "fishingrod"],
}
## Item id -> the name of the kit's picture. The axe's item is `farm_axe` (`axe` is the weapon
## the starter gear may be); its picture is the kit's `axe`.
const KIT_TOOLS := {"hoe": "hoe", "watering_can": "watering_can", "sickle": "sickle", "farm_axe": "axe", "fishing_rod": "fishing_rod"}
## The fishing rod (T17.10) is the last: an item of every farm, sold where the farm has a pond.
const TOOL_ORDER: Array[String] = ["hoe", "watering_can", "sickle", "farm_axe", "fishing_rod"]
## What a new game has of them (T17.08): the other two are bought at the shop.
const START_TOOLS: Array[String] = ["hoe", "watering_can"]
const START_SEEDS := 15
## The money of a new game unless `starter_map.starting_money` says otherwise
## (config.FARM_STARTING_MONEY).
const START_MONEY := 100
## `starter_map.day_length` -> the real seconds of a game minute (`config.FARM_DAY_LENGTHS`): a
## day of 1200 minutes lasts 10, 14 or 20 minutes.
const DAY_LENGTHS := {"short": 0.5, "normal": 0.7, "long": 1.0}
## The bin and the bed: a pack's own is known by these (farm_kit.BIN, farm_kit.BED).
const BIN_ROLES: Array[String] = ["DECORATION", "ITEM", "BUILDING"]
const BIN_TAG := "bin"
const BED_ROLES: Array[String] = ["DECORATION", "INTERIOR", "ITEM"]
const BED_WORDS: Array[String] = ["bed", "beds"]

const WOOD := Color(0.55, 0.36, 0.2)
const METAL := Color(0.75, 0.77, 0.8)
const CAN := Color(0.4, 0.55, 0.7)
const BAG := Color(0.8, 0.68, 0.45)
const LEAF := Color(0.3, 0.62, 0.25)
const EARTH := Color(0.58, 0.44, 0.28)
const TILLED := Color(0.42, 0.29, 0.18)
const WET := Color(0.27, 0.2, 0.16)
const WATER := Color(0.27, 0.5, 0.78)
## The boards of the floor of a room and the plaster of its walls (room_texture).
const BOARD := Color(0.72, 0.56, 0.36)
const PLASTER := Color(0.85, 0.78, 0.62)
const ROOM_TILESET := "res://generated/tilesets/farm_room.tres"

# ---------------------------------------------------------------- the project

## What the farm's recipes mean by a tile: the tile of the project's maps, and for an isometric
## farm (T17.14) the length of one step on its diamonds (MapGeo.tile_unit), which is how large
## its people and the things of the drawn kit are.
static func tile(ctx: BuildContext) -> int:
	if MapGeo.is_isometric(ctx):
		return MapGeo.tile_unit(ctx)
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return JsonUtil.to_int(def["tile_size"][0]) if not def.is_empty() else maxi(8, JsonUtil.to_int(ctx.config.get("base_tile_size", 16)))

## The `farm` section of the stored plan (rpggen/core/crop_plan.py), or {}. Its `map` is the
## farm's own map (farm_plan.py) and its `people` the people of the village (people_plan.py).
static func plan() -> Dictionary:
	if not FileAccess.file_exists(WORLD_PLAN):
		return {}
	return JsonUtil.to_dict(JsonUtil.to_dict(JsonUtil.read(WORLD_PLAN)).get("farm", {}))

## The crops of the plan, in its order.
static func crops() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in JsonUtil.to_array(plan().get("crops", [])):
		out.append(JsonUtil.to_dict(raw))
	return out

## The fish and the forage of the plan (rpggen/core/forage_plan.py: `farm.forage`), or {}.
static func forage() -> Dictionary:
	return JsonUtil.to_dict(plan().get("forage", {}))

## True when the rod is sold: the farm has a pond and the option `starter_map.fishing` is on
## (the plan's `fishing`, which follows both on every generation).
static func fishing() -> bool:
	return JsonUtil.to_bool(forage().get("fishing", false))

## One of the farm's options (a key of the config's `starter_map`), or `fallback`.
static func option(ctx: BuildContext, key: String, fallback: Variant) -> Variant:
	return ctx.section("starter_map").get(key, fallback)

## The money a new game starts with (`starter_map.starting_money`).
static func starting_money(ctx: BuildContext) -> int:
	return maxi(0, JsonUtil.to_int(option(ctx, "starting_money", START_MONEY), START_MONEY))

## False when staying up to 2:00 costs no money (`starter_map.pass_out_loss`).
static func pass_out_loss(ctx: BuildContext) -> bool:
	return JsonUtil.to_bool(option(ctx, "pass_out_loss", true), true)

## The days of a season (`starter_map.days_per_season`: 7, 14 or 28; anything else is 28).
static func days_per_season(ctx: BuildContext) -> int:
	var days := JsonUtil.to_int(option(ctx, "days_per_season", RpgCalendar.DAYS_PER_SEASON), RpgCalendar.DAYS_PER_SEASON)
	return RpgCalendar.season_length(days)

## The real seconds of a game minute (`starter_map.day_length`: `short`, `normal` or `long`).
static func minute_s(ctx: BuildContext) -> float:
	var length := JsonUtil.to_str(option(ctx, "day_length", "normal"))
	return JsonUtil.to_float(DAY_LENGTHS.get(length, RpgCalendar.MINUTE_S), RpgCalendar.MINUTE_S)

## What a new game of a farm starts with, before what every game starts with: a hoe, a can and
## fifteen seeds of the first crop of the plan (it grows in spring).
static func starting_items() -> Array:
	var items: Array = []
	for tool_id in START_TOOLS:
		items.append({"item_id": tool_id, "qty": 1})
	var planned := crops()
	if not planned.is_empty():
		items.append({"item_id": JsonUtil.to_str(planned[0].get("seed", "")), "qty": START_SEEDS})
	return items

# ---------------------------------------------------------------- the packs

static func _usable(asset: Dictionary) -> bool:
	return not (asset.get("status", "") in ["UNUSED", "MISSING"])

## The picture of a tool: a pack's own (role TOOL, tag `tool`, one of the tool's words in its
## file name; the farmer swinging its hoe has the tag too, but is no TOOL), else the kit's, or {}.
static func tool_asset(ctx: BuildContext, tool_id: String) -> Dictionary:
	var words: Array = TOOLS.get(tool_id, [])
	for asset in ctx.catalog.assets():
		var eff: Dictionary = ctx.catalog.effective(asset)
		var tags: Array = eff.get("tags", [])
		if not _usable(asset) or asset.get("pack_id", "") == KIT_PACK or eff.get("role", "") != "TOOL" or not tags.has("tool"):
			continue
		var file := JsonUtil.to_str(asset.get("path", "")).get_file().get_basename().to_lower()
		for word: String in words:
			if file.split("_", false).has(word):
				return asset
	return kit_asset(ctx, JsonUtil.to_str(KIT_TOOLS.get(tool_id, "")))

## The picture of the shipping bin: a pack's own (an object or a sprite tagged `bin`), else the
## kit's, or {}.
static func bin_asset(ctx: BuildContext) -> Dictionary:
	for asset in ctx.catalog.assets():
		var eff: Dictionary = ctx.catalog.effective(asset)
		var tags: Array = eff.get("tags", [])
		if _own_object(asset, eff, BIN_ROLES) and tags.has(BIN_TAG):
			return asset
	return kit_asset(ctx, "shipping_bin")

## The picture of the bed: a pack's own (an object or a sprite with `bed` in its file name),
## else the kit's, or {}.
static func bed_asset(ctx: BuildContext) -> Dictionary:
	for asset in ctx.catalog.assets():
		var eff: Dictionary = ctx.catalog.effective(asset)
		if not _own_object(asset, eff, BED_ROLES):
			continue
		var file := JsonUtil.to_str(asset.get("path", "")).get_file().get_basename().to_lower()
		for word in BED_WORDS:
			if file.split("_", false).has(word):
				return asset
	return kit_asset(ctx, "bed")

## True for a picture of the packs (not the kit's) that is in use, stands on a map (an object
## or a sprite) and has one of `roles`.
static func _own_object(asset: Dictionary, eff: Dictionary, roles: Array[String]) -> bool:
	if not _usable(asset) or asset.get("pack_id", "") == KIT_PACK:
		return false
	return roles.has(JsonUtil.to_str(eff.get("role", ""))) and ["sprite", "object"].has(JsonUtil.to_str(eff.get("usage", "")))

## The picture `kit_name` of the drawn farm kit, or {} when this run did not draw it.
static func kit_asset(ctx: BuildContext, kit_name: String) -> Dictionary:
	var asset: Dictionary = ctx.catalog.asset("%s.%s" % [KIT_PACK, kit_name])
	return asset if not asset.is_empty() and _usable(asset) else {}

## The tile of tilled (`soil`) or watered (`watered`) soil as {path, coords}: a pack's own tile
## sheet with that tag, else the kit's tile; {} when neither has one. Of a sheet of many tiles
## (a terrain) the tile is the one that joins on every side; a sheet that does not say which
## that is gives {}.
static func soil_tile(ctx: BuildContext, tag: String, size: int) -> Dictionary:
	var found: Dictionary = {}
	for asset in ctx.catalog.assets():
		var eff: Dictionary = ctx.catalog.effective(asset)
		var tags: Array = eff.get("tags", [])
		if not _usable(asset) or eff.get("usage", "") != "tiles" or not tags.has(tag):
			continue
		if tag == "soil" and tags.has("watered"):
			continue
		if asset.get("pack_id", "") != KIT_PACK:
			found = asset
			break
		if found.is_empty():
			found = asset
	if found.is_empty():
		return {}
	var facets: Dictionary = ctx.catalog.effective(found)
	var sheet: Array = facets.get("size", [size, size])
	var path := "res://" + JsonUtil.to_str(found["path"])
	if JsonUtil.to_int(sheet[0]) <= size and JsonUtil.to_int(sheet[1]) <= size:
		return {"path": path, "coords": Vector2i.ZERO}
	var overrides: Dictionary = facets.get("tile_overrides", {})
	if overrides.is_empty():
		overrides = JsonUtil.to_dict(JsonUtil.to_dict(facets.get("terrain_proposal", {})).get("tile_overrides", {}))
	var cells: Array = overrides.keys()
	cells.sort()
	for key: Variant in cells:
		var peering := JsonUtil.to_dict(JsonUtil.to_dict(JsonUtil.to_dict(overrides[key]).get("terrain", {})).get("peering", {}))
		var whole := peering.size() >= 4
		for side: Variant in peering.values():
			if JsonUtil.to_int(side, -1) < 0:
				whole = false
		if whole:
			var parts := JsonUtil.to_str(key).split(",")
			return {"path": path, "coords": Vector2i(int(parts[0]), int(parts[1]))}
	return {}

## The tile of tilled (`soil`) or watered (`watered`) soil of an isometric farm (T17.14): the id
## of the first flat tile of the project's tile set of diamonds that a pack tagged so
## (`dirtFarmland` of the miniature packs), or "" when the packs have none: the field recipe
## then draws the diamond.
static func iso_soil_asset(ctx: BuildContext, tag: String) -> String:
	var reader := MapGeo.new(ctx).iso
	if reader == null:
		return ""
	for asset_id in reader.tile_ids():
		var eff := reader.facets(asset_id)
		var tags: Array = eff.get("tags", [])
		if not tags.has(tag) or (tag == "soil" and tags.has("watered")) or JsonUtil.to_int(eff.get("rise", 0)) > 0:
			continue
		return reader.turned(asset_id, 0)
	return ""

## The first cell of a picture as a texture (an icon), or null.
static func first_frame(ctx: BuildContext, asset: Dictionary) -> Texture2D:
	return frame_texture(ctx, asset, 0)

## Cell `index` of a strip as a texture, or null.
static func frame_texture(ctx: BuildContext, asset: Dictionary, index: int) -> Texture2D:
	if asset.is_empty():
		return null
	var eff: Dictionary = ctx.catalog.effective(asset)
	var size: Array = eff.get("frame", eff.get("size", [16, 16]))
	var cell := Vector2i(JsonUtil.to_int(size[0]), JsonUtil.to_int(size[1]))
	return TextureUtil.region_texture("res://" + JsonUtil.to_str(asset["path"]), Rect2i(Vector2i(cell.x * index, 0), cell))

# ---------------------------------------------------------------- the farmer

## What the farmer has beside the top-down player: its script, the frame on the tile ahead and
## the icon of the tool in use. Called by actor_recipes for the player of a farm.
static func augment_player(root: Node, frame: Vector2i, _origin: Vector2i, tile_px: int) -> void:
	SceneUtil.attach_script(root, FARMER)
	root.set("tile_px", tile_px)
	var half := tile_px * 0.5
	var outline := Line2D.new()
	outline.name = "TileFrame"
	outline.top_level = true  # it lies on the ground of the map, not at the farmer's feet
	outline.points = PackedVector2Array([Vector2(-half, -half), Vector2(half, -half), Vector2(half, half), Vector2(-half, half)])
	outline.closed = true
	outline.width = 1.0
	outline.default_color = Color(1.0, 1.0, 1.0, 0.7)
	root.add_child(outline)
	var icon := Sprite2D.new()
	icon.name = "ToolIcon"
	icon.position = Vector2(0.0, -frame.y * 0.5)
	icon.z_index = 1
	icon.visible = false
	root.add_child(icon)

# ---------------------------------------------------------------- drawn stand-ins

## A rectangle of one colour with its bottom middle on the origin.
static func stand_in(node_name: String, size: Vector2, color: Color) -> Polygon2D:
	var shape := Polygon2D.new()
	shape.name = node_name
	var half := size.x * 0.5
	shape.polygon = PackedVector2Array([Vector2(-half, -size.y), Vector2(half, -size.y), Vector2(half, 0.0), Vector2(-half, 0.0)])
	shape.color = color
	return shape

static func _blank(width: int, height: int) -> Image:
	var image := Image.create_empty(width, height, false, Image.FORMAT_RGBA8)
	image.fill(Color(0, 0, 0, 0))
	return image

## Rectangles given in sixteenths of `size`: [[x, y, w, h, colour], ...].
static func _draw(image: Image, at: Vector2i, size: int, rects: Array) -> void:
	var unit := size / 16.0
	for rect: Array in rects:
		var x0 := roundi(JsonUtil.to_float(rect[0]) * unit)
		var y0 := roundi(JsonUtil.to_float(rect[1]) * unit)
		var x1 := roundi((JsonUtil.to_float(rect[0]) + JsonUtil.to_float(rect[2])) * unit)
		var y1 := roundi((JsonUtil.to_float(rect[1]) + JsonUtil.to_float(rect[3])) * unit)
		var colour: Color = rect[4]
		image.fill_rect(Rect2i(at + Vector2i(x0, y0), Vector2i(maxi(1, x1 - x0), maxi(1, y1 - y0))), colour)

static func _icon_rects(kind: String, colour: Color) -> Array:
	match kind:
		"hoe":
			return [[7, 3, 2, 11, WOOD], [4, 2, 7, 3, METAL]]
		"watering_can":
			return [[4, 6, 8, 7, CAN], [12, 5, 3, 2, CAN], [2, 7, 2, 4, CAN], [5, 7, 6, 1, CAN.lightened(0.3)]]
		"sickle":
			return [[7, 9, 2, 6, WOOD], [5, 2, 7, 2, METAL], [11, 3, 2, 5, METAL], [4, 3, 2, 3, METAL]]
		"farm_axe":
			return [[7, 3, 2, 12, WOOD], [9, 3, 4, 5, METAL]]
		"fishing_rod":
			return [[3, 12, 3, 2, WOOD], [6, 9, 3, 3, WOOD], [9, 6, 3, 3, WOOD], [12, 3, 2, 3, WOOD], [13, 5, 1, 6, METAL], [12, 11, 3, 2, Color(0.84, 0.24, 0.2)]]
		"fish":
			return [[2, 6, 9, 5, colour], [3, 5, 7, 7, colour], [11, 7, 2, 3, colour], [13, 5, 2, 7, colour], [4, 7, 1, 1, Color(0.17, 0.13, 0.12)]]
		"seed":
			return [[4, 5, 8, 9, BAG], [6, 3, 4, 2, BAG.darkened(0.25)], [7, 8, 2, 3, colour]]
	return [[5, 5, 6, 7, colour], [4, 6, 8, 5, colour], [7, 3, 2, 2, LEAF]]  # what is harvested

## A drawn icon of 16 px: a tool (its item id), a bag of seeds (`seed`), a fish (`fish`) or
## produce (anything else) in `colour`.
static func drawn_icon(kind: String, colour: Color = Color.WHITE) -> ImageTexture:
	var image := _blank(16, 16)
	_draw(image, Vector2i.ZERO, 16, _icon_rects(kind, colour))
	return ImageTexture.create_from_image(image)

## The five drawn tiles of the `Soil` layer side by side, each `size` px: ground that can be
## tilled, tilled soil with its furrows, watered soil, water, and a tile that shows nothing.
## The first is always used; the tilled and the watered one only when neither the packs nor the
## kit have the tile; the water where a map has no water tile of the packs.
static func soil_texture(size: int) -> ImageTexture:
	var image := _blank(size * 5, size)
	_draw(image, Vector2i.ZERO, size, [[0, 0, 16, 16, EARTH], [3, 4, 2, 1, EARTH.darkened(0.15)], [10, 9, 2, 1, EARTH.darkened(0.15)], [6, 12, 1, 1, EARTH.lightened(0.15)]])
	for i: int in [1, 2]:
		var base: Color = TILLED if i == 1 else WET
		var rects: Array = [[0, 0, 16, 16, base]]
		for row: int in [2, 6, 10, 14]:
			rects.append([1, row, 14, 1, base.darkened(0.25)])
		_draw(image, Vector2i(size * i, 0), size, rects)
	_draw(image, Vector2i(size * 3, 0), size, [[0, 0, 16, 16, WATER], [2, 4, 5, 1, WATER.lightened(0.25)], [9, 10, 5, 1, WATER.lightened(0.25)]])
	return ImageTexture.create_from_image(image)

## The five tiles of the `Soil` layer of an isometric farm (T17.14) side by side, each a diamond
## of `footprint`: ground that can be tilled, tilled soil with its furrows, watered soil, water,
## and a tile that shows nothing. They are drawn here because no isometric ground is drawn
## anywhere else and the square soil of the farm kit cannot lie on a diamond: earth in the
## colours of the square tiles, the furrows along the rows of the map (they run down to the
## right on the screen).
static func iso_soil_texture(footprint: Vector2i) -> ImageTexture:
	var image := _blank(footprint.x * 5, footprint.y)
	for index in 4:
		for y in footprint.y:
			for x in footprint.x:
				var at := RpgIso.grid_point(Vector2(x + 0.5, y + 0.5), footprint)
				if at.x < 0.0 or at.y < 0.0 or at.x >= 1.0 or at.y >= 1.0:
					continue
				image.set_pixel(footprint.x * index + x, y, _iso_soil_colour(index, at))
	return ImageTexture.create_from_image(image)

## The colour of a place (`at`, each coordinate from 0 to 1 across the cell) of a tile of
## `iso_soil_texture`.
static func _iso_soil_colour(index: int, at: Vector2) -> Color:
	var stripe := int(at.y * 8.0) % 2 == 1
	match index:
		0:
			var speck := (int(at.x * 7.0) + int(at.y * 5.0) * 3) % 11 == 0
			return EARTH.darkened(0.15) if speck else EARTH
		1:
			return TILLED.darkened(0.25) if stripe else TILLED
		2:
			return WET.darkened(0.25) if stripe else WET
	var ripple := int(at.x * 6.0 + at.y * 2.0) % 5 == 0
	return WATER.lightened(0.25) if ripple else WATER

## The floor and the wall of a room of the farm (T17.18), two tiles of `size` px side by side:
## boards with their seams and a knot or two, and a plastered wall with a rail along its foot.
## Drawn for the farmhouse and the animal houses of a project whose packs have no interior
## tiles: such a room was floored with the grass of the pack and walled with its hedge.
static func room_texture(size: int) -> ImageTexture:
	var image := _blank(size * 2, size)
	var boards: Array = [[0, 0, 16, 16, BOARD]]
	for row: int in [3, 7, 11, 15]:
		boards.append([0, row, 16, 1, BOARD.darkened(0.22)])
	for seam: Array in [[5, 0], [11, 4], [3, 8], [9, 12]]:
		boards.append([seam[0], seam[1], 1, 3, BOARD.darkened(0.22)])
	boards.append([13, 1, 1, 1, BOARD.darkened(0.35)])
	boards.append([6, 9, 1, 1, BOARD.darkened(0.35)])
	_draw(image, Vector2i.ZERO, size, boards)
	_draw(image, Vector2i(size, 0), size, [[0, 0, 16, 16, PLASTER], [0, 0, 16, 1, PLASTER.lightened(0.2)], [0, 12, 16, 4, BOARD.darkened(0.3)], [0, 12, 16, 1, BOARD.darkened(0.45)]])
	return ImageTexture.create_from_image(image)

## The floor of a room of an isometric farm: one diamond of `footprint` of the same boards,
## which run along the rows of the map. (The walls of an isometric room are the pieces of the
## packs, or none: MapGeo.paint_walls.)
static func iso_room_texture(footprint: Vector2i) -> ImageTexture:
	var image := _blank(footprint.x, footprint.y)
	for y in footprint.y:
		for x in footprint.x:
			var at := RpgIso.grid_point(Vector2(x + 0.5, y + 0.5), footprint)
			if at.x < 0.0 or at.y < 0.0 or at.x >= 1.0 or at.y >= 1.0:
				continue
			var row := int(at.y * 16.0)
			var seam := row % 4 == 3 or int(at.x * 16.0) == 3 + 4 * (int(at.y * 4.0) % 3)
			image.set_pixel(x, y, BOARD.darkened(0.22) if seam else BOARD)
	return ImageTexture.create_from_image(image)

## The colour of a crop of the plan: its own (a drawn crop), else one that its name gives.
static func crop_colour(crop: Dictionary) -> Color:
	var given := JsonUtil.to_str(crop.get("color", ""))
	if given != "":
		return Color.html(given)
	var hue := (JsonUtil.to_str(crop.get("id", "")).hash() % 360) / 360.0
	return Color.from_hsv(absf(hue), 0.65, 0.85)
