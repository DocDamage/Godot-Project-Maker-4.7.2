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

static func events() -> RpgEvents:
	return autoload(&"Events") as RpgEvents

static func state() -> RpgGameState:
	return autoload(&"GameState") as RpgGameState

## The most hit points `stats` can have: max_hp with the owner's equipment applied.
static func max_hp(stats: RpgStats) -> int:
	var game := state()
	return roundi(game.effective_stat(stats, &"max_hp")) if game != null else stats.max_hp

## The most magic points `stats` can have: max_mp with the owner's equipment applied.
static func max_mp(stats: RpgStats) -> int:
	var game := state()
	return roundi(game.effective_stat(stats, &"max_mp")) if game != null else stats.max_mp

static func router() -> RpgSceneRouter:
	return autoload(&"SceneRouter") as RpgSceneRouter

static func save_manager() -> RpgSaveManager:
	return autoload(&"SaveManager") as RpgSaveManager

static func settings() -> RpgSettingsStore:
	return autoload(&"RpgSettings") as RpgSettingsStore

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

## Where a node is in the world: its global position, or, for a node outside the tree (unit
## tests), the position its 2D ancestors' transforms give it.
static func world_position(node: Node2D) -> Vector2:
	if node.is_inside_tree():
		return node.global_position
	var xf := Transform2D.IDENTITY
	var at: Node = node
	while at is Node2D:
		xf = (at as Node2D).transform * xf
		at = at.get_parent()
	return xf.origin

## The tile size of a map in pixels (its first TileMapLayer with a tile set), 16 when it has none.
## An isometric map (T17.14) answers with the length of one step from a diamond to the next
## (RpgIso.unit): what a reach, a spacing or a step counter means by a tile there.
static func map_tile_px(map: Node) -> int:
	if map != null:
		for layer in map.find_children("*", "TileMapLayer", true, false):
			var tiles := layer as TileMapLayer
			if tiles.tile_set != null:
				if RpgIso.is_iso(tiles.tile_set):
					return RpgIso.unit(tiles.tile_set.tile_size)
				return tiles.tile_set.tile_size.x
	return 16

## True when `actor` stands beside `thing` in a side-view room: within `tile` px up or down of it
## (not on a platform above it or in a pit below). Without an actor there is nothing to refuse.
static func beside(thing: Node2D, actor: Node, tile: float = 16.0) -> bool:
	if not (actor is Node2D) or thing == null:
		return true
	return absf(world_position(actor as Node2D).y - world_position(thing).y) <= tile

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
		var items: Array = value
		for v: Variant in items:
			out.append(restore_numbers(v))
		return out
	if value is Dictionary:
		var out_d := {}
		var table: Dictionary = value
		for k: Variant in table.keys():
			out_d[k] = restore_numbers(table[k])
		return out_d
	return value

# ---- typed conversions of Variant values (strict GDScript, T12.29) -------------------------------
# JSON and Dictionary values arrive as Variant. Passing one to a typed parameter, or converting it
# with int()/float()/bool(), is flagged by the strict warnings; these functions are the one place
# that looks at the type. They return the fallback when the value is not what was expected.

## `int(v)` for a Variant: numbers (JSON numbers are floats), booleans and numeric strings.
static func to_int(v: Variant, fallback: int = 0) -> int:
	match typeof(v):
		TYPE_INT:
			var i: int = v
			return i
		TYPE_FLOAT:
			var f: float = v
			return int(f)
		TYPE_BOOL:
			var b: bool = v
			return int(b)
		TYPE_STRING, TYPE_STRING_NAME:
			var s: String = v
			return s.to_int()
	return fallback

## `float(v)` for a Variant.
static func to_float(v: Variant, fallback: float = 0.0) -> float:
	match typeof(v):
		TYPE_INT, TYPE_FLOAT:
			var f: float = v
			return f
		TYPE_BOOL:
			var b: bool = v
			return float(b)
		TYPE_STRING, TYPE_STRING_NAME:
			var s: String = v
			return s.to_float()
	return fallback

## `bool(v)` for a Variant: booleans and numbers (zero is false).
static func to_bool(v: Variant, fallback: bool = false) -> bool:
	match typeof(v):
		TYPE_BOOL:
			var b: bool = v
			return b
		TYPE_INT, TYPE_FLOAT:
			var f: float = v
			return f != 0.0
	return fallback

## `String(v)` for a Variant (any value prints as text).
static func to_str(v: Variant) -> String:
	return str(v)

## `StringName(v)` for a Variant.
static func to_name(v: Variant) -> StringName:
	return StringName(str(v))

## The Dictionary in `v`, or an empty one.
static func to_dict(v: Variant) -> Dictionary:
	if v is Dictionary:
		var d: Dictionary = v
		return d
	return {}

## The Array in `v`, or an empty one.
static func to_array(v: Variant) -> Array:
	if v is Array:
		var a: Array = v
		return a
	return []
