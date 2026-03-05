"""
scripts/lib/naming.py
Campaign In A Box v2.1

Provides strict deterministic naming and stable identifiers across counties, contests, and files.
Enforces normalization rules to prevent drift, duplication, and ambiguity.
"""
import re
from pathlib import Path

from .county_registry import normalize_county_input

def normalize_county(name: str) -> tuple[str, str, str]:
    """
    Given a county name string, returns Title Case name, slug, and FIPS.
    Raises ValueError if county is not recognized as a CA county.
    """
    record = normalize_county_input(name)
    return record["county_name"], record["county_slug"], record["county_fips"]


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
