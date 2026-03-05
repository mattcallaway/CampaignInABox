"""
scripts/lib/ca_fips.py

California county FIPS code → county name mapping.
Used by the ingestion pipeline to identify counties from filenames
like c097_mprec.geojson → Sonoma County.

FIPS codes are zero-padded 3-digit strings (state prefix dropped).
Full state FIPS for CA is 06; county FIPS are 001-115 (odd only).

Reference: US Census Bureau CA county FIPS codes.
"""

# Maps 3-digit county FIPS (string, zero-padded) → canonical county name
CA_FIPS_TO_COUNTY: dict[str, str] = {
    "001": "Alameda",
    "003": "Alpine",
    "005": "Amador",
    "007": "Butte",
    "009": "Calaveras",
    "011": "Colusa",
    "013": "Contra Costa",
    "015": "Del Norte",
    "017": "El Dorado",
    "019": "Fresno",
    "021": "Glenn",
    "023": "Humboldt",
    "025": "Imperial",
    "027": "Inyo",
    "029": "Kern",
    "031": "Kings",
    "033": "Lake",
    "035": "Lassen",
    "037": "Los Angeles",
    "039": "Madera",
    "041": "Marin",
    "043": "Mariposa",
    "045": "Mendocino",
    "047": "Merced",
    "049": "Modoc",
    "051": "Mono",
    "053": "Monterey",
    "055": "Napa",
    "057": "Nevada",
    "059": "Orange",
    "061": "Placer",
    "063": "Plumas",
    "065": "Riverside",
    "067": "Sacramento",
    "069": "San Benito",
    "071": "San Bernardino",
    "073": "San Diego",
    "075": "San Francisco",
    "077": "San Joaquin",
    "079": "San Luis Obispo",
    "081": "San Mateo",
    "083": "Santa Barbara",
    "085": "Santa Clara",
    "087": "Santa Cruz",
    "089": "Shasta",
    "091": "Sierra",
    "093": "Siskiyou",
    "095": "Solano",
    "097": "Sonoma",
    "099": "Stanislaus",
    "101": "Sutter",
    "103": "Tehama",
    "105": "Trinity",
    "107": "Tulare",
    "109": "Tuolumne",
    "111": "Ventura",
    "113": "Yolo",
    "115": "Yuba",
}

# Reverse mapping: lower-case county name → FIPS
COUNTY_TO_FIPS: dict[str, str] = {v.lower(): k for k, v in CA_FIPS_TO_COUNTY.items()}


def fips_to_county(fips_code: str) -> str | None:
    """
    Look up county name for a FIPS code.
    Accepts 3-digit paddded ('097'), 5-digit ('06097'), or bare int-like ('97').
    Returns None if not found.
    """
    code = str(fips_code).strip()
    # Strip state prefix if 5 digits
    if len(code) == 5 and code.startswith("06"):
        code = code[2:]
    code = code.zfill(3)
    return CA_FIPS_TO_COUNTY.get(code)


def county_to_fips(county_name: str) -> str | None:
    """Return FIPS for a county name (case-insensitive). None if not found."""
    return COUNTY_TO_FIPS.get(county_name.lower().strip())


def extract_fips_from_filename(filename: str) -> str | None:
    """
    Attempt to extract a CA county FIPS code from a filename.
    Patterns tried:
      - c097_*   → '097'
      - c06097_* → '097'
      - _097_    → '097'
      - 06097    → '097'
    Returns FIPS 3-digit string or None.
    """
    import re
    name = filename.lower()

    # Pattern: c<3digit>_ or c<5digit>_
    m = re.search(r'\bc0?6?(\d{3})[_\-\.]', name)
    if m:
        candidate = m.group(1).zfill(3)
        if candidate in CA_FIPS_TO_COUNTY:
            return candidate

    # Pattern: _<3digit>_ standalone
    m = re.search(r'(?<![0-9])(\d{3})(?![0-9])', name)
    if m:
        candidate = m.group(1).zfill(3)
        if candidate in CA_FIPS_TO_COUNTY:
            return candidate

    return None
