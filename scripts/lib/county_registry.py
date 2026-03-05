"""
scripts/lib/county_registry.py

Loads and interfaces with the CA county JSON database (`config/counties_ca.json`).
Acts as the single source of truth for all county naming, slugs, FIPS codes, and aliases.
"""

import json
from pathlib import Path
from typing import TypedDict, Optional

class CountyRecord(TypedDict):
    county_name: str
    county_slug: str
    county_fips: str
    aliases: list[str]

class CountyRegistry:
    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        self._data: dict | None = None
        self._counties: list[CountyRecord] = []
        self._alias_map: dict[str, CountyRecord] = {}
        self._fips_map: dict[str, CountyRecord] = {}

    def load(self):
        """Load the JSON database into memory."""
        if self._data is not None:
            return  # already loaded

        if not self.registry_path.exists():
            raise FileNotFoundError(f"County registry not found at {self.registry_path}")

        with open(self.registry_path, "r", encoding="utf-8") as f:
            self._data = json.load(f)

        for c in self._data.get("counties", []):
            record: CountyRecord = {
                "county_name": c["county_name"],
                "county_slug": c["county_slug"],
                "county_fips": c["county_fips"],
                "aliases": c.get("aliases", []),
            }
            self._counties.append(record)
            
            # Map canonical name and slug just in case they aren't in aliases
            self._alias_map[record["county_name"].lower()] = record
            self._alias_map[record["county_slug"]] = record

            for alias in record["aliases"]:
                self._alias_map[alias.lower()] = record
                
            self._fips_map[record["county_fips"]] = record

    @property
    def version(self) -> str:
        """Return the registry schema version."""
        self.load()
        return self._data.get("version", "unknown") if self._data else "unknown"

    def get_all(self) -> list[CountyRecord]:
        self.load()
        return self._counties

    def get_by_name_or_alias(self, input_str: str) -> Optional[CountyRecord]:
        """Look up a county by name, slug, or alias."""
        if not input_str:
            return None
        self.load()
        
        # Clean input: lowercase, strip, remove extra spaces
        clean_in = " ".join(input_str.strip().lower().split())
        if clean_in in self._alias_map:
            return self._alias_map[clean_in]
            
        # Try stripping punctuation if strict match fails (e.g. "l.a.")
        stripped = "".join(c for c in clean_in if c.isalnum() or c.isspace())
        stripped =" ".join(stripped.split())
        return self._alias_map.get(stripped)

    def get_by_fips(self, fips_str: str) -> Optional[CountyRecord]:
        """Look up by precise 3-digit FIPS code (e.g., '097')."""
        if not fips_str:
            return None
        self.load()
        return self._fips_map.get(str(fips_str).zfill(3))


# --- Singleton Pattern for Global Access ---

_REGISTRY_INSTANCE: Optional[CountyRegistry] = None

def _get_instance() -> CountyRegistry:
    global _REGISTRY_INSTANCE
    if _REGISTRY_INSTANCE is None:
        # Resolve config/counties_ca.json relative to project root
        project_root = Path(__file__).resolve().parent.parent.parent
        reg_path = project_root / "config" / "counties_ca.json"
        _REGISTRY_INSTANCE = CountyRegistry(reg_path)
    return _REGISTRY_INSTANCE


def load_county_registry() -> CountyRegistry:
    """Get the active registry instance, ensuring it is loaded."""
    reg = _get_instance()
    reg.load()
    return reg


def get_county_by_name_or_alias(input_str: str) -> Optional[CountyRecord]:
    """Helper to query the global registry by name or alias."""
    return _get_instance().get_by_name_or_alias(input_str)


def get_county_by_fips(fips_str: str) -> Optional[CountyRecord]:
    """Helper to query the global registry by exact 3-digit FIPS string."""
    return _get_instance().get_by_fips(fips_str)


def normalize_county_input(input_str: str) -> CountyRecord:
    """
    Given free text (name, alias, slug, fips), strictly resolve to a CA county.
    Raises ValueError if unmatched.
    """
    if not input_str:
        raise ValueError("Empty county input provided.")
        
    input_str = str(input_str).strip()
    
    reg = _get_instance()
    # If 3 digits, try FIPS route first
    if input_str.isdigit() and len(input_str) == 3:
        record = reg.get_by_fips(input_str)
        if record:
            return record

    record = reg.get_by_name_or_alias(input_str)
    if record:
        return record

    # Fallback heuristic: drop "county" word and retry
    clean_in = input_str.lower()
    if " county" in clean_in or "county of " in clean_in:
        clean_no_cty = clean_in.replace("county of", "").replace("county", "").strip()
        record = reg.get_by_name_or_alias(clean_no_cty)
        if record:
            return record

    raise ValueError(f"Could not resolve '{input_str}' to a valid California county in the registry.")
