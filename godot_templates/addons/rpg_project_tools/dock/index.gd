@tool
extends RefCounted
## The asset library's entries: placeable object scenes, character scenes and enemy scenes,
## described by the index files the builder writes and by the catalog.
##
## An entry is {id, name, role, category, kind, scene_path, tags, asset_id}. `kind` is "object",
## "character" or "enemy"; `asset_id` is the catalog asset or sheet object the scene came from
## ("" when the scene has no catalog record).

const CatalogEdit := preload("../tools/catalog_edit.gd")
const JsonIo := preload("../tools/json_io.gd")

const OBJECT_INDEX := "res://rpggen/object_index.json"
const CHARACTER_INDEX := "res://rpggen/character_index.json"
const ENEMY_DIR := "res://generated/scenes/enemies"
const CATEGORIES := ["All", "Buildings", "Decorations", "Interior", "Characters", "Enemies", "Items", "Interactables"]

## The category of a library entry.
static func category_of(role: String, tags: Array, kind: String) -> String:
	if kind == "enemy" or role == "ENEMY" or role == "BOSS":
		return "Enemies"
	if kind == "character":
		return "Characters"
	if role == "BUILDING":
		return "Buildings"
	if tags.has("chest") or tags.has("sign"):
		return "Interactables"
	match role:
		"ITEM":
			return "Items"
		"INTERIOR":
			return "Interior"
		"DECORATION":
			return "Decorations"
	return ""

static func _last_part(id: String) -> String:
	return id.get_slice("#", id.get_slice_count("#") - 1) if id.contains("#") else id.get_slice(".", id.get_slice_count(".") - 1)

## Entries for every scene of the indexes, sorted by name then id.
static func build(catalog: Dictionary = {}) -> Array:
	var entries: Array = []
	var objects: Variant = JsonIo.read(OBJECT_INDEX)
	if objects is Dictionary:
		for id in objects.keys():
			entries.append(_object_entry(String(id), String(objects[id]), catalog))
	var characters: Variant = JsonIo.read(CHARACTER_INDEX)
	if characters is Dictionary:
		for id in characters.keys():
			entries.append(_character_entry(String(id), String(characters[id]), catalog))
	var dir := DirAccess.open(ENEMY_DIR)
	if dir != null:
		for file_name in dir.get_files():
			if file_name.get_extension() == "tscn":
				entries.append(_enemy_entry(ENEMY_DIR + "/" + file_name))
	entries.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		var ka := String(a["name"]).to_lower() + "|" + String(a["id"])
		var kb := String(b["name"]).to_lower() + "|" + String(b["id"])
		return ka < kb)
	return entries

static func _object_entry(id: String, scene_path: String, catalog: Dictionary) -> Dictionary:
	var role := "NONE"
	var tags: Array = []
	var display := _last_part(id)
	var index := CatalogEdit.object_index(catalog, id)
	if index >= 0:
		var obj: Dictionary = catalog["objects"][index]
		role = String(obj.get("role", "NONE"))
		tags = obj.get("tags", []).duplicate()
		display = String(obj.get("name", display))
	else:
		var asset := CatalogEdit.find_asset(catalog, id)
		if not asset.is_empty():
			var eff := CatalogEdit.effective(asset)
			role = String(eff.get("role", "NONE"))
			tags = eff.get("tags", []).duplicate()
	return {"id": id, "name": display, "role": role, "category": category_of(role, tags, "object"),
		"kind": "object", "scene_path": scene_path, "tags": tags, "asset_id": id}

static func _character_entry(id: String, scene_path: String, catalog: Dictionary) -> Dictionary:
	var role := "NPC"
	var tags: Array = []
	var asset := CatalogEdit.find_asset(catalog, id)
	if not asset.is_empty():
		var eff := CatalogEdit.effective(asset)
		role = String(eff.get("role", "NPC"))
		tags = eff.get("tags", []).duplicate()
	return {"id": id, "name": _last_part(id), "role": role, "category": category_of(role, tags, "character"),
		"kind": "character", "scene_path": scene_path, "tags": tags, "asset_id": id}

static func _enemy_entry(scene_path: String) -> Dictionary:
	var stem := scene_path.get_file().get_basename()
	return {"id": "enemy:" + stem, "name": stem.replace("_", " ").capitalize(), "role": "ENEMY", "category": "Enemies",
		"kind": "enemy", "scene_path": scene_path, "tags": [], "asset_id": ""}

## Entries matching the search text (name, id and tags, case-insensitive) and the category.
static func filter(entries: Array, text: String, category: String) -> Array:
	var needle := text.strip_edges().to_lower()
	var out: Array = []
	for e in entries:
		if category != "All" and e["category"] != category:
			continue
		if needle != "":
			var hay := (String(e["name"]) + " " + String(e["id"]) + " " + " ".join(PackedStringArray(e["tags"]))).to_lower()
			if not hay.contains(needle):
				continue
		out.append(e)
	return out

## Modification times of the index files and the catalog, joined into one string; a rescan is
## needed when it changes.
static func fingerprint() -> String:
	var parts: PackedStringArray = []
	for path in [OBJECT_INDEX, CHARACTER_INDEX, CatalogEdit.CATALOG_PATH]:
		parts.append("%s:%d" % [path, FileAccess.get_modified_time(path) if FileAccess.file_exists(path) else 0])
	var dir := DirAccess.open(ENEMY_DIR)
	if dir != null:
		for file_name in dir.get_files():
			parts.append("%s:%d" % [file_name, FileAccess.get_modified_time(ENEMY_DIR + "/" + file_name)])
	return "|".join(parts)

## The 48 px icon of a library scene: the first frame of its sprite (nearest filtering is set by
## the item list). Null when the scene has no sprite.
static func icon_of(scene_path: String) -> Texture2D:
	var packed := load(scene_path) as PackedScene
	if packed == null:
		return null
	var inst := packed.instantiate()
	var tex := _first_texture(inst)
	inst.free()
	return tex

static func _first_texture(node: Node) -> Texture2D:
	if node is Sprite2D and (node as Sprite2D).texture != null:
		return (node as Sprite2D).texture
	if node is AnimatedSprite2D:
		var sprite := node as AnimatedSprite2D
		var frames := sprite.sprite_frames
		if frames != null:
			for anim in ["idle_down", "walk_down", "default"]:
				if frames.has_animation(anim) and frames.get_frame_count(anim) > 0:
					return frames.get_frame_texture(anim, 0)
			for anim in frames.get_animation_names():
				if frames.get_frame_count(anim) > 0:
					return frames.get_frame_texture(anim, 0)
	for child in node.get_children():
		var tex := _first_texture(child)
		if tex != null:
			return tex
	return null
