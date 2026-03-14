"""
Patch script: fix ALLOCATE_VOTES dict/DataFrame crash in run_pipeline.py
Run from project root: python _patch_allocate_votes.py
"""
from pathlib import Path

TARGET = Path("scripts/run_pipeline.py")
src = TARGET.read_text(encoding="utf-8")

# ── Find the exact broken substring ──────────────────────────────────────────
OLD_MARKER = '                        on=next((c for c in ["PrecinctID", xwalk.columns[0]]'
if OLD_MARKER not in src:
    print("ALREADY PATCHED or marker not found. Current lines 559-576:")
    for i, l in enumerate(src.splitlines()[558:577], 559):
        print(f"  {i}: {l}")
    raise SystemExit(0)

# ── Build precise old block using the actual line endings in the file ────────
lines = src.splitlines(keepends=True)
# Find the "# Allocation" comment line
alloc_start = next(i for i, l in enumerate(lines) if "# Allocation" in l and "xwalk" not in l)
# Grab lines alloc_start through alloc_start+16 (the broken block)
old_block = "".join(lines[alloc_start : alloc_start + 17])
print("OLD BLOCK FOUND:")
print(old_block)

NEW_BLOCK = """\
            # Allocation
            xwalk = next(iter(crosswalks.values()), None) if crosswalks else None
            if xwalk and membership_method != "area_weighted":
                try:
                    import pandas as _pd
                    if isinstance(xwalk, dict):
                        _rows = [
                            {"_xw_src": src_id, "_xw_tgt": tgt, "_xw_wt": wt}
                            for src_id, entries in xwalk.items()
                            for tgt, wt in (entries if entries else [])
                        ]
                        xwalk_df = _pd.DataFrame(_rows) if _rows else None
                    else:
                        xwalk_df = xwalk  # already a DataFrame
                    if xwalk_df is not None and not xwalk_df.empty:
                        _join_col = next(
                            (c for c in ["PrecinctID", "srprec", "mprec", "precinct"]
                             if c in totals_df.columns),
                            totals_df.columns[0],
                        )
                        allocated_df = safe_merge(
                            totals_df, xwalk_df,
                            left_on=_join_col, right_on="_xw_src",
                            how="left", expect="many_to_one",
                            name=f"crosswalk_alloc/{sheet_name}",
                            log_ctx=sheet_name,
                            contest_id=_contest_id_for_diag if "_contest_id_for_diag" in dir() else "unknown",
                            run_id=run_id, logger=logger,
                        )
                    else:
                        logger.info(f"  [ALLOCATE] Empty crosswalk dict — area-weighted fallback")
                        allocated_df = area_weighted_fallback(totals_df, src_id_col="PrecinctID")
                except JoinExplosionError as _jex:
                    logger.warn(f"  [JOIN_GUARD] Explosion in crosswalk alloc: {_jex}. Falling back.")
                    allocated_df = area_weighted_fallback(totals_df, src_id_col="PrecinctID")
                except Exception as _xe:
                    logger.warn(f"  [ALLOCATE] Crosswalk error: {_xe}. Falling back to area-weighted.")
                    allocated_df = area_weighted_fallback(totals_df, src_id_col="PrecinctID")
                method_used = "crosswalk"
"""

patched = src.replace(old_block, NEW_BLOCK, 1)
if patched == src:
    print("ERROR: replacement had no effect — block mismatch")
    raise SystemExit(1)

TARGET.write_text(patched, encoding="utf-8")
print("PATCHED OK — verifying line 565:")
for i, l in enumerate(patched.splitlines()[558:603], 559):
    print(f"  {i}: {l}")
