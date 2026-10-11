extends RefCounted
## T16.08: the soldier of a run and gun on the platform actor: eight aims, the gun, the crouch,
## a hit and the drop back in, the camera that never goes back, the grenade, and the scenes the
## recipes build.

const Fixtures := preload("../lib/fixtures.gd")
const PlatformTests := preload("test_platform_actor.gd")
const StageRecipes := preload("res://builder/recipes/arcade/stage_recipes.gd")
const HudRecipe := preload("res://builder/recipes/arcade/hud_recipe.gd")
const SoldierRecipe := preload("res://builder/recipes/run_and_gun/soldier_recipe.gd")
const StageRecipe := preload("res://builder/recipes/run_and_gun/stage_recipe.gd")
const RngBuild := preload("res://builder/recipes/run_and_gun/run_and_gun_build.gd")

const TILE := 16
const VIEW := Vector2i(320, 180)
const FLOOR_ROW := 9  # the top of the floor is at y = 144
const PLAYER := RpgArcadeBulletPool.Team.PLAYER

## Something a bullet or a blast can hit.
class Target extends Node2D:
	var hit_radius := 6.0
	var taken := 0

	func _ready() -> void:
		add_to_group(RpgArcadeBulletPool.TARGET_GROUP)

	func take_hit(damage: int) -> void:
		taken += damage

class Field:
	var stage: RpgArcadeStage
	var soldier: RpgSoldier
	var pool: RpgArcadeBulletPool

	func frames(count: int) -> void:
		for i in count:
			await Engine.get_main_loop().physics_frame

	func drop() -> void:
		if stage.get_parent() != null:
			stage.get_parent().remove_child(stage)
		stage.free()

## A stage two screens long with a flat floor, the bullet pool and the soldier standing on it.
func _field(health: int = 1, left_edge_kills: bool = true) -> Field:
	await Fixtures.tree().process_frame
	var field := Field.new()
	var plan := {"axis": "right", "speed": 0.0, "length": 320.0, "exit": "custom", "waves": []}
	field.stage = StageRecipes.build_stage(0, plan, VIEW, Vector2(40, FLOOR_ROW * TILE)) as RpgArcadeStage
	var ground := TileMapLayer.new()
	ground.name = "Ground"
	ground.tile_set = PlatformTests.tileset()
	for x in 60:
		for y in range(FLOOR_ROW, FLOOR_ROW + 3):
			ground.set_cell(Vector2i(x, y), 0, PlatformTests.GROUND)
	field.stage.add_child(ground)
	field.pool = RpgArcadeBulletPool.new()
	field.pool.name = "Bullets"
	field.pool.wall_mask = 1
	field.pool.view_size = Vector2(VIEW)
	field.stage.add_child(field.pool)
	var grenade := PackedScene.new()
	var made := SoldierRecipe.build_grenade(TILE, null)
	grenade.pack(made)
	made.free()
	field.soldier = SoldierRecipe.build_soldier(null, Vector2i(16, 24), Vector2i(8, 23), VIEW, TILE, null, grenade, health, left_edge_kills) as RpgSoldier
	field.soldier.input_node_enabled = false
	field.soldier.position = Vector2(40, FLOOR_ROW * TILE)
	field.stage.add_child(field.soldier)
	Fixtures.tree().root.add_child(field.stage)
	field.stage.setup(plan)
	field.stage.begin()
	await field.frames(8)
	return field

# ---------------------------------------------------------------- the aim and the gun

func test_the_stick_gives_eight_aims_and_down_only_in_the_air(t) -> void:
	t.eq(RpgGunAim.direction(Vector2.ZERO, 1, true), Vector2.RIGHT, "nothing held: forward")
	t.eq(RpgGunAim.direction(Vector2.ZERO, -1, true), Vector2.LEFT)
	t.eq(RpgGunAim.direction(Vector2(0, -1), 1, true), Vector2.UP)
	t.eq(RpgGunAim.direction(Vector2(1, -1), 1, true), Vector2(1, -1).normalized())
	t.eq(RpgGunAim.direction(Vector2(-1, -1), 1, true), Vector2(-1, -1).normalized(), "the stick wins over the facing")
	t.eq(RpgGunAim.direction(Vector2(1, 1), 1, true), Vector2(1, 1).normalized(), "down and forward, also on the ground")
	t.eq(RpgGunAim.direction(Vector2(0, 1), 1, true), Vector2.RIGHT, "down on the ground is no aim")
	t.eq(RpgGunAim.direction(Vector2(0, 1), 1, false), Vector2.DOWN, "in the air it is")
	t.eq(RpgGunAim.direction(Vector2(0, -1), -1, true, true), Vector2.LEFT, "a crouched soldier aims forward")
	t.eq(RpgGunAim.direction(Vector2(0.2, -0.2), 1, true), Vector2.RIGHT, "a stick that is barely moved is nothing held")
	var eight := RpgGunAim.all()
	t.eq(eight.size(), 8)
	var names := {}
	for aim in eight:
		t.near(aim.length(), 1.0, 0.0001)
		names[RpgGunAim.name_of(aim)] = true
	t.eq(names.keys().size(), 5, "up, up_forward, forward, down_forward, down: the same to both sides")
	t.eq([RpgGunAim.name_of(Vector2.UP), RpgGunAim.name_of(Vector2(-1, -1).normalized()), RpgGunAim.name_of(Vector2.LEFT)], ["up", "up_forward", "forward"])
	t.eq(RpgSoldier.aim_animation("up"), ["aim_up", "shoot"] as Array[String])
	t.eq(RpgSoldier.aim_animation("down_forward"), ["aim_diagonal", "shoot"] as Array[String])

func test_eight_aims_give_eight_bullet_angles(t) -> void:
	await Fixtures.tree().process_frame
	var pool := RpgArcadeBulletPool.new()
	pool.auto_advance = false
	Fixtures.tree().root.add_child(pool)
	var gun := RpgGun.new()
	gun.bullet_speed = 100.0
	var angles := {}
	for aim in RpgGunAim.all():
		pool.clear(PLAYER)
		t.eq(gun.shoot(pool, Vector2.ZERO, aim), 1)
		pool.advance(1.0, Rect2())
		var at := pool.positions(PLAYER)[0]
		t.near(at.distance_to(aim * 100.0), 0.0, 0.001)
		angles[snappedf(rad_to_deg(at.angle()), 0.01)] = true
	t.eq(angles.size(), 8)
	var sorted: Array = angles.keys()
	sorted.sort()
	t.eq(sorted, [-135.0, -90.0, -45.0, 0.0, 45.0, 90.0, 135.0, 180.0], "every forty-five degrees")
	# the rate, a shot of several bullets, and the range
	pool.clear(PLAYER)
	gun.rate = 4.0
	t.eq(gun.advance(0.125, false, pool, Vector2.ZERO, Vector2.RIGHT), 0)
	t.eq(gun.advance(0.125, true, pool, Vector2.ZERO, Vector2.RIGHT), 1, "the first shot at once")
	t.eq(gun.advance(0.125, true, pool, Vector2.ZERO, Vector2.RIGHT), 0)
	t.eq(gun.advance(0.125, true, pool, Vector2.ZERO, Vector2.RIGHT), 1, "four a second")
	pool.clear(PLAYER)
	gun.bullets_per_shot = 5
	gun.spread_deg = 40.0
	var fan := gun.volley(Vector2.RIGHT)
	t.eq(fan.size(), 5)
	t.near(rad_to_deg(fan[0].angle_to(fan[4])), 40.0, 0.001)
	gun.bullets_per_shot = 1
	gun.range_px = 50.0
	gun.shoot(pool, Vector2.ZERO, Vector2.RIGHT)
	pool.advance(0.25, Rect2())
	t.eq(pool.active(PLAYER), 1, "25 px on")
	pool.advance(0.25, Rect2())
	t.eq(pool.active(PLAYER), 0, "a bullet is gone at the end of its range")
	gun.free()
	pool.get_parent().remove_child(pool)
	pool.free()

# ---------------------------------------------------------------- the soldier

func test_the_soldier_runs_jumps_and_fires_along_its_aim(t) -> void:
	var field: Field = await _field()
	var soldier := field.soldier
	t.ok(soldier.is_on_floor(), "it stands on the floor of the stage")
	t.near(soldier.position.y, FLOOR_ROW * TILE, 0.5)
	soldier.move_x = 1.0
	await field.frames(30)
	t.ok(soldier.position.x > 80.0 and soldier.facing == 1, "half a second of running")
	soldier.move_x = 0.0
	soldier.shooting = true
	await field.frames(6)
	t.eq(soldier.aim, Vector2.RIGHT)
	t.ok(field.pool.active(PLAYER) >= 1, "it fires")
	for at in field.pool.positions(PLAYER):
		t.ok(at.x > soldier.position.x and at.y < soldier.position.y, "ahead of it, at the height of the gun")
	t.ok((soldier.get_node("Muzzle") as Node2D).position.x > 0.0, "the flash is where the shot goes")
	field.pool.clear(PLAYER)
	soldier.move_y = -1.0
	await field.frames(12)
	t.eq(soldier.aim, Vector2.UP)
	for at in field.pool.positions(PLAYER):
		t.near(at.x, soldier.position.x, 0.01, "straight up")
		t.ok(at.y < soldier.position.y - 15.0, "above its head: %s" % at)
	t.near((soldier.get_node("Muzzle") as Node2D).rotation, -PI * 0.5, 0.0001)
	# a bullet that is fired into the ground stops there
	field.pool.clear(PLAYER)
	soldier.shooting = false
	soldier.move_y = 0.0
	field.pool.fire(PLAYER, soldier.position + Vector2(0, -8), Vector2.DOWN * 200.0)
	await field.frames(6)
	t.eq(field.pool.active(PLAYER), 0, "the ground stops bullets")
	# a held jump, and down only in the air
	soldier.press_jump()
	soldier.jump_held = true
	var top := soldier.position.y
	soldier.move_y = 1.0
	var aimed_down := false
	for i in 50:
		await Fixtures.tree().physics_frame
		top = minf(top, soldier.position.y)
		if not soldier.is_on_floor() and soldier.aim == Vector2.DOWN:
			aimed_down = true
	t.ok(FLOOR_ROW * TILE - top > TILE * 2.5, "a full jump is more than two and a half tiles")
	t.ok(aimed_down, "in the air, down is an aim")
	soldier.move_y = 0.0
	soldier.jump_held = false
	await field.frames(40)
	t.ok(soldier.is_on_floor(), "it lands again")
	field.drop()

func test_a_crouch_lowers_what_can_be_hit_and_holds_the_soldier(t) -> void:
	var field: Field = await _field()
	var soldier := field.soldier
	var high := soldier.hit_center()
	var tall := soldier.hit_radius
	var at := soldier.position.x
	soldier.move_y = 1.0
	soldier.move_x = 0.0
	await field.frames(4)
	t.ok(soldier.crouching)
	t.ok(soldier.hit_center().y > high.y + 3.0, "the middle of what can be hit is lower")
	t.ok(soldier.hit_radius < tall * 0.6, "and smaller")
	t.eq(soldier.aim, Vector2.RIGHT, "it fires forward")
	t.near(soldier.position.x, at, 0.01, "and stays where it is")
	# a bullet at the height of a standing soldier's chest passes over a crouched one
	field.pool.fire(RpgArcadeBulletPool.Team.ENEMY, Vector2(high.x + 60.0, high.y - 2.0), Vector2.LEFT * 240.0)
	await field.frames(30)
	t.ok(not soldier.dead, "it ducked under the bullet")
	soldier.move_y = 0.0
	await field.frames(3)
	t.ok(not soldier.crouching)
	field.pool.fire(RpgArcadeBulletPool.Team.ENEMY, Vector2(high.x + 60.0, high.y - 2.0), Vector2.LEFT * 240.0)
	await field.frames(30)
	t.ok(soldier.dead, "standing, the same bullet hits")
	# holding the aim: the soldier does not walk, and aims
	var other: Field = await _field()
	other.soldier.aim_locked = true
	other.soldier.move_x = 1.0
	other.soldier.move_y = -1.0
	var from := other.soldier.position.x
	await other.frames(20)
	t.near(other.soldier.position.x, from, 0.01, "aim lock holds it in place")
	t.eq(other.soldier.aim, Vector2(1, -1).normalized())
	other.drop()
	field.drop()

func test_a_hit_with_one_health_is_a_death_and_the_soldier_drops_back_in(t) -> void:
	Fixtures.install_state()
	var field: Field = await _field()
	var soldier := field.soldier
	var mode := RpgRunAndGunMode.new()
	mode.auto_screens = true
	mode.sequence = RpgArcadeStageSequence.from_array([{"exit": "custom", "waves": []}])
	Fixtures.tree().root.add_child(mode)
	var events: Array = []
	soldier.destroyed.connect(func() -> void: events.append("destroyed"))
	soldier.respawned.connect(func() -> void: events.append("respawned"))
	mode.bind_stage(field.stage)
	t.ok(mode.soldier == soldier, "the mode found the soldier of the stage")
	t.eq([soldier.max_health, soldier.health], [1, 1])
	t.ok(soldier.hit())
	await Fixtures.tree().process_frame
	t.eq(events, ["destroyed", "respawned"], "one hit is a death; the mode brings the soldier back")
	t.eq(mode.lives.count, 2)
	t.ok(not soldier.dead and soldier.is_invulnerable() and soldier.health == 1)
	t.near(soldier.position.y, soldier.body_height(), 3.0, "at the top of the screen")
	t.near(soldier.position.x, 160.0 - 80.0, 0.01, "a quarter of the screen in from its middle")
	t.ok(not soldier.hit(), "nothing hits it while it blinks")
	await field.frames(60)
	t.ok(soldier.is_on_floor(), "it has dropped to the floor")
	await field.frames(70)
	t.ok(not soldier.is_invulnerable(), "two seconds")
	# a fall out of the stage is a death too
	soldier.position = Vector2(100, 400)
	await field.frames(3)
	t.eq(mode.lives.count, 1, "below the stage")
	mode.get_parent().remove_child(mode)
	mode.free()
	field.drop()
	# a soldier with more health takes hits before it dies
	var tough: Field = await _field(3)
	var hits: Array = []
	tough.soldier.was_hit.connect(func(left: int) -> void: hits.append(left))
	t.ok(tough.soldier.hit())
	t.ok(not tough.soldier.dead and tough.soldier.is_invulnerable())
	t.ok(not tough.soldier.hit(), "safe for a moment after a hit")
	await tough.frames(70)
	tough.soldier.hit()
	await tough.frames(70)
	tough.soldier.hit()
	t.eq(hits, [2, 1, 0])
	t.ok(tough.soldier.dead, "the third hit")
	tough.drop()
	Fixtures.uninstall_state()

func test_the_camera_follows_to_the_right_and_never_goes_back(t) -> void:
	var field: Field = await _field(1, false)
	var soldier := field.soldier
	var scroll := field.stage.scroller()
	var camera := field.stage.get_node("Camera") as Camera2D
	t.eq([scroll.progress, camera.position], [0.0, Vector2(160, 90)], "at the start the soldier is behind the leash")
	soldier.move_x = 1.0
	await field.frames(60)
	var reached := scroll.progress
	t.ok(reached > 20.0, "the camera follows")
	t.near(camera.position.x, 160.0 + reached, 0.01)
	t.near(soldier.position.x - (camera.position.x - 160.0), 320.0 * 0.4, 1.0, "the soldier is kept at two fifths of the screen")
	soldier.move_x = -1.0
	await field.frames(40)
	t.eq(scroll.progress, reached, "it never goes back")
	t.ok(soldier.position.x < 160.0 + reached - 20.0, "though the soldier does")
	# the left edge is a wall here: the soldier cannot leave the screen
	await field.frames(200)
	t.near(soldier.position.x, reached + soldier.body_width() * 0.5, 0.5, "stopped at the left edge")
	t.ok(not soldier.dead)
	# it stops at the end of the stage, and a holder stops it too
	soldier.move_x = 0.0
	scroll.hold(self)
	t.eq(scroll.follow(reached + 50.0), 0.0, "held: a wave that has to be cleared")
	scroll.release(self)
	t.eq(scroll.follow(9999.0), 320.0 - reached, "to the end and no further")
	t.ok(scroll.at_end())
	field.drop()
	# where the left edge kills
	var deadly: Field = await _field(1, true)
	deadly.soldier.move_x = 1.0
	await deadly.frames(60)
	deadly.soldier.move_x = -1.0
	await deadly.frames(240)
	t.ok(deadly.soldier.dead, "the left edge of the screen kills")
	deadly.drop()

func test_a_grenade_flies_an_arc_and_its_blast_hits_what_is_in_its_radius(t) -> void:
	var field: Field = await _field()
	var soldier := field.soldier
	var near := Target.new()
	near.position = Vector2(125, FLOOR_ROW * TILE - 10)
	field.stage.add_child(near)
	var far := Target.new()
	far.position = Vector2(300, FLOOR_ROW * TILE - 10)
	field.stage.add_child(far)
	t.eq(soldier.grenades, 3)
	var thrown: Array[Node2D] = []
	soldier.grenade_thrown.connect(func(g: Node2D) -> void: thrown.append(g))
	soldier.press_grenade()
	await field.frames(2)
	t.eq([soldier.grenades, thrown.size()], [2, 1])
	var grenade := thrown[0] as RpgGrenade
	t.eq(grenade.velocity.x, 7.0 * TILE, "forward at seven tiles a second")
	t.ok(grenade.velocity.y < -6.0 * TILE, "and up")
	t.eq(grenade.blast_radius, 40.0)
	var blasts: Array = []
	grenade.exploded.connect(func(hit: int) -> void: blasts.append(hit))
	var top := grenade.position.y
	for i in 120:
		if not blasts.is_empty():
			break
		top = minf(top, grenade.position.y)
		await Fixtures.tree().physics_frame
	t.ok(top < soldier.position.y - 20.0, "it rose before it fell (to %.1f)" % top)
	t.eq(blasts, [1], "one target in the blast")
	t.eq([near.taken, far.taken], [5, 0], "what is in the radius is hurt, what is far is not")
	# the blast alone: a target's own size counts
	var loose := SoldierRecipe.build_grenade(TILE, null) as RpgGrenade
	loose.auto_advance = false
	loose.position = Vector2(300 - 44, FLOOR_ROW * TILE - 10)
	field.stage.add_child(loose)
	t.eq(loose.targets_at(loose.global_position).size(), 1, "44 px away: 40 of blast and 6 of target")
	loose.position.x -= 4.0
	t.eq(loose.targets_at(loose.global_position).size(), 0)
	loose.fuse_s = 0.1
	loose.gravity = 0.0
	loose.advance(0.2)
	t.ok(loose.is_queued_for_deletion(), "the fuse runs out")
	soldier.grenades = 0
	t.ok(not soldier.throw_grenade(), "none left")
	t.ok(soldier.add_grenade() and soldier.grenades == 1)
	soldier.grenades = soldier.max_grenades
	t.ok(not soldier.add_grenade())
	field.drop()

# ---------------------------------------------------------------- the recipes and the HUD

func test_the_recipes_build_the_soldier_and_the_floor_of_a_stage(t) -> void:
	var soldier := SoldierRecipe.build_soldier(null, Vector2i(16, 24), Vector2i(8, 23), VIEW, TILE, null, null, 3, false)
	t.ok(soldier is RpgSoldier)
	var typed := soldier as RpgSoldier
	t.eq([typed.max_health, typed.left_edge_kills, typed.view, typed.tile_size], [3, false, Vector2(320, 180), 16.0])
	t.ok(typed.get_collision_layer_value(2) and typed.get_collision_mask_value(1) and typed.get_collision_mask_value(11), "the layers")
	t.ok(typed.gun() != null and typed.get_node_or_null("Input") is RpgSoldierInput and typed.get_node_or_null("Muzzle") is Polygon2D, "gun, input, flash")
	t.eq(typed.gun().bullet_speed, 240.0)
	t.ok(typed.get_node_or_null("Body") is CollisionShape2D and typed.get_node_or_null("Visual") != null, "the platform body")
	var packed := PackedScene.new()
	t.eq(packed.pack(typed), OK)
	var again := packed.instantiate()
	t.ok(again.get_node_or_null("Gun") is RpgGun and again.get_node_or_null("Input") != null, "its parts are saved with it")
	again.free()
	typed.free()
	t.eq(StageRecipe.stage_cells(1920.0, Vector2i(640, 360), 16), Vector2i(160, 23), "the stage and one more screen wide, the screen high")
	t.eq(StageRecipe.floor_row(23), 20)
	var layer := TileMapLayer.new()
	layer.tile_set = PlatformTests.tileset()
	var kit := {"top": {"source_id": 0, "coords": PlatformTests.GROUND}, "fill": {}}
	StageRecipe.paint_floor(layer, Vector2i(10, 23), kit)
	t.eq(layer.get_used_rect(), Rect2i(0, 20, 10, 3), "three rows of ground over the whole width")
	layer.free()
	t.eq(RngBuild.SOLDIER_PATH, "res://generated/scenes/run_and_gun/soldier.tscn")
	t.eq(HudRecipe.script_for("run_and_gun"), "res://addons/rpg_runtime/archetypes/run_and_gun/ui/run_and_gun_hud.gd")

func test_the_hud_has_the_grenades_and_the_health_of_a_forgiving_soldier(t) -> void:
	await Fixtures.tree().process_frame
	var hud := HudRecipe.build_hud(HudRecipe.script_for("run_and_gun")) as RpgRunAndGunHud
	t.ok(hud != null)
	Fixtures.tree().root.add_child(hud)
	hud.set_process(false)
	var soldier := SoldierRecipe.build_soldier(null, Vector2i(16, 24), Vector2i(8, 23), VIEW, TILE, null, null) as RpgSoldier
	hud.show_soldier(soldier)
	t.eq([hud.row_text("grenades"), hud.row_text("health")], ["Grenades: 3", ""], "one hit is a death: no health to show")
	soldier.max_health = 3
	soldier.health = 2
	soldier.grenades = 1
	hud.show_soldier(soldier)
	t.eq([hud.row_text("grenades"), hud.row_text("health")], ["Grenades: 1", "Health: 2"])
	hud.show_soldier(null)
	t.eq(hud.row_text("grenades"), "")
	soldier.free()
	hud.get_parent().remove_child(hud)
	hud.free()
