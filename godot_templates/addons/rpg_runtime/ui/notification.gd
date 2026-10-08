class_name RpgNotification
extends Control
## Toast stack, top-right: 2.5 s each, at most 3 at a time. Listens to Events.notify.

const LIFETIME := 2.5
const MAX_TOASTS := 3

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var bus := RpgUtil.events()
	if bus != null:
		bus.notify.connect(show_toast)

func _stack() -> VBoxContainer:
	return get_node("%Stack") as VBoxContainer

func toast_count() -> int:
	return _stack().get_child_count()

func show_toast(text: String) -> void:
	var stack := _stack()
	while stack.get_child_count() >= MAX_TOASTS:
		var oldest := stack.get_child(0)
		stack.remove_child(oldest)
		oldest.queue_free()
	var panel := PanelContainer.new()
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var label := Label.new()
	label.text = tr(text)
	panel.add_child(label)
	stack.add_child(panel)
	if is_inside_tree():
		get_tree().create_timer(LIFETIME, true).timeout.connect(_expire.bind(panel))

## A toast that was dropped to make room has been freed by the time its timer ends, so the
## parameter takes anything and is checked before use.
func _expire(panel: Variant) -> void:
	if not is_instance_valid(panel):
		return
	var node: Node = panel
	var parent := node.get_parent()
	if parent != null:
		parent.remove_child(node)
		node.queue_free()
