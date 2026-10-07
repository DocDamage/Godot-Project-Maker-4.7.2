extends RefCounted
## Builds the turn-based battle scene (generated/scenes/battle/battle.tscn) and the scene of the
## combat mode that boot adds under SceneRouter (generated/scenes/combat/combat_mode.tscn).
##
##   Battle (Node2D, battle_scene.gd)
##   +- Background (CanvasLayer)  a BACKGROUND asset as a TextureRect, else two ColorRects
##   +- EnemySlots / PartySlots   Marker2D Slot1..Slot4
##   +- Controller (Node, battle_controller.gd)
##   +- UI (CanvasLayer, battle_ui.gd)
##      CommandPanel > Commands, TargetCursor, ItemSubmenu > ItemList, BattleLog > LogLabel,
##      PartyStatus, EnemyStatus
##
## The buttons, status rows and battlers are created at runtime from the commands and the encounter.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const UiUtil := preload("../../lib/ui_util.gd")

const BATTLE_PATH := "res://generated/scenes/battle/battle.tscn"
const COMBAT_PATH := "res://generated/scenes/combat/combat_mode.tscn"
const ARCH := "res://addons/rpg_runtime/archetypes/turn_based/"
const SLOT_COUNT := 4
const DEFAULT_RESOLUTION := [640, 360]

func outputs(_ctx) -> PackedStringArray:
	return PackedStringArray([BATTLE_PATH, COMBAT_PATH])

func input_hash(ctx) -> String:
	return ctx.stable_hash({
		"v": RECIPE_VERSION, "resolution": _resolution(ctx),
		"background": _background(ctx).get("id", ""), "music": _music(ctx),
	})

func _resolution(ctx) -> Vector2:
	var r: Array = ctx.config.get("resolution", DEFAULT_RESOLUTION)
	return Vector2(float(r[0]), float(r[1]))

func _usable(ctx, a: Dictionary) -> bool:
	var eff: Dictionary = ctx.catalog.effective(a)
	return not (a.get("status", "") in ["UNUSED", "MISSING"]) and ["sprite", "object", "background"].has(eff.get("usage", "sprite"))

## The first BACKGROUND asset (by id), or {}.
func _background(ctx) -> Dictionary:
	for a in ctx.catalog.assets_by_role("BACKGROUND"):
		if _usable(ctx, a) and ResourceLoader.exists("res://" + String(a["path"])):
			return a
	return {}

## The music of the battle: the sound slot music_battle, else the first music asset whose name
## contains "battle", or "".
func _music(ctx) -> String:
	var sounds: Dictionary = ctx.config.get("sounds", {})
	if sounds.has("music_battle"):
		return String(sounds["music_battle"])  # "" = the user cleared it
	for a in ctx.catalog.assets_by_role("AUDIO_MUSIC"):
		if String(a["id"]).to_lower().contains("battle") or String(a["path"]).get_file().to_lower().contains("battle"):
			return String(a["id"])
	return ""

func build(ctx) -> Array:
	var issues: Array = []
	var err := SceneUtil.save_scene(_build_battle(ctx), BATTLE_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": BATTLE_PATH, "err": err}, BATTLE_PATH))
	var combat := Node.new()
	combat.name = "Combat"
	SceneUtil.attach_script(combat, ARCH + "turn_based_mode.gd")
	err = SceneUtil.save_scene(combat, COMBAT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": COMBAT_PATH, "err": err}, COMBAT_PATH))
	return issues

# ---------------------------------------------------------------- the battle scene

func _build_battle(ctx) -> Node:
	var size := _resolution(ctx)
	var root := Node2D.new()
	root.name = "Battle"
	SceneUtil.attach_script(root, ARCH + "battle_scene.gd")
	root.set("music_asset_id", _music(ctx))
	root.add_child(_background_node(ctx))
	root.add_child(_slots("EnemySlots", size, Vector2(0.20, 0.34), Vector2(0.16, 0.0)))
	root.add_child(_slots("PartySlots", size, Vector2(0.66, 0.50), Vector2(0.05, 0.06)))
	var controller := Node.new()
	controller.name = "Controller"
	SceneUtil.attach_script(controller, ARCH + "battle_controller.gd")
	UiUtil.unique(controller)
	root.add_child(controller)
	root.add_child(_ui(size))
	return root

func _background_node(ctx) -> CanvasLayer:
	var layer := CanvasLayer.new()
	layer.name = "Background"
	layer.layer = -10
	var asset := _background(ctx)
	if not asset.is_empty():
		var picture := TextureRect.new()
		picture.name = "Picture"
		picture.texture = load("res://" + String(asset["path"])) as Texture2D
		picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		picture.stretch_mode = TextureRect.STRETCH_SCALE
		picture.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		layer.add_child(picture)
		return layer
	for part in [["Sky", Color("#2b3a67"), 0.0, 0.55], ["Ground", Color("#3d5a3a"), 0.55, 1.0]]:
		var rect := ColorRect.new()
		rect.name = part[0]
		rect.color = part[1]
		rect.anchor_left = 0.0
		rect.anchor_right = 1.0
		rect.anchor_top = part[2]
		rect.anchor_bottom = part[3]
		rect.offset_left = 0.0
		rect.offset_right = 0.0
		rect.offset_top = 0.0
		rect.offset_bottom = 0.0
		layer.add_child(rect)
	return layer

func _slots(slot_name: String, size: Vector2, start: Vector2, step: Vector2) -> Node2D:
	var holder := Node2D.new()
	holder.name = slot_name
	UiUtil.unique(holder)
	for i in SLOT_COUNT:
		var marker := Marker2D.new()
		marker.name = "Slot%d" % (i + 1)
		marker.position = Vector2(size.x * (start.x + step.x * i), size.y * (start.y + step.y * i)).round()
		holder.add_child(marker)
	return holder

# ---------------------------------------------------------------- the interface

func _panel(parent: Node, panel_name: String, min_width: float) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.name = panel_name
	panel.custom_minimum_size = Vector2(min_width, 0)
	UiUtil.unique(panel)
	parent.add_child(panel)
	var margin := MarginContainer.new()
	margin.name = "Margin"
	for side in ["left", "top", "right", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 6)
	panel.add_child(margin)
	var box := VBoxContainer.new()
	box.name = "Box"
	box.add_theme_constant_override("separation", 2)
	margin.add_child(box)
	return box

func _ui(size: Vector2) -> CanvasLayer:
	var ui := CanvasLayer.new()
	ui.name = "UI"
	SceneUtil.attach_script(ui, ARCH + "ui/battle_ui.gd")
	UiUtil.unique(ui)

	var commands_box := _panel(ui, "CommandPanel", 116.0)
	var commands := VBoxContainer.new()
	commands.name = "Commands"
	UiUtil.unique(commands)
	commands.add_theme_constant_override("separation", 2)
	commands_box.add_child(commands)
	_pin(commands_box.get_parent().get_parent(), Control.PRESET_BOTTOM_LEFT, Vector2(8, 8))

	var cursor := Control.new()
	cursor.name = "TargetCursor"
	SceneUtil.attach_script(cursor, ARCH + "ui/target_cursor.gd")
	UiUtil.unique(cursor)
	ui.add_child(cursor)

	var items_box := _panel(ui, "ItemSubmenu", 150.0)
	var item_list := VBoxContainer.new()
	item_list.name = "ItemList"
	UiUtil.unique(item_list)
	items_box.add_child(item_list)
	var items_panel := items_box.get_parent().get_parent() as Control
	_pin(items_panel, Control.PRESET_BOTTOM_LEFT, Vector2(8 + 116 + 8, 8))

	var log_box := _panel(ui, "BattleLog", 0.0)
	var log_label := UiUtil.label(log_box, "LogLabel", "", true)
	log_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	log_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var log_panel := log_box.get_parent().get_parent() as Control
	_pin(log_panel, Control.PRESET_TOP_WIDE, Vector2(8, 8))
	log_panel.offset_left = size.x * 0.2
	log_panel.offset_right = -size.x * 0.2

	var party := VBoxContainer.new()
	party.name = "PartyStatus"
	UiUtil.unique(party)
	ui.add_child(party)
	_pin(party, Control.PRESET_BOTTOM_RIGHT, Vector2(8, 8))

	var enemies := VBoxContainer.new()
	enemies.name = "EnemyStatus"
	UiUtil.unique(enemies)
	ui.add_child(enemies)
	_pin(enemies, Control.PRESET_TOP_LEFT, Vector2(8, 8))
	return ui

## Anchors `c` to a corner or edge with a margin; it starts empty-sized there and grows away from
## the anchor as its contents change.
func _pin(c: Control, preset: int, margin: Vector2) -> void:
	c.set_anchors_preset(preset)
	match preset:
		Control.PRESET_TOP_LEFT:
			c.offset_left = margin.x
			c.offset_top = margin.y
		Control.PRESET_BOTTOM_LEFT:
			c.offset_left = margin.x
			c.offset_top = -margin.y
			c.grow_vertical = Control.GROW_DIRECTION_BEGIN
		Control.PRESET_BOTTOM_RIGHT:
			c.offset_left = -margin.x
			c.offset_top = -margin.y
			c.grow_horizontal = Control.GROW_DIRECTION_BEGIN
			c.grow_vertical = Control.GROW_DIRECTION_BEGIN
		Control.PRESET_TOP_WIDE:
			c.offset_left = margin.x
			c.offset_right = -margin.x
			c.offset_top = margin.y
	if preset != Control.PRESET_TOP_WIDE:
		c.offset_right = c.offset_left
	c.offset_bottom = c.offset_top
