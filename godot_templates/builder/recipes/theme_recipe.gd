extends RefCounted
## Builds res://generated/theme/main_theme.tres.
##
## A UI asset with a nine_slice becomes the panel/button StyleBoxTexture; otherwise flat styles.
## A FONT asset is used only when its pack has a license file.

const RECIPE_VERSION := 1

const Paths := preload("../lib/paths.gd")

const OUT_PATH := "res://generated/theme/main_theme.tres"
const BG := Color("#1b1f2a")
const BORDER := Color("#c9b37e")

func outputs(_ctx) -> PackedStringArray:
	return PackedStringArray([OUT_PATH])

func _base_tile(ctx) -> int:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return int(def["tile_size"][0]) if not def.is_empty() else int(ctx.config.get("base_tile_size", 16))

func _ui_asset(ctx) -> Dictionary:
	for a in ctx.catalog.assets_by_role("UI"):
		var eff: Dictionary = ctx.catalog.effective(a)
		if a.get("status", "") in ["UNUSED", "MISSING"]:
			continue
		if eff.get("usage", "") == "ui" and eff.get("nine_slice", null) is Array and eff["nine_slice"].size() == 4:
			return a
	return {}

## {asset, licensed} of the first FONT asset, or {}.
func _font_asset(ctx) -> Dictionary:
	for a in ctx.catalog.assets_by_role("FONT"):
		if a.get("status", "") in ["UNUSED", "MISSING"]:
			continue
		var licensed := false
		for pack in ctx.catalog.catalog.get("packs", []):
			if pack.get("pack_id", "") == a.get("pack_id", "") and not pack.get("license_files", []).is_empty():
				licensed = true
		return {"asset": a, "licensed": licensed}
	return {}

func input_hash(ctx) -> String:
	var ui := _ui_asset(ctx)
	var font := _font_asset(ctx)
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"tile": _base_tile(ctx),
		"ui": ctx.catalog.effective(ui) if not ui.is_empty() else {},
		"ui_sha": ui.get("sha256", ""),
		"font": font.get("asset", {}).get("id", ""),
		"font_sha": font.get("asset", {}).get("sha256", ""),
		"licensed": font.get("licensed", false),
	})

func _flat(bg: Color, border: Color) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.set_border_width_all(2)
	sb.border_color = border
	sb.set_corner_radius_all(2)
	sb.content_margin_left = 6
	sb.content_margin_right = 6
	sb.content_margin_top = 3
	sb.content_margin_bottom = 3
	return sb

func _textured(tex: Texture2D, nine: Array, tint: Color) -> StyleBoxTexture:
	var sb := StyleBoxTexture.new()
	sb.texture = tex
	sb.texture_margin_left = float(nine[0])
	sb.texture_margin_top = float(nine[1])
	sb.texture_margin_right = float(nine[2])
	sb.texture_margin_bottom = float(nine[3])
	sb.content_margin_left = float(nine[0]) + 2.0
	sb.content_margin_right = float(nine[2]) + 2.0
	sb.content_margin_top = float(nine[1]) + 2.0
	sb.content_margin_bottom = float(nine[3]) + 2.0
	sb.modulate_color = tint
	return sb

func build(ctx) -> Array:
	var issues: Array = []
	var theme := Theme.new()
	var ui := _ui_asset(ctx)
	var tex: Texture2D = null
	if not ui.is_empty():
		tex = load("res://" + String(ui["path"])) as Texture2D
	if tex != null:
		var nine: Array = ctx.catalog.effective(ui)["nine_slice"]
		theme.set_stylebox("panel", "PanelContainer", _textured(tex, nine, Color.WHITE))
		theme.set_stylebox("normal", "Button", _textured(tex, nine, Color.WHITE))
		theme.set_stylebox("hover", "Button", _textured(tex, nine, Color(1.15, 1.15, 1.15)))
		theme.set_stylebox("pressed", "Button", _textured(tex, nine, Color(0.8, 0.8, 0.8)))
		theme.set_stylebox("disabled", "Button", _textured(tex, nine, Color(0.6, 0.6, 0.6)))
		theme.set_stylebox("focus", "Button", _flat(Color(0, 0, 0, 0), BORDER))
	else:
		theme.set_stylebox("panel", "PanelContainer", _flat(BG, BORDER))
		theme.set_stylebox("normal", "Button", _flat(BG, BORDER.darkened(0.4)))
		theme.set_stylebox("hover", "Button", _flat(BG.lightened(0.15), BORDER))
		theme.set_stylebox("pressed", "Button", _flat(BG.darkened(0.2), BORDER))
		theme.set_stylebox("disabled", "Button", _flat(BG.darkened(0.2), BORDER.darkened(0.7)))
		theme.set_stylebox("focus", "Button", _flat(Color(0, 0, 0, 0), Color.WHITE))
	theme.set_color("font_color", "Button", Color.WHITE)
	theme.set_color("font_disabled_color", "Button", Color(0.55, 0.55, 0.55))
	theme.set_color("font_color", "Label", Color.WHITE)
	theme.default_font_size = maxi(8, _base_tile(ctx) / 2)
	var font := _font_asset(ctx)
	if not font.is_empty():
		if font["licensed"]:
			var font_file := load("res://" + String(font["asset"]["path"])) as Font
			if font_file != null:
				theme.default_font = font_file
		else:
			issues.append(ctx.make_issue("ASSET-024", {"asset": font["asset"]["id"]}))
	DirAccess.make_dir_recursive_absolute(OUT_PATH.get_base_dir())
	var err := ResourceSaver.save(theme, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	return issues
