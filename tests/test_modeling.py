import numpy as np
import pandas as pd

from credittool_engine.modeling import fit_logistic_regression, predict_probability


def _synthetic_woe_and_target(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    # WOE-like predictor: positive means safer, so it should get a
    # negative coefficient when predicting P(bad).
    woe = rng.normal(size=n)
    logit_bad = -1.5 * woe - 0.5
    p_bad = 1 / (1 + np.exp(-logit_bad))
    bad = (rng.uniform(size=n) < p_bad).astype(float)
    return pd.DataFrame({"woe_income": woe}), pd.Series(bad)


def test_coefficient_sign_matches_woe_convention():
    frame, bad = _synthetic_woe_and_target()
    model = fit_logistic_regression(frame, bad, ["woe_income"])

    coef = next(c for c in model.coefficients if c.variable == "woe_income")
    assert coef.coefficient < 0  # higher WOE (safer) -> lower P(bad)
    assert coef.p_value < 0.01  # strong synthetic signal should be significant


def test_model_reports_fit_diagnostics():
    frame, bad = _synthetic_woe_and_target()
    model = fit_logistic_regression(frame, bad, ["woe_income"])

    assert model.n_obs == len(frame)
    assert model.pseudo_r2 > 0
    assert "const" in model.fitted_params
    assert "woe_income" in model.fitted_params


def test_predict_probability_matches_fitted_values():
    frame, bad = _synthetic_woe_and_target()
    model = fit_logistic_regression(frame, bad, ["woe_income"])

    predicted = predict_probability(frame, model.fitted_params)
    assert predicted.between(0, 1).all()
    # Higher WOE should correlate with lower predicted P(bad).
    assert predicted.corr(frame["woe_income"]) < 0


def test_multi_variable_model_fits():
    rng = np.random.default_rng(1)
    n = 1000
    woe_a = rng.normal(size=n)
    woe_b = rng.normal(size=n)
    logit_bad = -1.0 * woe_a - 0.5 * woe_b
    p_bad = 1 / (1 + np.exp(-logit_bad))
    bad = pd.Series((rng.uniform(size=n) < p_bad).astype(float))
    frame = pd.DataFrame({"woe_a": woe_a, "woe_b": woe_b})

    model = fit_logistic_regression(frame, bad, ["woe_a", "woe_b"])
    assert len(model.coefficients) == 2
    assert all(c.coefficient < 0 for c in model.coefficients)
