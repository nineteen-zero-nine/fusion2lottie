"""Converted animations against Resolve's own renders, frame by frame.

Each fixture is a comp as Resolve saved it (tests/fixtures/<name>.comp) and frames Resolve rendered from it
(tests/fixtures/<name>/f_####.png; see fidelity/render_in_resolve.py). The conversion is played by lottie-web in
headless Chrome, so this needs Node, `npm install` in fidelity/, and Chrome; it is skipped without them.
Side-by-sides of every compared frame (Resolve | Lottie | difference) land in .fidelity/<name>/.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from fusion2lottie import convert, parse

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
RENDERER = ROOT / "fidelity" / "render-lottie.mjs"
OUT = ROOT / ".fidelity"
NAMES = sorted(p.name for p in FIXTURES.iterdir() if p.is_dir())

# Measured against the shapes' own area (pixels that are not background in either render), one-pixel
# anti-aliasing along the edges stays under this even for thin outlines; a misplaced or missized shape does not.
MAX_OFF_PERCENT = 3.0

needs_renderer = pytest.mark.skipif(
    not shutil.which("node") or not (ROOT / "fidelity" / "node_modules" / "lottie-web").exists(),
    reason="needs Node and `npm install` in fidelity/")


def off_percent(a: Image.Image, b: Image.Image) -> float:
    """The share of the drawn area (not background in either image) where the two differ by more than 32/255."""
    def mask(im):
        return im.convert("L").point(lambda v: 255 if v > 32 else 0)

    background = Image.new("RGB", a.size, a.getpixel((0, 0)))
    drawn = ImageChops.lighter(mask(ImageChops.difference(a, background)), mask(ImageChops.difference(b, background)))
    area = drawn.histogram()[255]
    off = mask(ImageChops.difference(a, b)).histogram()[255]
    return off / area * 100 if area else 0.0


@needs_renderer
@pytest.mark.parametrize("name", NAMES)
def test_matches_resolve(name):
    resolve_frames = sorted((FIXTURES / name).glob("f_*.png"))
    samples_file = FIXTURES / f"{name}.samples.json"
    samples = json.loads(samples_file.read_text()) if samples_file.exists() else None
    lottie, _ = convert(parse((FIXTURES / f"{name}.comp").read_text()), fps=30, samples=samples)
    out = OUT / name
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    (out / "animation.json").write_text(json.dumps(lottie))
    frames = [str(int(p.stem[2:])) for p in resolve_frames]
    subprocess.run(["node", str(RENDERER), str(out / "animation.json"), str(out / "lottie"), *frames], check=True)

    results = {}
    for rf in resolve_frames:
        a = Image.open(rf).convert("RGB")
        b = Image.open(out / "lottie" / rf.name).convert("RGB")
        results[int(rf.stem[2:])] = round(off_percent(a, b), 3)
        side = Image.new("RGB", (a.width * 3, a.height))
        for i, im in enumerate((a, b, ImageChops.difference(a, b).point(lambda v: min(255, v * 4)))):
            side.paste(im, (i * a.width, 0))
        side.save(out / f"compare_{rf.name}")
    assert max(results.values()) < MAX_OFF_PERCENT, f"{name}: % of pixels off per frame {results}"
