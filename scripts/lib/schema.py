"""
scripts/lib/schema.py

Schema Registry utility for Campaign In A Box v2.
Standardizes DataFrames columns and validates system outputs.
"""

import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "config" / "schema_registry.yaml"

def load_registry() -> Dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def canonicalize_df(df: pd.DataFrame, log_mapping=True) -> pd.DataFrame:
    """
    Map raw column names to canonical system names based on schema_registry.yaml.
    """
    registry = load_registry()
    mappings = registry.get("mappings", {})
    
    # Reverse the mapping list for efficient lookup
    # e.g. "mprec" -> "canonical_precinct_id"
    reverse_map = {}
    for canonical, variants in mappings.items():
        for v in variants:
            reverse_map[v.lower()] = canonical
            
    # Identity mapping for canonical names themselves
    for canonical in mappings.keys():
        reverse_map[canonical.lower()] = canonical

    current_cols = df.columns.tolist()
    rename_dict = {}
    
    for col in current_cols:
        l_col = col.lower()
        if l_col in reverse_map:
            target = reverse_map[l_col]
            if target != col:
                rename_dict[col] = target
                
    if rename_dict:
        df = df.rename(columns=rename_dict)
        if log_mapping:
            print(f"[Schema] Canonicalized {len(rename_dict)} columns: {rename_dict}")
            
    return df

def validate_schema(df: pd.DataFrame, required: Optional[List[str]] = None):
    """
    Performs basic validation on the DataFrame.
    """
    registry = load_registry()
    rules = registry.get("rules", {})
    
    # 1. Check required columns
    if required:
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"[Schema] Missing required columns: {missing}")

    # 2. Require Finite
    for col in rules.get("require_finite", []):
        if col in df.columns:
            if df[col].isnull().any() or (df[col] == float('inf')).any():
                print(f"[Schema] [WARN] Column '{col}' contains non-finite values.")

    # 3. Scale 0-1
    for col in rules.get("scale_0_1", []):
        if col in df.columns:
            # Tolerant check (allow slight floating point overflow)
            if df[col].max() > 1.05 or df[col].min() < -0.05:
                print(f"[Schema] [WARN] Column '{col}' values out of bounds (0-1): min={df[col].min()}, max={df[col].max()}")

    return True
