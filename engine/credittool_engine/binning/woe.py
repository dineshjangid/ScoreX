"""Shared WOE/IV computation given any bin assignment.

Convention (Siddiqi, "Credit Risk Scorecards"): WOE_i = ln(dist_good_i /
dist_bad_i), where dist_good_i / dist_bad_i are each bin's share of all
good / bad records. A bin with more goods than its overall share gets a
positive WOE (safer); IV is the population-weighted sum of the WOE gap.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

# Small additive smoothing so a bin with zero goods or zero bads doesn't
# produce ln(0) / a divide-by-zero WOE.
_EPS = 1e-4


@dataclass
class BinStat:
    label: str
    n_total: int
    n_good: int
    n_bad: int
    bad_rate_pct: float
    pct_of_total: float
    woe: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "n_total": self.n_total,
            "n_good": self.n_good,
            "n_bad": self.n_bad,
            "bad_rate_pct": self.bad_rate_pct,
            "pct_of_total": self.pct_of_total,
            "woe": self.woe,
        }


def compute_bin_stats(bin_labels: pd.Series, bad_flag: pd.Series, order: list[str]) -> tuple[list[BinStat], float]:
    """bin_labels and bad_flag must be aligned to the same valid index.

    `order` fixes the display/scoring order of bin labels; any label in
    `order` with no rows is skipped.
    """
    n_total_all = len(bad_flag)
    total_good = int((bad_flag == 0).sum())
    total_bad = int((bad_flag == 1).sum())

    stats: list[BinStat] = []
    iv = 0.0
    for label in order:
        mask = bin_labels == label
        n_total = int(mask.sum())
        if n_total == 0:
            continue
        sub_bad = bad_flag[mask]
        n_bad = int((sub_bad == 1).sum())
        n_good = n_total - n_bad

        dist_good = n_good / total_good if total_good else 0.0
        dist_bad = n_bad / total_bad if total_bad else 0.0
        woe = float(np.log((dist_good + _EPS) / (dist_bad + _EPS)))
        iv += (dist_good - dist_bad) * woe

        stats.append(
            BinStat(
                label=str(label),
                n_total=n_total,
                n_good=n_good,
                n_bad=n_bad,
                bad_rate_pct=round(n_bad / n_total * 100, 2),
                pct_of_total=round(n_total / n_total_all * 100, 2) if n_total_all else 0.0,
                woe=round(woe, 4),
            )
        )
    return stats, round(iv, 4)
