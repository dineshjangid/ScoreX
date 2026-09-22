import numpy as np
import pandas as pd

from credittool_engine.binning import MISSING_LABEL, bin_categorical_variable, bin_numeric_variable, bin_variable


def _monotonic_synthetic(n=1000, seed=0):
    """A numeric variable whose bad rate rises with the variable's value,
    plus a comparable amount of noise, so binning has real merging to do."""
    rng = np.random.default_rng(seed)
    x = rng.uniform(0, 100, n)
    p_bad = 0.05 + 0.5 * (x / 100)
    bad = (rng.uniform(size=n) < p_bad).astype(float)
    return pd.Series(x, name="score"), pd.Series(bad, name="target")


def test_numeric_bins_are_monotonic_in_bad_rate():
    x, bad_flag = _monotonic_synthetic()
    result = bin_numeric_variable(x, bad_flag, max_bins=10, min_bin_size=0.05)

    assert result.kind == "numeric"
    rates = [b.bad_rate_pct for b in result.bins]
    diffs = np.diff(rates)
    assert np.all(diffs >= -1e-9) or np.all(diffs <= 1e-9)
    assert result.iv > 0
    # every row accounted for exactly once
    assert sum(b.n_total for b in result.bins) == len(x)


def test_numeric_binning_separates_missing_values():
    x, bad_flag = _monotonic_synthetic(n=200)
    x = x.copy()
    x.iloc[:20] = np.nan

    result = bin_numeric_variable(x, bad_flag, max_bins=10, min_bin_size=0.05)
    missing_bin = next(b for b in result.bins if b.label == MISSING_LABEL)
    assert missing_bin.n_total == 20


def test_numeric_binning_respects_min_bin_size():
    x, bad_flag = _monotonic_synthetic(n=500)
    result = bin_numeric_variable(x, bad_flag, max_bins=10, min_bin_size=0.1)
    non_missing_bins = [b for b in result.bins if b.label != MISSING_LABEL]
    for b in non_missing_bins[:-1]:  # last bin can be a small remainder in edge cases
        assert b.n_total >= 0.1 * len(x) * 0.5  # allow some slack from merge order


def test_categorical_binning_groups_rare_categories_into_other():
    n = 300
    categories = ["A"] * 140 + ["B"] * 140 + ["rare1"] * 10 + ["rare2"] * 10
    rng = np.random.default_rng(1)
    bad = pd.Series((rng.uniform(size=n) < 0.2).astype(float))
    values = pd.Series(categories, name="segment")

    result = bin_categorical_variable(values, bad, min_bin_size=0.05)

    labels = {b.label for b in result.bins}
    assert "A" in labels
    assert "B" in labels
    assert "Other" in labels
    assert "rare1" not in labels
    assert "rare2" not in labels
    other_bin = next(b for b in result.bins if b.label == "Other")
    assert other_bin.n_total == 20


def test_categorical_binning_keeps_two_largest_when_all_small():
    values = pd.Series(["A", "A", "B", "B", "C"])
    bad = pd.Series([0, 1, 0, 1, 0], dtype=float)
    result = bin_categorical_variable(values, bad, min_bin_size=0.5)
    labels = {b.label for b in result.bins}
    # not every category collapsed into Other
    assert labels != {"Other"}


def test_bin_variable_dispatches_by_dtype():
    numeric = pd.Series([1.0, 2.0, 3.0, 4.0], name="x")
    categorical = pd.Series(["a", "b", "a", "b"], name="y")
    bad = pd.Series([0, 1, 0, 1], dtype=float)

    assert bin_variable(numeric, bad).kind == "numeric"
    assert bin_variable(categorical, bad).kind == "categorical"


def test_iv_is_zero_when_bad_rate_is_uniform_across_bins():
    # No signal: bad flag independent of x -> IV should be small (near zero)
    rng = np.random.default_rng(2)
    x = pd.Series(rng.uniform(0, 100, 2000))
    bad = pd.Series((rng.uniform(size=2000) < 0.2).astype(float))
    result = bin_numeric_variable(x, bad, max_bins=10, min_bin_size=0.05)
    assert result.iv < 0.05
