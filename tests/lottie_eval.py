"""Evaluate Lottie properties the way players do, so tests can compare an export with Fusion's own values."""


def bezier_ease(x1, y1, x2, y2, x):
    """CSS/Lottie cubic-bezier easing: solve the curve's x for `x`, return its y."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        s = (lo + hi) / 2
        bx = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s ** 3
        lo, hi = (s, hi) if bx < x else (lo, s)
    s = (lo + hi) / 2
    return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s * s * y2 + s ** 3


def value_at(prop, frame, dim=0):
    """The value of a Lottie property at a frame (one dimension of it)."""
    if not prop["a"]:
        k = prop["k"]
        return k[dim] if isinstance(k, list) else k
    keys = prop["k"]
    if frame <= keys[0]["t"]:
        return keys[0]["s"][dim]
    for a, b in zip(keys, keys[1:]):
        if a["t"] <= frame < b["t"]:
            x = (frame - a["t"]) / (b["t"] - a["t"])
            y = bezier_ease(a["o"]["x"][dim], a["o"]["y"][dim], a["i"]["x"][dim], a["i"]["y"][dim], x)
            return a["s"][dim] + (b["s"][dim] - a["s"][dim]) * y
    return keys[-1]["s"][dim]


def find(node, name):
    """The first group or item called `name` anywhere under a Lottie node."""
    if isinstance(node, dict):
        if node.get("nm") == name:
            return node
        children = node.get("layers") or node.get("shapes") or node.get("it") or []
        for child in children:
            hit = find(child, name)
            if hit is not None:
                return hit
    return None


def transform_of(group):
    return next(item for item in group["it"] if item["ty"] == "tr")


def vertex_at(path_prop, frame, index=0):
    """One vertex of a Lottie path at a frame, blending keyframed paths by their easing the way players do."""
    if not path_prop["a"]:
        return path_prop["k"]["v"][index]
    keys = path_prop["k"]
    if frame <= keys[0]["t"]:
        return keys[0]["s"][0]["v"][index]
    for a, b in zip(keys, keys[1:]):
        if a["t"] <= frame < b["t"]:
            x = (frame - a["t"]) / (b["t"] - a["t"])
            o, i = a["o"], a["i"]
            y = bezier_ease(o["x"], o["y"], i["x"], i["y"], x)
            va, vb = a["s"][0]["v"][index], b["s"][0]["v"][index]
            return [va[d] + (vb[d] - va[d]) * y for d in (0, 1)]
    return keys[-1]["s"][0]["v"][index]
