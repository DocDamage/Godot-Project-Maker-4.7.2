extends RefCounted
## The light texture of objects tagged "light" (T12.62): a soft radial gradient, generated here
## and saved as a resource (never drawn by hand), shared by every light.

const RECIPE_VERSION := 1

const BuildContext := preload("../lib/build_context.gd")

const TEXTURE_PATH := "res://generated/lighting/light_radial.tres"
const SIZE := 128

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([TEXTURE_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "size": SIZE})

## White in the middle fading to nothing at the edge; PointLight2D tints it with its colour.
static func make_texture() -> GradientTexture2D:
	var gradient := Gradient.new()
	gradient.offsets = PackedFloat32Array([0.0, 0.35, 1.0])
	gradient.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 0.55), Color(1, 1, 1, 0)])
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.width = SIZE
	texture.height = SIZE
	texture.fill = GradientTexture2D.FILL_RADIAL
	texture.fill_from = Vector2(0.5, 0.5)
	texture.fill_to = Vector2(1.0, 0.5)
	return texture

func build(ctx: BuildContext) -> Array:
	DirAccess.make_dir_recursive_absolute(TEXTURE_PATH.get_base_dir())
	var err := ResourceSaver.save(make_texture(), TEXTURE_PATH)
	if err != OK:
		return [ctx.make_issue("BUILD-004", {"file": TEXTURE_PATH, "err": err}, TEXTURE_PATH)]
	return []
