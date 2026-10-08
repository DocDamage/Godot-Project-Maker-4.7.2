class_name RpgCredits
extends Resource
## What the Credits screen lists. The builder writes it on every build (generated/data/credits.tres)
## from the licences of the asset packs, as the Audit page shows them, and from
## game/data/credits_extra.tsv, the lines of your own (a tab between a section and a line).

const PATH := "res://generated/data/credits.tres"
const EXTRA_PATH := "res://game/data/credits_extra.tsv"
const EXTRA_HEADER := "section\ttext"

## One per pack: {name, author, license, license_url, url, attribution_required}.
@export var packs: Array[Dictionary] = []
## {section, text} from credits_extra.tsv at build time (an exported game has no .tsv file).
@export var extra: Array[Dictionary] = []

## The credits of the project, or an empty set when the builder has not written them.
static func load_project() -> RpgCredits:
	if ResourceLoader.exists(PATH):
		var found := load(PATH) as RpgCredits
		if found != null:
			return found
	return RpgCredits.new()

## {section, text} rows of a credits_extra.tsv text. Empty lines, lines starting with "#" and the
## header are skipped; a line without a tab is a line without a section.
static func parse_extra(text: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw in text.split("\n"):
		var line := raw.strip_edges(false, true)
		if line.strip_edges() == "" or line.strip_edges().begins_with("#") or line == EXTRA_HEADER:
			continue
		var cut := line.find("\t")
		var section := line.substr(0, cut).strip_edges() if cut >= 0 else ""
		var text_part := line.substr(cut + 1).strip_edges() if cut >= 0 else line.strip_edges()
		if text_part != "":
			out.append({"section": section, "text": text_part})
	return out

## Your own lines: read from the .tsv when the project has it (a run from the editor shows an edit
## at once), else the lines the last build baked in.
func extra_lines() -> Array[Dictionary]:
	if FileAccess.file_exists(EXTRA_PATH):
		return parse_extra(FileAccess.get_file_as_string(EXTRA_PATH))
	return extra
