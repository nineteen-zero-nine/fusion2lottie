"""Converting a Fusion composition to Lottie.

Fusion's shape system and Lottie's shape layers are close relatives: shapes, groups and transforms, animated by
cubic-bezier keyframes. Both facts the mapping rests on were checked against Resolve's own renders:

- Shape units are fractions of the comp's width, with the origin at the centre and y pointing up. Lottie works in
  pixels, with the origin at the top left and y pointing down.
- A Fusion BezierSpline segment is a cubic Bezier in (time, value), the model Lottie's easing uses, so keyframes
  convert exactly. Only channels whose key times differ are sampled once per frame ("baked").

Anything outside the supported subset is reported, never approximated: `convert` raises `ConversionError` naming
every problem, and `check` returns them.
"""
from __future__ import annotations

import re

from . import shapes
from .comp import Table

LOTTIE_VERSION = "5.12.0"

# The primitives: their geometry, the inputs that shape it (argument: (input, Fusion's default)), and the whole
# numbers among them, which cannot animate.
PRIMITIVES = {
    "sRectangle": (shapes.rectangle, {"width": ("Width", 0.5), "height": ("Height", 0.5),
                                      "corner_radius": ("CornerRadius", 0.0)}, {}),
    "sEllipse": (shapes.ellipse, {"width": ("Width", 0.5), "height": ("Height", 0.5)}, {}),
    "sNGon": (shapes.polygon, {"width": ("Width", 0.5), "height": ("Height", 0.5)}, {"sides": ("Sides", 6)}),
    "sStar": (shapes.star, {"width": ("Width", 0.5), "height": ("Height", 0.5), "depth": ("Depth", 0.5)},
              {"points": ("Points", 6)}),
}
# Fusion's JoinStyle and CapStyle to Lottie's lj (1 miter, 2 round, 3 bevel) and lc (1 butt, 2 round, 3 square).
JOINS = {0: 3, 1: 2, 2: 1}
CAPS = {0: 1, 1: 2, 2: 3}


def bezier_ease(x1, y1, x2, y2, x):
    """Lottie's easing: the cubic Bezier from (0, 0) to (1, 1) with these handles, solved for x."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        s = (lo + hi) / 2
        lo, hi = (s, hi) if 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s ** 3 < x else (lo, s)
    s = (lo + hi) / 2
    return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s * s * y2 + s ** 3


class ConversionError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


class Unsupported(Exception):
    """Raised inside the converter for one tool; recorded as a problem and the tool skipped."""


def convert(comp: Table, fps: float = 30.0) -> tuple[dict, list[str]]:
    """Return (lottie, notes). Raise ConversionError when the comp uses anything outside the supported subset."""
    converter = _Converter(comp, fps)
    lottie = converter.export()
    if converter.problems:
        raise ConversionError(converter.problems)
    return lottie, converter.notes


def check(comp: Table, fps: float = 30.0) -> list[str]:
    """Every problem that would stop `convert`, without writing anything."""
    converter = _Converter(comp, fps)
    converter.export()
    return converter.problems


class _Converter:
    def __init__(self, comp: Table, fps: float):
        if not isinstance(comp, Table) or comp.kind != "Composition":
            raise ConversionError(["not a Fusion composition (expected `Composition { ... }`)"])
        self.tools = comp["Tools"]
        self.fps = fps
        fmt = comp.get("Prefs", {}).get("Comp", {}).get("FrameFormat", {})
        self.w, self.h = int(fmt.get("Width", 1920)), int(fmt.get("Height", 1080))
        # Resolve sets GlobalRange to the clip's length; the animation's own range is RenderRange.
        rng = comp.get("RenderRange")
        rng = rng if rng is not None else comp["GlobalRange"]
        self.start, self.end = (int(v) for v in rng.items_)
        self.problems: list[str] = []
        self.notes: list[str] = []

    # --- inputs -------------------------------------------------------------------------------------------------

    def raw(self, tool, name, default=None):
        """An input's static value, ('op', name) when it is driven by another tool, or `default`."""
        inp = self.tools[tool].get("Inputs", {}).get(name)
        if inp is None:
            return default
        if "SourceOp" in inp:
            return ("op", inp["SourceOp"])
        val = inp.get("Value", default)
        if isinstance(val, Table) and val.kind is None and not val:
            return val.items_
        if isinstance(val, Table) and val.kind == "FuID":  # an enumerated choice: FuID { "Screen" }
            return val.items_[0]
        return val

    def source(self, tool, name):
        r = self.raw(tool, name)
        return r[1] if isinstance(r, tuple) else None

    def spline(self, op):
        node = self.tools.get(op)
        if node is None or node.kind != "BezierSpline":
            raise Unsupported(f"{op}: {node.kind if node is not None else 'missing'} modifier — only BezierSpline "
                              "keyframes convert")
        keys = []
        for t, k in sorted(node["KeyFrames"].items()):
            keys.append({"t": t, "v": k.items_[0], "lh": k.get("LH"), "rh": k.get("RH"),
                         "linear": bool(k.get("Flags", {}).get("Linear"))})
        return keys

    def number(self, tool, name, default):
        """A scalar input as ('static', value) or ('keys', keyframes)."""
        r = self.raw(tool, name, default)
        if isinstance(r, tuple):
            return ("keys", self.spline(r[1]))
        return ("static", float(r))

    def static(self, tool, name, default):
        r = self.raw(tool, name, default)
        if isinstance(r, tuple):
            raise Unsupported(f"{tool}.{name}: animating this input is not supported")
        return r

    def require(self, tool, name, default, what):
        """Refuse a tool whose input is animated or set away from its default."""
        r = self.raw(tool, name, default)
        if isinstance(r, tuple) or (isinstance(default, (int, float)) and float(r) != default) or \
                (isinstance(default, str) and r != default):
            raise Unsupported(f"{tool}.{name}: {what} is not supported")

    # --- keyframes ----------------------------------------------------------------------------------------------

    @staticmethod
    def handles(keys, i):
        a, b = keys[i], keys[i + 1]
        dt, dv = b["t"] - a["t"], b["v"] - a["v"]
        if a["linear"] and a["rh"] is None:
            return (a["t"] + dt / 3, a["v"] + dv / 3), (b["t"] - dt / 3, b["v"] - dv / 3)
        p1 = tuple(a["rh"].items_) if a["rh"] is not None else (a["t"] + dt / 3, a["v"] + dv / 3)
        p2 = tuple(b["lh"].items_) if b["lh"] is not None else (b["t"] - dt / 3, b["v"] - dv / 3)
        return p1, p2

    def value_at(self, channel, t):
        if channel[0] == "static":
            return channel[1]
        keys = channel[1]
        if t <= keys[0]["t"]:
            return keys[0]["v"]
        if t >= keys[-1]["t"]:
            return keys[-1]["v"]
        i = max(j for j in range(len(keys) - 1) if keys[j]["t"] <= t)
        a, b = keys[i], keys[i + 1]
        (t1, v1), (t2, v2) = self.handles(keys, i)
        lo, hi = 0.0, 1.0  # solve the curve's time for t, then read its value there
        for _ in range(60):
            s = (lo + hi) / 2
            bt = (1 - s) ** 3 * a["t"] + 3 * (1 - s) ** 2 * s * t1 + 3 * (1 - s) * s * s * t2 + s ** 3 * b["t"]
            lo, hi = (s, hi) if bt < t else (lo, s)
        s = (lo + hi) / 2
        return (1 - s) ** 3 * a["v"] + 3 * (1 - s) ** 2 * s * v1 + 3 * (1 - s) * s * s * v2 + s ** 3 * b["v"]

    def ease(self, channel, i):
        """Lottie's (o.x, o.y, i.x, i.y) for segment i, or None when it cannot be written as one easing curve."""
        keys = channel[1]
        a, b = keys[i], keys[i + 1]
        (t1, v1), (t2, v2) = self.handles(keys, i)
        dt, dv = b["t"] - a["t"], b["v"] - a["v"]
        if abs(dv) < 1e-12:
            if abs(v1 - a["v"]) > 1e-9 or abs(v2 - a["v"]) > 1e-9:
                return None  # leaves its value and comes back: not an easing between two values
            return ((t1 - a["t"]) / dt, 0.0, (t2 - a["t"]) / dt, 1.0)
        return ((t1 - a["t"]) / dt, (v1 - a["v"]) / dv, (t2 - a["t"]) / dt, (v2 - a["v"]) / dv)

    def prop(self, channels, maps):
        """A Lottie property from scalar channels, each mapped by an affine function (which keeps easing intact)."""
        if all(c[0] == "static" for c in channels):
            vals = [m(c[1]) for c, m in zip(channels, maps)]
            return {"a": 0, "k": vals if len(vals) > 1 else vals[0]}
        animated = [c for c in channels if c[0] == "keys"]
        times = [tuple(k["t"] for k in c[1]) for c in animated]
        if all(t == times[0] for t in times):
            keyframes = self.keyframes(channels, maps, list(times[0]))
            if keyframes is not None:
                return {"a": 1, "k": keyframes}
        self.notes.append("sampled once per frame: " + ", ".join(sorted({str(len(t)) + " keys" for t in times})))
        return self.baked(channels, maps)

    def keyframes(self, channels, maps, times):
        out = []
        for i, t in enumerate(times):
            kf = {"t": t - self.start, "s": [m(self.value_at(c, t)) for c, m in zip(channels, maps)]}
            if i < len(times) - 1:
                eases = [self.ease(c, i) if c[0] == "keys" else (1 / 3, 1 / 3, 2 / 3, 2 / 3) for c in channels]
                if any(e is None for e in eases):
                    return None
                kf["o"] = {"x": [e[0] for e in eases], "y": [e[1] for e in eases]}
                kf["i"] = {"x": [e[2] for e in eases], "y": [e[3] for e in eases]}
            out.append(kf)
        return out

    def baked(self, channels, maps):
        n = len(channels)
        return {"a": 1, "k": [{"t": f - self.start, "s": [m(self.value_at(c, f)) for c, m in zip(channels, maps)],
                               "o": {"x": [0] * n, "y": [0] * n}, "i": {"x": [1] * n, "y": [1] * n}}
                              for f in range(self.start, self.end + 1)]}

    # --- coordinates --------------------------------------------------------------------------------------------

    def px_x(self, u):
        return self.w / 2 + u * self.w

    def px_y(self, v):
        return self.h / 2 - v * self.w

    def transform(self, tool, *, anchor=(0.0, 0.0), pos, scale, rot, opacity=None):
        return {"ty": "tr", "nm": f"{tool} transform",
                "a": {"a": 0, "k": [self.px_x(anchor[0]), self.px_y(anchor[1])]},
                "p": self.prop(pos, [self.px_x, self.px_y]),
                "s": self.prop(scale, [lambda v: v * 100, lambda v: v * 100]),
                "r": self.prop([rot], [lambda v: -v]),
                "o": self.prop([opacity or ("static", 1.0)], [lambda v: v * 100]),
                "sk": {"a": 0, "k": 0}, "sa": {"a": 0, "k": 0}}

    def point(self, tool, name, default):
        r = self.static(tool, name, default)
        return [("static", float(r[0])), ("static", float(r[1]))]

    # --- shape tools --------------------------------------------------------------------------------------------

    def shape(self, tool):
        """The Lottie group for a shape tool, or None (with the problem recorded) when it cannot convert."""
        try:
            kind = self.tools[tool].kind
            if kind == "sPolygon":
                return self.polygon(tool)
            if kind in PRIMITIVES:
                return self.primitive(tool, kind)
            if kind == "sMerge":
                return self.smerge(tool)
            if kind == "sTransform":
                return self.stransform(tool)
            raise Unsupported(f"{tool}: the {kind} shape tool is not supported yet")
        except Unsupported as e:
            self.problems.append(str(e))
            return None

    def color(self, tool):
        color = [self.number(tool, c, 1.0) for c in ("Red", "Green", "Blue")]
        if any(c[0] == "keys" for c in color):
            return self.prop(color + [("static", 1.0)], [lambda x: x] * 4)
        return {"a": 0, "k": [ch[1] for ch in color] + [1]}

    def paint(self, tool):
        """What draws the path: a fill, or an outline (Solid off), after a trim when only part is written on."""
        items = []
        position, length = self.number(tool, "WritePosition", 0.0), self.number(tool, "WriteLength", 1.0)
        if position != ("static", 0.0) or length != ("static", 1.0):
            solid = self.static(tool, "Solid", 1) in (1, 1.0)
            # Fusion still draws the caps of an outline written on to nothing (a dot); Lottie draws nothing at zero
            # length, so keep a sliver. Scaling rather than clamping keeps the keyframes' easing exact.
            sliver = 0.0 if solid or int(self.static(tool, "CapStyle", 1)) == 0 else 0.01
            items.append({"ty": "tm", "nm": f"{tool} write on", "m": 1, "s": {"a": 0, "k": 0},
                          "e": self.prop([length], [lambda x: sliver + x * (100 - sliver)]),
                          "o": self.prop([position], [lambda x: x * 360])})
        alpha = self.prop([self.number(tool, "Alpha", 1.0)], [lambda x: x * 100])
        if self.static(tool, "Solid", 1) in (1, 1.0):
            self.require(tool, "BorderWidth", 0, "a border on a solid shape")
            items.append({"ty": "fl", "nm": f"{tool} fill", "c": self.color(tool), "o": alpha,
                          "r": 1 if self.static(tool, "FillMethod", 0) in (0, 0.0) else 2})
        else:
            join, cap = int(self.static(tool, "JoinStyle", 1)), int(self.static(tool, "CapStyle", 1))
            items.append({"ty": "st", "nm": f"{tool} outline", "c": self.color(tool), "o": alpha,
                          "w": self.prop([self.number(tool, "BorderWidth", 0.0)], [lambda x: x * self.w]),
                          "lj": JOINS[join], "lc": CAPS[cap], "ml": float(self.static(tool, "MiterLimit", 10))})
        return items

    def to_path(self, geometry, closed=True):
        v, i, o = geometry
        return {"c": closed, "v": [[x * self.w, -y * self.w] for x, y in v],
                "i": [[x * self.w, -y * self.w] for x, y in i], "o": [[x * self.w, -y * self.w] for x, y in o]}

    def path_prop(self, channels, geometry):
        """A path whose shape follows animated inputs: keyframed when one easing curve moves every vertex exactly as
        Fusion does, otherwise sampled once per frame."""
        animated = {n: c for n, c in channels.items() if c[0] == "keys"}
        values = {n: c[1] for n, c in channels.items()}
        if not animated:
            return {"a": 0, "k": self.to_path(geometry(**values))}

        def at(t):
            return geometry(**{n: self.value_at(c, t) for n, c in channels.items()})

        times = {tuple(k["t"] for k in c[1]) for c in animated.values()}
        if len(times) == 1:
            times = list(times.pop())
            eases = [{self.ease(c, s) for c in animated.values()} for s in range(len(times) - 1)]
            if all(len(e) == 1 and None not in e for e in eases):
                eases = [e.pop() for e in eases]
                if self.follows(at, times, eases):
                    return {"a": 1, "k": [dict({"t": t - self.start, "s": [self.to_path(at(t))]},
                                               **({"o": {"x": eases[n][0], "y": eases[n][1]},
                                                   "i": {"x": eases[n][2], "y": eases[n][3]}}
                                                  if n < len(eases) else {}))
                                          for n, t in enumerate(times)]}
        self.notes.append("a path sampled once per frame")
        return {"a": 1, "k": [{"t": f - self.start, "s": [self.to_path(at(f))], "o": {"x": 0, "y": 0},
                               "i": {"x": 1, "y": 1}} for f in range(self.start, self.end + 1)]}

    def follows(self, at, times, eases):
        """Whether blending each segment's end shapes by its easing reproduces the geometry at every frame."""
        for n in range(len(times) - 1):
            a, b = at(times[n]), at(times[n + 1])
            for f in range(int(times[n]) + 1, int(times[n + 1])):
                y = bezier_ease(*eases[n], (f - times[n]) / (times[n + 1] - times[n]))
                truth = at(f)
                for part in range(3):
                    for pa, pb, pt in zip(a[part], b[part], truth[part]):
                        if any(abs(pa[d] + (pb[d] - pa[d]) * y - pt[d]) > 1e-6 for d in (0, 1)):
                            return False
        return True

    def primitive(self, tool, kind):
        self.require(tool, "Translate.Z", 0, "Z translation")
        geometry, numbers, counts = PRIMITIVES[kind]
        channels = {arg: self.number(tool, name, default) for arg, (name, default) in numbers.items()}
        for arg, (name, default) in counts.items():
            channels[arg] = ("static", int(self.static(tool, name, default)))
        path = {"ty": "sh", "nm": f"{tool} path", "ks": self.path_prop(channels, geometry)}
        tr = self.transform(tool, pos=[self.number(tool, "Translate.X", 0.0), self.number(tool, "Translate.Y", 0.0)],
                            scale=[("static", 1.0)] * 2, rot=self.number(tool, "Angle", 0.0),
                            opacity=self.number(tool, "Opacity", 1.0))
        tr["a"] = {"a": 0, "k": [0, 0]}
        return {"ty": "gr", "nm": tool, "it": [path, *self.paint(tool), tr]}

    def polygon(self, tool):
        for name, default, what in (("XRotation", 0, "rotation about X"), ("YRotation", 0, "rotation about Y"),
                                    ("Translate.Z", 0, "Z translation")):
            self.require(tool, name, default, what)
        pl = self.static(tool, "Polyline", None)
        if pl is None:
            raise Unsupported(f"{tool}: has no polyline")
        v, i, o = [], [], []
        for p in pl["Points"].items_:
            v.append([p["X"] * self.w, -p["Y"] * self.w])
            if p.get("Linear"):
                i.append([0, 0])
                o.append([0, 0])
            else:
                i.append([p.get("LX", 0) * self.w, -p.get("LY", 0) * self.w])
                o.append([p.get("RX", 0) * self.w, -p.get("RY", 0) * self.w])
        path = {"ty": "sh", "nm": f"{tool} path",
                "ks": {"a": 0, "k": {"c": bool(pl.get("Closed")), "v": v, "i": i, "o": o}}}
        size = self.number(tool, "Size", 1.0)
        tr = self.transform(tool, pos=self.point(tool, "Center", [0, 0]), scale=[size, size],
                            rot=self.number(tool, "ZRotation", 0.0), opacity=self.number(tool, "Opacity", 1.0))
        tr["a"] = {"a": 0, "k": [0, 0]}  # the polyline is drawn around Center
        return {"ty": "gr", "nm": tool, "it": [path, *self.paint(tool), tr]}

    def smerge(self, tool):
        inputs = self.tools[tool].get("Inputs", {})
        names = sorted((k for k in inputs if re.fullmatch(r"Input\d+", k)), key=lambda k: int(k[5:]))
        children = [self.shape(src) for src in (self.source(tool, n) for n in names) if src]
        identity = self.transform(tool, pos=[("static", 0.0)] * 2, scale=[("static", 1.0)] * 2, rot=("static", 0.0))
        identity["a"] = identity["p"] = {"a": 0, "k": [0, 0]}
        # Lottie draws its first item on top; Fusion puts the highest input on top.
        return {"ty": "gr", "nm": tool, "it": [c for c in reversed(children) if c] + [identity]}

    def stransform(self, tool):
        pivot = (float(self.static(tool, "XPivot", 0)), float(self.static(tool, "YPivot", 0)))

        def offset(channel, by):
            kind, val = channel
            return (kind, [dict(k, v=k["v"] + by) for k in val] if kind == "keys" else val + by)

        pos = [offset(self.number(tool, "XOffset", 0.0), pivot[0]), offset(self.number(tool, "YOffset", 0.0), pivot[1])]
        tr = self.transform(tool, anchor=pivot, pos=pos,
                            scale=[self.number(tool, "XSize", 1.0), self.number(tool, "YSize", 1.0)],
                            rot=self.number(tool, "ZRotation", 0.0))
        child = self.shape(self.source(tool, "Input")) if self.source(tool, "Input") else None
        return {"ty": "gr", "nm": tool, "it": ([child] if child else []) + [tr]}

    # --- image tools: the comp ends in MediaOut <- Merge(Background, sRender) ----------------------------------

    def layers(self, tool):
        try:
            kind = self.tools[tool].kind
            if kind == "Merge":
                for name, default, what in (("Size", 1.0, "scaling a Merge"), ("Angle", 0.0, "rotating a Merge"),
                                            ("Blend", 1.0, "blending a Merge"),
                                            ("ApplyMode", "Normal", "an apply mode other than Normal")):
                    self.require(tool, name, default, what)
                center = self.static(tool, "Center", [0.5, 0.5])
                if [float(c) for c in center] != [0.5, 0.5]:
                    raise Unsupported(f"{tool}.Center: moving a Merge's foreground is not supported yet")
                fg, bg = self.source(tool, "Foreground"), self.source(tool, "Background")
                return (self.layers(fg) if fg else []) + (self.layers(bg) if bg else [])
            if kind == "sRender":
                root = self.shape(self.source(tool, "Input")) if self.source(tool, "Input") else None
                return [{"ty": 4, "nm": tool, "shapes": [root] if root else []}]
            if kind == "Background":
                self.require(tool, "Type", "Solid", "a gradient background")
                rgb = [float(self.static(tool, f"TopLeft{c}", 0)) for c in ("Red", "Green", "Blue")]
                return [{"ty": 1, "nm": tool, "sc": "#" + "".join(f"{round(c * 255):02x}" for c in rgb),
                         "sw": self.w, "sh": self.h}]
            raise Unsupported(f"{tool}: the {kind} tool is not supported (the image side takes Merge, sRender "
                              "and a solid Background)")
        except Unsupported as e:
            self.problems.append(str(e))
            return []

    def export(self) -> dict:
        outs = [k for k, t in self.tools.items() if t.kind in ("Saver", "MediaOut") and "Index" in t.get("Inputs", {})]
        if not outs:
            self.problems.append("no MediaOut: nothing to export")
            layers = []
        else:
            src = self.source(outs[0], "Input")
            layers = self.layers(src) if src else []
        n = self.end - self.start + 1
        for i, layer in enumerate(layers):
            layer.update({"ind": i + 1, "ip": 0, "op": n, "st": 0, "sr": 1, "ao": 0, "bm": 0,
                          "ks": {"o": {"a": 0, "k": 100}, "r": {"a": 0, "k": 0}, "p": {"a": 0, "k": [0, 0, 0]},
                                 "a": {"a": 0, "k": [0, 0, 0]}, "s": {"a": 0, "k": [100, 100, 100]}}})
        return {"v": LOTTIE_VERSION, "fr": self.fps, "ip": 0, "op": n, "w": self.w, "h": self.h,
                "nm": "fusion2lottie", "ddd": 0, "assets": [], "layers": layers}
