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
| `sPolygon`: polyline (straight or curved), colour, `Center`, `Size`, `ZRotation`, `Opacity`, `Alpha` | shape group: path, fill, transform |
| `sMerge` | group (Fusion's highest input drawn on top) |
| `sTransform`: offset, size (including mirroring with a negative size), rotation, pivot | group transform |
| `sRender` | shape layer |
| `Background` (solid) | solid layer |
| `Merge` (untransformed, Normal) | layer order |
| `BezierSpline` keyframes | keyframes with the same easing, converted exactly |

One tool's output feeding several tools is fine: Lottie has no instancing, so the shared part is written once per use.

**Not yet:** `sRectangle`, `sEllipse`, `sNGon`, `sStar`, outlines (`Solid` off), write-on (`WritePosition`/`WriteLength`), animated polylines and points, `Text+`, transformed or blended `Merge`s, expressions and modifiers other than keyframes.

**Never:** blur, glow, particles, 3D and other pixel effects. Lottie is vector, so render those as video with alpha instead.

## How it is checked

Every converted animation is compared with Resolve's own render, frame by frame. The first one, the Valhalla logo intro (90 frames, 1024×1024), differs from Resolve's render in 0.05% of pixels on average and 0.09% on the worst frame, all of it one-pixel anti-aliasing. The tests also check keyframes against the values Fusion itself reports.

## Develop

```sh
uv run pytest
```

## License

MIT
