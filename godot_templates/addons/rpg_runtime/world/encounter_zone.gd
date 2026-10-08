class_name RpgEncounterZone
extends Area2D
## Where random battles happen while the player walks (turn-based games; the action RPG has no
## random encounters). The zone is the shape of its CollisionPolygon2D / CollisionShape2D children,
## or the painted cells of a TileMapLayer: `cells_layer`, else a layer named "Encounters" in the
## map when the zone has no shape of its own. The turn-based mode counts the tiles the player
## walks inside it (RpgEncounterSteps) and draws from GameState's seeded RNG at every step.
## The zone takes part in no physics: it only holds the shape for the editor.

const CELLS_LAYER_NAME := "Encounters"

@export var table: RpgEncounterTable
## The average number of steps (tiles walked) between two battles.
@export var steps_per_encounter: float = 24.0
## A flag "<entity>.<key>": while it is true the zone brings no battles (e.g. "bridge.repaired").
@export var disabled_flag: String = ""
## A TileMapLayer whose painted cells are the zone (the layer is hidden in the game).
@export var cells_layer: NodePath

func _ready() -> void:
	add_to_group("rpg_encounter_zones")
	monitoring = false
	monitorable = false
	collision_layer = 0
	collision_mask = 0
	var layer := cells()
	if layer != null:
		layer.visible = false

## True when the zone can bring a battle now: it has a table and its flag is not set.
func is_enabled() -> bool:
	if table == null or steps_per_encounter <= 0.0:
		return false
	if disabled_flag == "":
		return true
	var dot := disabled_flag.rfind(".")
	var state := RpgUtil.state()
	if dot <= 0 or state == null:
		return true
	return not RpgUtil.to_bool(state.get_flag(disabled_flag.substr(0, dot), disabled_flag.substr(dot + 1), false))

## The TileMapLayer of painted cells, or null when the zone is a shape.
func cells() -> TileMapLayer:
	if not cells_layer.is_empty():
		return get_node_or_null(cells_layer) as TileMapLayer
	if _has_shape():
		return null
	var top: Node = self
	while top.get_parent() != null:
		top = top.get_parent()
	return top.find_child(CELLS_LAYER_NAME, true, false) as TileMapLayer

func _has_shape() -> bool:
	for child in get_children():
		if child is CollisionPolygon2D or child is CollisionShape2D:
			return true
	return false

## True when the world point is inside the zone.
func contains(world: Vector2) -> bool:
	var layer := cells()
	if layer != null:
		return layer.get_cell_source_id(layer.local_to_map(to_local_of(layer, world))) != -1
	for child in get_children():
		if child is CollisionPolygon2D:
			var poly := child as CollisionPolygon2D
			if poly.polygon.size() >= 3 and Geometry2D.is_point_in_polygon(to_local_of(poly, world), poly.polygon):
				return true
		elif child is CollisionShape2D:
			var holder := child as CollisionShape2D
			var local := to_local_of(holder, world)
			if holder.shape is RectangleShape2D:
				var size := (holder.shape as RectangleShape2D).size
				if Rect2(-size / 2.0, size).has_point(local):
					return true
			elif holder.shape is CircleShape2D:
				if local.length() <= (holder.shape as CircleShape2D).radius:
					return true
	return false

## `node.to_local(world)`, also for a node outside the tree (the transforms of its 2D ancestors).
static func to_local_of(node: Node2D, world: Vector2) -> Vector2:
	if node.is_inside_tree():
		return node.to_local(world)
	var xf := Transform2D.IDENTITY
	var at: Node = node
	while at is Node2D:
		xf = (at as Node2D).transform * xf
		at = at.get_parent()
	return xf.affine_inverse() * world

## One step inside the zone: true when it brings a battle. Draws one number from `rng`.
func roll(rng: RpgRng) -> bool:
	return rng.randf() * steps_per_encounter < 1.0

## The first enabled zone of `map` that contains the point, or null.
static func zone_at(map: Node, world: Vector2) -> RpgEncounterZone:
	if map == null:
		return null
	for node in map.find_children("*", "Area2D", true, false):
		var zone := node as RpgEncounterZone
		if zone != null and not zone.is_queued_for_deletion() and zone.is_enabled() and zone.contains(world):
			return zone
	return null
