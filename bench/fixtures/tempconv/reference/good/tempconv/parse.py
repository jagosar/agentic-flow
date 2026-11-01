"""Parsing of a temperature written as a number and a unit."""
import re

UNITS = ("C", "F", "K")
TEMPERATURE = re.compile(r"\s*([-+]?\d+(?:\.\d+)?)\s*([A-Za-z])\s*")


def parse(text):
    """("12.5C", "-40 F", "300k") -> (12.5, "C"), (-40.0, "F"), (300.0, "K"). ValueError for anything else."""
    match = TEMPERATURE.fullmatch(text or "")
    if not match:
        raise ValueError(f"not a temperature: {text!r}")
    unit = match.group(2).upper()
    if unit not in UNITS:
        raise ValueError(f"unknown unit: {unit}")
    return float(match.group(1)), unit
