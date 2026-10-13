@tool
extends RefCounted
## World repair (T13.24): mends the doors of a project's maps that lead nowhere and the maps that
## cannot be reached, by **adding** spawn points and doors (and by pointing a door at a map that
## exists). Nothing a person placed is moved or deleted, and a door that has its partner is never
## changed. The headless tool (builder/tools/world_repair.gd) and the dock's validator use the
## same two steps:
##
##   plan_repairs(...) -> actions      what would be done, each for one map file
##   apply(action, root) -> nodes      does one action in that map's scene tree
##
## An action is {kind, map, node, what, cause_map, cause_node, ...}: `kind` is "retarget" (a door
## gets a target that exists), "spawn" (a spawn point is added), "door" (a door is added), "exit"
## (the exit of a side-view room is added, T14.06) or
## "unfixable" (nothing safe can be done; `what` says why). `map` is the scene the action changes
## and `node` the node it is about; `what` is the sentence the report shows. `cause_map` and
## `cause_node` name the finding the action answers (the door that led nowhere, or the map that
## could not be reached with an empty node), so the dock can fix one row.
##
## Doors added by a repair stand on the floor beside the wall, not in it (the wall is the
## person's): walking onto the cell uses the door, and the player arrives one cell further in.

const MapGraph := preload("map_graph.gd")
const JsonIo := preload("json_io.gd")

const DOOR_SCRIPT := "res://addons/rpg_runtime/world/door.gd"
const SPAWN_SCRIPT := "res://addons/rpg_runtime/world/spawn_point.gd"
## The exit of a side-view room (T14.06). A project of another archetype has no such script and
## no such maps, so nothing here ever loads it there.
const ROOM_EXIT_SCRIPT := "res://addons/rpg_runtime/archetypes/metroidvania/room_exit.gd"
const WORLD_PLAN := "res://rpggen/world_plan.json"
const START := "res://game/maps/starter_map.tscn"
const SEARCH_TILES := 3
const EDGES: Array[String] = ["E", "S", "W", "N"]
const OPPOSITE := {"N": "S", "S": "N", "E": "W", "W": "E"}
const INWARD := {"N": Vector2i(0, 1), "S": Vector2i(0, -1), "E": Vector2i(-1, 0), "W": Vector2i(1, 0)}
const FACING := {"N": "down", "S": "up", "E": "left", "W": "right"}

# ---------------------------------------------------------------- what a map looks like

## What the repair needs to know of a map: {tile, rect (cells, Rect2i), solid ({Vector2i: true}),
## painted ({Vector2i: true})}. A cell is walkable when something is painted there and no layer
## has a tile with a collision shape on it. An isometric map (T17.14) also has `iso`, the
## diamond of its cells: `cell_of` and `center_of` then count by it, and `tile` is one step.
static func survey(root: Node) -> Dictionary:
	var tile := 16
	var diamond := Vector2i.ZERO
	var solid := {}
	var painted := {}
	var rect := Rect2i()
	var first := true
	for found in root.find_children("*", "TileMapLayer", true, false):
		var layer := found as TileMapLayer
		if layer.tile_set == null:
			continue
		tile = layer.tile_set.tile_size.x
		if RpgIso.is_iso(layer.tile_set):
			diamond = layer.tile_set.tile_size
			tile = RpgIso.unit(diamond)
		for cell in layer.get_used_cells():
			painted[cell] = true
			rect = Rect2i(cell, Vector2i.ONE) if first else rect.merge(Rect2i(cell, Vector2i.ONE))
			first = false
			var data := layer.get_cell_tile_data(cell)
			if data != null and layer.tile_set.get_physics_layers_count() > 0 and data.get_collision_polygons_count(0) > 0:
				solid[cell] = true
	var info := {"tile": tile, "rect": rect, "solid": solid, "painted": painted, "side": JsonIo.to_bool(root.get("side_view"))}
	if diamond != Vector2i.ZERO:
		info["iso"] = diamond
	if info["side"]:
		# a room is as large as it says, not as large as what is painted (most of it is air)
		var size: Variant = root.get("room_size")
		if size is Vector2i:
			var cells: Vector2i = size
			info["rect"] = Rect2i(Vector2i.ZERO, cells)
		# and solid is what a body stands on: the world layer or a one-way platform
		for found in root.find_children("*", "TileMapLayer", true, false):
			var layer := found as TileMapLayer
			if layer.tile_set == null or layer.tile_set.get_physics_layers_count() < 2:
				continue
			for cell in layer.get_used_cells():
				var data := layer.get_cell_tile_data(cell)
				if data != null and data.get_collision_polygons_count(1) > 0:
					solid[cell] = true
	return info

static func walkable(info: Dictionary, cell: Vector2i) -> bool:
	var painted: Dictionary = info["painted"]
	var solid: Dictionary = info["solid"]
	return painted.has(cell) and not solid.has(cell)

static func cell_of(info: Dictionary, position: Vector2) -> Vector2i:
	if info.get("iso") is Vector2i:
		var diamond: Vector2i = info["iso"]
		return RpgIso.screen_to_cell(position, diamond)
	var tile := JsonIo.to_int(info["tile"])
	return Vector2i(floori(position.x / tile), floori(position.y / tile))

static func center_of(info: Dictionary, cell: Vector2i) -> Vector2:
	if info.get("iso") is Vector2i:
		var diamond: Vector2i = info["iso"]
		return RpgIso.cell_to_screen(cell, diamond)
	var tile := JsonIo.to_float(info["tile"])
	return Vector2(cell) * tile + Vector2(tile, tile) / 2.0

## The walkable cell nearest to `wanted` within SEARCH_TILES (rings outwards, in reading order),
## or `none` when there is none.
static func nearest_walkable(info: Dictionary, wanted: Vector2i, none: Vector2i) -> Vector2i:
	for radius in SEARCH_TILES + 1:
		for dy in range(-radius, radius + 1):
			for dx in range(-radius, radius + 1):
				if maxi(absi(dx), absi(dy)) != radius:
					continue
				var cell := wanted + Vector2i(dx, dy)
				if walkable(info, cell):
					return cell
	return none

## The edge of the map a cell lies on or nearest to.
static func edge_of(info: Dictionary, cell: Vector2i) -> String:
	var rect: Rect2i = info["rect"]
	var distances := {
		"W": cell.x - rect.position.x, "E": rect.end.x - 1 - cell.x,
		"N": cell.y - rect.position.y, "S": rect.end.y - 1 - cell.y,
	}
	var best := "E"
	for edge in EDGES:
		if JsonIo.to_int(distances[edge]) < JsonIo.to_int(distances[best]):
			best = edge
	return best

## A place for a door on `edge`: {door, spawn} cells, the door on the first walkable cell in from
## the wall and the spawn one cell further in, scanned along the edge from `along` (a fraction of
## its length, 0.5 = the middle) outwards. {} when the edge has no such place.
static func place_on_edge(info: Dictionary, edge: String, along: float = 0.5) -> Dictionary:
	var rect: Rect2i = info["rect"]
	var inward: Vector2i = INWARD[edge]
	var length := rect.size.x if edge in ["N", "S"] else rect.size.y
	var middle := clampi(roundi(along * (length - 1)), 0, maxi(0, length - 1))
	for offset in length:
		for sign: int in [1, -1]:
			var at: int = middle + offset * sign
			if at < 0 or at >= length or (offset == 0 and sign == -1):
				continue
			var start := Vector2i(rect.position.x + at, rect.position.y) if edge == "N" else Vector2i(rect.position.x + at, rect.end.y - 1)
			if edge == "W":
				start = Vector2i(rect.position.x, rect.position.y + at)
			elif edge == "E":
				start = Vector2i(rect.end.x - 1, rect.position.y + at)
			for depth in 3:  # the wall may be one or two cells thick
				var door: Vector2i = start + inward * depth
				if walkable(info, door) and walkable(info, door + inward):
					return {"door": door, "spawn": door + inward}
	return {}

# ---------------------------------------------------------------- the stored plan

static func read_plan(path: String = WORLD_PLAN) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JsonIo.read(path)
	if parsed is Dictionary:
		var plan: Dictionary = parsed
		return plan
	return {}

## The maps of the plan: the areas of a top-down world, and the rooms of a metroidvania (T14.06).
## A room is given the `doors` an area has, made from its exits, so the same lookups read both.
static func _areas(plan: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var raw: Variant = plan.get("areas", [])
	if raw is Array:
		var list: Array = raw
		for entry: Variant in list:
			if entry is Dictionary:
				var area: Dictionary = entry
				out.append(area)
	var rooms_raw: Variant = JsonIo.to_dict(plan.get("rooms", {})).get("list", [])
	if rooms_raw is Array:
		var rooms: Array = rooms_raw
		var map_of := {}
		for entry: Variant in rooms:
			var listed := JsonIo.to_dict(entry)
			map_of[JsonIo.to_str(listed.get("id", ""))] = JsonIo.to_str(listed.get("map", ""))
		for entry: Variant in rooms:
			var room := JsonIo.to_dict(entry).duplicate()
			var doors: Array = []
			var exits: Variant = room.get("exits", [])
			if exits is Array:
				var exit_list: Array = exits
				for exit_raw: Variant in exit_list:
					var exit_spec := JsonIo.to_dict(exit_raw)
					doors.append({
						"id": exit_spec.get("id", ""), "edge": exit_spec.get("edge", ""), "spawn_id": exit_spec.get("id", ""),
						"to": exit_spec.get("to", ""), "to_map": map_of.get(JsonIo.to_str(exit_spec.get("to", "")), ""),
						"to_spawn": exit_spec.get("to_exit", ""),
					})
			room["doors"] = doors
			out.append(room)
	return out

static func _area_path(area: Dictionary) -> String:
	var map := JsonIo.to_str(area.get("map", ""))
	return map if map.contains("://") else "res://" + map

static func area_of_map(plan: Dictionary, map_path: String) -> Dictionary:
	for area in _areas(plan):
		if _area_path(area) == map_path:
			return area
	return {}

static func _doors(area: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var raw: Variant = area.get("doors", [])
	if raw is Array:
		var list: Array = raw
		for entry: Variant in list:
			if entry is Dictionary:
				var door: Dictionary = entry
				out.append(door)
	return out

static func _grid_cell(plan: Dictionary, area_id: String) -> Vector2i:
	var grid: Variant = plan.get("grid", {})
	if not (grid is Dictionary):
		return Vector2i(9999, 9999)
	var table: Dictionary = grid
	var raw: Variant = table.get(area_id)
	if not (raw is Array):
		return Vector2i(9999, 9999)
	var pair: Array = raw
	return Vector2i(JsonIo.to_int(pair[0]), JsonIo.to_int(pair[1])) if pair.size() == 2 else Vector2i(9999, 9999)

static func _pair_cell(value: Variant) -> Vector2i:
	if not (value is Array):
		return Vector2i.ZERO
	var pair: Array = value
	return Vector2i(JsonIo.to_int(pair[0]), JsonIo.to_int(pair[1])) if pair.size() == 2 else Vector2i.ZERO

# ---------------------------------------------------------------- planning

## What has to be done to `maps` (scene paths): the actions, in the order they must be applied.
## `instance_of.call(path)` gives a map's instantiated root (the caller owns it); `plan` is the
## stored world plan ({} without one). The actions take earlier ones into account, so a second
## call after applying them finds nothing more to do.
static func plan_repairs(maps: Array[String], plan: Dictionary, instance_of: Callable, start: String = START) -> Array[Dictionary]:
	var actions: Array[Dictionary] = []
	var graph := MapGraph.read(maps, instance_of)
	var surveys := {}
	for path: String in graph.keys():
		var map_root: Node = instance_of.call(path)
		surveys[path] = survey(map_root)
	var exists := func(path: String) -> bool: return graph.has(path) or FileAccess.file_exists(path)
	# 1. doors whose map does not exist
	for found in MapGraph.dangling(graph, exists):
		if found["missing"] == "map":
			var before := actions.size()
			_retarget(found, graph, plan, actions)
			_caused_by(actions, before, str(found["map"]), str(found["node"]))
	# 2. doors whose spawn point does not exist
	for found in MapGraph.dangling(graph, exists):
		if found["missing"] == "spawn":
			var before := actions.size()
			if _is_room(surveys, str(found["target"])):
				_add_room_arrival(found, graph, surveys, actions)
			else:
				_add_arrival(found, graph, surveys, plan, instance_of, actions)
			_caused_by(actions, before, str(found["map"]), str(found["node"]))
	# 3. maps the start cannot reach
	for path in MapGraph.unreachable(graph, start):
		var before := actions.size()
		if _is_room(surveys, path):
			_join_rooms(path, graph, surveys, plan, start, actions)
		else:
			_join(path, graph, surveys, plan, start, actions)
		_caused_by(actions, before, path, "")
	for action in actions:
		if not action.has("tile") and surveys.has(action["map"]):
			var info: Dictionary = surveys[action["map"]]
			action["tile"] = info["tile"]
	return actions

static func _caused_by(actions: Array[Dictionary], from: int, cause_map: String, cause_node: String) -> void:
	for i in range(from, actions.size()):
		actions[i]["cause_map"] = cause_map
		actions[i]["cause_node"] = cause_node

## The actions that answer one finding of the validator (its file and node).
static func actions_for(actions: Array[Dictionary], file: String, node: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for action in actions:
		if str(action.get("cause_map", "")) == file and str(action.get("cause_node", "")) == node:
			out.append(action)
	return out

static func _note(graph: Dictionary, map: String, door: Dictionary = {}, spawn: String = "") -> void:
	var entry: Dictionary = graph[map]
	if not door.is_empty():
		var doors: Array = entry["doors"]
		doors.append(door)
	if spawn != "":
		var spawns: Array = entry["spawns"]
		spawns.append(spawn)

## Repair 1: the map the plan paired the door with, else the nearest map of the plan's grid.
static func _retarget(found: Dictionary, graph: Dictionary, plan: Dictionary, actions: Array[Dictionary]) -> void:
	var source := str(found["map"])
	var area := area_of_map(plan, source)
	var node_name := str(found["node"]).get_file()
	var target := ""
	var spawn := ""
	for door in _doors(area):
		var planned := "res://" + JsonIo.to_str(door.get("to_map", ""))
		if JsonIo.to_str(door.get("id", "")) == node_name and graph.has(planned) and planned != source:
			target = planned
			spawn = JsonIo.to_str(door.get("to_spawn", ""))
	if target == "" and not area.is_empty():
		var here := _grid_cell(plan, JsonIo.to_str(area.get("id", "")))
		var best := 99999
		for other in _areas(plan):
			var path := _area_path(other)
			if path == source or not graph.has(path):
				continue
			var at := _grid_cell(plan, JsonIo.to_str(other.get("id", "")))
			var distance := absi(at.x - here.x) + absi(at.y - here.y)
			if distance < best:
				best = distance
				target = path
				spawn = "from_" + JsonIo.to_str(area.get("id", ""))
	if target == "":
		actions.append({"kind": "unfixable", "map": source, "node": found["node"], "what": "the door %s leads to the missing map %s, and the world plan knows no other map for it" % [node_name, str(found["target"]).get_file()]})
		return
	actions.append({
		"kind": "retarget", "map": source, "node": found["node"], "target_map": target, "target_spawn": spawn,
		"what": "the door %s now leads to %s (it led to the missing map %s)" % [node_name, target.get_file(), str(found["target"]).get_file()],
	})
	var entry: Dictionary = graph[source]
	var doors: Array = entry["doors"]
	for door: Dictionary in doors:
		if door["node"] == found["node"]:
			door["target"] = target
			door["spawn"] = spawn

## Repair 2: a spawn point on the target where the door's players arrive, and a door back beside
## it when the target has no door to the source.
static func _add_arrival(found: Dictionary, graph: Dictionary, surveys: Dictionary, plan: Dictionary, instance_of: Callable, actions: Array[Dictionary]) -> void:
	var source := str(found["map"])
	var target := str(found["target"])
	var spawn_id := str(found["spawn"])
	var source_info: Dictionary = surveys[source]
	var target_info: Dictionary = surveys[target]
	var source_root: Node = instance_of.call(source)
	var door_node := source_root.get_node_or_null(str(found["node"])) as Node2D
	var door_cell := cell_of(source_info, door_node.position) if door_node != null else Vector2i.ZERO
	var facing := "down"
	var spawn_cell := Vector2i(-9999, -9999)
	var back_cell := Vector2i(-9999, -9999)
	var back_name := "%s_door_%s" % [target.get_file().get_basename(), source.get_file().get_basename()]
	# from the stored plan when the pair is planned
	for door in _doors(area_of_map(plan, target)):
		if JsonIo.to_str(door.get("spawn_id", "")) == spawn_id:
			var planned := _pair_cell(door.get("spawn"))
			if walkable(target_info, planned):
				spawn_cell = planned
				facing = JsonIo.to_str(door.get("facing", "down"))
				var planned_door := _pair_cell(door.get("cell"))
				back_cell = planned_door if walkable(target_info, planned_door) else Vector2i(-9999, -9999)
				back_name = JsonIo.to_str(door.get("id", back_name))
	if spawn_cell.x == -9999:  # by geometry: the opposite edge, the same offset along it
		var edge := edge_of(source_info, door_cell)
		var source_rect: Rect2i = source_info["rect"]
		var along := 0.5
		if edge in ["N", "S"] and source_rect.size.x > 1:
			along = float(door_cell.x - source_rect.position.x) / float(source_rect.size.x - 1)
		elif source_rect.size.y > 1:
			along = float(door_cell.y - source_rect.position.y) / float(source_rect.size.y - 1)
		var opposite: String = OPPOSITE[edge]
		var place := place_on_edge(target_info, opposite, along)
		if not place.is_empty():
			var place_door: Vector2i = place["door"]
			var place_spawn: Vector2i = place["spawn"]
			var target_rect: Rect2i = target_info["rect"]
			var length := target_rect.size.x if opposite in ["N", "S"] else target_rect.size.y
			var wanted := clampi(roundi(along * (length - 1)), 0, maxi(0, length - 1))
			var got := (place_door.x - target_rect.position.x) if opposite in ["N", "S"] else (place_door.y - target_rect.position.y)
			if absi(got - wanted) <= SEARCH_TILES:
				spawn_cell = place_spawn
				back_cell = place_door
				facing = FACING[opposite]
	if spawn_cell.x == -9999:
		actions.append({"kind": "unfixable", "map": target, "node": found["node"], "what": "%s has no free floor within %d tiles of where the door %s of %s arrives" % [target.get_file(), SEARCH_TILES, str(found["node"]).get_file(), source.get_file()]})
		return
	actions.append({
		"kind": "spawn", "map": target, "node": "SpawnPoints/" + spawn_id, "spawn_id": spawn_id,
		"position": center_of(target_info, spawn_cell), "facing": facing,
		"what": "added the spawn point %s (the door %s of %s arrives there)" % [spawn_id, str(found["node"]).get_file(), source.get_file()],
	})
	_note(graph, target, {}, spawn_id)
	if MapGraph.has_door(graph, target, source):
		return
	if back_cell.x == -9999:
		back_cell = nearest_walkable(target_info, spawn_cell - _step_of(facing), Vector2i(-9999, -9999))
		if back_cell == spawn_cell or back_cell.x == -9999:
			return  # no room for the door back: the arrival is mended, the way back is not
	var home := _spawn_near(source_root, source_info, door_cell)
	if home == "":
		home = "from_" + target.get_file().get_basename()
		var source_edge := edge_of(source_info, door_cell)
		var inward: Vector2i = INWARD[source_edge]
		var beside := nearest_walkable(source_info, door_cell + inward, Vector2i(-9999, -9999))
		if beside.x == -9999:
			return
		actions.append({
			"kind": "spawn", "map": source, "node": "SpawnPoints/" + home, "spawn_id": home,
			"position": center_of(source_info, beside), "facing": FACING[source_edge],
			"what": "added the spawn point %s (the new door of %s arrives there)" % [home, target.get_file()],
		})
		_note(graph, source, {}, home)
	actions.append({
		"kind": "door", "map": target, "node": "Triggers/" + back_name, "name": back_name,
		"position": center_of(target_info, back_cell), "target_map": source, "target_spawn": home,
		"what": "added the door %s back to %s" % [back_name, source.get_file()],
	})
	_note(graph, target, {"node": "Triggers/" + back_name, "target": source, "spawn": home})

static func _step_of(facing: String) -> Vector2i:
	match facing:
		"up":
			return Vector2i(0, -1)
		"left":
			return Vector2i(-1, 0)
		"right":
			return Vector2i(1, 0)
	return Vector2i(0, 1)

## The id of a spawn point of `root` within two cells of `cell`, or "".
static func _spawn_near(root: Node, info: Dictionary, cell: Vector2i) -> String:
	var nodes: Array[Node] = []
	MapGraph._walk(root, nodes)
	for node in nodes:
		if MapGraph._is(node, MapGraph.SPAWN_SUFFIX) and node is Node2D:
			var at := cell_of(info, (node as Node2D).position)
			if maxi(absi(at.x - cell.x), absi(at.y - cell.y)) <= 2 and str(node.get("spawn_id")) != "default":
				return str(node.get("spawn_id"))
	return ""

## Repair 3: a door pair between an unreachable map and a reachable one beside it on the plan's
## grid (the start map when the map is not in the plan).
static func _join(path: String, graph: Dictionary, surveys: Dictionary, plan: Dictionary, start: String, actions: Array[Dictionary]) -> void:
	var reachable := MapGraph.reachable(graph, start)
	var area := area_of_map(plan, path)
	var partner := ""
	var edge := ""
	if not area.is_empty():
		var here := _grid_cell(plan, JsonIo.to_str(area.get("id", "")))
		var steps := {"E": Vector2i(1, 0), "S": Vector2i(0, 1), "W": Vector2i(-1, 0), "N": Vector2i(0, -1)}
		for candidate_edge in EDGES:
			var step: Vector2i = steps[candidate_edge]
			for other in _areas(plan):
				var other_path := _area_path(other)
				if partner == "" and reachable.has(other_path) and _grid_cell(plan, JsonIo.to_str(other.get("id", ""))) == here + step:
					partner = other_path
					edge = candidate_edge
	var tried: Array[String] = []
	var place_here := {}
	var place_there := {}
	var here_info: Dictionary = surveys[path]
	if partner != "":
		var there_info: Dictionary = surveys[partner]
		var facing_edge: String = OPPOSITE[edge]
		tried.append("%s of %s" % [edge, path.get_file()])
		place_here = place_on_edge(here_info, edge)
		place_there = place_on_edge(there_info, facing_edge)
	elif area.is_empty() and graph.has(start):
		partner = start
		var start_info: Dictionary = surveys[start]
		for candidate_edge in EDGES:  # any edge of the start map with room, and the one facing it
			var facing_edge: String = OPPOSITE[candidate_edge]
			tried.append("%s of %s" % [candidate_edge, start.get_file()])
			place_there = place_on_edge(start_info, candidate_edge)
			place_here = place_on_edge(here_info, facing_edge)
			if not place_there.is_empty() and not place_here.is_empty():
				edge = facing_edge
				break
	if partner == "" or place_here.is_empty() or place_there.is_empty():
		var why := "no reachable map lies beside it in the world plan" if partner == "" else "no cell is free on both sides (tried %s)" % ", ".join(PackedStringArray(tried))
		actions.append({"kind": "unfixable", "map": path, "node": "", "what": "%s cannot be reached, and %s" % [path.get_file(), why]})
		return
	var here_id := path.get_file().get_basename()
	var there_id := partner.get_file().get_basename()
	var sides := [
		[path, surveys[path], place_here, edge, here_id, there_id, partner],
		[partner, surveys[partner], place_there, OPPOSITE[edge], there_id, here_id, path],
	]
	for side: Array in sides:
		var map: String = side[0]
		var info: Dictionary = side[1]
		var place: Dictionary = side[2]
		var side_edge: String = side[3]
		var own: String = side[4]
		var other: String = side[5]
		var other_map: String = side[6]
		var spawn_id := "from_" + other
		var door_name := "%s_door_%s" % [own, other]
		var spawn_at: Vector2i = place["spawn"]
		var door_at: Vector2i = place["door"]
		var entry: Dictionary = graph[map]
		var known_spawns: Array = entry["spawns"]
		if not known_spawns.has(spawn_id):  # what the map has already is left as it is
			actions.append({
				"kind": "spawn", "map": map, "node": "SpawnPoints/" + spawn_id, "spawn_id": spawn_id,
				"position": center_of(info, spawn_at), "facing": FACING[side_edge],
				"what": "added the spawn point %s (players from %s arrive there)" % [spawn_id, other_map.get_file()],
			})
			_note(graph, map, {}, spawn_id)
		if not MapGraph.has_door(graph, map, other_map):
			actions.append({
				"kind": "door", "map": map, "node": "Triggers/" + door_name, "name": door_name,
				"position": center_of(info, door_at), "target_map": other_map, "target_spawn": "from_" + own,
				"what": "added the door %s to %s (the map could not be reached)" % [door_name, other_map.get_file()],
			})
			_note(graph, map, {"node": "Triggers/" + door_name, "target": other_map, "spawn": "from_" + own})

# ---------------------------------------------------------------- side-view rooms (T14.06)
# A room's exit is mended the way a door is: nothing of the room is dug away. The new exit stands
# on the floor beside the wall of the matching edge (walking into it leaves the room), and the
# players of its partner arrive two and a half tiles further in.

static func _is_room(surveys: Dictionary, path: String) -> bool:
	return surveys.has(path) and JsonIo.to_bool(JsonIo.to_dict(surveys[path]).get("side", false))

## True when a body can stand in `cell`: solid below it and three free cells from it upwards.
static func _stands(info: Dictionary, cell: Vector2i) -> bool:
	var solid: Dictionary = info["solid"]
	if not solid.has(cell + Vector2i(0, 1)):
		return false
	for up in 3:
		if solid.has(cell - Vector2i(0, up)):
			return false
	return true

## A place for an exit on the side edge `edge` ("E" or "W") of a room: {position, area, spawn,
## facing} in map px, or {} when nobody can stand beside that wall. The lowest floor is taken,
## or the one nearest to the row `wanted_row` when one is given (-1: none).
static func room_exit_place(info: Dictionary, edge: String, wanted_row: int = -1) -> Dictionary:
	if edge != "E" and edge != "W":
		return {}
	var rect: Rect2i = info["rect"]
	var tile := JsonIo.to_float(info["tile"])
	var column := rect.end.x - 2 if edge == "E" else rect.position.x + 1
	var inward := -1 if edge == "E" else 1
	var best := -1
	for row in range(rect.position.y, rect.end.y):
		var feet := Vector2i(column, row)
		if not _stands(info, feet) or not _stands(info, feet + Vector2i(inward * 2, 0)):
			continue
		if best < 0 or (wanted_row >= 0 and absi(row - wanted_row) < absi(best - wanted_row)) or (wanted_row < 0 and row > best):
			best = row
	if best < 0:
		return {}
	var floor_y := (best + 1) * tile
	var wall_x := (column + (1 if edge == "E" else 0)) * tile  # the side of the cell toward the wall
	var area := Rect2(-tile if edge == "E" else 0.0, -3.0 * tile, tile, 3.0 * tile)
	return {
		"position": Vector2(wall_x, floor_y), "area": area,
		"spawn": Vector2((column + inward * 2 + 0.5) * tile, floor_y), "facing": "left" if edge == "E" else "right",
	}

static func _exit_action(map: String, exit_id: String, edge: String, place: Dictionary, target: String, target_exit: String, why: String) -> Dictionary:
	return {
		"kind": "exit", "map": map, "node": "Triggers/" + exit_id, "name": exit_id, "edge": edge,
		"position": place["position"], "area": place["area"], "target_map": target, "target_spawn": target_exit,
		"what": "added the exit %s to %s (%s)" % [exit_id, target.get_file(), why],
	}

static func _room_spawn_action(map: String, spawn_id: String, place: Dictionary, why: String) -> Dictionary:
	return {
		"kind": "spawn", "map": map, "node": "SpawnPoints/" + spawn_id, "spawn_id": spawn_id,
		"position": place["spawn"], "facing": place["facing"], "side_view": true,
		"what": "added the spawn point %s (%s)" % [spawn_id, why],
	}

static func _door_entry(graph: Dictionary, map: String, node: String) -> Dictionary:
	var entry: Dictionary = graph[map]
	var doors: Array = entry["doors"]
	for door: Dictionary in doors:
		if str(door["node"]) == node:
			return door
	return {}

## Repair 2 for rooms: the exit `found` leads to a room that has no arrival for it. The target room
## gets the spawn point on the edge facing the source, and an exit back when it has none.
static func _add_room_arrival(found: Dictionary, graph: Dictionary, surveys: Dictionary, actions: Array[Dictionary]) -> void:
	var source := str(found["map"])
	var target := str(found["target"])
	var spawn_id := str(found["spawn"])
	var door := _door_entry(graph, source, str(found["node"]))
	var source_edge := str(door.get("edge", "E"))
	var target_info: Dictionary = surveys[target]
	var place := room_exit_place(target_info, str(OPPOSITE.get(source_edge, "W")))
	if place.is_empty():
		actions.append({"kind": "unfixable", "map": target, "node": found["node"], "what": "%s has no floor beside its wall where the exit %s of %s arrives" % [target.get_file(), str(found["node"]).get_file(), source.get_file()]})
		return
	actions.append(_room_spawn_action(target, spawn_id, place, "the exit %s of %s arrives there" % [str(found["node"]).get_file(), source.get_file()]))
	_note(graph, target, {}, spawn_id)
	if MapGraph.has_door(graph, target, source):
		return
	var back_exit := str(door.get("id", ""))
	actions.append(_exit_action(target, spawn_id, str(OPPOSITE.get(source_edge, "W")), place, source, back_exit, "the way back"))
	_note(graph, target, {"node": "Triggers/" + spawn_id, "target": source, "spawn": back_exit, "exit": true, "edge": OPPOSITE.get(source_edge, "W"), "id": spawn_id})

## Repair 3 for rooms: an exit pair between an unreachable room and a reachable one beside it on
## the plan's grid, on the side edge they share.
static func _join_rooms(path: String, graph: Dictionary, surveys: Dictionary, plan: Dictionary, start: String, actions: Array[Dictionary]) -> void:
	var reachable := MapGraph.reachable(graph, start)
	var area := area_of_map(plan, path)
	var steps := {"E": Vector2i(1, 0), "W": Vector2i(-1, 0)}
	var tried: Array[String] = []
	if not area.is_empty():
		var here := _grid_cell(plan, JsonIo.to_str(area.get("id", "")))
		for edge: String in ["E", "W"]:
			var step: Vector2i = steps[edge]
			for other in _areas(plan):
				var partner := _area_path(other)
				if not reachable.has(partner) or _grid_cell(plan, JsonIo.to_str(other.get("id", ""))) != here + step:
					continue
				tried.append("%s of %s" % [edge, path.get_file()])
				var back: String = OPPOSITE[edge]
				var here_info: Dictionary = surveys[path]
				var there_info: Dictionary = surveys[partner]
				var place_here := room_exit_place(here_info, edge)
				var place_there := room_exit_place(there_info, back)
				if place_here.is_empty() or place_there.is_empty():
					continue
				var here_id := "%s_exit_%s" % [path.get_file().get_basename(), edge.to_lower()]
				var there_id := "%s_exit_%s" % [partner.get_file().get_basename(), back.to_lower()]
				var sides := [[path, here_id, edge, place_here, partner, there_id], [partner, there_id, back, place_there, path, here_id]]
				for side: Array in sides:
					var map: String = side[0]
					var own_id: String = side[1]
					var other_map: String = side[4]
					var entry: Dictionary = graph[map]
					var known: Array = entry["spawns"]
					var place: Dictionary = side[3]
					if not known.has(own_id):
						actions.append(_room_spawn_action(map, own_id, place, "players from %s arrive there" % other_map.get_file()))
						_note(graph, map, {}, own_id)
					if not MapGraph.has_door(graph, map, other_map):
						var other_id: String = side[5]
						var side_edge: String = side[2]
						actions.append(_exit_action(map, own_id, side_edge, place, other_map, other_id, "the room could not be reached"))
						_note(graph, map, {"node": "Triggers/" + own_id, "target": other_map, "spawn": other_id, "exit": true, "edge": side_edge, "id": own_id})
				return
	var why := "no reachable room lies beside it in the world plan" if tried.is_empty() else "nobody can stand beside the wall on both sides (tried %s)" % ", ".join(PackedStringArray(tried))
	actions.append({"kind": "unfixable", "map": path, "node": "", "what": "%s cannot be reached, and %s" % [path.get_file(), why]})

# ---------------------------------------------------------------- applying

## The node of `root` that new nodes of this kind go under: "SpawnPoints" / "Triggers" when the
## map has them, else the root.
static func _holder(root: Node, holder_name: String) -> Node:
	var found := root.get_node_or_null(holder_name)
	return found if found != null else root

## A node of a "spawn" or "door" action, not yet in the tree.
static func build(action: Dictionary) -> Node2D:
	var position: Vector2 = action["position"]
	if str(action["kind"]) == "spawn":
		var marker := Marker2D.new()
		marker.name = str(action["spawn_id"])
		marker.set_script(load(SPAWN_SCRIPT))
		marker.set("spawn_id", StringName(str(action["spawn_id"])))
		marker.set("facing", str(action.get("facing", "down")))
		if JsonIo.to_bool(action.get("side_view", false)):
			marker.set("side_view", true)
		marker.position = position
		return marker
	if str(action["kind"]) == "exit":  # the exit of a side-view room
		var room_exit := Area2D.new()
		room_exit.name = str(action["name"])
		room_exit.set_script(load(ROOM_EXIT_SCRIPT))
		room_exit.collision_layer = 0
		room_exit.collision_mask = 0
		room_exit.set_collision_layer_value(6, true)  # triggers
		room_exit.set_collision_mask_value(2, true)  # player
		room_exit.position = position
		room_exit.set("exit_id", str(action["name"]))
		room_exit.set("edge", str(action["edge"]))
		room_exit.set("target_room", str(action["target_map"]))
		room_exit.set("target_exit", str(action["target_spawn"]))
		var exit_shape := CollisionShape2D.new()
		exit_shape.name = "Shape"
		var exit_rect := RectangleShape2D.new()
		var area: Rect2 = action["area"]
		exit_rect.size = area.size
		exit_shape.shape = exit_rect
		exit_shape.position = area.get_center()
		room_exit.add_child(exit_shape)
		return room_exit
	var door := Area2D.new()
	door.name = str(action["name"])
	door.set_script(load(DOOR_SCRIPT))
	door.collision_layer = 0
	door.collision_mask = 0
	door.set_collision_layer_value(6, true)  # triggers
	door.set_collision_mask_value(2, true)  # player
	door.position = position
	door.set("target_map", str(action["target_map"]))
	door.set("target_spawn", StringName(str(action["target_spawn"])))
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var rect := RectangleShape2D.new()
	var tile := JsonIo.to_float(action.get("tile", 16))
	rect.size = Vector2(tile, tile)
	shape.shape = rect
	door.add_child(shape)
	return door

## Does one action in `root` (the scene of action.map). Returns the nodes it added (a "retarget"
## adds none): the dock records them for undo, the tool saves the scene.
static func apply(action: Dictionary, root: Node) -> Array[Node]:
	var added: Array[Node] = []
	match str(action["kind"]):
		"retarget":
			var door := root.get_node_or_null(str(action["node"]))
			if door != null and MapGraph._is(door, MapGraph.ROOM_EXIT_SUFFIX):
				door.set("target_room", str(action["target_map"]))
				door.set("target_exit", str(action["target_spawn"]))
			elif door != null:
				door.set("target_map", str(action["target_map"]))
				door.set("target_spawn", StringName(str(action["target_spawn"])))
		"spawn", "door", "exit":
			var holder := _holder(root, "SpawnPoints" if str(action["kind"]) == "spawn" else "Triggers")
			var node := build(action)
			holder.add_child(node)
			node.owner = root
			for child in node.get_children():
				child.owner = root
			added.append(node)
	return added

## The line of an action for the report and the result file: {kind, map, node, what}.
static func line(action: Dictionary) -> Dictionary:
	return {"kind": str(action["kind"]), "map": str(action["map"]).trim_prefix("res://"), "node": str(action.get("node", "")), "what": str(action["what"])}
