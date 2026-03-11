import re
from pathlib import Path

target = Path("scripts/run_pipeline.py")
content = target.read_text("utf-8")

start_marker = "    # ── Step 3: Validate geography "
end_marker = "    # ── Step 17: Strategic Region Clustering (v3) "

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print(f"Markers not found! start:{start_idx} end:{end_idx}")
    exit(1)

pre = content[:start_idx]
post = content[end_idx:]
middle = content[start_idx:end_idx]

new_middle = """    counties_list = [c.strip() for c in county.split(",")]
    
    # \u2500\u2500 Prompt 19: Jurisdiction Master Index \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    if len(counties_list) > 1:
        try:
            from engine.geo.master_index_builder import build_master_precinct_index
            build_master_precinct_index(BASE_DIR, state, counties_list)
        except Exception as e:
            logger.warn(f"Failed to build master index: {e}")

    # Aggregated outputs across all counties
    global_all_scored_dfs = {}
    global_all_voter_features = []
    global_all_universes = {}
    
    for current_county in counties_list:
        logger.info(f"=== Processing County: {current_county} ===")
        loop_county = current_county
"""

middle = re.sub(r'\bcounty\b', 'loop_county', middle)
# Indent the middle by 4 spaces
indented_middle = "\n".join("    " + line if line else "" for line in middle.splitlines())

new_middle += indented_middle + "\n"

new_middle += """
        # Append to globals by sheet name
        for sname, sdf in all_scored_dfs:
            if sname not in global_all_scored_dfs:
                global_all_scored_dfs[sname] = []
            global_all_scored_dfs[sname].append(sdf)
            
        if not voter_features_df.empty:
            global_all_voter_features.append(voter_features_df)
            
        for sname, udf in all_universes:
            if sname not in global_all_universes:
                global_all_universes[sname] = []
            global_all_universes[sname].append(udf)

    # Re-combine into expected schema for Step 17+
    import pandas as pd
    all_scored_dfs = []
    for sname, dfs in global_all_scored_dfs.items():
        if dfs:
            all_scored_dfs.append((sname, pd.concat(dfs, ignore_index=True)))
            
    if global_all_voter_features:
        voter_features_df = pd.concat(global_all_voter_features, ignore_index=True)
    else:
        voter_features_df = pd.DataFrame()
        
    all_universes = []
    for sname, dfs in global_all_universes.items():
        if dfs:
            all_universes.append((sname, pd.concat(dfs, ignore_index=True)))
            
    # Restore original comma-separated string for trailing logging if needed
    county = ",".join(counties_list)

"""

target.write_text(pre + new_middle + post, "utf-8")
print("Refactor complete.")
