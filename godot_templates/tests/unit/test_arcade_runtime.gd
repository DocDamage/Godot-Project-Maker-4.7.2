extends RefCounted
## T16.01: the arcade framework. Stages and their waves, the scroller, lives and score, bosses,
## the continue screen, the high scores in the shared section of the saves, the HUD and the
## builder's stage scenes.

const Fixtures := preload("../lib/fixtures.gd")
const ArcadeBuild := preload("res://builder/recipes/arcade/arcade_build.gd")
const StageRecipes := preload("res://builder/recipes/arcade/stage_recipes.gd")
const HudRecipe := preload("res://builder/recipes/arcade/hud_recipe.gd")

const STEP := 0.125  # exact in binary: steps add up to whole seconds
const SAVE_DIR := "user://test_arcade_saves"

## A drawn stand-in that can be shot: what a kind's enemy is to the framework.
class Enemy extends Node2D:
	signal defeated
	var points := 100

	func kill() -> void:
		defeated.emit()
		leave()

	## Gone without a kill: flown off the screen.
	func leave() -> void:
		if get_parent() != null:
			get_parent().remove_child(self)  # the spawner hears of it now
		queue_free()

static func _enemy(wave: RpgArcadeWave) -> Node2D:
	var enemy := Enemy.new()
	enemy.points = wave.points
	enemy.add_child(ArcadeBuild.stand_in("Visual", Vector2(12, 12), Color.RED))
	return enemy

func _stage(index: int, data: Dictionary) -> RpgArcadeStage:
	var stage := StageRecipes.build_stage(index, data, Vector2i(320, 180), Vector2(160, 150)) as RpgArcadeStage
	stage.auto_advance = false
	stage.enemy_factory = _enemy
	Fixtures.tree().root.add_child(stage)
	if not data.is_empty():
		stage.setup(data)  # without a mode the stage reads its own entry
	return stage

func _drop(node: Node) -> void:
	if node.get_parent() != null:
		node.get_parent().remove_child(node)
	node.free()

func _enemies(stage: RpgArcadeStage) -> Array:
	return stage.entities().get_children().filter(func(n: Node) -> bool: return n is Enemy)

func _kill_all(stage: RpgArcadeStage) -> int:
	var killed := 0
	for enemy: Enemy in _enemies(stage):
		enemy.kill()
		killed += 1
	return killed

func _mode() -> RpgArcadeMode:
	var mode := RpgArcadeMode.new()
	mode.auto_screens = true
	Fixtures.tree().root.add_child(mode)
	return mode

func _saves() -> Node:
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER)
	save.dir = SAVE_DIR
	if DirAccess.dir_exists_absolute(SAVE_DIR):
		for file: String in DirAccess.get_files_at(SAVE_DIR):
			DirAccess.remove_absolute(SAVE_DIR.path_join(file))
	return save

const TWO_STAGES := [
	{"title": "First", "exit": "clear_waves", "par_time_s": 30.0,
		"waves": [{"id": "a", "formation": "line", "count": 3, "gap": 20, "position": [0, -40], "points": 100}]},
	{"title": "Second", "exit": "clear_waves",
		"waves": [{"id": "b", "formation": "v", "count": 2, "points": 250}]},
]

# ---------------------------------------------------------------- score and lives

func test_the_score_counts_with_a_multiplier_that_a_hit_resets(t) -> void:
	var score := RpgArcadeScore.new()
	var seen: Array = []
	score.changed.connect(func(points: int, multiplier: int) -> void: seen.append([points, multiplier]))
	for i in 4:
		t.eq(score.add_kill(100), 100)
	t.eq(score.multiplier, 1)
	t.eq(score.add_kill(100), 100, "the fifth kill is still counted once")
	t.eq(score.multiplier, 2, "five kills in a row")
	t.eq(score.add_kill(100), 200)
	t.eq(score.add_pickup(50), 100, "a pickup is multiplied and does not feed the streak")
	t.eq(score.streak, 6)
	score.add_bonus(1000)
	t.eq(score.points, 1800)
	score.hit()
	t.eq([score.multiplier, score.streak, score.points], [1, 0, 1800], "a hit costs the multiplier, not the points")
	t.eq(seen[-1], [1800, 1])
	for i in 100:
		score.add_kill(1)
	t.eq(score.multiplier, RpgArcadeScore.MAX_MULTIPLIER, "it stops growing at the top")
	t.eq(score.add_kill(-5), 0, "nothing is taken away")
	score.reset()
	t.eq([score.points, score.multiplier], [0, 1])
	score.free()

func test_lives_are_lost_gained_by_score_and_end_the_game(t) -> void:
	var lives := RpgArcadeLives.new()
	lives.start_lives = 3
	lives.extra_every = 1000
	lives.reset()
	var events: Array = []
	lives.extra_life.connect(func() -> void: events.append("extra"))
	lives.game_over.connect(func() -> void: events.append("over"))
	lives.on_score(999)
	t.eq(lives.count, 3)
	lives.on_score(1000)
	t.eq(lives.count, 4, "an extra life at the first thousand")
	lives.on_score(1500)
	t.eq(lives.count, 4, "once per step")
	lives.on_score(3200)
	t.eq(lives.count, 6, "two steps at once are two lives")
	for i in 20:
		lives.on_score(4000 + i * 1000)
	t.eq(lives.count, RpgArcadeLives.MAX_LIVES)
	lives.reset(25000)
	t.eq(lives.count, 3, "a continue starts with the starting lives")
	lives.on_score(25500)
	t.eq(lives.count, 3, "and is not paid again for the score it has")
	lives.on_score(26000)
	t.eq(lives.count, 4)
	events.clear()
	lives.reset()
	t.ok(not lives.lose())
	t.ok(not lives.lose())
	t.ok(lives.lose(), "the third death is the last")
	t.eq(events, ["over"])
	t.ok(lives.lose() and lives.count == 0, "nothing below zero")
	lives.extra_every = 0
	lives.on_score(999999)
	t.eq(lives.count, 0, "0 gives no extra lives")
	lives.restore(2, 0)
	t.eq(lives.count, 2)
	lives.free()

# ---------------------------------------------------------------- waves

func test_a_wave_is_read_from_its_entry_and_every_formation_has_its_places(t) -> void:
	var wave := RpgArcadeWave.from_dict({"id": "w", "enemy": "drone", "formation": "circle", "count": 4.0, "gap": 10,
		"position": [20, -30], "trigger": "progress", "at": 120, "blocking": true, "points": 300, "interval": 0.5})
	t.eq([wave.id, wave.enemy, wave.formation, wave.count, wave.trigger], ["w", "drone", "circle", 4, "progress"])
	t.eq([wave.position, wave.at, wave.blocking, wave.points, wave.interval], [Vector2(20, -30), 120.0, true, 300, 0.5])
	var plain := RpgArcadeWave.from_dict({"formation": "spiral", "trigger": "whenever", "count": 0})
	t.eq([plain.formation, plain.trigger, plain.count, plain.anchor], ["line", "start", 1, "screen"], "what is not known is the plain thing")
	t.eq(RpgArcadeWave.FORMATIONS.size(), 5)
	for shape in RpgArcadeWave.FORMATIONS:
		for count: int in [1, 2, 5, 8]:
			var places := RpgArcadeWave.offsets(shape, count, 16.0)
			t.eq(places.size(), count, "%s of %d" % [shape, count])
			var distinct := {}
			for place in places:
				distinct[place.snappedf(0.01)] = true
			t.eq(distinct.size(), count, "%s of %d: nobody stands on another" % [shape, count])
			t.eq(places, RpgArcadeWave.offsets(shape, count, 16.0), "the same every time")
	t.eq(RpgArcadeWave.offsets("line", 3, 10.0), PackedVector2Array([Vector2(-10, 0), Vector2(0, 0), Vector2(10, 0)]))
	t.eq(RpgArcadeWave.offsets("column", 2, 10.0), PackedVector2Array([Vector2(0, -5), Vector2(0, 5)]))
	t.eq(RpgArcadeWave.offsets("v", 3, 10.0), PackedVector2Array([Vector2(0, 0), Vector2(-10, -10), Vector2(10, -10)]))
	for place in RpgArcadeWave.offsets("circle", 6, 10.0):
		t.near(place.length(), 10.0, 0.01, "never tighter than the gap")
	t.near(RpgArcadeWave.offsets("circle", 12, 10.0)[0].length(), 120.0 / TAU, 0.01)

func test_a_spawner_waits_for_its_trigger_and_spawns_at_an_interval(t) -> void:
	await Fixtures.tree().process_frame
	var holder := Node2D.new()
	Fixtures.tree().root.add_child(holder)
	var spawner := RpgArcadeSpawner.new()
	spawner.wave = RpgArcadeWave.from_dict({"id": "late", "count": 3, "interval": 1.0, "gap": 10, "trigger": "time", "at": 2.0, "points": 70})
	holder.add_child(spawner)
	var log: Array = []
	spawner.spawned.connect(func(_e: Node2D) -> void: log.append("spawn"))
	spawner.enemy_defeated.connect(func(points: int) -> void: log.append(points))
	spawner.cleared.connect(func() -> void: log.append("cleared"))
	t.ok(not spawner.should_trigger(999.0, 1.9, {}), "time is not progress")
	t.ok(spawner.should_trigger(0.0, 2.0, {}))
	spawner.trigger(Vector2(100, 50), _enemy, holder)
	t.eq(log, ["spawn"], "the first one at once")
	t.ok(not spawner.should_trigger(0.0, 9.0, {}), "a wave comes once")
	spawner.advance(0.5)
	t.eq(spawner.alive(), 1)
	var first := holder.get_child(1) as Enemy
	t.eq(first.position, Vector2(90, 50), "the left end of the line")
	first.kill()
	t.eq(log, ["spawn", 70])
	t.ok(not spawner.is_cleared(), "two are still to come")
	spawner.advance(0.5)
	spawner.advance(1.0)
	t.eq(spawner.alive(), 2)
	t.eq(log, ["spawn", 70, "spawn", "spawn"])
	(holder.get_child(1) as Enemy).leave()
	t.ok(not spawner.is_cleared())
	(holder.get_child(1) as Enemy).kill()
	t.eq(log, ["spawn", 70, "spawn", "spawn", 70, "cleared"], "an enemy that left is gone without points")
	var after := RpgArcadeSpawner.new()
	after.wave = RpgArcadeWave.from_dict({"trigger": "after", "after": "late"})
	t.ok(not after.should_trigger(0.0, 0.0, {}))
	t.ok(after.should_trigger(0.0, 0.0, {"late": true}))
	after.free()
	_drop(holder)

# ---------------------------------------------------------------- the scroller

func test_the_scroller_stops_at_a_blocking_wave_and_goes_on(t) -> void:
	await Fixtures.tree().process_frame
	var stage := _stage(0, {"axis": "up", "speed": 80.0, "length": 200.0, "exit": "reach_end", "waves": [
		{"id": "gate", "trigger": "progress", "at": 100, "count": 2, "blocking": true, "position": [0, -60]},
		{"id": "free", "trigger": "progress", "at": 150, "count": 1},
	]})
	var scroll := stage.scroller()
	var camera := stage.get_node("Camera") as Camera2D
	var events: Array = []
	scroll.stopped.connect(func() -> void: events.append("stopped"))
	scroll.resumed.connect(func() -> void: events.append("resumed"))
	stage.cleared.connect(func() -> void: events.append("cleared"))
	stage.begin()
	t.eq(camera.position, Vector2(160, 90))
	for i in 9:
		stage.advance(STEP)
	t.near(scroll.progress, 90.0, 0.01)
	t.eq(camera.position.y, 90.0 - 90.0, "up is toward smaller y")
	t.eq(_enemies(stage).size(), 0)
	stage.advance(STEP)
	t.eq(_enemies(stage).size(), 2, "the wave comes at 100 px")
	t.ok(scroll.is_held())
	t.eq((_enemies(stage)[0] as Node2D).position, Vector2(160 - 12, 90 - 100 - 60), "placed relative to the camera")
	for i in 30:
		stage.advance(STEP)
	t.near(scroll.progress, 100.0, 0.01, "it waits for the wave")
	t.eq(events, ["stopped"])
	(_enemies(stage)[0] as Enemy).kill()
	stage.advance(STEP)
	t.near(scroll.progress, 100.0, 0.01, "one enemy is left")
	(_enemies(stage)[0] as Enemy).leave()
	t.eq(events, ["stopped", "resumed"])
	for i in 5:
		stage.advance(STEP)
	t.near(scroll.progress, 150.0, 0.01)
	t.eq(_enemies(stage).size(), 1, "the second wave does not hold the scroller")
	for i in 30:
		stage.advance(STEP)
	t.near(scroll.progress, 200.0, 0.01, "it ends at the length")
	t.eq(events, ["stopped", "resumed", "cleared"], "reach_end does not wait for a wave that does not block")
	t.ok(stage.is_cleared and not stage.running)
	var still := RpgArcadeScroller.new()
	still.axis = "none"
	t.eq(still.advance(1.0), 0.0)
	still.axis = "right"
	still.speed = 10.0
	still.advance(1.0)
	t.eq(still.offset(), Vector2(10, 0))
	still.hold(self)
	still.hold(self)
	still.release(self)
	t.ok(not still.is_held(), "one holder holds once")
	still.free()
	_drop(stage)

# ---------------------------------------------------------------- a run

func test_a_run_of_two_stages_is_cleared_by_killing_the_spawns(t) -> void:
	await Fixtures.tree().process_frame
	Fixtures.install_state()
	_saves()
	var mode := _mode()
	mode.sequence = RpgArcadeStageSequence.from_array(StageRecipes.with_scenes(TWO_STAGES))
	t.eq(mode.sequence.scene_of(1), "res://generated/scenes/stages/stage_02.tscn")
	var log: Array = []
	mode.stage_started.connect(func(i: int) -> void: log.append("start %d" % i))
	mode.stage_cleared.connect(func(i: int, bonus: Dictionary) -> void: log.append("clear %d +%d" % [i, bonus["total"]]))
	mode.stage_wanted.connect(func(i: int) -> void: log.append("want %d" % i))
	mode.run_finished.connect(func(points: int, rank: int) -> void: log.append("done %d #%d" % [points, rank]))
	var first := _stage(0, {})
	mode.bind_stage(first)
	t.eq(first.title_text(), "First", "the stage got its entry of the list")
	t.eq([mode.lives.count, mode.score.points, mode.phase], [3, 0, RpgArcadeMode.Phase.PLAYING])
	first.advance(STEP)
	t.eq(_enemies(first).size(), 3)
	(_enemies(first)[0] as Enemy).kill()
	first.advance(STEP)
	t.ok(not first.is_cleared)
	t.eq(_kill_all(first), 2)
	first.advance(STEP)
	t.ok(first.is_cleared)
	# 3 kills of 100, a time bonus for 30 s of par less 0.375 s (30 whole seconds left) and 3 lives
	t.eq(mode.score.points, 300 + 30 * 100 + 3 * 1000)
	t.eq(log, ["start 0", "clear 0 +6000", "want 1"])
	t.eq(mode.saved_run().get("stage"), 0, "the save is of the start of the stage")
	var second := _stage(1, {})
	mode.bind_stage(second)
	t.eq(mode.saved_run(), {"stage": 1, "lives": 3, "score": 6300, "weapon": ""}, "saved between the stages")
	second.advance(STEP)
	t.eq(_kill_all(second), 2)
	second.advance(STEP)
	t.eq(mode.phase, RpgArcadeMode.Phase.FINISHED)
	t.eq(log.slice(3), ["start 1", "clear 1 +3000", "done 9800 #0"], "no par time: only the lives pay")
	t.eq(RpgArcadeHighScores.read(), [{"name": "AAA", "score": 9800, "stage": 2}] as Array[Dictionary])
	t.eq(mode.saved_run(), {}, "a finished run is not in the saved game")
	t.ok(not mode.in_run)
	_drop(first)
	_drop(second)
	_drop(mode)
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()

func test_the_last_life_asks_to_continue_and_continue_starts_the_stage_again(t) -> void:
	await Fixtures.tree().process_frame
	Fixtures.install_state()
	_saves()
	var mode := _mode()
	mode.sequence = RpgArcadeStageSequence.from_array(StageRecipes.with_scenes(TWO_STAGES))
	var log: Array = []
	mode.life_lost.connect(func(left: int) -> void: log.append("lost, %d left" % left))
	mode.game_over.connect(func() -> void: log.append("over"))
	mode.continued.connect(func() -> void: log.append("continued"))
	mode.stage_wanted.connect(func(i: int) -> void: log.append("want %d" % i))
	var stage := _stage(0, {})
	mode.bind_stage(stage)
	stage.advance(STEP)
	for i in 6:
		mode.score.add_kill(100)
	t.eq(mode.score.multiplier, 2)
	mode.player_hit()
	t.eq(mode.score.multiplier, 1, "a hit costs the multiplier")
	var points := mode.score.points
	await mode.player_died()
	await mode.player_died()
	t.eq(log, ["lost, 2 left", "lost, 1 left"])
	await mode.player_died()
	t.eq(log.slice(2), ["over", "continued", "want 0"], "the stage is asked for again")
	t.eq([mode.lives.count, mode.score.points, mode.score.multiplier], [3, points, 1], "the score stays")
	t.ok(mode.in_run)
	# the stage comes again from its start
	var again := _stage(0, {})
	mode.bind_stage(again)
	t.eq(mode.phase, RpgArcadeMode.Phase.PLAYING)
	again.advance(STEP)
	t.eq(_enemies(again).size(), 3)
	# Quit: the run is over and its score is in the table
	mode.auto_continue = false
	log.clear()
	for i in 3:
		await mode.player_died()
	t.eq(log, ["lost, 2 left", "lost, 1 left", "over"])
	t.ok(not mode.in_run and mode.phase == RpgArcadeMode.Phase.IDLE)
	t.eq(mode.saved_run(), {})
	t.eq(RpgArcadeHighScores.read(), [{"name": "AAA", "score": points, "stage": 1}] as Array[Dictionary])
	await mode.player_died()
	t.eq(log.size(), 3, "nobody dies outside a stage")
	_drop(stage)
	_drop(again)
	_drop(mode)
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()

func test_the_run_is_in_the_saved_game_and_a_loaded_game_goes_on_with_it(t) -> void:
	await Fixtures.tree().process_frame
	var state := Fixtures.install_state() as RpgGameState
	_saves()
	var mode := _mode()
	mode.sequence = RpgArcadeStageSequence.from_array(StageRecipes.with_scenes(TWO_STAGES))
	var first := _stage(0, {})
	mode.bind_stage(first)
	mode.weapon = "spread"
	mode.score.add_kill(700)
	mode.lives.lose()
	first.advance(STEP)
	_kill_all(first)
	first.advance(STEP)
	var second := _stage(1, {})
	mode.bind_stage(second)
	var saved := JSON.stringify(state.to_dict())
	t.ok(saved.contains("\"arcade\""))
	# a new game forgets it; the loaded one has the run again, at x1
	state.new_game()
	mode._on_game_loaded(0)
	var fresh := _stage(0, {})
	mode.bind_stage(fresh)
	t.eq([mode.lives.count, mode.score.points, mode.weapon], [3, 0, ""], "a new game starts a new run")
	state.from_dict(RpgUtil.restore_numbers(JSON.parse_string(saved)))
	mode._on_game_loaded(1)
	var loaded := _stage(1, {})
	mode.bind_stage(loaded)
	t.eq(mode.stages().index, 1)
	t.eq([mode.lives.count, mode.score.points, mode.score.multiplier, mode.weapon], [2, 700 + 300 + 30 * 100 + 2000, 1, "spread"])
	t.eq(loaded.title_text(), "Second")
	t.ok(mode.autosave_on_every_map and mode.saves_between_stages and not mode.is_in_combat())
	for node: Node in [first, second, fresh, loaded, mode]:
		_drop(node)
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- high scores

func test_the_table_keeps_ten_sorted_entries_through_the_shared_section_of_the_saves(t) -> void:
	Fixtures.install_state()
	var save := _saves()
	t.eq(save.read_shared(), {}, "a game that never wrote it reads an empty section")
	t.eq(RpgArcadeHighScores.read(), [] as Array[Dictionary])
	var places: Array = []
	for i in 14:
		places.append(RpgArcadeHighScores.submit("P%d" % i, [500, 900, 100, 900, 300, 700, 200, 800, 600, 400, 50, 1000, 450, 10][i], i + 1))
	t.eq(places.slice(0, 4), [0, 0, 2, 1], "a later equal score goes behind the earlier one")
	t.eq(places.slice(10), [-1, 0, 7, -1], "the table is full: only a better score gets in")
	var table := RpgArcadeHighScores.read()
	t.eq(table.size(), RpgArcadeHighScores.MAX_ENTRIES)
	var scores: Array = table.map(func(e: Dictionary) -> int: return e["score"])
	t.eq(scores, [1000, 900, 900, 800, 700, 600, 500, 450, 400, 300])
	t.eq([table[1]["name"], table[2]["name"], table[0]["stage"]], ["P1", "P3", 12])
	t.eq(RpgArcadeHighScores.rank_of(table, 300), -1, "a tie with the last place does not push it out")
	t.eq(RpgArcadeHighScores.rank_of(table, 0), -1, "nothing is not a score")
	# the file is beside the slots, verified like them, and no slot knows of it
	t.ok(FileAccess.file_exists(SAVE_DIR.path_join("meta.json")))
	t.ok(not save.any_save())
	t.ok(save.set_shared_value("other", {"n": 3}))
	t.eq(save.shared_value("other"), {"n": 3})
	t.eq(RpgArcadeHighScores.read().size(), 10, "another value leaves the table alone")
	t.eq(save.shared_value("missing", "x"), "x")
	t.eq(RpgSaveManager.SAVE_VERSION, 1)
	var file := FileAccess.open(SAVE_DIR.path_join("meta.json"), FileAccess.WRITE)
	file.store_string("{\"values\": {\"high_scores\": [{\"name\": \"X\", \"score\": 99999}]}, \"checksum\": \"no\"}")
	file.close()
	t.eq(RpgArcadeHighScores.read(), [] as Array[Dictionary], "a damaged file is an empty table")
	t.eq(RpgArcadeHighScores.submit("  a very long name\n ", 5, 1), 0)
	t.eq(RpgArcadeHighScores.read()[0]["name"], "a very l")
	t.eq(RpgArcadeHighScores.clean([{"score": "x"}, "junk", {"name": "", "score": 4.0, "stage": 0}, {"score": 9}]),
		[{"name": "AAA", "score": 9, "stage": 1}, {"name": "AAA", "score": 4, "stage": 1}] as Array[Dictionary])
	Fixtures.uninstall("SaveManager")
	t.eq(RpgArcadeHighScores.read(), [] as Array[Dictionary], "without a save manager there is no table")
	t.eq(RpgArcadeHighScores.submit("A", 5, 1), 0)
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- bosses

func test_a_boss_changes_phase_at_the_fraction_warns_before_it_attacks_and_dies(t) -> void:
	var boss := RpgArcadeBoss.new()
	boss.auto_advance = false
	boss.setup({"name": "Core", "health": 100, "points": 4000, "phases": [
		{"until": 0.5, "movement": "sweep", "attacks": ["spread", "aimed"], "interval": 2.0, "telegraph_s": 0.5},
		{"until": 0.0, "movement": "still", "attacks": ["laser"], "interval": 1.0, "telegraph_s": 0.25},
	]})
	boss.intro_s = 1.0
	boss.defeat_s = 1.0
	boss.explosions = 4
	var log: Array = []
	boss.intro_started.connect(func(n: String) -> void: log.append("intro " + n))
	boss.intro_finished.connect(func() -> void: log.append("fight"))
	boss.phase_changed.connect(func(i: int) -> void: log.append("phase %d" % i))
	boss.telegraphed.connect(func(a: String) -> void: log.append("warn " + a))
	boss.attacked.connect(func(a: String) -> void: log.append("attack " + a))
	boss.defeated.connect(func() -> void: log.append("defeated"))
	boss.exploded.connect(func(_at: Vector2) -> void: log.append("boom"))
	boss.finished.connect(func() -> void: log.append("finished"))
	t.eq(boss.take(10), 0, "it cannot be hurt before it comes in")
	boss.begin()
	t.eq(boss.take(10), 0, "nor during its intro")
	for i in 8:
		boss.advance(STEP)
	t.eq(log, ["intro Core", "fight"])
	t.ok(boss.is_fighting() and boss.fraction() == 1.0)
	for i in 11:
		boss.advance(STEP)
	t.eq(log.slice(2), [], "nothing yet")
	boss.advance(STEP)
	t.eq(log.slice(2), ["warn spread"], "the warning comes half a second before the attack")
	for i in 4:
		boss.advance(STEP)
	t.eq(log.slice(2), ["warn spread", "attack spread"])
	t.ok(boss.position.x != 0.0, "it sweeps")
	for i in 16:
		boss.advance(STEP)
	t.eq(log.slice(4), ["warn aimed", "attack aimed"], "the attacks of a phase take turns")
	log.clear()
	t.eq(boss.take(49), 49)
	t.eq(boss.phase_index(), 0, "51 of 100 is above the half")
	boss.take(1)
	t.eq(boss.phase_index(), 1, "at the half the second phase begins")
	t.eq(log, ["phase 1"])
	var x := boss.position.x
	for i in 8:
		boss.advance(STEP)
	t.eq(boss.position.x, x, "it stands still now")
	t.eq(log, ["phase 1", "warn laser", "attack laser"])
	log.clear()
	t.eq(boss.take(500), 50, "no more than it has")
	t.eq(log, ["defeated"])
	t.eq(boss.take(1), 0, "a dead boss is not hit")
	boss.advance(STEP)
	t.eq(log, ["defeated", "boom"], "the explosions come one after another")
	for i in 7:
		boss.advance(STEP)
	t.eq(log, ["defeated", "boom", "boom", "boom", "boom", "finished"])
	t.eq(RpgArcadeBoss.burst_offset(3), RpgArcadeBoss.burst_offset(3))
	var plain := RpgArcadeBossPhase.list_from([])
	t.eq([plain.size(), plain[0].until], [1, 0.0], "a boss without phases has one")
	var mixed := RpgArcadeBossPhase.list_from([{"until": 0.2}, {"until": 0.7}, "junk"])
	t.eq([mixed[0].until, mixed[1].until], [0.7, 0.0], "sorted, and the last one lasts to the end")
	t.eq([RpgArcadeBossPhase.index_at(mixed, 1.0), RpgArcadeBossPhase.index_at(mixed, 0.7), RpgArcadeBossPhase.index_at(mixed, 0.0)], [0, 1, 1])
	boss.free()

func test_a_stage_with_a_boss_stops_for_it_and_ends_when_it_is_beaten(t) -> void:
	await Fixtures.tree().process_frame
	Fixtures.install_state()
	_saves()
	var mode := _mode()
	mode.sequence = RpgArcadeStageSequence.from_array([{"title": "Only", "axis": "right", "speed": 100.0, "length": 50.0,
		"exit": "reach_end", "boss": {"name": "Gate", "health": 30, "points": 2000, "position": [80, 0],
			"phases": [{"until": 0.0, "movement": "still"}]}}])
	var stage := _stage(0, {})
	stage.boss_factory = func(_data: Dictionary) -> RpgArcadeBoss:
		var made := RpgArcadeBoss.new()
		made.auto_advance = false
		made.intro_s = 0.25
		made.defeat_s = 0.25
		made.add_child(ArcadeBuild.stand_in("Visual", Vector2(48, 48), Color.PURPLE))
		return made
	var hud := HudRecipe.build_hud() as RpgArcadeHud
	Fixtures.tree().root.add_child(hud)
	hud.bind(mode)
	mode.bind_stage(stage)
	t.ok(stage.has_boss())
	t.ok(hud.visible and not hud.boss_shown())
	t.eq([hud.lives_text(), hud.score_text(), hud.stage_text()], ["Lives: 3", "Score: 0", "Only"])
	for i in 5:
		stage.advance(STEP)
	t.ok(stage.scroller().at_end())
	var boss := stage.boss
	t.ok(boss != null and boss.state == RpgArcadeBoss.State.INTRO, "the boss comes in at the end")
	t.eq([boss.boss_name, boss.max_health, boss.points], ["Gate", 30, 2000])
	t.eq(boss.position, Vector2(160 + 50 + 80, 90), "in front of the camera")
	t.ok(stage.scroller().is_held())
	t.ok(hud.boss_shown() and hud.boss_fraction() == 1.0)
	stage.advance(STEP)
	t.ok(not stage.is_cleared, "the stage waits for the boss")
	boss.advance(0.25)
	boss.take(15)
	t.near(hud.boss_fraction(), 0.5)
	boss.take(15)
	t.eq(mode.score.points, 2000, "the boss pays its points")
	stage.advance(STEP)
	t.ok(not stage.is_cleared, "its defeat plays out first")
	boss.advance(0.25)
	t.ok(not hud.boss_shown())
	stage.advance(STEP)
	t.ok(stage.is_cleared)
	t.eq(mode.phase, RpgArcadeMode.Phase.FINISHED, "the only stage: the run is over")
	t.eq(mode.score.points, 2000 + 3000)
	_drop(hud)
	_drop(stage)
	_drop(mode)
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()

func test_a_custom_exit_ends_when_the_kind_says_so(t) -> void:
	await Fixtures.tree().process_frame
	var stage := _stage(0, {"exit": "custom"})
	var cleared := [0]
	stage.cleared.connect(func() -> void: cleared[0] += 1)
	stage.begin()
	for i in 16:
		stage.advance(STEP)
	t.eq(cleared[0], 0, "a race is not over before its last lap")
	t.near(stage.time_s, 2.0, 0.001)
	stage.finish()
	stage.advance(STEP)
	stage.advance(STEP)
	t.eq(cleared[0], 1, "once")
	_drop(stage)

# ---------------------------------------------------------------- the HUD and the screens

func test_the_hud_shows_the_run_and_takes_rows_of_a_kind(t) -> void:
	await Fixtures.tree().process_frame
	Fixtures.install_state()
	var mode := _mode()
	mode.sequence = RpgArcadeStageSequence.from_array(TWO_STAGES)
	var hud := HudRecipe.build_hud() as RpgArcadeHud
	Fixtures.tree().root.add_child(hud)
	hud.bind(mode)
	t.ok(not hud.visible, "nothing to show before a stage")
	var stage := _stage(1, {})
	mode.bind_stage(stage)
	t.ok(hud.visible)
	t.eq(hud.stage_text(), "Second")
	for i in 5:
		mode.score.add_kill(100)
	t.eq([hud.score_text(), hud.multiplier_text()], ["Score: 500", "x2"])
	mode.lives.lose()
	t.eq(hud.lives_text(), "Lives: 2")
	hud.set_row("bombs", "Bombs: 3")
	hud.set_row("weapon", "Spread")
	t.eq([hud.row_text("bombs"), hud.row_text("weapon")], ["Bombs: 3", "Spread"])
	hud.set_row("bombs", "Bombs: 2")
	t.eq(hud.row_text("bombs"), "Bombs: 2")
	hud.set_row("bombs", "")
	t.eq(hud.row_text("bombs"), "")
	var untitled := _stage(0, {"title": ""})
	t.eq(untitled.title_text(), "Stage 1")
	for node: Node in [hud, stage, untitled, mode]:
		_drop(node)
	Fixtures.uninstall_state()

func test_the_tally_the_continue_screen_and_the_table_screen(t) -> void:
	await Fixtures.tree().process_frame
	t.eq(RpgArcadeStageClear.tally(42.3, 60.0, 2), {"time_bonus": 1800, "life_bonus": 2000, "total": 3800})
	t.eq(RpgArcadeStageClear.tally(90.0, 60.0, 0), {"time_bonus": 0, "life_bonus": 0, "total": 0}, "slower than par earns nothing")
	t.eq(RpgArcadeStageClear.tally(10.0, 0.0, 1)["time_bonus"], 0, "no par time, no time bonus")
	var clear := RpgArcadeStageClear.new()
	Fixtures.tree().root.add_child(clear)
	clear.show_tally("First", {"time_bonus": 1800, "life_bonus": 2000, "total": 3800}, 5000)
	var texts: Array = clear.find_children("*", "Label", true, false).map(func(l: Label) -> String: return l.text)
	t.eq(texts, ["First  Stage clear!", "Time bonus", "1800", "Lives bonus", "2000", "Score", "5000"])
	var closed := [0]
	clear.finished.connect(func() -> void: closed[0] += 1)
	clear.close()
	clear.close()
	t.eq(closed[0], 1)
	_drop(clear)
	var screen := RpgArcadeContinueScreen.new()
	Fixtures.tree().root.add_child(screen)
	screen.set_process(false)
	var answers: Array = []
	screen.chosen.connect(func(go_on: bool) -> void: answers.append(go_on))
	t.eq((screen.find_child("Countdown", true, false) as Label).text, "Continue? 9")
	screen.advance(3.5)
	t.eq((screen.find_child("Countdown", true, false) as Label).text, "Continue? 6")
	screen.advance(6.0)
	t.eq(answers, [false], "the countdown running out is Quit")
	screen.choose(true)
	t.eq(answers, [false], "one answer")
	_drop(screen)
	var pressed := RpgArcadeContinueScreen.new()
	Fixtures.tree().root.add_child(pressed)
	pressed.chosen.connect(func(go_on: bool) -> void: answers.append(go_on))
	(pressed.find_child("Continue", true, false) as Button).pressed.emit()
	t.eq(answers, [false, true])
	_drop(pressed)
	var table := RpgArcadeHighScoreTable.new()
	Fixtures.tree().root.add_child(table)
	var entries: Array[Dictionary] = [{"name": "ANA", "score": 900, "stage": 3}, {"name": "BO", "score": 200, "stage": 1}]
	t.eq(RpgArcadeHighScoreTable.lines(entries), [[" 1.", "ANA", "900", "Stage 3"], [" 2.", "BO", "200", "Stage 1"]])
	var names: Array = []
	table.closed.connect(func(n: String) -> void: names.append(n))
	table.show_table(entries, true, 500)
	var edit := table.find_child("Name", true, false) as LineEdit
	t.eq([edit.max_length, edit.text], [8, "AAA"])
	edit.text = "  kim  "
	table.close()
	t.eq(names, ["kim"])
	table.show_table([] as Array[Dictionary])
	t.ok(table.find_child("Empty", true, false) != null)
	table.close()
	t.eq(names, ["kim", ""], "no name was asked for")
	_drop(table)

# ---------------------------------------------------------------- the builder

func test_the_recipes_make_a_stage_scene_that_saves_and_loads(t) -> void:
	var stage := StageRecipes.build_stage(2, {"title": "Third", "axis": "right", "speed": 60, "length": 900,
		"exit": "reach_end", "par_time_s": 45, "music": "pack.music.stage"}, Vector2i(320, 180), Vector2(40, 90))
	t.ok(stage is RpgArcadeStage)
	var typed := stage as RpgArcadeStage
	t.eq([typed.name, typed.map_id, typed.stage_index, typed.title, typed.exit_condition, typed.par_time_s],
		[&"Stage03", &"stage_03", 2, "Third", "reach_end", 45.0])
	t.eq(typed.music_asset_id, "pack.music.stage")
	t.eq((typed.get_node("Camera") as Camera2D).position, Vector2(160, 90))
	var scroll := typed.get_node("Scroller") as RpgArcadeScroller
	t.eq([scroll.axis, scroll.speed, scroll.length], ["right", 60.0, 900.0])
	t.ok(typed.get_node("Entities") is Node2D)
	var packed := PackedScene.new()
	t.eq(packed.pack(typed), OK)
	var again := packed.instantiate() as RpgArcadeStage
	t.ok(again != null and again.get_node_or_null("Scroller") is RpgArcadeScroller, "every node is saved with the scene")
	t.eq(again.get_spawn(&"default").position, Vector2(40, 90))
	t.eq((again.get_node("Scroller") as RpgArcadeScroller).length, 900.0)
	again.free()
	typed.free()
	t.eq(ArcadeBuild.stage_path(0), "res://generated/scenes/stages/stage_01.tscn")
	var listed := StageRecipes.with_scenes([{"title": "A"}, {"title": "B", "scene": "old"}])
	t.eq(listed, [{"title": "A", "scene": ArcadeBuild.stage_path(0)}, {"title": "B", "scene": ArcadeBuild.stage_path(1)}])
	var sequence := RpgArcadeStageSequence.from_array(listed)
	t.eq([sequence.size(), sequence.index_of_scene(ArcadeBuild.stage_path(1)), sequence.index_of_scene("x")], [2, 1, -1])
	t.ok(not sequence.is_last() and sequence.advance() and sequence.is_last() and not sequence.advance())
	t.eq(RpgArcadeStageSequence.load_file("res://tests/no_such_stages.json").size(), 0, "no file is no stages")
	t.eq(RpgArcadeStageSequence.load_file("").size(), 0)
	var listed_path := "user://test_arcade_stages.json"
	var file := FileAccess.open(listed_path, FileAccess.WRITE)
	file.store_string(JSON.stringify({"stages": listed}))
	file.close()
	var mode := RpgArcadeMode.new()
	t.eq(mode.stages_path, "", "the runtime knows no path of the game; the recipe sets it")
	t.eq(mode.get_child_count(), 0, "a mode that is only made has no children: the saved scene holds none")
	mode.stages_path = listed_path
	t.eq([mode.stages().size(), mode.stages().scene_of(1)], [2, ArcadeBuild.stage_path(1)])
	mode.free()
	DirAccess.remove_absolute(listed_path)
	t.eq(ArcadeBuild.STAGES_PATH, "res://game/data/stages.json")
	var hud := HudRecipe.build_hud()
	t.ok(hud is RpgArcadeHud)
	hud.free()
	var box := ArcadeBuild.stand_in("Box", Vector2(10, 6), Color.RED)
	t.eq(box.polygon, PackedVector2Array([Vector2(-5, -3), Vector2(5, -3), Vector2(5, 3), Vector2(-5, 3)]))
	box.free()
	var recipe = HudRecipe.new()
	t.eq(recipe.outputs(null), PackedStringArray(["res://generated/scenes/ui/hud_arcade.tscn"]))

func test_every_text_of_the_framework_has_its_english(t) -> void:
	for key: String in ["ARC_LIVES", "ARC_SCORE", "ARC_STAGE_CLEAR", "ARC_GAME_OVER", "ARC_CONTINUE", "ARC_QUIT",
			"ARC_HIGH_SCORES", "ARC_NEW_HIGH_SCORE", "ARC_SAVED_BETWEEN_STAGES"]:
		t.ok(RpgArcadeStrings.KEYS.has(key), key)
		t.ok(RpgArcadeStrings.t(key) != key, key)
	t.eq(RpgArcadeStrings.t("ARC_STAGE", [4]), "Stage 4")
	t.eq(RpgArcadeStrings.t("ARC_MULTIPLIER", [3]), "x3")
