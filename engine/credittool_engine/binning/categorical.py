"""Binning for a categorical variable: each category is its own bin,
except categories too small to trust are grouped into a single "Other"
bin. Missing values get their own bin, same as for numeric variables.
"""
from __future__ import annotations

import pandas as pd

from .types import MISSING_LABEL, OTHER_LABEL, VariableBinning
from .woe import compute_bin_stats


def bin_categorical_variable(
    values: pd.Series,
    bad_flag: pd.Series,
    min_bin_size: float = 0.05,
) -> VariableBinning:
    valid_mask = bad_flag.notna()
    missing_mask = valid_mask & values.isna()
    present_mask = valid_mask & ~missing_mask

    present_values = values[present_mask].astype(str)
    n_present = len(present_values)
    min_count = max(1, int(min_bin_size * n_present)) if n_present else 0

    value_counts = present_values.value_counts()
    small_categories = set(value_counts[value_counts < min_count].index) if n_present else set()
    # Never collapse every category into "Other" — keep at least the two
    # largest categories intact even if they're individually small.
    if len(small_categories) == len(value_counts) and len(value_counts) > 1:
        keep = set(value_counts.index[:2])
        small_categories -= keep

    categories_map: dict[str, str] = {}
    for cat in value_counts.index:
        categories_map[cat] = OTHER_LABEL if cat in small_categories else cat

    labels = pd.Series(index=bad_flag[valid_mask].index, dtype="object")
    if n_present:
        labels.loc[present_values.index] = present_values.map(categories_map)

    bin_order = [c for c in value_counts.index if c not in small_categories]
    if small_categories:
        bin_order.append(OTHER_LABEL)

    if missing_mask.any():
        labels.loc[bad_flag[missing_mask].index] = MISSING_LABEL
        bin_order.append(MISSING_LABEL)

    bad_flag_valid = bad_flag[valid_mask]
    bins, iv = compute_bin_stats(labels, bad_flag_valid, bin_order)
    # Sort by bad rate for readability (no natural order for categories).
    bins.sort(key=lambda b: b.bad_rate_pct)

    return VariableBinning(
        variable=str(values.name),
        kind="categorical",
        iv=iv,
        bins=bins,
        categories_map=categories_map,
    )
