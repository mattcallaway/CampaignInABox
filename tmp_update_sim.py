import re
from pathlib import Path

fpath = Path("scripts/ops/simulation_engine.py")
content = fpath.read_text("utf-8")

replacement = """    base_registered = plan_df["registered"].sum()
    base_turnout = plan_df["turnout_pct"].mean()
    base_support = plan_df["support_pct"].mean()
    
    scenarios = [
        {"id": "baseline", "name": "Baseline (No Field)", "effort": 0.0},
        {"id": "field_light", "name": "Field Light (30% Capacity)", "effort": 0.3},
        {"id": "field_medium", "name": "Field Medium (70% Capacity)", "effort": 0.7},
        {"id": "field_heavy", "name": "Field Heavy (100% Capacity)", "effort": 1.0},
    ]
    
    results = []
    
    # ── Master / Top-Level ──
    for scn in scenarios:
        effort = scn["effort"]
        total_gain = plan_df["expected_net_gain"].sum() * effort
        adj_votes_baseline = base_registered * base_turnout * base_support
        adj_votes_final = adj_votes_baseline + total_gain
        results.append({
            "jurisdiction": "All",
            "scenario_id": scn["id"],
            "scenario_name": scn["name"],
            "effort_level": effort,
            "net_vote_gain": int(total_gain) if pd.notna(total_gain) else 0,
            "projected_support_votes": int(adj_votes_final) if pd.notna(adj_votes_final) else 0,
            "win_margin_estimate": int(adj_votes_final - (base_registered * base_turnout * 0.5)) if pd.notna(adj_votes_final) else 0
        })
        
    # ── Prompt 19: Per-Jurisdiction ──
    if "county" in plan_df.columns:
        for county, group in plan_df.groupby("county"):
            g_reg = group["registered"].sum()
            g_turn = group["turnout_pct"].mean()
            g_supp = group["support_pct"].mean()
            for scn in scenarios:
                effort = scn["effort"]
                t_gain = group["expected_net_gain"].sum() * effort
                a_base = g_reg * g_turn * g_supp
                a_fin = a_base + t_gain
                results.append({
                    "jurisdiction": county,
                    "scenario_id": scn["id"],
                    "scenario_name": scn["name"],
                    "effort_level": effort,
                    "net_vote_gain": int(t_gain) if pd.notna(t_gain) else 0,
                    "projected_support_votes": int(a_fin) if pd.notna(a_fin) else 0,
                    "win_margin_estimate": int(a_fin - (g_reg * g_turn * 0.5)) if pd.notna(a_fin) else 0
                })
"""

start_sentinel = '    base_registered = plan_df["registered"].sum()'
end_sentinel = '        })'

if start_sentinel in content and end_sentinel in content:
    pre = content[:content.find(start_sentinel)]
    post = content[content.rfind(end_sentinel) + len(end_sentinel):]
    fpath.write_text(pre + replacement + post, "utf-8")
    print("Sim engine updated successfully.")
else:
    print("Could not find sentinels.")
