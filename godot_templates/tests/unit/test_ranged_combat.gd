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
	var arrows := map.get_children().filter(func(n: Node) -> bool: return n is RpgProjectile)
	t.eq(arrows.size(), 1, "one arrow per attack")
	map.free()
	Fixtures.uninstall_state()
