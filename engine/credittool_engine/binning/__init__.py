from __future__ import annotations

import pandas as pd

from .categorical import bin_categorical_variable
from .numeric import bin_numeric_variable
from .types import MISSING_LABEL, VariableBinning
from .woe import BinStat, compute_bin_stats

__all__ = [
    "MISSING_LABEL",
    "VariableBinning",
    "BinStat",
    "compute_bin_stats",
    "bin_numeric_variable",
    "bin_categorical_variable",
    "bin_variable",
]


def bin_variable(
    values: pd.Series,
    bad_flag: pd.Series,
    max_bins: int = 10,
    min_bin_size: float = 0.05,
) -> VariableBinning:
    """Dispatch to numeric or categorical binning based on dtype."""
    if pd.api.types.is_numeric_dtype(values) and not pd.api.types.is_bool_dtype(values):
        return bin_numeric_variable(values, bad_flag, max_bins=max_bins, min_bin_size=min_bin_size)
    return bin_categorical_variable(values, bad_flag, min_bin_size=min_bin_size)
