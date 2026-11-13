"""Guess the EPSG code of coordinates from value ranges and known extents."""

from .core import KNOWN_CRS, Match, sniff
from .io import read_csv, read_file, read_geojson

__version__ = "0.1.0"
__all__ = ["KNOWN_CRS", "Match", "sniff", "read_csv", "read_file", "read_geojson", "__version__"]
