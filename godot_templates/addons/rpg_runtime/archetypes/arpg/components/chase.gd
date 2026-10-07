class_name RpgChase
extends Node
## Enemy component: moves toward the player. nav_mode "direct" uses the direction vector (the
## Movement component slides along walls); "agent" follows the NavigationAgent2D path and falls back
## to the direct way when there is none.

var speed := 60.0
var lose_px := 160.0
var lose_time_s := 2.0
var attack_range_px := 18.0
var nav_mode := "direct"

var actor: RpgActor
var detection: RpgDetection
var agent: NavigationAgent2D
var _lost := 0.0

func _ready() -> void:
	var node := get_parent()
	while node != null and not (node is RpgActor):
		node = node.get_parent()
	actor = node as RpgActor
	if actor != null:
		detection = actor.component("Detection") as RpgDetection
		agent = actor.get_node_or_null("Navigation") as NavigationAgent2D

func reset() -> void:
	_lost = 0.0

## True after the player was farther than `lose_px` for `lose_time_s` seconds in a row.
func gave_up() -> bool:
	return _lost >= lose_time_s

func distance() -> float:
	return detection.distance_to_player() if detection != null else INF

func in_attack_range() -> bool:
	return distance() <= attack_range_px

## The direction the next step goes in.
func direction() -> Vector2:
	var to_player := detection.player_position() - detection.actor_position()
	if nav_mode == "agent" and agent != null and agent.process_mode != Node.PROCESS_MODE_DISABLED:
		agent.target_position = detection.player_position()
		if not agent.is_navigation_finished():
			var next := agent.get_next_path_position() - detection.actor_position()
			if next.length() > 0.5:
				return next.normalized()
	return to_player.normalized()

func step(delta: float) -> void:
	if actor == null or detection == null:
		return
	var d := distance()
	_lost = _lost + delta if d > lose_px else 0.0
	var movement := actor.component("Movement") as RpgMovement
	if movement != null:
		movement.speed = speed
	var to_player := detection.player_position() - detection.actor_position()
	if d <= attack_range_px * 0.5:
		actor.move_dir(Vector2.ZERO)  # close enough: stand and face the player
		actor.set_facing(RpgAnimationDriver.dir_to_facing(to_player))
		return
	actor.move_dir(direction())
