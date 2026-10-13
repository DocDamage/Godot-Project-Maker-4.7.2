class_name RpgMapRoot
extends Node2D
## Script of every map's root node.

@export var map_id: StringName = &""
@export var music_asset_id: String = ""
## The name shown on a save slot: a translation key. Empty means "MAP_<ID>" from `map_id`.
@export var display_name: String = ""
## An inside map (T12.62): a dimmer ambient, and the day/night cycle does not reach it. A map whose
## id starts with "interior" counts as one too (projects made before the flag).
@export var is_interior: bool = false
## A colour of your own for this map's ambient; transparent (the default) uses day or interior.
@export var ambient_override: Color = Color(0, 0, 0, 0)

const AMBIENT_NODE := "Ambient"
const CYCLE_STEP_S := 0.5  # how often the day/night colour is updated

var _ambient: CanvasModulate = null
var _since_update := 0.0

func _ready() -> void:
	_ambient = get_node_or_null(AMBIENT_NODE) as CanvasModulate
	if _ambient == null:
		_ambient = CanvasModulate.new()
		_ambient.name = AMBIENT_NODE
		add_child(_ambient)
	update_ambient()

func _process(delta: float) -> void:
	_since_update += delta
	if _since_update >= CYCLE_STEP_S:
		_since_update = 0.0
		update_ambient()

func interior() -> bool:
	return is_interior or str(map_id).begins_with("interior")

## Sets the CanvasModulate colour; only an outdoor map with the cycle on keeps updating. The cycle
## is on by its setting, or because the game has a calendar the light follows.
func update_ambient() -> void:
	if _ambient == null:
		return
	var settings := RpgUtil.settings()
	var cycle := not interior() and (RpgDayNight.calendar() != null or (settings != null and settings.day_night))
	var state := RpgUtil.state()
	var playtime := state.playtime_s if state != null else 0.0
	_ambient.color = ambient_override if ambient_override.a > 0.0 else RpgDayNight.map_ambient(interior(), cycle, playtime)
	set_process(cycle and ambient_override.a <= 0.0)

## The translation key of this map's name ("MAP_STARTER_MAP" for the map `starter_map`).
func name_key() -> String:
	if display_name != "":
		return display_name
	var id := str(map_id) if str(map_id) != "" else scene_file_path.get_file().get_basename()
	return "MAP_" + id.to_upper()

## The spawn with this id; else "default"; else the first spawn in the map; else null.
func get_spawn(spawn_id: StringName) -> RpgSpawnPoint:
	var spawns: Array[RpgSpawnPoint] = []
	_collect_spawns(self, spawns)
	for spawn in spawns:
		if spawn.spawn_id == spawn_id:
			return spawn
	for spawn in spawns:
		if spawn.spawn_id == &"default":
			return spawn
	return spawns[0] if spawns.size() > 0 else null

func _collect_spawns(node: Node, out: Array[RpgSpawnPoint]) -> void:
	for child in node.get_children():
		if child is RpgSpawnPoint:
			out.append(child)
		_collect_spawns(child, out)

## The first node of group "player" inside this map, or null.
func get_player() -> Node2D:
	for node in get_tree().get_nodes_in_group("player"):
		if node is Node2D and is_ancestor_of(node):
			return node
	return null

## Union of every TileMapLayer's used rectangle, in pixels (map-local), or an empty Rect2. On an
## isometric map (T17.14) it is the rectangle around the diamonds that are painted.
func used_rect_px() -> Rect2:
	var result := Rect2()
	var first := true
	for layer in _collect_layers(self):
		if layer.tile_set == null:
			continue
		var cells := layer.get_used_rect()
		if cells.size == Vector2i.ZERO:
			continue
		var rect := RpgIso.used_rect(layer, cells)
		rect.position += layer.position
		result = rect if first else result.merge(rect)
		first = false
	return result

func _collect_layers(node: Node) -> Array[TileMapLayer]:
	var layers: Array[TileMapLayer] = []
	for child in node.get_children():
		if child is TileMapLayer:
			layers.append(child)
		layers.append_array(_collect_layers(child))
	return layers
