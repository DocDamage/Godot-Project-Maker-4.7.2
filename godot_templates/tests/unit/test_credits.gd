extends RefCounted
## The Credits screen (T12.51): the recipe's pack entries and licence rules, the extra lines of
## credits_extra.tsv, the generated resource, and the menu.

const Fixtures := preload("../lib/fixtures.gd")
const UiRecipes := preload("res://builder/recipes/ui_recipes.gd")
const SceneUtil := preload("res://builder/lib/scene_util.gd")
const CreditsRecipe := preload("res://builder/recipes/credits_recipe.gd")

const MENU_TMP := "user://test_credits_menu.tscn"

func _catalog() -> Dictionary:
	return {"packs": [
		{"pack_id": "town_tiles", "license": {"license_id": "CC-BY-4.0", "author": "Jane Doe", "url": "https://jane.example/town", "attribution_required": true}},
		{"pack_id": "free_sfx", "license": {"license_id": "CC0-1.0", "author": "", "url": "", "attribution_required": false}},
		{"pack_id": "heroes", "license": {"license_id": "", "author": "", "url": "", "attribution_required": false},
			"license_overrides": {"license_id": "OGA-BY-3.0", "author": "Ann Lee"}},
	]}

func test_pack_entries_use_the_corrections_and_sort_by_id(t) -> void:
	var entries := CreditsRecipe.pack_entries(_catalog())
	t.eq(entries.size(), 3)
	t.eq(entries[0]["pack_id"], "free_sfx")
	t.eq(entries[0]["license"], "CC0 1.0")
	t.eq(entries[0]["attribution_required"], false)
	var heroes: Dictionary = entries[1]
	t.eq(heroes["name"], "Heroes")
	t.eq(heroes["author"], "Ann Lee")
	t.eq(heroes["license"], "OGA-BY 3.0")
	t.eq(heroes["attribution_required"], true, "a licence chosen on the Audit page brings its credit rule")
	var town: Dictionary = entries[2]
	t.eq(town["name"], "Town Tiles")
	t.eq(town["license_url"], "https://creativecommons.org/licenses/by/4.0/")
	t.eq(town["url"], "https://jane.example/town")

func test_licence_names_and_links(t) -> void:
	t.eq(CreditsRecipe.label("CC-BY-SA-3.0"), "CC BY-SA 3.0")
	t.eq(CreditsRecipe.label("CC-BY-NC-4.0"), "CC BY-NC 4.0")
	t.eq(CreditsRecipe.label("MIT"), "MIT")
	t.eq(CreditsRecipe.label("rpgmaker"), "RPG Maker terms")
	t.eq(CreditsRecipe.label("commercial"), "Commercial licence")
	t.eq(CreditsRecipe.label(""), "Unknown licence")
	t.eq(CreditsRecipe.license_url("CC-BY-SA-4.0"), "https://creativecommons.org/licenses/by-sa/4.0/")
	t.eq(CreditsRecipe.license_url("CC0-1.0"), "https://creativecommons.org/publicdomain/zero/1.0/")
	t.eq(CreditsRecipe.license_url("commercial"), "")
	var kept := CreditsRecipe.effective({"license_id": "commercial", "attribution_required": true}, {"license_id": "commercial"})
	t.eq(kept["attribution_required"], true, "a licence whose wording decides keeps the detected rule")
	var chosen := CreditsRecipe.effective({"license_id": "CC-BY-4.0", "attribution_required": true}, {"license_id": "CC0-1.0"})
	t.eq(chosen["attribution_required"], false)
	var forced := CreditsRecipe.effective({"license_id": "CC0-1.0"}, {"attribution_required": true})
	t.eq(forced["attribution_required"], true)

func test_extra_lines_skip_notes_and_the_header(t) -> void:
	var rows := RpgCredits.parse_extra(CreditsRecipe.EXTRA_SEED)
	t.eq(rows.size(), 0, "the seeded file only has notes")
	rows = RpgCredits.parse_extra("section\ttext\nMade by\tSam\n\n# a note\nThanks to my cat\nMade by\tAlex\n")
	t.eq(rows.size(), 3)
	t.eq(rows[0], {"section": "Made by", "text": "Sam"})
	t.eq(rows[1], {"section": "", "text": "Thanks to my cat"})
	t.eq(rows[2]["text"], "Alex")

func _credits() -> RpgCredits:
	var credits := RpgCredits.new()
	var packs: Array[Dictionary] = []
	for entry: Dictionary in CreditsRecipe.pack_entries(_catalog()):
		packs.append(entry)
	credits.packs = packs
	credits.extra = RpgCredits.parse_extra("Made by\tSam\nMade by\tAlex\nMusic\tKim\n")
	return credits

func _menu(credits: RpgCredits) -> RpgCreditsMenu:
	var root: Node = UiRecipes.new().call("_build_credits_menu")
	SceneUtil.save_scene(root, MENU_TMP)
	var menu := (load(MENU_TMP) as PackedScene).instantiate() as RpgCreditsMenu
	menu.credits = credits
	Fixtures.tree().root.add_child(menu)
	if not menu.is_node_ready():
		menu._ready()
	return menu

func test_the_menu_lists_own_lines_then_packs_then_the_engine(t) -> void:
	var english := Fixtures.install_english()
	var menu := _menu(_credits())
	var texts := menu.shown_texts()
	t.eq(texts[0], "Made by")
	t.eq(texts[1], "Sam")
	t.eq(texts[2], "Alex")
	t.eq(texts[3], "Music")
	t.eq(texts[4], "Kim")
	t.eq(texts[5], "Art and sound")
	t.ok(texts.has("Town Tiles by Jane Doe"), str(texts))
	t.ok(texts.has("CC BY 4.0  https://creativecommons.org/licenses/by/4.0/"), str(texts))
	t.ok(texts.has("https://jane.example/town"))
	t.ok(texts.has("Free Sfx"), "a pack without an author is listed by name")
	t.ok(texts.has("Heroes by Ann Lee"))
	t.eq(texts[texts.size() - 4], "Engine")
	t.eq(texts[texts.size() - 3], RpgCreditsMenu.ENGINE_NAME)
	t.ok((menu.get_node("%Back") as Button) != null)
	menu.free()
	Fixtures.uninstall_english(english)

func test_an_empty_project_still_names_the_engine(t) -> void:
	var menu := _menu(RpgCredits.new())
	var texts := menu.shown_texts()
	t.eq(texts.size(), 4)
	t.eq(texts[1], RpgCreditsMenu.ENGINE_NAME)
	menu.free()

func test_the_title_and_pause_menus_have_a_credits_button(t) -> void:
	var recipes := UiRecipes.new()
	t.ok(UiRecipes.SCENES.has("credits_menu"))
	for scene_name: String in ["title_screen", "pause_menu"]:
		var root: Node = recipes.call("_build_" + scene_name)
		t.ok(root.find_child("Credits", true, false) is Button, scene_name)
		root.free()
