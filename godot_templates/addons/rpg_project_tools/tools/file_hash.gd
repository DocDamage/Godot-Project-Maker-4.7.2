@tool
extends RefCounted
## GDScript port of rpggen.core.ledger.file_hash: sha256 of the file bytes; text files (by
## extension, or by name for dotfiles) are hashed after CRLF -> LF. The test vectors in
## tests/fixtures/hash_vectors.json are checked by both implementations.

const TEXT_EXTS := [".gd", ".tscn", ".tres", ".json", ".cfg", ".godot", ".md", ".import", ".uid", ".txt", ".csv", ".gitignore", ".gitattributes"]

static func is_text(file_name: String) -> bool:
	var lower := file_name.to_lower()
	var dot := lower.rfind(".")
	var ext := lower.substr(dot) if dot > 0 else ""
	return TEXT_EXTS.has(ext) or lower in [".gitignore", ".gitattributes"]

## Hash of bytes already read, as `file_hash` would compute for a file called `file_name`.
static func bytes_hash(bytes: PackedByteArray, file_name: String) -> String:
	if is_text(file_name) and bytes.find(13) != -1:
		bytes = bytes.get_string_from_utf8().replace("\r\n", "\n").to_utf8_buffer()
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(bytes)
	return ctx.finish().hex_encode()

## Hash of a file ("" when it cannot be read).
static func file_hash(path: String) -> String:
	if not FileAccess.file_exists(path):
		return ""
	return bytes_hash(FileAccess.get_file_as_bytes(path), path.get_file())
