"""
scripts/validation/geography_validator.py

Validates that required geography and crosswalk files are present
for a given county before the modeling pipeline runs.

Returns structured validation result with NEEDS entries for anything missing.
"""

from __future__ import annotations

from pathlib import Path


# ── Known category labels and where they live ─────────────────────────────

REQUIRED_GEOMETRY_LABELS = [
    "MPREC GeoJSON", "MPREC GeoPackage", "MPREC Shapefile",
    "SRPREC GeoJSON", "SRPREC GeoPackage", "SRPREC Shapefile",
]

REQUIRED_CROSSWALK_LABELS = [
    "2020 BLK TO MPREC",
    "RGPREC TO 2020 BLK",
    "SRPREC TO 2020 BLK",
    "RG to RR to SR to SVPREC",
    "MPREC to SRPREC",
    "SRPREC to CITY",
]

GEOGRAPHY_LABEL_TO_FOLDER = {
    "MPREC GeoJSON":         "precinct_shapes/MPREC_GeoJSON",
    "MPREC GeoPackage":      "precinct_shapes/MPREC_GeoPackage",
    "MPREC Shapefile":       "precinct_shapes/MPREC_Shapefile",
    "SRPREC GeoJSON":        "precinct_shapes/SRPREC_GeoJSON",
    "SRPREC GeoPackage":     "precinct_shapes/SRPREC_GeoPackage",
    "SRPREC Shapefile":      "precinct_shapes/SRPREC_Shapefile",
    "2020 BLK TO MPREC":     "crosswalks",
    "RGPREC TO 2020 BLK":    "crosswalks",
    "SRPREC TO 2020 BLK":    "crosswalks",
    "RG to RR to SR to SVPREC": "crosswalks",
    "MPREC to SRPREC":       "crosswalks",
    "SRPREC to CITY":        "crosswalks",
}

GEO_EXTENSIONS = {".geojson", ".gpkg", ".shp"}
CROSSWALK_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls"}


def _folder_has_data(folder: Path, extensions: set[str]) -> bool:
    """Return True if folder exists and contains at least one file with a valid extension."""
    if not folder.is_dir():
        return False
    return any(
        f.suffix.lower() in extensions
        for f in folder.iterdir()
        if f.is_file() and f.name != ".gitkeep"
    )


def validate_county_geography(
    data_root: str | Path,
    county: str,
    log=None,
) -> dict:
    """
    Validate that required geography and crosswalk files are present.

    Returns {
        "valid": bool,
        "canonical_geometry": "MPREC" | "SRPREC" | "NONE",
        "present": [list of labels],
        "missing": [list of labels],
        "needs_entries": [list of needs dicts],
        "blocked_steps": [list of step names]
    }
    """
    data_root = Path(data_root)
    geo_dir = data_root / "CA" / "counties" / county / "geography"

    def _log(msg, level="INFO"):
        if log:
            getattr(log, level.lower(), log.info)(msg)

    present_labels: list[str] = []
    missing_labels: list[str] = []
    needs_entries: list[dict] = []
    blocked_steps: list[str] = []

    all_labels = REQUIRED_GEOMETRY_LABELS + REQUIRED_CROSSWALK_LABELS

    for label in all_labels:
        folder_rel = GEOGRAPHY_LABEL_TO_FOLDER.get(label, "")
        folder = geo_dir / folder_rel if folder_rel else geo_dir
        exts = GEO_EXTENSIONS if label in REQUIRED_GEOMETRY_LABELS else CROSSWALK_EXTENSIONS

        has_data = _folder_has_data(folder, exts)
        if has_data:
            present_labels.append(label)
            _log(f"  [present] {label}")
        else:
            missing_labels.append(label)
            _log(f"  [missing] {label} -- expected at: {folder}", "WARN")

            # Determine what this blocks
            blocks = []
            if label in {"MPREC GeoJSON", "MPREC GeoPackage", "MPREC Shapefile",
                          "SRPREC GeoJSON", "SRPREC GeoPackage", "SRPREC Shapefile"}:
                blocks = ["geometry_load", "kepler_export", "precinct_model"]
            elif label in {"MPREC to SRPREC", "RG to RR to SR to SVPREC"}:
                blocks = ["crosswalk_allocation"]
            else:
                blocks = [f"crosswalk_{label.replace(' ', '_')}"]

            needs_entries.append({
                "category": label,
                "status": "missing",
                "blocks": blocks,
                "expected_path": str(folder),
            })
            blocked_steps.extend(b for b in blocks if b not in blocked_steps)

    # Determine canonical geometry
    mprec_present = any(
        lbl in present_labels
        for lbl in {"MPREC GeoJSON", "MPREC GeoPackage", "MPREC Shapefile"}
    )
    srprec_present = any(
        lbl in present_labels
        for lbl in {"SRPREC GeoJSON", "SRPREC GeoPackage", "SRPREC Shapefile"}
    )
    canonical_geo = "MPREC" if mprec_present else ("SRPREC" if srprec_present else "NONE")

    valid = len(missing_labels) == 0
    _log(
        f"Geography validation: {len(present_labels)}/{len(all_labels)} present, "
        f"canonical={canonical_geo}"
    )

    return {
        "valid": valid,
        "canonical_geometry": canonical_geo,
        "present": present_labels,
        "missing": missing_labels,
        "needs_entries": needs_entries,
        "blocked_steps": blocked_steps,
    }


def validate_votes_present(
    votes_root: str | Path,
    year: str | int,
    county: str,
    contest_slug: str,
    log=None,
) -> dict:
    """
    Validate that a detail.xlsx (or .xls) exists for the given contest.
    Returns {valid, path, blocked_steps}.
    """
    votes_root = Path(votes_root)
    contest_dir = votes_root / str(year) / "CA" / county / contest_slug

    def _log(msg, level="INFO"):
        if log:
            getattr(log, level.lower(), log.info)(msg)

    for ext in (".xlsx", ".xls"):
        candidate = contest_dir / f"detail{ext}"
        if candidate.exists():
            _log(f"  [present] votes: {candidate}")
            return {"valid": True, "path": candidate, "blocked_steps": []}

    _log(f"  [missing] votes: no detail.xlsx/xls in {contest_dir}", "WARN")
    return {
        "valid": False,
        "path": None,
        "blocked_steps": ["parse_contest", "allocate_votes", "export_model"],
        "needs_entry": {
            "category": "detail.xlsx",
            "status": "missing",
            "blocks": ["parse_contest", "allocate_votes", "export_model"],
            "expected_path": str(contest_dir / "detail.xlsx"),
        },
    }
