"""The outlines Fusion's shape primitives draw, as Bezier paths in shape units (y up, centred on the shape).

Each returns (vertices, in-tangents, out-tangents), tangents relative to their vertex, running counter-clockwise
from where Fusion starts drawing them: what `WritePosition` and `WriteLength` measure along.
"""
from __future__ import annotations

import math

KAPPA = 0.5522847498  # a quarter circle as one cubic Bezier


def ellipse(width: float, height: float):
    rx, ry = width / 2, height / 2
    v = [(rx, 0), (0, ry), (-rx, 0), (0, -ry)]
    i = [(0, -KAPPA * ry), (KAPPA * rx, 0), (0, KAPPA * ry), (-KAPPA * rx, 0)]
    o = [(-x, -y) for x, y in i]
    return v, i, o


def rectangle(width: float, height: float, corner_radius: float = 0.0):
    hw, hh = width / 2, height / 2
    r = max(0.0, min(corner_radius, 1.0)) * min(hw, hh)
    if r <= 0:
        v = [(hw, hh), (-hw, hh), (-hw, -hh), (hw, -hh)]
        return v, [(0, 0)] * 4, [(0, 0)] * 4
    k = KAPPA * r
    # From the top side's right end, counter-clockwise: each side, then the corner arc to the next side.
    v = [(hw - r, hh), (-hw + r, hh), (-hw, hh - r), (-hw, -hh + r),
         (-hw + r, -hh), (hw - r, -hh), (hw, -hh + r), (hw, hh - r)]
    o = [(0, 0), (-k, 0), (0, 0), (0, -k), (0, 0), (k, 0), (0, 0), (0, k)]
    i = [(k, 0), (0, 0), (0, k), (0, 0), (-k, 0), (0, 0), (0, -k), (0, 0)]
    return v, i, o


def polygon(sides: int, width: float, height: float):
    rx, ry = width / 2, height / 2
    v = [(rx * math.cos(2 * math.pi * k / sides), ry * math.sin(2 * math.pi * k / sides)) for k in range(sides)]
    return v, [(0, 0)] * sides, [(0, 0)] * sides


def star(points: int, depth: float, width: float, height: float):
    rx, ry = width / 2, height / 2
    v = []
    for k in range(points * 2):
        r = 1 if k % 2 == 0 else depth
        a = math.pi * k / points
        v.append((rx * r * math.cos(a), ry * r * math.sin(a)))
    return v, [(0, 0)] * len(v), [(0, 0)] * len(v)
