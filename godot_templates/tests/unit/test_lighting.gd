extends RefCounted
## Lighting and day/night (T12.62).

const Fixtures := preload("../lib/fixtures.gd")
const ObjectScenes := preload("res://builder/recipes/object_scenes_recipe.gd")
const LightingRecipe := preload("res://builder/recipes/lighting_recipe.gd")

static func _entry(tags: Array, entry_name: String) -> Dictionary:
	var image := Image.create(16, 32, false, Image.FORMAT_RGBA8)
	image.fill(Color(0.8, 0.5, 0.2))
	var path := "user://test_light_sheet_%d.png" % Time.get_ticks_usec()
	image.save_png(path)
	return {
		"id": "pack.props.%s" % entry_name, "name": entry_name, "role": "DECORATION", "tags": tags,
		"texture_path": path, "region": [0, 0, 16, 32], "origin": [8, 31], "footprint": [],
		"collision": {"profile": "NONE"}, "door": [], "sha256": "", "open_region": [],
	}

func test_a_tagged_object_scene_has_a_light(t) -> void:
	var recipe := ObjectScenes.new()
	var out := "user://test_light_object_%d.tscn" % Time.get_ticks_usec()
	t.eq(recipe.call("_build_scene", _entry(["light"], "wall_torch"), out, 16), OK)
	var scene := (load(out) as PackedScene).instantiate()
	var light := scene.get_node_or_null("Light") as PointLight2D
	t.ok(light != null, "the torch has a light")
	if light != null:
		t.ok(light is RpgLightSource)
		t.eq(light.get("flicker"), true, "a torch flickers")
		t.ok(light.texture is GradientTexture2D, "the texture is generated, not drawn")
		t.near(light.texture_scale, 16.0 * 4.0 / LightingRecipe.SIZE)
	scene.free()
	t.eq(recipe.call("_build_scene", _entry(["light"], "street_lamp"), out, 16), OK)
	var lamp := (load(out) as PackedScene).instantiate()
	t.eq(lamp.get_node("Light").get("flicker"), false, "a lamp is steady")
	lamp.free()
	t.eq(recipe.call("_build_scene", _entry([], "barrel"), out, 16), OK)
	var plain := (load(out) as PackedScene).instantiate()
	t.ok(plain.get_node_or_null("Light") == null, "no tag: no light")
	plain.free()

func test_the_interior_ambient_and_the_outdoor_day(t) -> void:
	var settings := Fixtures.install("RpgSettings", Fixtures.SETTINGS) as RpgSettingsStore
	settings.day_night = false
	var inside := RpgMapRoot.new()
	inside.is_interior = true
	inside._ready()
	var ambient := inside.get_node("Ambient") as CanvasModulate
	t.eq(ambient.color, RpgDayNight.INTERIOR)
	t.ok(ambient.color.v < 1.0, "dimmer than day")
	var by_name := RpgMapRoot.new()
	by_name.map_id = &"interior_2"  # a project made before the flag
	by_name._ready()
	t.eq((by_name.get_node("Ambient") as CanvasModulate).color, RpgDayNight.INTERIOR)
	var outside := RpgMapRoot.new()
	outside._ready()
	t.eq((outside.get_node("Ambient") as CanvasModulate).color, RpgDayNight.DAY)
	t.ok(not outside.is_processing(), "no cycle: nothing to update")
	settings.day_night = true
	outside.update_ambient()
	t.ok(outside.is_processing(), "the cycle keeps the outdoor ambient up to date")
	inside.update_ambient()
	t.ok(not inside.is_processing(), "the cycle does not reach inside")
	for root: Node in [inside, by_name, outside]:
		root.free()
	Fixtures.uninstall("RpgSettings")

func test_the_cycle_is_deterministic_at_a_fixed_time(t) -> void:
	t.near(RpgDayNight.hour_at(0.0), RpgDayNight.START_HOUR)
	t.near(RpgDayNight.hour_at(RpgDayNight.CYCLE_MINUTES * 60.0), RpgDayNight.START_HOUR, 0.0001, "a full cycle is a day")
	t.near(RpgDayNight.hour_at(RpgDayNight.CYCLE_MINUTES * 30.0), fposmod(RpgDayNight.START_HOUR + 12.0, 24.0))
	t.eq(RpgDayNight.ambient_at(12.0), RpgDayNight.DAY)
	t.eq(RpgDayNight.ambient_at(2.0), RpgDayNight.NIGHT)
	var dusk := RpgDayNight.ambient_at(19.75)
	t.eq(dusk, RpgDayNight.ambient_at(19.75 + 24.0), "the same hour of another day")
	t.ok(dusk != RpgDayNight.DAY and dusk != RpgDayNight.NIGHT, "dusk is in between")
	var at := RpgDayNight.map_ambient(false, true, 600.0)
	t.eq(at, RpgDayNight.map_ambient(false, true, 600.0))
	t.eq(RpgDayNight.map_ambient(false, false, 600.0), RpgDayNight.DAY)
	t.eq(RpgDayNight.map_ambient(true, true, 600.0), RpgDayNight.INTERIOR)
	t.near(RpgLightSource.flicker_energy(1.0, 0.0, 3.0), 1.0, 0.0001, "no flicker amount: full energy")
	t.eq(RpgLightSource.flicker_energy(1.0, 0.2, 3.0), RpgLightSource.flicker_energy(1.0, 0.2, 3.0))
