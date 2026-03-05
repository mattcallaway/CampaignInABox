"""
scripts/tools/export_audit_bundle.py — Post-Prompt-8.6 Audit Export

Gathers all diagnostic artifacts produced after Prompt 8.6 into one
deterministic bundle directory for external inspection.

Does NOT re-run modeling. Only copies/creates export files.

Usage:
    python scripts/tools/export_audit_bundle.py [--run-id <RUN_ID>]
"""
from __future__ import annotations

import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TS = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Step 1: Locate Latest Run ──────────────────────────────────────────────────
def detect_latest_run() -> dict:
    info = {"run_id": "unknown", "contest_id": "unknown", "state": "CA", "county": "Sonoma"}

    # Try needs.yaml meta
    needs_path = BASE_DIR / "needs" / "needs.yaml"
    if needs_path.exists() and yaml:
        needs = yaml.safe_load(needs_path.read_text(encoding="utf-8")) or {}
        info["run_id"] = needs.get("meta", {}).get("last_run_id", "unknown")

    # Try pathway.json for run context
    runs_dir = BASE_DIR / "logs" / "runs"
    if runs_dir.exists():
        pathways = sorted(runs_dir.glob("*pathway*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if pathways:
            try:
                pw = json.loads(pathways[0].read_text())
                info["run_id"]    = pathways[0].stem.split("__pathway")[0]
                info["state"]     = pw.get("state", info["state"])
                info["county"]    = pw.get("county", info["county"])
                info["contest_id"] = pw.get("contest_slug", info["contest_id"])
            except Exception:
                pass

    # Strategy meta fallback
    sp_root = BASE_DIR / "derived" / "strategy_packs"
    if sp_root.exists():
        metas = sorted(sp_root.rglob("STRATEGY_META.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if metas:
            try:
                meta = json.loads(metas[0].read_text())
                if info["contest_id"] == "unknown":
                    info["contest_id"] = meta.get("contest_id", "unknown")
                info["_latest_strategy_meta"] = str(metas[0])
            except Exception:
                pass

    return info


# ── Step 2: Create export directory ──────────────────────────────────────────
def create_bundle_dir(run_id: str) -> Path:
    bundle = BASE_DIR / "reports" / "export_audits" / f"{run_id}__prompt86_bundle" / "audit_bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "strategy_outputs").mkdir(exist_ok=True)
    return bundle


# ── Step 3-9: Copy files ──────────────────────────────────────────────────────
def _copy(src: Path | None, dest: Path, missing: list) -> bool:
    if src and src.exists():
        shutil.copy2(src, dest)
        return True
    missing.append(dest.name)
    return False


def _find_latest(root: Path, pattern: str) -> Path | None:
    if not root.exists():
        return None
    matches = sorted(root.rglob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    matches = [m for m in matches if m.is_file() and ".gitkeep" not in str(m)]
    return matches[0] if matches else None


def populate_bundle(bundle: Path, info: dict) -> tuple[list, list]:
    run_id = info["run_id"]
    copied = []
    missing = []

    def cp(src, dest_name, subdir=""):
        dest = bundle / subdir / dest_name if subdir else bundle / dest_name
        if _copy(src, dest, missing):
            copied.append(dest.name if not subdir else f"{subdir}/{dest_name}")

    audit_dir  = BASE_DIR / "reports" / "audit"
    qa_dir     = BASE_DIR / "reports" / "qa"
    val_dir    = BASE_DIR / "reports" / "validation"
    runs_dir   = BASE_DIR / "logs" / "runs"
    diag_dir   = BASE_DIR / "derived" / "diagnostics"
    needs_dir  = BASE_DIR / "needs"
    sp_root    = BASE_DIR / "derived" / "strategy_packs"
    pm_root    = BASE_DIR / "derived" / "precinct_models"
    uni_root   = BASE_DIR / "derived" / "universes"
    tgt_root   = BASE_DIR / "derived" / "campaign_targets"

    # Audit reports
    cp(_find_latest(audit_dir, "*post_prompt86*.json"), "post_prompt86_audit.json")
    cp(_find_latest(audit_dir, "*post_prompt86*.md"),   "post_prompt86_audit.md")
    cp(_find_latest(audit_dir, "*post_prompt85*.json"), "post_prompt85_audit.json")
    cp(_find_latest(audit_dir, "*post_prompt85*.md"),   "post_prompt85_audit.md")
    cp(_find_latest(audit_dir, "*.json"),               "audit_report.json")
    cp(_find_latest(audit_dir, "*.md"),                 "audit_report.md")

    # Strategy meta (latest)
    cp(Path(info["_latest_strategy_meta"]) if "_latest_strategy_meta" in info else None,
       "STRATEGY_META.json")

    # Integrity diagnostics
    cp(_find_latest(qa_dir,   "*integrity_repairs*.md"), "integrity_repairs.md")
    cp(_find_latest(diag_dir, "*integrity_repairs*.csv"), "integrity_repairs.csv")

    # Join guard
    cp(_find_latest(qa_dir,   "*join_guard*.md"), "join_guard.md")
    cp(_find_latest(diag_dir, "*join_guard*.csv"), "join_guard.csv")

    # Schema mapping
    cp(_find_latest(qa_dir,   "*schema_mapping*.md"), "schema_mapping.md")
    cp(_find_latest(diag_dir, "*schema_mapping*.json"), "schema_mapping.json")

    # Validation + QA
    cp(_find_latest(val_dir, f"*{run_id}*validation_report*.md"), "validation.md")
    cp(_find_latest(qa_dir,  f"*{run_id}*qa*.md"), "qa.md")
    if "validation.md" in missing:  # fallback to any validation
        cp(_find_latest(val_dir, "*validation_report*.md"), "validation.md")
    if "qa.md" in missing:
        cp(_find_latest(qa_dir, "*qa*.md"), "qa.md")

    # Pipeline artifacts
    run_log_candidates = sorted(runs_dir.glob(f"*{run_id}*run.log"), key=lambda p: p.stat().st_mtime, reverse=True) if runs_dir.exists() else []
    cp(run_log_candidates[0] if run_log_candidates else None, "run.log")

    pw_candidates = sorted(runs_dir.glob(f"*{run_id}*pathway*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if runs_dir.exists() else []
    cp(pw_candidates[0] if pw_candidates else None, "pathway.json")

    # NEEDS
    cp(needs_dir / "needs.yaml", "needs.yaml")
    cp(_find_latest(needs_dir / "history", f"*{run_id}*needs_snapshot*.yaml"), "needs_snapshot.yaml")
    if "needs_snapshot.yaml" in missing:  # latest fallback
        cp(_find_latest(needs_dir / "history", "*needs_snapshot*.yaml"), "needs_snapshot.yaml")

    # Model diagnostics
    cp(_find_latest(pm_root,  "*.csv"), "precinct_model.csv")
    cp(_find_latest(uni_root, "*precinct_universes*.csv"), "precinct_universes.csv")
    cp(_find_latest(tgt_root, "*targeting_list*.csv"), "targeting_list.csv")

    # Strategy pack outputs
    strategy_files = ["STRATEGY_SUMMARY.md", "TOP_TARGETS.csv", "TOP_TURFS.csv",
                      "FIELD_PLAN.csv", "SIMULATION_RESULTS.csv", "FIELD_PACE.csv", "FIELD_PACE.csv"]
    sp_meta_path = Path(info.get("_latest_strategy_meta", "")) if info.get("_latest_strategy_meta") else None
    sp_dir = sp_meta_path.parent if sp_meta_path and sp_meta_path.exists() else None
    for sf in set(strategy_files):
        src = sp_dir / sf if sp_dir else None
        cp(src, sf, subdir="strategy_outputs")

    return copied, missing


# ── Step 6: Geo status ────────────────────────────────────────────────────────
def write_geo_status(bundle: Path) -> None:
    try:
        import geopandas
        geopandas_ok = True
    except ImportError:
        geopandas_ok = False

    geo_root = BASE_DIR / "data" / "CA" / "counties" / "Sonoma" / "geography" / "precinct_shapes"
    mprec_ok = bool(_find_latest(geo_root / "MPREC_GeoJSON", "*.geojson"))
    srprec_ok = bool(_find_latest(geo_root / "SRPREC_GeoJSON", "*.geojson"))

    parsed = 0
    if geopandas_ok and mprec_ok:
        try:
            import geopandas as gpd
            p = _find_latest(geo_root / "MPREC_GeoJSON", "*.geojson")
            parsed = len(gpd.read_file(p)) if p else 0
        except Exception:
            pass

    status = {
        "geopandas_installed":          geopandas_ok,
        "mprec_geojson_found":          mprec_ok,
        "srprec_geojson_found":         srprec_ok,
        "geometry_parsed":              parsed > 0,
        "precinct_count_from_geometry": parsed,
    }
    (bundle / "geo_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")


# ── Step 7: Repo metrics ─────────────────────────────────────────────────────
def write_repo_metrics(bundle: Path) -> None:
    def count(root, pat):
        return len([f for f in root.rglob(pat) if f.is_file() and ".git" not in str(f)]) if root.exists() else 0

    sized = sorted(
        [(f, f.stat().st_size) for f in BASE_DIR.rglob("*")
         if f.is_file() and ".git" not in str(f) and "node_modules" not in str(f)],
        key=lambda x: x[1], reverse=True
    )[:5]

    metrics = {
        "total_files":     count(BASE_DIR, "*"),
        "python_files":    count(BASE_DIR / "scripts", "*.py"),
        "geo_files":       count(BASE_DIR, "*.geojson") + count(BASE_DIR, "*.gpkg"),
        "vote_files":      count(BASE_DIR / "votes", "detail.xlsx"),
        "derived_outputs": count(BASE_DIR / "derived", "*.csv"),
        "strategy_packs":  count(BASE_DIR / "derived" / "strategy_packs", "*"),
        "largest_files":   [{"path": str(f.relative_to(BASE_DIR)), "bytes": s} for f, s in sized],
    }
    (bundle / "repo_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")


# ── Step 8: Manifest ─────────────────────────────────────────────────────────
def write_manifest(bundle: Path, info: dict, copied: list, missing: list) -> None:
    files_in_bundle = sorted(
        [str(f.relative_to(bundle)) for f in bundle.rglob("*") if f.is_file()]
    )
    total_size = sum(f.stat().st_size for f in bundle.rglob("*") if f.is_file())

    md = [
        "# Prompt 8.6 Audit Export Bundle",
        f"**RUN_ID:** `{info['run_id']}`",
        f"**Contest:** `{info['contest_id']}`  **State:** {info['state']}  **County:** {info['county']}",
        f"**Exported:** {TS}",
        f"**Total size:** {total_size:,} bytes",
        "",
        "## Files Included",
        *[f"- {f}" for f in files_in_bundle],
        "",
    ]
    if missing:
        md += [
            "## ⚠️ Missing Artifacts",
            *[f"- {m}" for m in missing],
        ]
    else:
        md.append("## ✅ All expected artifacts found")

    (bundle / "EXPORT_MANIFEST.md").write_text("\n".join(md), encoding="utf-8")


# ── Main ─────────────────────────────────────────────────────────────────────
def main(run_id_override: str | None = None) -> None:
    info = detect_latest_run()
    if run_id_override:
        info["run_id"] = run_id_override

    run_id = info["run_id"]
    bundle = create_bundle_dir(run_id)

    print(f"Bundle: {bundle}")
    print(f"Run ID: {run_id}  | Contest: {info['contest_id']}")

    copied, missing = populate_bundle(bundle, info)
    write_geo_status(bundle)
    write_repo_metrics(bundle)

    total_files = sum(1 for f in bundle.rglob("*") if f.is_file())
    total_size  = sum(f.stat().st_size for f in bundle.rglob("*") if f.is_file())

    write_manifest(bundle, info, copied, missing)

    print()
    print("=" * 60)
    print("EXPORT AUDIT COMPLETE")
    print(f"Bundle path: {bundle.parent}")
    print(f"Total files exported: {total_files}")
    print(f"Total size:           {total_size:,} bytes ({total_size/1024:.1f} KB)")
    if missing:
        print(f"Missing artifacts: {missing}")
    else:
        print("All expected artifacts found.")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post-Prompt-8.6 Audit Export")
    parser.add_argument("--run-id", default=None, help="Override run_id detection")
    args = parser.parse_args()
    main(run_id_override=args.run_id)
