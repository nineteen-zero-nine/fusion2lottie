"""Exporting from inside DaVinci Resolve: the Workspace → Scripts → Export to Lottie menu entry, and its installer.

Inside Resolve the converter gets what the comp file lacks: the timeline's frame rate, and the values Fusion gives
inputs driven by expressions or modifiers, sampled at every frame through Fusion's API.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from . import __version__
from .comp import parse
from .convert import ConversionError, convert, frame_range, needs_samples

MENU_SCRIPT = "Export to Lottie.py"


# --- inside Resolve ---------------------------------------------------------------------------------------------

def timeline_fps(timeline) -> float:
    return float(timeline.GetSetting("timelineFrameRate"))


def sample(fusion_comp, needs: list[str], start: int, end: int) -> dict:
    """Fusion's value for each "Tool.Input" at every frame from start to end."""
    samples = {}
    for key in needs:
        tool_name, input_name = key.split(".", 1)  # tool names have no dots; inputs can (Translate.X)
        tool = fusion_comp.FindTool(tool_name)
        values = []
        for frame in range(start, end + 1):
            v = tool.GetInput(input_name, frame)
            if isinstance(v, dict):  # a point: {1: x, 2: y, 3: z}
                v = [float(v[k]) for k in sorted(v, key=lambda k: float(k))[:2]]
            values.append(v)
        samples[key] = values
    return samples


def export_item(item, output: Path, fps: float, comp_index: int = 1) -> list[str]:
    """Convert one of a timeline item's Fusion compositions to a Lottie file. Return the notes; raise
    ConversionError with every problem when it cannot convert."""
    with tempfile.TemporaryDirectory() as tmp:
        saved = Path(tmp) / "comp.comp"
        if not item.ExportFusionComp(str(saved), comp_index):
            raise ConversionError([f"Resolve could not save composition {comp_index} of {item.GetName()}"])
        comp = parse(saved.read_text())
    start, end = frame_range(comp)
    needs = needs_samples(comp)
    samples = sample(item.GetFusionCompByIndex(comp_index), needs, start, end) if needs else None
    lottie, notes = convert(comp, fps, samples)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(lottie, separators=(",", ":")))
    if needs:
        notes.insert(0, f"sampled in Resolve: {', '.join(needs)}")
    return notes


def default_folder() -> Path:
    for name in ("Movies", "Videos"):
        if (Path.home() / name).is_dir():
            return Path.home() / name
    return Path.home()


def menu(resolve, fusion=None):
    """The Export to Lottie menu entry: export the Fusion clip under the playhead."""
    project = resolve.GetProjectManager().GetCurrentProject()
    timeline = project.GetCurrentTimeline() if project else None
    item = timeline.GetCurrentVideoItem() if timeline else None
    if item is None or not item.GetFusionCompCount():
        message = ("Export to Lottie: put the playhead over a clip with a Fusion composition on the timeline, "
                   "then run it again.")
        print(message)
        comp = fusion.GetCurrentComp() if fusion else None
        if comp:
            comp.AskUser("Export to Lottie", {1: {1: "Message", 2: "Text", "Default": message, "ReadOnly": True,
                                                  "Lines": 3, "Wrap": True}})
        return
    names = item.GetFusionCompNameList()
    comp = item.GetFusionCompByIndex(1)
    controls = {1: {1: "Output", 2: "FileBrowse", "Name": "Lottie file", "Save": True,
                    "Default": str(default_folder() / f"{item.GetName()}.json")},
                2: {1: "FPS", 2: "Screw", "Name": "Frame rate", "Default": timeline_fps(timeline), "Min": 1,
                    "Max": 240}}
    if len(names) > 1:
        controls[3] = {1: "Comp", 2: "Dropdown", "Name": "Composition",
                       "Options": {i + 1: n for i, n in enumerate(names)}, "Default": 0}
    answer = comp.AskUser(f"Export to Lottie — {item.GetName()}", controls)
    if not answer:
        return
    output = Path(answer["Output"]).expanduser()
    if output.suffix.lower() != ".json":
        output = output.with_suffix(".json")
    index = int(answer.get("Comp", 0)) + 1
    try:
        notes = export_item(item, output, float(answer["FPS"]), index)
        report = f"Wrote {output}\n" + "".join(f"\n• {n}" for n in notes)
    except ConversionError as e:
        report = ("This composition uses what Lottie cannot show exactly:\n" +
                  "".join(f"\n• {p}" for p in e.problems))
    print(report)
    comp.AskUser("Export to Lottie", {1: {1: "Report", 2: "Text", "Default": report, "ReadOnly": True,
                                          "Lines": 12, "Wrap": True}})


# --- installing the menu entry ----------------------------------------------------------------------------------

def scripts_folder() -> Path:
    """Resolve's per-user Scripts/Utility folder: scripts there are listed under Workspace → Scripts on every page."""
    if sys.platform == "darwin":
        base = Path.home() / "Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts"
    elif sys.platform == "win32":
        base = Path(os.environ["APPDATA"]) / "Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts"
    else:
        base = Path.home() / ".local/share/DaVinciResolve/Fusion/Scripts"
    return base / "Utility"


def library_folder() -> Path:
    """Where the installer keeps its own copy of fusion2lottie, for Resolve's Python, which has no pip."""
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/fusion2lottie"
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / "fusion2lottie"
    return Path.home() / ".local/share/fusion2lottie"


LAUNCHER = '''# Export to Lottie — installed by fusion2lottie {version} (`fusion2lottie install-resolve`).
# Converts the Fusion clip under the playhead to a Lottie animation. Remove with `fusion2lottie uninstall-resolve`.
import sys

sys.path.insert(0, {library!r})
from fusion2lottie.resolve import menu

menu(resolve, fusion)  # noqa: F821 — Resolve defines these for the scripts it runs
'''


def install(scripts: Path | None = None, library: Path | None = None) -> Path:
    scripts, library = scripts or scripts_folder(), library or library_folder()
    package = Path(__file__).parent
    target = library / "fusion2lottie"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(package, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    scripts.mkdir(parents=True, exist_ok=True)
    launcher = scripts / MENU_SCRIPT
    launcher.write_text(LAUNCHER.format(version=__version__, library=str(library)))
    return launcher


def uninstall(scripts: Path | None = None, library: Path | None = None) -> list[Path]:
    scripts, library = scripts or scripts_folder(), library or library_folder()
    removed = []
    for path in (scripts / MENU_SCRIPT, library / "fusion2lottie"):
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(path)
        elif path.exists():
            path.unlink()
            removed.append(path)
    return removed
