"""Command-line interface.

Exit status: 0 = at least one candidate CRS, 1 = no known CRS fits, 2 = invalid input.
"""

from __future__ import annotations

import argparse
import json
import sys

from .core import sniff
from .io import read_file


def parse_coords(text: str, allow_z: bool = False) -> list[list[float]]:
    """Parse 'x,y;x,y' (or 'x,y,z;...' with allow_z) into coordinate lists."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("--coords must not be empty")
    allowed = (2, 3) if allow_z else (2,)
    out = []
    for item in text.split(";"):
        parts = item.split(",")
        if len(parts) not in allowed:
            raise ValueError(f"coordinate {item!r} must have {' or '.join(map(str, allowed))} values")
        try:
            out.append([float(p.strip()) for p in parts])
        except ValueError:
            raise ValueError(f"coordinate {item!r} is not numeric") from None
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="crs-sniffer",
        description="Guess the EPSG code of coordinates from value ranges and known extents.",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("path", nargs="?", help="GeoJSON (.geojson/.json) or CSV (.csv/.txt) file")
    src.add_argument("--coords", metavar="X,Y;X,Y", help="inline coordinates; use --coords=-1,2 for negatives")
    p.add_argument("--allow-z", action="store_true", help="accept a third (Z) value per coordinate")
    p.add_argument("--json", action="store_true", help="print matches as JSON")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)  # argparse errors exit with status 2
    try:
        if args.coords is not None:
            coords = parse_coords(args.coords, args.allow_z)
        else:
            coords = read_file(args.path, args.allow_z)
        matches = sniff(coords, allow_z=args.allow_z)
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        print(f"invalid input: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([{"epsg": m.epsg, "name": m.name} for m in matches]))
    elif matches:
        for i, m in enumerate(matches):
            print(f"{'best' if i == 0 else 'also'}: {m.code}  {m.name}")
    else:
        print("no known CRS fits these coordinates")
    return 0 if matches else 1


if __name__ == "__main__":
    sys.exit(main())
