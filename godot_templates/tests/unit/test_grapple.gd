extends RefCounted
## T16.11: the grapple arm of a run and gun's soldier: the hook holds on a ceiling, the swing
## is the pendulum rpggen plans with, letting go keeps its speed, a hook straight above hoists
## the soldier on to a ledge, and a soldier that cannot jump does not.

const Fixtures := preload("../lib/fixtures.gd")
const PlatformTests := preload("test_platform_actor.gd")
const StageRecipes := preload("res://builder/recipes/arcade/stage_recipes.gd")
const SoldierRecipe := preload("res://builder/recipes/run_and_gun/soldier_recipe.gd")

const TILE := 16
const VIEW := Vector2i(320, 180)
const FLOOR_ROW := 9  # the top of the floor is at y = 144
const FLOOR_Y := FLOOR_ROW * TILE
## A block to swing from: its underside is at y = 64.
const BLOCK_ROW := 3
const BLOCK_COLS := [7, 8, 9, 10]
## A plank to be hoisted on to: its top is at y = 80.
const PLANK_ROW := 5
const PLANK_COLS := [2, 3]
## A thick ceiling to hang under.
const CEILING_COL := 14
## stage_plan.swing_period(64, 2 * 3.25 * 16 / 0.38 ** 2, pi / 4): tests/unit/test_stage_plan.py
## has the same number.
const PYTHON_PERIOD := 1.947866
const SWING_PX := 64.0
const SWING_RAD := PI / 4.0

class Field:
	var stage: RpgArcadeStage
	var soldier: RpgSoldier
	var rope: RpgGrapple

	func frames(count: int) -> void:
		for i in count:
			await Engine.get_main_loop().physics_frame

	## Steps until `check` is true; false when it never was.
	func until(check: Callable, count: int) -> bool:
		for i in count:
			if check.call():
				return true
			await Engine.get_main_loop().physics_frame
		return check.call()

	func stand_at(x: float) -> void:
		soldier.position = Vector2(x, FLOOR_Y)
		soldier.velocity = Vector2.ZERO
		soldier.move_x = 0.0
		soldier.move_y = 0.0
		await frames(4)

	func drop() -> void:
		if stage.get_parent() != null:
			stage.get_parent().remove_child(stage)
		stage.free()

## A flat stage with a block in the air, a plank and a thick ceiling, and a soldier with the
## grapple arm standing on its floor.
func _field() -> Field:
	await Fixtures.tree().process_frame
	var field := Field.new()
	var plan := {"axis": "right", "speed": 0.0, "length": 320.0, "exit": "custom", "waves": []}
	field.stage = StageRecipes.build_stage(0, plan, VIEW, Vector2(40, FLOOR_Y)) as RpgArcadeStage
	var ground := TileMapLayer.new()
	ground.name = "Ground"
	ground.tile_set = PlatformTests.tileset()
	for x in 60:
		for y in range(FLOOR_ROW, FLOOR_ROW + 3):
			ground.set_cell(Vector2i(x, y), 0, PlatformTests.GROUND)
	for x: int in BLOCK_COLS:
		ground.set_cell(Vector2i(x, BLOCK_ROW), 0, PlatformTests.GROUND)
	for x: int in PLANK_COLS:
		ground.set_cell(Vector2i(x, PLANK_ROW), 0, PlatformTests.ONE_WAY)
	for y in range(0, BLOCK_ROW + 1):
		ground.set_cell(Vector2i(CEILING_COL, y), 0, PlatformTests.GROUND)
	field.stage.add_child(ground)
	field.soldier = SoldierRecipe.build_soldier(null, Vector2i(16, 24), Vector2i(8, 23), VIEW, TILE, null, null, 1, false) as RpgSoldier
	field.rope = SoldierRecipe.add_grapple(field.soldier, TILE) as RpgGrapple
	field.soldier.input_node_enabled = false
	field.soldier.position = Vector2(40, FLOOR_Y)
	field.stage.add_child(field.soldier)
	Fixtures.tree().root.add_child(field.stage)
	field.stage.setup(plan)
	field.stage.begin()
	await field.frames(8)
	return field

## Fires the hook up and forward from `x` and waits until it holds.
func _hook_on_the_block(field: Field, x: float) -> bool:
	await field.stand_at(x)
	field.soldier.aim_locked = true
	field.soldier.move_x = 1.0
	field.soldier.move_y = -1.0
	await field.frames(2)
	field.soldier.press_grapple()
	var held := await field.until(func() -> bool: return field.rope.is_attached(), 30)
	field.soldier.aim_locked = false
	field.soldier.move_x = 0.0
	field.soldier.move_y = 0.0
	return held

# ---------------------------------------------------------------- the arithmetic

func test_the_swing_is_the_pendulum_rpggen_plans_with(t) -> void:
	var gravity := RpgPlatformMath.gravity(3.25 * TILE, 0.38)
	var formula := RpgPlatformMath.swing_period(SWING_PX, gravity, SWING_RAD)
	t.near(formula, PYTHON_PERIOD, 0.0001, "the formula is rpggen's")
	var stepped := RpgPlatformMath.simulate_swing(SWING_PX, gravity, SWING_RAD, 1.0 / 60.0)
	t.ok(absf(stepped - PYTHON_PERIOD) <= PYTHON_PERIOD * 0.01, "stepped at 60 Hz the period is within 1 %% (%f, %f)" % [stepped, PYTHON_PERIOD])
	var slow := RpgPlatformMath.simulate_swing(SWING_PX, gravity, SWING_RAD, 1.0 / 30.0)
	t.ok(absf(slow - PYTHON_PERIOD) <= PYTHON_PERIOD * 0.01, "and at 30 Hz (%f)" % slow)
	t.ok(formula > TAU * sqrt(SWING_PX / gravity), "a wide swing takes longer than a small one")
	# a swing let go at rest comes back to where it began: the step keeps its energy
	var state := Vector2(SWING_RAD, 0.0)
	var widest := 0.0
	for i in 600:
		state = RpgPlatformMath.swing_step(state.x, state.y, SWING_PX, gravity, 1.0 / 60.0)
		widest = maxf(widest, absf(state.x))
	t.near(widest, SWING_RAD, 0.01, "ten seconds of swinging do not widen it")
	t.near(RpgPlatformMath.swing_speed(SWING_PX, gravity, PI / 2.0), sqrt(2.0 * gravity * SWING_PX), 0.01)
	t.eq(RpgPlatformMath.swing_step(1.0, 2.0, 0.0, gravity, 0.1), Vector2(1.0, 0.0), "no rope, no swing")

func test_the_hook_is_fired_up_the_upper_diagonals_and_forward(t) -> void:
	t.eq(RpgGrapple.direction(Vector2.UP, 1), Vector2.UP)
	t.eq(RpgGrapple.direction(Vector2.RIGHT, 1), Vector2.RIGHT)
	t.eq(RpgGrapple.direction(Vector2.LEFT, -1), Vector2.LEFT)
	t.near(RpgGrapple.direction(Vector2(1, -1).normalized(), 1).angle(), -PI / 4.0, 0.001)
	t.near(RpgGrapple.direction(Vector2(-1, -1).normalized(), -1).angle(), -PI * 0.75, 0.001)
	t.eq(RpgGrapple.direction(Vector2.DOWN, -1), Vector2.LEFT, "an aim downward fires forward")
	t.eq(RpgGrapple.direction(Vector2(1, 1).normalized(), 1), Vector2.RIGHT)

# ---------------------------------------------------------------- the hook

func test_the_hook_holds_on_a_ceiling_and_swings_the_soldier(t) -> void:
	var field := await _field()
	var soldier := field.soldier
	var rope := field.rope
	t.ok(soldier.grapple() == rope and rope.is_idle(), "the soldier has its arm")
	var fired := [0]
	var hooked: Array[Vector2] = []
	soldier.grapple_fired.connect(func() -> void: fired[0] += 1)
	soldier.grapple_hooked.connect(func(at: Vector2) -> void: hooked.append(at))
	t.ok(await _hook_on_the_block(field, 68.0), "a hook fired up and forward holds on the block")
	t.eq(fired[0], 1)
	t.eq(hooked.size(), 1)
	t.eq(rope.state, RpgGrapple.State.SWING, "a hook that holds to the side is a swing")
	t.near(rope.anchor.y, (BLOCK_ROW + 1) * TILE, 4.5, "it holds on the underside of the block")
	t.ok(rope.anchor.x >= BLOCK_COLS[0] * TILE and rope.anchor.x <= (BLOCK_COLS[-1] + 1) * TILE, "under the block (%f)" % rope.anchor.x)
	var whole := (soldier.position + soldier.hand()).distance_to(rope.anchor)
	t.ok(rope.swing_length < whole, "the swing's rope is shorter than the way to the hook")
	var far := await field.until(func() -> bool: return soldier.position.x > rope.anchor.x + TILE, 240)
	t.ok(far, "the swing carries the soldier past the hook (at %s)" % soldier.position)
	t.ok(soldier.position.y < FLOOR_Y - 4.0, "off the ground")
	t.near((soldier.position + soldier.hand()).distance_to(rope.anchor), rope.swing_length, 1.0, "at the end of the rope")
	t.ok(not soldier.dead)
	# the button again lets go
	soldier.press_grapple()
	await field.frames(2)
	t.ok(rope.is_idle(), "the button again lets go")
	t.ok(await field.until(func() -> bool: return soldier.is_on_floor(), 240), "and the soldier comes down")
	field.drop()

func test_letting_go_keeps_the_speed_of_the_swing(t) -> void:
	var field := await _field()
	var soldier := field.soldier
	var rope := field.rope
	t.ok(await _hook_on_the_block(field, 68.0))
	# at the lowest point the swing is at its fastest, and goes to the right
	var low := await field.until(func() -> bool: return rope.angle >= 0.0 and rope.omega > 0.0 and is_equal_approx(rope.length, rope.swing_length), 240)
	t.ok(low, "the swing comes through its lowest point")
	var speed := rope.swing_velocity()
	t.ok(speed.x > TILE * 2.0, "fast, to the right (%s)" % speed)
	t.near(speed.length(), absf(rope.omega) * rope.length, 0.01)
	var at := soldier.position.x
	soldier.release_grapple()
	t.ok(rope.is_idle())
	t.eq(soldier.velocity, speed, "the soldier has the speed of the swing")
	await field.frames(6)
	t.near(soldier.velocity.x, speed.x, 0.5, "nothing held, and the speed stays")
	t.ok(soldier.position.x > at + speed.x * 0.08, "the soldier flies on")
	t.ok(await field.until(func() -> bool: return soldier.is_on_floor(), 240), "until it lands")
	await field.frames(3)
	t.near(soldier.velocity.x, 0.0, 0.5, "on the ground it stands again")
	# jump lets go too
	t.ok(await _hook_on_the_block(field, 68.0))
	await field.frames(10)
	soldier.press_jump()
	t.ok(rope.is_idle(), "jump lets go of the rope")
	t.ok(soldier.velocity.y >= -absf(rope.omega) * rope.length - 200.0, "and is no jump")
	# a soldier that dies lets go
	t.ok(await _hook_on_the_block(field, 68.0), "the hook holds again")
	soldier.die()
	t.ok(rope.is_idle(), "death lets go of the rope")
	field.drop()

func test_a_hook_straight_above_hoists_the_soldier_on_to_the_ledge(t) -> void:
	var field := await _field()
	var soldier := field.soldier
	var rope := field.rope
	await field.stand_at(44.0)
	var done := [false]
	rope.hoisted.connect(func() -> void: done[0] = true)
	soldier.move_y = -1.0
	await field.frames(2)
	t.eq(soldier.aim, Vector2.UP)
	soldier.press_grapple()
	await field.frames(1)
	soldier.move_y = 0.0
	t.ok(await field.until(func() -> bool: return rope.state == RpgGrapple.State.HOIST or done[0], 30), "a hook that holds straight above hoists")
	t.ok(await field.until(func() -> bool: return done[0], 120), "the soldier climbs the rope")
	t.ok(rope.is_idle(), "and lets go on the ledge")
	await field.frames(6)
	t.near(soldier.position.y, PLANK_ROW * TILE, 1.0, "it stands on the plank")
	t.ok(soldier.is_on_floor(), "on its feet")
	t.ok(soldier.position.x >= PLANK_COLS[0] * TILE and soldier.position.x <= (PLANK_COLS[-1] + 1) * TILE)
	# under a thick ceiling there is nowhere to stand: the soldier hangs until it lets go
	await field.stand_at(CEILING_COL * TILE + 8.0)
	soldier.move_y = -1.0
	await field.frames(2)
	soldier.press_grapple()
	await field.frames(1)
	soldier.move_y = 0.0
	t.ok(await field.until(func() -> bool: return rope.state == RpgGrapple.State.HANG, 120), "under a ceiling the soldier hangs")
	var hung := soldier.position.y
	t.ok(hung < FLOOR_Y - TILE, "up at the ceiling (%f)" % hung)
	await field.frames(20)
	t.near(soldier.position.y, hung, 0.5, "and stays there")
	soldier.press_grapple()
	await field.frames(2)
	t.ok(rope.is_idle())
	t.ok(await field.until(func() -> bool: return soldier.is_on_floor(), 240))
	t.near(soldier.position.y, FLOOR_Y, 1.0, "let go, it falls back to the floor")
	field.drop()

func test_a_hook_that_finds_nothing_comes_back(t) -> void:
	var field := await _field()
	var soldier := field.soldier
	var rope := field.rope
	var missed := [0]
	rope.missed.connect(func() -> void: missed[0] += 1)
	# only tiles that say so, with `tagged_only`: the plank does not
	rope.tagged_only = true
	await field.stand_at(44.0)
	soldier.move_y = -1.0
	await field.frames(2)
	soldier.press_grapple()
	await field.frames(1)
	soldier.move_y = 0.0
	await field.frames(30)
	t.ok(rope.is_idle() and missed[0] == 1, "a tile without the `grapple` data does not hold the hook (state %d, %d missed)" % [rope.state, missed[0]])
	rope.tagged_only = false
	await field.stand_at(300.0)
	soldier.move_y = -1.0
	await field.frames(2)
	soldier.press_grapple()
	await field.frames(1)
	t.ok(rope.is_flying(), "the hook is in the air")
	var highest := [soldier.position.y]
	t.ok(await field.until(func() -> bool:
		highest[0] = minf(highest[0], rope.hook.y)
		return rope.is_idle(), 60), "its reach ends")
	t.eq(missed[0], 2)
	t.ok(soldier.position.y + soldier.hand().y - highest[0] <= rope.reach_px() + 1.0, "no further than its reach")
	t.near(soldier.position.y, FLOOR_Y, 1.0, "the soldier stands where it stood")
	field.drop()

func test_a_soldier_that_cannot_jump_does_not(t) -> void:
	var field := await _field()
	var soldier := field.soldier
	# down with jump still drops through a plank
	soldier.can_jump = false
	soldier.position = Vector2(44.0, PLANK_ROW * TILE - 2.0)
	await field.frames(6)
	t.ok(soldier.is_on_floor() and soldier.standing_on_one_way(), "on the plank (at %s)" % soldier.position)
	soldier.move_y = 1.0
	soldier.press_jump()
	await field.frames(30)
	soldier.move_y = 0.0
	t.ok(soldier.position.y > PLANK_ROW * TILE + 4.0, "down with jump drops through it")
	await field.stand_at(200.0)
	soldier.press_jump()
	soldier.jump_held = true
	await field.frames(12)
	t.near(soldier.position.y, FLOOR_Y, 0.5, "the jump button does nothing")
	t.ok(soldier.is_on_floor())
	soldier.jump_held = false
	soldier.can_jump = true
	await field.stand_at(200.0)
	soldier.press_jump()
	await field.frames(12)
	t.ok(soldier.position.y < FLOOR_Y - TILE, "a soldier that can jump does")
	field.drop()
