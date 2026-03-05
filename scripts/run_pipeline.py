#!/usr/bin/env python3
"""
scripts/run_pipeline.py

Campaign In A Box — Main Pipeline CLI

Usage:
    python scripts/run_pipeline.py \\
        --state CA \\
        --county SAMPLE_COUNTY \\
        --contest-file votes/2024/CA/SAMPLE_COUNTY/MEASURE_A/detail.xlsx \\
        --membership-method auto

    python scripts/run_pipeline.py --check-structure

All paths are relative to the Campaign In A Box root (parent of this scripts/ folder).
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Bootstrap: resolve base directory and add scripts/ to sys.path
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent  # Campaign In A Box/
SCRIPTS_DIR = Path(__file__).resolve().parent

if str(SCRIPTS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR.parent))


# ---------------------------------------------------------------------------
# Imports (after sys.path adjustment)
# ---------------------------------------------------------------------------

from scripts.loaders.logger import RunLogger, generate_run_id, sha256_file
from scripts.loaders.file_loader import discover_files
from scripts.loaders.manifest_builder import write_manifest
from scripts.loaders.contest_registry import scaffold_contest_json
from scripts.loaders.categories import (
    ALL_CATEGORIES, MPREC_GEOM_CATEGORIES, SRPREC_GEOM_CATEGORIES,
    CROSSWALK_CATEGORIES,
)
from scripts.geography.boundary_loader import load_canonical_geometry
from scripts.geography.crosswalk_resolver import load_crosswalk_from_category
from scripts.modeling.precinct_model import build_precinct_model, build_targeting_list
from scripts.aggregation.vote_allocator import (
    parse_contest_workbook,
    allocate_votes_crosswalk,
    area_weighted_fallback,
    run_sanity_checks,
)
from scripts.exports.exporter import (
    export_precinct_model,
    export_targeting_list,
    export_district_aggregates,
    export_kepler_geojson,
)

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config(key: str) -> dict:
    """Load a YAML config file from config/. Returns {} on missing."""
    path = BASE_DIR / "config" / f"{key}.yaml"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def check_structure() -> bool:
    """Verify all required directories exist. Returns True if OK."""
    required = (
        [f"Campaign in a box Data/CA/SAMPLE_COUNTY/{cat}" for cat in ALL_CATEGORIES]
        + [
            "votes/2024/CA/SAMPLE_COUNTY/MEASURE_A",
            "voters/CA/SAMPLE_COUNTY",
            "derived/normalized_boundaries",
            "derived/memberships",
            "derived/precinct_models",
            "derived/district_aggregates",
            "derived/campaign_targets",
            "derived/maps",
            "derived/reports",
            "logs/runs",
            "logs/latest",
            "reports/validation",
            "reports/qa",
            "needs/history",
            "config",
            "scripts/loaders",
            "scripts/geography",
            "scripts/modeling",
            "scripts/aggregation",
            "scripts/exports",
        ]
    )
    missing = [d for d in required if not (BASE_DIR / d).is_dir()]
    if missing:
        print(f"[STRUCTURE CHECK] FAIL — {len(missing)} directories missing:")
        for m in missing:
            print(f"  missing: {m}")
        return False
    print(f"[STRUCTURE CHECK] OK — all {len(required)} required directories present.")
    return True


def _parse_contest_slug_from_path(contest_file: Path) -> tuple[str, str, str, str]:
    """
    Infer year/state/county/contest_slug from contest file path:
    votes/<YEAR>/<STATE>/<COUNTY>/<CONTEST_SLUG>/detail.xlsx
    """
    parts = contest_file.parts
    try:
        votes_idx = next(i for i, p in enumerate(parts) if p.lower() == "votes")
        year         = parts[votes_idx + 1]
        state        = parts[votes_idx + 2]
        county       = parts[votes_idx + 3]
        contest_slug = parts[votes_idx + 4]
        return year, state, county, contest_slug
    except (StopIteration, IndexError):
        return "UNKNOWN", "CA", "UNKNOWN_COUNTY", contest_file.stem


def _git_commit(message: str, paths: list[Path]):
    """Stage files and commit with provided message."""
    try:
        str_paths = [str(p) for p in paths if p.exists()]
        if not str_paths:
            return
        subprocess.run(
            ["git", "add"] + str_paths,
            cwd=str(BASE_DIR), capture_output=True, check=False
        )
        subprocess.run(
            ["git", "commit", "-m", message, "--allow-empty"],
            cwd=str(BASE_DIR), capture_output=True, check=False
        )
    except Exception:
        pass  # Git failure is non-fatal for pipeline run


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    state: str,
    county: str,
    contest_file_rel: str,
    membership_method: str = "auto",
    commit: bool = True,
) -> str:
    """
    Execute the full pipeline. Returns RUN_ID on success.
    Raises RuntimeError on hard-fail.
    """
    # ── Step 0: Generate RUN_ID and open logger ──────────────────────────
    run_id = generate_run_id()
    logger = RunLogger(run_id, BASE_DIR)
    logger.info(f"Pipeline starting")
    logger.info(f"  state={state}  county={county}")
    logger.info(f"  contest_file={contest_file_rel}")
    logger.info(f"  membership_method={membership_method}")
    logger.info(f"  base_dir={BASE_DIR}")

    config = load_config("model_parameters")

    contest_file = BASE_DIR / contest_file_rel
    year, inferred_state, inferred_county, contest_slug = _parse_contest_slug_from_path(contest_file)

    # Allow CLI overrides to win
    if state == "CA" and inferred_state:
        state = inferred_state if inferred_state != "UNKNOWN" else state
    if inferred_county and inferred_county != "UNKNOWN_COUNTY":
        county = inferred_county

    data_root = BASE_DIR / "Campaign in a box Data"

    # ── Step 1: Discover inputs ───────────────────────────────────────────
    logger.step_start(
        "DISCOVER_INPUTS",
        expected=[
            f"Campaign in a box Data/{state}/{county}/",
            str(contest_file),
        ],
    )

    # Build/refresh manifest
    manifest_path = write_manifest(data_root, state, county)
    logger.info(f"  Manifest written: {manifest_path}")

    # Scaffold contest.json
    votes_root = BASE_DIR / "votes"
    contest_json_path = scaffold_contest_json(
        votes_root,
        year=year,
        state=state,
        county=county,
        contest_slug=contest_slug,
    )
    logger.step_done("DISCOVER_INPUTS", outputs=[manifest_path, contest_json_path])

    # ── Step 2: Validate inputs ───────────────────────────────────────────
    logger.step_start("VALIDATE_INPUTS", expected=["contest_file readable"])
    if not contest_file.exists():
        logger.hard_fail("VALIDATE_INPUTS", f"Contest file not found: {contest_file}")

    logger.register_input("contest_file", contest_file)
    logger.register_sanity("contest_file_exists", True, str(contest_file))
    logger.step_done("VALIDATE_INPUTS")

    # ── Step 3: Load geometry ─────────────────────────────────────────────
    logger.step_start(
        "LOAD_GEOMETRY",
        expected=["MPREC GeoJSON or GeoPackage preferred", "SRPREC as fallback"],
    )

    gdf, geo_level, geo_id_col = load_canonical_geometry(
        data_root, state, county, logger=logger
    )

    if gdf is None:
        # No geometry at all — log as NEED and continue (geometry is required for Kepler)
        logger.register_need(
            "MPREC_GeoJSON",
            "missing",
            blocks=["kepler_export"],
            path=str(data_root / state / county / "MPREC_GeoJSON"),
        )
        logger.register_need(
            "SRPREC_GeoJSON",
            "missing",
            blocks=["kepler_export"],
            path=str(data_root / state / county / "SRPREC_GeoJSON"),
        )
        logger.step_skip("LOAD_GEOMETRY", reason="No geometry files found in data pack")
        geo_level = "NONE"

    elif isinstance(gdf, dict) and gdf.get("_stub"):
        # geopandas not installed
        file_hint = gdf.get("_file", "unknown")
        logger.warn(f"geopandas not installed; geometry found at {file_hint} but not loaded")
        logger.register_need(
            "geopandas_library",
            "missing",
            blocks=["geometry_load", "kepler_export"],
        )
        logger.step_skip("LOAD_GEOMETRY", reason="geopandas not available")
        gdf = None
        geo_level = "NONE"

    else:
        logger.set_coverage("geometry_features", len(gdf))
        logger.set_coverage("geography_level", geo_level)
        logger.set_coverage("geometry_id_col", geo_id_col)
        logger.step_done("LOAD_GEOMETRY")

    # ── Step 4: Load crosswalks ───────────────────────────────────────────
    logger.step_start("LOAD_CROSSWALKS")

    crosswalks: dict[str, dict] = {}
    county_dir = data_root / state / county

    for cat in CROSSWALK_CATEGORIES:
        xwalk, success = load_crosswalk_from_category(county_dir, cat, logger=logger)
        if success:
            crosswalks[cat] = xwalk
        else:
            logger.register_need(
                cat,
                "missing",
                blocks=[f"crosswalk_{cat}"],
                path=str(county_dir / cat),
            )

    if crosswalks:
        logger.step_done("LOAD_CROSSWALKS", notes=[f"Loaded: {list(crosswalks.keys())}"])
    else:
        logger.step_skip("LOAD_CROSSWALKS", reason="No crosswalk files found; will use identity mapping")

    # ── Step 5: Parse contest workbook ────────────────────────────────────
    logger.step_start(
        "PARSE_CONTEST",
        expected=["All sheets parsed", "Contest type detected"],
    )

    parsed_sheets = parse_contest_workbook(
        contest_file,
        contest_json_path=contest_json_path,
        config=config,
        logger=logger,
    )
    logger.set_coverage("sheets_parsed", len(parsed_sheets))
    logger.step_done("PARSE_CONTEST")

    # ── Step 6: Allocate votes ────────────────────────────────────────────
    logger.step_start("ALLOCATE_VOTES")

    all_model_dfs: list[pd.DataFrame] = []
    all_artifacts: list[Path] = []

    for parsed in parsed_sheets:
        sheet_name  = parsed["sheet_name"]
        contest_type = parsed["contest_type"]
        totals_df   = parsed["totals_df"]

        if totals_df.empty:
            logger.step_skip(f"ALLOCATE_VOTES/{sheet_name}", reason="No data rows")
            continue

        logger.info(f"  Allocating sheet: {sheet_name!r} ({len(totals_df)} precincts)")

        # Choose allocation method
        if membership_method == "auto":
            # Try MPREC_to_SRPREC crosswalk first
            xwalk = crosswalks.get("MPREC_to_SRPREC") or crosswalks.get("RG_to_RR_to_SR_to_SVPREC")
        elif membership_method == "crosswalk":
            xwalk = next(iter(crosswalks.values()), None) if crosswalks else None
        else:
            xwalk = None

        if xwalk:
            allocated_df = allocate_votes_crosswalk(
                totals_df, xwalk, src_id_col="PrecinctID", tgt_id_col="MPREC_ID"
            )
            method_used = "crosswalk"
        else:
            allocated_df = area_weighted_fallback(totals_df, src_id_col="PrecinctID")
            method_used = "area_weighted_fallback"

        logger.info(f"    Allocation method: {method_used}, {len(allocated_df)} target precincts")

        # ── Step 7: Sanity checks ─────────────────────────────────────────
        logger.step_start(f"SANITY_CHECKS/{sheet_name}")
        passed, violations = run_sanity_checks(allocated_df, config, logger=logger)
        if not passed:
            violation_str = "; ".join(violations)
            logger.hard_fail(
                f"SANITY_CHECKS/{sheet_name}",
                f"Sanity violations: {violation_str}",
            )
        logger.step_done(f"SANITY_CHECKS/{sheet_name}")

        # ── Step 8: Build precinct model ──────────────────────────────────
        logger.step_start(f"BUILD_MODEL/{sheet_name}")
        id_col = "MPREC_ID" if "MPREC_ID" in allocated_df.columns else allocated_df.columns[0]
        model_df = build_precinct_model(
            allocated_df,
            canvas_id_col=id_col,
            geography_level=geo_level,
            gdf=gdf,
            geo_id_col=geo_id_col,
            config=config,
        )
        model_df["SheetName"] = sheet_name
        model_df["ContestType"] = contest_type
        logger.set_coverage(f"precinct_rows_{sheet_name}", len(model_df))
        all_model_dfs.append(model_df)
        logger.step_done(f"BUILD_MODEL/{sheet_name}")

    logger.step_done("ALLOCATE_VOTES")

    if not all_model_dfs:
        logger.hard_fail("ALLOCATE_VOTES", "No model DataFrames produced from any sheet")

    # ── Step 9: Export outputs ────────────────────────────────────────────
    logger.step_start("EXPORT_OUTPUTS")

    for model_df in all_model_dfs:
        sheet_name = model_df["SheetName"].iloc[0]
        sheet_slug = contest_slug + ("" if len(all_model_dfs) == 1 else f"__{sheet_name}")

        # Precinct model CSV
        csv_path = export_precinct_model(
            model_df, BASE_DIR, run_id, state, county, sheet_slug
        )
        logger.info(f"  Precinct model CSV: {csv_path}")
        all_artifacts.append(csv_path)

        # Targeting list CSV
        field_config = load_config("field_effects")
        min_score = field_config.get("targeting", {}).get("universe_min_score", 0.30)
        targeting_df = build_targeting_list(model_df, min_score=min_score)
        target_path = export_targeting_list(
            targeting_df, BASE_DIR, run_id, state, county, sheet_slug
        )
        logger.info(f"  Targeting list CSV: {target_path} ({len(targeting_df)} rows)")
        all_artifacts.append(target_path)

        # District aggregates CSV
        agg_path = export_district_aggregates(
            model_df, BASE_DIR, run_id, state, county, sheet_slug
        )
        logger.info(f"  District aggregates: {agg_path}")
        all_artifacts.append(agg_path)

        # Kepler GeoJSON (only if geometry present)
        id_col = next((c for c in model_df.columns if "ID" in c.upper()), "PrecinctID")
        kepler_path = export_kepler_geojson(
            model_df, BASE_DIR, run_id, state, county, sheet_slug, id_col=id_col
        )
        if kepler_path:
            logger.info(f"  Kepler GeoJSON: {kepler_path}")
            all_artifacts.append(kepler_path)
        else:
            logger.step_skip(
                f"KEPLER_EXPORT/{sheet_name}",
                reason="No geometry in model (boundary files missing or geopandas unavailable)",
            )
            logger.register_need(
                "geometry_for_kepler",
                "blocked",
                blocks=["kepler_geojson"],
                path=str(BASE_DIR / "Campaign in a box Data" / state / county / "MPREC_GeoJSON"),
            )

    logger.step_done("EXPORT_OUTPUTS", outputs=all_artifacts)

    # ── Step 10: Finalize logging ─────────────────────────────────────────
    logger.finalize(
        state=state,
        county=county,
        contest_slug=contest_slug,
        run_status="success",
    )

    # ── Step 11: Git commit ───────────────────────────────────────────────
    if commit:
        commit_paths = (
            [manifest_path, contest_json_path]
            + all_artifacts
            + [logger.log_path, logger.pathway_path,
               logger.validation_path, logger.qa_path,
               logger.needs_path, logger.needs_snapshot_path]
            + list(logger.latest_dir.iterdir())
        )
        _git_commit(
            f"derived: run {run_id} — {state}/{county}/{contest_slug}",
            commit_paths,
        )
        _git_commit(
            f"reports: logs and needs for run {run_id}",
            [logger.log_path, logger.pathway_path,
             logger.validation_path, logger.qa_path,
             logger.needs_path, logger.needs_snapshot_path],
        )

    print(f"\n{'='*60}")
    print(f"  RUN COMPLETE — RUN_ID: {run_id}")
    print(f"  Artifacts produced: {len(all_artifacts)}")
    print(f"  Logs: logs/runs/{run_id}__run.log")
    print(f"  Latest: logs/latest/")
    print(f"{'='*60}\n")

    return run_id


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Campaign In A Box — Election Modeling Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_pipeline.py --check-structure

  python scripts/run_pipeline.py \\
    --state CA \\
    --county SAMPLE_COUNTY \\
    --contest-file votes/2024/CA/SAMPLE_COUNTY/MEASURE_A/detail.xlsx \\
    --membership-method auto
        """,
    )
    parser.add_argument(
        "--check-structure", action="store_true",
        help="Verify required directory tree exists and exit."
    )
    parser.add_argument("--state",   default="CA",   help="State code (default: CA)")
    parser.add_argument("--county",  default=None,   help="County name (inferred from path if omitted)")
    parser.add_argument(
        "--contest-file", dest="contest_file", default=None,
        help="Relative path to detail.xlsx from Campaign In A Box root",
    )
    parser.add_argument(
        "--membership-method", dest="membership_method",
        choices=["crosswalk", "area_weighted", "auto"], default="auto",
        help="Method for allocating votes to canonical geography (default: auto)",
    )
    parser.add_argument(
        "--no-commit", dest="commit", action="store_false",
        help="Skip git commit after run (useful for dry-runs)",
    )
    parser.set_defaults(commit=True)

    args = parser.parse_args()

    if args.check_structure:
        ok = check_structure()
        sys.exit(0 if ok else 1)

    if not args.contest_file:
        parser.error("--contest-file is required unless --check-structure is used.")

    county = args.county
    if county is None:
        # Infer county from contest file path
        cf = Path(args.contest_file)
        _, _, county, _ = _parse_contest_slug_from_path(BASE_DIR / cf)

    try:
        run_id = run_pipeline(
            state=args.state,
            county=county,
            contest_file_rel=args.contest_file,
            membership_method=args.membership_method,
            commit=args.commit,
        )
    except RuntimeError as e:
        print(f"\n[PIPELINE HARD FAIL] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[PIPELINE ERROR] Unexpected: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
