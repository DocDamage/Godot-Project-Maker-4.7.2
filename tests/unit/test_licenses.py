"""Pack licences from the licence files, the catalog fields and ASSET-028 (T12.51)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.core import licenses, requirements
from rpggen.core.licenses import PackLicense

TEXTS = Path(__file__).parent / "license_texts"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (
            "cc_by_readme.txt",
            PackLicense("CC-BY-4.0", "Jane Doe", "https://janedoe.itch.io/forest", True),
        ),
        ("cc_by_sa_license.txt", PackLicense("CC-BY-SA-3.0", "Ann Lee", "", True)),
        ("cc0_license.txt", PackLicense("CC0-1.0", "", "", False)),
        ("mit_license.txt", PackLicense("MIT", "Kit Pixel", "", True)),
        (
            "oga_credits.txt",
            PackLicense("OGA-BY-3.0", "Buch", "http://opengameart.org/users/buch", True),
        ),
        ("rpgmaker_terms.txt", PackLicense("rpgmaker", "", "", False)),
        (
            "commercial_license.html",
            PackLicense("commercial", "Fox Studio", "https://foxstudio.example.com", True),
        ),
        ("readme_nothing.txt", PackLicense()),
    ],
)
def test_detection_on_fixture_texts(name: str, expected: PackLicense) -> None:
    assert licenses.detect_files(TEXTS, [name]) == expected


def test_licence_files_win_over_readmes_and_fill_in_each_other() -> None:
    found = licenses.detect(
        [
            ("readme.txt", "Thanks!\nAuthor: Sam Reed\nLicense: CC0"),
            ("LICENSE.txt", "Creative Commons Attribution 4.0"),
        ]
    )
    assert found == PackLicense("CC-BY-4.0", "Sam Reed", "", True)


def test_wording_decides_for_a_vendor_licence() -> None:
    free = licenses.detect([("license.txt", "Free for commercial use. No credit required.")])
    assert free == PackLicense("commercial", "", "", False)
    asked = licenses.detect([("license.txt", "Commercial use is allowed. Credit is required.")])
    assert asked.attribution_required
    # a licence with a rule of its own wins: CC0 that asks politely for credit still needs none
    polite = licenses.detect([("license.txt", "CC0. Please credit me if you like.")])
    assert polite == PackLicense("CC0-1.0", "", "", False)


@pytest.mark.parametrize(
    "text",
    [
        "YOU CAN USE THE ASSET IN NON COMMERCIAL PROJECTS\n"
        "YOU CAN'T USE THE ASSET IN COMMERCIAL PROJECTS",
        "You may not use this art in commercial games.",
        "Commercial use is not permitted.",
        "Only for non-commercial use.",
        "Noncommercial projects only.",
        "You can’t use these in commercial games.",
    ],
)
def test_restricted_custom_terms_are_not_a_commercial_grant(text: str) -> None:
    found = licenses.detect([("LICENSE.txt", text), ("readme.txt", "Free for commercial use")])
    assert found.license_id == licenses.NONCOMMERCIAL
    assert licenses.label(found.license_id) == "Non-commercial use only"
    assert licenses.license_url(found.license_id) == ""


@pytest.mark.parametrize(
    "text",
    [
        "You can use this in commercial and non-commercial projects.",
        "Free for commercial use. You cannot resell the assets.",
        "Commercial use is allowed. Non-commercial use is allowed too.",
        "You can use this in commercial games. You cannot resell the assets for commercial use.",
    ],
)
def test_commercial_permission_is_preserved_when_terms_also_mention_restrictions(text: str) -> None:
    assert licenses.detect([("LICENSE.txt", text)]).license_id == licenses.COMMERCIAL


@pytest.mark.parametrize("word", ["non-commercial", "non commercial", "noncommercial"])
def test_noncommercial_permission_alone_does_not_grant_commercial_use(word: str) -> None:
    assert licenses.detect([("LICENSE", f"Free for {word} use.")]).license_id != licenses.COMMERCIAL


@pytest.mark.parametrize("negative", ["can't", "may not"])
def test_resale_prohibition_alone_does_not_grant_commercial_permission(negative: str) -> None:
    found = licenses.detect([("LICENSE", f"You {negative} resell these for commercial purposes.")])
    assert found.license_id == licenses.UNKNOWN


@pytest.mark.parametrize(
    ("text", "license_id"),
    [
        ("CC BY-SA 4.0", "CC-BY-SA-4.0"),
        ("cc-by-nc-sa 3.0", "CC-BY-NC-SA-3.0"),
        ("https://creativecommons.org/licenses/by-nd/4.0/", "CC-BY-ND-4.0"),
        ("Creative Commons Attribution-NonCommercial 4.0", "CC-BY-NC-4.0"),
        ("Licensed CC-BY", "CC-BY-4.0"),
        ("cc by sample tiles", "CC-BY-4.0"),
    ],
)
def test_creative_commons_variants(text: str, license_id: str) -> None:
    assert licenses.detect([("LICENSE", text)]).license_id == license_id


def test_read_text_skips_binary_files_and_strips_markup(tmp_path) -> None:
    (tmp_path / "license.pdf").write_bytes(b"%PDF CC-BY")
    (tmp_path / "license.txt").write_bytes(b"caf\xe9 CC0")  # not UTF-8
    (tmp_path / "license.rtf").write_text(r"{\rtf1\ansi Author: Rae\par CC0}")
    assert licenses.read_text(tmp_path / "license.pdf") == ""
    assert "CC0" in licenses.read_text(tmp_path / "license.txt")
    assert licenses.detect_files(tmp_path, ["license.rtf"]).author == "Rae"
    assert licenses.read_text(tmp_path / "missing.txt") == ""


def test_labels_and_links() -> None:
    assert licenses.label("CC-BY-SA-4.0") == "CC BY-SA 4.0"
    assert licenses.label("CC0-1.0") == "CC0 1.0"
    assert licenses.label("OGA-BY-3.0") == "OGA-BY 3.0"
    assert licenses.label("") == "Unknown licence"
    assert licenses.license_url("CC-BY-NC-4.0") == "https://creativecommons.org/licenses/by-nc/4.0/"
    assert licenses.license_url("commercial") == ""


def test_effective_takes_the_corrections() -> None:
    detected = PackLicense("CC-BY-4.0", "", "", True).to_json()
    assert licenses.effective(detected, {"author": "Lee"}).author == "Lee"
    # a licence chosen by hand brings its own credit rule unless that was set too
    assert not licenses.effective(detected, {"license_id": "CC0-1.0"}).attribution_required
    both = {"license_id": "CC0-1.0", "attribution_required": True}
    assert licenses.effective(detected, both).attribution_required
    assert licenses.effective(None, None) == PackLicense()


def _pack(**changes) -> catalog_mod.CatalogPack:
    pack = catalog_mod.CatalogPack("forest", "abc", "assets/packs/forest", ["LICENSE.txt"])
    for key, value in changes.items():
        setattr(pack, key, value)
    return pack


def test_catalog_packs_round_trip_the_licence() -> None:
    pack = _pack(
        license=PackLicense("CC-BY-4.0", "", "", True).to_json(),
        license_overrides={"author": "Jane"},
    )
    data = pack.to_json()
    assert data["license"]["license_id"] == "CC-BY-4.0"
    assert data["license_overrides"] == {"author": "Jane"}
    back = catalog_mod.CatalogPack.from_json(data)
    assert back.effective_license() == PackLicense("CC-BY-4.0", "Jane", "", True)
    assert "license_overrides" not in _pack().to_json()  # written only when there are some


def test_an_older_catalog_without_licences_still_loads(tmp_path) -> None:
    cat = catalog_mod.Catalog(packs=[_pack()])
    data = cat.to_json()
    for pack in data["packs"]:
        del pack["license"]
    from rpggen import jsonio

    jsonio.write(tmp_path / "catalog.json", data)
    loaded = catalog_mod.load(tmp_path / "catalog.json")
    assert loaded.packs[0].effective_license() == PackLicense()


def test_asset_028_when_credit_is_required_but_no_author_is_known() -> None:
    cfg = config_mod.default_for("T", [])
    needs = _pack(license=PackLicense("CC-BY-4.0", "", "", True).to_json())
    codes = [i.code for i in requirements.check(catalog_mod.Catalog(packs=[needs]), cfg)]
    assert "ASSET-028" in codes
    needs.license_overrides = {"author": "Jane"}
    codes = [i.code for i in requirements.check(catalog_mod.Catalog(packs=[needs]), cfg)]
    assert "ASSET-028" not in codes
    free = _pack(license=PackLicense("CC0-1.0").to_json())
    codes = [i.code for i in requirements.check(catalog_mod.Catalog(packs=[free]), cfg)]
    assert "ASSET-028" not in codes
