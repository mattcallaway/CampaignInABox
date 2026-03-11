import re
from pathlib import Path

target = Path("scripts/strategy/strategy_generator.py")
content = target.read_text("utf-8")

# Find the end of write_strategy_pack function
insertion_point = b"""
    if logger:
        _p12_files = ["GOTV_TARGETS.csv", "PERSUASION_TARGETS.csv", "TARGETING_QUADRANTS.csv",
"""

# The insertion logic
patch = """
    # ── Prompt 19: Jurisdiction Strategy Aggregation ─────────────────────────
    master_index_path = BASE_DIR / "derived" / "geography" / "precinct_master_index.csv"
    if master_index_path.exists() and not targets.empty:
        try:
            mi_df = pd.read_csv(master_index_path, dtype=str)
            # Find the precinct column in targets
            p_col = "canonical_precinct_id" if "canonical_precinct_id" in targets.columns else (
                    "MPREC_ID" if "MPREC_ID" in targets.columns else targets.columns[0])
            
            # Merge to get jurisdiction
            # Rename master index 'precinct' to match target's precinct column
            mi_df = mi_df.rename(columns={"precinct": p_col, "mprec_id": p_col})
            
            merged_targets = pd.merge(targets, mi_df, on=p_col, how="left")
            
            # Aggregate by county
            if "county" in merged_targets.columns:
                jurisdiction_strategy = merged_targets.groupby("county").agg(
                    total_precincts=(p_col, "count"),
                    total_registered=("registered", "sum") if "registered" in merged_targets.columns else (p_col, "count"),
                    avg_target_score=("target_score", "mean") if "target_score" in merged_targets.columns else (p_col, "count")
                ).reset_index()
                
                jurisdiction_strategy.to_csv(out_root / "jurisdiction_strategy.csv", index=False)
                
                # Also do resource allocation by jurisdiction if field_plan exists
                fp_df = inputs.get("field_plan", pd.DataFrame())
                if not fp_df.empty and "region_id" in fp_df.columns and "region_id" in merged_targets.columns:
                    # Map region_id to county via targets
                    region_county = merged_targets[["region_id", "county"]].drop_duplicates().dropna()
                    fp_merged = pd.merge(fp_df, region_county, on="region_id", how="left")
                    
                    res_alloc = fp_merged.groupby("county").agg(
                        doors_to_knock=("doors_to_knock", "sum") if "doors_to_knock" in fp_merged.columns else ("region_id", "count"),
                        volunteers_needed=("volunteers_needed", "sum") if "volunteers_needed" in fp_merged.columns else ("region_id", "count")
                    ).reset_index()
                    res_alloc.to_csv(out_root / "resource_allocation_by_jurisdiction.csv", index=False)
        except Exception as e:
            if logger: logger.warn(f"Failed to generate jurisdiction strategy: {e}")

"""

if insertion_point.decode("utf-8") in content:
    content = content.replace(insertion_point.decode("utf-8"), patch + insertion_point.decode("utf-8"))
    target.write_text(content, "utf-8")
    print("Patch successful!")
else:
    print("Insertion point not found!")

