"""What the Options page decides, without its widgets: the draft config, feature dependencies,
the starter and imported maps, the input table, presets, the summary and validation. The pure
rules are in ``rpggen.core.options``; this class keeps the page's state around them."""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rpggen.core import app_settings, options, preflight
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.gui.models.forms import Translate, no_translation
from rpggen.gui.state import WizardState

INPUT_COLUMNS = ("Action", "Keys", "Mouse buttons", "Joy buttons")
SEED_MAX = 2**31 - 1
LAYER_MESSAGES = {
    options.LAYER_GROUND_REQUIRED: "The Ground layer is required.",
    options.LAYER_EMPTY: "Layer names cannot be empty.",
    options.LAYER_DUPLICATE: "Layer names must be unique.",
}
DEFAULTS_ITEM = "__defaults__"
STARTER_COUNTS = (
    ("buildings", "Buildings"),
    ("npcs", "Villagers"),
    ("enemies", "Enemies"),
    ("chests", "Chests"),
    ("decorations", "Decorations"),
    ("ground_patches", "Ground patches"),
)
STARTER_SIZE_NAMES = {(32, 20): "Small", (40, 24): "Medium", (64, 40): "Large"}
EXISTING_MAP_TEXT = (
    "The starter map already exists and is yours; these options apply to new projects."
)
IMPORTED_STARTER_TEXT = (
    "The starter map is an imported map, so the layout options are not used. "
    "Set the starter map under Imported maps back to the layout options to use them."
)
PACK_ART_LABELS = {
    "commit": "Commit the pack art with the project",
    "lfs": "Use Git LFS for the pack art",
    "ignore": "Leave the pack art out of git",
}


@dataclass(frozen=True)
class FeatureState:
    """A feature that depends on others: off and disabled while one of them is off."""

    enabled: bool
    checked: bool
    tooltip: str
    needs: str  # "" when nothing is missing


@dataclass(frozen=True)
class StarterState:
    """Which starter map controls can change, and the note that says why not."""

    layout_enabled: bool  # size, counts, ground set and reset
    imported_enabled: bool  # the imported-map starter combo
    note: str
    note_visible: bool  # also: the preview shows the note instead of a map


@dataclass
class OptionValues:
    """Everything the widgets show, read back in one go."""

    features: dict[str, bool]
    resolution: tuple[int, int]
    window_size: tuple[int, int]
    layers: list[str]
    seed: int
    starter: dict[str, Any]
    imported: dict[str, Any] | None  # None when the packs have no maps
    input_rows: list[tuple[str, list[str]]]


class OptionsModel:
    """The draft config of the Options page and the decisions about it."""

    def __init__(self, tr: Translate = no_translation) -> None:
        self.tr = tr
        self.state: WizardState | None = None
        self.draft: config_mod.GeneratorConfig | None = None
        self.input_map: dict[str, dict[str, Any]] = {}
        self.input_errors: list[str] = []
        self.demo_wish = True
        self.starter_locked = False
        self._pack_bytes_key: tuple | None = None
        self._pack_bytes = 0

    # ------------------------------------------------------------------ state

    def enter(self, state: WizardState) -> None:
        """Takes a copy of the state's config as the draft (None without a config)."""
        self.state = state
        cfg = state.config
        if cfg is None:
            self.draft = None
            return
        self.draft = dataclasses.replace(
            cfg,
            map_layers=list(cfg.map_layers),
            features=dict(cfg.features),
            input=copy.deepcopy(cfg.input),
            validation=dict(cfg.validation),
            starter_map=copy.deepcopy(cfg.starter_map),
            imported_maps=copy.deepcopy(cfg.imported_maps),
            git=dict(cfg.git),
        )
        self.starter_locked = self.starter_exists()

    def loaded(self) -> None:
        """The draft is about to be shown: the wishes start from it."""
        assert self.draft is not None
        self.demo_wish = self.draft.features.get("demo", True)
        self.input_map = copy.deepcopy(self.draft.input)

    def apply_to(self, cfg: config_mod.GeneratorConfig) -> None:
        """Writes the draft into ``cfg`` (an existing starter map keeps its options)."""
        assert self.draft is not None
        cfg.features = dict(self.draft.features)
        cfg.resolution = self.draft.resolution
        cfg.window_size = self.draft.window_size
        cfg.map_layers = list(self.draft.map_layers)
        cfg.seed = self.draft.seed
        cfg.input = copy.deepcopy(self.draft.input)
        cfg.validation = dict(self.draft.validation)
        cfg.git = dict(self.draft.git)
        if not self.starter_locked:
            cfg.starter_map = copy.deepcopy(self.draft.starter_map)
        cfg.imported_maps = copy.deepcopy(self.draft.imported_maps)

    @property
    def catalog(self) -> catalog_mod.Catalog | None:
        return self.state.catalog if self.state else None

    # ------------------------------------------------------------------ git

    def git_box(self, available: bool) -> tuple[str, str, bool]:
        """New project: "Initialize git repository" (on by default). Regeneration: "Commit
        regeneration" (off by default). Off without git. (text, tooltip, checked)"""
        state = self.state
        regenerating = bool(state and state.regenerating)
        text = (
            self.tr("Commit regeneration") if regenerating else self.tr("Initialize git repository")
        )
        tooltip = "" if available else self.tr("git was not found on this computer")
        want = state.git_commit if state and state.git_commit is not None else not regenerating
        return text, tooltip, bool(want) and available

    def set_git(self, checked: bool) -> None:
        if self.state is not None:
            self.state.git_commit = checked

    def set_pack_art(self, choice: str) -> None:
        assert self.draft is not None
        if choice == config_mod.GIT_DEFAULTS["pack_art"]:
            self.draft.git.pop("pack_art", None)
        else:
            self.draft.git["pack_art"] = choice

    # ------------------------------------------------------------------ features

    def feature_wish(self, key: str, checked: bool) -> None:
        if key == "demo":
            self.demo_wish = checked

    def dependent_features(self, current: dict[str, bool]) -> dict[str, FeatureState]:
        """A feature whose dependencies are off is unchecked and disabled and says what it needs;
        it returns to the user's choice once they are on again."""
        out = {}
        for key in options.FEATURE_DEPS:
            missing = options.missing_deps(current, key)
            if missing:
                names = ", ".join(self.tr(options.feature_label(m)) for m in missing)
                out[key] = FeatureState(
                    False,
                    False,
                    self.tr("Requires: {0}").format(names),
                    self.tr("Needs: {0}").format(names),
                )
            else:
                out[key] = FeatureState(
                    True, self.demo_wish, self.tr(options.FEATURE_INFO[key][2]), ""
                )
        return out

    def default_features(self) -> dict[str, bool]:
        defaults = config_mod.default_features()
        self.demo_wish = defaults.get("demo", True)
        return defaults

    # ------------------------------------------------------------------ screen

    def tile(self) -> int:
        return self.draft.base_tile_size if self.draft else 16

    def screen_hint(self, resolution: tuple[int, int]) -> tuple[str, tuple[int, int] | None]:
        """The "tiles across" line and the suggested resolution preset."""
        tile = self.tile()
        return (
            options.tiles_hint(resolution, tile),
            options.suggested_preset(options.RESOLUTION_PRESETS, tile),
        )

    @staticmethod
    def default_screen() -> tuple[tuple[int, int], tuple[int, int]]:
        cfg = config_mod.GeneratorConfig("x", [])
        return cfg.resolution, cfg.window_size

    # ------------------------------------------------------------------ starter map

    def ground_choices(self) -> list[tuple[str, str]]:
        """(label, asset id) of the tile sheets that are GROUND."""
        catalog = self.catalog
        if catalog is None:
            return []
        return [
            (f"{a.path.rsplit('/', 1)[-1]} · {a.pack_id}", a.id)
            for a in sorted(catalog.assets, key=lambda a: a.id)
            if a.status not in ("UNUSED", "MISSING")
            and catalog_mod.effective(a).get("role") == "GROUND"
            and catalog_mod.effective(a).get("usage") == "tiles"
        ]

    def starter_exists(self) -> bool:
        state = self.state
        if state is None or not state.regenerating or state.target is None:
            return False
        return (state.target / "game" / "maps" / "starter_map.tscn").is_file()

    def imported_starter(self) -> str:
        return str((self.draft.imported_maps if self.draft else {}).get("starter", ""))

    def starter_state(self) -> StarterState:
        """The layout options apply to a planned starter map: not to one that already exists and
        not to an imported one."""
        locked = self.starter_locked
        imported = bool(self.imported_starter()) and not locked
        text = self.tr(EXISTING_MAP_TEXT if locked else IMPORTED_STARTER_TEXT)
        return StarterState(
            layout_enabled=not locked and not imported,
            imported_enabled=not locked,  # the starter map of a project is its own
            note=text,
            note_visible=locked or imported,
        )

    def starter_defaults(self) -> dict[str, Any]:
        assert self.draft is not None
        return config_mod.starter_map_defaults(self.draft.archetype)

    def store_starter(self, values: dict[str, Any]) -> None:
        """Stores only what differs from the defaults of the archetype."""
        if self.draft is None or self.starter_locked:
            return
        defaults = self.starter_defaults()
        self.draft.starter_map = {k: v for k, v in values.items() if v != defaults[k]}

    def preview_options(self, values: dict[str, Any]) -> dict[str, Any] | None:
        """The options the starter map preview draws, or None when there is nothing to draw."""
        if self.starter_locked or self.draft is None or self.catalog is None:
            return None
        if self.imported_starter():
            return None
        return {**self.starter_defaults(), **values}

    # ------------------------------------------------------------------ imported maps

    def imported_maps(self) -> list[dict[str, Any]]:
        catalog = self.catalog
        return list(catalog.maps) if catalog is not None else []

    def imported_map_ids(self) -> list[str]:
        """The ids of the maps the catalog read from the packs."""
        return [m["id"] for m in self.imported_maps()]

    def imported_rows(self) -> list[tuple[str, str, str]]:
        """(label, id, source) of each imported map."""
        return [(options.imported_map_label(m), m["id"], m["source"]) for m in self.imported_maps()]

    def has_intgrid(self) -> bool:
        return bool(options.intgrid_rows(self.imported_maps()))

    def chosen_imported(self) -> dict[str, Any] | None:
        """The draft's selection made to fit the catalog's maps; None without maps."""
        known = self.imported_map_ids()
        if not known or self.draft is None:
            return None  # no catalog: the selection of the config stays as it is
        chosen = options.normalize_imported_maps(self.draft.imported_maps, known)
        self.draft.imported_maps = chosen
        return chosen

    def normalize_imported(self, include: list[str], starter: str) -> dict[str, Any]:
        return options.normalize_imported_maps(
            {"include": include, "starter": starter}, self.imported_map_ids()
        )

    def solid_rows(self) -> list[dict[str, Any]]:
        return options.intgrid_rows(self.imported_maps())

    def set_solid(self, choices: dict[tuple[str, str, int], bool]) -> int:
        catalog = self.catalog
        return options.set_solid(catalog.maps, choices) if catalog is not None else 0

    # ------------------------------------------------------------------ input map

    def input_rows(self) -> list[tuple[str, list[str]]]:
        """Each action with the text of its binding cells."""
        return [
            (action, [options.format_list(b.get(f, [])) for f, _kind in options.BINDING_FIELDS])
            for action, b in self.input_map.items()
        ]

    def read_input(self, rows: list[tuple[str, list[str]]]) -> dict[str, dict[str, Any]]:
        """The bindings of the table; the cells that are not lists of numbers go to
        ``input_errors``."""
        self.input_errors = []
        result: dict[str, dict[str, Any]] = {}
        for action, cells in rows:
            bindings = copy.deepcopy(self.input_map.get(action, {}))
            for col, ((field, _kind), text) in enumerate(
                zip(options.BINDING_FIELDS, cells, strict=False), start=1
            ):
                try:
                    bindings = options.apply_binding_text(bindings, field, text)
                except ValueError:
                    self.input_errors.append(
                        self.tr("{0}: {1} must be whole numbers separated by commas.").format(
                            action, self.tr(INPUT_COLUMNS[col])
                        )
                    )
            result[action] = bindings
        return result

    # ------------------------------------------------------------------ collecting

    def collect(self, values: OptionValues) -> None:
        if self.draft is None:
            return
        self.draft.features = options.effective_features(values.features)
        self.draft.resolution = values.resolution
        self.draft.window_size = values.window_size
        self.draft.map_layers = values.layers
        self.draft.seed = values.seed
        self.store_starter(values.starter)
        if values.imported is not None:
            self.draft.imported_maps = values.imported
        collected = self.read_input(values.input_rows)
        if not self.input_errors:
            self.draft.input = collected

    def validate(self) -> list[str]:
        if self.draft is None:
            return []
        layer_problems = [
            self.tr(LAYER_MESSAGES[m]) for m in options.layer_issues(self.draft.map_layers)
        ]
        return [*layer_problems, *self.input_errors, *options.config_errors(self.draft)]

    # ------------------------------------------------------------------ summary

    def summary(
        self, wanted: dict[str, bool], resolution: tuple[int, int]
    ) -> tuple[options.Summary, float | None, int | None]:
        """The summary card: what will be built, the time estimate and the project size."""
        assert self.draft is not None
        summary = options.summarize(
            self.draft.archetype,
            wanted,
            self.draft.starter_map_options(),
            self.draft.base_tile_size,
            resolution,
            self.draft.imported_maps,
        )
        settings = app_settings.get()
        assets = len(self.catalog.assets) if self.catalog else 0
        seconds = options.estimate_generation_seconds(
            settings.phase_timings, settings.timing_assets, assets
        )
        pack_bytes = self.pack_size()
        return summary, seconds, options.estimate_project_bytes(pack_bytes) if pack_bytes else None

    def pack_size(self) -> int:
        """The bytes of the packs (an archive counts as its unpacked size when it is a zip),
        read once per set of packs."""
        sources = tuple(str(p) for p in (self.state.pack_sources if self.state else []))
        if sources != self._pack_bytes_key:
            self._pack_bytes_key = sources
            self._pack_bytes = sum(preflight.pack_stats(Path(s))[2] or 0 for s in sources)
        return self._pack_bytes

    # ------------------------------------------------------------------ presets

    @staticmethod
    def preset_names() -> list[str]:
        return sorted(app_settings.get().option_presets)

    def apply_preset(self, name: str) -> bool:
        """Applies a saved preset (or the defaults, ``DEFAULTS_ITEM``) to the draft; False when
        there is no such preset. Raises ``ValueError`` when it does not fit."""
        if self.draft is None:
            return False
        preset = (
            options.default_preset(self.draft.archetype)
            if name == DEFAULTS_ITEM
            else app_settings.get().option_presets.get(name)
        )
        if preset is None:
            return False
        new = options.apply_preset(self.draft, preset)
        self.draft = dataclasses.replace(new, seed=self.draft.seed)  # a preset keeps the seed
        if self.starter_locked:  # the starter map is the user's: only the other options change
            self.draft.starter_map = {}
        return True

    def save_preset(self, name: str) -> bool:
        if self.draft is None or not name or name == self.tr("Defaults"):
            return False
        preset = options.to_preset(self.draft)
        app_settings.store().update(lambda settings: settings.option_presets.update({name: preset}))
        return True

    @staticmethod
    def edit_presets(renames: dict[str, str], deleted: list[str]) -> None:
        def apply(settings: app_settings.AppSettings) -> None:
            for old, new in renames.items():
                if old in settings.option_presets:
                    settings.option_presets[new] = settings.option_presets.pop(old)
            for name in deleted:
                settings.option_presets.pop(name, None)

        app_settings.store().update(apply)
