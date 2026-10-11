class_name RpgArcadeMode
extends RpgCombatMode
## The combat mode of the arcade kinds (SceneRouter.combat): a run through the stages of
## game/data/stages.json with lives and a score. The mode of a kind extends it, as
## RpgMetroidvaniaMode extends RpgCombatMode.
##
## A stage is a map (RpgArcadeStage): when the router has entered one the mode binds it, counts
## its kills, and on its end shows the tally and goes to the next stage. After the last stage the
## run ends with the high-score entry and the credits. A death costs a life; after the last one
## the continue screen asks: Continue starts the stage again with the score kept and the
## multiplier back at x1, Quit goes to the title.
##
## Saving: between stages only, by itself, into the autosave slot (the pause menu's Save is off).
## The save holds the stage, the lives, the score and the weapon; loading it starts that stage
## from its beginning.

signal stage_started(index: int)
signal stage_cleared(index: int, bonus: Dictionary)
## The next stage is asked for (the router loads its scene when it has one).
signal stage_wanted(index: int)
signal life_lost(left: int)
signal game_over
signal continued
signal run_finished(points: int, rank: int)

enum Phase { IDLE, PLAYING, CLEARING, GAME_OVER, FINISHED }

const GROUP := &"rpg_arcade_mode"
## The entry of the saved game's flags that holds the run.
const SAVE_ENTITY := "arcade"
const SCREEN_LAYER := 80

## The list of the stages (set by the recipe: the stages.json of the game).
@export var stages_path: String = ""

## Read by the save manager: every stage entered saves, without a wait and without a toast.
var autosave_on_every_map := true
## Read by the pause menu: Save cannot be pressed and says why.
var saves_between_stages := true
## The weapon of the run, kept in the save (the kinds set it).
var weapon := ""
## True for tests and smoke runs: no screen waits for a press.
var auto_screens := false
## What the continue screen answers when nobody can press a button.
var auto_continue := true

var lives: RpgArcadeLives = null
var score: RpgArcadeScore = null
var sequence: RpgArcadeStageSequence = null
var stage: RpgArcadeStage = null
var phase: int = Phase.IDLE
var in_run := false

## The lives and the score are children of the mode, made when it is first needed: not when the
## script is attached, or the scene the builder saves would hold them and every game would make
## them a second time.
func _ensure_parts() -> void:
	if lives == null:
		lives = get_node_or_null("Lives") as RpgArcadeLives
	if lives == null:
		lives = RpgArcadeLives.new()
		lives.name = "Lives"
		add_child(lives)
	if score == null:
		score = get_node_or_null("Score") as RpgArcadeScore
	if score == null:
		score = RpgArcadeScore.new()
		score.name = "Score"
		add_child(score)
	if not score.changed.is_connected(_on_score_changed):
		score.changed.connect(_on_score_changed)

func _ready() -> void:
	_ensure_parts()
	add_to_group(GROUP)
	var bus := RpgUtil.events()
	if bus != null:
		bus.map_entered.connect(_on_map_entered)
		bus.game_loaded.connect(_on_game_loaded)

## The arcade mode of the running game, or null.
static func current() -> RpgArcadeMode:
	var router := RpgUtil.router()
	if router != null and router.combat is RpgArcadeMode:
		return router.combat as RpgArcadeMode
	var tree := RpgUtil.tree()
	return tree.get_first_node_in_group(GROUP) as RpgArcadeMode if tree != null else null

func is_in_combat() -> bool:
	return false

func start_encounter(_data: RpgEncounterData) -> void:
	push_warning("[RPG-COMBAT] an arcade game has no encounters; enemies come in waves")

## The stages of the run (read once from `stages_path`).
func stages() -> RpgArcadeStageSequence:
	if sequence == null:
		sequence = RpgArcadeStageSequence.load_file(stages_path)
	return sequence

func _on_score_changed(points: int, _multiplier: int) -> void:
	lives.on_score(points)

func _on_game_loaded(_slot: int) -> void:
	in_run = false  # the stage that is entered next takes the run from the loaded game

func _on_map_entered(_map_id: StringName) -> void:
	var router := RpgUtil.router()
	var map: Node = router.current_map if router != null else null
	if map is RpgArcadeStage:
		bind_stage(map as RpgArcadeStage)
	else:
		stage = null
		in_run = false
		phase = Phase.IDLE

# ------------------------------------------------------------------ the run

## What the saved game holds of the run ({} for a new game).
func saved_run() -> Dictionary:
	var state := RpgUtil.state()
	if state == null:
		return {}
	return RpgUtil.to_dict(state.flags.get(SAVE_ENTITY, {}))

func _store_run() -> void:
	var state := RpgUtil.state()
	if state == null:
		return
	state.flags[SAVE_ENTITY] = {
		"stage": stages().index,
		"lives": lives.count,
		"score": score.points,
		"weapon": weapon,
	}

func _forget_run() -> void:
	var state := RpgUtil.state()
	if state != null:
		state.flags.erase(SAVE_ENTITY)

## A run begins with the first stage that is entered: a new one, or the one of a loaded game.
func _begin_run() -> void:
	in_run = true
	var saved := saved_run()
	if saved.is_empty():
		score.reset()
		lives.reset()
		weapon = ""
		return
	score.restore(RpgUtil.to_int(saved.get("score", 0)))
	lives.restore(RpgUtil.to_int(saved.get("lives", lives.start_lives), lives.start_lives), score.points)
	weapon = RpgUtil.to_str(saved.get("weapon", ""))

## Takes over a stage that has just been entered: gives it its waves, counts its kills and
## starts it. Called by itself when the router enters a stage.
func bind_stage(next: RpgArcadeStage) -> void:
	_ensure_parts()
	stage = next
	var all := stages()
	all.index = clampi(next.stage_index, 0, maxi(0, all.size() - 1))
	if not in_run:
		_begin_run()
	if not next.is_configured() and not all.current().is_empty():
		next.setup(all.current())
	next.enemy_defeated.connect(_on_kill)
	next.boss_defeated.connect(_on_kill)
	next.cleared.connect(_on_stage_cleared)
	_store_run()
	phase = Phase.PLAYING
	next.begin()
	stage_started.emit(next.stage_index)

func _on_kill(points: int) -> void:
	if phase == Phase.PLAYING:
		score.add_kill(points)

## The player picked something up worth `points`.
func pickup(points: int) -> void:
	if phase == Phase.PLAYING:
		score.add_pickup(points)

## The player was hit and lives on: the multiplier is gone.
func player_hit() -> void:
	if phase == Phase.PLAYING:
		score.hit()

## The player died: a life is lost. With lives left `life_lost` says so (the kind puts the player
## back); without, the continue screen.
func player_died() -> void:
	if phase != Phase.PLAYING:
		return
	score.hit()
	if lives.lose():
		await _game_over()
	else:
		life_lost.emit(lives.count)

## What the shared code calls for a defeated player.
func apply_defeat() -> void:
	await player_died()

func _game_over() -> void:
	phase = Phase.GAME_OVER
	game_over.emit()
	if await _ask_continue():
		lives.reset(score.points)
		score.reset_multiplier()
		continued.emit()
		await _go_to_stage(stages().index)
		return
	await _enter_score()
	await quit_run()

## Ends the run and goes to the title.
func quit_run() -> void:
	_end_run()
	var router := RpgUtil.router()
	if router != null and ResourceLoader.exists(RpgMenuUtil.TITLE_SCENE):
		await router.go_to(RpgMenuUtil.TITLE_SCENE)

func _end_run() -> void:
	in_run = false
	phase = Phase.IDLE
	stage = null
	_forget_run()

func _on_stage_cleared() -> void:
	if phase != Phase.PLAYING or stage == null:
		return
	phase = Phase.CLEARING
	var index := stage.stage_index
	var bonus := RpgArcadeStageClear.tally(stage.time_s, stage.par_time_s, lives.count)
	score.add_bonus(RpgUtil.to_int(bonus["total"]))
	stage_cleared.emit(index, bonus)
	await _show_stage_clear(bonus)
	var all := stages()
	if all.is_last():
		await _finish_run()
		return
	all.advance()
	await _go_to_stage(all.index)

## Asks for the stage `index`: its scene is loaded when there is a router and a scene (the stage
## is bound when it is entered).
func _go_to_stage(index: int) -> void:
	stage_wanted.emit(index)
	var router := RpgUtil.router()
	var path := stages().scene_of(index)
	if router != null and path != "" and ResourceLoader.exists(path):
		await router.go_to(path)

## The last stage is cleared: the high-score entry, then the credits.
func _finish_run() -> void:
	var points := score.points
	var rank := await _enter_score()
	_end_run()
	phase = Phase.FINISHED
	run_finished.emit(points, rank)
	_show_credits()

## Puts the run into the high-score table when it is good enough (the name is asked for).
## Returns its place, or -1.
func _enter_score() -> int:
	var points := score.points
	var table := RpgArcadeHighScores.read()
	if RpgArcadeHighScores.rank_of(table, points) < 0:
		return -1
	var player_name := await _ask_name(table, points)
	return RpgArcadeHighScores.submit(player_name, points, stages().index + 1)

func _show_credits() -> void:
	var router := RpgUtil.router()
	var controller := router.get_node_or_null("UiController") if router != null else null
	if controller != null and controller.has_method(&"open_menu"):
		controller.call(&"open_menu", "credits_menu", {})

# ------------------------------------------------------------------ the screens

## True when nobody can press a button: a test, a smoke run.
func is_automatic() -> bool:
	return auto_screens or RpgDefeatPolicy.is_automatic() or not is_inside_tree()

## Shows `screen` over the game, which stands still until _close() is called with the layer.
func _open(screen: Control) -> CanvasLayer:
	var layer := CanvasLayer.new()
	layer.name = "ArcadeScreen"
	layer.layer = SCREEN_LAYER
	layer.process_mode = Node.PROCESS_MODE_ALWAYS
	layer.add_child(screen)
	var router := RpgUtil.router()
	var host: Node = router if router != null else self
	host.add_child(layer)
	get_tree().paused = true
	return layer

func _close(layer: CanvasLayer) -> void:
	get_tree().paused = false
	layer.queue_free()

func _ask_continue() -> bool:
	if is_automatic():
		return auto_continue
	var screen := RpgArcadeContinueScreen.new()
	var layer := _open(screen)
	var go_on: bool = await screen.chosen
	_close(layer)
	return go_on

func _show_stage_clear(bonus: Dictionary) -> void:
	if is_automatic() or stage == null:
		return
	var screen := RpgArcadeStageClear.new()
	var layer := _open(screen)
	screen.show_tally(stage.title_text(), bonus, score.points)
	await screen.finished
	_close(layer)

func _ask_name(table: Array[Dictionary], points: int) -> String:
	if is_automatic():
		return RpgArcadeHighScores.DEFAULT_NAME
	var screen := RpgArcadeHighScoreTable.new()
	var layer := _open(screen)
	screen.show_table(table, true, points)
	var typed: String = await screen.closed
	_close(layer)
	return typed
