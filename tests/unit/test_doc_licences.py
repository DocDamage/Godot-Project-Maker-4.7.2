"""A licence read from a documentation file, and the credit it asks for in the README (T17.29)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from rpggen.core import archive, catalog, config, inventory, licenses, staging
from rpggen.core.licenses import PackLicense

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"

# worded as the two real packs word theirs
MANDATORY = """Full version license:

These asset packs can be used in any commercial or non-commercial project.
They cannot be resold or redistributed, even if modified.

Credits are mandatory: You can credit me by linking to my Itch.io page: someartist.itch.io.

You can be credited as "SomeArtist".

- someartist@example.com
"""
APPRECIATED = """FARM PACK LICENSE
-
YOU CAN:
-Use the asset in any commercial or non commercial project
-
YOU CAN'T:
- Resell or distribute the asset to others
-
- Credits much appreciated (shopname.itch.io)
"""


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _write(root: Path, rel: str, text: str | bytes) -> None:
    path = root.joinpath(*rel.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")


def _assemble(source: Path):
    opened = archive.open_pack(source, set())
    inv = inventory.build_inventory(opened)
    cat, issues, _generated = catalog.assemble([(opened, inv)], None, [], use_cache=False)
    return cat, [i.code for i in issues]


# --------------------------------------------------------------------------- the wording


def test_mandatory_credit_with_the_name_to_credit_and_a_page_without_its_scheme() -> None:
    found = licenses.detect([("Documentation.txt", MANDATORY)])
    assert found == PackLicense(
        licenses.COMMERCIAL, "SomeArtist", "https://someartist.itch.io", True
    )


def test_credit_appreciated_is_not_required_and_the_shop_names_the_author() -> None:
    found = licenses.detect([("LICENSE.txt", APPRECIATED)])
    assert found == PackLicense(licenses.COMMERCIAL, "shopname", "https://shopname.itch.io", False)


def test_a_bare_page_does_not_repeat_a_full_one_and_a_mail_is_no_page() -> None:
    text = (
        "Made by Jane.\nhttps://jane.itch.io/forest\njane.itch.io/forest\nmail: me@jane.itch.io\n"
    )
    found = licenses._scan(text)
    assert found.urls == ["https://jane.itch.io/forest"]


def test_credits_are_required_says_so() -> None:
    assert licenses._scan("Credits are required.").attribution is True
    assert licenses._scan("Credit is appreciated but not required.").attribution is False


# --------------------------------------------------------------------------- the files


def _kinds(root: Path) -> list[tuple[str, str]]:
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    return [(rel, inventory.classify_kind(rel)) for rel in files]


def test_a_documentation_file_at_the_root_or_one_folder_down_is_a_licence(tmp_path: Path) -> None:
    _write(tmp_path, "Documentation.txt", MANDATORY)
    _write(tmp_path, "Wrapper/Terms of use.md", "Commercial use is allowed.")
    _write(tmp_path, "Wrapper/About.txt", "A pack of farm tiles. Have fun!")  # says nothing
    _write(tmp_path, "Wrapper/Tiles/Info.txt", "Credit me, licence CC-BY.")  # two folders down
    _write(tmp_path, "Wrapper/Changelog.txt", "v1.1: licence file reworded")  # not its name
    _write(tmp_path, "Wrapper/Tile information.txt", "credit")  # "info" is not where it begins
    assert licenses.doc_licence_files(tmp_path, _kinds(tmp_path)) == [
        "Documentation.txt",
        "Wrapper/Terms of use.md",
    ]


def test_the_folder_of_a_nested_archive_does_not_count_as_a_folder(tmp_path: Path) -> None:
    _write(tmp_path, "Wrapper/inner_extracted/Read me.txt", "Credits are mandatory.")
    _write(tmp_path, "Wrapper/inner_extracted/sub/Info.txt", "Credits are mandatory.")
    assert licenses.doc_licence_files(tmp_path, _kinds(tmp_path)) == [
        "Wrapper/inner_extracted/Read me.txt"
    ]


def test_a_pack_with_its_licence_in_its_documentation_has_a_licence(tmp_path: Path) -> None:
    pack = tmp_path / "Farm Pack"
    _write(pack, "Farm Pack/Documentation.txt", MANDATORY)
    for rel in ("Farm Pack/Tiles/terrain.png",):
        _write(pack, rel, (SYNTH / "basic16" / "tiles" / "terrain.png").read_bytes())
    cat, codes = _assemble(pack)
    assert "ASSET-021" not in codes
    (found,) = cat.packs
    assert found.license_files == [f"{found.root}/Farm Pack/Documentation.txt"]
    assert found.effective_license() == PackLicense(
        licenses.COMMERCIAL, "SomeArtist", "https://someartist.itch.io", True
    )


def test_a_documentation_that_says_nothing_of_a_licence_is_none(tmp_path: Path) -> None:
    pack = tmp_path / "Plain"
    _write(pack, "Plain/Documentation.txt", "Tiles are 16 x 16.")
    _write(pack, "Plain/Tiles/terrain.png", (SYNTH / "basic16/tiles/terrain.png").read_bytes())
    cat, codes = _assemble(pack)
    assert "ASSET-021" in codes and cat.packs[0].license_files == []


def _zip_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as zf:
        for name, content in entries:
            zf.writestr(name, content)
    return data.getvalue()


def test_a_licence_at_the_root_of_a_zip_or_of_a_zip_in_it_is_found(tmp_path: Path) -> None:
    terrain = (SYNTH / "basic16" / "tiles" / "terrain.png").read_bytes()
    inner = _zip_bytes([("Terms.txt", APPRECIATED.encode()), ("tiles/b.png", terrain)])
    outer = tmp_path / "pack.zip"
    outer.write_bytes(_zip_bytes([("Wrapper/tiles/a.png", terrain), ("Wrapper/more.zip", inner)]))
    cat, codes = _assemble(outer)
    assert "ASSET-021" not in codes
    root = cat.packs[0].root
    assert cat.packs[0].license_files == [f"{root}/Wrapper/more_extracted/Terms.txt"]
    assert cat.packs[0].effective_license().url == "https://shopname.itch.io"


def test_the_synthetic_pack_of_a_licence_in_a_documentation_file() -> None:
    cat, codes = _assemble(SYNTH / "doc_licence")
    assert "ASSET-021" not in codes
    (pack,) = cat.packs
    assert pack.license_files == [f"{pack.root}/Doc Licence Pack/Documentation.txt"]
    assert pack.effective_license() == PackLicense(
        licenses.COMMERCIAL, "Synth Artist", "https://synthartist.itch.io", True
    )


# --------------------------------------------------------------------------- the README

TEMPLATE = (
    "{project_name}{archetype}{opening}{runtime_version}{godot_version}{kind_note}"
    "{version_control_note}{custom_sound_slots}\nPacks:\n\n{packs_list}\n\n## 1. Quick start\n"
)


def _catalog(*packs: tuple[str, PackLicense]) -> catalog.Catalog:
    cat = catalog.Catalog()
    for pack_id, found in packs:
        cat.packs.append(catalog.CatalogPack(pack_id, "0" * 64, f"assets/packs/{pack_id}"))
        cat.packs[-1].license = found.to_json()
    return cat


def test_the_readme_lists_the_credits_the_licences_require() -> None:
    refs = [config.PackRef(p, "x", "0" * 64, "folder") for p in ("farm_rpg", "kenney", "lime")]
    cfg = config.default_for("Green Acre", refs, archetype="farm")
    cat = _catalog(
        ("farm_rpg", PackLicense(licenses.COMMERCIAL, "EmanuelleDev", "https://e.itch.io", True)),
        ("kenney", PackLicense("CC0-1.0", "Kenney", "", False)),
        ("lime", PackLicense("CC-BY-4.0", "", "", True)),
    )
    text = staging.render_readme(TEMPLATE, cfg, "1.0.0", "", cat)
    assert (
        "- farm_rpg\n- kenney\n- lime\n\n### Credits\n\n"
        "The licences of these packs require credit. Keep it in your game and on its page; the\n"
        "game's Credits screen shows it.\n\n"
        "- **farm_rpg**: EmanuelleDev — Commercial licence — https://e.itch.io\n"
        "- **lime**: author not named (see its licence file) — CC BY 4.0\n\n## 1. Quick start\n"
    ) in text
    assert "**kenney**" not in text


def test_a_correction_on_the_audit_page_is_what_the_readme_says() -> None:
    cfg = config.default_for("G", [config.PackRef("p", "x", "0" * 64, "folder")])
    cat = _catalog(("p", PackLicense(licenses.COMMERCIAL, "", "", True)))
    cat.packs[0].license_overrides = {"attribution_required": False}
    assert "### Credits" not in staging.render_readme(TEMPLATE, cfg, "1.0.0", "", cat)


def test_a_readme_whose_packs_ask_no_credit_is_what_it_was() -> None:
    cfg = config.default_for("G", [config.PackRef("p", "x", "0" * 64, "folder")])
    cat = _catalog(("p", PackLicense("CC0-1.0", "Kenney", "", False)))
    before = staging.render_readme(TEMPLATE, cfg, "1.0.0")
    assert staging.render_readme(TEMPLATE, cfg, "1.0.0", "", cat) == before


def test_the_written_readme_has_the_credits(tmp_path: Path) -> None:
    cfg = config.default_for("G", [config.PackRef("p", "x", "0" * 64, "folder")])
    cat = _catalog(("p", PackLicense(licenses.COMMERCIAL, "Ann", "https://ann.itch.io", True)))
    stg = staging.create_staging(tmp_path / "g")
    staging.write_project_files(stg, cfg, cat)
    text = (stg.staging / "README.md").read_text(encoding="utf-8")
    assert "- p\n\n### Credits\n" in text
    assert "- **p**: Ann — Commercial licence — https://ann.itch.io\n\n## 1. Quick start" in text
