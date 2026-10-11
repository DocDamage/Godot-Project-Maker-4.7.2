class_name RpgArcadeStage
extends RpgMapRoot
## One stage of an arcade run: a map with a camera that a scroller moves, waves of enemies that
## spawners bring in, a place for a boss, and a condition that ends it. What happens in it comes
## from the stage's entry in game/data/stages.json (RpgArcadeStageSequence); the runtime reads the
## waves and never invents one.
##
## The stage ends ("exit"): `reach_end` when the scroller has come to the end of its length,
## `clear_waves` when every wave is cleared, `custom` when the kind calls finish() (the laps of a
## race). A boss, when the stage has one, comes in at that moment and has to be beaten first.

signal started
signal wave_cleared(wave_id: String)
signal enemy_defeated(points: int)
signal boss_started(boss: RpgArcadeBoss)
signal boss_defeated(points: int)
## A formation was shot whole: its bonus.
signal formation_bonus(points: int)
signal cleared

const EXITS: Array[String] = ["reach_end", "clear_waves", "custom"]
const SCROLLER_NODE := "Scroller"
const ENTITIES_NODE := "Entities"
const BOSS_NODE := "Boss"
const CAMERA_NODE := "Camera"

## Which stage of the run this is (the index in game/data/stages.json).
@export var stage_index: int = 0
## The name shown on the HUD and the tally: a translation key or plain text. Empty shows "Stage N".
@export var title: String = ""
@export var exit_condition: String = "clear_waves"
## A stage cleared faster than this earns a time bonus; 0 gives none.
@export var par_time_s: float = 0.0

## Makes the enemy of a wave (RpgArcadeWave -> Node2D). Unset, the scene of the wave is instanced.
var enemy_factory: Callable = Callable()
## Makes the boss (Dictionary -> RpgArcadeBoss). Unset, the node "Boss" or the scene of the entry.
var boss_factory: Callable = Callable()
## False for a test that steps the stage by hand.
var auto_advance := true

var time_s := 0.0
var running := false
var is_cleared := false
var boss: RpgArcadeBoss = null
var spawners: Array[RpgArcadeSpawner] = []

var _boss_data: Dictionary = {}
var _boss_started := false
var _boss_done := false
var _finish_asked := false
var _cleared_ids: Dictionary = {}
var _configured := false

func _physics_process(delta: float) -> void:
	if auto_advance:
		advance(delta)

func scroller() -> RpgArcadeScroller:
	var found := get_node_or_null(SCROLLER_NODE) as RpgArcadeScroller
	if found == null:
		found = RpgArcadeScroller.new()
		found.name = SCROLLER_NODE
		found.axis = "none"
		add_child(found)
	return found

## Where the enemies go (a node "Entities", made when the scene has none).
func entities() -> Node2D:
	var found := get_node_or_null(ENTITIES_NODE) as Node2D
	if found == null:
		found = Node2D.new()
		found.name = ENTITIES_NODE
		add_child(found)
	return found

func is_configured() -> bool:
	return _configured

## The text of the stage's name.
func title_text() -> String:
	if title == "":
		return RpgArcadeStrings.t("ARC_STAGE", [stage_index + 1])
	return tr(title)

## Reads the entry of this stage: how it scrolls, how it ends, its waves and its boss.
func setup(data: Dictionary) -> void:
	_configured = true
	if data.has("title"):
		title = RpgUtil.to_str(data["title"])
	var wanted := RpgUtil.to_str(data.get("exit", exit_condition))
	exit_condition = wanted if EXITS.has(wanted) else "clear_waves"
	par_time_s = RpgUtil.to_float(data.get("par_time_s", par_time_s), par_time_s)
	var scroll := scroller()
	var axis := RpgUtil.to_str(data.get("axis", scroll.axis))
	scroll.axis = axis if RpgArcadeScroller.AXES.has(axis) else "none"
	scroll.speed = RpgUtil.to_float(data.get("speed", scroll.speed), scroll.speed)
	scroll.length = maxf(0.0, RpgUtil.to_float(data.get("length", scroll.length), scroll.length))
	for old in spawners:
		old.queue_free()
	spawners.clear()
	var number := 0
	for raw: Variant in RpgUtil.to_array(data.get("waves", [])):
		if not (raw is Dictionary):
			continue
		var entry: Dictionary = raw
		var spawner := RpgArcadeSpawner.new()
		spawner.wave = RpgArcadeWave.from_dict(entry)
		if spawner.wave.id == "":
			spawner.wave.id = "wave_%02d" % number
		spawner.name = "Spawner%02d" % number
		spawner.cleared.connect(_on_wave_cleared.bind(spawner))
		spawner.enemy_defeated.connect(_on_enemy_defeated)
		spawner.cleared_whole.connect(_on_cleared_whole)
		add_child(spawner)
		spawners.append(spawner)
		number += 1
	_boss_data = RpgUtil.to_dict(data.get("boss", {}))

## The stage starts: time runs, the scroller moves, the waves come.
func begin() -> void:
	if running or is_cleared:
		return
	running = true
	started.emit()

## The kind says the stage is done (exit "custom": the last lap is finished).
func finish() -> void:
	_finish_asked = true

func waves_cleared() -> bool:
	for spawner in spawners:
		if not spawner.is_cleared():
			return false
	return true

## One step of the stage.
func advance(delta: float) -> void:
	if not running or is_cleared:
		return
	time_s += delta
	var scroll := scroller()
	scroll.advance(delta)
	for spawner in spawners:
		if spawner.should_trigger(scroll.progress, time_s, _cleared_ids):
			_trigger(spawner, scroll)
		spawner.advance(delta)
	if not _end_reached(scroll):
		return
	if has_boss() and not _boss_started:
		_start_boss(scroll)
	if not has_boss() or _boss_done:
		_clear()

func _trigger(spawner: RpgArcadeSpawner, scroll: RpgArcadeScroller) -> void:
	var wave := spawner.wave
	var middle := wave.position if wave.anchor == "stage" else scroll.view_center() + wave.position
	if wave.blocking:
		scroll.hold(spawner)
	spawner.trigger(middle, _make_enemy, entities())

func _make_enemy(wave: RpgArcadeWave) -> Node2D:
	if enemy_factory.is_valid():
		var made: Variant = enemy_factory.call(wave)
		if made is Node2D:
			var enemy: Node2D = made
			return enemy
		return null
	if wave.scene != "" and ResourceLoader.exists(wave.scene):
		var packed := load(wave.scene) as PackedScene
		if packed != null:
			return packed.instantiate() as Node2D
	push_warning("[RPG-ARCADE] wave %s has no enemy to spawn" % wave.id)
	return null

func _on_wave_cleared(spawner: RpgArcadeSpawner) -> void:
	_cleared_ids[spawner.wave.id] = true
	scroller().release(spawner)
	wave_cleared.emit(spawner.wave.id)

func _on_enemy_defeated(points: int) -> void:
	enemy_defeated.emit(points)

func _on_cleared_whole(bonus: int) -> void:
	if bonus > 0:
		formation_bonus.emit(bonus)

## Takes an enemy that no wave brought (what a carrier releases, the halves of an asteroid) into
## the stage at `at`: its kill is scored like any other, and no wave waits for it.
func adopt(enemy: Node2D, at: Vector2) -> void:
	enemy.position = at
	if enemy.has_signal(&"defeated"):
		enemy.connect(&"defeated", _on_adopted_defeated.bind(enemy))
	entities().add_child(enemy)

func _on_adopted_defeated(enemy: Node2D) -> void:
	var own: Variant = enemy.get(&"points") if is_instance_valid(enemy) else null
	enemy_defeated.emit(RpgUtil.to_int(own, 0) if own != null else 0)

func _end_reached(scroll: RpgArcadeScroller) -> bool:
	match exit_condition:
		"reach_end":
			return scroll.at_end() and _blocking_cleared()
		"custom":
			return _finish_asked
	return waves_cleared()

func _blocking_cleared() -> bool:
	for spawner in spawners:
		if spawner.wave.blocking and not spawner.is_waiting() and not spawner.is_cleared():
			return false
	return true

func has_boss() -> bool:
	return not _boss_data.is_empty() or get_node_or_null(BOSS_NODE) is RpgArcadeBoss

func _find_boss() -> RpgArcadeBoss:
	var placed := get_node_or_null(BOSS_NODE) as RpgArcadeBoss
	if placed != null:
		return placed
	var made: RpgArcadeBoss = null
	if boss_factory.is_valid():
		var out: Variant = boss_factory.call(_boss_data)
		if out is RpgArcadeBoss:
			made = out
	else:
		var path := RpgUtil.to_str(_boss_data.get("scene", ""))
		if path != "" and ResourceLoader.exists(path):
			var packed := load(path) as PackedScene
			made = packed.instantiate() as RpgArcadeBoss if packed != null else null
	if made != null:
		made.name = BOSS_NODE
		var where := RpgUtil.to_array(_boss_data.get("position", []))
		var at := Vector2.ZERO
		if where.size() >= 2:
			at = Vector2(RpgUtil.to_float(where[0]), RpgUtil.to_float(where[1]))
		made.position = scroller().view_center() + at
		entities().add_child(made)
	return made

func _start_boss(scroll: RpgArcadeScroller) -> void:
	_boss_started = true
	boss = _find_boss()
	if boss == null:
		push_warning("[RPG-ARCADE] stage %d has a boss entry and no boss to show" % stage_index)
		_boss_done = true
		return
	if not _boss_data.is_empty():
		boss.setup(_boss_data)
	scroll.hold(boss)
	boss.defeated.connect(_on_boss_defeated)
	boss.finished.connect(_on_boss_finished)
	boss.begin()
	boss_started.emit(boss)

func _on_boss_defeated() -> void:
	boss_defeated.emit(boss.points if boss != null else 0)

func _on_boss_finished() -> void:
	_boss_done = true
	if boss != null:
		scroller().release(boss)

func _clear() -> void:
	is_cleared = true
	running = false
	cleared.emit()
