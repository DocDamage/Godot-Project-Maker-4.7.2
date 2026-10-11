class_name RpgArcadeBoss
extends Node2D
## The boss of a stage: health, phases that change at a fraction of it, a warning before every
## attack, an intro (the stage stops scrolling and shows the name) and a defeat with explosions.
## The kinds extend it and say what a movement pattern and an attack are (_move, _perform); the
## base knows "still" and "sweep".

signal intro_started(boss_name: String)
signal intro_finished
signal health_changed(health: int, max_health: int)
signal phase_changed(index: int)
signal telegraphed(attack: String)
signal attacked(attack: String)
signal defeated
signal exploded(at: Vector2)
## The defeat has played out: the stage may end.
signal finished

enum State { WAITING, INTRO, FIGHT, DYING, DONE }

@export var boss_name: String = ""
@export var max_health: int = 100
@export var points: int = 5000
@export var intro_s: float = 1.5
@export var defeat_s: float = 1.5
@export var explosions: int = 6
## How far a "sweep" goes to each side, in px.
@export var sweep_px: float = 60.0

var health := 100
var phases: Array[RpgArcadeBossPhase] = [RpgArcadeBossPhase.new()]
var state: int = State.WAITING
## False for a test that steps the boss by hand.
var auto_advance := true

var _phase := 0
var _clock := 0.0
var _fight_s := 0.0
var _since_attack := 0.0
var _attack_index := 0
var _warned := false
var _home := Vector2.ZERO
var _bursts := 0

func _process(delta: float) -> void:
	if auto_advance:
		advance(delta)

## Reads what a stage file says about its boss: name, health, points and phases.
func setup(data: Dictionary) -> void:
	boss_name = RpgUtil.to_str(data.get("name", boss_name))
	max_health = maxi(1, RpgUtil.to_int(data.get("health", max_health), max_health))
	points = RpgUtil.to_int(data.get("points", points), points)
	phases = RpgArcadeBossPhase.list_from(RpgUtil.to_array(data.get("phases", [])))

## The boss comes in: the intro runs, then the fight.
func begin() -> void:
	if state != State.WAITING:
		return
	health = max_health
	_home = position
	_phase = 0
	_clock = 0.0
	state = State.INTRO
	intro_started.emit(boss_name)
	health_changed.emit(health, max_health)

func fraction() -> float:
	return clampf(float(health) / maxf(1.0, max_health), 0.0, 1.0)

func phase_index() -> int:
	return _phase

func phase() -> RpgArcadeBossPhase:
	return phases[clampi(_phase, 0, phases.size() - 1)]

func is_fighting() -> bool:
	return state == State.FIGHT

## The boss is hit for `amount`. Only during the fight: the intro and the defeat cannot be hurt.
## Returns what was dealt.
func take(amount: int) -> int:
	if state != State.FIGHT or amount <= 0:
		return 0
	var dealt := mini(amount, health)
	health -= dealt
	health_changed.emit(health, max_health)
	if health <= 0:
		state = State.DYING
		_clock = 0.0
		_bursts = 0
		defeated.emit()
		return dealt
	var now := RpgArcadeBossPhase.index_at(phases, fraction())
	if now != _phase:
		_phase = now
		_since_attack = 0.0
		_attack_index = 0
		_warned = false
		phase_changed.emit(_phase)
	return dealt

## One step of the intro, the fight or the defeat.
func advance(delta: float) -> void:
	match state:
		State.INTRO:
			_clock += delta
			if _clock >= intro_s:
				state = State.FIGHT
				_fight_s = 0.0
				_since_attack = 0.0
				intro_finished.emit()
		State.FIGHT:
			_fight_s += delta
			_move(phase().movement, delta, _fight_s)
			_step_attack(delta)
		State.DYING:
			_clock += delta
			var due := explosions if defeat_s <= 0.0 else mini(explosions, floori(_clock / defeat_s * explosions) + 1)
			while _bursts < due:
				exploded.emit(global_position + burst_offset(_bursts))
				_bursts += 1
			if _clock >= defeat_s:
				state = State.DONE
				finished.emit()

func _step_attack(delta: float) -> void:
	var now := phase()
	if now.attacks.is_empty():
		return
	_since_attack += delta
	var attack := now.attacks[_attack_index % now.attacks.size()]
	if not _warned and _since_attack >= now.interval - now.telegraph_s:
		_warned = true
		telegraphed.emit(attack)
	if _since_attack >= now.interval:
		_since_attack -= now.interval
		_warned = false
		_attack_index += 1
		attacked.emit(attack)
		_perform(attack)

## Where the explosion number `index` of the defeat is, relative to the boss: the same every time.
static func burst_offset(index: int) -> Vector2:
	var angle := index * 2.4
	return Vector2(cos(angle), sin(angle)) * (8.0 + 6.0 * (index % 4))

## The attack `attack` happens now. The kinds fire their bullets here.
func _perform(_attack: String) -> void:
	pass

## The movement `pattern` at `time_s` seconds into the fight. The kinds add their own.
func _move(pattern: String, _delta: float, time_s: float) -> void:
	if pattern == "sweep":
		position = _home + Vector2(sin(time_s * phase().speed) * sweep_px, 0.0)
