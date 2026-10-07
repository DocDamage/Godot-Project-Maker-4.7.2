extends RefCounted
## RpgInventory (T6.03).

const Fixtures := preload("../lib/fixtures.gd")

func _inv() -> RpgInventory:
	var inv := RpgInventory.new()
	inv.registry = {
		&"potion": Fixtures.item(&"potion", 5, &"heal", 10),
		&"key": Fixtures.item(&"key", 1),
		&"junk": Fixtures.item(&"junk", 99, &"", 0),
	}
	return inv

func test_add_overflows_into_new_stacks(t) -> void:
	var inv := _inv()
	t.eq(inv.add(&"potion", 12), 12)
	t.eq(inv.slots.size(), 3)
	t.eq(inv.slots[0]["qty"], 5)
	t.eq(inv.slots[2]["qty"], 2)
	t.eq(inv.count(&"potion"), 12)

func test_add_fills_existing_stacks_first(t) -> void:
	var inv := _inv()
	inv.add(&"potion", 3)
	inv.add(&"potion", 4)
	t.eq(inv.slots.size(), 2)
	t.eq(inv.slots[0]["qty"], 5)
	t.eq(inv.slots[1]["qty"], 2)

func test_add_respects_capacity(t) -> void:
	var inv := _inv()
	inv.capacity = 2
	t.eq(inv.add(&"key", 5), 2, "only two single-item stacks fit")
	t.eq(inv.count(&"key"), 2)

func test_add_ignores_nonsense(t) -> void:
	var inv := _inv()
	t.eq(inv.add(&"potion", 0), 0)
	t.eq(inv.add(&"potion", -3), 0)
	t.eq(inv.add(&"", 1), 0)
	t.eq(inv.slots.size(), 0)

func test_remove_more_than_held_changes_nothing(t) -> void:
	var inv := _inv()
	inv.add(&"potion", 4)
	t.ok(not inv.remove(&"potion", 5))
	t.eq(inv.count(&"potion"), 4)
	t.ok(not inv.remove(&"potion", 0))

func test_remove_across_stacks_drops_empty_ones(t) -> void:
	var inv := _inv()
	inv.add(&"potion", 7)
	t.ok(inv.remove(&"potion", 3))
	t.eq(inv.count(&"potion"), 4)
	t.eq(inv.slots.size(), 1)
	t.ok(inv.remove(&"potion", 4))
	t.eq(inv.slots.size(), 0)

func test_has_and_count(t) -> void:
	var inv := _inv()
	inv.add(&"key", 1)
	t.ok(inv.has(&"key"))
	t.ok(not inv.has(&"key", 2))
	t.eq(inv.count(&"missing"), 0)

func test_use_heal_clamps_at_max_hp(t) -> void:
	var inv := _inv()
	inv.add(&"potion", 2)
	var stats := RpgStats.new()
	stats.hp = 18
	stats.max_hp = 20
	t.ok(inv.use(&"potion", stats))
	t.eq(stats.hp, 20)
	t.eq(inv.count(&"potion"), 1)

func test_use_heal_at_full_health_keeps_the_item(t) -> void:
	var inv := _inv()
	inv.add(&"potion", 1)
	var stats := RpgStats.new()
	t.ok(not inv.use(&"potion", stats))
	t.eq(inv.count(&"potion"), 1)

func test_use_without_effect_or_definition_fails(t) -> void:
	var inv := _inv()
	inv.add(&"junk", 1)
	inv.add(&"ghost", 1)
	var stats := RpgStats.new()
	stats.hp = 1
	t.ok(not inv.use(&"junk", stats))
	t.ok(not inv.use(&"ghost", stats))
	t.ok(not inv.use(&"potion", stats), "not held")

func test_unknown_ids_are_kept_through_a_round_trip(t) -> void:
	var inv := _inv()
	inv.add(&"potion", 6)
	inv.add(&"from_a_removed_mod", 2)
	var parsed: Variant = JSON.parse_string(JSON.stringify(inv.to_array()))
	var back := _inv()
	back.load_array(parsed)
	t.eq(back.count(&"potion"), 6)
	t.eq(back.count(&"from_a_removed_mod"), 2)
	t.eq(back.slots.size(), inv.slots.size())

func test_events_are_emitted(t) -> void:
	var state := Fixtures.install_state()
	var seen := []
	var bus: Node = RpgUtil.events()
	bus.item_added.connect(func(id: StringName, qty: int) -> void: seen.append(["add", id, qty]))
	bus.item_removed.connect(func(id: StringName, qty: int) -> void: seen.append(["remove", id, qty]))
	var inv := _inv()
	inv.add(&"potion", 2)
	inv.remove(&"potion", 1)
	t.eq(seen, [["add", &"potion", 2], ["remove", &"potion", 1]])
	t.ok(state != null)
	Fixtures.uninstall_state()
