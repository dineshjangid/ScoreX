import numpy as np
import pandas as pd

from credittool_engine.binning import (
    apply_variable_binning,
    bin_categorical_variable,
    bin_numeric_variable,
)


def test_numeric_transform_reproduces_fit_woe():
    rng = np.random.default_rng(0)
    x = pd.Series(rng.uniform(0, 100, 500), name="x")
    bad = pd.Series((rng.uniform(size=500) < (0.05 + 0.4 * x / 100)).astype(float))

    binning = bin_numeric_variable(x, bad, max_bins=5, min_bin_size=0.05)
    transformed = apply_variable_binning(x, binning)

    # Recomputing WOE per row and averaging within each original bin
    # should reproduce that bin's stored WOE, since transform just
    # reapplies the same cutpoints.
    woe_by_label = {b.label: b.woe for b in binning.bins}
    edges = [-np.inf] + binning.cutpoints + [np.inf]
    intervals = pd.cut(x, bins=edges, right=True, include_lowest=True).astype(str)
    for label, expected_woe in woe_by_label.items():
        mask = intervals == label
        if mask.any():
            assert np.allclose(transformed[mask], expected_woe)


def test_numeric_transform_handles_missing():
    x = pd.Series([1.0, 2.0, np.nan, 4.0])
    bad = pd.Series([0.0, 1.0, 0.0, 1.0])
    binning = bin_numeric_variable(x, bad, max_bins=2, min_bin_size=0.1)

    transformed = apply_variable_binning(x, binning)
    missing_woe = next(b.woe for b in binning.bins if b.label == "Missing")
    assert transformed.iloc[2] == missing_woe


def test_categorical_transform_maps_known_and_unseen_categories():
    values = pd.Series(["A"] * 50 + ["B"] * 50 + ["rare"] * 5)
    bad = pd.Series([0.0] * 40 + [1.0] * 10 + [0.0] * 45 + [1.0] * 5 + [0.0] * 5)
    binning = bin_categorical_variable(values, bad, min_bin_size=0.1)

    new_values = pd.Series(["A", "B", "never_seen_before"])
    transformed = apply_variable_binning(new_values, binning)

    woe_by_label = {b.label: b.woe for b in binning.bins}
    assert transformed.iloc[0] == woe_by_label["A"]
    assert transformed.iloc[1] == woe_by_label["B"]
    # unseen category falls back to "Other" bin's WOE
    assert transformed.iloc[2] == woe_by_label["Other"]
