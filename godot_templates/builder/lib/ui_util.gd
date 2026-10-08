extends RefCounted
## Node-building helpers for the UI scene recipes. Every visible string is a translation key.

const SceneUtil := preload("scene_util.gd")

## A full-rect Control root with the runtime script `script_path`.
static func control_root(root_name: String, script_path: String) -> Control:
	var root := Control.new()
	root.name = root_name
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	SceneUtil.attach_script(root, script_path)
	return root

static func dim_background(root: Control, alpha: float = 0.6) -> ColorRect:
	var rect := ColorRect.new()
	rect.name = "Dim"
	rect.color = Color(0, 0, 0, alpha)
	rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(rect)
	return rect

## Center -> Panel -> Margin -> VBox. Returns the VBox the menu content goes into.
static func center_panel(root: Control, min_size: Vector2 = Vector2(220, 0)) -> VBoxContainer:
	var center := CenterContainer.new()
	center.name = "Center"
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(center)
	var panel := PanelContainer.new()
	panel.name = "Panel"
	panel.custom_minimum_size = min_size
	center.add_child(panel)
	var margin := MarginContainer.new()
	margin.name = "Margin"
	for side: String in ["left", "top", "right", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 8)
	panel.add_child(margin)
	var box := VBoxContainer.new()
	box.name = "Box"
	box.add_theme_constant_override("separation", 4)
	margin.add_child(box)
	return box

static func unique(node: Node) -> Node:
	node.unique_name_in_owner = true
	return node

static func label(parent: Node, node_name: String, text_key: String, is_unique: bool = false) -> Label:
	var l := Label.new()
	l.name = node_name
	l.text = text_key
	if is_unique:
		unique(l)
	parent.add_child(l)
	return l

static func button(parent: Node, node_name: String, text_key: String) -> Button:
	var b := Button.new()
	b.name = node_name
	b.text = text_key
	unique(b)
	parent.add_child(b)
	return b

## Wraps `parent`'s buttons in a vertical focus ring (top/bottom wrap) with explicit neighbors.
static func wire_vertical(controls: Array) -> void:
	var n := controls.size()
	for i in n:
		var c: Control = controls[i]
		var prev: Control = controls[(i - 1 + n) % n]
		var nxt: Control = controls[(i + 1) % n]
		c.focus_neighbor_top = c.get_path_to(prev)
		c.focus_neighbor_bottom = c.get_path_to(nxt)
		c.focus_neighbor_left = c.get_path_to(c)
		c.focus_neighbor_right = c.get_path_to(c)
