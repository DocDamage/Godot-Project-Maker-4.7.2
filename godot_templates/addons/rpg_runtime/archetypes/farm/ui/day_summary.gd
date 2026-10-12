class_name RpgDaySummary
extends Control
## The morning's summary of a farm (T17.08): what the shipping bin sold overnight, what each
## thing earned, and the total. RpgDayEnd shows it once when a day begins after a night in which
## something was sold (never an empty one), over the paused game; `confirm`, `interact`,
## `cancel` or its button closes it.
##
## It builds itself (`setup`), like the screens of the arcade kinds: it is shown by code, not
## opened as a menu. The children a test or a theme can find: `%Heading`, `%Rows` (a Label a
## row), `%Total` and `%Ok`.

## It is gone and the game may go on.
signal closed

const CLOSE_ACTIONS: Array[StringName] = [&"confirm", &"interact", &"cancel"]
## Swallowed while it is shown, so that no menu opens over it.
const HELD_BACK: Array[StringName] = [&"menu"]

var sale: Dictionary = {}

var _armed := false  # the key that ended the day is up again
var _closing := false  # a key closed it and is still down
var _done := false

## The rows of a sale (RpgShippingBin.sell_all) as text: "Turnip x3 — 60 G".
static func lines(of_sale: Dictionary) -> PackedStringArray:
	var out := PackedStringArray()
	var short := RpgRealtimeText.t("UI_GOLD_SHORT", [], RpgStrings.KEYS)
	for raw: Variant in RpgUtil.to_array(of_sale.get("rows", [])):
		var row := RpgUtil.to_dict(raw)
		var qty := RpgUtil.to_int(row.get("qty", 0))
		var item_name := RpgFarmStrings.item_name(StringName(RpgUtil.to_str(row.get("item_id", ""))))
		out.append("%s x%d — %d %s" % [item_name, qty, RpgUtil.to_int(row.get("earned", 0)), short])
	return out

## "Total: 120 G".
static func total_text(of_sale: Dictionary) -> String:
	return RpgFarmStrings.t("FARM_SUMMARY_TOTAL", [RpgUtil.to_int(of_sale.get("total", 0)), RpgRealtimeText.t("UI_GOLD_SHORT", [], RpgStrings.KEYS)])

## True for a night in which something was sold: only then is there anything to show.
static func worth_showing(of_sale: Dictionary) -> bool:
	return not RpgUtil.to_array(of_sale.get("rows", [])).is_empty()

## Builds the screen for a sale. Called once, before or after it enters the tree.
func setup(of_sale: Dictionary) -> void:
	sale = of_sale
	process_mode = Node.PROCESS_MODE_ALWAYS
	# (with the offsets: a control that is in the tree keeps its size otherwise, which is none)
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var shade := ColorRect.new()
	shade.name = "Shade"
	shade.color = Color(0, 0, 0, 0.6)
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(shade)
	var center := CenterContainer.new()
	center.name = "Center"
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var panel := PanelContainer.new()
	panel.name = "Panel"
	center.add_child(panel)
	var box := VBoxContainer.new()
	box.name = "Box"
	panel.add_child(box)
	var heading := Label.new()
	heading.name = "Heading"
	heading.text = RpgFarmStrings.t("FARM_SUMMARY_TITLE")
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(heading)
	var rows := VBoxContainer.new()
	rows.name = "Rows"
	box.add_child(rows)
	var index := 0
	for line in lines(sale):
		index += 1
		var row := Label.new()
		row.name = "Row%d" % index
		row.text = line
		rows.add_child(row)
	var total := Label.new()
	total.name = "Total"
	total.text = total_text(sale)
	total.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	box.add_child(total)
	var ok := Button.new()
	ok.name = "Ok"
	ok.text = RpgRealtimeText.t("UI_CONTINUE", [], RpgStrings.KEYS)
	ok.pressed.connect(_on_ok)
	box.add_child(ok)
	for node: Node in [heading, rows, total, ok]:
		node.owner = self
		node.unique_name_in_owner = true
	if is_inside_tree():
		ok.grab_focus.call_deferred()

func _ready() -> void:
	var ok := get_node_or_null("%Ok") as Button
	if ok != null:
		ok.grab_focus.call_deferred()

func _on_ok() -> void:
	_closing = true

static func _down(action: StringName) -> bool:
	return InputMap.has_action(action) and Input.is_action_pressed(action)

func _any_down() -> bool:
	for action in CLOSE_ACTIONS:
		if _down(action):
			return true
	return false

## A press closes it, and the game goes on when the key is up again: the press that ended the
## day does not close it, and the press that closes it is not seen by the farmer.
func _process(_delta: float) -> void:
	if _done:
		return
	var down := _any_down()
	if _closing:
		if not down:
			close()
	elif not _armed:
		_armed = not down
	elif down:
		_closing = true

func _input(event: InputEvent) -> void:
	for action in HELD_BACK:
		if InputMap.has_action(action) and event.is_action(action):
			get_viewport().set_input_as_handled()

## Closes it at once.
func close() -> void:
	if _done:
		return
	_done = true
	closed.emit()
	queue_free()
