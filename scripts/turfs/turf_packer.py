"""
scripts/turfs/turf_packer.py

Generates individual CSV and MD files for each turf.
"""

import pandas as pd
from pathlib import Path

def generate_turf_packs(
    plan_df: pd.DataFrame, 
    turfs_df: pd.DataFrame,
    out_dir: Path,
    run_id: str
):
    """
    For each turf in turfs_df, create a CSV of its precincts and a summary MD.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    
    for _, turf in turfs_df.iterrows():
        tid = turf["turf_id"]
        p_ids = turf["precinct_ids"].split(",")
        
        # 1. Filter plan data for this turf
        turf_precincts = plan_df[plan_df["canonical_precinct_id"].isin(p_ids)]
        
        # 2. Export CSV
        csv_path = out_dir / f"{run_id}__{tid}.csv"
        turf_precincts.to_csv(csv_path, index=False)
        
        # 3. Export MD Summary
        md_path = out_dir / f"{run_id}__{tid}_summary.md"
        
        md_content = f"""# Walk Turf Summary: {tid}
**Run ID:** {run_id}
**Precincts:** {turf['precinct_count']}
**Total Registered:** {int(turf['sum_registered']):,}
**Avg Target Score:** {turf['avg_target_score']:.2f}

## Strategic Instructions
- **Primary Goal:** {turf_precincts['universe_name'].mode().iloc[0] if not turf_precincts.empty else "General Outreach"}
- **Priority:** {'High' if turf['avg_target_score'] > 0.6 else 'Medium'}

## Precinct List
| Precinct ID | Registered | Support % | Turnout % | Target Score |
|---|---|---|---|---|
"""
        for _, p in turf_precincts.iterrows():
            md_content += f"| {p['canonical_precinct_id']} | {int(p['registered'])} | {p['support_pct']:.1%} | {p['turnout_pct']:.1%} | {p['target_score']:.2f} |\n"
            
        md_path.write_text(md_content)
