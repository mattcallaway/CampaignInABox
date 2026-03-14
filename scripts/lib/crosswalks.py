"""
scripts/lib/crosswalks.py

Crosswalk discovery and validation for Campaign In A Box.
Finds geographic crosswalk files for a given state/county pair.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Canonical crosswalk names and what they enable
CROSSWALK_REGISTRY = {
    "SRPREC_TO_2020_BLK": {
        "description": "SRPREC → 2020 Census Block mapping",
        "blocks": ["block_weighted_allocation"],
        "required_cols": ["srprec", "block"],   # actual: c097_g24_sr_blk_map.csv
        "alt_patterns": ["*sr_blk_map*", "*SRPREC*BLK*", "*srprec*blk*", "*srprec*block*"],
    },
    "RGPREC_TO_2020_BLK": {
        "description": "RGPREC → 2020 Census Block mapping",
        "blocks": ["rgprec_weighted_allocation"],
        "required_cols": ["rgprec", "block"],   # actual: c097_g24_rg_blk_map.csv
        "alt_patterns": ["*rg_blk_map*", "*RGPREC*BLK*", "*rgprec*blk*"],
    },
    "2020_BLK_TO_MPREC": {
        "description": "2020 Census Block → MPREC mapping",
        "blocks": ["block_to_mprec_join"],
        "required_cols": ["block", "mprec"],    # actual: blk_mprec_097_g24_v01.csv
        "alt_patterns": ["*blk_mprec*", "*BLK*MPREC*", "*block*mprec*"],
    },
    "MPREC_to_SRPREC": {
        "description": "MPREC → SRPREC reverse mapping",
        "blocks": ["mprec_to_srprec_join"],
        "required_cols": ["mprec", "srprec"],   # actual: mprec_srprec_097_g24.csv
        "alt_patterns": ["*mprec_srprec*", "*MPREC*SRPREC*", "*mprec*srprec*"],
    },
    "SRPREC_to_CITY": {
        "description": "SRPREC → City/Jurisdiction mapping",
        "blocks": ["city_aggregation"],
        "required_cols": ["srprec", "city"],    # actual: c097_g24_srprec_to_city.csv
        "alt_patterns": ["*srprec_to_city*", "*SRPREC*CITY*", "*srprec*city*", "*city*srprec*", "*cities_by*"],
    },
    "RG_to_RR_to_SR_to_SVPREC": {
        "description": "RG → RR → SR → SVPREC chain mapping",
        "blocks": ["rg_to_svprec_join"],
        "required_cols": ["rgprec", "svprec"],  # actual: c097_rg_rr_sr_svprec_g24.csv
        "alt_patterns": ["*rg_rr_sr_svprec*", "*RG*SR*SVPREC*", "*rg*to*svprec*", "*rgprec*svprec*"],
    },
}


def discover_crosswalks(
    project_root: Path,
    state: str,
    county_fips_or_name: str,
) -> dict[str, dict]:
    """
    Search for crosswalk files across known locations.
    Returns dict of crosswalk_name -> {status, path, row_count, ...}
    """
    results = {}
    search_roots = [
        project_root / "data" / state,
        project_root / "data" / state / "counties",
        project_root / "data" / state / "crosswalks",
        project_root / "data",
        project_root / "config",
    ]
    # Also try county-specific paths
    county_clean = county_fips_or_name.replace(" ", "_")
    for root in list(search_roots):
        search_roots.append(root / county_clean)
        search_roots.append(root / county_fips_or_name)

    for name, spec in CROSSWALK_REGISTRY.items():
        entry: dict = {
            "name": name,
            "description": spec["description"],
            "blocks": spec["blocks"],
            "status": "missing",
            "path": None,
            "row_count": 0,
            "unique_keys": 0,
            "pct_null_keys": None,
            "missing_required_cols": [],
        }

        found_path = _search(search_roots, [f"*{name}*"] + spec["alt_patterns"])
        if found_path:
            entry["status"] = "found"
            entry["path"] = str(found_path.relative_to(project_root))
            # Validate
            report = validate_crosswalk(found_path, spec["required_cols"], name)
            entry.update(report)
        else:
            # Check config/cities_by_county_ca.json as fallback for SRPREC_to_CITY
            if name == "SRPREC_to_CITY":
                fallback = project_root / "config" / "cities_by_county_ca.json"
                if fallback.exists():
                    entry["status"] = "fallback"
                    entry["path"] = "config/cities_by_county_ca.json"
                    entry["fallback_note"] = "City names available via cities_by_county_ca.json"

        results[name] = entry

    return results


def validate_crosswalk(
    path: Path,
    required_cols: list[str],
    name: str,
) -> dict:
    """
    Validate a crosswalk file.
    Returns partial dict to merge into the crosswalk entry.
    """
    report: dict = {}
    try:
        import pandas as pd
        if path.suffix.lower() in (".csv", ".txt"):
            df = pd.read_csv(path, nrows=100_000)
        elif path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(path, nrows=100_000)
        elif path.suffix.lower() == ".json":
            import json
            data = json.loads(path.read_text())
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                df = pd.DataFrame([{"key": k, "value": v} for k, v in data.items()])
            else:
                df = pd.DataFrame()
        else:
            report["status"] = "found_unreadable"
            return report

        report["row_count"] = len(df)
        # Required cols (case-insensitive match)
        lower_cols = {c.lower(): c for c in df.columns}
        missing_req = []
        for req in required_cols:
            if req.lower() not in lower_cols and req not in df.columns:
                missing_req.append(req)
        report["missing_required_cols"] = missing_req

        # Key null check (first required col)
        if required_cols and required_cols[0].lower() in lower_cols:
            key_col = lower_cols[required_cols[0].lower()]
            n_null = df[key_col].isna().sum()
            report["pct_null_keys"] = round(n_null / max(len(df), 1), 4)
            report["unique_keys"]   = int(df[key_col].nunique())

    except Exception as e:
        report["status"] = "found_unreadable"
        report["read_error"] = str(e)

    return report


def write_crosswalk_validation(
    crosswalk_results: dict,
    contest_id: str,
    run_id: str,
    project_root: Path,
) -> dict[str, Path]:
    """Write crosswalk validation outputs."""
    import pandas as pd

    diag_dir    = project_root / "derived" / "diagnostics"
    reports_dir = project_root / "reports" / "validation"
    diag_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    # ── CSV ───────────────────────────────────────────────────────────────────
    rows = []
    for name, entry in crosswalk_results.items():
        rows.append({
            "crosswalk":   name,
            "description": entry.get("description", ""),
            "status":      entry.get("status", "missing"),
            "path":        entry.get("path", ""),
            "row_count":   entry.get("row_count", 0),
            "unique_keys": entry.get("unique_keys", 0),
            "pct_null":    entry.get("pct_null_keys", ""),
            "missing_cols":"; ".join(entry.get("missing_required_cols", [])),
            "blocks":      "; ".join(entry.get("blocks", [])),
        })
    csv_path = diag_dir / f"{contest_id}__crosswalk_status.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    paths["crosswalk_status_csv"] = csv_path

    # ── Markdown ──────────────────────────────────────────────────────────────
    def sym(s):
        return {"found": "✅", "fallback": "⚠️", "missing": "❌", "found_unreadable": "⚠️"}.get(s, "?")

    md_lines = [
        f"# Crosswalk Validation Report",
        f"**Contest:** `{contest_id}`   **Run:** `{run_id}`",
        f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "| Crosswalk | Status | Rows | Blocks (if missing) |",
        "|---|---|---|---|",
    ]
    for name, e in crosswalk_results.items():
        md_lines.append(
            f"| `{name}` | {sym(e['status'])} {e['status']} "
            f"| {e.get('row_count', '—')} "
            f"| {', '.join(e.get('blocks', [])) if e['status'] == 'missing' else '—'} |"
        )
    md_lines += ["", "_Output: `derived/diagnostics/`_"]
    md_path = reports_dir / f"{run_id}__crosswalk_validation.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    paths["crosswalk_validation_md"] = md_path

    return paths


def update_needs_crosswalks(
    crosswalk_results: dict,
    project_root: Path,
) -> None:
    """Update needs.yaml with crosswalk status."""
    try:
        import yaml
        needs_path = project_root / "needs" / "needs.yaml"
        needs_path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict = {}
        if needs_path.exists():
            existing = yaml.safe_load(needs_path.read_text()) or {}
        cw_entry = {}
        for name, e in crosswalk_results.items():
            cw_entry[name] = {
                "status": e.get("status", "missing"),
                "blocks": e.get("blocks", []),
            }
        existing["crosswalks"] = cw_entry
        needs_path.write_text(yaml.dump(existing, default_flow_style=False), encoding="utf-8")
    except Exception:
        pass


def _search(roots: list[Path], patterns: list[str]) -> Optional[Path]:
    """Search multiple roots for the first match of any pattern."""
    for root in roots:
        if not root.exists():
            continue
        for pattern in patterns:
            matches = sorted(root.rglob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            matches = [m for m in matches if m.is_file() and ".gitkeep" not in str(m)]
            if matches:
                return matches[0]
    return None
