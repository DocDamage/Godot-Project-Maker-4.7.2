from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rpggen import __version__, godot_target, jsonio, schema
from rpggen.errors import RpgGenError

CONFIG_VERSION = 1
GODOT_VERSION = godot_target.VERSION
DEFAULT_MAP_LAYERS = ["Ground", "GroundDetails", "Walls", "Props", "Overhead"]
GIT_DEFAULTS = {"pack_art": "commit"}
PACK_ART_CHOICES = ("commit", "lfs", "ignore")
# export targets in their fixed order (the presets in export_check.TARGETS follow it)
EXPORT_TARGETS = ("windows", "web", "linux", "macos")
EXPORT_TARGET_DEFAULT = ("windows",)
FEATURE_KEYS = (
    "tilesets",
    "collision",
    "terrain",
    "animations",
    "demo",
    "editor_tools",
    "save",
    "dialogue",
    "combat",
    "navigation",
    "debug_tools",
)


@dataclass(frozen=True, slots=True)
class PackRef:
    pack_id: str
    source: str  # absolute path as the user gave it; informational only
    source_sha256: str
    kind: str  # "zip" | "7z" | "folder"

    def to_json(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "source": self.source,
            "source_sha256": self.source_sha256,
            "kind": self.kind,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> PackRef:
        return cls(data["pack_id"], data["source"], data["source_sha256"], data["kind"])


def default_input(archetype: str) -> dict[str, dict[str, Any]]:
    """Default input bindings (02_SCHEMAS §1.1) for the archetype."""
    bindings: dict[str, dict[str, Any]] = {
        "move_up": {"keys": ["W", "Up"], "joy_buttons": [11], "joy_axes": [[1, -1.0]]},
        "move_down": {"keys": ["S", "Down"], "joy_buttons": [12], "joy_axes": [[1, 1.0]]},
        "move_left": {"keys": ["A", "Left"], "joy_buttons": [13], "joy_axes": [[0, -1.0]]},
        "move_right": {"keys": ["D", "Right"], "joy_buttons": [14], "joy_axes": [[0, 1.0]]},
        "interact": {"keys": ["E", "Space"], "joy_buttons": [0]},
        "confirm": {"keys": ["Enter", "Space"], "joy_buttons": [0]},
        "cancel": {"keys": ["Escape", "Backspace"], "joy_buttons": [1]},
        "menu": {"keys": ["Escape", "Tab"], "joy_buttons": [6]},
    }
    if archetype == "arpg":
        bindings["attack"] = {"keys": ["J"], "mouse_buttons": [1], "joy_buttons": [2]}
        bindings["secondary_attack"] = {"keys": ["K"], "mouse_buttons": [2], "joy_buttons": [3]}
        bindings["dodge"] = {"keys": ["Shift"], "joy_buttons": [1]}
        bindings["quick_item"] = {"keys": ["Q"], "joy_buttons": [9]}
    return bindings


STARTER_MAP_SIZE_RANGE = (24, 96)
STARTER_MAP_COUNTS = {  # key -> (minimum, maximum)
    "buildings": (0, 4),
    "npcs": (0, 6),
    "enemies": (0, 8),
    "chests": (0, 4),
    "decorations": (0, 40),
    "ground_patches": (0, 20),
}


def starter_map_defaults(archetype: str = "turn_based") -> dict[str, Any]:
    """The starter map of every project before M11 (so the defaults reproduce it exactly)."""
    return {
        "size": [40, 24],
        "buildings": 1,
        "npcs": 1,
        "enemies": 2 if archetype == "arpg" else 1,
        "chests": 1,
        "decorations": 8,
        "ground_patches": 6,
        "ground": "",
    }


def default_features() -> dict[str, bool]:
    return {key: key != "navigation" for key in FEATURE_KEYS}


@dataclass(slots=True)
class GeneratorConfig:
    project_name: str
    packs: list[PackRef]
    archetype: str = "turn_based"
    base_tile_size: int = 16
    resolution: tuple[int, int] = (640, 360)
    window_size: tuple[int, int] = (1280, 720)
    map_layers: list[str] = field(default_factory=lambda: list(DEFAULT_MAP_LAYERS))
    features: dict[str, bool] = field(default_factory=default_features)
    validation: dict[str, Any] = field(default_factory=lambda: {"smoke_test": True})
    seed: int = 12345
    input: dict[str, dict[str, Any]] = field(default_factory=dict)
    starter: dict[str, str] = field(default_factory=dict)  # role key -> asset or object id
    sounds: dict[str, str] = field(default_factory=dict)  # sound slot -> audio asset id
    starter_map: dict[str, Any] = field(default_factory=dict)  # overrides of starter_map_defaults
    # Tiled and LDtk maps to build (T12.49): {"include": [map id, ...], "starter": map id}
    imported_maps: dict[str, Any] = field(default_factory=dict)
    git: dict[str, str] = field(default_factory=dict)  # {"pack_art": "commit" | "lfs" | "ignore"}
    # platforms that get an export preset and the export check (T12.52)
    export_targets: list[str] = field(default_factory=lambda: list(EXPORT_TARGET_DEFAULT))
    config_version: int = CONFIG_VERSION
    generator_version: str = __version__
    godot_version: str = GODOT_VERSION

    def __post_init__(self) -> None:
        if not self.input:
            self.input = default_input(self.archetype)

    def to_json(self) -> dict[str, Any]:
        out = self._base_json()
        if self.starter:
            out["starter"] = dict(sorted(self.starter.items()))
        if self.sounds:
            out["sounds"] = dict(sorted(self.sounds.items()))
        options = self.starter_map_options()
        if options != starter_map_defaults(self.archetype):
            out["starter_map"] = options
        git = {k: v for k, v in sorted(self.git.items()) if v != GIT_DEFAULTS.get(k)}
        if git:
            out["git"] = git
        targets = self.selected_export_targets()
        if targets != list(EXPORT_TARGET_DEFAULT):
            out["export_targets"] = targets
        imported = self.imported_map_selection()
        if imported["include"] or imported["starter"]:
            out["imported_maps"] = {
                k: v for k, v in imported.items() if v
            }  # a key that holds its default is left out
        return out

    def imported_map_selection(self) -> dict[str, Any]:
        """``{"include": [...], "starter": id}``: the maps to build and the one that becomes the
        starter map (it is built even when it is not listed in ``include``)."""
        starter = str(self.imported_maps.get("starter", ""))
        include = sorted({str(i) for i in self.imported_maps.get("include", [])} | {starter} - {""})
        return {"include": include, "starter": starter}

    def selected_export_targets(self) -> list[str]:
        """The export targets in the fixed order; Windows when none is chosen."""
        chosen = set(self.export_targets)
        return [t for t in EXPORT_TARGETS if t in chosen] or list(EXPORT_TARGET_DEFAULT)

    @property
    def pack_art(self) -> str:
        """How the purchased art is handled by git: ``commit`` (default), ``lfs`` or ``ignore``."""
        return self.git.get("pack_art", GIT_DEFAULTS["pack_art"])

    def starter_map_options(self) -> dict[str, Any]:
        """The starter map options with the archetype's defaults filled in (a deep copy)."""
        return copy.deepcopy({**starter_map_defaults(self.archetype), **self.starter_map})

    def _base_json(self) -> dict[str, Any]:
        return {
            "config_version": self.config_version,
            "generator_version": self.generator_version,
            "godot_version": self.godot_version,
            "project_name": self.project_name,
            "archetype": self.archetype,
            "packs": [p.to_json() for p in self.packs],
            "base_tile_size": self.base_tile_size,
            "resolution": list(self.resolution),
            "window_size": list(self.window_size),
            "map_layers": list(self.map_layers),
            "features": dict(sorted(self.features.items())),
            "validation": dict(self.validation),
            "seed": self.seed,
            "input": copy.deepcopy(self.input),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> GeneratorConfig:
        return cls(
            project_name=data["project_name"],
            packs=[PackRef.from_json(p) for p in data["packs"]],
            archetype=data["archetype"],
            base_tile_size=data["base_tile_size"],
            resolution=(data["resolution"][0], data["resolution"][1]),
            window_size=(data["window_size"][0], data["window_size"][1]),
            map_layers=list(data["map_layers"]),
            features=dict(data["features"]),
            validation=dict(data["validation"]),
            seed=data["seed"],
            input=copy.deepcopy(data["input"]),
            starter=dict(data.get("starter", {})),
            sounds=dict(data.get("sounds", {})),
            starter_map=copy.deepcopy(data.get("starter_map", {})),
            imported_maps=copy.deepcopy(data.get("imported_maps", {})),
            git=dict(data.get("git", {})),
            export_targets=list(data.get("export_targets", EXPORT_TARGET_DEFAULT)),
            config_version=data["config_version"],
            generator_version=data["generator_version"],
            godot_version=data["godot_version"],
        )


def default_for(
    project_name: str,
    packs: list[PackRef],
    archetype: str = "turn_based",
    base_tile_size: int = 16,
) -> GeneratorConfig:
    """A config with every default filled in."""
    return GeneratorConfig(
        project_name=project_name,
        packs=list(packs),
        archetype=archetype,
        base_tile_size=base_tile_size,
    )


def load(path: Path) -> GeneratorConfig:
    data = jsonio.read(path)
    schema.validate("config", data)
    return GeneratorConfig.from_json(data)


def save(cfg: GeneratorConfig, path: Path) -> None:
    data = cfg.to_json()
    schema.validate("config", data)
    jsonio.write(path, data)


def hash_file_list(entries: list[tuple[str, str]]) -> str:
    """sha256 of the sorted ``path:sha256`` lines (the identity of a folder pack)."""
    lines = sorted(f"{path}:{digest}" for path, digest in entries)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def folder_sha256(folder: Path) -> str:
    """Identity hash of a folder pack: the sorted ``path:sha256`` lines of its files, junk
    (``Thumbs.db``, ``.DS_Store``, ...) left out. It is the hash the inventory computes too, so
    the config and the catalog agree on one identity."""
    from rpggen.core import archive

    entries: list[tuple[str, str]] = []
    files, _links = archive.walk_files(Path(folder))  # a link is never followed or hashed
    for rel in files:
        if rel == archive.COMPLETE_MARKER or rel.endswith(".partial") or archive.is_junk(rel):
            continue
        entries.append((rel, archive.sha256_file(Path(folder) / rel)))
    return hash_file_list(entries)


def pack_ref_from_source(source: Path, pack_id: str, known_sha256: str | None = None) -> PackRef:
    """PackRef for a pack folder or a .zip / .7z / .rar archive.

    ``known_sha256`` is the identity the analysis already computed (``Inventory.source_sha256``);
    with it no pack file is read. Without it an archive is streamed, never read into memory.
    """
    from rpggen.core import archive

    source = Path(source)
    if source.is_dir():
        return PackRef(
            pack_id, str(source.resolve()), known_sha256 or folder_sha256(source), "folder"
        )
    if not source.is_file():
        raise RpgGenError("ARCH-001", path=str(source), reason="does not exist")
    kind = source.suffix.lower().lstrip(".")
    if kind not in ("zip", "7z", "rar"):
        raise RpgGenError("ARCH-001", path=str(source), reason="unsupported file type")
    digest = known_sha256 or archive.sha256_file(source)
    return PackRef(pack_id, str(source.resolve()), digest, kind)


def pack_ref_from_folder(folder: Path, pack_id: str) -> PackRef:
    folder = Path(folder)
    if not folder.is_dir():
        raise RpgGenError("ARCH-001", path=str(folder), reason="not a folder")
    return pack_ref_from_source(folder, pack_id)
