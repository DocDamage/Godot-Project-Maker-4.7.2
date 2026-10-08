class_name RpgMenuUtil
extends RefCounted
## Helpers shared by the menu scripts.

const UI_DIR := "res://generated/scenes/ui/"
const TITLE_SCENE := "res://generated/scenes/ui/title_screen.tscn"
## The focus that a menu takes when it opens is silent: opening a menu must not tick.
const QUIET_AFTER_WIRING_MS := 300

static var _quiet_until_ms := 0

## Plays the sound of a UI slot (silent when the game has no audio or the slot is unset).
static func play_ui(slot: StringName) -> void:
	var router := RpgUtil.router()
	var audio: Node = router.audio if router != null else null
	if audio != null and audio.has_method("play_ui_slot"):
		audio.call("play_ui_slot", slot)

## Connects the cursor and confirm sounds of the controls of a menu, once per control.
static func attach_sounds(controls: Array) -> void:
	_quiet_until_ms = Time.get_ticks_msec() + QUIET_AFTER_WIRING_MS
	for item: Control in controls:
		var control := item
		if control == null or control.has_meta("rpg_ui_sounds"):
			continue
		control.set_meta("rpg_ui_sounds", true)
		control.focus_entered.connect(_on_control_focused)
		if control is BaseButton:
			(control as BaseButton).pressed.connect(_on_control_pressed)

static func _on_control_focused() -> void:
	if Time.get_ticks_msec() >= _quiet_until_ms:
		play_ui(&"sfx_ui_move")

static func _on_control_pressed() -> void:
	play_ui(&"sfx_ui_confirm")

static func scene_path(menu_name: String) -> String:
	return UI_DIR + menu_name + ".tscn"

## Instances a menu scene as a child of `parent` (it covers the parent) after setting `args` as
## properties. Returns null when the scene is missing.
static func open_submenu(parent: Control, menu_name: String, args: Dictionary = {}) -> Control:
	var path := scene_path(menu_name)
	if not ResourceLoader.exists(path):
		push_error("[RPG-UI] menu scene %s is missing" % path)
		return null
	var menu := (load(path) as PackedScene).instantiate() as Control
	for key: Variant in args.keys():  # before add_child, so _ready() already sees them
		menu.set(StringName(str(key)), args[key])
	parent.add_child(menu)
	return menu

## Wires focus_neighbor_top/bottom of `controls` as a wrapping vertical list.
static func wire_vertical(controls: Array) -> void:
	attach_sounds(controls)
	var n := controls.size()
	for i in n:
		var c: Control = controls[i]
		var prev: Control = controls[(i - 1 + n) % n]
		var nxt: Control = controls[(i + 1) % n]
		c.focus_neighbor_top = c.get_path_to(prev)
		c.focus_neighbor_bottom = c.get_path_to(nxt)

## Wires a grid (row-major) with wrapping in both directions.
static func wire_grid(controls: Array, columns: int) -> void:
	attach_sounds(controls)
	var n := controls.size()
	if n == 0 or columns <= 0:
		return
	var rows := ceili(float(n) / columns)
	for i in n:
		var c: Control = controls[i]
		var col := i % columns
		var row := i / columns
		var left := row * columns + (col - 1 + columns) % columns
		while left >= n:
			left -= 1
		var right := row * columns + (col + 1) % columns
		if right >= n:
			right = row * columns
		var up := ((row - 1 + rows) % rows) * columns + col
		while up >= n:
			up -= columns
		var down := ((row + 1) % rows) * columns + col
		if down >= n:
			down = col
		var to_left: Control = controls[left]
		c.focus_neighbor_left = c.get_path_to(to_left)
		var to_right: Control = controls[right]
		c.focus_neighbor_right = c.get_path_to(to_right)
		var to_up: Control = controls[up]
		c.focus_neighbor_top = c.get_path_to(to_up)
		var to_down: Control = controls[down]
		c.focus_neighbor_bottom = c.get_path_to(to_down)

## All visible, enabled Buttons and sliders under `node`, in tree order.
static func focusables(node: Node) -> Array:
	var out: Array = []
	_collect(node, out)
	return out

static func _collect(node: Node, out: Array) -> void:
	if node is Control:
		var c := node as Control
		if not c.visible:
			return
		if c.focus_mode != Control.FOCUS_NONE and (node is BaseButton or node is Slider):
			if not (node is BaseButton and (node as BaseButton).disabled):
				out.append(c)
	for child in node.get_children():
		_collect(child, out)
