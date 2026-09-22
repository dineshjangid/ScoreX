"""Train/test/out-of-time sample assignment for a defined target."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from sklearn.model_selection import train_test_split

SAMPLE_LABELS = ["train", "test", "oot", "excluded"]


@dataclass
class SamplingConfig:
    test_size: float = 0.3
    oot_size: float = 0.0
    date_column: str | None = None
    random_state: int = 42

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_size": self.test_size,
            "oot_size": self.oot_size,
            "date_column": self.date_column,
            "random_state": self.random_state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SamplingConfig":
        return cls(
            test_size=data.get("test_size", 0.3),
            oot_size=data.get("oot_size", 0.0),
            date_column=data.get("date_column"),
            random_state=data.get("random_state", 42),
        )


def assign_samples(df: pd.DataFrame, bad_flag: pd.Series, config: SamplingConfig) -> pd.DataFrame:
    """Return a DataFrame aligned to df.index with columns 'target' and 'sample'.

    'sample' is one of SAMPLE_LABELS. Rows where bad_flag is NaN (excluded /
    indeterminate per the target definition) are always labeled 'excluded'.
    """
    sample = pd.Series("excluded", index=df.index, dtype="object")
    valid_idx = bad_flag.dropna().index
    remaining_idx = valid_idx

    oot_idx: pd.Index = pd.Index([])
    if config.oot_size > 0 and len(valid_idx) > 0:
        if config.date_column:
            dates = pd.to_datetime(df.loc[valid_idx, config.date_column], errors="coerce")
            n_oot = int(round(len(valid_idx) * config.oot_size))
            oot_idx = dates.sort_values(ascending=False).head(n_oot).index
            remaining_idx = valid_idx.difference(oot_idx)
        else:
            remaining_idx, oot_list = train_test_split(
                remaining_idx.to_numpy(),
                test_size=config.oot_size,
                stratify=bad_flag.loc[remaining_idx],
                random_state=config.random_state,
            )
            remaining_idx = pd.Index(remaining_idx)
            oot_idx = pd.Index(oot_list)

    if len(remaining_idx) > 0 and config.test_size > 0:
        train_idx, test_idx = train_test_split(
            remaining_idx.to_numpy(),
            test_size=config.test_size,
            stratify=bad_flag.loc[remaining_idx],
            random_state=config.random_state,
        )
    else:
        train_idx, test_idx = remaining_idx.to_numpy(), []

    sample.loc[pd.Index(train_idx)] = "train"
    sample.loc[pd.Index(test_idx)] = "test"
    sample.loc[oot_idx] = "oot"

    return pd.DataFrame({"target": bad_flag, "sample": sample})


def sampling_summary(assignment: pd.DataFrame) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label in SAMPLE_LABELS:
        subset = assignment[assignment["sample"] == label]
        n_total = int(len(subset))
        n_bad = int((subset["target"] == 1).sum())
        n_good = int((subset["target"] == 0).sum())
        result[label] = {
            "n_total": n_total,
            "n_good": n_good,
            "n_bad": n_bad,
            "bad_rate_pct": round(n_bad / n_total * 100, 2) if n_total else 0.0,
        }
    return result
