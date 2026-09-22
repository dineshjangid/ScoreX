"""Adverse-action-style reason codes: for each scored record, the
variables whose bin contributed the most negative points — the biggest
reasons the score is lower than it could be.
"""
from __future__ import annotations

import pandas as pd

from ..binning import apply_binning


def compute_variable_contributions(
    df: pd.DataFrame,
    binning_variables: dict[str, dict],
    fitted_params: dict[str, float],
    factor: float,
) -> pd.DataFrame:
    """Points contribution per variable per row (same math as
    scoring.compute_scores, but kept per-variable rather than summed).

    Rounded per variable, same as scoring.compute_scores, so the points
    shown here match the exported scorecard's own points table exactly.
    """
    data = {}
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
        data[var] = (-factor * coef * woe).round()
    return pd.DataFrame(data, index=df.index)


def compute_reason_codes(contributions: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    """For each row, the top_n variables with the lowest (most negative)
    point contribution, as reason_1..reason_n (+ _points) columns."""
    out_rows = []
    for _, row in contributions.iterrows():
        ranked = row.sort_values()
        entry: dict[str, object] = {}
        for i in range(top_n):
            if i < len(ranked):
                entry[f"reason_{i + 1}"] = ranked.index[i]
                entry[f"reason_{i + 1}_points"] = round(float(ranked.iloc[i]), 2)
            else:
                entry[f"reason_{i + 1}"] = None
                entry[f"reason_{i + 1}_points"] = None
        out_rows.append(entry)
    return pd.DataFrame(out_rows, index=contributions.index)
