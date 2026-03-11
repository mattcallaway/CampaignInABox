"""
engine/geo/master_index_builder.py — Prompt 19

Generates 'derived/geography/precinct_master_index.csv' by stitching together
all discovered geographic crosswalks across counties in a state.
"""
import logging
from pathlib import Path
import pandas as pd
from scripts.lib.crosswalks import discover_crosswalks

log = logging.getLogger(__name__)

def build_master_precinct_index(base_dir: Path | str, state: str, counties: list[str]) -> Path | None:
    """
    Builds the cross-jurisdiction precinct master index containing:
    state, county, precinct, mprec, srprec, city, supervisorial_district, etc.
    """
    root = Path(base_dir)
    out_dir = root / "derived" / "geography"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "precinct_master_index.csv"
    
    all_dfs = []
    
    for county in counties:
        # Discover all local crosswalks for this county
        xwalks_meta = discover_crosswalks(root, state, county)
        
        county_dfs = {}
        for xw_id, meta in xwalks_meta.items():
            if meta.get("status") in ["found", "fallback"] and meta.get("path"):
                try:
                    df = pd.read_csv(meta["path"], dtype=str)
                    county_dfs[xw_id] = df
                except Exception as e:
                    log.warning(f"Failed to read crosswalk for master index: {meta['path']} -> {e}")

        # The core is usually MPREC. If a crosswalk maps MPREC to SRPREC, or SRPREC to CITY
        # we can join them. Since crosswalk schemas can vary wildly, we try to create a standard frame.
        
        # Build a base dataframe with MPREC as the foundational "precinct"
        base_df = pd.DataFrame()
        mprec_to_srprec = county_dfs.get("MPREC_to_SRPREC")
        if mprec_to_srprec is not None and not mprec_to_srprec.empty:
            df = mprec_to_srprec.copy()
            # Standardize columns
            col_map = {c: c.lower() for c in df.columns}
            df = df.rename(columns=col_map)
            
            # Extract common columns
            if "mprec_id" in df.columns: base_df["precinct"] = df["mprec_id"]
            elif "mprec" in df.columns: base_df["precinct"] = df["mprec"]
            elif "precinct" in df.columns: base_df["precinct"] = df["precinct"]
            else: base_df["precinct"] = df.iloc[:, 0]
            
            if "srprec_id" in df.columns: base_df["srprec"] = df["srprec_id"]
            elif "srprec" in df.columns: base_df["srprec"] = df["srprec"]
            else: base_df["srprec"] = df.iloc[:, 1]
            
            base_df["mprec"] = base_df["precinct"]
        
        # If no base_df could be formed from mprec_to_srprec, we can't do much automatically,
        # but we'll create a fallback list if any crosswalk exists.
        if base_df.empty and county_dfs:
            first_df = list(county_dfs.values())[0]
            base_df["precinct"] = first_df.iloc[:, 0].astype(str)
            base_df["mprec"] = base_df["precinct"]
            base_df["srprec"] = None
            
        base_df["state"] = state
        base_df["county"] = county
        base_df["city"] = "Unincorporated"
        base_df["supervisorial_district"] = "Unknown"
        base_df["school_district"] = "Unknown"
        
        # Attempt to map cities if SRPREC_to_CITY crosswalk exists
        sr_to_city = county_dfs.get("SRPREC_to_CITY")
        if sr_to_city is not None and not base_df.empty and not sr_to_city.empty:
            c_map = {c: c.lower() for c in sr_to_city.columns}
            sr_to_city = sr_to_city.rename(columns=c_map)
            
            sr_col = "srprec_id" if "srprec_id" in sr_to_city.columns else ("srprec" if "srprec" in sr_to_city.columns else sr_to_city.columns[0])
            city_col = "city" if "city" in sr_to_city.columns else ("city_name" if "city_name" in sr_to_city.columns else sr_to_city.columns[1])
            
            # create mapping dictionary
            if sr_col and city_col:
                mapping = dict(zip(sr_to_city[sr_col].astype(str), sr_to_city[city_col].astype(str)))
                base_df["city"] = base_df["srprec"].map(mapping).fillna(base_df["city"])
        
        all_dfs.append(base_df)
        
    if not all_dfs:
        return None

    final_df = pd.concat(all_dfs, ignore_index=True)
    
    final_df.to_csv(out_path, index=False)
    log.info(f"Built Precinct Master Index with {len(final_df)} precincts across {len(counties)} counties.")
    return out_path
