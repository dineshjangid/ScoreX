"""Adverse-action-style reason codes: for each scored record, the
variables whose bin contributed the most negative points — the biggest
reasons the score is lower than it could be.
"""
from __future__ import annotations

import pandas as pd

from ..binning import apply_binning
from ..modeling import FEATURE_MODE, Algorithm, apply_feature_encoding, shap_matrix


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


def compute_shap_contributions(
    df: pd.DataFrame,
    variables: list[str],
    model,
    categories: dict[str, list[str]],
    algorithm: Algorithm,
) -> pd.DataFrame:
    """Per-row, per-variable SHAP contribution to the "bad" class, for an ML
    final model — the equivalent of compute_variable_contributions' per-bin
    WOE/points contribution, but for a tree ensemble instead of the
    logistic+WOE+scaling pipeline. A positive value pushes the prediction
    towards "bad" (worse); the biggest positive contributors are the reasons
    a record scored poorly.
    """
    X = apply_feature_encoding(df, variables, categories, FEATURE_MODE[algorithm])
    matrix = shap_matrix(model, X)
    return pd.DataFrame(matrix, columns=variables, index=df.index)


def compute_shap_reason_codes(contributions: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    """For each row, the top_n variables with the highest (most positive,
    most "towards bad") SHAP contribution, as reason_1..reason_n (+ _points)
    columns — same output shape as compute_reason_codes so both paths can
    share one preview/export rendering."""
    out_rows = []
    for _, row in contributions.iterrows():
        ranked = row.sort_values(ascending=False)
        entry: dict[str, object] = {}
        for i in range(top_n):
            if i < len(ranked):
                entry[f"reason_{i + 1}"] = ranked.index[i]
                entry[f"reason_{i + 1}_points"] = round(float(ranked.iloc[i]), 4)
            else:
                entry[f"reason_{i + 1}"] = None
                entry[f"reason_{i + 1}_points"] = None
        out_rows.append(entry)
    return pd.DataFrame(out_rows, index=contributions.index)
