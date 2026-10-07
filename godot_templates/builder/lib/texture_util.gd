extends RefCounted
## Texture helpers for scene recipes.

## AtlasTextures already made in this build, by atlas path and region. They are embedded in the
## scenes that use them as sub-resources; no separate .tres file is written per region.
static var _cache: Dictionary = {}

static func region_texture(atlas_path: String, region: Rect2i) -> AtlasTexture:
	var key := "%s|%d,%d,%d,%d" % [atlas_path, region.position.x, region.position.y, region.size.x, region.size.y]
	if _cache.has(key):
		return _cache[key]
	if not ResourceLoader.exists(atlas_path):
		return null
	var atlas := load(atlas_path) as Texture2D
	if atlas == null:
		return null
	var tex := AtlasTexture.new()
	tex.atlas = atlas
	tex.region = Rect2(region)
	_cache[key] = tex
	return tex

## The image of a catalog asset (a Dictionary with a project-relative `path`).
static func asset_texture(asset: Dictionary) -> Texture2D:
	return load("res://" + str(asset.get("path", ""))) as Texture2D

static func clear_cache() -> void:
	_cache.clear()
