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

## `sfx_step_<surface>` when the bank has that slot and the ground under the player is of that
## surface; else `sfx_step`. The surface of a tile is its `footstep` custom data (a Tiled map can
## set it), else the surface of its asset (the tag `surface:<name>`, through the bank's table).
func _surface_slot(audio: Node) -> StringName:
	var router := RpgUtil.router()
	var map: Node = router.get("current_map") if router != null else null
	if map == null or not audio.get("bank") is RpgSoundBank:
		return RpgSoundBank.STEP_SLOT
	var bank: RpgSoundBank = audio.get("bank")
	if not bank.has_step_surfaces():
		return RpgSoundBank.STEP_SLOT
	var layers: Array[TileMapLayer] = []
	for layer in map.find_children("*", "TileMapLayer", true, false):
		layers.append(layer as TileMapLayer)
	return bank.step_slot(surface_at(layers, actor.global_position, bank))

## The surface of the ground at `at` (global): the topmost layer that has a tile with a surface.
static func surface_at(layers: Array[TileMapLayer], at: Vector2, bank: RpgSoundBank) -> String:
	for i in range(layers.size() - 1, -1, -1):
		var tile_layer := layers[i]
		if tile_layer == null or tile_layer.tile_set == null:
			continue
		var local := tile_layer.to_local(at) if tile_layer.is_inside_tree() else at - tile_layer.position
		var data := tile_layer.get_cell_tile_data(tile_layer.local_to_map(local))
		if data == null:
			continue
		var surface := ""
		if tile_layer.tile_set.get_custom_data_layer_by_name("footstep") != -1:
			surface = str(data.get_custom_data("footstep"))
		if surface == "" and tile_layer.tile_set.get_custom_data_layer_by_name("asset_id") != -1:
			surface = bank.surface_of(str(data.get_custom_data("asset_id")))
		if surface != "":
			return surface
	return ""

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
	# A cutscene walks characters itself and holds everyone else (RpgSequenceRunner).
	var wanted := Vector2.ZERO if RpgSequenceRunner.running() else desired
	actor.velocity = wanted * walk_speed() + external_velocity
	actor.move_and_slide()
	_footsteps(_delta)
	external_velocity *= 0.85
	if external_velocity.length() < 0.5:
		external_velocity = Vector2.ZERO
