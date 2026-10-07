class_name RpgMenuUtil
extends RefCounted
## Helpers shared by the menu scripts.

const UI_DIR := "res://generated/scenes/ui/"
const TITLE_SCENE := "res://generated/scenes/ui/title_screen.tscn"

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
	for key in args.keys():  # before add_child, so _ready() already sees them
		menu.set(key, args[key])
	parent.add_child(menu)
	return menu

## Wires focus_neighbor_top/bottom of `controls` as a wrapping vertical list.
static func wire_vertical(controls: Array) -> void:
	var n := controls.size()
	for i in n:
		var c := controls[i] as Control
		var prev := controls[(i - 1 + n) % n] as Control
		var nxt := controls[(i + 1) % n] as Control
		c.focus_neighbor_top = c.get_path_to(prev)
		c.focus_neighbor_bottom = c.get_path_to(nxt)

## Wires a grid (row-major) with wrapping in both directions.
static func wire_grid(controls: Array, columns: int) -> void:
	var n := controls.size()
	if n == 0 or columns <= 0:
		return
	var rows := ceili(float(n) / columns)
	for i in n:
		var c := controls[i] as Control
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
		c.focus_neighbor_left = c.get_path_to(controls[left])
		c.focus_neighbor_right = c.get_path_to(controls[right])
		c.focus_neighbor_top = c.get_path_to(controls[up])
		c.focus_neighbor_bottom = c.get_path_to(controls[down])

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
