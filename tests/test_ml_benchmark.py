import numpy as np
import pandas as pd

from credittool_engine.modeling import fit_ml_benchmark


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


def test_ml_benchmark_reports_discriminative_auc():
    df, bad = _synthetic_credit_data()
    train_df, test_df = df.iloc[:700], df.iloc[700:]
    train_bad, test_bad = bad.iloc[:700], bad.iloc[700:]

    result = fit_ml_benchmark(train_df, train_bad, test_df, test_bad, variables=["income", "segment"])

    assert result.train_auc > 0.55
    assert result.test_auc > 0.5
    assert np.isclose(result.train_gini, 2 * result.train_auc - 1, atol=1e-3)


def test_ml_benchmark_feature_importance_covers_all_variables():
    df, bad = _synthetic_credit_data()
    train_df, test_df = df.iloc[:700], df.iloc[700:]
    train_bad, test_bad = bad.iloc[:700], bad.iloc[700:]

    result = fit_ml_benchmark(train_df, train_bad, test_df, test_bad, variables=["income", "segment"])

    variables_in_importance = {f.variable for f in result.feature_importance}
    assert variables_in_importance == {"income", "segment"}
    assert all(f.mean_abs_shap >= 0 for f in result.feature_importance)
    # sorted descending by importance
    importances = [f.mean_abs_shap for f in result.feature_importance]
    assert importances == sorted(importances, reverse=True)


def test_ml_benchmark_handles_single_class_test_sample():
    df, bad = _synthetic_credit_data(n=200)
    train_df, test_df = df.iloc[:150], df.iloc[150:]
    train_bad = bad.iloc[:150]
    test_bad = pd.Series([0.0] * 50)  # degenerate: no bads in test

    result = fit_ml_benchmark(train_df, train_bad, test_df, test_bad, variables=["income", "segment"])
    assert result.test_auc == 0.5
    assert result.test_gini == 0.0
