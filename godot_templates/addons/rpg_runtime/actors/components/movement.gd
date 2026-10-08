class_name RpgMovement
extends Node
## Moves the owning RpgActor from `desired` (a direction) plus a decaying knockback velocity.

@export var speed: float = 80.0
## Distance the player walks between two footstep sounds (one tile by default).
@export var step_interval_px: float = 16.0
@export var step_volume_db: float = -6.0
var desired := Vector2.ZERO
var external_velocity := Vector2.ZERO  # knockback (ARPG); decays: *= 0.85 per physics frame

var actor: RpgActor

var _step_distance := 0.0
var _step_rng := RandomNumberGenerator.new()  # sound only: never the game's seeded RNG

func _ready() -> void:
	actor = _find_actor()
	if actor == null:
		push_error("[RPG-ACTOR] Movement has no RpgActor ancestor")

func _find_actor() -> RpgActor:
	var node := get_parent()
	while node != null:
		if node is RpgActor:
			return node
		node = node.get_parent()
	return null

## One step sound per `step_interval_px` walked (the player only, and only on purpose: not while
## being knocked back). Pitch varies by about 5% so that it does not machine-gun.
func _footsteps(delta: float) -> void:
	if not actor.is_in_group("player") or desired == Vector2.ZERO:
		_step_distance = 0.0
		return
	_step_distance += actor.get_real_velocity().length() * delta
	if _step_distance < step_interval_px:
		return
	_step_distance = fmod(_step_distance, step_interval_px)
	var router := RpgUtil.router()
	var audio: Node = router.audio if router != null else null
	if audio == null or not audio.has_method("play"):
		return
	var slot := _surface_slot(audio)
	audio.call("play", slot, step_volume_db, _step_rng.randf_range(0.95, 1.05))

## `sfx_step_<surface>` when the tile under the player has `footstep` custom data and the sound
## bank has that slot; else `sfx_step`.
func _surface_slot(audio: Node) -> StringName:
	var router := RpgUtil.router()
	var map: Node = router.get("current_map") if router != null else null
	if map == null or not audio.get("bank") is RpgSoundBank:
		return &"sfx_step"
	var bank: RpgSoundBank = audio.get("bank")
	var has_surfaces := false
	for slot_name in bank.slots():
		if str(slot_name).begins_with("sfx_step_"):
			has_surfaces = true
			break
	if not has_surfaces:
		return &"sfx_step"
	for layer in map.find_children("*", "TileMapLayer", true, false):
		var tile_layer := layer as TileMapLayer
		if tile_layer.tile_set == null or tile_layer.tile_set.get_custom_data_layer_by_name("footstep") == -1:
			continue
		var cell := tile_layer.local_to_map(tile_layer.to_local(actor.global_position))
		var data := tile_layer.get_cell_tile_data(cell)
		if data == null:
			continue
		var surface := str(data.get_custom_data("footstep"))
		if surface != "" and bank.has_slot(StringName("sfx_step_" + surface)):
			return StringName("sfx_step_" + surface)
	return &"sfx_step"

## `speed` scaled by what the player wears (a move_speed modifier of equipment); everyone else
## walks at `speed`.
func walk_speed() -> float:
	if actor != null and actor.is_in_group("player"):
		var state := RpgUtil.state()
		if state != null:
			return speed * state.move_speed_factor(state.player_stats)
	return speed

func _physics_process(_delta: float) -> void:
	if actor == null:
		return
	actor.velocity = desired * walk_speed() + external_velocity
	actor.move_and_slide()
	_footsteps(_delta)
	external_velocity *= 0.85
	if external_velocity.length() < 0.5:
		external_velocity = Vector2.ZERO
