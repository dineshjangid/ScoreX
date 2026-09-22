"""Apply a fitted scorecard (factor/offset from scaling + the model's
fitted params + the binning) to raw data, producing a total score per
row. Reused by validation (scoring train/test/oot), reason codes, and
scorecard export.
"""
from __future__ import annotations

import pandas as pd

from ..binning import apply_binning


def compute_scores(
    df: pd.DataFrame,
    binning_variables: dict[str, dict],
    fitted_params: dict[str, float],
    factor: float,
    offset: float,
) -> pd.Series:
    const = fitted_params["const"]
    base_points = offset - factor * const

    total = pd.Series(base_points, index=df.index, dtype=float)
    for var, coef in fitted_params.items():
        if var == "const":
            continue
        binning = binning_variables[var]
        woe = apply_binning(
            df[var],
            kind=binning["kind"],
            bins=binning["bins"],
            cutpoints=binning.get("cutpoints"),
            categories_map=binning.get("categories_map"),
        )
        total = total + (-factor * coef * woe)

    return total.round().astype(int)
