from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rpggen import __version__, jsonio, schema
from rpggen.errors import RpgGenError

CONFIG_VERSION = 1
GODOT_VERSION = "4.7.2"
DEFAULT_MAP_LAYERS = ["Ground", "GroundDetails", "Walls", "Props", "Overhead"]
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
        return out

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
    """Identity hash of a folder: sha256 of its sorted ``path:sha256`` lines."""
    return hash_file_list(
        [
            (p.relative_to(folder).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
            for p in folder.rglob("*")
            if p.is_file()
        ]
    )


def pack_ref_from_source(source: Path, pack_id: str) -> PackRef:
    """PackRef for a pack folder or a .zip / .7z / .rar archive."""
    source = Path(source)
    if source.is_dir():
        return PackRef(pack_id, str(source.resolve()), folder_sha256(source), "folder")
    if not source.is_file():
        raise RpgGenError("ARCH-001", path=str(source), reason="does not exist")
    kind = source.suffix.lower().lstrip(".")
    if kind not in ("zip", "7z", "rar"):
        raise RpgGenError("ARCH-001", path=str(source), reason="unsupported file type")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    return PackRef(pack_id, str(source.resolve()), digest, kind)


def pack_ref_from_folder(folder: Path, pack_id: str) -> PackRef:
    folder = Path(folder)
    if not folder.is_dir():
        raise RpgGenError("ARCH-001", path=str(folder), reason="not a folder")
    return pack_ref_from_source(folder, pack_id)
