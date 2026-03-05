"""
app/lib/output_browser.py

Discovers derived artifacts organized by county / contest / run_id.
"""
from __future__ import annotations
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DERIVED_ROOT = BASE_DIR / "derived"
LOGS_ROOT    = BASE_DIR / "logs"
REPORTS_ROOT = BASE_DIR / "reports"
NEEDS_ROOT   = BASE_DIR / "needs"


def discover_run_artifacts(county: str, state: str = "CA") -> list[dict]:
    """
    Scan derived/ for all county artifacts.
    Returns list of {contest_slug, run_id, type, path}.
    """
    results = []
    for subfolder_name, artifact_type in [
        ("precinct_models",    "precinct_model"),
        ("campaign_targets",   "targeting_list"),
        ("district_aggregates","district_aggregates"),
        ("maps",               "kepler_geojson"),
    ]:
        base = DERIVED_ROOT / subfolder_name / state / county
        if not base.is_dir():
            continue
        for contest_dir in sorted(base.iterdir()):
            if not contest_dir.is_dir():
                continue
            for f in sorted(contest_dir.glob("*")):
                if f.is_file() and f.suffix in (".csv", ".geojson") and f.name != ".gitkeep":
                    run_id = f.stem.rsplit("__", 1)[0] if "__" in f.stem else f.stem
                    results.append({
                        "contest_slug": contest_dir.name,
                        "run_id": run_id,
                        "type": artifact_type,
                        "path": f,
                        "name": f.name,
                        "size_bytes": f.stat().st_size,
                    })
    return results


def discover_log_artifacts() -> dict[str, Path]:
    """Return dict of name→path for logs/latest/ artifacts."""
    latest = LOGS_ROOT / "latest"
    known = ["run.log", "pathway.json", "validation.md", "qa.md",
             "needs.yaml", "RUN_ID.txt"]
    return {n: (latest / n) for n in known if (latest / n).exists()}


def discover_all_run_logs() -> list[dict]:
    """List every run log in logs/runs/."""
    runs_dir = LOGS_ROOT / "runs"
    if not runs_dir.is_dir():
        return []
    logs = []
    for f in sorted(runs_dir.glob("*__run.log"), reverse=True):
        run_id = f.stem.replace("__run", "")
        pathway = runs_dir / f"{run_id}__pathway.json"
        logs.append({
            "run_id": run_id,
            "log": f,
            "pathway": pathway if pathway.exists() else None,
            "mtime": f.stat().st_mtime,
        })
    return logs


def read_file_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"[Error reading {path}: {e}]"


def get_needs_summary() -> dict:
    """Parse needs.yaml into present/missing/blocked sections."""
    import yaml
    np = NEEDS_ROOT / "needs.yaml"
    if not np.exists():
        return {"raw": None}
    try:
        data = yaml.safe_load(np.read_text(encoding="utf-8")) or {}
        return data
    except Exception as e:
        return {"raw": f"Error: {e}"}
