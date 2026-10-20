"""fusion2lottie COMP [-o OUT] [--fps N] [--check]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .comp import CompSyntaxError, parse
from .convert import ConversionError, check, convert


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fusion2lottie",
                                 description="Convert a Fusion composition, as DaVinci Resolve or Fusion saves it, "
                                             "to a Lottie animation.")
    ap.add_argument("comp", type=Path, help="the .comp or .setting file")
    ap.add_argument("-o", "--output", type=Path, help="where to write the Lottie (default: the comp's name, .json)")
    ap.add_argument("--fps", type=float,
                    help="frame rate; Resolve does not save it in the comp, so pass your timeline's (default 30)")
    ap.add_argument("--check", action="store_true", help="list what would stop the conversion, write nothing")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args(argv)

    try:
        comp = parse(args.comp.read_text())
    except (OSError, CompSyntaxError) as e:
        print(f"fusion2lottie: cannot read {args.comp}: {e}", file=sys.stderr)
        return 2
    fps = args.fps or 30.0

    try:
        if args.check:
            problems = check(comp, fps)
            for p in problems:
                print(p)
            print(f"{len(problems)} problem{'s' * (len(problems) != 1)}" if problems else "converts cleanly")
            return 1 if problems else 0
        lottie, notes = convert(comp, fps)
    except ConversionError as e:
        print(f"fusion2lottie: {args.comp} uses what Lottie cannot show exactly:", file=sys.stderr)
        for p in e.problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    out = args.output or args.comp.with_suffix(".json")
    out.write_text(json.dumps(lottie, separators=(",", ":")))
    if args.fps is None:
        notes.insert(0, "no --fps given: assumed 30")
    for n in notes:
        print(f"note: {n}", file=sys.stderr)
    print(f"wrote {out}: {lottie['w']}x{lottie['h']}, {lottie['op']} frames at {lottie['fr']:g} fps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
