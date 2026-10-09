class_name RpgGuardian
extends RpgSideEnemy
## The guardian of a metroidvania: the one large enemy that stands between the player and the
## first ability. While it lives the exits of its room are shut (the gates beside them open on the
## flag `<entity_id>.defeated`); defeating it opens them and grants `grants`.
##
## It fights in three phases, by how much health it has left:
##   1 (above two thirds)  walks toward the player and lunges
##   2 (above one third)   also jumps: landing shakes the room and a rock falls from the ceiling
##   3 (the rest)          the same, faster
## Every attack is telegraphed: it stops for TELEGRAPH_S and its sprite is tinted.

signal phase_changed(phase: int)
signal attacked(kind: StringName)

const TELEGRAPH_S := 0.4
const LUNGE_S := 0.35
const LUNGE_SPEED_MUL := 2.5
const WALK_S := 1.2
const RECOVER_S := 0.5
const PHASE_3_SPEED := 1.5
const TELEGRAPH_TINT := Color(1.0, 0.55, 0.35)

const WALK := &"walk"
const TELEGRAPH := &"telegraph"
const LUNGE := &"lunge"
const SLAM := &"slam"
const RECOVER := &"recover"

## The ability its defeat grants ("" for none).
@export var grants: StringName = &""

var phase := 1
var mode: StringName = WALK
## The attack the telegraph announces.
var next_attack: StringName = LUNGE
## The rock that fell last (tests look at it).
var last_rock: RpgProjectile = null
var _mode_time := 0.0
var _attacks := 0
var _slamming := false

func _ready() -> void:
	super._ready()
	landed.connect(_on_landed)
	if health != null:
		health.changed.connect(_on_health_changed)

## 1, 2 or 3 from the health that is left.
static func phase_for(hp: int, max_hp: int) -> int:
	if max_hp <= 0 or hp * 3 > max_hp * 2:
		return 1
	return 2 if hp * 3 > max_hp else 3

func _on_health_changed(hp: int, max_hp: int) -> void:
	var now := phase_for(hp, max_hp)
	if now != phase:
		phase = now
		phase_changed.emit(phase)

func speed_factor() -> float:
	return PHASE_3_SPEED if phase >= 3 else 1.0

func _go(to: StringName) -> void:
	mode = to
	_mode_time = 0.0

func think(delta: float) -> void:
	_mode_time += delta * speed_factor()
	var player := find_player()
	var toward := 0.0
	if player != null:
		var dx := player.global_position.x - global_position.x
		toward = signf(dx) if absf(dx) > tile_size * 0.5 else 0.0
	match mode:
		WALK:
			speed_scale = 0.5 * speed_factor()
			move_x = toward
			if _mode_time >= WALK_S and player != null and is_on_floor():
				# from the second phase on every other attack is the slam
				next_attack = SLAM if phase >= 2 and _attacks % 2 == 1 else LUNGE
				facing_locked = true
				move_x = 0.0  # it stops in the same step
				_go(TELEGRAPH)
				flash(TELEGRAPH_TINT, TELEGRAPH_S / speed_factor())
		TELEGRAPH:
			move_x = 0.0
			if _mode_time >= TELEGRAPH_S:
				_attacks += 1
				attacked.emit(next_attack)
				if next_attack == SLAM:
					_slamming = true
					press_jump()
					_go(SLAM)
				else:
					_go(LUNGE)
		LUNGE:
			speed_scale = LUNGE_SPEED_MUL
			move_x = float(facing)
			if _mode_time >= LUNGE_S or is_on_wall():
				_go(RECOVER)
		SLAM:
			speed_scale = 0.5
			move_x = toward
			if _mode_time >= 2.0:  # it never left the ground: go on
				_slamming = false
				_go(RECOVER)
		RECOVER:
			move_x = 0.0
			if _mode_time >= RECOVER_S:
				facing_locked = false
				_go(WALK)

## The slam's landing: the room shakes and a rock falls from the ceiling above the player.
func _on_landed(_speed: float) -> void:
	if not _slamming or dead:
		return
	_slamming = false
	_go(RECOVER)
	var room := _map_root()
	var camera := room.get_node_or_null("Camera") as Camera2D if room != null else null
	RpgScreenFeedback.shake(camera, 4.0, 0.2)
	drop_rock()

## A rock from the top of the room, straight down onto where the player stands now.
func drop_rock() -> RpgProjectile:
	var player := find_player()
	var parent := get_parent()
	if player == null or not (parent is Node2D):
		return null
	var holder := parent as Node2D
	var top := global_position.y - tile_size * 12.0
	var room := _map_root()
	if room != null and room.has_method(&"bounds"):
		var bounds: Rect2 = room.call(&"bounds")
		top = bounds.position.y + tile_size * 2.5
	var from := Vector2(player.global_position.x, top) - holder.global_position
	var rock := RpgProjectile.create(self, from, Vector2.DOWN, &"enemy", px(150.0), tile_size * 24.0)
	last_rock = rock
	holder.add_child(rock)
	return rock

## Defeated: the ability is the player's (the gates open by the flag the base enemy has set).
func on_defeated() -> void:
	var state := RpgUtil.state()
	if state != null and grants != &"" and state.grant(grants):
		RpgUtil.notify(RpgAbilities.toast(grants))
		play_sound(&"sfx_ability")
