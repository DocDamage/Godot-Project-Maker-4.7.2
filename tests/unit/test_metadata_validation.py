from __future__ import annotations

from PIL import Image

from rpggen.core import catalog, metadata_validation


def _cat(facets: dict) -> catalog.Catalog:
    return catalog.Catalog(
        assets=[
            catalog.Asset(
                id="p.sprite",
                pack_id="p",
                path="assets/packs/p/sprite.png",
                sha256="0" * 64,
                kind="image",
                status="NEEDS_REVIEW",
                detected=facets,
            )
        ]
    )


def test_animation_checks_use_the_named_source_and_preserve_trim_padding(tmp_path):
    base, alternate = tmp_path / "base.png", tmp_path / "alternate.png"
    Image.new("RGBA", (16, 16)).save(base)
    Image.new("RGBA", (64, 32)).save(alternate)
    facets = {
        "usage": "sprite",
        "frame": [32, 32],
        "animations": {
            "idle": {
                "frames": [],
                "rects": [[40, 2, 20, 24]],
                "offsets": [[4, 8]],
                "source": "other.png",
                "fps": 8,
                "loop": True,
                "durations": [1.5],
            }
        },
    }

    def resolve(path):
        return alternate if path == "other.png" else base

    report = metadata_validation.validate_images(_cat(facets), resolve)
    assert report["passed"] and report["frames"] == 1 and report["image_headers"] == 2
    facets["animations"]["idle"]["offsets"] = [[20, 8]]
    assert (
        metadata_validation.validate_images(_cat(facets), resolve)["failures"][0]["code"]
        == "frame_outside_canvas"
    )


def test_bad_frame_indices_timing_missing_images_and_crop_completeness(tmp_path):
    file = tmp_path / "sheet.png"
    Image.new("RGBA", (32, 16)).save(file)
    cat = _cat(
        {
            "usage": "sprite",
            "frame": [16, 16],
            "animations": {
                "walk": {
                    "frames": [[0, 0], [2, 0]],
                    "fps": 0,
                    "loop": True,
                    "durations": [float("nan")],
                    "active_frames": [2],
                }
            },
        }
    )
    result = metadata_validation.validate_images(cat, lambda _: file)
    assert {f["code"] for f in result["failures"]} == {
        "animation_speed",
        "animation_durations",
        "active_frame_index",
        "frame_outside_image",
    }
    assert not metadata_validation.validate_images(cat, lambda _: None)["passed"]
    cat.assets[0].detected = {"usage": "growth_strip", "frame": [16, 16], "stages": 3}
    assert (
        metadata_validation.validate_images(cat, lambda _: file)["failures"][0]["code"]
        == "crop_strip_size"
    )
    cat.assets[0].detected["stages"] = 2
    assert metadata_validation.validate_images(cat, lambda _: file)["passed"]
    cat.assets[0].status = "UNUSED"
    assert metadata_validation.validate_images(cat, lambda _: None)["images"] == 0


def test_metadata_cli_saves_a_report_and_returns_failure_without_changing_catalog(tmp_path):
    from rpggen import jsonio
    from tools import validate_metadata

    Image.new("RGBA", (32, 16)).save(tmp_path / "sprite.png")
    cat = _cat({"usage": "growth_strip", "role": "CROP", "frame": [16, 16], "stages": 2})
    source = tmp_path / "catalog.json"
    catalog.save(cat, source)
    original = source.read_bytes()
    report = tmp_path / "report.json"
    args = ["--catalog", str(source), "--root", f"p={tmp_path}", "--out", str(report)]
    assert validate_metadata.main(args) == 0
    assert jsonio.read(report)["passed"]
    Image.new("RGBA", (16, 16)).save(tmp_path / "sprite.png")
    assert validate_metadata.main(args) == 1
    assert not jsonio.read(report)["passed"]
    assert source.read_bytes() == original
