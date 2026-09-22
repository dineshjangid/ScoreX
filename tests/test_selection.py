import numpy as np
import pandas as pd

from credittool_engine.selection import select_variables


def _synthetic_woe_frame(n=1000, seed=0):
    rng = np.random.default_rng(seed)
    strong = rng.normal(size=n)
    duplicate_of_strong = strong + rng.normal(scale=0.01, size=n)  # near-identical, highly correlated
    weak = rng.normal(size=n) * 0.01  # negligible signal
    independent = rng.normal(size=n)

    frame = pd.DataFrame(
        {
            "strong_var": strong,
            "duplicate_var": duplicate_of_strong,
            "weak_var": weak,
            "independent_var": independent,
        }
    )
    iv_by_variable = {
        "strong_var": 0.4,
        "duplicate_var": 0.35,
        "weak_var": 0.01,
        "independent_var": 0.15,
    }
    return frame, iv_by_variable


def test_low_iv_variable_is_dropped():
    frame, iv = _synthetic_woe_frame()
    result = select_variables(frame, iv, min_iv=0.02, max_corr=0.95, max_vif=100)

    assert "weak_var" not in result.selected
    reasons = {d["variable"]: d["reason"] for d in result.dropped}
    assert "IV" in reasons["weak_var"]


def test_highly_correlated_variable_drops_the_lower_iv_one():
    frame, iv = _synthetic_woe_frame()
    result = select_variables(frame, iv, min_iv=0.02, max_corr=0.7, max_vif=100)

    assert "strong_var" in result.selected
    assert "duplicate_var" not in result.selected
    reasons = {d["variable"]: d["reason"] for d in result.dropped}
    assert "correlated" in reasons["duplicate_var"]


def test_independent_variable_survives_all_filters():
    frame, iv = _synthetic_woe_frame()
    result = select_variables(frame, iv, min_iv=0.02, max_corr=0.7, max_vif=100)
    assert "independent_var" in result.selected


def test_final_vif_and_correlation_reported_for_selected():
    frame, iv = _synthetic_woe_frame()
    result = select_variables(frame, iv, min_iv=0.02, max_corr=0.7, max_vif=100)
    assert set(result.vif.keys()) == set(result.selected)
    assert set(result.correlation_matrix.keys()) == set(result.selected)
