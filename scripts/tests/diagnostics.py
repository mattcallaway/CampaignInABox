"""
scripts/tests/diagnostics.py

QA and Anomaly detection for Campaign In A Box v2.
Produces anomaly tables and model diagnostic reports.
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Bootstrap
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.lib.schema import canonicalize_df

def run_diagnostics(df: pd.DataFrame, contest_id: str, logger=None) -> pd.DataFrame:
    """
    Checks for logical inconsistencies and outliers.
    """
    df = canonicalize_df(df.copy())
    anomalies = []
    
    # 1. Turnout sanity
    if "turnout_pct" in df.columns:
        # Pct > 1.0 (or 100%)
        high_to = df[df["turnout_pct"] > 1.05]
        for _, row in high_to.iterrows():
            anomalies.append({
                "precinct_id": row["canonical_precinct_id"],
                "type": "IMPOSSIBLE_TURNOUT",
                "detail": f"TurnoutPct={row['turnout_pct']}",
                "severity": "CRITICAL"
            })
            
    # 2. Vote sanity
    if "ballots_cast" in df.columns and "registered" in df.columns:
        over_vote = df[df["ballots_cast"] > df["registered"] + 5] # Allow tiny margin for reporting errors
        for _, row in over_vote.iterrows():
             anomalies.append({
                "precinct_id": row["canonical_precinct_id"],
                "type": "OVERVOTE",
                "detail": f"Ballots({row['ballots_cast']}) > Reg({row['registered']})",
                "severity": "HIGH"
            })
            
    # 3. Missing Joins
    if "target_score" in df.columns:
        null_scores = df[df["target_score"].isnull()]
        for _, row in null_scores.iterrows():
            anomalies.append({
                "precinct_id": row["canonical_precinct_id"],
                "type": "MODEL_FAILURE",
                "detail": "TargetScore is NULL",
                "severity": "HIGH"
            })

    # 4. Data Type check
    # Check if precinct IDs look like floats (common error)
    if not df["canonical_precinct_id"].empty:
        sample = str(df["canonical_precinct_id"].iloc[0])
        if ".0" in sample:
            anomalies.append({
                "precinct_id": "GLOBAL",
                "type": "DATA_TYPE_ERROR",
                "detail": "Precinct IDs contain float decimals",
                "severity": "MEDIUM"
            })

    return pd.DataFrame(anomalies)

def run_ops_diagnostics(plan_df: pd.DataFrame, turfs_df: pd.DataFrame, logger=None) -> pd.DataFrame:
    """
    Checks for campaign operations inconsistencies.
    """
    anomalies = []
    
    # 1. Turf constraint checks
    if not turfs_df.empty:
        # Check sum_registered vs capacity/min
        min_reg = 100 # from field_ops.yaml default
        low_reg = turfs_df[turfs_df["sum_registered"] < min_reg]
        for _, row in low_reg.iterrows():
            anomalies.append({
                "precinct_id": row["turf_id"],
                "type": "LOW_REGISTRATION_TURF",
                "detail": f"Registered({row['sum_registered']}) < {min_reg}",
                "severity": "MEDIUM"
            })

    # 2. Scenario Math sanity
    if "expected_net_gain" in plan_df.columns:
        # Gain should be positive usually, but let's check for extreme outliers
        high_gain = plan_df[plan_df["expected_net_gain"] > plan_df["registered"] * 0.5]
        for _, row in high_gain.iterrows():
            anomalies.append({
                "precinct_id": row["canonical_precinct_id"],
                "type": "EXTREME_NET_GAIN",
                "detail": f"Gain({row['expected_net_gain']:.1f}) is > 50% of Registered",
                "severity": "HIGH"
            })
            
    # 3. Ballots <= Registered (Total projected)
    # This is handled in simulation_engine usually, but we check here too
    if "projected_support_votes" in plan_df.columns:
        err = plan_df[plan_df["projected_support_votes"] > plan_df["registered"]]
        for _, row in err.iterrows():
            anomalies.append({
                "precinct_id": row["canonical_precinct_id"],
                "type": "PROJECTED_VOTES_OVER_REG",
                "detail": f"ProjVotes({row['projected_support_votes']}) > Reg({row['registered']})",
                "severity": "CRITICAL"
            })

    return pd.DataFrame(anomalies)

def generate_diagnostic_summary(anomalies_df: pd.DataFrame, pipeline_meta: dict) -> str:
    """
    Builds a markdown report for humans.
    """
    total = len(anomalies_df)
    critical = len(anomalies_df[anomalies_df["severity"] == "CRITICAL"])
    
    report = f"# Model Diagnostics & QA\n\n"
    report += f"**Contest:** {pipeline_meta.get('contest_slug', 'N/A')}\n"
    report += f"**Anomalies Found:** {total} ({critical} critical)\n\n"
    
    if total == 0:
        report += "✅ **No anomalies detected.** Model outputs are logically sound.\n"
    else:
        report += "## Anomaly Details\n\n"
        report += anomalies_df.to_markdown(index=False)
        report += "\n\n"
        if critical > 0:
            report += "> [!CAUTION]\n"
            report += "> CRITICAL anomalies found. Verify input data registration counts and vote totals.\n"
            
    return report

if __name__ == "__main__":
    pass
