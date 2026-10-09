class_name RpgAbilities
extends RefCounted
## The table of the metroidvania's abilities. Which ones the player has is in the saved game
## (GameState.abilities); what each one does is in RpgPlatformActor and RpgPlatformPlayer.
##
##   double_jump   a second jump in the air, once per airtime
##   dash          a 0.18 s burst at 3x the run speed, invulnerable, 0.6 s cooldown, one per airtime
##   wall_jump     a slower fall against a wall and a jump off it
##   high_jump     jumps 1.25 tiles higher
##   break_blocks  the attack breaks tiles whose custom data `breakable` is true

const DOUBLE_JUMP := &"double_jump"
const DASH := &"dash"
const WALL_JUMP := &"wall_jump"
const HIGH_JUMP := &"high_jump"
const BREAK_BLOCKS := &"break_blocks"

## Every ability, in the order the world planner hands them out.
const ORDER: Array[StringName] = [DOUBLE_JUMP, DASH, WALL_JUMP, HIGH_JUMP, BREAK_BLOCKS]

## Per ability: the input action its hint names ("" when it needs no key) and the colour of its
## generated icon.
const TABLE: Dictionary = {
	DOUBLE_JUMP: {"action": "jump", "color": Color(0.35, 0.75, 0.9)},
	DASH: {"action": "dash", "color": Color(0.95, 0.6, 0.25)},
	WALL_JUMP: {"action": "jump", "color": Color(0.55, 0.85, 0.45)},
	HIGH_JUMP: {"action": "", "color": Color(0.9, 0.85, 0.35)},
	BREAK_BLOCKS: {"action": "attack", "color": Color(0.8, 0.5, 0.85)},
}

static func is_known(id: StringName) -> bool:
	return TABLE.has(id)

## The translation keys of an ability: MV_ABILITY_<ID>_NAME, _DESC and _HINT.
static func name_key(id: StringName) -> String:
	return "MV_ABILITY_%s_NAME" % String(id).to_upper()

static func description_key(id: StringName) -> String:
	return "MV_ABILITY_%s_DESC" % String(id).to_upper()

static func hint_key(id: StringName) -> String:
	return "MV_ABILITY_%s_HINT" % String(id).to_upper()

static func display_name(id: StringName) -> String:
	var text := RpgMetroidvaniaStrings.t(name_key(id))
	return text if text != name_key(id) else String(id).capitalize()

static func description(id: StringName) -> String:
	var text := RpgMetroidvaniaStrings.t(description_key(id))
	return text if text != description_key(id) else ""

## How to use it, with the key of the device in use: "Press [Space] twice".
static func hint(id: StringName) -> String:
	var entry: Dictionary = TABLE.get(id, {})
	var action := str(entry.get("action", ""))
	var text := RpgMetroidvaniaStrings.t(hint_key(id))
	if text == hint_key(id):
		return ""
	return text % RpgInputGlyphs.glyph(action) if action != "" and text.contains("%s") else text

## The toast of a pickup: the name, then the hint.
static func toast(id: StringName) -> String:
	var how := hint(id)
	var got := RpgMetroidvaniaStrings.t("MV_ABILITY_GAINED", [display_name(id)])
	return got if how == "" else "%s  %s" % [got, how]

## A small generated icon for an ability without art: a disc of its colour with a light rim.
static func glyph_texture(id: StringName, size: int = 12) -> Texture2D:
	var entry: Dictionary = TABLE.get(id, {})
	var color: Color = entry.get("color", Color(0.8, 0.8, 0.8))
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	var mid := (size - 1) * 0.5
	for y in size:
		for x in size:
			var d := Vector2(x - mid, y - mid).length()
			if d <= mid - 1.0:
				img.set_pixel(x, y, color)
			elif d <= mid:
				img.set_pixel(x, y, color.lightened(0.5))
	return ImageTexture.create_from_image(img)

## Takes the tiles the player broke in `room_id` out of the layers of `root` again (a room is
## loaded fresh from its scene every time it is entered).
static func apply_broken_cells(root: Node, room_id: String) -> int:
	var state := RpgUtil.state()
	if state == null or not state.has_method(&"broken_cells_of"):
		return 0
	var cells: Array = state.call(&"broken_cells_of", room_id)
	var erased := 0
	for layer in RpgSideTiles.layers_of(root):
		for cell: Vector2i in cells:
			if RpgSideTiles.cell_has(layer, cell, RpgSideTiles.BREAKABLE):
				layer.erase_cell(cell)
				erased += 1
	return erased
