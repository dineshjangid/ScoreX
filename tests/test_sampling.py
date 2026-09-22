import numpy as np
import pandas as pd

from credittool_engine.sampling import SamplingConfig, assign_samples, sampling_summary


def _synthetic_df(n=200, seed=0):
    rng = np.random.default_rng(seed)
    bad_flag = pd.Series(rng.choice([0, 1], size=n, p=[0.85, 0.15]), name="target").astype(float)
    df = pd.DataFrame({"x": rng.normal(size=n)})
    return df, bad_flag


def test_train_test_split_no_oot():
    df, bad_flag = _synthetic_df()
    config = SamplingConfig(test_size=0.3, oot_size=0.0)

    assignment = assign_samples(df, bad_flag, config)
    summary = sampling_summary(assignment)

    assert summary["oot"]["n_total"] == 0
    assert summary["excluded"]["n_total"] == 0
    assert summary["train"]["n_total"] + summary["test"]["n_total"] == 200
    # roughly stratified: bad rate close to the population 15%
    assert abs(summary["train"]["bad_rate_pct"] - summary["test"]["bad_rate_pct"]) < 10


def test_split_excludes_indeterminate_rows():
    df, bad_flag = _synthetic_df(n=100)
    bad_flag.iloc[:10] = np.nan  # simulate excluded/indeterminate accounts
    config = SamplingConfig(test_size=0.3, oot_size=0.0)

    assignment = assign_samples(df, bad_flag, config)
    summary = sampling_summary(assignment)

    assert summary["excluded"]["n_total"] == 10
    assert summary["train"]["n_total"] + summary["test"]["n_total"] == 90


def test_random_oot_split_when_no_date_column():
    df, bad_flag = _synthetic_df(n=300)
    config = SamplingConfig(test_size=0.3, oot_size=0.2, date_column=None)

    assignment = assign_samples(df, bad_flag, config)
    summary = sampling_summary(assignment)

    assert summary["oot"]["n_total"] == 60
    assert summary["train"]["n_total"] + summary["test"]["n_total"] == 240
