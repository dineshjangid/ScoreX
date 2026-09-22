"""Apply a fitted binning to raw values: assign bin labels, or map those
labels straight to WOE. Both take plain primitives (not the
VariableBinning dataclass) so they can be called against a binning
artifact loaded from JSON (as the API layer stores it) without
re-hydrating dataclasses.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .types import MISSING_LABEL, OTHER_LABEL, VariableBinning


def assign_bin_labels(
    values: pd.Series,
    kind: str,
    cutpoints: list[float] | None = None,
    categories_map: dict[str, str] | None = None,
    known_labels: set[str] | None = None,
) -> pd.Series:
    """Return the bin label string for each value, aligned to `values.index`.

    A category never seen during fitting falls back to the "Other" bin
    when one exists in `known_labels`; otherwise it's left as NaN.
    """
    missing_mask = values.isna()
    result = pd.Series(np.nan, index=values.index, dtype="object")

    present = values[~missing_mask]
    if len(present) > 0:
        if kind == "numeric":
            edges = [-np.inf] + list(cutpoints or []) + [np.inf]
            intervals = pd.cut(present.astype(float), bins=edges, right=True, include_lowest=True)
            result.loc[present.index] = intervals.astype(str)
        else:
            mapped = present.astype(str).map(categories_map or {})
            unseen = mapped.isna()
            if unseen.any() and known_labels and OTHER_LABEL in known_labels:
                mapped = mapped.where(~unseen, OTHER_LABEL)
            result.loc[present.index] = mapped

    if missing_mask.any():
        result.loc[missing_mask] = MISSING_LABEL

    return result


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
    labels = assign_bin_labels(values, kind, cutpoints, categories_map, known_labels=set(woe_by_label))
    return labels.map(woe_by_label).fillna(0.0).astype(float)


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
