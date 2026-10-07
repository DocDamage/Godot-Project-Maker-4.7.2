class_name RpgUtil
extends RefCounted
## Small static helpers. Autoloads are looked up by node path instead of by global name, so the
## runtime scripts also parse (and unit-test) in a project that has not registered the autoloads.

static func tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

## The autoload node `/root/<autoload_name>`, or null.
static func autoload(autoload_name: StringName) -> Node:
	var t := tree()
	if t == null or t.root == null:
		return null
	return t.root.get_node_or_null(NodePath(String(autoload_name)))

static func events() -> Node:
	return autoload(&"Events")

static func state() -> Node:
	return autoload(&"GameState")

static func router() -> Node:
	return autoload(&"SceneRouter")

static func settings() -> Node:
	return autoload(&"RpgSettings")

## Emits a signal on the Events bus when the bus exists.
static func emit(signal_name: StringName, args: Array = []) -> void:
	var bus := events()
	if bus == null or not bus.has_signal(signal_name):
		return
	match args.size():
		0:
			bus.emit_signal(signal_name)
		1:
			bus.emit_signal(signal_name, args[0])
		2:
			bus.emit_signal(signal_name, args[0], args[1])
		_:
			bus.emit_signal(signal_name, args[0], args[1], args[2])

## Shows a toast through Events.notify.
static func notify(text: String) -> void:
	emit(&"notify", [text])

## The first node of a group (a UI service such as the dialogue box), or null.
static func service(group: StringName) -> Node:
	var t := tree()
	return t.get_first_node_in_group(group) if t != null else null

## Whole-number floats (what JSON gives back for ints) become ints; containers are converted deeply.
static func restore_numbers(value: Variant) -> Variant:
	if value is float:
		var f: float = value
		if f == floorf(f) and absf(f) < 9.0e15:
			return int(f)
		return f
	if value is Array:
		var out: Array = []
		for v in value:
			out.append(restore_numbers(v))
		return out
	if value is Dictionary:
		var out_d := {}
		for k in value.keys():
			out_d[k] = restore_numbers(value[k])
		return out_d
	return value
