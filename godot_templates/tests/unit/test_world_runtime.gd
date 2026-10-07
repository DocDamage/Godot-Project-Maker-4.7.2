extends RefCounted
## RpgMapRoot spawn resolution and the SceneRouter busy flag (T4.02).

const SceneUtil := preload("res://builder/lib/scene_util.gd")
const ROUTER_SCRIPT := "res://addons/rpg_runtime/world/scene_router.gd"

func _spawn(parent: Node, spawn_name: String, spawn_id: StringName, pos: Vector2) -> RpgSpawnPoint:
	var s := RpgSpawnPoint.new()
	s.name = spawn_name
	s.spawn_id = spawn_id
	s.position = pos
	parent.add_child(s)
	return s

func _map(spawns: Array) -> RpgMapRoot:
	var map := RpgMapRoot.new()
	map.map_id = &"test"
	var holder := Node2D.new()
	holder.name = "SpawnPoints"
	map.add_child(holder)
	for entry in spawns:
		_spawn(holder, String(entry[0]), entry[0], entry[1])
	return map

func test_spawn_with_the_requested_id_wins(t) -> void:
	var map := _map([[&"first", Vector2(1, 1)], [&"default", Vector2(2, 2)], [&"door_exit", Vector2(3, 3)]])
	t.eq(map.get_spawn(&"door_exit").position, Vector2(3, 3))
	map.free()

func test_default_is_used_when_the_id_is_unknown(t) -> void:
	var map := _map([[&"first", Vector2(1, 1)], [&"default", Vector2(2, 2)]])
	t.eq(map.get_spawn(&"nowhere").position, Vector2(2, 2))
	map.free()

func test_first_spawn_is_used_without_a_default(t) -> void:
	var map := _map([[&"a", Vector2(5, 5)], [&"b", Vector2(6, 6)]])
	t.eq(map.get_spawn(&"nowhere").position, Vector2(5, 5))
	map.free()

func test_no_spawn_returns_null(t) -> void:
	var map := _map([])
	t.ok(map.get_spawn(&"default") == null)
	map.free()

func test_used_rect_px_is_the_union_of_the_layers(t) -> void:
	var map := RpgMapRoot.new()
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	var src := TileSetAtlasSource.new()
	src.texture = load("res://icon.svg")
	src.texture_region_size = Vector2i(16, 16)
	src.create_tile(Vector2i(0, 0))
	ts.add_source(src, 0)
	var a := TileMapLayer.new()
	a.tile_set = ts
	a.set_cell(Vector2i(0, 0), 0, Vector2i(0, 0))
	a.set_cell(Vector2i(2, 1), 0, Vector2i(0, 0))
	map.add_child(a)
	var b := TileMapLayer.new()
	b.tile_set = ts
	b.set_cell(Vector2i(4, 3), 0, Vector2i(0, 0))
	map.add_child(b)
	t.eq(map.used_rect_px(), Rect2(0, 0, 80, 64))
	map.free()

func test_the_busy_flag_ignores_a_second_call(t) -> void:
	var router: Node = load(ROUTER_SCRIPT).new()
	t.ok(not router.is_busy())
	router.set("_busy", true)
	router.go_to("res://does/not/matter.tscn")
	t.eq(router.ignored_calls, 1)
	router.go_to("res://does/not/matter.tscn")
	t.eq(router.ignored_calls, 2)
	t.ok(router.is_busy(), "the running change is not disturbed")
	router.free()
