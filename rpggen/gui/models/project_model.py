"""What the Project page decides, without its widgets: the slow input checks, the field lines,
the pack cards, the suggested name and folder, pack updates and the first config."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rpggen import godot_target, ids, paths
from rpggen.core import archive, godot, inventory, pack_diff, pack_sniff, preflight
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.errors import Issue, IssueList, Severity
from rpggen.gui import state as state_mod
from rpggen.gui.models.forms import (
    FieldStatus,
    Translate,
    form_error,
    form_missing,
    hint,
    no_translation,
    status_of,
)
from rpggen.gui.state import WizardState

SAMPLE_NAME = "Sample RPG"
SAMPLE_PROFILE = "sample.rpgprofile.json"
# the side-view sample (T14.09): its own pack, profile and name; it is a metroidvania
SIDE_SAMPLE_NAME = "Sample Cave"
SIDE_SAMPLE_PROFILE = "sample_side.rpgprofile.json"
SIDE_SAMPLE_ARCHETYPE = "metroidvania"


@dataclass(frozen=True)
class Sample:
    """A bundled sample pack and the game it is tried as."""

    key: str
    label: str  # in the menus
    tooltip: str
    folder: str  # beside the template project
    profile: str  # the audit of the pack, in its folder
    name: str  # of the project
    archetype: str


# The five samples, in the order of the kinds' cards (T16.17). The first two are older.
SAMPLES: tuple[Sample, ...] = (
    Sample(
        "top",
        "Top-down village",
        "A turn-based RPG from the village pack",
        "sample_pack",
        SAMPLE_PROFILE,
        SAMPLE_NAME,
        "turn_based",
    ),
    Sample(
        "side",
        "Side-view cave",
        "A metroidvania from the cave pack",
        "sample_pack_side",
        SIDE_SAMPLE_PROFILE,
        SIDE_SAMPLE_NAME,
        SIDE_SAMPLE_ARCHETYPE,
    ),
    Sample(
        "shmup",
        "Star lane",
        "A shoot 'em up from the Star lane pack",
        "sample_pack_shmup",
        "sample_shmup.rpgprofile.json",
        "Star Lane",
        "shmup",
    ),
    Sample(
        "gun",
        "Jungle line",
        "A run and gun from the Jungle line pack",
        "sample_pack_gun",
        "sample_gun.rpgprofile.json",
        "Jungle Line",
        "run_and_gun",
    ),
    Sample(
        "race",
        "Dirt cup",
        "A racing game from the Dirt cup pack",
        "sample_pack_race",
        "sample_race.rpgprofile.json",
        "Dirt Cup",
        "racing",
    ),
)


def sample(key: str) -> Sample:
    """The sample with ``key``; the top-down village for a key that is not one."""
    return next((s for s in SAMPLES if s.key == key), SAMPLES[0])


def offered_samples() -> list[Sample]:
    """The samples whose kind of game can be chosen (its feature flag): the sample of a kind
    that is not offered yet is not offered either."""
    from rpggen import features

    on = {
        "metroidvania": features.METROIDVANIA_AVAILABLE,
        "shmup": features.SHMUP_AVAILABLE,
        "run_and_gun": features.RUN_AND_GUN_AVAILABLE,
        "racing": features.RACING_AVAILABLE,
    }
    return [s for s in SAMPLES if on.get(s.archetype, True)]


NAME_MAX = 64
ARCHIVE_SUFFIXES = (".zip", ".7z", ".rar")
FORMAT_NAMES = {
    "rpgmaker": "RPG Maker",
    "lpc": "LPC",
    "tiled": "Tiled",
    "ldtk": "LDtk",
    "aseprite": "Aseprite",
    "generic": "Generic",
}


@dataclass
class InputCheck:
    """Result of the slow checks (one Godot launch, disk statistics, zip directories)."""

    godot: list[Issue] = field(default_factory=list)
    godot_version: str = ""
    target: list[Issue] = field(default_factory=list)
    packs: list[Issue] = field(default_factory=list)
    pack_info: dict[str, tuple[str, int | None, int | None]] = field(default_factory=dict)
    pack_issues: dict[str, list[Issue]] = field(default_factory=dict)
    # T16.22: the bundles the packs were taken from, by the archive's path
    bundles: dict[str, pack_sniff.PackSniff] = field(default_factory=dict)
    bundle_issues: dict[str, list[Issue]] = field(default_factory=dict)
    pack_sniff: dict[str, pack_sniff.PackSniff] = field(default_factory=dict)


def member_source(bundle: Path, pack: pack_sniff.BundlePack) -> Path:
    """The source a pack folder of a bundle is added as: ``<archive>/<folder name>`` for an
    archive (``pack_sniff.member_path``), the folder itself for a bundle that is a folder."""
    if Path(bundle).is_dir():
        return Path(bundle).joinpath(*pack.path.split("/"))
    return pack_sniff.member_path(bundle, pack.name)


def _check_member(out: InputCheck, pack: Path, bundle: Path, folder: str) -> None:
    """The checks of a pack taken from a bundle: the archive is looked at once for all its
    packs, and the figures are those of the pack's folder in the listing."""
    key = str(bundle)
    if key not in out.bundles:
        out.bundles[key] = pack_sniff.sniff(bundle)
        out.bundle_issues[key] = preflight.check_pack(bundle)
        out.packs.extend(out.bundle_issues[key])
    found = IssueList()
    listed = next((p for p in out.bundles[key].bundle if p.name == folder), None)
    if listed is None and not out.bundle_issues[key]:
        found.add("ARCH-001", path=key, reason=f'it has no pack folder "{folder}"')
        out.packs.extend(found)
    out.pack_issues[str(pack)] = [*out.bundle_issues[key], *found]
    out.pack_info[str(pack)] = (bundle.name, None, listed.bytes if listed else None)
    out.pack_sniff[str(pack)] = pack_sniff.PackSniff(format="generic")


def check_inputs(
    godot_exe: Path | None,
    target: Path | None,
    packs: list[Path],
    *,
    callbacks: object = None,
) -> InputCheck:
    """Everything the page checks that touches the disk or starts a process."""
    out = InputCheck()
    if godot_exe is not None:
        try:
            version = godot.detect_version(godot_exe)
            out.godot_version = ".".join(str(p) for p in version[:3]) + f".{version[3]}"
            out.godot.extend(godot.check_version(version))
        except Exception as exc:  # noqa: BLE001 - shown as a field message
            out.godot.append(getattr(exc, "issue", None) or form_error(str(exc)))
    members = {str(pack): pack_sniff.split_member(pack) for pack in packs}
    if target is not None:  # a pack of a bundle is on the disk as its archive
        on_disk = [m[0] if (m := members[str(pack)]) else pack for pack in packs]
        out.target = preflight.check_target(target, list(dict.fromkeys(on_disk)))
    for pack in packs:
        member = members[str(pack)]
        if member is not None:
            _check_member(out, pack, *member)
            continue
        found = preflight.check_pack(pack)
        out.packs.extend(found)
        out.pack_issues[str(pack)] = found
        out.pack_info[str(pack)] = preflight.pack_stats(pack)
        out.pack_sniff[str(pack)] = pack_sniff.sniff(pack)
    return out


_BAD_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def prefill_name(source: Path) -> str:
    """A project name from a pack's file or folder name: words title-cased, characters that a
    folder name cannot hold removed, at most 64 characters."""
    base = source.stem if source.is_file() else source.name
    base = _BAD_NAME_CHARS.sub("", re.sub(r"[_\-.]+", " ", base)).strip()
    name = " ".join(word[:1].upper() + word[1:] for word in base.split())
    return name[:NAME_MAX].strip() or "My Game"


def format_size(size: int | None) -> str:
    if size is None:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024  # type: ignore[assignment]
    return ""


def sample_target(documents: Path) -> Path:
    """The first free ``rpggen-sample-<n>`` folder under ``documents``."""
    n = 1
    while (documents / f"rpggen-sample-{n}").exists():
        n += 1
    return documents / f"rpggen-sample-{n}"


def update_summary(pack_id: str, d: pack_diff.PackDiff) -> str:
    lines = [
        f"Update {pack_id}:",
        f"  {len(d.added)} added, {len(d.removed)} removed, {len(d.renamed)} renamed",
        f"  {len(d.changed_same_size)} changed (same size), {len(d.changed_resized)} resized",
        f"  {len(d.unchanged)} unchanged",
    ]
    if d.changed_resized:
        lines.append("")
        lines.append("These sheets changed size and become CONFLICT (painted tiles are kept):")
        lines += [f"  {p}" for p in d.changed_resized[:12]]
        if len(d.changed_resized) > 12:
            lines.append(f"  ... and {len(d.changed_resized) - 12} more")
    if d.removed:
        lines.append("")
        lines.append("Removed files stay in the project until you confirm their removal.")
    lines += ["", "Continue?"]
    return "\n".join(lines)


@dataclass
class Inputs:
    """The four fields as the widgets show them."""

    sources: list[Path]
    target: Path | None
    godot: Path | None
    name: str  # stripped

    def key(self) -> tuple:
        return (
            str(self.godot or ""),
            str(self.target or ""),
            tuple(str(p) for p in self.sources),
        )


class ProjectModel:
    """The state of the Project page that is not a widget value."""

    def __init__(self, tr: Translate = no_translation) -> None:
        self.tr = tr
        self.check: InputCheck | None = None  # latest completed slow check
        self.check_key: tuple | None = None
        self.generation = 0  # ignores results of superseded checks
        self.touched = {"packs": False, "target": False, "godot": False, "name": False}
        self.suggested_target = ""
        self.suggested_name = ""
        self.name_touched = False
        self.pack_updates: dict[str, str] = {}  # new source -> pack_id it replaces
        self.update_changed: set[str] = set()  # asset paths added, resized or removed
        # what the analysis said about each pack (the catalog's pack warnings), by its source
        self.catalog_marks: dict[str, tuple[str, ...]] = {}

    # ------------------------------------------------------------------ checks

    def begin_check(self) -> int:
        """A new slow check starts; returns its generation."""
        self.generation += 1
        return self.generation

    def finish_check(self, generation: int, key: tuple, result: InputCheck) -> bool:
        """Keeps ``result`` unless a newer check started meanwhile."""
        if generation != self.generation:
            return False
        self.check, self.check_key = result, key
        return True

    def current_check(self, inputs: Inputs) -> InputCheck | None:
        return self.check if self.check_key == inputs.key() else None

    # ------------------------------------------------------------------ editing

    def new_sources(self, existing: list[Path], dropped: list[Path]) -> list[Path]:
        """The folders and archives of ``dropped`` that are not listed yet."""
        known = {str(p).casefold() for p in existing}
        out: list[Path] = []
        for path in map(Path, dropped):
            if path.is_file() and path.suffix.lower() not in ARCHIVE_SUFFIXES:
                continue
            if str(path).casefold() not in known:
                out.append(path)
                known.add(str(path).casefold())
                self.touched["packs"] = True
        return out

    def suggestions(
        self, sources: list[Path], name_text: str, target_text: str, documents: Path
    ) -> tuple[str | None, str | None]:
        """A name from the first pack and an output folder, until the user has typed a name or a
        folder of their own: (new name, new folder), None where the field stays as it is."""
        if not sources:
            return None, None
        prefilled = prefill_name(sources[0])
        new_name = None
        if not self.name_touched and name_text in ("", self.suggested_name):
            self.suggested_name = new_name = name_text = prefilled
        new_target = None
        if target_text.strip() in ("", self.suggested_target):
            folder = documents / "rpggen" / (name_text.strip() or prefilled)
            self.suggested_target = new_target = str(folder)
        return new_name, new_target

    def target_typed(self) -> None:
        self.touched["target"] = True
        self.suggested_target = ""  # typed by the user: no more suggestions

    def name_typed(self) -> None:
        self.name_touched = True
        self.touched["name"] = True
        self.suggested_name = ""

    def touch_all(self) -> None:
        self.touched = dict.fromkeys(self.touched, True)

    # ------------------------------------------------------------------ field lines

    def name_issues(self, name: str) -> list[Issue]:
        if not name:
            return [form_missing(self.tr("The name needs 1 to 64 characters."))]
        if len(name) > NAME_MAX:
            return [form_error(self.tr("The name needs 1 to 64 characters."))]
        return []

    def name_status(self, name: str) -> FieldStatus:
        issues = self.name_issues(name)
        if issues and issues[0].code == "GUI-EMPTY" and not self.touched["name"]:
            return hint(self.tr("A name for the game, 1 to 64 characters."))
        return status_of(issues, self.tr("Name is fine."))

    def packs_status(self, inputs: Inputs) -> FieldStatus:
        if not inputs.sources and not self.touched["packs"]:
            return hint(self.tr("Drag a folder or archive here, or use the buttons."))
        issues = [] if inputs.sources else [form_error(self.tr("Add at least one asset pack."))]
        check = self.current_check(inputs)
        if check:
            issues += check.packs
        return status_of(issues, self.tr("{0} pack(s) ready.").format(len(inputs.sources)))

    def _godot_needed(self) -> str:
        return self.tr("Select a Godot {0}.x executable.").format(godot_target.MAJOR_MINOR)

    def godot_status(self, inputs: Inputs) -> FieldStatus:
        check = self.current_check(inputs)
        if inputs.godot is None:
            if self.touched["godot"]:
                return status_of([form_error(self._godot_needed())])
            return hint(self.tr("Select the Godot executable, or press Download Godot."))
        if check:
            return status_of(check.godot, self.tr("Godot {0}").format(check.godot_version))
        return FieldStatus(self.tr("Checking…"))

    def target_status(self, inputs: Inputs) -> FieldStatus:
        check = self.current_check(inputs)
        if inputs.target is None:
            if self.touched["target"]:
                return status_of([form_error(self.tr("Choose an output folder."))])
            return hint(self.tr("Where the Godot project will be created."))
        if check:
            return status_of(check.target, self.tr("Output folder is fine."))
        return FieldStatus(self.tr("Checking…"))

    def offers_download(self, inputs: Inputs) -> bool:
        """Offer the Godot download when there is no usable Godot (none chosen, or not 4.7.x)."""
        check = self.current_check(inputs)
        unsupported = check is not None and any(i.code == "ENV-002" for i in check.godot)
        return inputs.godot is None or unsupported

    # ------------------------------------------------------------------ pack rows

    def _detail(self, info: tuple[str, int | None, int | None]) -> list[str]:
        kind, count, size = info
        bits = [kind]
        if count is not None:
            bits.append(self.tr("{0} files").format(count))
        if size is not None:
            bits.append(format_size(size))
        return bits

    def mark_words(self, marks: tuple[str, ...]) -> list[str]:
        """The words of a pack card for what detection said about the pack (T16.02, T16.21):
        the kind of game it looks made for, and the engines it ships its art for."""
        words: list[str] = []
        for mark in marks:
            kind, _, rest = mark.partition(":")
            if mark == catalog_mod.VIEW_SHMUP:
                words.append(self.tr("Looks like a shooter pack"))
            elif mark == catalog_mod.VIEW_RACING:
                words.append(self.tr("Looks like a racing pack"))
            elif kind == "engines":
                count, _, kept = rest.partition(":")
                words.append(self.tr("art for {0} engines: {1}'s is used").format(count, kept))
        return words

    def card_for(self, path: str, check: InputCheck | None) -> dict[str, Any]:
        """What the pack card shows: name, kind/files/size, the chips and an inline error."""
        source = Path(path)
        card: dict[str, Any] = {
            "name": source.name or path,
            "detail": path,
            "chips": [],
            "error": "",
        }
        if check is None or path not in check.pack_info:
            return card
        member = pack_sniff.split_member(source)
        if member is not None:
            return self._member_card(card, path, check, str(member[0]))
        bits = self._detail(check.pack_info[path])
        card["detail"] = " · ".join(bits)
        sniffed = check.pack_sniff.get(path)
        problems = [i for i in check.pack_issues.get(path, []) if i.code.startswith("ARCH-")]
        if sniffed is not None:
            problems += [i for i in sniffed.issues if i not in problems]
        if problems:
            card["error"] = problems[0].message
            return card
        if sniffed is not None and sniffed.format:
            label = self.tr(FORMAT_NAMES.get(sniffed.format, sniffed.format))
            if sniffed.tile_size:
                label += f" · {sniffed.tile_size} px"
            if sniffed.bundle:  # a bundle that is in the list whole, as one pack
                label = self.tr("Bundle of {0} packs").format(len(sniffed.bundle))
            card["chips"].append((label, "format"))
            if sniffed.has_license is True:
                card["chips"].append((self.tr("Licence found"), "ok"))
            elif sniffed.has_license is False:
                card["chips"].append((self.tr("No licence file"), "warn"))
        marks = self.catalog_marks.get(path, sniffed.marks if sniffed is not None else ())
        card["detail"] = " · ".join([*bits, *self.mark_words(marks)])
        return card

    def _member_card(
        self, card: dict[str, Any], path: str, check: InputCheck, bundle: str
    ) -> dict[str, Any]:
        """The card of a pack taken from a bundle: its folder's pictures and size. What is
        known of its licence is said once, on the row of the bundle."""
        sniffed = check.bundles.get(bundle)
        packs = sniffed.bundle if sniffed is not None else ()
        listed = next((p for p in packs if p.name == card["name"]), None)
        problems = [i for i in check.pack_issues.get(path, []) if i.code.startswith("ARCH-")]
        if sniffed is not None:
            problems += [i for i in sniffed.issues if i not in problems]
        if problems:
            card["error"] = problems[0].message
        if listed is not None:
            bits = [self.tr("{0} images").format(listed.images), format_size(listed.bytes)]
            marks = self.catalog_marks.get(path, ())
            card["detail"] = " · ".join([*bits, *self.mark_words(marks)])
        return card

    def group_card(self, bundle: str, check: InputCheck | None, taken: int) -> dict[str, Any]:
        """The row over the packs taken from a bundle (T16.22): the archive, how many of its
        packs are taken, what is known of its licence, and *Choose packs…*."""
        card: dict[str, Any] = {
            "name": Path(bundle).name,
            "detail": self.tr("{0} pack(s) taken").format(taken),
            "chips": [],
            "error": "",
            "action": self.tr("Choose packs…"),
        }
        sniffed = check.bundles.get(bundle) if check is not None else None
        if check is None or sniffed is None:
            return card
        problems = [*check.bundle_issues.get(bundle, []), *sniffed.issues]
        if problems:
            card["error"] = problems[0].message
        elif sniffed.bundle:
            card["detail"] = self.tr("{0} of {1} packs").format(taken, len(sniffed.bundle))
            if sniffed.bundle_license:
                card["chips"].append((self.tr("Licence found"), "ok"))
            else:  # said once here, not on every pack of the bundle
                card["chips"].append((self.tr("Licence: not found in the bundle"), "warn"))
        return card

    @staticmethod
    def bundle_choice(
        sources: list[Path], bundle: Path, packs: tuple[pack_sniff.BundlePack, ...]
    ) -> list[str]:
        """The names of the pack folders of ``bundle`` that are in the list now."""
        listed = {str(source).casefold() for source in sources}
        return [p.name for p in packs if str(member_source(bundle, p)).casefold() in listed]

    def row_text(self, path: str, check: InputCheck | None) -> tuple[str, str]:
        """The plain text of a pack row and its tooltip: the pack, its kind, file count and size
        once known, and a warning sign with the text of an archive problem."""
        if check is None or path not in check.pack_info:
            return path, path
        text = f"{path}   ·   " + " · ".join(self._detail(check.pack_info[path]))
        problems = [i for i in check.pack_issues.get(path, []) if i.code.startswith("ARCH-")]
        if problems:
            return "⚠ " + text, problems[0].message + " " + problems[0].fix
        return text, path

    # ------------------------------------------------------------------ validation

    def validate(self, inputs: Inputs) -> list[Issue]:
        issues: list[Issue] = []
        if not inputs.sources:
            issues.append(form_missing(self.tr("Add at least one asset pack.")))
        if inputs.target is None:
            issues.append(form_missing(self.tr("Choose an output folder.")))
        if inputs.godot is None:
            issues.append(form_missing(self._godot_needed()))
        issues += self.name_issues(inputs.name)
        check = self.current_check(inputs)
        if check is None:
            if not issues:
                issues.append(form_error(self.tr("Checking your choices…")))
            return issues
        for found in (*check.godot, *check.target, *check.packs):
            if found.severity is Severity.ERROR:
                issues.append(found)
        return issues

    # ------------------------------------------------------------------ pack update

    @staticmethod
    def project_pack_ids(target: Path | None) -> list[str]:
        """The pack ids of the rpggen project in ``target`` (none when it is not one)."""
        if target is None or not preflight.is_rpggen_project(target):
            return []
        return [p.pack_id for p in config_mod.load(target / paths.CONFIG).packs]

    @staticmethod
    def diff_update(target: Path, pack_id: str, new_source: Path) -> pack_diff.PackDiff:
        """What replacing the installed pack ``pack_id`` with ``new_source`` changes; raises
        ``RpgGenError`` or ``OSError`` when a pack cannot be read."""
        installed = target / "assets" / "packs" / pack_id
        old_opened = archive.open_pack(installed, set(), pack_id=pack_id)
        new_opened = archive.open_pack(Path(new_source), set(), pack_id=pack_id)
        return pack_diff.diff(
            inventory.build_inventory(old_opened), inventory.build_inventory(new_opened)
        )

    @staticmethod
    def old_source(target: Path, pack_id: str) -> str:
        cfg = config_mod.load(target / paths.CONFIG)
        return next(p.source for p in cfg.packs if p.pack_id == pack_id)

    def record_update(self, new_source: Path, pack_id: str, d: pack_diff.PackDiff) -> None:
        self.pack_updates[str(new_source)] = pack_id
        prefix = f"assets/packs/{pack_id}/"
        self.update_changed |= {prefix + p for p in [*d.changed_paths(), *d.renamed]}

    # ------------------------------------------------------------------ state

    def load(self, state: WizardState) -> None:
        self.touched["packs"] = bool(state.pack_sources)
        self.touched["target"] = state.target is not None
        self.touched["name"] = bool(state.project_name)
        self.name_touched = bool(state.project_name)
        self.catalog_marks = {}
        if state.catalog is not None and len(state.opened_packs) == len(state.pack_sources):
            warnings = {pack.pack_id: tuple(pack.warnings) for pack in state.catalog.packs}
            for source, opened in zip(state.pack_sources, state.opened_packs, strict=True):
                if opened.pack_id in warnings:
                    self.catalog_marks[str(source)] = warnings[opened.pack_id]

    def store(self, state: WizardState, inputs: Inputs) -> None:
        """Writes the fields into ``state`` (the analysis is the page's)."""
        state.pack_sources = inputs.sources
        state.target = inputs.target
        state.godot_exe = inputs.godot
        state.project_name = inputs.name
        state.pack_updates = {
            s: p for s, p in self.pack_updates.items() if Path(s) in inputs.sources
        }
        state.changed_paths = set(self.update_changed) if state.pack_updates else set()


def godot_choices(state_exe: Path | None, saved: str) -> tuple[list[str], str | None]:
    """The Godot combo: the found executables (the state's first when it is not one of them)
    and the text to select (None keeps the combo's first entry)."""
    candidates = [str(p) for p in godot.auto_find_godot()]
    if state_exe and str(state_exe) not in candidates:
        candidates.insert(0, str(state_exe))
    if state_exe:
        return candidates, str(state_exe)
    if saved and Path(saved).is_file():
        if saved not in candidates:
            candidates.insert(0, saved)
        return candidates, saved
    return candidates, None if candidates else ""


def analysed_hash(state: WizardState, index: int) -> str | None:
    """The identity the analysis worker already computed for pack ``index`` (archives: the file
    hash, folders: the hash of the file list), so that no pack file is read on the GUI thread."""
    if index < len(state.opened_packs) and state.opened_packs[index].source_sha256:
        return state.opened_packs[index].source_sha256
    if index < len(state.inventories):
        return state.inventories[index].source_sha256 or None
    return None


def config_with_packs(state: WizardState) -> config_mod.GeneratorConfig:
    """An existing project's config with its pack list brought up to date: packs that stay keep
    their ids, an updated pack keeps the id of the pack it replaces."""
    assert state.config is not None
    old = {str(p.path).casefold(): p for p in state.config.packs}
    used = {p.pack_id for p in state.config.packs}
    refs = []
    for index, source in enumerate(state.pack_sources):
        known = old.get(str(source).casefold())
        if known is not None:
            refs.append(known)
            continue
        pack_id = state.pack_updates.get(str(source))
        if pack_id is None:
            whole = source.is_dir() or pack_sniff.split_member(source) is not None
            stem = source.name if whole else source.stem  # a pack of a bundle: its folder
            pack_id = ids.pack_id_from_name(stem, used)
            used.add(pack_id)
        refs.append(config_mod.pack_ref_from_source(source, pack_id, analysed_hash(state, index)))
    state.config.packs = refs
    return state.config


def default_config(state: WizardState) -> config_mod.GeneratorConfig:
    refs = [
        config_mod.pack_ref_from_source(source, opened.pack_id, analysed_hash(state, index))
        for index, (opened, source) in enumerate(
            zip(state.opened_packs, state.pack_sources, strict=True)
        )
    ]
    tile = catalog_mod.dominant_tile_size(state.catalog) if state.catalog else None
    return config_mod.default_for(
        state.project_name, refs, archetype=state.archetype, base_tile_size=tile or 16
    )


def load_previous(
    state: WizardState, target: Path, ask_resume: Callable[[], bool]
) -> catalog_mod.Catalog | None:
    """The catalog to build on: an existing project's, or a saved draft (when resumed)."""
    if preflight.is_rpggen_project(target):
        state.regenerating = True
        state.config = config_mod.load(target / paths.CONFIG)
        state.archetype = state.config.archetype
        return catalog_mod.load(target / paths.CATALOG)
    state.regenerating = False
    draft = state_mod.load_draft(target)
    if draft is not None and ask_resume():
        return state_mod.apply_draft(state, draft)
    return None


def needs_analysis(state: WizardState, key: tuple, previous: object) -> bool:
    """False when the catalog of ``state`` is already the analysis of these packs."""
    return not (state.catalog is not None and state.analyzed_key == key and previous is None)


def refresh_config(state: WizardState) -> None:
    """After an analysis: a config for the analysed packs, unless the state has one for them."""
    sources = [str(s) for s in state.pack_sources]
    if state.config is not None and [str(p.path) for p in state.config.packs] == sources:
        return
    if state.regenerating and state.config is not None:
        state.config = config_with_packs(state)
    else:
        state.config = default_config(state)
