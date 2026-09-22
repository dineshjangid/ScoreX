"""Define the "bad" outcome for a scorecard build and derive a bad flag.

A TargetDefinition turns one raw column into a three-way outcome per
record: bad (1), good (0), or excluded/indeterminate (NaN — dropped from
modeling samples but kept for reference, e.g. rejected applicants or
accounts mid-cure).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

TargetMode = Literal["values", "threshold"]


@dataclass
class TargetDefinition:
    target_column: str
    mode: TargetMode
    bad_values: list[str] = field(default_factory=list)
    threshold: float | None = None
    exclude_values: list[str] = field(default_factory=list)
    # Column the exclude_values are matched against. Defaults to
    # target_column itself (e.g. a sentinel value mixed into the outcome
    # column); set this to exclude based on a separate column instead, e.g.
    # dropping declined applicants via a "decision" column while the target
    # is computed from a repayment column.
    exclude_column: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_column": self.target_column,
            "mode": self.mode,
            "bad_values": self.bad_values,
            "threshold": self.threshold,
            "exclude_values": self.exclude_values,
            "exclude_column": self.exclude_column,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TargetDefinition":
        return cls(
            target_column=data["target_column"],
            mode=data["mode"],
            bad_values=data.get("bad_values", []),
            threshold=data.get("threshold"),
            exclude_values=data.get("exclude_values", []),
            exclude_column=data.get("exclude_column"),
        )


def apply_target_definition(df: pd.DataFrame, target_def: TargetDefinition) -> pd.Series:
    """Return a Series of 1 (bad) / 0 (good) / NaN (excluded), aligned to df.index."""
    col = df[target_def.target_column]

    if target_def.mode == "threshold":
        if target_def.threshold is None:
            raise ValueError("threshold mode requires a threshold value")
        numeric = pd.to_numeric(col, errors="coerce")
        valid_mask = numeric.notna()
        bad_mask = valid_mask & (numeric >= target_def.threshold)
    else:
        if not target_def.bad_values:
            raise ValueError("values mode requires at least one bad_value")
        raw = col.astype(str)
        valid_mask = pd.Series(True, index=df.index)
        bad_mask = raw.isin(target_def.bad_values)

    excluded_mask = pd.Series(False, index=df.index)
    if target_def.exclude_values:
        exclude_col = df[target_def.exclude_column] if target_def.exclude_column else col
        excluded_mask = exclude_col.astype(str).isin(target_def.exclude_values)

    bad_flag = pd.Series(np.nan, index=df.index)
    good_mask = valid_mask & ~bad_mask & ~excluded_mask
    final_bad_mask = valid_mask & bad_mask & ~excluded_mask
    bad_flag[good_mask] = 0
    bad_flag[final_bad_mask] = 1
    return bad_flag


def target_summary(bad_flag: pd.Series) -> dict[str, Any]:
    n_total = int(len(bad_flag))
    n_bad = int((bad_flag == 1).sum())
    n_good = int((bad_flag == 0).sum())
    n_excluded = n_total - n_bad - n_good
    n_valid = n_bad + n_good
    return {
        "n_total": n_total,
        "n_good": n_good,
        "n_bad": n_bad,
        "n_excluded": n_excluded,
        "bad_rate_pct": round(n_bad / n_valid * 100, 2) if n_valid else 0.0,
    }
