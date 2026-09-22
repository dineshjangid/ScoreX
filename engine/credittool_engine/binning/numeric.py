"""Monotonic binning for a numeric variable.

Builds fine quantile bins, then greedily merges adjacent bins until every
bin meets a minimum size and the bad rate is monotonic across bins (the
property scorecard reviewers expect: risk should move in one direction as
the variable increases). Missing values get their own bin, excluded from
the monotonicity requirement.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .types import MISSING_LABEL, VariableBinning
from .woe import compute_bin_stats


def _bad_rate(n_good: int, n_bad: int) -> float:
    total = n_good + n_bad
    return n_bad / total if total else 0.0


def _initial_edges(present_values: pd.Series, max_bins: int) -> np.ndarray:
    n_unique = present_values.nunique()
    n_bins_init = max(2, min(max_bins, n_unique))
    try:
        _, edges = pd.qcut(present_values, q=n_bins_init, retbins=True, duplicates="drop")
    except ValueError:
        edges = np.array([present_values.min(), present_values.max()])
    edges = np.unique(edges)
    if len(edges) < 2:
        edges = np.array([present_values.min(), present_values.max()])
    edges = edges.astype(float)
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def _counts_by_interval(present_values: pd.Series, present_bad: pd.Series, edges: np.ndarray) -> list[dict]:
    intervals = pd.cut(present_values, bins=edges, right=True, include_lowest=True)
    counts = []
    for interval in intervals.cat.categories:
        mask = intervals == interval
        n_total = int(mask.sum())
        if n_total == 0:
            continue
        n_bad = int((present_bad[mask] == 1).sum())
        counts.append({"left": interval.left, "right": interval.right, "n_good": n_total - n_bad, "n_bad": n_bad})
    return counts


def _merge_at(counts: list[dict], i: int) -> list[dict]:
    merged = {
        "left": counts[i]["left"],
        "right": counts[i + 1]["right"],
        "n_good": counts[i]["n_good"] + counts[i + 1]["n_good"],
        "n_bad": counts[i]["n_bad"] + counts[i + 1]["n_bad"],
    }
    return counts[:i] + [merged] + counts[i + 2 :]


def _merge_small_bins(counts: list[dict], min_count: int) -> list[dict]:
    changed = True
    while changed and len(counts) > 2:
        changed = False
        for i, c in enumerate(counts):
            if c["n_good"] + c["n_bad"] < min_count:
                j = i + 1 if i < len(counts) - 1 else i - 1
                counts = _merge_at(counts, min(i, j))
                changed = True
                break
    return counts


def _is_monotonic(rates: list[float]) -> bool:
    diffs = np.diff(rates)
    return bool(np.all(diffs >= -1e-9) or np.all(diffs <= 1e-9))


def _merge_until_monotonic(counts: list[dict]) -> list[dict]:
    while len(counts) > 2:
        rates = [_bad_rate(c["n_good"], c["n_bad"]) for c in counts]
        if _is_monotonic(rates):
            break
        diffs = np.diff(rates)
        trend = np.sign(np.corrcoef(np.arange(len(rates)), rates)[0, 1]) or 1
        violations = [i for i, d in enumerate(diffs) if d != 0 and np.sign(d) != trend]
        if not violations:
            break
        idx = min(violations, key=lambda i: abs(diffs[i]))
        counts = _merge_at(counts, idx)
    return counts


def bin_numeric_variable(
    values: pd.Series,
    bad_flag: pd.Series,
    max_bins: int = 10,
    min_bin_size: float = 0.05,
) -> VariableBinning:
    valid_mask = bad_flag.notna()
    missing_mask = valid_mask & values.isna()
    present_mask = valid_mask & ~missing_mask

    present_values = values[present_mask]
    present_bad = bad_flag[present_mask]

    cutpoints: list[float] = []
    labels = pd.Series(index=bad_flag[valid_mask].index, dtype="object")

    if len(present_values) > 0:
        edges = _initial_edges(present_values, max_bins)
        counts = _counts_by_interval(present_values, present_bad, edges)
        min_count = max(1, int(min_bin_size * len(present_values)))
        counts = _merge_small_bins(counts, min_count)
        counts = _merge_until_monotonic(counts)

        cutpoints = [float(c["right"]) for c in counts[:-1]]
        final_edges = np.array([-np.inf] + cutpoints + [np.inf])
        intervals = pd.cut(present_values, bins=final_edges, right=True, include_lowest=True)
        bin_order = [str(iv) for iv in intervals.cat.categories if (intervals == iv).any()]
        labels.loc[present_values.index] = intervals.astype(str)
    else:
        bin_order = []

    if missing_mask.any():
        labels.loc[bad_flag[missing_mask].index] = MISSING_LABEL
        bin_order = bin_order + [MISSING_LABEL]

    bad_flag_valid = bad_flag[valid_mask]
    bins, iv = compute_bin_stats(labels, bad_flag_valid, bin_order)

    return VariableBinning(variable=str(values.name), kind="numeric", iv=iv, bins=bins, cutpoints=cutpoints)
