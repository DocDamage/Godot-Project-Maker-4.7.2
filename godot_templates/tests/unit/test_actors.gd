extends RefCounted
## Actors, components, chests, signs and NPCs (T6.05, T6.07).

const Fixtures := preload("../lib/fixtures.gd")
const ActorBuild := preload("res://builder/lib/actor_build.gd")

func _actor(kind: String) -> RpgActor:
	return ActorBuild.build(kind, "Test", null, Vector2i(16, 24), Vector2i(8, 23), 16) as RpgActor

func _free(node: Node) -> void:
	node.free()

func test_built_actor_has_the_component_layout(t) -> void:
	var a := _actor("base")
	t.ok(a.get_node_or_null("Visual") is AnimatedSprite2D)
	t.ok(a.get_node_or_null("Feet") is CollisionShape2D)
	var comps := a.components()
	t.eq(comps.keys(), ["Movement", "Stats"])
	t.ok(comps["Movement"] is RpgMovement)
	t.ok(comps["Stats"] is RpgStatsComponent)
	t.ok(a.component("Nothing") == null)
	_free(a)

func test_player_collision_and_extras(t) -> void:
	var p := _actor("player")
	t.eq(p.collision_layer, 2, "only the player layer")
	t.eq(p.collision_mask, 1 + 4 + 8)
	t.ok(p.is_in_group("player"))
	t.ok(p.get_node("Interaction") is RpgInteraction)
	t.ok(p.get_node("Camera") is Camera2D)
	t.ok(p.component("PlayerInput") is RpgPlayerInput)
	_free(p)

func test_npc_collision(t) -> void:
	var n := _actor("npc")
	t.ok(n is RpgNpc)
	t.eq(n.collision_layer, 8, "npcs layer")
	t.ok(not n.is_in_group("player"))
	_free(n)

func test_move_dir_forwards_and_faces(t) -> void:
	var a := _actor("base")
	var seen := []
	a.facing_changed.connect(func(f: String) -> void: seen.append(f))
	a.move_dir(Vector2(1, 0))
	t.eq(a.component("Movement").desired, Vector2(1, 0))
	t.eq(a.facing, "right")
	a.move_dir(Vector2.ZERO)
	t.eq(a.facing, "right", "stopping keeps the facing")
	a.set_facing("up")
	a.set_facing("up")
	t.eq(seen, ["right", "up"], "the signal fires only on a change")
	_free(a)

func test_movement_knockback_decays(t) -> void:
	var a := _actor("base")
	var m: RpgMovement = a.component("Movement")
	m.actor = a
	m.external_velocity = Vector2(100, 0)
	for i in 3:
		m.external_velocity *= 0.85
	t.near(m.external_velocity.x, 61.4125, 0.01)
	_free(a)

func test_stats_component_damage_and_heal(t) -> void:
	var state := Fixtures.install_state()
	var a := _actor("base")
	var comp: RpgStatsComponent = a.component("Stats")
	comp.actor = a
	comp.stats = RpgStats.new()
	comp.stats.max_hp = 10
	comp.stats.hp = 10
	var died := []
	var changes := []
	comp.died.connect(func() -> void: died.append(true))
	comp.hp_changed.connect(func(hp: int, max_hp: int) -> void: changes.append([hp, max_hp]))
	t.eq(comp.take_damage(4), 4)
	t.eq(comp.stats.hp, 6)
	t.eq(comp.take_damage(0), 0)
	t.eq(comp.heal(100), 4, "heal stops at max_hp")
	t.eq(comp.heal(5), 0)
	t.eq(comp.take_damage(50), 10, "damage is capped at the remaining hp")
	t.ok(comp.is_dead())
	t.eq(died.size(), 1)
	t.eq(comp.take_damage(1), 0, "the dead take no damage")
	t.eq(changes, [[6, 10], [10, 10], [0, 10]])
	t.ok(not comp.is_player())
	_free(a)
	t.ok(state != null)
	Fixtures.uninstall_state()

func test_player_stats_component_emits_events(t) -> void:
	Fixtures.install_state()
	var seen := []
	RpgUtil.events().player_damaged.connect(func(n: int) -> void: seen.append(["hurt", n]))
	RpgUtil.events().player_healed.connect(func(n: int) -> void: seen.append(["heal", n]))
	var p := _actor("player")
	var comp: RpgStatsComponent = p.component("Stats")
	comp.actor = p
	comp.stats = RpgStats.new()
	comp.take_damage(3)
	comp.heal(2)
	t.eq(seen, [["hurt", 3], ["heal", 2]])
	t.ok(comp.is_player())
	_free(p)
	Fixtures.uninstall_state()

func test_interaction_follows_the_facing(t) -> void:
	var p := _actor("player")
	var inter: RpgInteraction = p.get_node("Interaction")
	inter.tile_size = 16.0
	inter.actor = p
	inter._reposition("down")
	t.eq(inter.position, Vector2(0, 9.6))
	inter._reposition("up")
	t.eq(inter.position, Vector2(0, -9.6))
	inter._reposition("left")
	t.eq(inter.position, Vector2(-9.6, 0))
	inter._reposition("right")
	t.eq(inter.position, Vector2(9.6, 0))
	t.ok(not inter.try_interact(), "nothing in reach")
	t.ok(inter.find_target() == null)
	_free(p)

func test_player_input_disabled_stops_movement(t) -> void:
	var p := _actor("player")
	var input: RpgPlayerInput = p.component("PlayerInput")
	input.actor = p
	p.move_dir(Vector2(0, 1))
	p.input_enabled = false
	input._physics_process(0.0)
	t.eq(p.component("Movement").desired, Vector2.ZERO)
	_free(p)

# ---------------------------------------------------------------- chest, sign, npc

func _chest(entity_id: String, loot: Array, gold: int) -> RpgChest:
	var c := RpgChest.new()
	c.entity_id = entity_id
	c.loot.assign(loot)
	c.gold = gold
	var sprite := Sprite2D.new()
	sprite.name = "Sprite"
	c.add_child(sprite)
	return c

func test_chest_gives_its_contents_once(t) -> void:
	var state := Fixtures.install_state({&"potion": Fixtures.item(&"potion")})
	state.new_game()
	var notes := []
	RpgUtil.events().notify.connect(func(text: String) -> void: notes.append(text))
	var english := Fixtures.install_english()
	var chest := _chest("map_chest_001", [{"item_id": "potion", "qty": 2}], 20)
	var gold: int = state.gold
	var potions: int = state.inventory.count(&"potion")
	chest.interact()
	t.eq(state.gold, gold + 20)
	t.eq(state.inventory.count(&"potion"), potions + 2)
	t.eq(state.get_flag("map_chest_001", "opened"), true)
	t.ok(chest.is_opened())
	t.eq(notes.size(), 1)
	t.ok(String(notes[0]).begins_with("Found "))
	t.ok(String(notes[0]).contains("20 Gold"), "the gold is named with the translated word")
	Fixtures.uninstall_english(english)
	t.near((chest.get_node("Sprite") as Sprite2D).modulate.r, 0.55)
	chest.interact()
	t.eq(state.gold, gold + 20, "a second interaction gives nothing")
	t.eq(notes.size(), 1)
	chest.free()
	Fixtures.uninstall_state()

func test_chest_apply_opened_state_without_interaction(t) -> void:
	var chest := _chest("x", [], 0)
	chest.apply_opened_state()
	t.ok(chest.is_opened())
	chest.free()

func test_chest_uses_an_open_texture_when_given(t) -> void:
	var chest := _chest("x", [], 0)
	var sprite := chest.get_node("Sprite") as Sprite2D
	var open_tex := PlaceholderTexture2D.new()
	sprite.set_meta("open_texture", open_tex)
	chest.apply_opened_state()
	t.ok(sprite.texture == open_tex)
	chest.free()

func test_empty_chest_says_so(t) -> void:
	var state := Fixtures.install_state()
	var notes := []
	RpgUtil.events().notify.connect(func(text: String) -> void: notes.append(text))
	var english := Fixtures.install_english()
	var chest := _chest("empty_one", [], 0)
	chest.interact()
	t.eq(notes, [RpgStrings.english("UI_CHEST_EMPTY")])
	Fixtures.uninstall_english(english)
	chest.free()
	t.ok(state != null)
	Fixtures.uninstall_state()

func test_npc_faces_the_actor_before_talking(t) -> void:
	var npc := _actor("npc") as RpgNpc
	var other := Node2D.new()
	other.global_position = Vector2(-50, 0)
	npc.interact(other)  # no dialogue assigned: only turns
	t.eq(npc.facing, "left")
	other.global_position = Vector2(0, -50)
	npc.interact(other)
	t.eq(npc.facing, "up")
	other.free()
	_free(npc)

func test_sign_without_dialogue_does_nothing(t) -> void:
	var sign := RpgSign.new()
	sign.interact()
	t.ok(sign.dialogue == null)
	sign.free()
