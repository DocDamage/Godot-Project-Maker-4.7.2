extends RefCounted

const CatalogEdit := preload("res://addons/rpg_project_tools/tools/catalog_edit.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")
const JsonIo := preload("res://addons/rpg_project_tools/tools/json_io.gd")

func test_effective_matches_the_builder_reader_on_the_shared_fixture(t) -> void:
	var cases: Variant = JsonIo.read("res://tests/fixtures/effective_cases.json")
	t.ok(cases is Array and cases.size() > 0, "fixture loads")
	for c in cases:
		t.eq(CatalogEdit.effective(c["asset"]), c["expected"], "case '%s'" % c["name"])
		t.eq(CatalogEdit.effective(c["asset"]), CatalogReader.effective(c["asset"]), "same as the builder, case '%s'" % c["name"])

func test_recompute_status_matches_the_python_cases(t) -> void:
	var cases: Variant = JsonIo.read("res://tests/fixtures/status_cases.json")
	t.ok(cases is Array and cases.size() > 0, "fixture loads")
	for c in cases:
		var asset: Dictionary = c["asset"].duplicate(true)
		t.eq(CatalogEdit.recompute_status(asset, c.get("file_missing", false)), c["expected"], "case '%s'" % c["name"])

func _catalog() -> Dictionary:
	return {
		"assets": [{"id": "p.hero", "status": "AUTO_DETECTED", "detected": {"role": "PLAYER", "origin": [8, 23], "animations": {"walk_down": {"fps": 8.0, "loop": true}}}, "overrides": {}, "confidence": 0.8}],
		"objects": [{"id": "p.town#house", "role": "BUILDING", "origin": [40, 63], "tags": [], "status": "AUTO_DETECTED", "source": "auto"}],
		"id_allocations": {"tilesets": {}, "entities": {}},
	}

func test_apply_overrides_confirms_the_asset(t) -> void:
	var cat := _catalog()
	var status := CatalogEdit.apply_overrides(cat, "p.hero", {"origin": [8, 22], "animations": {"walk_down": {"fps": 12.0}}})
	t.eq(status, "CONFIRMED")
	var eff := CatalogEdit.effective(cat["assets"][0])
	t.eq(eff["origin"], [8, 22])
	t.eq(eff["animations"]["walk_down"]["fps"], 12.0)
	t.eq(eff["animations"]["walk_down"]["loop"], true, "the detected loop flag survives the fps override")
	t.eq(cat["assets"][0]["detected"]["origin"], [8, 23], "detected facets are never edited")

func test_a_null_change_removes_the_override(t) -> void:
	var cat := _catalog()
	CatalogEdit.apply_overrides(cat, "p.hero", {"origin": [1, 1]})
	CatalogEdit.apply_overrides(cat, "p.hero", {"origin": null})
	t.eq(cat["assets"][0]["overrides"], {})
	t.eq(cat["assets"][0]["status"], "AUTO_DETECTED")

func test_role_none_marks_the_asset_unused(t) -> void:
	var cat := _catalog()
	t.eq(CatalogEdit.apply_overrides(cat, "p.hero", {"role": "NONE"}), "UNUSED")

func test_unknown_asset(t) -> void:
	t.eq(CatalogEdit.apply_overrides(_catalog(), "nope", {"role": "NPC"}), "")
	t.ok(not CatalogEdit.apply_object_changes(_catalog(), "nope", {"role": "NPC"}))

func test_object_changes_are_the_users(t) -> void:
	var cat := _catalog()
	t.ok(CatalogEdit.apply_object_changes(cat, "p.town#house", {"role": "DECORATION", "tags": ["door"], "origin": null}))
	var obj: Dictionary = cat["objects"][0]
	t.eq(obj["role"], "DECORATION")
	t.eq(obj["tags"], ["door"])
	t.ok(not obj.has("origin"))
	t.eq(obj["source"], "user")
	t.eq(obj["status"], "CONFIRMED")

func test_entity_allocations_are_created_on_demand(t) -> void:
	var cat := {}
	var alloc := CatalogEdit.entity_allocations(cat, "starter_map")
	alloc["npc"] = 3
	t.eq(cat["id_allocations"]["entities"]["starter_map"]["npc"], 3)
	t.eq(CatalogEdit.entity_allocations(cat, "starter_map")["npc"], 3)

func test_save_and_load_round_trip(t) -> void:
	var path := "user://m8_catalog_test.json"
	t.eq(CatalogEdit.save_catalog(_catalog(), path), OK)
	var loaded := CatalogEdit.load_catalog(path)
	t.eq(loaded["assets"][0]["id"], "p.hero")
	DirAccess.remove_absolute(path)
	t.eq(CatalogEdit.load_catalog("user://m8_no_such_catalog.json"), {})
