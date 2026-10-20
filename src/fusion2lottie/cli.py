"""fusion2lottie COMP [-o OUT] [--fps N] [--samples JSON] [--check]
fusion2lottie install-resolve | uninstall-resolve"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .comp import CompSyntaxError, parse
from .convert import ConversionError, check, convert


def resolve_menu(command: str) -> int:
    from . import resolve

    if command == "install-resolve":
        launcher = resolve.install()
        print(f"installed {launcher}\nRestart DaVinci Resolve, then use Workspace → Scripts → Export to Lottie.")
    else:
        removed = resolve.uninstall()
        print("\n".join(f"removed {p}" for p in removed) if removed else "nothing to remove")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("install-resolve", "uninstall-resolve"):
        return resolve_menu(argv[0])
    ap = argparse.ArgumentParser(prog="fusion2lottie",
                                 description="Convert a Fusion composition, as DaVinci Resolve or Fusion saves it, "
                                             "to a Lottie animation.",
                                 epilog="`fusion2lottie install-resolve` adds Export to Lottie to Resolve's "
                                        "Workspace → Scripts menu.")
    ap.add_argument("comp", type=Path, help="the .comp or .setting file")
    ap.add_argument("-o", "--output", type=Path, help="where to write the Lottie (default: the comp's name, .json)")
    ap.add_argument("--fps", type=float,
                    help="frame rate; Resolve does not save it in the comp, so pass your timeline's (default 30)")
    ap.add_argument("--samples", type=Path,
                    help='values per frame for inputs only Fusion can evaluate: {"Tool.Input": [...], ...}')
    ap.add_argument("--check", action="store_true", help="list what would stop the conversion, write nothing")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args(argv)

    try:
        comp = parse(args.comp.read_text())
        samples = json.loads(args.samples.read_text()) if args.samples else None
    except (OSError, CompSyntaxError, ValueError) as e:
        print(f"fusion2lottie: cannot read {e.filename if isinstance(e, OSError) else args.comp}: {e}", file=sys.stderr)
        return 2
    fps = args.fps or 30.0

    try:
        if args.check:
            problems = check(comp, fps, samples)
            for p in problems:
                print(p)
            print(f"{len(problems)} problem{'s' * (len(problems) != 1)}" if problems else "converts cleanly")
            return 1 if problems else 0
        lottie, notes = convert(comp, fps, samples)
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
