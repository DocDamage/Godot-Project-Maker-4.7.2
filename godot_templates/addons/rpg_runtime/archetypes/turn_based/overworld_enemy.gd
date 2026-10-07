class_name RpgOverworldEnemy
extends RpgActor
## An enemy standing on the map. Touching it (or interacting with it, when `encounter_on_interact`
## is set) starts a battle through SceneRouter.combat. It wanders around its home point meanwhile.
## Layers: enemies (3); the Contact area is on triggers (6) and looks for the player (2).
## An RpgPersistent child removes the node on map load once its `defeated` flag is set.

@export var entity_id: String = ""
## Who fights: `group`, or just `definition` when the group is empty.
@export var group: Array[RpgEnemyDefinition] = []
@export var encounter_on_interact: bool = false
@export var can_escape: bool = true
@export var wander_enabled: bool = true
@export var wander_radius_tiles: float = 2.0
@export var tile_size: float = 16.0
@export var wander_speed: float = 24.0

var _home := Vector2.ZERO
var _target := Vector2.ZERO
var _moving := false
var _timer := 0.0
var _grace := 0.0
var _rng := RpgRng.new()
var _contact: Area2D = null

func _ready() -> void:
	super._ready()
	_home = global_position
	_rng.seed_value(hash(entity_id if entity_id != "" else String(name)))
	_timer = _rng.randf_range(2.0, 4.0)
	_contact = get_node_or_null("Contact") as Area2D
	var movement := component("Movement") as RpgMovement
	if movement != null:
		movement.speed = wander_speed
	if encounter_on_interact:
		set_collision_layer_value(5, true)  # interactables: found by the player's interaction area

func is_in_grace() -> bool:
	return _grace > 0.0

## No contact encounters for `seconds` (after the player escaped).
func grant_grace(seconds: float) -> void:
	_grace = maxf(_grace, seconds)

func interact(_actor: Node = null) -> void:
	if encounter_on_interact:
		_try_encounter()

func _physics_process(delta: float) -> void:
	super._physics_process(delta)
	if _grace > 0.0:
		_grace = maxf(0.0, _grace - delta)
	_wander(delta)
	if not encounter_on_interact and _grace <= 0.0 and _contact != null and _contact.has_overlapping_bodies():
		_try_encounter()

func _wander(delta: float) -> void:
	if not wander_enabled or not input_enabled:
		move_dir(Vector2.ZERO)
		return
	if _moving:
		var to_target := _target - global_position
		_timer -= delta
		if to_target.length() < 1.5 or _timer <= 0.0:  # arrived, or the path is blocked
			_moving = false
			_timer = _rng.randf_range(2.0, 4.0)
			move_dir(Vector2.ZERO)
		else:
			move_dir(to_target.normalized())
		return
	move_dir(Vector2.ZERO)
	_timer -= delta
	if _timer <= 0.0:
		var r := wander_radius_tiles * tile_size
		_target = _home + Vector2(_rng.randf_range(-r, r), _rng.randf_range(-r, r))
		_moving = true
		_timer = 3.0

func _group_definitions() -> Array[RpgEnemyDefinition]:
	if not group.is_empty():
		return group
	var out: Array[RpgEnemyDefinition] = []
	var def := definition as RpgEnemyDefinition
	if def != null:
		out.append(def)
	return out

## The encounter this enemy starts (the combat mode fills in the way back).
func build_encounter() -> RpgEncounterData:
	var data := RpgEncounterData.new()
	data.entity_id = entity_id
	data.enemies.assign(_group_definitions())
	data.can_escape = can_escape
	return data

func _try_encounter() -> void:
	var router := RpgUtil.router()
	if router == null or router.get("combat") == null:
		return
	var combat: Variant = router.get("combat")
	if combat.is_in_combat() or router.is_busy():
		return  # tried again on the next physics frame
	if _group_definitions().is_empty():
		push_error("[RPG-COMBAT] enemy %s has no definition" % entity_id)
		return
	combat.start_encounter(build_encounter())
