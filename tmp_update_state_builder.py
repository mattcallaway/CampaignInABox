from pathlib import Path

fpath = Path("engine/state/state_builder.py")
content = fpath.read_text("utf-8")

replacement = """    # ── Section N: multi_jurisdiction_summary (Prompt 19) ─────────────────────
    mj_strategy_path = _latest_file(root / "derived" / "strategy_packs" / contest_id, "*jurisdiction_strategy.csv")
    if mj_strategy_path:
        mj_rows = _read_csv_dicts(mj_strategy_path)
        state["jurisdictions"] = [r.get("county") for r in mj_rows if r.get("county")]
    
    sim_path_mj = _latest_file(root / "derived" / "strategy_packs" / contest_id, "*SIMULATION_RESULTS.csv")
    if sim_path_mj:
        sim_rows = _read_csv_dicts(sim_path_mj)
        mj_forecast = {}
        for r in sim_rows:
            j = r.get("jurisdiction", "All")
            sid = r.get("scenario_id", "baseline")
            if j not in mj_forecast:
                mj_forecast[j] = {}
            mj_forecast[j][sid] = {
                "margin": r.get("win_margin_estimate", 0),
                "support_votes": r.get("projected_support_votes", 0)
            }
        state["multi_jurisdiction_forecast"] = mj_forecast

    # ── Write outputs ─────────────────────────────────────────────────────────"""

start_sentinel = "    # ── Write outputs ─────────────────────────────────────────────────────────"

if start_sentinel in content:
    content = content.replace(start_sentinel, replacement)
    fpath.write_text(content, "utf-8")
    print("State builder updated successfully.")
else:
    print("Could not find sentinel.")
