"""
scripts/lib/naming.py
Campaign In A Box v2.1

Provides strict deterministic naming and stable identifiers across counties, contests, and files.
Enforces normalization rules to prevent drift, duplication, and ambiguity.
"""
import re
from pathlib import Path

# CA County FIPS lookup table (3 digits)
CA_COUNTY_FIPS = {
    "Alameda": "001", "Alpine": "003", "Amador": "005", "Butte": "007", "Calaveras": "009", 
    "Colusa": "011", "Contra Costa": "013", "Del Norte": "015", "El Dorado": "017", "Fresno": "019", 
    "Glenn": "021", "Humboldt": "023", "Imperial": "025", "Inyo": "027", "Kern": "029", 
    "Kings": "031", "Lake": "033", "Lassen": "035", "Los Angeles": "037", "Madera": "039", 
    "Marin": "041", "Mariposa": "043", "Mendocino": "045", "Merced": "047", "Modoc": "049", 
    "Mono": "051", "Monterey": "053", "Napa": "055", "Nevada": "057", "Orange": "059", 
    "Placer": "061", "Plumas": "063", "Riverside": "065", "Sacramento": "067", "San Benito": "069", 
    "San Bernardino": "071", "San Diego": "073", "San Francisco": "075", "San Joaquin": "077", 
    "San Luis Obispo": "079", "San Mateo": "081", "Santa Barbara": "083", "Santa Clara": "085", 
    "Santa Cruz": "087", "Shasta": "089", "Sierra": "091", "Siskiyou": "093", "Solano": "095", 
    "Sonoma": "097", "Stanislaus": "099", "Sutter": "101", "Tehama": "103", "Trinity": "105", 
    "Tulare": "107", "Tuolumne": "109", "Ventura": "111", "Yolo": "113", "Yuba": "115"
}

def normalize_county(name: str) -> tuple[str, str, str]:
    """
    Given a county name string, returns Title Case name, slug, and FIPS.
    Raises ValueError if county is not recognized as a CA county.
    """
    norm = name.strip().title()
    
    # special cases
    if norm.lower() == "la" or norm.lower() == "l.a.":
        norm = "Los Angeles"
    if norm.lower() == "sf" or norm.lower() == "s.f.":
        norm = "San Francisco"
        
    for k in CA_COUNTY_FIPS.keys():
        if k.lower() == norm.lower():
            true_name = k
            slug = k.lower().replace(" ", "_")
            fips = CA_COUNTY_FIPS[k]
            return true_name, slug, fips
            
    raise ValueError(f"Unrecognized California county: '{name}'")


def normalize_contest_slug(slug: str) -> str:
    """
    Enforces rules: lowercase, letters/numbers/underscore only, no spaces.
    Collapses repeated underscores, strips leading/trailing.
    Max 64 chars.
    """
    s = slug.lower().strip()
    s = re.sub(r"[^\w]+", "_", s) # replace non-alphanumeric with underscore
    s = re.sub(r"_+", "_", s)     # collapse repeated underscores
    s = s.strip("_")
    return s[:64]


def generate_contest_id(year: str, state: str, county_slug: str, contest_slug: str) -> str:
    """
    Returns stable contest_id: <year>_<state>_<county_slug>_<contest_slug>
    Example: 2024_CA_sonoma_nov2024_general
    """
    return f"{year}_{state}_{county_slug}_{contest_slug}"


def normalize_precinct_id(val: any, pad_to: int = 0) -> str:
    """
    All precinct IDs must be treated as strings.
    - strip whitespace
    - remove .0 artifacts (Excel float import)
    - left-pad numeric strings if pad_to > 0 and the string is purely numeric
    - preserve leading zeros if present originally
    """
    if val is None or str(val).strip() == "" or str(val).lower() == "nan":
        return ""
        
    s = str(val).strip()
    
    # Handle float exports like '4001.0'
    if s.endswith(".0"):
        s = s[:-2]
        
    # If pad_to is set and the string is fully numeric, zero-pad it
    # We only pad if it's purely digits to avoid padding alphanumeric codes like 'PREC_A'
    if pad_to > 0 and s.isdigit():
        s = s.zfill(pad_to)
        
    return s


def normalize_jurisdiction_name(name: str) -> tuple[str, str]:
    """
    Returns Title Case name and lowercase slug.
    Example: "Santa Rosa" -> ("Santa Rosa", "santa_rosa")
    """
    norm_name = name.strip().title()
    slug = norm_name.lower().replace(" ", "_")
    slug = re.sub(r"[^\w]+", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return norm_name, slug


def deduplicate_slug(base_slug: str, existing_slugs: list[str]) -> str:
    """
    Finds the next available slug if base_slug collides.
    e.g. 'general' -> 'general_v2'
    """
    if base_slug not in existing_slugs:
        return base_slug
        
    i = 2
    while f"{base_slug}_v{i}" in existing_slugs:
        i += 1
        
    return f"{base_slug}_v{i}"
