"""Manual bin overrides: recompute a single variable's bins from
user-specified structure (cutpoints for numeric, a category-to-group map
for categorical) instead of the automatic algorithm. Uses the same WOE/IV
math as automatic binning, so an edited bin is fully consistent with the
rest of the tool.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .types import MISSING_LABEL, VariableBinning
from .woe import compute_bin_stats


def apply_manual_numeric_bins(values: pd.Series, bad_flag: pd.Series, cutpoints: list[float]) -> VariableBinning:
    valid_mask = bad_flag.notna()
    missing_mask = valid_mask & values.isna()
    present_mask = valid_mask & ~missing_mask

    cutpoints = sorted(cutpoints)
    labels = pd.Series(index=bad_flag[valid_mask].index, dtype="object")
    bin_order: list[str] = []

    present_values = values[present_mask]
    if len(present_values) > 0:
        edges = [-np.inf] + cutpoints + [np.inf]
        intervals = pd.cut(present_values.astype(float), bins=edges, right=True, include_lowest=True)
        labels.loc[present_values.index] = intervals.astype(str)
        bin_order = [str(c) for c in intervals.cat.categories]

    if missing_mask.any():
        labels.loc[bad_flag[missing_mask].index] = MISSING_LABEL
        bin_order.append(MISSING_LABEL)

    bad_flag_valid = bad_flag[valid_mask]
    bins, iv = compute_bin_stats(labels, bad_flag_valid, bin_order)
    return VariableBinning(variable=str(values.name), kind="numeric", iv=iv, bins=bins, cutpoints=cutpoints)


def apply_manual_categorical_bins(values: pd.Series, bad_flag: pd.Series, categories_map: dict[str, str]) -> VariableBinning:
    valid_mask = bad_flag.notna()
    missing_mask = valid_mask & values.isna()
    present_mask = valid_mask & ~missing_mask

    labels = pd.Series(index=bad_flag[valid_mask].index, dtype="object")
    bin_order: list[str] = []

    present_values = values[present_mask].astype(str)
    if len(present_values) > 0:
        mapped = present_values.map(categories_map)
        unmapped = mapped.isna()
        if unmapped.any():
            unknown = sorted(set(present_values[unmapped]))
            raise ValueError(f"categories_map is missing these observed values: {unknown}")
        labels.loc[present_values.index] = mapped
        bin_order = list(dict.fromkeys(mapped))

    if missing_mask.any():
        labels.loc[bad_flag[missing_mask].index] = MISSING_LABEL
        bin_order.append(MISSING_LABEL)

    bad_flag_valid = bad_flag[valid_mask]
    bins, iv = compute_bin_stats(labels, bad_flag_valid, bin_order)
    return VariableBinning(variable=str(values.name), kind="categorical", iv=iv, bins=bins, categories_map=categories_map)
