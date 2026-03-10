"""
engine/war_room/runtime_loader.py — Prompt 14

Loads live campaign runtime data from:
  data/campaign_runtime/CA/<county>/<contest_id>/

Provides get_runtime_summary() → dict describing what's loaded vs missing.
All runtime files are gitignored. No voter-level data is ever stored here.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
log = logging.getLogger(__name__)


def _runtime_dir(campaign_config: Optional[dict] = None) -> Path:
    """Resolve the runtime data directory from campaign config."""
    cfg = campaign_config or {}
    state  = "CA"
    jurisdiction = cfg.get("campaign", {}).get("jurisdiction", "Sonoma County, CA")
    county = (jurisdiction.replace(", CA", "").replace(" County", "")
              .strip().replace(" ", "_"))
    contest_name = cfg.get("campaign", {}).get("contest_name", "campaign")
    slug = contest_name.lower().replace(" ", "_").replace(".", "")[:24]
    return BASE_DIR / "data" / "campaign_runtime" / state / county / slug


def _load_csv(path: Path) -> Optional[pd.DataFrame]:
    try:
        if path.exists():
            df = pd.read_csv(path, encoding="utf-8")
            if not df.empty:
                return df
    except Exception as e:
        log.warning(f"[RUNTIME] Could not load {path.name}: {e}")
    return None


def load_field_results(campaign_config: Optional[dict] = None) -> Optional[pd.DataFrame]:
    """Load field_results.csv. Columns: date, turf_id, doors_knocked, contacts_made,
    canvasser_count, persuasion_contacts, gotv_contacts."""
    return _load_csv(_runtime_dir(campaign_config) / "field_results.csv")


def load_volunteer_log(campaign_config: Optional[dict] = None) -> Optional[pd.DataFrame]:
    """Load volunteer_log.csv. Columns: date, volunteer_count, shifts_completed, hours_worked."""
    return _load_csv(_runtime_dir(campaign_config) / "volunteer_log.csv")


def load_budget_actuals(campaign_config: Optional[dict] = None) -> Optional[pd.DataFrame]:
    """Load budget_actuals.csv. Columns: date, category, planned_spend, actual_spend, notes."""
    return _load_csv(_runtime_dir(campaign_config) / "budget_actuals.csv")


def load_contact_results(campaign_config: Optional[dict] = None) -> Optional[pd.DataFrame]:
    """Load contact_results.csv. Columns: date, region, contacts, supporters_count,
    persuadables_count, opposition_count, follow_up_needed."""
    return _load_csv(_runtime_dir(campaign_config) / "contact_results.csv")


def get_runtime_summary(campaign_config: Optional[dict] = None) -> dict:
    """
    Returns a dict describing what runtime data is available.

    Keys:
      runtime_dir: Path
      field_results: DataFrame or None
      volunteer_log: DataFrame or None
      budget_actuals: DataFrame or None
      contact_results: DataFrame or None
      has_any: bool
      presence: dict[str, bool]
      metrics: dict of computed aggregates
    """
    field    = load_field_results(campaign_config)
    vols     = load_volunteer_log(campaign_config)
    budget   = load_budget_actuals(campaign_config)
    contacts = load_contact_results(campaign_config)

    presence = {
        "field_results":   field    is not None,
        "volunteer_log":   vols     is not None,
        "budget_actuals":  budget   is not None,
        "contact_results": contacts is not None,
    }

    # ── Computed aggregates ──────────────────────────────────────────────────
    metrics = {}

    if field is not None:
        doors_col    = next((c for c in ["doors_knocked", "doors"] if c in field.columns), None)
        contacts_col = next((c for c in ["contacts_made", "contacts"] if c in field.columns), None)
        pers_col     = next((c for c in ["persuasion_contacts", "persuasion"] if c in field.columns), None)
        gotv_col     = next((c for c in ["gotv_contacts", "gotv"] if c in field.columns), None)

        if doors_col:
            total_doors = int(pd.to_numeric(field[doors_col], errors="coerce").sum())
            metrics["total_doors_knocked"] = total_doors
        if contacts_col:
            total_contacts = int(pd.to_numeric(field[contacts_col], errors="coerce").sum())
            metrics["total_contacts_made"] = total_contacts
            if doors_col and total_doors > 0:
                metrics["observed_contact_rate"] = round(total_contacts / total_doors, 4)
        if pers_col and contacts_col and "total_contacts_made" in metrics:
            total_pers = int(pd.to_numeric(field[pers_col], errors="coerce").sum())
            metrics["total_persuasion_contacts"] = total_pers
            tc = metrics["total_contacts_made"]
            if tc > 0:
                metrics["observed_persuasion_rate"] = round(total_pers / tc, 4)
        if gotv_col:
            metrics["total_gotv_contacts"] = int(pd.to_numeric(field[gotv_col], errors="coerce").sum())

        # Weekly avg doors (last 4 weeks)
        if "date" in field.columns and doors_col:
            try:
                field["_date"] = pd.to_datetime(field["date"], errors="coerce")
                cutoff = field["_date"].max() - pd.Timedelta(weeks=4)
                recent = field[field["_date"] >= cutoff]
                weeks = max((field["_date"].max() - cutoff).days / 7, 1)
                metrics["weekly_avg_doors_last4w"] = round(
                    pd.to_numeric(recent[doors_col], errors="coerce").sum() / weeks, 0
                )
            except Exception:
                pass

    if vols is not None:
        for col, key in [("volunteer_count", "total_volunteers_logged"),
                         ("shifts_completed", "total_shifts"),
                         ("hours_worked", "total_hours")]:
            if col in vols.columns:
                metrics[key] = int(pd.to_numeric(vols[col], errors="coerce").sum())
        if "volunteer_count" in vols.columns:
            metrics["avg_volunteers_per_week"] = round(
                pd.to_numeric(vols["volunteer_count"], errors="coerce").mean(), 1
            )

    if budget is not None:
        if "actual_spend" in budget.columns:
            metrics["total_actual_spend"] = float(pd.to_numeric(budget["actual_spend"], errors="coerce").sum())
        if "planned_spend" in budget.columns:
            metrics["total_planned_spend"] = float(pd.to_numeric(budget["planned_spend"], errors="coerce").sum())

    if contacts is not None:
        for col, key in [("contacts", "contact_results_total"),
                         ("supporters_count", "supporters_identified"),
                         ("persuadables_count", "persuadables_identified"),
                         ("opposition_count", "opposition_identified")]:
            if col in contacts.columns:
                metrics[key] = int(pd.to_numeric(contacts[col], errors="coerce").sum())

    return {
        "runtime_dir": _runtime_dir(campaign_config),
        "field_results":   field,
        "volunteer_log":   vols,
        "budget_actuals":  budget,
        "contact_results": contacts,
        "has_any":  any(presence.values()),
        "presence": presence,
        "metrics":  metrics,
    }


def save_runtime_data(
    data: pd.DataFrame,
    data_type: str,
    campaign_config: Optional[dict] = None,
    append: bool = True,
) -> Path:
    """
    Save runtime data to the appropriate CSV file.

    data_type: 'field_results' | 'volunteer_log' | 'budget_actuals' | 'contact_results'
    append: if True, append to existing rows; if False, overwrite.
    """
    runtime_dir = _runtime_dir(campaign_config)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    out = runtime_dir / f"{data_type}.csv"

    if append and out.exists():
        existing = pd.read_csv(out, encoding="utf-8")
        combined = pd.concat([existing, data], ignore_index=True)
        combined.to_csv(out, index=False, encoding="utf-8")
    else:
        data.to_csv(out, index=False, encoding="utf-8")

    log.info(f"[RUNTIME] Saved {len(data)} rows to {out}")
    return out
