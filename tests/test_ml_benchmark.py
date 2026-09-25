import numpy as np
import pandas as pd
import pytest

from credittool_engine.modeling import (
    ALL_ALGORITHMS,
    Hyperparams,
    fit_all_benchmarks,
    fit_ml_benchmark,
    fit_model,
    predict_bad_proba,
)
from credittool_engine.validation import discrimination_metrics


def _synthetic_credit_data(n=1000, seed=0):
    rng = np.random.default_rng(seed)
    income = rng.normal(50000, 15000, n)
    segment = rng.choice(["A", "B", "C"], n)
    segment_risk = np.where(segment == "C", 0.3, np.where(segment == "B", 0.1, -0.1))
    logit_bad = -0.00003 * (income - 50000) + segment_risk
    p_bad = 1 / (1 + np.exp(-logit_bad))
    bad = (rng.uniform(size=n) < p_bad).astype(float)
    df = pd.DataFrame({"income": income, "segment": segment})
    return df, pd.Series(bad)


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
def test_ml_benchmark_reports_discriminative_auc(algorithm):
    df, bad = _synthetic_credit_data()
    train_df, test_df = df.iloc[:700], df.iloc[700:]
    train_bad, test_bad = bad.iloc[:700], bad.iloc[700:]

    result = fit_ml_benchmark(train_df, train_bad, test_df, test_bad, variables=["income", "segment"], algorithm=algorithm)

    assert result.algorithm == algorithm
    assert result.train_auc > 0.55
    assert result.test_auc > 0.5
    assert np.isclose(result.train_gini, 2 * result.train_auc - 1, atol=1e-3)


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
def test_ml_benchmark_feature_importance_covers_all_variables(algorithm):
    df, bad = _synthetic_credit_data()
    train_df, test_df = df.iloc[:700], df.iloc[700:]
    train_bad, test_bad = bad.iloc[:700], bad.iloc[700:]

    result = fit_ml_benchmark(train_df, train_bad, test_df, test_bad, variables=["income", "segment"], algorithm=algorithm)

    variables_in_importance = {f.variable for f in result.feature_importance}
    assert variables_in_importance == {"income", "segment"}
    assert all(f.mean_abs_shap >= 0 for f in result.feature_importance)
    # sorted descending by importance
    importances = [f.mean_abs_shap for f in result.feature_importance]
    assert importances == sorted(importances, reverse=True)


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
def test_ml_benchmark_handles_single_class_test_sample(algorithm):
    df, bad = _synthetic_credit_data(n=200)
    train_df, test_df = df.iloc[:150], df.iloc[150:]
    train_bad = bad.iloc[:150]
    test_bad = pd.Series([0.0] * 50)  # degenerate: no bads in test

    result = fit_ml_benchmark(train_df, train_bad, test_df, test_bad, variables=["income", "segment"], algorithm=algorithm)
    assert result.test_auc == 0.5
    assert result.test_gini == 0.0


def test_fit_all_benchmarks_returns_one_result_per_algorithm():
    df, bad = _synthetic_credit_data()
    train_df, test_df = df.iloc[:700], df.iloc[700:]
    train_bad, test_bad = bad.iloc[:700], bad.iloc[700:]

    results = fit_all_benchmarks(train_df, train_bad, test_df, test_bad, variables=["income", "segment"])

    assert [r.algorithm for r in results] == list(ALL_ALGORITHMS)
    assert all(r.test_auc > 0.5 for r in results)


ALL_KNOBS = Hyperparams(n_estimators=40, max_depth=4, learning_rate=0.1, subsample=0.8, min_samples_leaf=20, l2_reg=3.0)


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
def test_every_algorithm_accepts_every_hyperparameter(algorithm):
    df, bad = _synthetic_credit_data()
    result = fit_ml_benchmark(df.iloc[:700], bad.iloc[:700], df.iloc[700:], bad.iloc[700:], ["income", "segment"], algorithm, ALL_KNOBS)
    assert result.hyperparams == ALL_KNOBS
    assert result.to_dict()["hyperparams"]["l2_reg"] == 3.0


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
def test_refit_with_stored_hyperparams_reproduces_benchmark(algorithm):
    """Picking a benchmark result as the final model refits it from its
    stored hyperparams — that refit must be the same model, or the final
    model's metrics silently differ from the benchmark row it was picked from."""
    df, bad = _synthetic_credit_data()
    train_df, train_bad = df.iloc[:700], bad.iloc[:700]
    result = fit_ml_benchmark(train_df, train_bad, df.iloc[700:], bad.iloc[700:], ["income", "segment"], algorithm, ALL_KNOBS)

    stored = Hyperparams.from_dict(result.to_dict()["hyperparams"])
    model, categories = fit_model(train_df, train_bad, ["income", "segment"], algorithm, stored)
    refit_train = discrimination_metrics(train_bad, predict_bad_proba(model, train_df, ["income", "segment"], categories, algorithm))
    assert refit_train == result.sample_metrics["train"]


def test_hyperparameters_change_the_model():
    df, bad = _synthetic_credit_data(n=2000)
    args = (df.iloc[:1400], bad.iloc[:1400], df.iloc[1400:], bad.iloc[1400:], ["income", "segment"], "random_forest")
    shallow = fit_ml_benchmark(*args, Hyperparams(max_depth=2))
    deep = fit_ml_benchmark(*args, Hyperparams(max_depth=12))
    # a deep unconstrained forest fits train much harder than a stump-ish one
    assert deep.train_gini > shallow.train_gini + 0.1


def test_oot_metrics_reported_only_when_oot_given():
    df, bad = _synthetic_credit_data()
    base = (df.iloc[:600], bad.iloc[:600], df.iloc[600:800], bad.iloc[600:800], ["income", "segment"], "lightgbm")
    without = fit_ml_benchmark(*base)
    with_oot = fit_ml_benchmark(*base, oot_df=df.iloc[800:], oot_bad=bad.iloc[800:])
    assert without.sample_metrics["oot"] is None
    assert with_oot.sample_metrics["oot"]["n_total"] == 200
    assert with_oot.sample_metrics["test"] == without.sample_metrics["test"]


def test_hyperparams_from_dict_ignores_nulls_and_unknown_keys():
    params = Hyperparams.from_dict({"max_depth": 5, "learning_rate": None, "bogus": 1})
    assert params == Hyperparams(max_depth=5)
