import numpy as np
import pandas as pd

from credittool_engine.binning import assign_bin_labels
from credittool_engine.validation import (
    compute_auc_gini,
    compute_ks,
    decile_table,
    population_stability_index,
    score_bucket_edges,
    score_histogram,
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


def test_score_histogram_covers_every_row_exactly_once():
    score, _ = _synthetic_scores(n=500)
    rows = score_histogram(score, n_bins=15)
    assert len(rows) == 15
    assert sum(r["count"] for r in rows) == 500
    # bins are contiguous and ascending
    for a, b in zip(rows, rows[1:]):
        assert a["bin_end"] == b["bin_start"]


def test_score_histogram_handles_constant_score():
    score = pd.Series([600.0] * 10)
    rows = score_histogram(score, n_bins=15)
    assert rows == [{"bin_start": 600.0, "bin_end": 600.0, "count": 10, "pct": 100.0}]


def test_score_histogram_handles_empty_input():
    assert score_histogram(pd.Series([], dtype=float)) == []


def test_train_edges_bucket_other_samples_row_for_row():
    train_score, train_bad = _synthetic_scores(n=2000, seed=0)
    test_score, test_bad = _synthetic_scores(n=500, seed=1)
    edges = score_bucket_edges(train_score, n_bins=10)

    train_rows = decile_table(train_bad, train_score, edges=edges)
    test_rows = decile_table(test_bad, test_score, edges=edges)

    assert len(train_rows) == len(test_rows) == 10
    assert [r["score_range"] for r in train_rows] == [r["score_range"] for r in test_rows]
    assert sum(r["n_total"] for r in test_rows) == 500
    # train buckets are its own deciles, so each holds ~10% of rows
    assert all(abs(r["n_total"] - 200) <= 1 for r in train_rows)
    assert train_rows[0]["score_range"].startswith("≤") and train_rows[-1]["score_range"].startswith(">")


def test_fixed_edges_report_empty_buckets_and_out_of_range_scores():
    train_score = pd.Series(np.arange(100, dtype=float))
    edges = score_bucket_edges(train_score, n_bins=4)
    # every comparison score sits far above train's range
    rows = decile_table(pd.Series([0.0, 1.0, 0.0]), pd.Series([1000.0, 1001.0, 1002.0]), edges=edges)

    assert len(rows) == 4
    assert [r["n_total"] for r in rows] == [0, 0, 0, 3]
    assert rows[-1]["bad_rate_pct"] == 33.33
    assert rows[0]["bad_rate_pct"] == 0.0


def test_fixed_edges_for_constant_train_score_collapse_to_one_bucket():
    edges = score_bucket_edges(pd.Series([600.0] * 20))
    rows = decile_table(pd.Series([0.0, 1.0]), pd.Series([500.0, 700.0]), edges=edges)
    assert len(rows) == 1 and rows[0]["n_total"] == 2


def test_histogram_on_train_range_clips_and_reports_pct():
    train_score, _ = _synthetic_scores(n=500, seed=0)
    value_range = (float(train_score.min()), float(train_score.max()))
    other = pd.Series([value_range[0] - 100, value_range[1] + 100, float(train_score.mean())])

    train_rows = score_histogram(train_score, n_bins=10, value_range=value_range)
    other_rows = score_histogram(other, n_bins=10, value_range=value_range)

    assert [r["bin_start"] for r in train_rows] == [r["bin_start"] for r in other_rows]
    assert sum(r["count"] for r in other_rows) == 3
    assert other_rows[0]["count"] >= 1 and other_rows[-1]["count"] >= 1
    assert abs(sum(r["pct"] for r in train_rows) - 100) < 0.1


def test_discrimination_metrics_rank_by_predicted_bad_probability():
    from credittool_engine.validation import discrimination_metrics

    score, bad = _synthetic_scores(n=1000)
    p_bad = 1 / (1 + np.exp((score - 600) / 20))  # higher score -> lower P(bad)
    metrics = discrimination_metrics(bad, p_bad)

    auc, gini = compute_auc_gini(bad, score)
    assert metrics == {"n_total": 1000, "ks": compute_ks(bad, score), "auc": auc, "gini": gini}
    assert discrimination_metrics(pd.Series([], dtype=float), pd.Series([], dtype=float)) is None
