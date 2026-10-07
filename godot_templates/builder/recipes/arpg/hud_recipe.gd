extends RefCounted
## generated/scenes/ui/hud_arpg.tscn: the action RPG's HUD (T9.04). A CanvasLayer on layer 20 with
## the HP bar and text, a thin XP bar, level, gold counter (with a coin icon when the pack has a
## coin item) and the quick-item slot. The bars are ProgressBars (flat styles, or a StyleBoxTexture
## when the packs have a nine-sliced UI bar); the whole HUD sits on a PanelContainer that uses the
## project theme's panel style. Boot adds the scene instead of hud_basic.

const RECIPE_VERSION := 2

const SceneUtil := preload("../../lib/scene_util.gd")
const UiUtil := preload("../../lib/ui_util.gd")
const TextureUtil := preload("../../lib/texture_util.gd")

const OUT_PATH := "res://generated/scenes/ui/hud_arpg.tscn"
const SCRIPT_PATH := "res://addons/rpg_runtime/archetypes/arpg/ui/hud.gd"
const COIN_WORDS := ["coin", "gold"]
const BAR_WORDS := ["bar", "gauge", "health", "hp"]
const BAR_BACK := Color(0.08, 0.08, 0.1, 0.85)
const HP_COLOR := Color(0.82, 0.2, 0.22)
const XP_COLOR := Color(0.3, 0.55, 0.9)

func outputs(_ctx) -> PackedStringArray:
	return PackedStringArray([OUT_PATH])

## The ITEM asset that looks like a coin, or {}.
func coin_asset(ctx) -> Dictionary:
	for a in ctx.catalog.assets_by_role("ITEM"):
		if a.get("status", "") in ["UNUSED", "MISSING"]:
			continue
		var eff: Dictionary = ctx.catalog.effective(a)
		if not ["sprite", "object"].has(eff.get("usage", "")):
			continue
		var text := String(a["id"]).to_lower()
		for word in COIN_WORDS:
			if text.contains(word):
				return a
	return {}

## The UI asset used to style the bars: a nine-sliced UI asset tagged `bar` or named like one
## (bar, gauge, health, hp), or {}.
func bar_asset(ctx) -> Dictionary:
	for a in ctx.catalog.assets_by_role("UI"):
		if a.get("status", "") in ["UNUSED", "MISSING"]:
			continue
		var eff: Dictionary = ctx.catalog.effective(a)
		if eff.get("usage", "") != "ui" or not (eff.get("nine_slice", null) is Array and eff["nine_slice"].size() == 4):
			continue
		if (eff.get("tags", []) as Array).has("bar"):
			return a
		var file_name := String(a["id"]).get_slice(".", String(a["id"]).get_slice_count(".") - 1).to_lower()
		for token in file_name.split("_", false):
			if BAR_WORDS.has(token):
				return a
		for word in BAR_WORDS:
			if file_name.begins_with(word) or file_name.ends_with(word):
				return a
	return {}

func input_hash(ctx) -> String:
	var coin := coin_asset(ctx)
	var bar := bar_asset(ctx)
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"coin": coin.get("id", ""),
		"sha256": coin.get("sha256", ""),
		"bar": bar.get("id", ""),
		"bar_sha": bar.get("sha256", ""),
		"bar_nine": ctx.catalog.effective(bar).get("nine_slice", []) if not bar.is_empty() else [],
	})

func build(ctx) -> Array:
	var issues: Array = []
	var root := CanvasLayer.new()
	root.name = "HudArpg"
	root.layer = 20
	SceneUtil.attach_script(root, SCRIPT_PATH)

	var panel := PanelContainer.new()
	panel.name = "Panel"
	panel.position = Vector2(6, 4)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(panel)
	var column := VBoxContainer.new()
	column.name = "Column"
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_theme_constant_override("separation", 2)
	panel.add_child(column)
	var bar_art := _bar_style(ctx)

	var hp_row := HBoxContainer.new()
	hp_row.name = "HpRow"
	hp_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(hp_row)
	hp_row.add_child(_bar("HpBar", Vector2(72, 8), HP_COLOR, bar_art))
	var hp_text := UiUtil.label(hp_row, "HpText", "", true)
	hp_text.mouse_filter = Control.MOUSE_FILTER_IGNORE

	column.add_child(_bar("XpBar", Vector2(72, 3), XP_COLOR, bar_art))

	var info := HBoxContainer.new()
	info.name = "Info"
	info.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(info)
	UiUtil.label(info, "Level", "UI_LEVEL", true).mouse_filter = Control.MOUSE_FILTER_IGNORE
	var coin := TextureRect.new()
	coin.name = "CoinIcon"
	coin.custom_minimum_size = Vector2(12, 12)
	coin.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	coin.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	coin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	coin.texture = _coin_texture(ctx)
	coin.visible = coin.texture != null
	UiUtil.unique(coin)
	info.add_child(coin)
	UiUtil.label(info, "Gold", "UI_GOLD", true).mouse_filter = Control.MOUSE_FILTER_IGNORE

	var slot := HBoxContainer.new()
	slot.name = "QuickSlot"
	slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(slot)
	var icon := TextureRect.new()
	icon.name = "QuickIcon"
	icon.custom_minimum_size = Vector2(16, 16)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	UiUtil.unique(icon)
	slot.add_child(icon)
	UiUtil.label(slot, "QuickQty", "-", true).mouse_filter = Control.MOUSE_FILTER_IGNORE

	var err := SceneUtil.save_scene(root, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	return issues

## {texture, nine} of the bar art, or {} for the flat styles.
func _bar_style(ctx) -> Dictionary:
	var asset := bar_asset(ctx)
	if asset.is_empty():
		return {}
	var tex := load("res://" + String(asset["path"])) as Texture2D
	if tex == null:
		return {}
	return {"texture": tex, "nine": ctx.catalog.effective(asset)["nine_slice"]}

func _textured(art: Dictionary, tint: Color) -> StyleBoxTexture:
	var nine: Array = art["nine"]
	var sb := StyleBoxTexture.new()
	sb.texture = art["texture"]
	sb.texture_margin_left = float(nine[0])
	sb.texture_margin_top = float(nine[1])
	sb.texture_margin_right = float(nine[2])
	sb.texture_margin_bottom = float(nine[3])
	sb.modulate_color = tint
	return sb

func _bar(bar_name: String, size: Vector2, fill: Color, art: Dictionary = {}) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.name = bar_name
	bar.custom_minimum_size = size
	bar.show_percentage = false
	bar.min_value = 0.0
	bar.max_value = 1.0
	bar.value = 1.0
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	if art.is_empty():
		var back := StyleBoxFlat.new()
		back.bg_color = BAR_BACK
		var front := StyleBoxFlat.new()
		front.bg_color = fill
		bar.add_theme_stylebox_override("background", back)
		bar.add_theme_stylebox_override("fill", front)
	else:
		# The frame is the background; the fill is the same art tinted with the bar colour.
		bar.add_theme_stylebox_override("background", _textured(art, Color(0.45, 0.45, 0.5)))
		bar.add_theme_stylebox_override("fill", _textured(art, fill))
	UiUtil.unique(bar)
	return bar

func _coin_texture(ctx) -> Texture2D:
	var coin := coin_asset(ctx)
	if coin.is_empty():
		return null
	var eff: Dictionary = ctx.catalog.effective(coin)
	var size: Array = eff.get("frame", eff.get("size", [16, 16]))
	return TextureUtil.region_texture("res://" + String(coin["path"]), Rect2i(0, 0, int(size[0]), int(size[1])))
