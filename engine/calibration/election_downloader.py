"""
engine/calibration/election_downloader.py — Prompt 11

Attempt to download historical CA election detail workbooks.

IMPORTANT: Most CA county registrar sites use JavaScript-rendered pages and
inconsistent URL structures. This module tries known URL patterns for Sonoma
County and the CA SoS, but graceful failure is the expected outcome for most
years. The download_status.json output tells you what to manually retrieve.

If you have historical detail.xls files, place them at:
  data/elections/CA/Sonoma/<year>/detail.xls
and the calibration module will find them automatically without this downloader.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
log = logging.getLogger(__name__)

# ── Known URL patterns ────────────────────────────────────────────────────────
# These are best-effort patterns; registrar sites change frequently.

SONOMA_ROV_PATTERNS = {
    # Sonoma County ROV election results — typical pattern
    2024: [
        "https://sonomacounty.ca.gov/wp-content/uploads/2024/11/detail.xls",
        "https://www.sonomacounty.ca.gov/fileadmin/county/departments/registrar/2024_general/detail.xls",
    ],
    2022: [
        "https://sonomacounty.ca.gov/wp-content/uploads/2022/11/detail.xls",
        "https://www.sonomacounty.ca.gov/fileadmin/county/departments/registrar/2022_general/detail.xls",
    ],
    2020: [
        "https://sonomacounty.ca.gov/wp-content/uploads/2020/11/detail.xls",
        "https://www.sonomacounty.ca.gov/fileadmin/county/departments/registrar/2020_general/detail.xls",
    ],
    2018: [
        "https://sonomacounty.ca.gov/wp-content/uploads/2018/11/detail.xls",
    ],
    2016: [
        "https://sonomacounty.ca.gov/wp-content/uploads/2016/11/detail.xls",
    ],
}

# Manual download links (for download_status.json output)
MANUAL_LINKS = {
    "Sonoma County ROV": "https://www.sonomacounty.ca.gov/elected-officials-and-departments/registrar-of-voters/election-results",
    "CA Secretary of State": "https://www.sos.ca.gov/elections/prior-elections/statewide-election-results/",
    "statewidedatabase.org election data": "https://statewidedatabase.org/d20/g24.html",
    "MIT Election Lab": "https://electionlab.mit.edu/data",
}


def _try_download(url: str, dest: Path, timeout: int = 20) -> bool:
    """Try to download a file from url to dest. Returns True on success."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 CampaignInABox/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                return False
            data = r.read()
        if len(data) < 1000:  # Too small to be a real workbook
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        log.info(f"[DOWNLOADER] Downloaded {url} → {dest} ({len(data):,} bytes)")
        return True
    except Exception as e:
        log.debug(f"[DOWNLOADER] Failed {url}: {e}")
        return False


def download_historical_elections(
    county: str = "Sonoma",
    state: str = "CA",
    years: Optional[list[int]] = None,
    logger=None,
) -> dict:
    """
    Attempt to download historical election detail workbooks.

    Returns a status dict with what was found/downloaded/failed.
    Writes: data/elections/CA/<county>/<year>/detail.xls
    Writes: data/elections/CA/<county>/download_status.json
    """
    _log = logger or log
    if years is None:
        years = [2016, 2018, 2020, 2022, 2024]

    elections_dir = BASE_DIR / "data" / "elections" / state / county
    elections_dir.mkdir(parents=True, exist_ok=True)

    status = {
        "county": county,
        "state": state,
        "years_attempted": years,
        "years_downloaded": [],
        "years_already_present": [],
        "years_failed": [],
        "manual_download_links": MANUAL_LINKS,
        "instructions": (
            "For years that failed automatic download, manually download the "
            "detail.xls file from the Sonoma County ROV website and place it at: "
            f"data/elections/{state}/{county}/<year>/detail.xls"
        ),
    }

    url_map = SONOMA_ROV_PATTERNS if county == "Sonoma" else {}

    for year in years:
        dest = elections_dir / str(year) / "detail.xls"

        # Already present?
        if dest.exists() and dest.stat().st_size > 1000:
            _log.info(f"[DOWNLOADER] {year}: already present ({dest.stat().st_size:,} bytes)")
            status["years_already_present"].append(year)
            continue

        # Try known URLs
        urls = url_map.get(year, [])
        downloaded = False
        for url in urls:
            if _try_download(url, dest):
                status["years_downloaded"].append(year)
                downloaded = True
                break

        if not downloaded:
            _log.info(
                f"[DOWNLOADER] {year}: automatic download failed — "
                f"manual download required (see download_status.json)"
            )
            status["years_failed"].append(year)

    # Write status JSON
    status_path = elections_dir / "download_status.json"
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)
    _log.info(
        f"[DOWNLOADER] Status: {len(status['years_downloaded'])} downloaded, "
        f"{len(status['years_already_present'])} already present, "
        f"{len(status['years_failed'])} failed. See {status_path}"
    )
    return status
