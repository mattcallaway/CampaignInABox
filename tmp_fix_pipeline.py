import re
from pathlib import Path

fpath = Path("scripts/run_pipeline.py")
content = fpath.read_text("utf-8")

replacement = """    counties_list = [c.strip() for c in county.split(",")]
    
    # ── Prompt 19: Jurisdiction Master Index ────────────────────────────
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

        # ── Step 2: Scaffold boundary index ──────────────────────────────────
        if not (rebuild_maps_only or rebuild_targets_only):
            logger.step_start(f"SCAFFOLD_BOUNDARY_INDEX_{loop_county}")
            bi_path = scaffold_boundary_index(data_root, loop_county, log=logger)
            bi_refresh = refresh_boundary_index(data_root, loop_county, log=logger)
            logger.step_done(f"SCAFFOLD_BOUNDARY_INDEX_{loop_county}", outputs=[bi_path])
            all_artifacts.append(bi_path)"""

# The start sentinel inside run_pipeline.py:
start_sentinel = """    # ── Step 2: Scaffold boundary index ──────────────────────────────────
    if not (rebuild_maps_only or rebuild_targets_only):
        logger.step_start("SCAFFOLD_BOUNDARY_INDEX")
        bi_path = scaffold_boundary_index(data_root, county, log=logger)
        bi_refresh = refresh_boundary_index(data_root, county, log=logger)
        logger.step_done("SCAFFOLD_BOUNDARY_INDEX", outputs=[bi_path])
        all_artifacts.append(bi_path)
    else:
        logger.step_skip("SCAFFOLD_BOUNDARY_INDEX", reason="Skipped due to targeted rebuild flag")

    counties_list = [c.strip() for c in county.split(",")]
    
    # ── Prompt 19: Jurisdiction Master Index ────────────────────────────
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
        loop_county = current_county"""

if start_sentinel in content:
    content = content.replace(start_sentinel, replacement)
    fpath.write_text(content, "utf-8")
    print("Fixed scripts/run_pipeline.py successfully.")
else:
    print("Error: Could not find start sentinel in content.")
