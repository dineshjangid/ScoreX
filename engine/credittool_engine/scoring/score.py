"""Apply a fitted scorecard (factor/offset from scaling + the model's
fitted params + the binning) to raw data, producing a total score per
row. Reused by validation (scoring train/test/oot), reason codes, and
scorecard export.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..binning import apply_binning
from ..modeling import Algorithm, predict_bad_proba


def compute_scores(
    df: pd.DataFrame,
    binning_variables: dict[str, dict],
    fitted_params: dict[str, float],
    factor: float,
    offset: float,
) -> pd.Series:
    # Round each variable's contribution separately (matching how
    # scaling.build_scorecard rounds each bin's points), so a score
    # computed here always equals the sum of the exported scorecard's own
    # points table for the same input — not a different number from
    # rounding the continuous total just once.
    const = fitted_params["const"]
    base_points = round(offset - factor * const)

    total = pd.Series(float(base_points), index=df.index)
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
        total = total + (-factor * coef * woe).round()

    return total.astype(int)


def compute_ml_scores(
    df: pd.DataFrame,
    variables: list[str],
    model,
    categories: dict[str, list[str]],
    algorithm: Algorithm,
) -> pd.Series:
    """"Safety score" (0-1000, higher = safer) for an ML final model, on the
    same "higher = safer" convention as compute_scores' points — so
    validation/decile/PSI/CSI (all of which just consume a `score` series)
    work unchanged regardless of which final model produced it.
    """
    p_bad = predict_bad_proba(model, df, variables, categories, algorithm)
    return np.round((1 - p_bad) * 1000).astype(int)
