"""Render the fidelity comps in DaVinci Resolve and keep what Resolve makes of them as test fixtures.

For each fidelity/comps/<name>.comp: import it into a fresh Fusion composition, save the comp as Resolve writes it
to tests/fixtures/<name>.comp, and render frames 0, 5, 10, 15 and 20 to tests/fixtures/<name>/f_####.png.

Run with DaVinci Resolve Studio open and external scripting enabled (Preferences → System → General):
    python3 fidelity/render_in_resolve.py [name ...]
Resolve then needs restarting before another import: after a render through the API it refuses new timelines.
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPS = ROOT / "fidelity" / "comps"
FIXTURES = ROOT / "tests" / "fixtures"
PROJECT = "fusion2lottie fidelity"
KEEP = (0, 5, 10, 15, 20)


def connect():
    sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules")
    import DaVinciResolveScript  # noqa: E402

    return DaVinciResolveScript.scriptapp("Resolve")


def run(resolve, names=None):
    pm = resolve.GetProjectManager()
    project = pm.LoadProject(PROJECT) or pm.CreateProject(PROJECT)
    for key, value in (("timelineResolutionWidth", "512"), ("timelineResolutionHeight", "512"),
                       ("timelineFrameRate", "30")):
        project.SetSetting(key, value)
    pool = project.GetMediaPool()
    comps = {}
    for path in sorted(COMPS.glob("*.comp")):
        if names and path.stem not in names:
            continue
        # A Fusion clip accepts one import, so each comp gets a timeline of its own.
        timeline = pool.CreateEmptyTimeline(f"{path.stem} {len(list(pool.GetRootFolder().GetClipList()))}")
        if timeline is None:
            raise SystemExit("Resolve refused a new timeline: restart it (it does this after an API render)")
        project.SetCurrentTimeline(timeline)
        item = timeline.InsertFusionCompositionIntoTimeline()
        if item.ImportFusionComp(str(path)) is None:
            raise SystemExit(f"Resolve could not import {path.name}")
        saved = FIXTURES / f"{path.stem}.comp"
        item.ExportFusionComp(str(saved), 1)
        # The saved comp names the user's cache folder: keep that out of the fixtures.
        saved.write_text(re.sub(r'\["ResolveCaches:"\] = "[^"]*"', '["ResolveCaches:"] = "/path/to/CacheClip/Fusion"',
                                saved.read_text()))
        comps[path.stem] = item.GetFusionCompByIndex(1)

    for name, comp in comps.items():
        frames = FIXTURES / name
        shutil.rmtree(frames, ignore_errors=True)
        frames.mkdir(parents=True)
        saver = comp.AddTool("Saver", 0, 0)
        saver.SetInput("Clip", str(frames / "f_.png"))
        saver.Input.ConnectTo(comp.FindTool("Over").Output)
        comp.Render({"Start": 0, "End": max(KEEP), "Wait": True})
        saver.Delete()
        for png in frames.glob("f_*.png"):
            if int(png.stem[2:]) not in KEEP:
                png.unlink()
        print(f"{name}: {len(list(frames.glob('*.png')))} frames")
    project_manager_save = pm.SaveProject()
    return sorted(comps), project_manager_save


if __name__ == "__main__":
    print(run(connect(), sys.argv[1:] or None))
