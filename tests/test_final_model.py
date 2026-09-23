import numpy as np
import pandas as pd
import pytest

from credittool_engine.modeling import (
    ALL_ALGORITHMS,
    apply_feature_encoding,
    categorical_categories,
    fit_model,
    load_model,
    predict_bad_proba,
    save_model,
)
from credittool_engine.reason_codes import compute_shap_contributions, compute_shap_reason_codes
from credittool_engine.scoring import compute_ml_scores


def _synthetic_credit_data(n=600, seed=0):
    rng = np.random.default_rng(seed)
    income = rng.normal(50000, 15000, n)
    segment = rng.choice(["A", "B", "C"], n)
    segment_risk = np.where(segment == "C", 0.3, np.where(segment == "B", 0.1, -0.1))
    logit_bad = -0.00003 * (income - 50000) + segment_risk
    p_bad = 1 / (1 + np.exp(-logit_bad))
    bad = (rng.uniform(size=n) < p_bad).astype(float)
    df = pd.DataFrame({"income": income, "segment": segment})
    return df, pd.Series(bad)


def test_categorical_categories_only_covers_non_numeric():
    df, _ = _synthetic_credit_data()
    cats = categorical_categories(df, ["income", "segment"])
    assert set(cats.keys()) == {"segment"}
    assert set(cats["segment"]) == {"A", "B", "C"}


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
def test_apply_feature_encoding_maps_unseen_category(algorithm):
    from credittool_engine.modeling import FEATURE_MODE

    df, _ = _synthetic_credit_data()
    variables = ["income", "segment"]
    cats = categorical_categories(df, variables)

    new_df = pd.DataFrame({"income": [50000.0], "segment": ["Z"]})  # "Z" unseen at training
    encoded = apply_feature_encoding(new_df, variables, cats, FEATURE_MODE[algorithm])

    mode = FEATURE_MODE[algorithm]
    if mode == "ordinal":
        assert encoded["segment"].iloc[0] == -1
    elif mode == "category":
        assert pd.isna(encoded["segment"].iloc[0])
    else:  # raw_str
        assert encoded["segment"].iloc[0] == "Z"


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
def test_fit_model_and_predict_bad_proba_discriminates(algorithm):
    df, bad = _synthetic_credit_data()
    train_df, test_df = df.iloc[:400], df.iloc[400:]
    train_bad, test_bad = bad.iloc[:400], bad.iloc[400:]
    variables = ["income", "segment"]

    model, categories = fit_model(train_df, train_bad, variables, algorithm)
    p_bad = predict_bad_proba(model, test_df, variables, categories, algorithm)

    assert len(p_bad) == len(test_df)
    assert p_bad.between(0, 1).all()
    from sklearn.metrics import roc_auc_score

    assert roc_auc_score(test_bad, p_bad) > 0.5


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
def test_save_and_load_model_round_trip(algorithm, tmp_path):
    df, bad = _synthetic_credit_data()
    variables = ["income", "segment"]
    model, categories = fit_model(df, bad, variables, algorithm)

    path = tmp_path / "final_model.joblib"
    save_model(model, path)
    loaded = load_model(path)

    original = predict_bad_proba(model, df, variables, categories, algorithm)
    restored = predict_bad_proba(loaded, df, variables, categories, algorithm)
    assert np.allclose(original.values, restored.values)


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
def test_predict_bad_proba_handles_empty_frame(algorithm):
    # An unused OOT sample is an empty dataframe — some libraries (LightGBM)
    # reject an empty 2D input outright rather than returning an empty
    # prediction, so this must be handled before calling predict_proba.
    df, bad = _synthetic_credit_data()
    variables = ["income", "segment"]
    model, categories = fit_model(df, bad, variables, algorithm)

    empty = df.iloc[0:0]
    result = predict_bad_proba(model, empty, variables, categories, algorithm)
    assert len(result) == 0


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
def test_compute_ml_scores_is_safety_score_0_to_1000(algorithm):
    df, bad = _synthetic_credit_data()
    variables = ["income", "segment"]
    model, categories = fit_model(df, bad, variables, algorithm)

    scores = compute_ml_scores(df, variables, model, categories, algorithm)
    assert scores.between(0, 1000).all()

    # Higher predicted P(bad) should map to a lower (riskier) safety score.
    p_bad = predict_bad_proba(model, df, variables, categories, algorithm)
    worst = p_bad.idxmax()
    best = p_bad.idxmin()
    assert scores.loc[worst] <= scores.loc[best]


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
def test_shap_reason_codes_pick_highest_contribution_first(algorithm):
    df, bad = _synthetic_credit_data()
    variables = ["income", "segment"]
    model, categories = fit_model(df, bad, variables, algorithm)

    contributions = compute_shap_contributions(df, variables, model, categories, algorithm)
    assert list(contributions.columns) == variables
    assert len(contributions) == len(df)

    reasons = compute_shap_reason_codes(contributions, top_n=2)
    for idx in df.index[:20]:
        row = contributions.loc[idx]
        top_var = reasons.loc[idx, "reason_1"]
        assert row[top_var] == row.max()
