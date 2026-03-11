"""
engine/setup/setup_wizard.py

Initial setup wizard to configure the campaign environment.
Runs automatically on first launch via run_campaign_box scripts.
"""
import os
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "campaign_config.yaml"

def run_wizard():
    print("==============================================")
    print(" Campaign In A Box — First Run Setup Wizard")
    print("==============================================")
    print("Let's configure your campaign environment.\n")

    campaign_name = input("Campaign Name (e.g., Sonoma Prop 50): ").strip()
    jurisdiction = input("Jurisdiction (e.g., Sonoma County): ").strip()
    state = input("State Code (e.g., CA): ").strip()
    county = input("County Name (e.g., Sonoma): ").strip()
    contest = input("Active Contest ID (e.g., prop_50_special): ").strip()
    
    # Defaults
    if not campaign_name: campaign_name = "My Campaign"
    if not jurisdiction: jurisdiction = "Local District"
    if not state: state = "CA"
    if not county: county = "Local"
    if not contest: contest = "local_race_2026"

    # Setup directories
    dirs = [
        "data", "data/elections", "data/voters", "data/intelligence", 
        "data/intelligence/private", "data/campaign_runtime",
        "derived", "logs", "archive", "reports", "config", "reports/system"
    ]
    for d in dirs:
        (BASE_DIR / d).mkdir(parents=True, exist_ok=True)
        
    config_data = {
        "campaign": {
            "contest_name": campaign_name,
            "contest_type": "ballot_measure",
            "jurisdiction": jurisdiction,
            "election_date": "2026-11-03",
            "state": state,
            "county": county,
            "contest_slug": contest
        },
        "targets": {
            "target_vote_share": 0.52,
            "win_margin": 0.04
        },
        "budget": {
            "total_budget": 100000
        },
        "field": {
            "total_volunteers": 50
        },
        "system": {
            "data_directory": "./data"
        }
    }

    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir()

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, sort_keys=False, default_flow_style=False)

    print("\n✓ Configuration saved to config/campaign_config.yaml")
    print("✓ Required directories initialized.")
    print("Setup complete! Launching dashboard...\n")

if __name__ == "__main__":
    if not CONFIG_FILE.exists():
        run_wizard()
    else:
        print("Config already exists.")
