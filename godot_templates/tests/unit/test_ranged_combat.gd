extends RefCounted
## Projectiles and enemy kinds of the action RPG (T12.67, T12.68): a shot's layers, flight, range,
## damage and walls; the shooter's and the charger's phases; how a kind is chosen; the player's
## ranged weapon.

const Fixtures := preload("../lib/fixtures.gd")
const EnemyRecipes := preload("res://builder/recipes/arpg/enemy_recipes.gd")

## An actor with Stats, Health, Hurtbox and AttackHitbox, not in the tree (as in test_arpg_runtime).
func _fighter(team: String, attack: int, defense: int, hp: int) -> RpgActor:
	var actor := RpgActor.new()
	actor.name = "Fighter"
	var components := Node.new()
	components.name = "Components"
	actor.add_child(components)
	var movement := RpgMovement.new()
	movement.name = "Movement"
	components.add_child(movement)
	var stats_node := RpgStatsComponent.new()
	stats_node.name = "Stats"
	var stats := RpgStats.new()
	stats.attack = attack
	stats.defense = defense
	stats.max_hp = hp
	stats.hp = hp
	stats.extra = {"crit_chance": 0.0}
	stats_node.stats = stats
	components.add_child(stats_node)
	var health := RpgHealth.new()
	health.name = "Health"
	actor.add_child(health)
	var hurtbox := RpgHurtbox.new()
	hurtbox.name = "Hurtbox"
	hurtbox.team = StringName(team)
	actor.add_child(hurtbox)
	var hitbox := RpgHitbox.new()
	hitbox.name = "AttackHitbox"
	hitbox.team = StringName(team)
	actor.add_child(hitbox)
	actor._cache_components()
	return actor

func _health(actor: Node) -> RpgHealth:
	return actor.get_node("Health") as RpgHealth

# ---------------------------------------------------------------- the projectile

func test_a_shot_takes_its_teams_layers_and_the_shooters_attack(t) -> void:
	var shooter := _fighter("enemy", 9, 0, 10)
	var shot := RpgProjectile.create(shooter, Vector2(10, 20), Vector2(0, -3), &"enemy", 100.0, 50.0)
	t.ok(shot.get_collision_layer_value(8) and shot.get_collision_mask_value(9), "an enemy shot is an enemy hitbox")
	t.ok(shot.get_collision_mask_value(1), "walls stop it")
	t.ok(not shot.get_collision_mask_value(10), "it never hurts enemies")
	t.eq(shot.attack, 9)
	t.eq(shot.velocity, Vector2(0, -100))
	t.near(shot.rotation, -PI / 2.0)
	t.eq(shot.position, Vector2(10, 20))
	var arrow := RpgProjectile.create(shooter, Vector2.ZERO, Vector2.RIGHT, &"player", 50.0, 50.0, "arrow")
	t.ok(arrow.get_collision_layer_value(7) and arrow.get_collision_mask_value(10))
	shot.free()
	arrow.free()
	shooter.free()

func test_a_shot_flies_its_range_and_is_done(t) -> void:
	var shot := RpgProjectile.create(null, Vector2.ZERO, Vector2.RIGHT, &"enemy", 60.0, 30.0)
	for i in 29:
		shot.advance(1.0 / 60.0)
	t.ok(not shot.done, "29 px flown")
	t.near(shot.position.x, 29.0, 0.01)
	shot.advance(1.0 / 60.0)
	t.ok(shot.done, "gone after its 30 px")
	t.eq(shot.velocity, Vector2.ZERO)
	shot.free()

func test_a_shot_hurts_the_other_team_once_and_stops(t) -> void:
	var state := Fixtures.install_state()
	var shooter := _fighter("enemy", 10, 0, 10)
	var target := _fighter("player", 1, 4, 30)
	var friend := _fighter("enemy", 1, 0, 30)
	var shot := RpgProjectile.create(shooter, Vector2.ZERO, Vector2.RIGHT, &"enemy", 100.0, 100.0)
	t.ok(not shot.hit(friend.get_node("Hurtbox") as RpgHurtbox), "its own team is ignored")
	t.ok(not shot.done)
	t.ok(shot.hit(target.get_node("Hurtbox") as RpgHurtbox))
	t.eq(_health(target).hp(), 30 - 8, "attack 10 against defense 4")
	t.ok(shot.done, "a shot is spent on its first hit")
	t.ok(not shot.hit(target.get_node("Hurtbox") as RpgHurtbox), "and does not hit again")
	t.eq(_health(target).hp(), 22)
	var second := RpgProjectile.create(shooter, Vector2.ZERO, Vector2.LEFT, &"enemy", 100.0, 100.0)
	var info := second.build_info(target.get_node("Hurtbox") as RpgHurtbox)
	t.eq(info.knockback.normalized(), Vector2.LEFT, "it pushes along its flight")
	second.heavy = true
	t.eq(second.build_info(target.get_node("Hurtbox") as RpgHurtbox).amount, RpgArpgMath.heavy_damage(8))
	for node: Node in [shot, second, shooter, target, friend]:
		node.free()
	Fixtures.uninstall_state()

func test_an_invulnerable_target_still_stops_a_shot(t) -> void:
	var shooter := _fighter("enemy", 10, 0, 10)
	var target := _fighter("player", 1, 0, 30)
	(target.get_node("Hurtbox") as RpgHurtbox).make_invulnerable(5.0)
	var shot := RpgProjectile.create(shooter, Vector2.ZERO, Vector2.RIGHT, &"enemy", 100.0, 100.0)
	t.ok(not shot.hit(target.get_node("Hurtbox") as RpgHurtbox), "no damage during the window")
	t.ok(shot.done)
	t.eq(_health(target).hp(), 30)
	for node: Node in [shot, shooter, target]:
		node.free()

# ---------------------------------------------------------------- shots on the ground

## A body standing with its feet at `feet`, `height` tall in its picture: a hurtbox as the action
## RPG's builder makes it (arpg_build.gd: the middle of the picture, 60 % of its height, half its
## width), the picture as wide as it is tall.
func _body(team: String, feet: Vector2, height: float) -> Node2D:
	var holder := Node2D.new()
	holder.name = "Body"
	holder.position = feet
	var hurtbox := RpgHurtbox.new()
	hurtbox.name = "Hurtbox"
	hurtbox.team = StringName(team)
	hurtbox.collision_layer = 0
	hurtbox.set_collision_layer_value(10 if team == "enemy" else 9, true)
	hurtbox.position = Vector2(0.0, -height * 0.5)
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(maxf(6.0, height * 0.5), maxf(8.0, height * 0.6))
	shape.shape = rect
	hurtbox.add_child(shape)
	holder.add_child(hurtbox)
	return holder

func _hurtbox_of(body: Node2D) -> RpgHurtbox:
	return body.get_node("Hurtbox") as RpgHurtbox

## Whether the line a shot fired at the middle of a 64-px shooter flew along (y = -32, radius 3)
## crosses `body`'s hurtbox: how the arrow flew before it flew on the ground.
func _old_flight_meets(body: Node2D) -> bool:
	var hurtbox := _hurtbox_of(body)
	var rect := (hurtbox.get_child(0) as CollisionShape2D).shape as RectangleShape2D
	var middle := body.position.y + hurtbox.position.y
	return absf(middle - (-32.0)) <= rect.size.y * 0.5 + RpgProjectile.RADIUS

func test_a_shot_on_the_ground_meets_short_and_tall_bodies_from_above(t) -> void:
	var shot := RpgProjectile.create(null, Vector2.ZERO, Vector2.RIGHT, &"player", 600.0, 400.0, "arrow")
	shot.set_on_ground(Vector2(0, -32))  # a shooter 64 px tall
	t.ok(shot.on_ground and shot.lift == Vector2(0, -32))
	t.ok(not shot.get_collision_mask_value(10) and not shot.get_collision_mask_value(9), "it meets footprints, not hurtboxes")
	t.ok(shot.get_collision_mask_value(1), "walls still stop it")
	t.eq(shot.drawn_lift(), Vector2(0, -32), "drawn at the hand when loosed")
	shot.travelled = 300.0
	t.eq(shot.drawn_lift(), Vector2(0, -8), "and lower as it flies (3/4 of its range)")
	shot.travelled = 0.0
	var way := Vector2(300, 0)
	for height: float in [8.0, 24.0, 30.0, 64.0, 128.0]:
		var body := _body("enemy", Vector2(96, 0), height)
		t.eq(shot.first_on_path(Vector2.ZERO, way, [_hurtbox_of(body)]), _hurtbox_of(body), "a body %d px tall in its way is hit" % int(height))
		var nearer := _body("enemy", Vector2(96, maxf(6.0, height * 0.5) * 0.4), height)
		t.eq(shot.first_on_path(Vector2.ZERO, way, [_hurtbox_of(nearer)]), _hurtbox_of(nearer), "and one standing a little nearer (%d px)" % int(height))
		body.free()
		nearer.free()
	var slime := _body("enemy", Vector2(96, 0), 24.0)
	t.ok(not _old_flight_meets(slime), "a body shorter than half the shooter: the flight at the middle of the shooter passed over it")
	slime.free()
	# a tall body standing 40 px nearer the camera: its picture covers the line, its feet do not
	var giant := _body("enemy", Vector2(96, 40), 128.0)
	t.ok(_old_flight_meets(giant), "the old flight met its body")
	t.ok(shot.first_on_path(Vector2.ZERO, way, [_hurtbox_of(giant)]) == null, "on the ground the shot passes behind it")
	giant.free()
	# straight down the screen
	var below := _body("enemy", Vector2(0, 96), 16.0)
	var aside := _body("enemy", Vector2(30, 96), 16.0)
	t.eq(shot.first_on_path(Vector2.ZERO, Vector2(0, 300), [_hurtbox_of(aside), _hurtbox_of(below)]), _hurtbox_of(below), "a short body below is hit, one aside is not")
	# the first footprint on the way, not the first in the list
	var far := _body("enemy", Vector2(200, 0), 128.0)
	var close := _body("enemy", Vector2(100, 0), 10.0)
	t.eq(shot.first_on_path(Vector2.ZERO, way, [_hurtbox_of(far), _hurtbox_of(close)]), _hurtbox_of(close))
	for node: Node in [below, aside, far, close, shot]:
		node.free()

func test_a_shot_on_the_ground_meets_short_and_tall_bodies_on_diamonds(t) -> void:
	# diamonds of 64 x 32: a step along a side of a diamond goes 32 across and 16 down
	var axis := Vector2(2, 1).normalized()
	var shot := RpgProjectile.create(null, Vector2.ZERO, axis, &"enemy", 600.0, 400.0)
	shot.set_on_ground(Vector2(0, -12))  # a short shooter (24 px) at a tall player
	var way := axis * 300.0
	for height: float in [10.0, 24.0, 48.0, 96.0]:
		var on_line := _body("player", Vector2(128, 64), height)
		var off_line := _body("player", Vector2(128, 0), height)
		t.eq(shot.first_on_path(Vector2.ZERO, way, [_hurtbox_of(on_line)]), _hurtbox_of(on_line), "a body %d px tall two diamonds along is hit" % int(height))
		t.ok(shot.first_on_path(Vector2.ZERO, way, [_hurtbox_of(off_line)]) == null, "one on the next row is not (%d px)" % int(height))
		on_line.free()
		off_line.free()
	shot.free()

func test_a_shot_on_the_ground_flies_into_a_short_body_in_the_tree(t) -> void:
	var state := Fixtures.install_state()
	var tree := Engine.get_main_loop() as SceneTree
	var map := Node2D.new()
	map.name = "ShotMap"
	tree.root.add_child(map)
	var shooter := _fighter("player", 10, 0, 10)
	map.add_child(shooter)
	var target := _fighter("enemy", 1, 0, 30)
	target.position = Vector2(150, 0)
	var hurtbox := target.get_node("Hurtbox") as RpgHurtbox
	hurtbox.collision_layer = 0
	hurtbox.set_collision_layer_value(10, true)
	hurtbox.position = Vector2(0, -6)  # 12 px tall, the shooter 64
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(6, 8)
	shape.shape = rect
	hurtbox.add_child(shape)
	map.add_child(target)
	t.ok(hurtbox.is_in_group(RpgHurtbox.GROUP), "a hurtbox in the tree is in the group")
	var shot := RpgProjectile.create(shooter, Vector2.ZERO, Vector2.RIGHT, &"player", 900.0, 400.0, "arrow")
	shot.set_on_ground(Vector2(0, -32))
	map.add_child(shot)
	var targets := shot.targets()
	t.ok(targets.size() == 1 and targets[0] == hurtbox, "the other team's hurtboxes")
	for i in 30:
		if shot.done:
			break
		shot.advance(1.0 / 60.0)  # 15 px a step: more than the body is wide
	t.ok(shot.done, "the shot stopped")
	t.eq(_health(target).hp(), 30 - 10, "it hurt the short body")
	t.ok(shot.position.x < 150.0 and shot.position.x > 140.0, "where its footprint begins (%.1f)" % shot.position.x)
	map.free()
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- enemy kinds

func test_the_kind_comes_from_the_behavior_or_the_asset_name(t) -> void:
	t.eq(RpgEnemyAi.merged_behavior({}, 16.0)["kind"], "melee")
	t.eq(RpgEnemyAi.merged_behavior({}, 32.0)["shoot_range_px"], 160.0, "ranges scale with the tile")
	t.eq(EnemyRecipes.kind_for("goblin_archer_idle"), "shooter")
	t.eq(EnemyRecipes.kind_for("Wild-Boar"), "charger")
	t.eq(EnemyRecipes.kind_for("evil_eye"), "turret")
	t.eq(EnemyRecipes.kind_for("slime"), "melee")
	t.eq(EnemyRecipes.kind_for("eyeball"), "melee", "whole words only")
	t.eq(EnemyRecipes.behavior_for(16, "direct", "charger")["kind"], "charger")
	t.eq(EnemyRecipes.variant_path("slime", "shooter"), "res://game/data/enemies/slime_shooter.tres")

func test_the_shooter_aims_waits_fires_and_cools_down(t) -> void:
	var actor := _fighter("enemy", 5, 0, 10)
	var map := Node2D.new()
	map.add_child(actor)
	var shoot := RpgEnemyShoot.new()
	shoot.name = "EnemyShoot"
	(actor.get_node("Components") as Node).add_child(shoot)
	if not shoot.is_node_ready():  # add_child readies it once the tree runs
		shoot._ready()
	shoot.windup_s = 0.3
	shoot.cooldown_s = 1.0
	t.ok(shoot.try_start(Vector2(0, 40)))
	t.eq(actor.facing, "down", "it turns to its target")
	t.ok(not shoot.can_start(), "one shot at a time")
	t.ok(not shoot.update(0.2), "still aiming")
	t.ok(shoot.last_shot == null)
	t.ok(shoot.update(0.15), "fired after the windup")
	var shot := shoot.last_shot
	t.ok(shot != null and shot.get_parent() == map, "the shot flies in the map, beside the shooter")
	t.eq(shot.velocity.normalized(), Vector2.DOWN)
	t.eq(shot.team, &"enemy")
	t.ok(shot.on_ground, "it flies on the ground")
	t.eq(shot.position, actor.position, "from the shooter's feet")
	t.ok(not shoot.can_start(), "cooling down")
	shoot._physics_process(1.0)
	t.ok(shoot.can_start())
	t.ok(shoot.try_start(Vector2(40, 0)))
	shoot.cancel()
	t.ok(not shoot.aiming and shoot.cooldown_left > 0.0, "a cancelled shot cools down too")
	map.free()

func test_the_charger_winds_up_dashes_with_its_hitbox_and_recovers(t) -> void:
	var actor := _fighter("enemy", 5, 0, 10)
	var charge := RpgEnemyCharge.new()
	charge.name = "EnemyCharge"
	(actor.get_node("Components") as Node).add_child(charge)
	if not charge.is_node_ready():  # add_child readies it once the tree runs
		charge._ready()
	charge.windup_s = 0.2
	charge.dash_s = 0.3
	charge.recover_s = 0.25
	charge.speed = 150.0
	var movement := actor.component("Movement") as RpgMovement
	movement.actor = actor
	movement.speed = 40.0
	var hitbox := actor.get_node("AttackHitbox") as RpgHitbox
	t.ok(charge.try_start(Vector2(-80, 0)))
	t.eq(charge.direction, Vector2.LEFT)
	t.ok(not charge.update(0.1))
	t.eq(charge.phase, RpgEnemyCharge.Phase.WINDUP)
	t.ok(not hitbox.active, "harmless while it winds up")
	charge.update(0.15)
	t.eq(charge.phase, RpgEnemyCharge.Phase.DASH)
	t.ok(hitbox.active, "the hitbox is live during the dash")
	t.eq(movement.speed, 150.0)
	t.eq(movement.desired, Vector2.LEFT)
	t.ok(actor.facing_locked)
	charge.update(0.31)
	t.eq(charge.phase, RpgEnemyCharge.Phase.RECOVER)
	t.ok(not hitbox.active)
	t.eq(movement.speed, 40.0, "its own speed is back")
	t.eq(movement.desired, Vector2.ZERO, "it stands while it recovers")
	t.ok(not charge.update(0.1))
	t.ok(charge.update(0.2), "done after the recovery")
	t.ok(not charge.can_start(), "and cools down")
	t.ok(charge.try_start(Vector2(80, 0)) == false)
	charge.cooldown_left = 0.0
	t.ok(charge.try_start(Vector2(80, 0)))
	charge.update(0.25)
	charge.cancel()
	t.ok(not hitbox.active and movement.speed == 40.0, "a cancelled dash puts everything back")
	actor.free()

# ---------------------------------------------------------------- the player's ranged weapon

func test_a_ranged_weapon_fires_arrows(t) -> void:
	var bow := Fixtures.item(&"bow", 1)
	bow.category = RpgItemDefinition.Category.WEAPON
	bow.ranged = true
	var sword := Fixtures.item(&"sword", 1)
	sword.category = RpgItemDefinition.Category.WEAPON
	var state := Fixtures.install_state({&"bow": bow, &"sword": sword})
	state.new_game()
	t.ok(not RpgPlayerCombat.weapon_is_ranged(), "bare hands")
	state.inventory.add(&"sword")
	state.equip(state.player_actor_id, &"sword")
	t.ok(not RpgPlayerCombat.weapon_is_ranged())
	state.inventory.add(&"bow")
	state.equip(state.player_actor_id, &"bow")
	t.ok(RpgPlayerCombat.weapon_is_ranged())
	var player := _fighter("player", 6, 0, 20)
	var map := Node2D.new()
	map.add_child(player)
	var combat := RpgPlayerCombat.new()
	combat.name = "PlayerCombat"
	player.add_child(combat)
	if not combat.is_node_ready():  # add_child readies it once the tree runs
		combat._ready()
	player.facing = "left"
	combat.machine.go(RpgPlayerCombat.ATTACK)
	for i in 30:
		combat.machine._physics_process(1.0 / 60.0)
	var shot := combat.last_shot
	t.ok(shot != null, "the attack fired an arrow")
	t.ok(not (player.get_node("AttackHitbox") as RpgHitbox).active, "and never swung")
	t.eq(shot.team, &"player")
	t.eq(shot.style, "arrow")
	t.eq(shot.velocity.normalized(), Vector2.LEFT)
	t.ok(shot.on_ground, "the arrow flies on the ground")
	t.eq(shot.position, player.position, "from the player's feet")
	t.eq(shot.lift, (player.get_node("Hurtbox") as Node2D).position, "drawn at the middle of the body")
	var arrows := map.get_children().filter(func(n: Node) -> bool: return n is RpgProjectile)
	t.eq(arrows.size(), 1, "one arrow per attack")
	map.free()
	Fixtures.uninstall_state()
