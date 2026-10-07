extends RefCounted

const FileHash := preload("res://addons/rpg_project_tools/tools/file_hash.gd")
const JsonIo := preload("res://addons/rpg_project_tools/tools/json_io.gd")
const FIXTURE := "res://tests/fixtures/hash_vectors.json"
const TMP := "user://m8_hash_test"

func test_file_hash_matches_the_python_vectors(t) -> void:
	var vectors: Variant = JsonIo.read(FIXTURE)
	t.ok(vectors is Array and vectors.size() > 0, "fixture loads")
	DirAccess.make_dir_recursive_absolute(TMP)
	for v in vectors:
		var path: String = TMP + "/" + String(v["file"])
		var f := FileAccess.open(path, FileAccess.WRITE)
		f.store_buffer(String(v["hex"]).hex_decode())
		f.close()
		t.eq(FileHash.file_hash(path), v["sha256"], "vector '%s'" % v["name"])
		DirAccess.remove_absolute(path)

func test_is_text(t) -> void:
	t.ok(FileHash.is_text("a.gd"))
	t.ok(FileHash.is_text("A.TSCN"))
	t.ok(FileHash.is_text(".gitignore"))
	t.ok(FileHash.is_text("x.backup.tres"))
	t.ok(not FileHash.is_text("pic.png"))
	t.ok(not FileHash.is_text("LICENSE"))
	t.ok(not FileHash.is_text(".gd"))

func test_missing_file_has_no_hash(t) -> void:
	t.eq(FileHash.file_hash("user://m8_hash_test/does_not_exist.gd"), "")
