#!/usr/bin/env python3
"""
scripts/run_pipeline.py  — Campaign In A Box v2

CLI entry point for the full election modeling pipeline.

Usage examples:
  # Check directory structure
  python scripts/run_pipeline.py --check-structure

  # Ingest staging data only
  python scripts/run_pipeline.py --ingest-only --staging-dir "C:/path/to/Campaign In A Box Data"

  # Full run with votes
  python scripts/run_pipeline.py \\
      --state CA \\
      --county Sonoma \\
      --year 2024 \\
      --contest-slug nov2024_general \\
      --membership-method auto \\
      --log-level verbose

  # Full run with explicit detail path
  python scripts/run_pipeline.py \\
      --state CA --county Sonoma --year 2024 --contest-slug nov2024_general \\
      --detail-path "votes/2024/CA/Sonoma/nov2024_general/detail.xlsx"
"""

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path

import yaml

# ── Bootstrap ─────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent   # Campaign In A Box/
SCRIPTS_DIR = BASE_DIR / "scripts"
for p in [str(BASE_DIR), str(SCRIPTS_DIR.parent)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ── Imports ───────────────────────────────────────────────────────────────────
from scripts.lib.run_id import generate_run_id
from scripts.lib.hashing import sha256_file, file_info
from scripts.lib.ca_fips import fips_to_county, county_to_fips
from app.lib.state_manager import clear_stale
from scripts.loaders.logger import RunLogger
from scripts.ingest import run_ingestion
from scripts.validation.geography_validator import (
    validate_county_geography,
    validate_votes_present,
)
from scripts.validation.boundary_index import (
    scaffold_boundary_index,
    refresh_boundary_index,
)
from scripts.geography.boundary_loader import load_canonical_geometry
from scripts.geography.crosswalk_resolver import load_crosswalk_from_category
from scripts.aggregation.vote_allocator import (
    parse_contest_workbook,
    allocate_votes_crosswalk,
    area_weighted_fallback,
    run_sanity_checks,
)
from scripts.modeling.precinct_model import build_precinct_model, build_targeting_list
from scripts.exports.exporter import (
    export_precinct_model,
    export_targeting_list,
    export_district_aggregates,
    export_kepler_geojson,
)
from scripts.loaders.contest_registry import scaffold_contest_json, update_contest_from_parse

import pandas as pd


# ── Config helpers ────────────────────────────────────────────────────────────

def load_config(key: str) -> dict:
    path = BASE_DIR / "config" / f"{key}.yaml"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _git_commit(message: str, paths: list[Path]):
    try:
        str_paths = [str(p) for p in paths if p and Path(p).exists()]
        if not str_paths:
            return
        subprocess.run(["git", "add"] + str_paths, cwd=str(BASE_DIR),
                       capture_output=True, check=False)
        subprocess.run(["git", "commit", "-m", message, "--allow-empty"],
                       cwd=str(BASE_DIR), capture_output=True, check=False)
    except Exception:
        pass


# ── Structure check ───────────────────────────────────────────────────────────

REQUIRED_DIRS = [
    "Campaign In A Box Data",
    "staging/extracted",
    "data/CA/counties/Sonoma/geography/precinct_shapes/MPREC_GeoJSON",
    "data/CA/counties/Sonoma/geography/precinct_shapes/MPREC_GeoPackage",
    "data/CA/counties/Sonoma/geography/precinct_shapes/MPREC_Shapefile",
    "data/CA/counties/Sonoma/geography/precinct_shapes/SRPREC_GeoJSON",
    "data/CA/counties/Sonoma/geography/precinct_shapes/SRPREC_GeoPackage",
    "data/CA/counties/Sonoma/geography/precinct_shapes/SRPREC_Shapefile",
    "data/CA/counties/Sonoma/geography/crosswalks",
    "data/CA/counties/Sonoma/geography/boundaries/supervisorial",
    "data/CA/counties/Sonoma/geography/boundaries/city_council",
    "data/CA/counties/Sonoma/geography/boundaries/school",
    "data/CA/counties/Sonoma/geography/boundary_index",
    "votes",
    "voters",
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
    "scripts/lib",
    "scripts/validation",
    "scripts/loaders",
    "scripts/geography",
    "scripts/modeling",
    "scripts/aggregation",
    "scripts/exports",
]


def check_structure() -> bool:
    missing = [d for d in REQUIRED_DIRS if not (BASE_DIR / d).is_dir()]
    if missing:
        print(f"[STRUCTURE CHECK] FAIL -- {len(missing)} directories missing:")
        for m in missing:
            print(f"  missing: {m}")
        return False
    print(f"[STRUCTURE CHECK] OK -- all {len(REQUIRED_DIRS)} required directories present.")
    return True


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    state: str,
    county: str,
    year: str,
    contest_slug: str,
    detail_path_override: str | None = None,
    membership_method: str = "auto",
    staging_dir: str | None = None,
    log_level: str = "verbose",
    commit: bool = True,
    rebuild_memberships_only: bool = False,
    rebuild_maps_only: bool = False,
    rebuild_targets_only: bool = False,
) -> str:
    """Execute the full pipeline. Returns RUN_ID on success."""
    context_key = f"{state}/{county}/{year}/{contest_slug}"

    # ── Step 0: RUN_ID + logger ───────────────────────────────────────────
    run_id = generate_run_id(repo_dir=BASE_DIR)
    logger = RunLogger(run_id, BASE_DIR)
    logger.info(f"Pipeline v2 starting")
    logger.info(f"  state={state}  county={county}  year={year}  contest_slug={contest_slug}")
    logger.info(f"  membership_method={membership_method}  log_level={log_level}")

    config    = load_config("model_parameters")
    data_root = BASE_DIR / "data"
    votes_root = BASE_DIR / "votes"
    all_artifacts: list[Path] = []

    # ── Step 1: Ingestion (if staging_dir provided) ───────────────────────
    if staging_dir:
        logger.step_start("INGEST_STAGING", expected=[f"Files from: {staging_dir}"])
        try:
            result = run_ingestion(
                staging_dir=staging_dir,
                data_root=data_root,
                dry_run=False,
                log=logger,
            )
            county_count = len(result)
            file_count = sum(len(v) for v in result.values())
            logger.step_done(
                "INGEST_STAGING",
                notes=[f"{file_count} files across {county_count} counties"],
            )
        except Exception as e:
            logger.warn(f"Ingestion error (non-fatal): {e}")
            logger.step_skip("INGEST_STAGING", reason=str(e))
    else:
        logger.step_skip("INGEST_STAGING", reason="No --staging-dir provided; skipping ingestion")

    # ── Step 2: Scaffold boundary index ──────────────────────────────────
    if not (rebuild_maps_only or rebuild_targets_only):
        logger.step_start("SCAFFOLD_BOUNDARY_INDEX")
        bi_path = scaffold_boundary_index(data_root, county, log=logger)
        bi_refresh = refresh_boundary_index(data_root, county, log=logger)
        logger.step_done("SCAFFOLD_BOUNDARY_INDEX", outputs=[bi_path])
        all_artifacts.append(bi_path)
    else:
        logger.step_skip("SCAFFOLD_BOUNDARY_INDEX", reason="Skipped due to targeted rebuild flag")

    # ── Step 3: Validate geography ────────────────────────────────────────
    logger.step_start("VALIDATE_GEOGRAPHY", expected=[
        f"data/CA/counties/{county}/geography/precinct_shapes/",
        f"data/CA/counties/{county}/geography/crosswalks/",
    ])
    geo_validation = validate_county_geography(data_root, county, log=logger)
    for need in geo_validation["needs_entries"]:
        logger.register_need(
            need["category"], need["status"], need["blocks"],
            path=need.get("expected_path"),
        )
    logger.set_coverage("canonical_geometry", geo_validation["canonical_geometry"])
    logger.set_coverage("categories_present", len(geo_validation["present"]))
    logger.set_coverage("categories_missing", len(geo_validation["missing"]))
    logger.step_done("VALIDATE_GEOGRAPHY")

    # ── Step 4: Validate votes ────────────────────────────────────────────
    logger.step_start("VALIDATE_VOTES", expected=[
        f"votes/{year}/CA/{county}/{contest_slug}/detail.xlsx"
    ])

    if detail_path_override:
        detail_path = Path(detail_path_override)
        if not detail_path.is_absolute():
            detail_path = BASE_DIR / detail_path_override
        votes_valid = detail_path.exists()
        votes_need  = None
    else:
        votes_result = validate_votes_present(votes_root, year, county, contest_slug, log=logger)
        votes_valid  = votes_result["valid"]
        detail_path  = votes_result.get("path")
        votes_need   = votes_result.get("needs_entry")

    if not votes_valid:
        if votes_need:
            logger.register_need(
                votes_need["category"], votes_need["status"],
                votes_need["blocks"], path=votes_need.get("expected_path"),
            )
        logger.step_skip("VALIDATE_VOTES", reason="blocked: missing votes — detail.xlsx not found")
        # Still run ingestion/validation; just skip modeling steps
        logger.finalize(state, county, contest_slug, run_status="partial")
        if commit:
            _git_commit(
                f"reports: ingestion+validation run {run_id} -- {state}/{county} (no votes)",
                [logger.log_path, logger.pathway_path, logger.validation_path,
                 logger.qa_path, logger.needs_path, logger.needs_snapshot_path],
            )
        _print_summary(run_id, all_artifacts, no_votes=True)
        return run_id
    else:
        logger.register_input("detail.xlsx", detail_path)
        logger.step_done("VALIDATE_VOTES")

    # ── Step 5: Load geometry ─────────────────────────────────────────────
    logger.step_start("LOAD_GEOMETRY", expected=["MPREC preferred; SRPREC fallback"])
    gdf, geo_level, geo_id_col = load_canonical_geometry(
        data_root / "CA" / "counties",  # boundary_loader expects county parent
        state,
        county,
        logger=logger,
    )

    if gdf is None or (isinstance(gdf, dict) and gdf.get("_stub")):
        logger.step_skip("LOAD_GEOMETRY", reason="No usable geometry (geopandas unavailable or files missing)")
        if isinstance(gdf, dict):
            logger.register_need("geopandas_library", "missing", ["geometry_load", "kepler_export"])
        gdf = None
        geo_level = geo_validation["canonical_geometry"]
    else:
        logger.set_coverage("geometry_features", len(gdf))
        logger.step_done("LOAD_GEOMETRY")

    # ── Step 6: Load crosswalks ───────────────────────────────────────────
    logger.step_start("LOAD_CROSSWALKS")
    county_geo_dir = data_root / "CA" / "counties" / county / "geography"
    crosswalks: dict = {}
    crosswalk_categories = {
        "MPREC_to_SRPREC":          county_geo_dir / "crosswalks",
        "RG_to_RR_to_SR_to_SVPREC": county_geo_dir / "crosswalks",
    }
    for cat_label, cat_dir in crosswalk_categories.items():
        xwalk, ok = load_crosswalk_from_category(county_geo_dir, "crosswalks", logger=logger)
        if ok:
            crosswalks[cat_label] = xwalk
            break  # use first available crosswalk

    if not crosswalks:
        logger.step_skip("LOAD_CROSSWALKS", reason="No crosswalk files; using identity mapping")
    else:
        logger.step_done("LOAD_CROSSWALKS", notes=[f"{len(crosswalks)} crosswalk(s) loaded"])

    # ── Step 7: Scaffold contest.json ─────────────────────────────────────
    if not (rebuild_maps_only or rebuild_memberships_only):
        logger.step_start("SCAFFOLD_CONTEST_JSON")
        contest_json_path = scaffold_contest_json(
            votes_root, year=year, state=state, county=county, contest_slug=contest_slug,
        )
        logger.step_done("SCAFFOLD_CONTEST_JSON", outputs=[contest_json_path])
        all_artifacts.append(contest_json_path)
    else:
        # Just grab the path for later commits
        contest_json_path = votes_root / year / state / county / contest_slug / "contest.json"
        logger.step_skip("SCAFFOLD_CONTEST_JSON", reason="Skipped due to targeted rebuild flag")

    # ── Step 8: Parse contest workbook ────────────────────────────────────
    logger.step_start("PARSE_CONTEST", expected=["Detect sheet types; aggregate vote methods"])
    parsed_sheets = parse_contest_workbook(
        detail_path,
        contest_json_path=contest_json_path,
        config=config,
        logger=logger,
    )
    logger.set_coverage("sheets_parsed", len(parsed_sheets))
    logger.step_done("PARSE_CONTEST")

    # ── Steps 9-12: Allocate → Sanity → Model → Export (per sheet) ───────
    logger.step_start("ALLOCATE_VOTES")
    all_model_dfs: list[pd.DataFrame] = []

    for parsed in parsed_sheets:
        sheet_name   = parsed["sheet_name"]
        contest_type = parsed["contest_type"]
        totals_df    = parsed["totals_df"]

        if totals_df.empty:
            logger.step_skip(f"SHEET/{sheet_name}", reason="No data rows")
            continue

        logger.info(f"  Sheet {sheet_name!r}: {len(totals_df)} precincts, type={contest_type}")

        # Allocation
        xwalk = next(iter(crosswalks.values()), None) if crosswalks else None
        if xwalk and membership_method != "area_weighted":
            allocated_df = allocate_votes_crosswalk(
                totals_df, xwalk, src_id_col="PrecinctID", tgt_id_col="MPREC_ID"
            )
            method_used = "crosswalk"
        else:
            allocated_df = area_weighted_fallback(totals_df, src_id_col="PrecinctID")
            method_used = "area_weighted_fallback"

        logger.info(f"    Allocation: {method_used}, {len(allocated_df)} target precincts")

        # Sanity checks
        logger.step_start(f"SANITY/{sheet_name}")
        passed, violations = run_sanity_checks(allocated_df, config, logger=logger)
        if not passed:
            logger.hard_fail(f"SANITY/{sheet_name}", "; ".join(violations))
        logger.step_done(f"SANITY/{sheet_name}")

        # Build model
        logger.step_start(f"BUILD_MODEL/{sheet_name}")
        id_col = "MPREC_ID" if "MPREC_ID" in allocated_df.columns else allocated_df.columns[0]
        model_df = build_precinct_model(
            allocated_df, canvas_id_col=id_col,
            geography_level=geo_level, gdf=gdf, geo_id_col=geo_id_col, config=config,
        )
        model_df["SheetName"]   = sheet_name
        model_df["ContestType"] = contest_type
        all_model_dfs.append(model_df)
        logger.set_coverage(f"rows_{sheet_name}", len(model_df))
        logger.step_done(f"BUILD_MODEL/{sheet_name}")

    logger.step_done("ALLOCATE_VOTES")

    if not all_model_dfs:
        logger.hard_fail("ALLOCATE_VOTES", "No model DataFrames produced")

    # ── Step 13: Export outputs ───────────────────────────────────────────
    logger.step_start("EXPORT_OUTPUTS")
    field_config = load_config("field_effects")
    min_score    = field_config.get("targeting", {}).get("universe_min_score", 0.30)

    for model_df in all_model_dfs:
        sname    = model_df["SheetName"].iloc[0]
        slug_out = f"{county}_{year}_{contest_slug}"
        if len(all_model_dfs) > 1:
            slug_out += f"__{sname}"

        csv_path = export_precinct_model(model_df, BASE_DIR, run_id, state, county, slug_out)
        all_artifacts.append(csv_path)
        logger.info(f"  Precinct model: {csv_path.name}")

        if not rebuild_maps_only:
            targeting_df = build_targeting_list(model_df, min_score=min_score)
            tgt_path = export_targeting_list(targeting_df, BASE_DIR, run_id, state, county, slug_out)
            all_artifacts.append(tgt_path)
            logger.info(f"  Targeting list: {tgt_path.name} ({len(targeting_df)} rows)")

        if not (rebuild_maps_only or rebuild_targets_only):
            agg_path = export_district_aggregates(model_df, BASE_DIR, run_id, state, county, slug_out)
            all_artifacts.append(agg_path)
            logger.info(f"  District aggregates: {agg_path.name}")

        if not rebuild_targets_only:
            kepler_path = export_kepler_geojson(model_df, BASE_DIR, run_id, state, county, slug_out, id_col=id_col)
            if kepler_path:
                all_artifacts.append(kepler_path)
                logger.info(f"  Kepler GeoJSON: {kepler_path.name}")
            else:
                logger.step_skip(f"KEPLER/{sname}", reason="No geometry (boundary files missing or geopandas unavailable)")
                logger.register_need("geometry_for_kepler", "blocked", ["kepler_geojson"],
                                      path=str(county_geo_dir / "precinct_shapes" / "MPREC_GeoJSON"))

    logger.step_done("EXPORT_OUTPUTS", outputs=all_artifacts)

    # ── Step 14: Finalize + commit ────────────────────────────────────────
    logger.finalize(state, county, contest_slug, run_status="success")

    # Clear staleness flags upon success
    cleared_domains = []
    if rebuild_memberships_only:
        cleared_domains = ["memberships", "precinct_models", "district_aggregates", "campaign_targets", "maps"]
    elif rebuild_targets_only:
        cleared_domains = ["campaign_targets"]
    elif rebuild_maps_only:
        cleared_domains = ["maps"]
    else:
        # full rebuild
        cleared_domains = ["memberships", "precinct_models", "district_aggregates", "campaign_targets", "maps"]
        
    clear_stale(context_key, cleared_domains)

    if commit:
        _git_commit(
            f"derived: run {run_id} -- {state}/{county}/{year}/{contest_slug}",
            all_artifacts + [contest_json_path],
        )
        _git_commit(
            f"reports: logs+needs for run {run_id}",
            [logger.log_path, logger.pathway_path, logger.validation_path,
             logger.qa_path, logger.needs_path, logger.needs_snapshot_path]
            + list(logger.latest_dir.iterdir()),
        )

    _print_summary(run_id, all_artifacts)
    return run_id


def _print_summary(run_id: str, artifacts: list, no_votes: bool = False):
    print(f"\n{'='*60}")
    print(f"  RUN_ID : {run_id}")
    if no_votes:
        print(f"  STATUS : partial (votes not yet provided)")
    else:
        print(f"  STATUS : success")
        print(f"  Artifacts: {len(artifacts)}")
    print(f"  Logs   : logs/latest/run.log")
    print(f"{'='*60}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Campaign In A Box v2 — Election Modeling Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--check-structure", action="store_true",
                        help="Verify directory tree and exit")
    parser.add_argument("--ingest-only", action="store_true",
                        help="Run ingestion from --staging-dir and exit")
    parser.add_argument("--state",         default="CA")
    parser.add_argument("--county",        default="Sonoma",
                        help="County name (e.g. Sonoma)")
    parser.add_argument("--year",          default="2024",
                        help="Election year (e.g. 2024)")
    parser.add_argument("--contest-slug",  dest="contest_slug", default="general",
                        help="Contest slug (e.g. nov2024_general)")
    parser.add_argument("--detail-path",   dest="detail_path", default=None,
                        help="Override path to detail.xlsx (relative to project root)")
    parser.add_argument("--staging-dir",   dest="staging_dir", default=None,
                        help="Path to STAGING_DIR (Campaign In A Box Data folder)")
    parser.add_argument("--membership-method", dest="membership_method",
                        choices=["crosswalk", "area_weighted", "auto"], default="auto")
    parser.add_argument("--log-level",     dest="log_level",
                        choices=["verbose", "summary"], default="verbose")
    parser.add_argument("--no-commit",     dest="commit", action="store_false")
    parser.add_argument("--rebuild-memberships", action="store_true", help="Rebuild memberships and all downstream")
    parser.add_argument("--rebuild-maps-only", action="store_true", help="Only rebuild maps")
    parser.add_argument("--rebuild-targets-only", action="store_true", help="Only rebuild campaign targets")
    parser.set_defaults(commit=True)

    args = parser.parse_args()

    if args.check_structure:
        sys.exit(0 if check_structure() else 1)

    if args.ingest_only:
        if not args.staging_dir:
            parser.error("--ingest-only requires --staging-dir")
        run_ingestion(staging_dir=args.staging_dir)
        sys.exit(0)

    try:
        run_pipeline(
            state=args.state,
            county=args.county,
            year=args.year,
            contest_slug=args.contest_slug,
            detail_path_override=args.detail_path,
            membership_method=args.membership_method,
            staging_dir=args.staging_dir,
            log_level=args.log_level,
            commit=args.commit,
            rebuild_memberships_only=args.rebuild_memberships,
            rebuild_maps_only=args.rebuild_maps_only,
            rebuild_targets_only=args.rebuild_targets_only,
        )
    except RuntimeError as e:
        print(f"\n[PIPELINE HARD FAIL] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[PIPELINE ERROR] {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
