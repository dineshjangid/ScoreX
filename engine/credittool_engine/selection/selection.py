"""Select a final variable list from WOE-transformed candidates.

Three passes, in order: drop variables below an IV threshold, drop the
weaker (by IV) of any pair of variables too correlated with each other,
then drop remaining variables whose VIF indicates they're still
redundant given the others.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor


@dataclass
class SelectionResult:
    selected: list[str]
    dropped: list[dict[str, Any]]
    correlation_matrix: dict[str, dict[str, float]]
    vif: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": self.selected,
            "dropped": self.dropped,
            "correlation_matrix": self.correlation_matrix,
            "vif": self.vif,
        }


def _compute_vifs(woe_frame: pd.DataFrame, columns: list[str]) -> list[float]:
    """VIF per column, with an intercept added (VIF's R^2 is meaningless
    without one) — the intercept's own VIF is excluded from the result.
    """
    design = sm.add_constant(woe_frame[columns], has_constant="add")
    values = design.to_numpy()
    return [variance_inflation_factor(values, i) for i in range(1, values.shape[1])]


def select_variables(
    woe_frame: pd.DataFrame,
    iv_by_variable: dict[str, float],
    min_iv: float = 0.02,
    max_corr: float = 0.7,
    max_vif: float = 5.0,
) -> SelectionResult:
    dropped: list[dict[str, Any]] = []

    remaining = [v for v in woe_frame.columns if iv_by_variable.get(v, 0.0) >= min_iv]
    for v in woe_frame.columns:
        if v not in remaining:
            dropped.append(
                {"variable": v, "reason": f"IV {iv_by_variable.get(v, 0.0):.4f} below threshold {min_iv}"}
            )

    while len(remaining) > 1:
        corr_values = woe_frame[remaining].corr().abs().to_numpy(copy=True)
        np.fill_diagonal(corr_values, 0.0)
        max_val = float(corr_values.max()) if corr_values.size else 0.0
        if max_val <= max_corr:
            break
        i, j = np.unravel_index(np.argmax(corr_values), corr_values.shape)
        var_i, var_j = remaining[i], remaining[j]
        drop_var, keep_var = (
            (var_i, var_j) if iv_by_variable.get(var_i, 0.0) < iv_by_variable.get(var_j, 0.0) else (var_j, var_i)
        )
        dropped.append({"variable": drop_var, "reason": f"correlated {max_val:.2f} with {keep_var} (lower IV)"})
        remaining.remove(drop_var)

    while len(remaining) > 2:
        vifs = _compute_vifs(woe_frame, remaining)
        max_vif_val = max(vifs)
        if max_vif_val <= max_vif:
            break
        idx = int(np.argmax(vifs))
        drop_var = remaining[idx]
        dropped.append({"variable": drop_var, "reason": f"VIF {max_vif_val:.2f} above threshold {max_vif}"})
        remaining.pop(idx)

    final_vif: dict[str, float] = {}
    corr_matrix: dict[str, dict[str, float]] = {}
    if len(remaining) >= 2:
        vifs = _compute_vifs(woe_frame, remaining)
        final_vif = {v: round(float(f), 3) for v, f in zip(remaining, vifs)}
        corr_matrix = woe_frame[remaining].corr().round(3).to_dict()

    return SelectionResult(selected=remaining, dropped=dropped, correlation_matrix=corr_matrix, vif=final_vif)
