import json
import re
from pathlib import Path

CITY_REGISTRY_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "cities_by_county_ca.json"

class CityRegistry:
    _instance = None
    
    def __init__(self):
        self.version = "unknown"
        self.counties = {}
        self.load()
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
        
    def load(self):
        if not CITY_REGISTRY_PATH.exists():
            raise FileNotFoundError(f"Missing city registry database: {CITY_REGISTRY_PATH}")
            
        with open(CITY_REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self.version = data.get("version", "unknown")
        
        for county in data.get("counties", []):
            fips = county.get("county_fips")
            cities_data = county.get("cities", [])
            
            # Index by primary name, slug, and aliases
            self.counties[fips] = {
                "records": cities_data,
                "name_map": {c["city_name"].lower(): c for c in cities_data},
                "slug_map": {c["city_slug"]: c for c in cities_data},
                "alias_map": {}
            }
            
            for c in cities_data:
                for alias in c.get("aliases", []):
                    self.counties[fips]["alias_map"][alias.lower()] = c
                    
    def get_all_for_county(self, fips_str: str) -> list[dict]:
        if fips_str not in self.counties:
            return []
        return self.counties[fips_str]["records"]


def load_city_registry() -> CityRegistry:
    return CityRegistry.get_instance()


def _clean_city_string(s: str) -> str:
    """Aggressively strip fluff and normalize a string."""
    s = s.lower().strip()
    s = re.sub(r'[^\w\s]', '', s) # removes trailing punctuation
    # Remove 'city of' or 'town of' prefix/suffix
    s = re.sub(r'^city of\s+', '', s)
    s = re.sub(r'^town of\s+', '', s)
    s = re.sub(r'\s+city$', '', s)
    s = re.sub(r'\s+town$', '', s)
    return s.strip()


def get_city_by_name_or_alias(county_fips: str, input_str: str) -> dict | None:
    """Exact or alias match within a county."""
    reg = load_city_registry()
    if county_fips not in reg.counties:
        return None
        
    county_index = reg.counties[county_fips]
    
    cleaned = _clean_city_string(input_str)
    
    # Check canonical name
    if cleaned in county_index["name_map"]:
        return county_index["name_map"][cleaned]
        
    # Check slug match
    if cleaned in county_index["slug_map"]:
        return county_index["slug_map"][cleaned]
        
    # Check aliases
    if cleaned in county_index["alias_map"]:
        return county_index["alias_map"][cleaned]
        
    # Try squished (no spaces) just in case
    squished = cleaned.replace(" ", "")
    for alias, record in county_index["alias_map"].items():
        if alias.replace(" ", "") == squished:
            return record
    for name, record in county_index["name_map"].items():
        if name.replace(" ", "") == squished:
            return record
            
    return None


def normalize_city_input(county_fips: str, input_str: str) -> dict:
    """
    Returns the canonical city record. 
    Raises ValueError if unmatched, providing closest options for the county.
    """
    if not input_str:
        raise ValueError("Empty city input provided.")
        
    res = get_city_by_name_or_alias(county_fips, input_str)
    if res:
        return res
        
    reg = load_city_registry()
    if county_fips not in reg.counties:
        raise ValueError(f"No cities registered for county FIPS '{county_fips}'.")
        
    available = [c["city_name"] for c in reg.counties[county_fips]["records"]]
    raise ValueError(f"Unrecognized city '{input_str}' for county {county_fips}. Available: {', '.join(available)}")
