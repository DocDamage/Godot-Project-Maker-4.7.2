extends RefCounted
## The farm's mode scene: boot adds it under SceneRouter as `combat`. It is RpgFarmMode (which
## asks for the calendar and makes the energy, the hotbar and the end of the day) with its part
## of the HUD as a child: the hotbar's ten slots and the energy bar over them, at the bottom of
## the screen. The option `starter_map.pass_out_loss` is the mode's property of that name.

const RECIPE_VERSION := 2

const SceneUtil := preload("../../lib/scene_util.gd")
const UiUtil := preload("../../lib/ui_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const FarmBuild := preload("farm_build.gd")

const SLOT_PX := 20
const GAP_PX := 2
const BAR_PX := 5
const MARGIN_PX := 4
const BAR_BACK := Color(0.08, 0.08, 0.1, 0.85)
const ENERGY_COLOR := Color(0.95, 0.8, 0.25)

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([FarmBuild.MODE_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "pass_out_loss": FarmBuild.pass_out_loss(ctx)})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var root := Node.new()
	root.name = "Combat"
	if not SceneUtil.attach_script(root, FarmBuild.MODE):
		issues.append(ctx.make_issue("VAL-002", {"file": FarmBuild.MODE}, FarmBuild.MODE))
	root.set("pass_out_loss", FarmBuild.pass_out_loss(ctx))
	root.add_child(_hud())
	var err := SceneUtil.save_scene(root, FarmBuild.MODE_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": FarmBuild.MODE_PATH, "err": err}, FarmBuild.MODE_PATH))
	return issues

func _hud() -> CanvasLayer:
	var hud := CanvasLayer.new()
	hud.name = "Hud"
	hud.layer = 5  # RpgFarmHud.LAYER: under the dialogue box and the menus
	SceneUtil.attach_script(hud, FarmBuild.HUD)
	var width := FarmBuild.HOTBAR_SLOTS * SLOT_PX + (FarmBuild.HOTBAR_SLOTS - 1) * GAP_PX
	var height := SLOT_PX + GAP_PX + BAR_PX
	var column := VBoxContainer.new()
	column.name = "Column"
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_theme_constant_override("separation", GAP_PX)
	# the middle of the bottom edge of the screen
	column.anchor_left = 0.5
	column.anchor_right = 0.5
	column.anchor_top = 1.0
	column.anchor_bottom = 1.0
	column.offset_left = -width / 2.0
	column.offset_right = width / 2.0
	column.offset_top = -(height + MARGIN_PX)
	column.offset_bottom = -MARGIN_PX
	hud.add_child(column)

	var bar := ProgressBar.new()
	bar.name = "EnergyBar"
	bar.custom_minimum_size = Vector2(width, BAR_PX)
	bar.show_percentage = false
	bar.min_value = 0.0
	bar.max_value = 100.0
	bar.value = 100.0
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var back := StyleBoxFlat.new()
	back.bg_color = BAR_BACK
	var fill := StyleBoxFlat.new()
	fill.bg_color = ENERGY_COLOR
	bar.add_theme_stylebox_override("background", back)
	bar.add_theme_stylebox_override("fill", fill)
	UiUtil.unique(bar)
	column.add_child(bar)

	var slots := HBoxContainer.new()
	slots.name = "Slots"
	slots.mouse_filter = Control.MOUSE_FILTER_IGNORE
	slots.add_theme_constant_override("separation", GAP_PX)
	UiUtil.unique(slots)
	column.add_child(slots)
	for i in FarmBuild.HOTBAR_SLOTS:
		slots.add_child(_slot(i))
	return hud

func _slot(index: int) -> PanelContainer:
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
