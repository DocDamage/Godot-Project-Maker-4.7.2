class_name RpgCreditsMenu
extends Control
## Credits, from the title screen and the pause menu: your own lines (game/data/credits_extra.tsv),
## the asset packs with their authors and licences (generated/data/credits.tres, rewritten by every
## build), and the engine. Up and down scroll the list; Back or cancel closes it.

const SCROLL_STEP := 24
const ENGINE_NAME := "Godot Engine"
const ENGINE_NOTICE := "© 2014-present Godot Engine contributors. © 2007-2014 Juan Linietsky, Ariel Manzur. MIT license."
const ENGINE_URL := "https://godotengine.org/license"

var credits: RpgCredits = null  # set before add_child to show other data (tests); else the project's

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	if credits == null:
		credits = RpgCredits.load_project()
	(get_node("%Back") as Button).pressed.connect(close)
	_fill()
	(get_node("%Back") as Button).grab_focus.call_deferred()

## The rows of the screen, in order: {text, heading} (a heading is a section title).
func credit_lines() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var sections: Array[String] = []
	var by_section := {}
	for row in credits.extra_lines():
		var section := str(row.get("section", ""))
		if not by_section.has(section):
			sections.append(section)
			by_section[section] = []
		var bucket: Array = by_section[section]
		bucket.append(str(row.get("text", "")))
	for section in sections:
		if section != "":
			out.append({"text": section, "heading": true})
		for text: String in by_section[section]:
			out.append({"text": text, "heading": false})
	if not credits.packs.is_empty():
		out.append({"text": tr("UI_CREDITS_ASSETS"), "heading": true})
		for pack in credits.packs:
			out.append_array(pack_lines(pack))
	out.append({"text": tr("UI_CREDITS_ENGINE"), "heading": true})
	out.append({"text": ENGINE_NAME, "heading": false})
	out.append({"text": ENGINE_NOTICE, "heading": false})
	out.append({"text": ENGINE_URL, "heading": false})
	return out

## A pack: "Name by Author", the licence (with its link) and the pack's URL.
func pack_lines(pack: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var author := str(pack.get("author", ""))
	var title := str(pack.get("name", ""))
	if author != "":
		title = tr("UI_CREDITS_BY") % [title, author]
	out.append({"text": title, "heading": false})
	var license := str(pack.get("license", ""))
	var license_url := str(pack.get("license_url", ""))
	if license_url != "":
		license += "  " + license_url
	if license != "":
		out.append({"text": license, "heading": false})
	var url := str(pack.get("url", ""))
	if url != "":
		out.append({"text": url, "heading": false})
	return out

func _fill() -> void:
	var list := get_node("%List") as VBoxContainer
	for child in list.get_children():
		list.remove_child(child)
		child.queue_free()
	var index := 0
	for row in credit_lines():
		var label := Label.new()
		label.name = "Line_%d" % index
		label.text = str(row["text"])
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		if row["heading"]:
			label.add_theme_color_override("font_color", Color("#f0d080"))
			if index > 0:
				label.add_theme_constant_override("line_spacing", 6)
		list.add_child(label)
		index += 1

## The texts of the lines on screen (tests and the smoke step read them).
func shown_texts() -> PackedStringArray:
	var out := PackedStringArray()
	for child in (get_node("%List") as VBoxContainer).get_children():
		if child is Label and not child.is_queued_for_deletion():
			out.append((child as Label).text)
	return out

func scroll_by(pixels: int) -> void:
	var scroll := get_node("%Scroll") as ScrollContainer
	scroll.scroll_vertical = maxi(0, scroll.scroll_vertical + pixels)

func _input(event: InputEvent) -> void:
	if not is_visible_in_tree():
		return
	if event.is_action_pressed("ui_down"):
		scroll_by(SCROLL_STEP)
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("ui_up"):
		scroll_by(-SCROLL_STEP)
		get_viewport().set_input_as_handled()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

func close() -> void:
	queue_free()
