"""Write the fidelity compositions: small comps that each exercise one family of Fusion shape tools.

Each comp is rendered by Resolve (render_in_resolve.py) and the Resolve-saved comp and frames become test fixtures.
Run: uv run fidelity/make_comps.py
"""
from pathlib import Path

OUT = Path(__file__).parent / "comps"
SIZE = 512
END = 20


def spline(name, keys):
    """keys: [(frame, value)], eased in and out."""
    rows = []
    for i, (t, v) in enumerate(keys):
        parts = [f"{v}"]
        if i > 0:
            parts.append(f"LH = {{ {t - (t - keys[i - 1][0]) / 3:.4f}, {v} }}")
        if i < len(keys) - 1:
            parts.append(f"RH = {{ {t + (keys[i + 1][0] - t) / 3:.4f}, {v} }}")
        rows.append(f"[{t}] = {{ {', '.join(parts)} }},")
    return f"{name} = BezierSpline {{ KeyFrames = {{ {' '.join(rows)} }} }},"


def tool(name, kind, inputs, anim=None):
    rows = [f"[\"{k}\"] = Input {{ {v} }}," for k, v in inputs.items()]
    extra = []
    for k, keys in (anim or {}).items():
        rows.append(f'["{k}"] = Input {{ SourceOp = "{name}{k.replace(".", "")}", Source = "Value" }},')
        extra.append(spline(f"{name}{k.replace('.', '')}", keys))
    return [f"{name} = {kind} {{ Inputs = {{ {' '.join(rows)} }} }},"] + extra


def color(r, g, b):
    return {"Red": f"Value = {r}", "Green": f"Value = {g}", "Blue": f"Value = {b}"}


def comp(name, shapes):
    """shapes: list of (tool name, lines). Merged in order, rendered over a dark background."""
    lines = []
    for _, tl in shapes:
        lines += tl
    merge = {f"Input{i + 1}": f'SourceOp = "{n}", Source = "Output"' for i, (n, _) in enumerate(shapes)}
    lines += tool("All", "sMerge", merge)
    lines += tool("Render", "sRender", {"Width": f"Value = {SIZE}", "Height": f"Value = {SIZE}",
                                        "Input": 'SourceOp = "All", Source = "Output"'})
    lines += tool("Back", "Background", {"Width": f"Value = {SIZE}", "Height": f"Value = {SIZE}",
                                         "TopLeftRed": "Value = 0.08", "TopLeftGreen": "Value = 0.08",
                                         "TopLeftBlue": "Value = 0.1"})
    lines += tool("Over", "Merge", {"Background": 'SourceOp = "Back", Source = "Output"',
                                    "Foreground": 'SourceOp = "Render", Source = "Output"'})
    lines += tool("MediaOut1", "Saver", {"Index": 'Value = "0"', "Input": 'SourceOp = "Over", Source = "Output"'})
    text = (f"Composition {{\n\tCurrentTime = 0,\n\tRenderRange = {{ 0, {END} }},\n\tGlobalRange = {{ 0, {END} }},\n"
            "\tTools = {\n" + "".join(f"\t\t{line}\n" for line in lines) + "\t},\n}\n")
    OUT.mkdir(exist_ok=True)
    (OUT / f"{name}.comp").write_text(text)


def at(x, y):
    return {"Translate.X": f"Value = {x}", "Translate.Y": f"Value = {y}"}


comp("rectangles", [
    ("Plain", tool("Plain", "sRectangle", {**at(-0.25, 0.2), "Width": "Value = 0.3", "Height": "Value = 0.15",
                                           **color(0.9, 0.35, 0.2)})),
    ("Rounded", tool("Rounded", "sRectangle", {**at(0.2, 0.2), "Width": "Value = 0.3", "Height": "Value = 0.2",
                                               "CornerRadius": "Value = 0.4", "Angle": "Value = 20",
                                               **color(0.2, 0.75, 0.7)})),
    ("Growing", tool("Growing", "sRectangle", {**at(0, -0.2), "Height": "Value = 0.1", **color(0.93, 0.9, 0.85)},
                     anim={"Width": [(0, 0.05), (20, 0.6)], "Angle": [(0, 0), (20, 45)]})),
])

comp("ellipses", [
    ("Circle", tool("Circle", "sEllipse", {**at(-0.25, 0.2), "Width": "Value = 0.2", "Height": "Value = 0.2",
                                           **color(0.9, 0.35, 0.2)})),
    ("Oval", tool("Oval", "sEllipse", {**at(0.2, 0.15), "Width": "Value = 0.35", "Height": "Value = 0.15",
                                       "Angle": "Value = 30", **color(0.2, 0.75, 0.7)})),
    ("Breathing", tool("Breathing", "sEllipse", {**at(0, -0.2), "Width": "Value = 0.3", **color(0.93, 0.9, 0.85)},
                       anim={"Height": [(0, 0.02), (10, 0.25), (20, 0.1)]})),
])

comp("polygons", [
    ("Pentagon", tool("Pentagon", "sNGon", {**at(-0.25, 0.2), "Sides": "Value = 5", "Width": "Value = 0.25",
                                            "Height": "Value = 0.25", **color(0.9, 0.35, 0.2)})),
    ("Hexagon", tool("Hexagon", "sNGon", {**at(0.2, 0.2), "Width": "Value = 0.35", "Height": "Value = 0.2",
                                          "Angle": "Value = 15", **color(0.2, 0.75, 0.7)})),
    ("Turning", tool("Turning", "sNGon", {**at(0, -0.2), "Sides": "Value = 3", "Width": "Value = 0.25",
                                          "Height": "Value = 0.25", **color(0.93, 0.9, 0.85)},
                     anim={"Angle": [(0, 0), (20, 120)]})),
])

comp("stars", [
    ("Five", tool("Five", "sStar", {**at(-0.25, 0.2), "Points": "Value = 5", "Width": "Value = 0.3",
                                    "Height": "Value = 0.3", **color(0.9, 0.35, 0.2)})),
    ("Spiky", tool("Spiky", "sStar", {**at(0.2, 0.2), "Points": "Value = 8", "Depth": "Value = 0.25",
                                      "Width": "Value = 0.35", "Height": "Value = 0.25", "Angle": "Value = 10",
                                      **color(0.2, 0.75, 0.7)})),
    ("Pulsing", tool("Pulsing", "sStar", {**at(0, -0.2), "Points": "Value = 4", "Width": "Value = 0.3",
                                          "Height": "Value = 0.3", **color(0.93, 0.9, 0.85)},
                     anim={"Depth": [(0, 0.1), (20, 0.8)]})),
])

open_path = ('Value = Polyline { Closed = false, Points = { { Linear = true, X = -0.15, Y = -0.05 }, '
             '{ Linear = true, X = 0, Y = 0.08 }, { Linear = true, X = 0.15, Y = -0.05 } } }')
comp("outlines", [
    ("Frame", tool("Frame", "sRectangle", {**at(-0.25, 0.2), "Width": "Value = 0.3", "Height": "Value = 0.2",
                                           "Solid": "Value = 0", "BorderWidth": "Value = 0.02",
                                           **color(0.9, 0.35, 0.2)})),
    ("Ring", tool("Ring", "sEllipse", {**at(0.2, 0.2), "Width": "Value = 0.25", "Height": "Value = 0.25",
                                       "Solid": "Value = 0", "BorderWidth": "Value = 0.01", **color(0.2, 0.75, 0.7)})),
    ("Bevel", tool("Bevel", "sPolygon", {"Center": "Value = { -0.25, -0.15 }", "Polyline": open_path,
                                         "Solid": "Value = 0", "BorderWidth": "Value = 0.025", "JoinStyle": "Value = 0",
                                         "CapStyle": "Value = 0", **color(0.93, 0.9, 0.85)})),
    ("Round", tool("Round", "sPolygon", {"Center": "Value = { 0.2, -0.15 }", "Polyline": open_path,
                                         "Solid": "Value = 0", "BorderWidth": "Value = 0.025", "JoinStyle": "Value = 2",
                                         "CapStyle": "Value = 2", **color(0.93, 0.9, 0.85)})),
    ("Thick", tool("Thick", "sPolygon", {"Center": "Value = { 0, -0.32 }", "Polyline": open_path,
                                         "Solid": "Value = 0", "JoinStyle": "Value = 1", "CapStyle": "Value = 1",
                                         **color(0.9, 0.35, 0.2)},
                   anim={"BorderWidth": [(0, 0.005), (20, 0.04)]})),
])

comp("write-on", [
    ("Drawing", tool("Drawing", "sEllipse", {**at(-0.2, 0.15), "Width": "Value = 0.3", "Height": "Value = 0.3",
                                             "Solid": "Value = 0", "BorderWidth": "Value = 0.02",
                                             **color(0.9, 0.35, 0.2)},
                     anim={"WriteLength": [(0, 0), (20, 1)]})),
    ("Sliding", tool("Sliding", "sRectangle", {**at(0.2, 0.15), "Width": "Value = 0.3", "Height": "Value = 0.3",
                                               "Solid": "Value = 0", "BorderWidth": "Value = 0.02",
                                               "WriteLength": "Value = 0.3", **color(0.2, 0.75, 0.7)},
                     anim={"WritePosition": [(0, 0), (20, 1)]})),
    ("Line", tool("Line", "sPolygon", {"Center": "Value = { 0, -0.2 }", "Polyline": open_path,
                                       "Solid": "Value = 0", "BorderWidth": "Value = 0.02",
                                       **color(0.93, 0.9, 0.85)},
                  anim={"WriteLength": [(0, 0), (20, 1)]})),
])

print("wrote", ", ".join(sorted(p.stem for p in OUT.glob("*.comp"))))
