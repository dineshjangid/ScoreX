"""Apply a fitted binning to raw values, producing per-row WOE.

Takes plain primitives (not the VariableBinning dataclass) so it can be
called directly against a binning artifact loaded from JSON (as the API
layer stores it) without re-hydrating dataclasses.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .types import MISSING_LABEL, OTHER_LABEL, VariableBinning


def apply_binning(
    values: pd.Series,
    kind: str,
    bins: list[dict],
    cutpoints: list[float] | None = None,
    categories_map: dict[str, str] | None = None,
) -> pd.Series:
    """Return a float Series of WOE values aligned to `values.index`.

    Values whose bin can't be determined (a category never seen during
    fitting, with no "Other" bin to fall back to) get WOE 0 (neutral).
    """
    woe_by_label = {b["label"]: b["woe"] for b in bins}
    missing_mask = values.isna()
    result = pd.Series(np.nan, index=values.index, dtype=float)

    present = values[~missing_mask]
    if len(present) > 0:
        if kind == "numeric":
            edges = [-np.inf] + list(cutpoints or []) + [np.inf]
            intervals = pd.cut(present.astype(float), bins=edges, right=True, include_lowest=True)
            labels = intervals.astype(str)
            result.loc[present.index] = labels.map(woe_by_label)
        else:
            mapped = present.astype(str).map(categories_map or {})
            unseen = mapped.isna()
            if unseen.any() and OTHER_LABEL in woe_by_label:
                mapped = mapped.where(~unseen, OTHER_LABEL)
            result.loc[present.index] = mapped.map(woe_by_label)

    if missing_mask.any():
        result.loc[missing_mask] = woe_by_label.get(MISSING_LABEL, 0.0)

    return result.fillna(0.0)


def apply_variable_binning(values: pd.Series, binning: VariableBinning) -> pd.Series:
    """Convenience wrapper for calling directly against a VariableBinning
    produced in-process (e.g. in tests), instead of a JSON artifact dict.
    """
    return apply_binning(
        values,
        kind=binning.kind,
        bins=[b.to_dict() for b in binning.bins],
        cutpoints=binning.cutpoints,
        categories_map=binning.categories_map,
    )
