"""Core CRS guessing logic (no dependencies)."""

from __future__ import annotations

import math
from dataclasses import dataclass

# (epsg, name, min_x, min_y, max_x, max_y) in the CRS's own units.
# Extents are approximate areas of use.
KNOWN_CRS = (
    (4326, "WGS 84 (lon/lat)", -180.0, -90.0, 180.0, 90.0),
    (3857, "WGS 84 / Pseudo-Mercator", -20037508.35, -20048966.11, 20037508.35, 20048966.11),
    (3035, "ETRS89 / LAEA Europe", 1896628.0, 1507846.0, 7104243.0, 6827128.0),
    (2154, "RGF93 v1 / Lambert-93", 100000.0, 6000000.0, 1300000.0, 7200000.0),
    (27700, "OSGB36 / British National Grid", 0.0, 0.0, 700000.0, 1300000.0),
)


@dataclass(frozen=True)
class Match:
    epsg: int
    name: str

    @property
    def code(self) -> str:
        return f"EPSG:{self.epsg}"


def to_number(value, what: str = "coordinate value") -> float:
    """Return value as a finite float; int/float only (bool rejected)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{what} must be a number, got {type(value).__name__}")
    try:
        number = float(value)
    except OverflowError:
        raise ValueError(f"{what} is too large to represent") from None
    if not math.isfinite(number):
        raise ValueError(f"{what} must be finite")
    return number


def validate_position(position, allow_z: bool = False) -> tuple[float, float]:
    """Validate one coordinate (list/tuple of 2, or 3 with allow_z); return (x, y)."""
    if not isinstance(position, (list, tuple)):
        raise ValueError(f"coordinate must be a list of numbers, got {type(position).__name__}")
    allowed = (2, 3) if allow_z else (2,)
    if len(position) not in allowed:
        raise ValueError(
            f"coordinate must have {' or '.join(map(str, allowed))} values, got {len(position)}"
        )
    values = [to_number(v) for v in position]
    return values[0], values[1]


def sniff(coords, allow_z: bool = False) -> list[Match]:
    """Return candidate CRSs for a non-empty list of (x, y) pairs, best first.

    Only CRSs whose extent contains every point are returned. Raises
    ValueError for any malformed input.
    """
    try:
        if not isinstance(coords, (list, tuple)):
            raise ValueError(f"coords must be a list of coordinates, got {type(coords).__name__}")
        if not coords:
            raise ValueError("coords must not be empty")
        points = [validate_position(c, bool(allow_z)) for c in coords]
        return _rank(points)
    except ValueError:
        raise
    except Exception as exc:  # defensive: contract is ValueError only
        raise ValueError(f"invalid coordinates: {exc}") from exc


def _rank(points: list[tuple[float, float]]) -> list[Match]:
    fits = [
        crs
        for crs in KNOWN_CRS
        if all(crs[2] <= x <= crs[4] and crs[3] <= y <= crs[5] for x, y in points)
    ]
    # Smaller extent = more specific = more likely, except that values that
    # all fit in degrees are far more plausibly lon/lat than metres near 0.
    fits.sort(key=lambda c: (c[0] != 4326, (c[4] - c[2]) * (c[5] - c[3])))
    return [Match(c[0], c[1]) for c in fits]
