class_name RpgFollowers
extends Node
## Shows the party members (GameState.party) walking behind the player on the map, in joining order,
## along the path the player walked. Created by boot under SceneRouter as "Followers". A follower is
## only a picture: it has no body, so it never blocks anyone, and nothing about it is saved (the
## party is). It walks when the player walks, scripted moves of a sequence included.

const NODE_NAME := "Followers"
## The distance between two members on the path, in tiles.
const SPACING_TILES := 1.0
## A new point of the trail every time the player has moved this far (px).
const MIN_STEP_PX := 1.0
## The followers keep walking this many frames after the player's last move (a slow walk does not
## move a whole pixel every frame).
const WALK_HOLD_FRAMES := 6

## False hides the followers (boot's `followers` export).
var enabled := true
var _trail: Array[Vector2] = []  # the player's path, newest first
var _nodes: Array[Node2D] = []
var _shown_ids: Array[StringName] = []
var _map: Node = null
var _spacing := 16.0
var _still_frames := WALK_HOLD_FRAMES

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_PAUSABLE

func _physics_process(_delta: float) -> void:
	update()

## The followers now: [{actor_id, node}] (tests).
func shown() -> Array[Node2D]:
	return _nodes

## Puts the followers where they belong this frame: built again after a map change or a change of
## the party, then placed along the trail.
func update() -> void:
	var router := RpgUtil.router()
	var state := RpgUtil.state()
	var map: Node = router.current_map if router != null else null
	var player: Node2D = router.current_map.get_player() if router != null and router.current_map != null and router.current_map.is_inside_tree() else null
	var wanted: Array[StringName] = []
	if enabled and state != null and player != null:
		for member in state.party:
			var member_id: StringName = member["actor_id"]
			wanted.append(member_id)
	if map != _map or wanted != _shown_ids or (not _nodes.is_empty() and not is_instance_valid(_nodes[0])):
		_rebuild(map, player, wanted)
	if player == null or _nodes.is_empty():
		return
	var at := RpgUtil.world_position(player)
	if record(_trail, at, MIN_STEP_PX, trail_points_needed(_nodes.size(), _spacing)):
		_still_frames = 0
	else:
		_still_frames += 1
	for i in _nodes.size():
		place(_nodes[i], _trail, (i + 1) * _spacing, _still_frames < WALK_HOLD_FRAMES)

func _rebuild(map: Node, player: Node2D, wanted: Array[StringName]) -> void:
	for node in _nodes:
		if is_instance_valid(node):
			node.queue_free()
	_nodes.clear()
	_trail.clear()
	_map = map
	_shown_ids = wanted.duplicate()
	if player == null or wanted.is_empty() or player.get_parent() == null:
		return
	_spacing = SPACING_TILES * float(RpgUtil.map_tile_px(map))
	var state := RpgUtil.state()
	for member_id in wanted:
		var node := make_follower(state.actor_definition(member_id) if state != null else null, player)
		node.name = "Follower_%s" % member_id
		node.set_meta("facing", str(player.get("facing")) if "facing" in player else "down")
		player.get_parent().add_child(node)
		node.global_position = player.global_position
		_nodes.append(node)
	_trail.append(RpgUtil.world_position(player))

## A follower node: an AnimatedSprite2D "Visual" with the member's frames (the player's when the
## definition has none), drawn like the player's.
static func make_follower(def: RpgActorDefinition, player: Node2D) -> Node2D:
	var node := Node2D.new()
	node.set_meta("facing", "down")
	var visual := AnimatedSprite2D.new()
	visual.name = "Visual"
	var player_visual := player.get_node_or_null("Visual") as AnimatedSprite2D
	var frames: SpriteFrames = def.sprite_frames if def != null and def.sprite_frames != null else null
	if frames == null and player_visual != null:
		frames = player_visual.sprite_frames
	visual.sprite_frames = frames
	if player_visual != null and (frames == player_visual.sprite_frames or def == null):
		visual.centered = player_visual.centered
		visual.offset = player_visual.offset
	elif frames != null:
		var size := Vector2(16, 16)
		for anim in frames.get_animation_names():  # a new SpriteFrames has an empty "default"
			if frames.get_frame_count(anim) > 0 and frames.get_frame_texture(anim, 0) != null:
				size = frames.get_frame_texture(anim, 0).get_size()
				break
		visual.centered = false
		visual.offset = Vector2(-size.x / 2.0, -size.y + 1.0)
	node.add_child(visual)
	return node

## Adds `at` to the front of the trail when the player has moved at least `min_step`; keeps at most
## `max_points`. True when it moved.
static func record(trail: Array[Vector2], at: Vector2, min_step: float, max_points: int) -> bool:
	if not trail.is_empty() and trail[0].distance_to(at) < min_step:
		return false
	trail.push_front(at)
	while trail.size() > max_points:
		trail.pop_back()
	return true

## Enough points for `members` followers `spacing` apart (each point is at least 1 px from the last).
static func trail_points_needed(members: int, spacing: float) -> int:
	return ceili((members + 1) * spacing / MIN_STEP_PX) + 2

## The point `distance` px back along the trail (the oldest point when the trail is shorter).
static func point_along(trail: Array[Vector2], distance: float) -> Vector2:
	if trail.is_empty():
		return Vector2.ZERO
	var left := distance
	for i in range(1, trail.size()):
		var seg := trail[i - 1].distance_to(trail[i])
		if seg >= left and seg > 0.0:
			return trail[i - 1].lerp(trail[i], left / seg)
		left -= seg
	return trail[trail.size() - 1]

## Puts a follower `distance` px back on the trail, facing the way the path goes, walking while the
## player moves.
static func place(node: Node2D, trail: Array[Vector2], distance: float, moving: bool) -> void:
	var at := point_along(trail, distance)
	var ahead := point_along(trail, maxf(0.0, distance - 4.0))
	if node.is_inside_tree():
		node.global_position = at
	else:
		node.position = at
	var facing := str(node.get_meta("facing", "down"))
	if ahead.distance_to(at) > 0.5:
		facing = RpgAnimationDriver.dir_to_facing(ahead - at)
		node.set_meta("facing", facing)
	var driver := RpgAnimationDriver.new()
	driver.sprite = node.get_node_or_null("Visual") as AnimatedSprite2D
	driver.play("walk" if moving else "idle", facing)
