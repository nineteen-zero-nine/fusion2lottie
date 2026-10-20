# fusion2lottie

Convert motion design made in **DaVinci Resolve's Fusion page** to **Lottie**, so it plays on the web and in apps (`lottie-web`, `lottie-react`, iOS, Android) the way After Effects animations do through Bodymovin.

```sh
uvx fusion2lottie intro.comp --fps 30      # writes intro.json
```

The conversion is exact, not approximate. Fusion's shape tools and Lottie's shape layers share the same model: shapes, groups and transforms, animated by cubic-bezier keyframes. A composition outside the supported subset is refused with a list of what to change, never silently approximated.

> **Alpha.** The core shape tools convert; more are on the way. See [What converts](#what-converts).

## Use it

1. In Resolve's Fusion page, build the animation with the shape tools (`sPolygon`, `sMerge`, `sTransform`, `sRender`) and keyframes.
2. Export the composition: right-click the clip in the Edit page, then **Fusion → Export Composition…**. From a script, use `TimelineItem.ExportFusionComp(path, 1)`.
3. Convert it:

   ```sh
   uvx fusion2lottie intro.comp --fps 30 -o intro.json
   uvx fusion2lottie intro.comp --check          # list what would stop the conversion
   ```

   Resolve does not save the frame rate in the comp, so pass your timeline's with `--fps`.
4. Play it, for example with `lottie-react`:

   ```jsx
   import { Lottie } from 'lottie-react';
   import intro from './intro.json';

   <Lottie src={intro} autoplay loop={false} style={{ width: 512, height: 512 }} />
   ```

From Python:

```python
from fusion2lottie import parse, convert

lottie, notes = convert(parse(open("intro.comp").read()), fps=30)
```

## What converts

| Fusion | Lottie |
|---|---|
| `sPolygon`: polyline (straight or curved, open or closed), `Center`, `Size`, `ZRotation` | shape group: path and transform |
| `sRectangle` (with `CornerRadius`), `sEllipse`, `sNGon`, `sStar`: `Width`, `Height`, `Depth`, `Translate`, `Angle` | path drawn where Fusion draws it, keyframed as it resizes |
| colour, `Alpha`, `Opacity` | fill or stroke colour and opacity, group opacity |
| outlines (`Solid` off): `BorderWidth`, `JoinStyle`, `CapStyle`, `MiterLimit` | stroke with the same width, joins and caps |
| write-on: `WritePosition`, `WriteLength` | trim path, starting and running where Fusion's does |
| `sMerge` | group (Fusion's highest input drawn on top) |
| `sTransform`: offset, size (including mirroring with a negative size), rotation, pivot | group transform |
| `sRender` | shape layer |
| `Background` (solid) | solid layer |
| `Merge` (untransformed, Normal) | layer order |
| `BezierSpline` keyframes | keyframes with the same easing, converted exactly |

One tool's output feeding several tools is fine: Lottie has no instancing, so the shared part is written once per use. A shape animated in a way one easing curve cannot reproduce exactly, such as width and height on different keyframes, is sampled once per frame instead, and the conversion says so.

**Not yet:** animated polylines and points, `Sides` and `Points` changing over time, `Text+`, transformed or blended `Merge`s, the other shape tools (`sBoolean`, `sDuplicate`, `sGrid`, `sOutline`, `sExpand`, `sJitter`), expressions and modifiers other than keyframes.

**Never:** blur, glow, particles, 3D and other pixel effects. Lottie is vector, so render those as video with alpha instead.

## How it is checked

Conversions are compared with Resolve's own render, frame by frame. `fidelity/` holds small compositions that each exercise one family of tools, and a script that renders them in Resolve and keeps the comp and frames Resolve produces as test fixtures. The test suite converts each fixture, plays it with `lottie-web` in headless Chrome, and requires every frame to match Resolve's within one-pixel anti-aliasing: under 3% of the drawn area, and in practice 0.3–1.4%. The tests also check keyframes against the values Fusion itself reports.

## Develop

```sh
(cd fidelity && npm install)   # lottie-web for the fidelity tests; also needs Google Chrome (or set CHROME)
uv run pytest
```

To add a fidelity case: describe it in `fidelity/make_comps.py`, run `uv run fidelity/make_comps.py`, then render it with Resolve Studio open (`python3 fidelity/render_in_resolve.py <name>`).

## License

MIT
