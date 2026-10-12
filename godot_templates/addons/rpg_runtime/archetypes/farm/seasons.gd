class_name RpgFarmSeasons
extends Node
## What a season changes on a farm beside the crops (T17.11): the pictures of the ground and of
## the trees, and the music. A child of the farm's mode (`Seasons`), made by it.
##
## * **The pictures.** `generated/data/seasons.json` (recipes/farm/hud_recipe.gd writes it from
##   the catalog) has a group for every sheet the packs have once a season: the path of the
##   texture for each season, and under `""` the one that names no season. When an outdoor map
##   is entered and when the season changes, every texture of the map that is a member of a
##   group is replaced by the group's texture of the season: the `texture` of the atlas sources
##   of the tile sets of its TileMapLayers, the `texture` of its Sprite2Ds and the frames of its
##   AnimatedSprite2Ds (an AtlasTexture's `atlas` is replaced, its region stays). Nothing is
##   built again and no cell is painted: the sheets of a group have one size and one layout.
##   A season a group has no sheet for shows the sheet that names none, else the group's first.
##   A tile set is one resource for all the maps that use it, so an interior that shares a tile
##   set with an outdoor map shows the season too; interiors are otherwise left alone.
## * **The music.** After dark (from NIGHT_HOUR until the morning) the slot `music_night`, when
##   it is filled; else the slot of the season (`music_spring` ... `music_winter`); a season
##   without its own plays the first that is filled; a game with none of them filled keeps the
##   music of its maps. It plays on outdoor maps, in the place of the map's own music.

const NODE_NAME := "Seasons"
const TABLE_PATH := "res://generated/data/seasons.json"
const MUSIC_SLOTS: Array[StringName] = [&"music_spring", &"music_summer", &"music_autumn", &"music_winter"]
const NIGHT_SLOT := &"music_night"
## The hour the night's music begins; it ends with the day.
const NIGHT_HOUR := 20
const MORNING_HOUR := 6

## The groups of the table: [{season name or "": texture path}].
var groups: Array[Dictionary] = []
## The slot whose music this part started last, or &"".
var music_slot: StringName = &""

var _group_of: Dictionary = {}  # texture path -> index into `groups`
var _loaded := false
var _claimed := ""  # the map music the audio service was told is playing

## The seasons of the running game, or null in a game that is no farm.
static func current() -> RpgFarmSeasons:
	var mode := RpgFarmMode.current()
	return mode.seasons if mode != null else null

## Listens to the calendar and to the maps. The mode calls it once the calendar exists; a
## second call changes nothing.
func attach() -> void:
	var calendar := RpgCalendar.current()
	if calendar != null:
		if not calendar.season_changed.is_connected(_on_season):
			calendar.season_changed.connect(_on_season)
		if not calendar.hour_passed.is_connected(_on_hour):
			calendar.hour_passed.connect(_on_hour)
		if not calendar.day_began.is_connected(_on_hour):
			calendar.day_began.connect(_on_hour)
	var bus := RpgUtil.events()
	if bus != null and not bus.map_entered.is_connected(_on_map):
		bus.map_entered.connect(_on_map)

func _on_season(_season: int) -> void:
	apply_to_current()
	update_music()

func _on_hour(_hour: int) -> void:
	update_music()

func _on_map(_id: StringName) -> void:
	apply_to_current()
	update_music()

# ------------------------------------------------------------------ the table

## Reads the table once. A game without the file has no groups.
func load_table(path: String = TABLE_PATH) -> void:
	_loaded = true
	var raw: Variant = null
	if FileAccess.file_exists(path):
		raw = JSON.parse_string(FileAccess.get_file_as_string(path))
	set_table(RpgUtil.to_dict(RpgUtil.to_dict(raw).get("groups", {})))

## Takes the groups of a table: {id of the group's first sheet: {season or "": texture path}}.
func set_table(table: Dictionary) -> void:
	_loaded = true
	groups.clear()
	_group_of.clear()
	var ids: Array = table.keys()
	ids.sort()
	for id: Variant in ids:
		var group := {}
		var raw := RpgUtil.to_dict(table[id])
		for season: Variant in raw.keys():
			group[RpgUtil.to_str(season)] = RpgUtil.to_str(raw[season])
		if group.size() < 2:
			continue
		for path: String in group.values():
			_group_of[path] = groups.size()
		groups.append(group)

## The path of the texture that stands for `path` in the season of this name; `path` itself
## when it is in no group.
func path_for(path: String, season_name: String) -> String:
	if not _group_of.has(path):
		return path
	var group: Dictionary = groups[RpgUtil.to_int(_group_of[path])]
	if group.has(season_name):
		return RpgUtil.to_str(group[season_name])
	if group.has(""):
		return RpgUtil.to_str(group[""])
	var names: Array = group.keys()
	names.sort()
	return RpgUtil.to_str(group[names[0]])

# ------------------------------------------------------------------ the pictures

## Shows the map of the game in the season of the calendar.
func apply_to_current() -> int:
	var router := RpgUtil.router()
	var calendar := RpgCalendar.current()
	if router == null or router.current_map == null or calendar == null:
		return 0
	return apply(router.current_map, calendar.season_name())

## Shows `map` in the season of this name. Returns how many textures were replaced. An interior
## is left alone.
func apply(map: Node, season_name: String) -> int:
	if not _loaded:
		load_table()
	var root := map as RpgMapRoot
	if map == null or groups.is_empty() or (root != null and root.interior()):
		return 0
	var seen := {}
	return _apply_node(map, season_name, seen)

func _apply_node(node: Node, season_name: String, seen: Dictionary) -> int:
	var count := 0
	if node is TileMapLayer:
		var tiles := (node as TileMapLayer).tile_set
		if tiles != null and not seen.has(tiles):
			seen[tiles] = true
			for i in tiles.get_source_count():
				var atlas := tiles.get_source(tiles.get_source_id(i)) as TileSetAtlasSource
				if atlas == null:
					continue
				var tile_texture := _replacement(atlas.texture, season_name, seen)
				if tile_texture != null:
					atlas.texture = tile_texture
					count += 1
	elif node is Sprite2D:
		var sprite := node as Sprite2D
		var sprite_texture := _replacement(sprite.texture, season_name, seen)
		if sprite_texture != null:
			sprite.texture = sprite_texture
			count += 1
	elif node is AnimatedSprite2D:
		var frames := (node as AnimatedSprite2D).sprite_frames
		if frames != null and not seen.has(frames):
			seen[frames] = true
			for animation in frames.get_animation_names():
				for i in frames.get_frame_count(animation):
					var frame_texture := _replacement(frames.get_frame_texture(animation, i), season_name, seen)
					if frame_texture != null:
						frames.set_frame(animation, i, frame_texture, frames.get_frame_duration(animation, i))
						count += 1
	for child in node.get_children():
		count += _apply_node(child, season_name, seen)
	return count

## What a texture is replaced by, or null when it stays. An AtlasTexture whose `atlas` is
## replaced is returned itself: it stays where it is, with another picture.
func _replacement(texture: Texture2D, season_name: String, seen: Dictionary) -> Texture2D:
	if texture == null:
		return null
	if texture is AtlasTexture:
		var part := texture as AtlasTexture
		if seen.has(part):
			return null
		seen[part] = true
		var inner := _replacement(part.atlas, season_name, seen)
		if inner == null:
			return null
		part.atlas = inner
		return part
	var path := texture.resource_path
	var wanted := path_for(path, season_name)
	if wanted == path or not ResourceLoader.exists(wanted):
		return null
	return load(wanted) as Texture2D

# ------------------------------------------------------------------ the music

## True at an hour (what a clock shows) of the night.
static func is_night(hour: int) -> bool:
	return hour >= NIGHT_HOUR or hour < MORNING_HOUR

## The slot whose music plays in a season (0 to 3) at an hour, of the slots `filled` knows
## (`func(slot: StringName) -> bool`), or &"" when none of them is filled.
static func slot_for(season: int, hour: int, filled: Callable) -> StringName:
	if is_night(hour) and filled.call(NIGHT_SLOT):
		return NIGHT_SLOT
	var own := MUSIC_SLOTS[posmod(season, MUSIC_SLOTS.size())]
	if filled.call(own):
		return own
	for slot in MUSIC_SLOTS:
		if filled.call(slot):
			return slot
	return &""

## Starts the music of the season and the hour on an outdoor map, unless it plays already.
func update_music() -> void:
	var router := RpgUtil.router()
	var calendar := RpgCalendar.current()
	var audio := router.audio as RpgAudio if router != null else null
	if audio == null or calendar == null or router.current_map == null or router.current_map.interior():
		return
	var wanted := slot_for(calendar.season, calendar.clock()[0], audio.bank.has_slot)
	if wanted == &"":
		return
	if wanted == music_slot and audio.current_music_id == _claimed:
		return
	audio.play_music_slot(wanted)
	music_slot = wanted
	# the router starts a map's music when another id is playing: it is told the map's plays,
	# so walking from one outdoor map to the next does not start the season's music again
	_claimed = str(router.current_map.music_asset_id)
	audio.current_music_id = _claimed
