"""The answer key of the owner's real packs (T17.34): drafted from what rpggen reads, corrected
group by group, spot-checked by the owner on a local page, then written as private-corpus entries
(``*.corpus.json``, T12.26) that ``rpggen analyze --private-corpus`` scores against.

Nothing of a pack is written into the repository: the key, its pictures and the owner's marks
live in the folder given with ``--out`` (``F:\\rpggen_scratch\\answer_key`` on the owner's machine).

    python tools/answer_key.py draft --out DIR [--pack NAME ...]
    python tools/answer_key.py sheets --out DIR [--pack NAME ...]
    python tools/answer_key.py serve --out DIR [--port 8765]
    python tools/answer_key.py corpus --out DIR
    python tools/answer_key.py fit --out DIR [--write]

``draft`` writes ``DIR/draft/NAME.json`` (every picture, its reading and its group); corrections
of the agent go in ``DIR/corrections/NAME.json`` (``{"groups": {group: facets}, "entries": {key:
facets}}``, a facet set to null removed); ``sheets`` draws a contact sheet of every group;
``serve`` shows the key, group by group, at ``http://127.0.0.1:PORT`` and saves the owner's marks
in ``DIR/marks/NAME.json`` as they are made; ``corpus`` writes ``DIR/corpus/NAME.corpus.json``;
``fit`` scores the corpus with the raw confidences, fits the calibration and reports per pack
and per publisher the sure share and the accuracy of the sure pictures before calibration and
after it, each pack measured with a table fitted on the other packs (``DIR/fit_report.md``);
``--write`` puts the table fitted on every pack into ``rpggen/data/calibration.json``.

``DIR/packs.json`` lists the packs: ``[{"name", "path", "publisher"}, ...]``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from rpggen.core import accuracy, archive, catalog, inventory, profiles  # noqa: E402

# the facets of an asset the key holds (as an exported profile holds them)
KEY_FACETS = ("usage", "role", "frame", "grid", "animations")


def load_packs(out: Path, names: list[str] | None = None) -> list[dict[str, Any]]:
    packs = json.loads((out / "packs.json").read_text(encoding="utf-8"))
    if names:
        packs = [p for p in packs if p["name"] in names]
    return packs


def assemble(
    pack: dict[str, Any],
) -> tuple[catalog.Catalog, inventory.Inventory, Path, dict[str, str]]:
    """The catalog of one pack read alone (as ``--private-corpus`` reads it), its inventory,
    the folder its files are read from and the pictures rpggen cut (project path -> file)."""
    opened = archive.open_pack(Path(pack["path"]), set(), pack_id=pack["name"])
    inv = inventory.build_inventory(opened)
    cat, _issues, generated = catalog.assemble([(opened, inv)], None, [])
    return cat, inv, opened.root, generated


def facets_of(asset: catalog.Asset) -> dict[str, Any]:
    eff = catalog.effective(asset)
    out: dict[str, Any] = {}
    for name in KEY_FACETS:
        value = eff.get(name)
        if value in (None, {}, []):
            continue
        if name == "grid":
            value = {k: value[k] for k in accuracy.GRID_FIELDS if k in value}
        if name == "animations":
            value = sorted(value)
        out[name] = value
    return out


def group_of(key: str, facets: dict[str, Any], sheet: str | None) -> str:
    """Pictures shown together for one look: those of one folder, or the parts cut from one
    sheet (``sheet``, its key: a cut part's own path is a generated file), with one drafted
    answer (a folder of numbered tiles holds many things: split by answer, a picture read apart
    from its neighbours is looked at apart)."""
    answer = f"[{facets.get('usage')}/{facets.get('role')}]"
    if sheet is not None:
        return f"{sheet} cut {answer}"
    folder = key.partition("#")[0].rpartition("/")[0]
    return f"{folder}/ {answer}"


def draft(out: Path, names: list[str] | None) -> None:
    for pack in load_packs(out, names):
        cat, inv, root, generated = assemble(pack)
        pack_id = inv.pack_id
        entries: dict[str, Any] = {}
        groups: dict[str, list[str]] = {}
        for asset in sorted(cat.assets, key=lambda a: a.id):
            if asset.kind != "image" or asset.status == "MISSING":
                continue
            key = profiles.asset_key(asset, pack_id)
            facets = facets_of(asset)
            base = cat.asset(asset.id.split("#", 1)[0]) if "#" in asset.id else None
            sheet = profiles.asset_key(base, pack_id) if base is not None else None
            group = group_of(key, facets, sheet)
            groups.setdefault(group, []).append(key)
            path = key.partition("#")[0]
            entries[key] = {
                "file": generated.get(asset.path) or str(root / path),
                "facets": facets,
                "group": group,
                "sheet": sheet,
                "draft": {
                    "status": asset.status,
                    "confidence": round(asset.confidence, 4),
                    "detected_by": asset.detected_by,
                },
            }
        doc = {
            "name": pack["name"],
            "publisher": pack["publisher"],
            "path": pack["path"],
            "fingerprint": accuracy.fingerprint(inv),
            "entries": entries,
            "groups": {g: sorted(m) for g, m in sorted(groups.items())},
        }
        dest = out / "draft" / f"{pack['name']}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
        sure = sum(
            1 for e in entries.values() if e["draft"]["status"] in ("CONFIRMED", "AUTO_DETECTED")
        )
        print(
            f"{pack['name']}: {len(entries)} pictures, {len(groups)} groups, sure {sure}",
            flush=True,
        )


def read_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def key_of(out: Path, name: str) -> dict[str, Any]:
    """A pack's key: the draft with the agent's corrections laid on, group then picture; each
    entry gets ``answer`` and ``corrected``."""
    doc = read_json(out / "draft" / f"{name}.json", None)
    if doc is None:
        raise SystemExit(f"no draft of {name}: run draft first")
    fixes = read_json(out / "corrections" / f"{name}.json", {})
    for key, entry in doc["entries"].items():
        answer = dict(entry["facets"])
        layers = (
            (fixes.get("groups") or {}).get(entry["group"]),
            (fixes.get("entries") or {}).get(key),
        )
        changed = False
        for layer in layers:
            for facet, value in (layer or {}).items():
                changed = True
                if value is None:
                    answer.pop(facet, None)
                else:
                    answer[facet] = value
        entry["answer"] = answer
        entry["corrected"] = changed
    return doc


SHEET_THUMB = 96
SHEET_THUMB_MANY = 64  # the thumbnails of a group of more than SHEET_FEW pictures
SHEET_FEW = 48
SHEET_COLUMNS = 8
SHEET_COLUMNS_MANY = 12
SHEET_MAX = 160  # the pictures of a group drawn on its sheet, at most
SHEET_ONE = 640  # a group of one picture is drawn as large as this, at most


def _picture(file: str) -> Any:
    from PIL import Image

    try:
        with Image.open(file) as opened:
            return opened.convert("RGBA")
    except (OSError, ValueError):
        return Image.new("RGBA", (16, 16), (255, 0, 255, 255))


def _fit(img: Any, box: int) -> Any:
    """``img`` as large as ``box`` at most, small pixel art enlarged by whole steps."""
    from PIL import Image

    w, h = img.size
    if max(w, h) <= box:
        scale = max(1, box // max(w, h))
        return img.resize((w * scale, h * scale), Image.Resampling.NEAREST)
    img = img.copy()
    img.thumbnail((box, box), Image.Resampling.NEAREST)
    return img


def sheets(out: Path, names: list[str] | None) -> None:
    """A contact sheet of each group (up to ``SHEET_MAX`` of its pictures on a checkerboard):
    ``DIR/sheets/NAME/<n>.png``, numbered as the groups are listed."""
    from PIL import Image

    for pack in load_packs(out, names):
        doc = read_json(out / "draft" / f"{pack['name']}.json", None)
        if doc is None:
            continue
        dest = out / "sheets" / pack["name"]
        dest.mkdir(parents=True, exist_ok=True)
        for n, members in enumerate(doc["groups"].values()):
            shown = members[:SHEET_MAX]
            if len(shown) == 1:
                thumbs = [_fit(_picture(doc["entries"][shown[0]]["file"]), SHEET_ONE // 2)]
                if max(thumbs[0].size) <= SHEET_ONE // 2:
                    thumbs = [_fit(thumbs[0], SHEET_ONE)]
                cell_w, cell_h, cols = thumbs[0].width + 8, thumbs[0].height + 8, 1
            else:
                many = len(shown) > SHEET_FEW
                box = SHEET_THUMB_MANY if many else SHEET_THUMB
                thumbs = [_fit(_picture(doc["entries"][k]["file"]), box) for k in shown]
                cell_w = cell_h = box + 8
                cols = min(SHEET_COLUMNS_MANY if many else SHEET_COLUMNS, len(thumbs))
            rows = (len(thumbs) + cols - 1) // cols
            sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (232, 232, 232, 255))
            for y in range(0, sheet.height, 8):
                for x in range((y // 8) % 2 * 8, sheet.width, 16):
                    sheet.paste((200, 200, 200, 255), (x, y, x + 8, y + 8))
            for i, thumb in enumerate(thumbs):
                x = (i % cols) * cell_w + (cell_w - thumb.width) // 2
                y = (i // cols) * cell_h + (cell_h - thumb.height) // 2
                sheet.alpha_composite(thumb, (x, y))
            sheet.convert("RGB").save(dest / f"{n}.png")
        print(f"{pack['name']}: {len(doc['groups'])} sheets")


def _notes(out: Path, name: str, doc: dict[str, Any]) -> dict[str, list[str]]:
    """The agent's notes per group (``corrections/NAME.notes.txt``, written by its helper): a
    group's own lines and those of its pictures, the last word kept for each target."""
    file = out / "corrections" / f"{name}.notes.txt"
    if not file.is_file():
        return {}
    by_target: dict[str, str] = {}
    for line in file.read_text(encoding="utf-8").splitlines():
        target, sep, rest = line.partition(": ")
        if sep:
            by_target[target] = rest
    groups = list(doc["groups"])
    out_notes: dict[str, list[str]] = {}
    for target, rest in by_target.items():
        if target.startswith("#") and " " in target:
            group = target.split(" ", 1)[1]
        else:
            group = (doc["entries"].get(target) or {}).get("group", "")
            rest = f"{target.rsplit('/', 1)[-1]}: {rest}"
        if group in groups:
            out_notes.setdefault(group, []).append(rest)
    return out_notes


def _answer_text(answers: list[dict[str, Any]]) -> str:
    """The answer a group's pictures share, a facet that differs between them said to."""
    lines = []
    for k in KEY_FACETS:
        values = {json.dumps(a.get(k), sort_keys=True) for a in answers}
        if len(values) > 1:
            lines.append(f"{k}: differs per picture ({len(values)} kinds)")
        elif k in answers[0]:
            lines.append(f"{k}: {json.dumps(answers[0][k])}")
    return "\n".join(lines) if lines else "(nothing: not used)"


def corpus(out: Path) -> None:
    """The key as private-corpus entries (``DIR/corpus/NAME.corpus.json``): the fingerprint of
    each pack and every picture's answer as an exported profile holds it. The marks say which
    groups the owner has looked at (``reviewed``)."""
    for pack in load_packs(out):
        if not (out / "draft" / f"{pack['name']}.json").is_file():
            continue
        doc = key_of(out, pack["name"])
        marks = read_json(out / "marks" / f"{pack['name']}.json", {})
        entry = {
            "corpus_version": accuracy.CORPUS_VERSION,
            "name": pack["name"],
            "publisher": pack["publisher"],
            "source": pack["path"],
            "fingerprint": doc["fingerprint"],
            "profile": {"assets": {k: e["answer"] for k, e in sorted(doc["entries"].items())}},
            "reviewed": sorted(g for g, m in marks.items() if m.get("mark") == "right"),
        }
        dest = out / "corpus" / f"{pack['name']}.corpus.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(entry, indent=1, sort_keys=True), encoding="utf-8")
        print(f"{pack['name']}: {len(doc['entries'])} pictures")


def review_data(out: Path) -> dict[str, Any]:
    """The smaller decision queue, kept separately from the owner's original group marks."""
    queue: dict[str, Any] = read_json(out / "review_queue.json", {})
    return {**queue, "decisions": read_json(out / "review_decisions.json", {})}


def save_review_decision(out: Path, data: dict[str, Any]) -> None:
    questions = {q["id"]: q for q in review_data(out).get("questions", [])}
    question = questions.get(str(data.get("id", "")))
    if question is None or data.get("choice") not in question["choices"]:
        raise ValueError("Choose one of the answers shown for this question.")
    note = data.get("note", "")
    if not isinstance(note, str) or len(note) > 2000:
        raise ValueError("Notes must be text of at most 2,000 characters.")
    marks = read_json(out / "review_decisions.json", {})
    decision = {"choice": data["choice"], "note": note}
    from rpggen import jsonio

    previous = marks.get(question["id"])
    if previous != decision:
        history = read_json(out / "review_decision_history.json", [])
        history.append({"id": question["id"], "before": previous, "after": decision})
        jsonio.write(out / "review_decision_history.json", history)
    marks[question["id"]] = decision
    jsonio.write(out / "review_decisions.json", marks)


def serve(out: Path, port: int) -> None:
    """The review page (``answer_key_page.html``) on ``127.0.0.1`` only; the owner's marks are
    written under ``out`` as they are made."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Lock
    from urllib.parse import parse_qs, urlparse

    page = (Path(__file__).parent / "answer_key_page.html").read_bytes()
    review_page = (Path(__file__).parent / "answer_key_decisions.html").read_bytes()
    decision_lock = Lock()
    packs = load_packs(out)
    names = {p["name"] for p in packs}

    def marks_of(name: str) -> dict[str, Any]:
        found: dict[str, Any] = read_json(out / "marks" / f"{name}.json", {})
        return found

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, kind: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data: Any) -> None:
            self._send(200, json.dumps(data).encode("utf-8"), "application/json")

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass

        def do_GET(self) -> None:  # noqa: N802
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path == "/":
                selected = (
                    review_page
                    if (out / "review_queue.json").is_file()
                    and q.get("all") != "1"
                    and "pack" not in q
                    else page
                )
                self._send(200, selected, "text/html; charset=utf-8")
            elif url.path == "/api/questions":
                self._json(review_data(out))
            elif url.path == "/review-sheet":
                question = next(
                    (r for r in review_data(out).get("questions", []) if r["id"] == q.get("id")),
                    None,
                )
                file = (out / question["sheet"]).resolve() if question else None
                if file is not None and file.is_relative_to(out.resolve()) and file.is_file():
                    self._send(200, file.read_bytes(), "image/png")
                else:
                    self._send(404, b"no sheet", "text/plain")
            elif url.path == "/api/packs":
                rows = []
                for p in packs:
                    doc = read_json(out / "draft" / f"{p['name']}.json", {"groups": {}})
                    marks = marks_of(p["name"])
                    rows.append(
                        {
                            **p,
                            "groups": len(doc["groups"]),
                            "marked": sum(1 for m in marks.values() if m.get("mark")),
                            "wrong": sum(
                                1 for m in marks.values() if m.get("mark") in ("wrong", "mixed")
                            ),
                        }
                    )
                self._json(rows)
            elif url.path == "/api/pack" and q.get("name") in names:
                doc = key_of(out, q["name"])
                notes = _notes(out, q["name"], doc)
                groups = []
                for group, members in doc["groups"].items():
                    groups.append(
                        {
                            "group": group,
                            "size": len(members),
                            "shown": min(len(members), SHEET_MAX),
                            "answer": _answer_text([doc["entries"][k]["answer"] for k in members]),
                            "corrected": any(doc["entries"][k]["corrected"] for k in members),
                            "notes": notes.get(group, [])[:12],
                        }
                    )
                self._json(
                    {"publisher": doc["publisher"], "groups": groups, "marks": marks_of(q["name"])}
                )
            elif url.path == "/sheet" and q.get("pack") in names and q.get("n", "").isdigit():
                file = out / "sheets" / q["pack"] / f"{int(q['n'])}.png"
                if file.is_file():
                    self._send(200, file.read_bytes(), "image/png")
                else:
                    self._send(404, b"no sheet", "text/plain")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path == "/api/decision":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 16000:
                        raise ValueError("Invalid decision size.")
                    data = json.loads(self.rfile.read(length))
                    if not isinstance(data, dict):
                        raise ValueError("Invalid decision.")
                    with decision_lock:
                        save_review_decision(out, data)
                except (ValueError, TypeError) as exc:
                    self._send(400, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
                    return
                self._json({"ok": True})
                return
            if urlparse(self.path).path != "/api/mark":
                self._send(404, b"not found", "text/plain")
                return
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            name = data.get("pack")
            if name not in names:
                self._send(400, b"no such pack", "text/plain")
                return
            marks = marks_of(name)
            marks[str(data.get("group"))] = {
                "mark": str(data.get("mark", "")),
                "note": str(data.get("note", "")),
            }
            dest = out / "marks" / f"{name}.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(marks, indent=1, sort_keys=True), encoding="utf-8")
            self._json({"ok": True})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"review page: http://127.0.0.1:{port}/  (Ctrl+C stops it)")
    server.serve_forever()


def _sure_counts(pictures: list[dict[str, Any]], sure_of: Any) -> dict[str, Any]:
    row = {"pictures": len(pictures), "sure": 0, "sure_right": 0, "right": 0}
    for p in pictures:
        sure = bool(sure_of(p))
        row["sure"] += int(sure)
        row["sure_right"] += int(sure and p["right"])
        row["right"] += int(bool(p["right"]))
    return {**row, **accuracy.sure_numbers(row)}


def fit(out: Path, write: bool) -> None:
    """Fit the calibration on the key and measure it honestly (each pack with the others' fit)."""
    import os

    os.environ["RPGGEN_CALIBRATION"] = "off"  # the fit reads the readers' own confidences
    from rpggen import analyze_cmd, jsonio
    from rpggen.core import calibration

    summary = analyze_cmd.run_private_corpus(out / "corpus", [])
    publisher_of = {p["name"]: p["publisher"] for p in load_packs(out)}
    pictures = {name: rep["pictures"] for name, rep in summary["packs"].items()}
    auto, confirmed = catalog.AUTO_CONFIDENCE, catalog.CONFIRMED_CONFIDENCE
    rows: dict[str, dict[str, Any]] = {}
    for name, own in sorted(pictures.items()):
        others = [p for n, ps in pictures.items() if n != name for p in ps]
        table = calibration.fit(others, auto, confirmed)
        rows[name] = {
            "before": _sure_counts(own, lambda p: p["sure"]),
            "after": _sure_counts(
                own,
                lambda p, t=table: (
                    calibration.calibrate_with(
                        t,
                        p["reader"],
                        p.get("role", ""),
                        float(p["confidence"]),
                        p.get("publisher", ""),
                    )
                    >= auto
                ),
            ),
        }
    by_publisher: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for name in pictures:
        slot = by_publisher.setdefault(publisher_of.get(name, "?"), {"before": [], "after": []})
        slot["before"].append(rows[name]["before"])
        slot["after"].append(rows[name]["after"])

    def merged(parts: list[dict[str, Any]]) -> dict[str, Any]:
        keys = ("pictures", "sure", "sure_right", "right")
        row = {k: sum(int(p[k]) for p in parts) for k in keys}
        return {**row, **accuracy.sure_numbers(row)}

    def pct(v: float | None) -> str:
        return "n/a" if v is None else f"{100 * v:.1f} %"

    lines = [
        "# Calibration on the answer key",
        "",
        "Sure: confirmed, or confidence at Auto-detected or above. *After*: each pack with a",
        "table fitted on the other packs (leave one pack out), so the numbers are what a new",
        "pack would see.",
        "",
        "| Pack | Pictures | Sure before | Sure right before | Sure after | Sure right after |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, row in rows.items():
        b, a = row["before"], row["after"]
        lines.append(
            f"| {name} | {b['pictures']} | {pct(b['sure_share'])} | {pct(b['sure_accuracy'])} | "
            f"{pct(a['sure_share'])} | {pct(a['sure_accuracy'])} |"
        )
    lines += ["", "| Publisher | Pictures | Sure before | Sure right before | Sure after | "
              "Sure right after |", "|---|---:|---:|---:|---:|---:|"]  # fmt: skip
    for publisher, slot in sorted(by_publisher.items()):
        b, a = merged(slot["before"]), merged(slot["after"])
        lines.append(
            f"| {publisher} | {b['pictures']} | {pct(b['sure_share'])} | "
            f"{pct(b['sure_accuracy'])} | {pct(a['sure_share'])} | {pct(a['sure_accuracy'])} |"
        )
    every_b = merged([r["before"] for r in rows.values()])
    every_a = merged([r["after"] for r in rows.values()])
    lines.append(
        f"| **all** | {every_b['pictures']} | {pct(every_b['sure_share'])} | "
        f"{pct(every_b['sure_accuracy'])} | {pct(every_a['sure_share'])} | "
        f"{pct(every_a['sure_accuracy'])} |"
    )
    if summary["missing"]:
        lines += ["", "Not found: " + ", ".join(summary["missing"])]
    (out / "fit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    jsonio.write(out / "fit_report.json", {"packs": rows, "missing": summary["missing"]})
    print("\n".join(lines))
    if write:
        table = calibration.fit([p for ps in pictures.values() for p in ps], auto, confirmed)
        calibration.TABLE.write_text(
            json.dumps(table, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"wrote {calibration.TABLE} ({len(table['bins'])} bins)")


SIZE_BANDS = ((0, 24), (24, 48), (48, 96), (96, 1 << 30))  # the larger side, px
VISION_USAGES = frozenset({"sprite", "object", "iso_tile", "portrait", "ui", "growth_strip"})


def _band(size: int) -> str:
    for lo, hi in SIZE_BANDS:
        if lo <= size < hi:
            return f"{lo}-{hi - 1}" if hi < 1 << 30 else f"{lo}+"
    return "?"


def vision_sample(out: Path, per_pack: int) -> list[dict[str, Any]]:
    """Up to ``per_pack`` pictures of each pack for the vision step: pictures (not sheets of
    tiles) rpggen is not sure of first, then sure ones, in an order fixed by their keys."""
    import hashlib

    picked = []
    for pack in load_packs(out):
        if not (out / "draft" / f"{pack['name']}.json").is_file():
            continue
        doc = key_of(out, pack["name"])
        rows = []
        for key, e in doc["entries"].items():
            if e["answer"].get("usage") not in VISION_USAGES or not e["answer"].get("role"):
                continue
            unsure = e["draft"]["status"] not in ("CONFIRMED", "AUTO_DETECTED")
            order = hashlib.sha256(key.encode("utf-8")).hexdigest()
            rows.append((not unsure, order, key, e))
        for sure, _order, key, e in sorted(rows)[:per_pack]:
            picked.append(
                {
                    "pack": pack["name"],
                    "publisher": pack["publisher"],
                    "key": key,
                    "file": e["file"],
                    "draft_role": e["facets"].get("role"),
                    "key_role": e["answer"].get("role"),
                    "draft_sure": sure,
                }
            )
    return picked


def vision(
    out: Path, per_pack: int, server: Path, model: Path, projector: Path, write: bool
) -> None:
    """Ask the local vision model about a sample of the key and measure, per size band and per
    role it names, how often its role is the key's beside how often rpggen's is
    (``DIR/vision_report.md``): where it is right more often, it may change rpggen's answer."""
    import hashlib

    from PIL import Image

    from rpggen.core import vision as vision_mod
    from rpggen.core.vision.llama import LlamaConfig

    sample = vision_sample(out, per_pack)
    for row in sample:
        data = Path(row["file"]).read_bytes()
        row["sha"] = hashlib.sha256(data).hexdigest()
        with Image.open(row["file"]) as img:
            row["size"] = max(img.size)
    config = LlamaConfig(server, model, projector)
    answers = vision_mod.ask_all(config, [(r["sha"], Path(r["file"])) for r in sample])
    for row in sample:
        found = answers[row["sha"]]
        row["vision_raw"], row["vision_role"] = found.raw, found.role
    (out / "vision.json").write_text(json.dumps(sample, indent=1), encoding="utf-8")

    measure_vision(out, sample, per_pack, write)


def measure_vision(
    out: Path, sample: list[dict[str, Any]], per_pack: int, write: bool
) -> dict[str, Any]:
    """Where the vision step helps: on the pictures the key uses (not NONE: whether a picture
    is set aside is the pack's matter, not the picture's) that rpggen is not sure of, per role
    the model names, how often its role is the key's beside how often rpggen's is. A role
    whose model accuracy, at the lower end of its 95 % interval, beats rpggen's on the same
    pictures is one the step may give (``rpggen/data/vision_rules.json`` with ``write``)."""
    from rpggen.core import calibration
    from rpggen.core import vision as vision_mod

    def person_ok(role: str | None, want: str | None) -> bool:
        return role == want or (role == vision_mod.PERSON and want in ("PLAYER", "NPC"))

    for row in sample:
        row["vision_role"] = vision_mod.role_of(row["vision_raw"])
    used = [r for r in sample if r["key_role"] != "NONE"]
    bands: dict[str, list[int]] = {}
    roles: dict[str, list[int]] = {}
    for row in used:
        v_ok = person_ok(row["vision_role"], row["key_role"])
        d_ok = row["draft_role"] == row["key_role"]
        keys = [(bands, _band(row["size"]))]
        if not row["draft_sure"]:
            keys.append((roles, str(row["vision_role"])))
        for table, k in keys:
            t = table.setdefault(k, [0, 0, 0, 0])  # pictures, vision right, rpggen right, fixed
            t[0] += 1
            t[1] += int(v_ok)
            t[2] += int(d_ok)
            t[3] += int(v_ok and not d_ok)
    helps = {}
    for role, (n, v, d, _f) in roles.items():
        low = calibration.wilson_low(v, n)
        if role not in ("None", vision_mod.PERSON) and n and low > d / n:
            helps[role] = {"pictures": n, "vision_low": round(low, 4), "rpggen": round(d / n, 4)}

    def pct(a: int, b: int) -> str:
        return f"{100 * a / b:.0f} %" if b else "n/a"

    lines = [
        "# The vision step on the answer key",
        "",
        f"{len(sample)} pictures asked ({per_pack} a pack at most, unsure ones first); "
        f"{len(sample) - len(used)} of them are set aside (NONE) in the key and left out.",
        "",
        "All pictures the key uses, by size:",
        "",
        "| Size (px) | Pictures | Vision right | rpggen right | rpggen wrong, vision right |",
        "|---|---:|---:|---:|---:|",
    ]
    for k in [_band(lo) for lo, _ in SIZE_BANDS]:
        if k in bands:
            n, v, d, f = bands[k]
            lines.append(f"| {k} | {n} | {pct(v, n)} | {pct(d, n)} | {f} |")
    lines += [
        "",
        "Pictures rpggen is not sure of, by the role the model names:",
        "",
        "| Vision says | Pictures | Vision right | rpggen right | rpggen wrong, vision right "
        "| Vision may change it |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for k, (n, v, d, f) in sorted(roles.items(), key=lambda kv: -kv[1][0]):
        may = "yes" if k in helps else ""
        lines.append(f"| {k} | {n} | {pct(v, n)} | {pct(d, n)} | {f} | {may} |")
    (out / "vision_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    rules = {"version": vision_mod.RULES_VERSION, "roles": dict(sorted(helps.items()))}
    if write:
        text = json.dumps(rules, indent=1, sort_keys=True) + "\n"
        vision_mod.RULES.write_text(text, encoding="utf-8")
        print(f"wrote {vision_mod.RULES}")
    return rules


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for cmd in ("draft", "sheets"):
        p = sub.add_parser(cmd)
        p.add_argument("--out", required=True, type=Path)
        p.add_argument("--pack", action="append")
    p = sub.add_parser("serve")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--port", type=int, default=8765)
    p = sub.add_parser("corpus")
    p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser("fit")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--write", action="store_true")
    p = sub.add_parser("vision")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--per-pack", type=int, default=80)
    p.add_argument("--server", required=True, type=Path)
    p.add_argument("--model", required=True, type=Path)
    p.add_argument("--projector", required=True, type=Path)
    p.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "draft":
        draft(args.out, args.pack)
    elif args.cmd == "sheets":
        sheets(args.out, args.pack)
    elif args.cmd == "serve":
        serve(args.out, args.port)
    elif args.cmd == "corpus":
        corpus(args.out)
    elif args.cmd == "fit":
        fit(args.out, args.write)
    elif args.cmd == "vision":
        vision(args.out, args.per_pack, args.server, args.model, args.projector, args.write)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
