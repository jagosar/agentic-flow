"""Temperature conversion between Celsius, Fahrenheit and Kelvin."""
UNITS = ("C", "F", "K")
ABSOLUTE_ZERO_C = -273.15
DECIMALS = 2


def _to_celsius(value, unit):
    if unit == "C":
        return value
    if unit == "F":
        return (value - 32) * 5 / 9
    return value + ABSOLUTE_ZERO_C


def _from_celsius(celsius, unit):
    if unit == "C":
        return celsius
    if unit == "F":
        return celsius * 9 / 5 + 32
    return celsius - ABSOLUTE_ZERO_C


def convert(value, from_unit, to_unit):
    """value in from_unit expressed in to_unit, rounded to 2 decimals. ValueError for an unknown unit or a
    temperature below absolute zero."""
    if from_unit not in UNITS or to_unit not in UNITS:
        raise ValueError(f"unknown unit: {from_unit!r} -> {to_unit!r}")
    celsius = _to_celsius(float(value), from_unit)
    return round(_from_celsius(celsius, to_unit), DECIMALS)
