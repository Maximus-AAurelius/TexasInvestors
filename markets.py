"""Configured assignment markets; support does not imply connected data feeds."""
COUNTIES = ("Harris", "Fort Bend", "Montgomery", "Brazoria", "Galveston",
            "Waller", "Liberty", "Chambers", "Nacogdoches")


def normalize_county(value):
    if not isinstance(value, str):
        raise ValueError("County must be text")
    name = " ".join(value.strip().casefold().split())
    if name.endswith(" county"):
        name = name[:-7].strip()
    if name == "nacogadoches":
        name = "nacogdoches"
    for county in COUNTIES:
        if name == county.casefold():
            return county
    raise ValueError(f"Unsupported county: {value!r}")


def market_catalog():
    return [{"county": county, "priority": "Primary" if county == "Harris" else "Additional" if county == "Nacogdoches" else "Surrounding",
             "coverage": "Local HCAD data and existing county tools; coverage is partial" if county == "Harris" else "Manual CSV / saved HTML import; no connected county feed"}
            for county in COUNTIES]
