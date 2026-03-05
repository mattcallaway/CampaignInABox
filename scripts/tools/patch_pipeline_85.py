"""
Patches run_pipeline.py for Prompt 8.5 stabilization.
Inserts:
  1. Enhanced crosswalk discovery in step 6
  2. INTEGRITY_ENFORCEMENT step after ALLOCATE_VOTES
Uses line-number anchors to avoid unicode string matching issues.
"""
from pathlib import Path

BASE = Path(r"c:\Users\Mathew C\Campaign In A Box")
target = BASE / "scripts" / "run_pipeline.py"
src = target.read_text(encoding="utf-8")

# ── Patch 1: Crosswalk step 6 — add discovery lines after the existing step ──
CROSSWALK_ANCHOR = '        logger.step_skip("LOAD_CROSSWALKS", reason="No crosswalk files; using identity mapping")'
CROSSWALK_INSERT_BEFORE = '        logger.step_skip("LOAD_CROSSWALKS"'

# Find the block to add discovery after the existing crosswalk loop
CW_SEARCH = (
    '    for cat_label, cat_dir in crosswalk_categories.items():\n'
    '        xwalk, ok = load_crosswalk_from_category(county_geo_dir, "crosswalks", logger=logger)\n'
    '        if ok:\n'
    '            crosswalks[cat_label] = xwalk\n'
    '            break  # use first available crosswalk\n'
    '\n'
    '    if not crosswalks:\n'
)

CW_REPLACE = (
    '    for cat_label, cat_dir in crosswalk_categories.items():\n'
    '        xwalk, ok = load_crosswalk_from_category(county_geo_dir, "crosswalks", logger=logger)\n'
    '        if ok:\n'
    '            crosswalks[cat_label] = xwalk\n'
    '            break  # use first available crosswalk\n'
    '\n'
    '    # Prompt 8.5: enhanced crosswalk discovery + validation\n'
    '    _county_fips = county_to_fips(county) or county\n'
    '    _contest_id_for_diag = f"{year}_{state}_{county.lower().replace(chr(32), chr(95))}_{contest_slug}"\n'
    '    _xwalk_full = discover_crosswalks(BASE_DIR, state, _county_fips)\n'
    '    write_crosswalk_validation(_xwalk_full, _contest_id_for_diag, run_id, BASE_DIR)\n'
    '    update_needs_crosswalks(_xwalk_full, BASE_DIR)\n'
    '    _n_xw_found = sum(1 for v in _xwalk_full.values() if v.get("status") in ("found", "fallback"))\n'
    '    logger.info(f"  [CROSSWALKS] Discovered {_n_xw_found}/{len(_xwalk_full)} crosswalks")\n'
    '\n'
    '    if not crosswalks:\n'
)

if CW_SEARCH in src:
    src = src.replace(CW_SEARCH, CW_REPLACE, 1)
    print("[OK] Patch 1: crosswalk discovery inserted")
else:
    print("[SKIP] Patch 1: anchor not found (already patched?)")

# ── Patch 2: Integrity step after ALLOCATE_VOTES ─────────────────────────────
INTEGRITY_SEARCH = (
    '    if not all_model_dfs:\n'
    '        logger.hard_fail("ALLOCATE_VOTES", "No model DataFrames produced")\n'
    '\n'
    '    # '
)

INTEGRITY_REPLACE = (
    '    if not all_model_dfs:\n'
    '        logger.hard_fail("ALLOCATE_VOTES", "No model DataFrames produced")\n'
    '\n'
    '    # Prompt 8.5: INTEGRITY_ENFORCEMENT step\n'
    '    logger.step_start("INTEGRITY_ENFORCEMENT")\n'
    '    _all_repair_reports: list[dict] = []\n'
    '    _repaired_model_dfs: list = []\n'
    '    for _mdf in all_model_dfs:\n'
    '        _sheet = _mdf["SheetName"].iloc[0] if "SheetName" in _mdf.columns else "unknown"\n'
    '        _mdf_repaired, _repair_report = enforce_precinct_constraints(\n'
    '            _mdf,\n'
    '            id_col="canonical_precinct_id",\n'
    '            registered_col="registered",\n'
    '            ballots_col="ballots_cast",\n'
    '            yes_col="yes_votes" if "yes_votes" in _mdf.columns else None,\n'
    '            no_col="no_votes"   if "no_votes"  in _mdf.columns else None,\n'
    '            log_ctx=_sheet,\n'
    '            logger=logger,\n'
    '        )\n'
    '        _all_repair_reports.append(_repair_report)\n'
    '        _repaired_model_dfs.append(_mdf_repaired)\n'
    '    all_model_dfs = _repaired_model_dfs\n'
    '    # Use _contest_id_for_diag if already defined, else build it\n'
    '    if "_contest_id_for_diag" not in dir():\n'
    '        _contest_id_for_diag = f"{year}_{state}_{county.lower().replace(chr(32), chr(95))}_{contest_slug}"\n'
    '    _primary_repair = _all_repair_reports[0] if _all_repair_reports else {}\n'
    '    write_integrity_report(_primary_repair, _contest_id_for_diag, run_id)\n'
    '    _n_repaired = _primary_repair.get("repaired_rows", 0)\n'
    '    logger.step_done("INTEGRITY_ENFORCEMENT", notes=[f"{_n_repaired} precinct(s) repaired"])\n'
    '\n'
    '    # '
)

if INTEGRITY_SEARCH in src:
    src = src.replace(INTEGRITY_SEARCH, INTEGRITY_REPLACE, 1)
    print("[OK] Patch 2: integrity enforcement inserted")
else:
    print("[SKIP] Patch 2: anchor not found (already patched?)")

target.write_text(src, encoding="utf-8")
print("Done. File written.")
print(f"File size: {target.stat().st_size:,} bytes")
