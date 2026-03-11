"""
engine/jurisdictions/jurisdiction_resolver.py — Prompt 19

Resolves geographic hierarchies and maps entities (precincts, voters, contests)
to jurisdictions defined in config/jurisdictions_registry.json.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional
import pandas as pd

log = logging.getLogger(__name__)

class JurisdictionResolver:
    def __init__(self, base_dir: Path | str, run_id: str):
        self.root = Path(base_dir)
        self.run_id = run_id
        self.registry = self._load_registry()
        self.master_index = self._load_master_index()
        
    def _load_registry(self) -> dict:
        reg_path = self.root / "config" / "jurisdictions_registry.json"
        if reg_path.exists():
            with open(reg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
        
    def _load_master_index(self) -> Optional[pd.DataFrame]:
        index_path = self.root / "derived" / "geography" / "precinct_master_index.csv"
        if index_path.exists():
            return pd.read_csv(index_path, dtype=str)
        return None

    def get_supported_counties(self, state: str) -> list[str]:
        """Returns list of active counties for a given state from registry."""
        state_config = self.registry.get(state, {})
        return list(state_config.keys())
        
    def resolve_precinct(self, state: str, county: str, precinct_id: str) -> dict:
        """
        Given a precinct, return its full jurisdictional lineage.
        (city, supervisorial_district, school_district, etc.)
        """
        if self.master_index is None or self.master_index.empty:
            # Fallback if no master index
            return {
                "state": state,
                "county": county,
                "precinct": precinct_id
            }
            
        # Try to find exactly matching precinct
        mask = (
            (self.master_index["state"] == state) & 
            (self.master_index["county"] == county) &
            (self.master_index["precinct"] == precinct_id)
        )
        match = self.master_index[mask]
        if not match.empty:
            # Return first match as a dict, replacing nan with None
            row = match.iloc[0].to_dict()
            return {k: (v if pd.notna(v) else None) for k, v in row.items()}
            
        return {
            "state": state,
            "county": county,
            "precinct": precinct_id
        }

    def get_precincts_for_jurisdiction(self, state: str, county: str, jurisdiction_level: str, jurisdiction_name: str) -> list[str]:
        """
        Retrieves all precinct IDs belonging to a specific jurisdiction 
        (e.g., all precincts in 'Supervisor District 1').
        """
        if self.master_index is None or self.master_index.empty:
            return []
            
        # Ensure column exists
        if jurisdiction_level not in self.master_index.columns:
            return []
            
        mask = (
            (self.master_index["state"] == state) & 
            (self.master_index["county"] == county) &
            (self.master_index[jurisdiction_level] == str(jurisdiction_name))
        )
        return self.master_index[mask]["precinct"].tolist()
