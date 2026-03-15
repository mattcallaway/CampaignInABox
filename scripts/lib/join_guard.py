"""
scripts/lib/join_guard.py  — Prompt 8.6

Join cardinality guard.  Wraps pd.merge with pre/post-merge checks:
  - Key uniqueness on each side (as expected by `expect`)
  - Row-count explosion detection (explosion_factor > threshold → CRITICAL)

Usage:
    from scripts.lib.join_guard import safe_merge, JoinExplosionError
    merged = safe_merge(left, right, on="MPREC_ID",
                        how="left", expect="one_to_one",
                        name="allocation_join", log_ctx="Sheet1")
"""
from __future__ import annotations

import csv
import datetime
from pathlib import Path
from typing import Literal, Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent

ExpectMode = Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]

# Explosion threshold: row count after / row count before left
EXPLOSION_THRESHOLD = 1.05   # >5% row gain triggers CRITICAL for one_to_one / many_to_one


class JoinExplosionError(RuntimeError):
    """Raised when a merge causes an unexpected row-count explosion."""


def assert_unique(
    df: pd.DataFrame,
    keys: list[str] | str,
    name: str = "df",
    log_ctx: str = "",
) -> dict:
    """
    Check that `keys` are unique in `df`.
    Returns a report dict; raises nothing (caller decides action).
    """
    if isinstance(keys, str):
        keys = [keys]
    keys = [k for k in keys if k in df.columns]
    if not keys:
        return {"unique": True, "dup_count": 0, "name": name}

    dup = df.duplicated(subset=keys, keep=False)
    dup_count = int(dup.sum())
    return {
        "name":      name,
        "log_ctx":   log_ctx,
        "keys":      keys,
        "unique":    dup_count == 0,
        "dup_count": dup_count,
        "dup_sample": df[dup][keys].head(5).to_dict("records"),
    }


def safe_merge(
    left: pd.DataFrame,
    right: pd.DataFrame,
    on: str | list[str] | None = None,
    left_on: str | list[str] | None = None,
    right_on: str | list[str] | None = None,
    how: str = "left",
    expect: ExpectMode = "one_to_many",
    name: str = "join",
    log_ctx: str = "",
    contest_id: str = "unknown",
    run_id: str = "unknown",
    logger=None,
    threshold: float = EXPLOSION_THRESHOLD,
) -> pd.DataFrame:
    """
    Perform pd.merge with cardinality guardrails.

    Parameters
    ----------
    left, right  : DataFrames to merge
    on           : join key(s) — used when left and right share the same column name
    left_on      : join key(s) on the left DataFrame (use with right_on)
    right_on     : join key(s) on the right DataFrame (use with left_on)
    how          : left/inner/right/outer
    expect       : expected cardinality relationship
    name         : human label for diagnostics
    log_ctx      : e.g. sheet name for log messages
    contest_id   : used in diagnostic output filename
    run_id       : used in diagnostic output filename
    logger       : optional pipeline logger
    threshold    : explosion factor triggering CRITICAL (default 1.05)

    Returns
    -------
    Merged DataFrame.

    Raises
    ------
    JoinExplosionError if expect=one_to_one or many_to_one and
    rows after / rows before > threshold.
    """
    if on is None and (left_on is None or right_on is None):
        raise ValueError("safe_merge requires either 'on' or both 'left_on' and 'right_on'")

    # Resolve key lists for uniqueness checks
    left_keys  = ([left_on] if isinstance(left_on, str) else list(left_on)) if left_on else ([on] if isinstance(on, str) else list(on))
    right_keys = ([right_on] if isinstance(right_on, str) else list(right_on)) if right_on else ([on] if isinstance(on, str) else list(on))

    n_left  = len(left)
    n_right = len(right)

    # Pre-merge uniqueness checks
    left_unique  = assert_unique(left,  left_keys,  name=f"{name}.left",  log_ctx=log_ctx)
    right_unique = assert_unique(right, right_keys, name=f"{name}.right", log_ctx=log_ctx)

    if logger:
        if not left_unique["unique"]:
            logger.warn(f"  [JOIN_GUARD] {name}: left side has {left_unique['dup_count']} duplicate key(s) on {left_keys}")
        if not right_unique["unique"]:
            logger.warn(f"  [JOIN_GUARD] {name}: right side has {right_unique['dup_count']} duplicate key(s) on {right_keys}")

    # Perform the merge — support both on= and left_on=/right_on=
    if left_on is not None and right_on is not None:
        merged = pd.merge(left, right, left_on=left_on, right_on=right_on, how=how)
    else:
        merged = pd.merge(left, right, on=on, how=how)
    n_merged = len(merged)

    # Post-merge explosion check
    explosion_factor = n_merged / n_left if n_left > 0 else 1.0
    is_critical = False

    if expect in ("one_to_one", "many_to_one") and explosion_factor > threshold:
        is_critical = True
        msg = (
            f"[JOIN_GUARD] CRITICAL: join explosion in {name!r} "
            f"({n_left} → {n_merged} rows, factor={explosion_factor:.2f}x). "
            f"Expect={expect}, threshold={threshold}. "
            f"This likely indicates a many-to-many join causing vote count inflation."
        )
        if logger:
            logger.warn(msg)

    # Build diagnostic record
    diag = {
        "timestamp":        datetime.datetime.now().isoformat(),
        "name":             name,
        "log_ctx":          log_ctx,
        "on":               keys,
        "how":              how,
        "expect":           expect,
        "n_left":           n_left,
        "n_right":          n_right,
        "n_merged":         n_merged,
        "explosion_factor": round(explosion_factor, 4),
        "left_unique":      left_unique["unique"],
        "right_unique":     right_unique["unique"],
        "is_critical":      is_critical,
        "contest_id":       contest_id,
        "run_id":           run_id,
    }

    _append_join_diagnostic(diag, contest_id)

    if is_critical:
        raise JoinExplosionError(
            f"Join explosion in {name!r}: {n_left} → {n_merged} rows "
            f"({explosion_factor:.2f}x). Indicates many-to-many join on {keys}. "
            f"Halting downstream to prevent corrupt vote counts."
        )

    if logger:
        logger.info(
            f"  [JOIN_GUARD] {name}: {n_left}+{n_right} → {n_merged} rows "
            f"(×{explosion_factor:.2f}) ✓"
        )

    return merged


def _append_join_diagnostic(diag: dict, contest_id: str) -> None:
    """Append a row to the per-contest join_guard CSV."""
    diag_dir = BASE_DIR / "derived" / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True)
    csv_path = diag_dir / f"{contest_id}__join_guard.csv"

    fieldnames = [
        "timestamp", "name", "log_ctx", "on", "how", "expect",
        "n_left", "n_right", "n_merged", "explosion_factor",
        "left_unique", "right_unique", "is_critical",
    ]
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(diag)
