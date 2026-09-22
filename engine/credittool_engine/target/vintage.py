"""Vintage analysis: bad rate by observation-date cohort. Used mainly for
behavioural scorecards to sanity-check the target/performance window
before finalizing sampling — e.g. confirming cohorts have matured enough
for their bad flag to be trustworthy.
"""
from __future__ import annotations

from typing import Any

import pandas as pd


def vintage_analysis(df: pd.DataFrame, date_column: str, bad_flag: pd.Series, freq: str = "M") -> list[dict[str, Any]]:
    dates = pd.to_datetime(df[date_column], errors="coerce")
    valid_mask = bad_flag.notna() & dates.notna()

    if not valid_mask.any():
        return []

    cohort = dates[valid_mask].dt.to_period(freq).astype(str)
    bad = bad_flag[valid_mask]

    rows = []
    for cohort_label, sub in pd.DataFrame({"cohort": cohort, "bad": bad}).groupby("cohort"):
        n_total = len(sub)
        n_bad = int((sub["bad"] == 1).sum())
        rows.append(
            {
                "cohort": str(cohort_label),
                "n_total": int(n_total),
                "n_bad": n_bad,
                "bad_rate_pct": round(n_bad / n_total * 100, 2) if n_total else 0.0,
            }
        )
    rows.sort(key=lambda r: r["cohort"])
    return rows
