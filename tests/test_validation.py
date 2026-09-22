import numpy as np
import pandas as pd

from credittool_engine.binning import assign_bin_labels
from credittool_engine.validation import (
    compute_auc_gini,
    compute_ks,
    decile_table,
    population_stability_index,
    stability_index,
)


def _synthetic_scores(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    score = rng.normal(600, 30, n)
    # higher score -> safer, so bad probability decreases with score
    p_bad = 1 / (1 + np.exp((score - 600) / 20))
    bad = (rng.uniform(size=n) < p_bad).astype(float)
    return pd.Series(score), pd.Series(bad)


def test_ks_is_zero_when_score_uninformative():
    rng = np.random.default_rng(1)
    n = 2000
    score = pd.Series(rng.normal(size=n))
    bad = pd.Series((rng.uniform(size=n) < 0.2).astype(float))
    ks = compute_ks(bad, score)
    assert ks < 10  # small KS for a non-informative score


def test_ks_is_high_for_perfectly_separating_score():
    bad = pd.Series([1] * 100 + [0] * 100, dtype=float)
    score = pd.Series(list(range(100)) + list(range(100, 200)), dtype=float)  # bads all have lower score
    ks = compute_ks(bad, score)
    assert ks == 100.0


def test_auc_and_gini_for_informative_score():
    score, bad = _synthetic_scores()
    auc, gini = compute_auc_gini(bad, score)
    assert auc > 0.6
    assert np.isclose(gini, 2 * auc - 1)


def test_auc_is_half_for_random_score():
    rng = np.random.default_rng(2)
    n = 2000
    score = pd.Series(rng.normal(size=n))
    bad = pd.Series((rng.uniform(size=n) < 0.2).astype(float))
    auc, gini = compute_auc_gini(bad, score)
    assert 0.4 < auc < 0.6
    assert abs(gini) < 0.2


def test_decile_table_bad_rate_increases_toward_riskiest_decile():
    score, bad = _synthetic_scores()
    rows = decile_table(bad, score, n_bins=10)
    assert len(rows) == 10
    assert sum(r["n_total"] for r in rows) == len(score)
    # first decile (lowest score = riskiest) should have a higher bad rate
    # than the last decile (highest score = safest)
    assert rows[0]["bad_rate_pct"] > rows[-1]["bad_rate_pct"]


def test_stability_index_zero_for_identical_distributions():
    labels = pd.Series(["A"] * 50 + ["B"] * 50)
    result = stability_index(labels, labels)
    assert result["index"] == 0.0


def test_stability_index_positive_for_shifted_distribution():
    reference = pd.Series(["A"] * 80 + ["B"] * 20)
    comparison = pd.Series(["A"] * 20 + ["B"] * 80)
    result = stability_index(reference, comparison)
    assert result["index"] > 0.1


def test_population_stability_index_low_for_same_sample_split_randomly():
    score, _ = _synthetic_scores(n=4000)
    reference = score.iloc[:2000]
    comparison = score.iloc[2000:]
    result = population_stability_index(reference, comparison, n_bins=10)
    assert result["index"] < 0.1  # random split of the same distribution -> stable


def test_csi_uses_shared_bin_label_assignment():
    # CSI reuses assign_bin_labels from the binning module directly.
    values_train = pd.Series([10.0, 20.0, 30.0, 40.0] * 50)
    values_test = pd.Series([10.0, 20.0, 30.0, 40.0] * 50)
    cutpoints = [15.0, 25.0, 35.0]
    train_labels = assign_bin_labels(values_train, "numeric", cutpoints=cutpoints)
    test_labels = assign_bin_labels(values_test, "numeric", cutpoints=cutpoints)
    result = stability_index(train_labels, test_labels)
    assert result["index"] == 0.0
