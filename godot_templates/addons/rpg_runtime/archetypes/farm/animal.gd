class_name RpgFarmAnimal
extends RpgActor
## An animal of a farm on the map that is shown (T17.07). What it is, what it is called, how
## well it likes the farmer and whether it was fed and petted today is not here: that is a row
## of the herd (RpgAnimalHouse, in the flags of the game state), and this node only shows the
## animal `animal_id` where the data says it is. RpgAnimalHouse makes it when a map is entered,
## from the scene of the animal's picture (`generated/scenes/farm/animals/`), and takes it away
## again. Layer: interactables (5), so `interact` finds it and the farmer walks through it; its
## mask is the world (1), so a fence holds it.
##
## * In its yard it **wanders** (`roam`): it stands, walks to a place of the yard, stands again.
##   The places are chosen with random numbers of its own, never the game's: where a hen
##   scratches changes nothing that is saved.
## * In its house at night it **sleeps** (`sleep`): the `sleep` animation when its sheet has
##   one, else it stands still.
## * `interact` pets it, and takes its product when it is one that is taken from the animal
##   (RpgAnimalHouse.touch).

## How long it stands between two walks, and how long it tries to reach a place.
const REST_S := Vector2(1.5, 4.5)
const WALK_S := 6.0
const NEAR := 2.0

## The kind of animal the scene shows (`hen`); the herd says which animal it is.
@export var kind: String = ""

var animal_id := 0
## The animal houses of the game (who made this node); found when it is needed.
var herd: RpgAnimalHouse = null
var asleep := false

var _roams := false
var _ground := Rect2()
var _goal := Vector2.ZERO
var _walking := false
var _timer := 0.0
var _rng := RandomNumberGenerator.new()

func _ready() -> void:
	super._ready()
	_rng.randomize()
	_timer = _rng.randf_range(0.0, REST_S.y)
	if asleep:
		_show_sleep()

func the_herd() -> RpgAnimalHouse:
	if herd == null or not is_instance_valid(herd):
		herd = RpgAnimalHouse.current()
	return herd

## `interact` (RpgInteraction calls this): the animal is petted and gives what it has.
func interact(_actor: Node = null) -> void:
	var found := the_herd()
	if found != null:
		found.touch(animal_id)

# ------------------------------------------------------------------ asleep

## True when the sheet has an animation to sleep in.
func has_sleep() -> bool:
	var sprite := get_node_or_null("Visual") as AnimatedSprite2D
	if sprite == null or sprite.sprite_frames == null:
		return false
	for anim in sprite.sprite_frames.get_animation_names():
		if String(anim).begins_with("sleep"):
			return true
	return false

## The animal sleeps where it stands until the node is made anew.
func sleep() -> void:
	asleep = true
	_roams = false
	_walking = false
	move_dir(Vector2.ZERO)
	if _driver.sprite != null:  # `_ready` has run; before it, `_ready` shows the sleep
		_show_sleep()

func _show_sleep() -> void:
	if not has_sleep():
		return
	animation_locked = true
	_driver.play("sleep", facing)

# ------------------------------------------------------------------ wandering

## The animal wanders over `ground` (a rectangle of the world) from now on.
func roam(ground: Rect2) -> void:
	_ground = ground
	_roams = not asleep and ground.size.x > 0.0 and ground.size.y > 0.0

func is_roaming() -> bool:
	return _roams

## The rectangle it wanders over.
func roaming_ground() -> Rect2:
	return _ground

func _physics_process(delta: float) -> void:
	super._physics_process(delta)
	if not _roams or asleep:
		return
	wander(delta)

## One step of the wandering: `delta` seconds of standing or of walking to the place chosen.
func wander(delta: float) -> void:
	var here := RpgUtil.world_position(self)
	_timer -= delta
	if _walking:
		var to := _goal - here
		if to.length() <= NEAR or _timer <= 0.0:
			_walking = false
			_timer = _rng.randf_range(REST_S.x, REST_S.y)
			move_dir(Vector2.ZERO)
		else:
			move_dir(to.normalized())
	elif _timer <= 0.0:
		_goal = _ground.position + Vector2(_rng.randf(), _rng.randf()) * _ground.size
		_walking = true
		_timer = WALK_S
	# never out of the yard, whatever pushed it (the gate of a yard is open)
	var kept := here.clamp(_ground.position, _ground.end)
	if kept != here:
		if is_inside_tree():
			global_position = kept
		else:
			position += kept - here
