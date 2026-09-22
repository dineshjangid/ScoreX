import numpy as np
import pandas as pd
import pytest

from credittool_engine.binning import apply_manual_categorical_bins, apply_manual_numeric_bins


def _monotonic_synthetic(n=1000, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0, 100, n)
    p_bad = 0.05 + 0.5 * (x / 100)
    bad = (rng.uniform(size=n) < p_bad).astype(float)
    return pd.Series(x, name="score"), pd.Series(bad, name="target")


def test_manual_numeric_bins_use_exact_cutpoints():
    x, bad = _monotonic_synthetic()
    result = apply_manual_numeric_bins(x, bad, cutpoints=[30.0, 70.0])

    assert result.cutpoints == [30.0, 70.0]
    non_missing = [b for b in result.bins if b.label != "Missing"]
    assert len(non_missing) == 3
    assert sum(b.n_total for b in result.bins) == len(x)


def test_manual_numeric_bins_can_merge_to_fewer_bins():
    x, bad = _monotonic_synthetic()
    # merging everything into a single bin (no interior cutpoints)
    result = apply_manual_numeric_bins(x, bad, cutpoints=[])
    assert result.cutpoints == []
    assert len(result.bins) == 1
    assert result.bins[0].n_total == len(x)


def test_manual_numeric_bins_separates_missing():
    x, bad = _monotonic_synthetic(n=200)
    x = x.copy()
    x.iloc[:15] = np.nan
    result = apply_manual_numeric_bins(x, bad, cutpoints=[50.0])
    missing_bin = next(b for b in result.bins if b.label == "Missing")
    assert missing_bin.n_total == 15


def test_manual_categorical_bins_apply_custom_grouping():
    values = pd.Series(["A", "B", "C", "D"] * 50)
    rng = np.random.default_rng(1)
    bad = pd.Series((rng.uniform(size=200) < 0.2).astype(float))

    # group A+B together, C+D together
    categories_map = {"A": "Group1", "B": "Group1", "C": "Group2", "D": "Group2"}
    result = apply_manual_categorical_bins(values, bad, categories_map)

    labels = {b.label for b in result.bins}
    assert labels == {"Group1", "Group2"}
    group1 = next(b for b in result.bins if b.label == "Group1")
    assert group1.n_total == 100


def test_manual_categorical_bins_raises_on_missing_mapping():
    values = pd.Series(["A", "B", "C"])
    bad = pd.Series([0.0, 1.0, 0.0])
    with pytest.raises(ValueError, match="C"):
        apply_manual_categorical_bins(values, bad, categories_map={"A": "G1", "B": "G1"})
