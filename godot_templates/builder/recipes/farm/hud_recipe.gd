extends RefCounted
## The HUD, the weather and the seasons of a farm (T17.11).
##
## As a recipe of the build's list it writes two files:
## * generated/data/seasons.json: for every sheet the packs have once a season (the catalog's
##   `season:<name>` and `variant_of:<id>` tags, T17.01; `catalog.season_groups` in Python) the
##   path of the texture of each season, which RpgFarmSeasons swaps the ground and the trees of
##   the outdoor maps by: `{ "version": 1, "groups": { "<id of the first sheet>": { "": path,
##   "winter": path, ... } } }`. A project whose packs have no such sheets has no groups.
## * generated/scenes/farm/weather_sign.tscn: the sign that tells tomorrow's weather
##   (RpgWeatherSign).
##
## As a library of the mode's recipe (mode_recipe.gd) it makes what the mode's scene holds:
## * `build_hud(ctx)`: the farm's HUD (RpgFarmHud): the hotbar and the energy at the bottom, and
##   in the top-left corner the time, the date, the weather and the money;
## * `build_weather(ctx)`: the node `Weather` (RpgFarmWeather) with the pictures of the overlay:
##   a pack's own (role EFFECT, tag `weather`, the word `rain`, `storm` or `snow` in its file
##   name), else the rain of the drawn farm kit; a storm and snow without a picture are drawn by
##   the runtime;
## * `mode_hash(ctx)`: what of all this the mode's scene depends on.
##
## `build_sign(ctx)` makes the sign as a node, not yet on a map: the farm's map recipe places
## it by the house (or instances the scene).

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const UiUtil := preload("../../lib/ui_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const TextureUtil := preload("../../lib/texture_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const MapGeo := preload("../../lib/map_geo.gd")
const FarmBuild := preload("farm_build.gd")

const SEASONS_PATH := "res://generated/data/seasons.json"
const SIGN_SCENE := "res://generated/scenes/farm/weather_sign.tscn"
const SIGN_NAME := "WeatherSign"
const WEATHER := FarmBuild.DIR + "weather.gd"
const SIGN := FarmBuild.DIR + "weather_sign.gd"
const WEATHER_NODE := "Weather"

const SEASONS: Array[String] = ["spring", "summer", "autumn", "winter"]
const SEASON_TAG := "season:"
const VARIANT_TAG := "variant_of:"
const COLOUR_TAG := "colour:"
const WEATHER_TAG := "weather"
## Kind of weather -> the words a pack's picture of it is known by.
const WEATHER_WORDS := {
	"sun": ["sun", "sunny", "clear"],
	"rain": ["rain", "rainy"],
	"storm": ["storm", "stormy", "thunder", "lightning"],
	"snow": ["snow", "snowy", "snowfall"],
}
const KINDS: Array[String] = ["sun", "rain", "storm", "snow"]

# the hotbar and the energy, at the bottom
const SLOT_PX := 20
const GAP_PX := 2
const BAR_PX := 5
const MARGIN_PX := 4
const BAR_BACK := Color(0.08, 0.08, 0.1, 0.85)
const ENERGY_COLOR := Color(0.95, 0.8, 0.25)
## The farmer's health over the energy, in a farm that fights (T17.24).
const HEALTH_COLOR := Color(0.86, 0.24, 0.22)
# the calendar and the money, in the top-left corner
const STATUS_AT := Vector2(6, 4)
const STATUS_BACK := Color(0.08, 0.08, 0.1, 0.6)
const STATUS_PAD := 3
## A screen lower than this (320 x 180) gets the small font.
const SMALL_BELOW := 270
const SMALL_FONT := 8
const ICON_PX := 12

const SIGN_WOOD := Color(0.55, 0.36, 0.2)
const SIGN_BOARD := Color(0.8, 0.68, 0.45)

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([SEASONS_PATH, SIGN_SCENE])

func input_hash(ctx: BuildContext) -> String:
	var hashed := {"v": RECIPE_VERSION, "groups": season_table(ctx), "sign": sign_asset(ctx).get("id", ""), "tile": FarmBuild.tile(ctx)}
	if MapGeo.is_isometric(ctx):  # only an isometric project's hash has the key (T17.14)
		var footprint := MapGeo.new(ctx).footprint
		hashed["iso"] = [footprint.x, footprint.y]
	return ctx.stable_hash(hashed)

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var err := JsonUtil.write(SEASONS_PATH, {"version": 1, "groups": season_table(ctx)})
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": SEASONS_PATH, "err": err}, SEASONS_PATH))
	err = SceneUtil.save_scene(build_sign(ctx), SIGN_SCENE)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": SIGN_SCENE, "err": err}, SIGN_SCENE))
	return issues

# ---------------------------------------------------------------- the seasons

static func _tag_value(tags: Array, prefix: String) -> String:
	for tag: Variant in tags:
		var text := JsonUtil.to_str(tag)
		if text.begins_with(prefix):
			return text.substr(prefix.length())
	return ""

## {id of a group's first sheet: {season or "": "res://" path}} for the sheets the catalog has
## once a season: the first sheet and every sheet tagged `variant_of:` it, each under its
## `season:` (the one that names none under ""). A group of colours (a member has a `colour:`
## tag) is none, and neither is one with fewer than two seasons.
static func season_table(ctx: BuildContext) -> Dictionary:
	var members := {}  # first id -> [asset, ...]
	var by_id := {}
	for asset in ctx.catalog.assets():
		if not FarmBuild._usable(asset):
			continue
		by_id[JsonUtil.to_str(asset.get("id", ""))] = asset
	var ids: Array = by_id.keys()
	ids.sort()
	for id: String in ids:
		var member: Dictionary = by_id[id]
		var tags: Array = ctx.catalog.effective(member).get("tags", [])
		var first := _tag_value(tags, VARIANT_TAG)
		if first == "" or not by_id.has(first):
			continue
		if not members.has(first):
			members[first] = [by_id[first]]
		var list: Array = members[first]
		list.append(member)
	var table := {}
	var firsts: Array = members.keys()
	firsts.sort()
	for first: String in firsts:
		var group := {}
		var colours := false
		var named := 0
		var list: Array = members[first]
		for asset: Dictionary in list:
			var tags: Array = ctx.catalog.effective(asset).get("tags", [])
			if _tag_value(tags, COLOUR_TAG) != "":
				colours = true
			var season := _tag_value(tags, SEASON_TAG)
			if group.has(season) or (season != "" and not SEASONS.has(season)):
				continue
			group[season] = "res://" + JsonUtil.to_str(asset.get("path", ""))
			if season != "":
				named += 1
		if not colours and named >= 2:
			table[first] = group
	return table

# ---------------------------------------------------------------- the weather

static func _has_word(asset: Dictionary, words: Array) -> bool:
	var file := JsonUtil.to_str(asset.get("path", "")).get_file().get_basename().to_lower()
	var parts := file.replace("-", "_").replace(" ", "_").split("_", false)
	for word: String in words:
		if parts.has(word):
			return true
	return false

## A pack's own overlay of a kind of weather (role EFFECT, tag `weather`, one of the kind's
## words in its file name), or {}.
static func weather_asset(ctx: BuildContext, kind: String) -> Dictionary:
	var words: Array = WEATHER_WORDS.get(kind, [])
	for asset in ctx.catalog.assets():
		var eff: Dictionary = ctx.catalog.effective(asset)
		var tags: Array = eff.get("tags", [])
		if not FarmBuild._usable(asset) or asset.get("pack_id", "") == FarmBuild.KIT_PACK:
			continue
		if eff.get("role", "") == "EFFECT" and tags.has(WEATHER_TAG) and _has_word(asset, words):
			return asset
	return {}

## The picture of the rain: a pack's own, else the drawn farm kit's, or {}.
static func rain_asset(ctx: BuildContext) -> Dictionary:
	var own := weather_asset(ctx, "rain")
	return own if not own.is_empty() else FarmBuild.kit_asset(ctx, "rain")

## A pack's icon of a kind of weather for the HUD (a `ui` picture tagged `weather` with one of
## the kind's words in its file name), or {}.
static func icon_asset(ctx: BuildContext, kind: String) -> Dictionary:
	var words: Array = WEATHER_WORDS.get(kind, [])
	for asset in ctx.catalog.assets():
		var eff: Dictionary = ctx.catalog.effective(asset)
		var tags: Array = eff.get("tags", [])
		if not FarmBuild._usable(asset) or asset.get("pack_id", "") == FarmBuild.KIT_PACK:
			continue
		if (eff.get("usage", "") == "ui" or eff.get("role", "") == "UI") and tags.has(WEATHER_TAG) and _has_word(asset, words):
			return asset
	return {}

## How an overlay is shown: [cells in its row, cells a second], from its first animation, else
## from its sheet and its cell.
static func strip_of(ctx: BuildContext, asset: Dictionary) -> Array:
	var eff: Dictionary = ctx.catalog.effective(asset)
	var animations := JsonUtil.to_dict(eff.get("animations", {}))
	var names: Array = animations.keys()
	names.sort()
	var chosen := "idle_down" if animations.has("idle_down") else (JsonUtil.to_str(names[0]) if not names.is_empty() else "")
	if chosen != "":
		var animation := JsonUtil.to_dict(animations[chosen])
		var count := JsonUtil.to_array(animation.get("frames", [])).size()
		if count > 0:
			return [count, JsonUtil.to_float(animation.get("fps", 9.0), 9.0)]
	var sheet: Array = eff.get("size", [0, 0])
	var cell: Array = eff.get("frame", sheet)
	var width := JsonUtil.to_int(cell[0])
	return [maxi(1, JsonUtil.to_int(sheet[0]) / width) if width > 0 else 1, 9.0]

## The node `Weather` of the mode's scene: RpgFarmWeather, switched on, with its pictures.
static func build_weather(ctx: BuildContext) -> Node:
	var node := Node.new()
	node.name = WEATHER_NODE
	SceneUtil.attach_script(node, WEATHER)
	node.set("enabled", true)
	for entry: Array in [["rain", rain_asset(ctx)], ["storm", weather_asset(ctx, "storm")], ["snow", weather_asset(ctx, "snow")]]:
		var kind: String = entry[0]
		var asset: Dictionary = entry[1]
		if asset.is_empty():
			continue
		var texture := TextureUtil.asset_texture(asset)
		if texture == null:
			continue
		var strip := strip_of(ctx, asset)
		node.set(kind + "_texture", texture)
		node.set(kind + "_frames", JsonUtil.to_int(strip[0]))
		node.set(kind + "_fps", JsonUtil.to_float(strip[1]))
	return node

## What the mode's scene depends on of the HUD and the weather.
static func mode_hash(ctx: BuildContext) -> Dictionary:
	var pictures := {}
	pictures["rain"] = rain_asset(ctx).get("id", "")
	for kind: String in ["storm", "snow"]:
		pictures[kind] = weather_asset(ctx, kind).get("id", "")
	for kind in KINDS:
		pictures["icon_" + kind] = icon_asset(ctx, kind).get("id", "")
	return {"hud": RECIPE_VERSION, "pictures": pictures, "small": _small(ctx)}

# ---------------------------------------------------------------- the HUD

static func _small(ctx: BuildContext) -> bool:
	var res: Array = JsonUtil.to_array(ctx.config.get("resolution", [640, 360]))
	return res.size() == 2 and JsonUtil.to_int(res[1]) < SMALL_BELOW

## The farm's HUD (RpgFarmHud), a child of the mode. `health`: the farmer's health as a red bar
## over the energy (`%HealthBar`, a farm that fights, T17.24); without it the scene is as before.
static func build_hud(ctx: BuildContext, health: bool = false) -> CanvasLayer:
	var hud := CanvasLayer.new()
	hud.name = "Hud"
	hud.layer = 5  # RpgFarmHud.LAYER: under the dialogue box and the menus
	SceneUtil.attach_script(hud, FarmBuild.HUD)
	var icons := {}
	for kind in KINDS:
		var texture := FarmBuild.first_frame(ctx, icon_asset(ctx, kind))
		if texture != null:
			icons[kind] = texture
	hud.set("weather_icons", icons)
	hud.add_child(_bottom(health))
	hud.add_child(_status(_small(ctx)))
	return hud

## The energy bar over the ten slots, in the middle of the bottom edge of the screen, and with
## `health` the health bar over the energy.
static func _bottom(health: bool = false) -> VBoxContainer:
	var width := FarmBuild.HOTBAR_SLOTS * SLOT_PX + (FarmBuild.HOTBAR_SLOTS - 1) * GAP_PX
	var height := SLOT_PX + GAP_PX + BAR_PX
	if health:
		height += BAR_PX + GAP_PX
	var column := VBoxContainer.new()
	column.name = "Column"
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_theme_constant_override("separation", GAP_PX)
	column.anchor_left = 0.5
	column.anchor_right = 0.5
	column.anchor_top = 1.0
	column.anchor_bottom = 1.0
	column.offset_left = -width / 2.0
	column.offset_right = width / 2.0
	column.offset_top = -(height + MARGIN_PX)
	column.offset_bottom = -MARGIN_PX

	if health:
		column.add_child(_bar("HealthBar", width, HEALTH_COLOR))
	column.add_child(_bar("EnergyBar", width, ENERGY_COLOR))

	var slots := HBoxContainer.new()
	slots.name = "Slots"
	slots.mouse_filter = Control.MOUSE_FILTER_IGNORE
	slots.add_theme_constant_override("separation", GAP_PX)
	UiUtil.unique(slots)
	column.add_child(slots)
	for i in FarmBuild.HOTBAR_SLOTS:
		slots.add_child(_slot(i))
	return column

## A bar of the HUD: `%<node_name>`, full, in `colour` on the dark ground.
static func _bar(node_name: String, width: int, colour: Color) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.name = node_name
	bar.custom_minimum_size = Vector2(width, BAR_PX)
	bar.show_percentage = false
	bar.min_value = 0.0
	bar.max_value = 100.0
	bar.value = 100.0
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var back := StyleBoxFlat.new()
	back.bg_color = BAR_BACK
	var fill := StyleBoxFlat.new()
	fill.bg_color = colour
	bar.add_theme_stylebox_override("background", back)
	bar.add_theme_stylebox_override("fill", fill)
	UiUtil.unique(bar)
	return bar

static func _slot(index: int) -> PanelContainer:
	var slot := PanelContainer.new()
	slot.name = "Slot%d" % (index + 1)
	slot.custom_minimum_size = Vector2(SLOT_PX, SLOT_PX)
	slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var icon := TextureRect.new()
	icon.name = "Icon"
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	slot.add_child(icon)
	var qty := Label.new()
	qty.name = "Qty"
	qty.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	qty.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	qty.add_theme_font_size_override("font_size", 8)
	qty.mouse_filter = Control.MOUSE_FILTER_IGNORE
	slot.add_child(qty)
	return slot

## The time and the date, the weather, and the money: three short lines on a dark ground in the
## top-left corner, where the basic HUD has its line of money (which RpgFarmHud hides). (No
## PanelContainer: the slots of the hotbar are the PanelContainers of this scene.)
static func _status(small: bool) -> MarginContainer:
	var panel := MarginContainer.new()
	panel.name = "Status"
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.position = STATUS_AT
	var back := ColorRect.new()
	back.name = "Back"
	back.color = STATUS_BACK
	back.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(back)
	var pad := MarginContainer.new()
	pad.name = "Pad"
	pad.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for side: String in ["left", "top", "right", "bottom"]:
		pad.add_theme_constant_override("margin_" + side, STATUS_PAD)
	panel.add_child(pad)
	var column := VBoxContainer.new()
	column.name = "Lines"
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_theme_constant_override("separation", 0)
	pad.add_child(column)

	var first := HBoxContainer.new()
	first.name = "Time"
	first.mouse_filter = Control.MOUSE_FILTER_IGNORE
	first.add_theme_constant_override("separation", 6)
	column.add_child(first)
	first.add_child(_line("Clock", "6:00", small))
	first.add_child(_line("Date", "", small))

	var second := HBoxContainer.new()
	second.name = "Sky"
	second.mouse_filter = Control.MOUSE_FILTER_IGNORE
	second.add_theme_constant_override("separation", 4)
	column.add_child(second)
	var icon := TextureRect.new()
	icon.name = "WeatherIcon"
	icon.custom_minimum_size = Vector2(ICON_PX, ICON_PX)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	icon.visible = false
	UiUtil.unique(icon)
	second.add_child(icon)
	second.add_child(_line("Weather", "", small))

	column.add_child(_line("Money", "", small))
	return panel

static func _line(node_name: String, text: String, small: bool) -> Label:
	var label := Label.new()
	label.name = node_name
	label.text = text
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if small:
		label.add_theme_font_size_override("font_size", SMALL_FONT)
	UiUtil.unique(label)
	return label

# ---------------------------------------------------------------- the sign

## A pack's own picture of a sign (an object or a sprite tagged `sign`), or {}.
static func sign_asset(ctx: BuildContext) -> Dictionary:
	for asset in ctx.catalog.assets():
		var eff: Dictionary = ctx.catalog.effective(asset)
		var tags: Array = eff.get("tags", [])
		if not FarmBuild._usable(asset) or asset.get("pack_id", "") == FarmBuild.KIT_PACK:
			continue
		if tags.has("sign") and ["sprite", "object"].has(JsonUtil.to_str(eff.get("usage", ""))):
			return asset
	return {}

## The sign that tells tomorrow's weather (RpgWeatherSign), not yet on a map: its foot (the
## middle of its lower edge) is its origin, it blocks and is found by `interact` (the world, 1,
## and the interactables, 5). A pack's own sign, else a drawn post with a board. On an isometric
## farm (T17.14) its origin is the middle of its cell and it blocks the middle of that diamond.
static func build_sign(ctx: BuildContext) -> StaticBody2D:
	var tile := FarmBuild.tile(ctx)
	var texture := FarmBuild.first_frame(ctx, sign_asset(ctx))
	var size := Vector2(texture.get_size()) if texture != null else Vector2(tile, tile)
	var body := StaticBody2D.new()
	body.name = SIGN_NAME
	SceneUtil.attach_script(body, SIGN)
	body.collision_layer = 0
	body.collision_mask = 0
	body.set_collision_layer_value(1, true)
	body.set_collision_layer_value(5, true)
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	if MapGeo.is_isometric(ctx):
		shape.shape = RpgFarmIso.diamond_shape(MapGeo.new(ctx).footprint, 0.5)
	else:
		var rect := RectangleShape2D.new()
		rect.size = Vector2(minf(size.x, tile) * 0.8, minf(size.y, tile) * 0.5)
		shape.shape = rect
		shape.position = Vector2(0.0, -rect.size.y * 0.5)
	body.add_child(shape)
	if texture != null:
		var sprite := Sprite2D.new()
		sprite.name = "Sprite"
		sprite.texture = texture
		sprite.centered = false
		sprite.position = Vector2(-size.x * 0.5, -size.y)
		body.add_child(sprite)
	else:
		body.add_child(FarmBuild.stand_in("Post", Vector2(tile * 0.15, tile * 0.9), SIGN_WOOD))
		var board := FarmBuild.stand_in("Sprite", Vector2(tile * 0.8, tile * 0.5), SIGN_BOARD)
		board.position = Vector2(0.0, -tile * 0.4)
		body.add_child(board)
	return body
