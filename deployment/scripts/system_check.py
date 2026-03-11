"""
deployment/scripts/system_check.py

Validates the environment, verifies dependencies and directories,
and outputs a markdown health report.
"""
import sys
import os
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPORT_FILE = BASE_DIR / "reports" / "system" / "system_health.md"

def check_system():
    report = [f"# Campaign In A Box - System Health Report\nGenerated: {datetime.now().isoformat()}\n\n"]
    passed = True

    # 1. Python version
    report.append("## Python Environment\n")
    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if py_ver.major >= 3 and py_ver.minor >= 10:
        report.append(f"- ✅ Python Version: {py_str}\n")
    else:
        report.append(f"- ❌ Python Version: {py_str} (Requires >= 3.10)\n")
        passed = False

    # 2. Dependencies
    report.append("\n## Dependencies\n")
    deps = ["pandas", "numpy", "streamlit", "plotly", "yaml", "sklearn"]
    for d in deps:
        try:
            __import__(d)
            report.append(f"- ✅ {d}\n")
        except ImportError:
            report.append(f"- ❌ {d} (Missing)\n")
            passed = False

    # 3. Directories
    report.append("\n## Data Directories\n")
    dirs = ["data", "data/elections", "data/voters", "derived", "logs", "config"]
    for d in dirs:
        if (BASE_DIR / d).exists():
            report.append(f"- ✅ {d}/\n")
        else:
            report.append(f"- ❌ {d}/ (Missing)\n")
            passed = False

    # 4. Config
    report.append("\n## Configuration\n")
    config_file = BASE_DIR / "config" / "campaign_config.yaml"
    if config_file.exists():
        report.append("- ✅ campaign_config.yaml found\n")
    else:
        report.append("- ⚠️ campaign_config.yaml missing (Run setup wizard)\n")
    
    report.append("\n## Overall Status\n")
    if passed:
        report.append("**System is HEALTHY and ready to run.** 🚀\n")
        print("System Check: PASS")
    else:
        report.append("**System is DEGRADED. Check logs.** ⚠️\n")
        print("System Check: FAIL (See reports/system/system_health.md)")

    (BASE_DIR / "reports" / "system").mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("".join(report), encoding="utf-8")
    print(f"Report written to {REPORT_FILE}")

if __name__ == "__main__":
    check_system()
