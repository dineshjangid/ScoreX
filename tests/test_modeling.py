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


def _signal_plus_noise(n=3000, seed=2):
    rng = np.random.default_rng(seed)
    woe_signal = rng.normal(size=n)
    woe_noise = rng.normal(size=n)
    p_bad = 1 / (1 + np.exp(-(-1.2 * woe_signal - 1.0)))
    bad = pd.Series((rng.uniform(size=n) < p_bad).astype(float))
    return pd.DataFrame({"woe_signal": woe_signal, "woe_noise": woe_noise}), bad


def test_unpenalised_fit_keeps_full_diagnostics():
    frame, bad = _signal_plus_noise()
    model = fit_logistic_regression(frame, bad, ["woe_signal", "woe_noise"])
    assert model.penalty == "none" and model.dropped_variables == []
    assert all(c.p_value is not None and c.std_error is not None for c in model.coefficients)


def test_zero_alpha_is_the_plain_fit():
    frame, bad = _signal_plus_noise()
    plain = fit_logistic_regression(frame, bad, ["woe_signal", "woe_noise"])
    zero = fit_logistic_regression(frame, bad, ["woe_signal", "woe_noise"], penalty="l2", alpha=0.0)
    assert zero.fitted_params == plain.fitted_params
    assert zero.penalty == "none"


def test_l2_penalty_shrinks_coefficients_and_drops_p_values():
    frame, bad = _signal_plus_noise()
    plain = fit_logistic_regression(frame, bad, ["woe_signal", "woe_noise"])
    ridge = fit_logistic_regression(frame, bad, ["woe_signal", "woe_noise"], penalty="l2", alpha=0.05)

    assert ridge.penalty == "l2" and ridge.alpha == 0.05
    assert abs(ridge.fitted_params["woe_signal"]) < abs(plain.fitted_params["woe_signal"])
    assert ridge.fitted_params["woe_signal"] < 0  # shrunk, not flipped
    assert ridge.variables == ["woe_signal", "woe_noise"]  # L2 never zeroes a variable out
    assert all(c.p_value is None and c.std_error is None and c.z_value is None for c in ridge.coefficients)
    assert ridge.log_likelihood < plain.log_likelihood  # penalised fit trades training fit for shrinkage


def test_l1_penalty_drops_the_noise_variable():
    frame, bad = _signal_plus_noise()
    lasso = fit_logistic_regression(frame, bad, ["woe_signal", "woe_noise"], penalty="l1", alpha=0.02)

    assert lasso.variables == ["woe_signal"]
    assert lasso.dropped_variables == ["woe_noise"]
    assert set(lasso.fitted_params) == {"const", "woe_signal"}
    assert [c.variable for c in lasso.coefficients] == ["woe_signal"]


def test_penalised_diagnostics_match_its_own_predictions():
    frame, bad = _signal_plus_noise()
    ridge = fit_logistic_regression(frame, bad, ["woe_signal", "woe_noise"], penalty="l2", alpha=0.05)

    p = predict_probability(frame, ridge.fitted_params).clip(1e-12, 1 - 1e-12)
    llf = float((bad * np.log(p) + (1 - bad) * np.log(1 - p)).sum())
    assert abs(ridge.log_likelihood - llf) < 1e-3
    assert abs(ridge.aic - (2 * 3 - 2 * llf)) < 1e-2
    assert 0 < ridge.pseudo_r2 < 1
