extends RefCounted
## generated/scenes/ui/hud_metroidvania.tscn: the metroidvania's HUD (T14.08), a CanvasLayer with
## RpgMetroidvaniaHud. The recipe gives it the abilities of the stored world plan, in the plan's
## order, with the art of each ability's pickup. Boot uses this scene in place of hud_basic.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const WorldPlan := preload("../../lib/world_plan.gd")
const Objects := preload("objects_recipe.gd")
const MvBuild := preload("metroidvania_build.gd")

const OUT_PATH := "res://generated/scenes/ui/hud_metroidvania.tscn"
const SCRIPT_PATH := MvBuild.DIR + "ui/hud.gd"

## The abilities of the world: the stored plan's, else every ability a pickup scene exists for.
static func abilities() -> PackedStringArray:
	var out := PackedStringArray()
	var rooms := JsonUtil.to_dict(WorldPlan.read().get("rooms", {}))
	for raw: Variant in JsonUtil.to_array(rooms.get("abilities", [])):
		out.append(JsonUtil.to_str(raw))
	return out

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([OUT_PATH])

func input_hash(ctx: BuildContext) -> String:
	var art: Array = []
	for ability in abilities():
		art.append(Objects._art(ctx, ["ability"], [ability, ability.replace("_", "")]).get("id", ""))
	return ctx.stable_hash({"v": RECIPE_VERSION, "abilities": abilities(), "art": art})

static func build_hud(ctx: BuildContext, shown: PackedStringArray) -> CanvasLayer:
	var root := CanvasLayer.new()
	root.name = "HudMetroidvania"
	SceneUtil.attach_script(root, SCRIPT_PATH)
	root.set("abilities", shown)
	var icons: Array[Texture2D] = []
	for ability in shown:
		icons.append(Objects._texture(ctx, Objects._art(ctx, ["ability"], [ability, ability.replace("_", "")])))
	root.set("icons", icons)
	return root

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var err := SceneUtil.save_scene(build_hud(ctx, abilities()), OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	return issues
