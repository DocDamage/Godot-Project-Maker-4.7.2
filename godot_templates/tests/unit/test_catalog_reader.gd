extends RefCounted

const CatalogReader := preload("../../builder/lib/catalog_reader.gd")
const JsonUtil := preload("../../builder/lib/json_util.gd")
const FIXTURE := "res://tests/fixtures/effective_cases.json"

func test_effective_matches_shared_fixture(t) -> void:
	var cases: Variant = JsonUtil.read(FIXTURE)
	t.ok(cases is Array and cases.size() > 0, "fixture loads")
	for c in cases:
		var got := CatalogReader.effective(c["asset"])
		t.eq(got, c["expected"], "case '%s'" % c["name"])

func test_assets_by_role_sorted_by_id(t) -> void:
	var reader := CatalogReader.new({
		"assets": [
			{"id": "p.b", "detected": {"role": "GROUND"}, "overrides": {}},
			{"id": "p.a", "detected": {"role": "GROUND"}, "overrides": {}},
			{"id": "p.c", "detected": {"role": "GROUND"}, "overrides": {"role": "WALL"}},
		],
		"tilesets": [{"name": "z"}, {"name": "a"}],
	})
	var ground := reader.assets_by_role("GROUND")
	t.eq(ground.size(), 2)
	t.eq(ground[0]["id"], "p.a")
	t.eq(ground[1]["id"], "p.b")
	t.eq(reader.assets_by_role("WALL")[0]["id"], "p.c")
	t.eq(reader.asset("p.b")["id"], "p.b")
	t.eq(reader.asset("nope"), {})
	t.eq(reader.tileset_defs()[0]["name"], "a")

func test_merge_does_not_mutate_inputs(t) -> void:
	var base := {"grid": {"cell": [16, 16]}}
	var over := {"grid": {"cell": null, "margin": [1, 1]}}
	var out := CatalogReader.merge(base, over)
	t.eq(base, {"grid": {"cell": [16, 16]}})
	t.eq(out, {"grid": {"margin": [1, 1]}})

## An asset is found by its id through an index (2026-10-26), and the index follows the
## catalog: a list replaced or grown is indexed again, an entry changed in place is found by its
## new id, a missing id is none; the first of two assets of one id is the one found, as before.
func test_asset_by_id_follows_the_catalog(t) -> void:
	var cat := {"assets": [{"id": "a", "n": 1}, {"id": "b", "n": 2}, {"id": "a", "n": 3}]}
	var reader := CatalogReader.new(cat)
	t.eq(reader.asset("b")["n"], 2)
	t.eq(reader.asset("a")["n"], 1, "the first of one id")
	t.eq(reader.asset("z"), {}, "none")
	(cat["assets"] as Array).append({"id": "c", "n": 4})
	t.eq(reader.asset("c")["n"], 4, "a list that grew")
	cat["assets"] = [{"id": "d", "n": 5}]
	t.eq(reader.asset("d")["n"], 5, "another list")
	t.eq(reader.asset("a"), {}, "gone with the old list")
	(cat["assets"] as Array)[0]["id"] = "e"
	t.eq(reader.asset("e")["n"], 5, "an entry changed in place")
	t.eq(reader.asset("d"), {}, "not by its old id")
