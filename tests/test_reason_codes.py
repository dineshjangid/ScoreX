import pandas as pd

from credittool_engine.reason_codes import compute_reason_codes, compute_variable_contributions


def _binning_variables():
    return {
        "income": {
            "kind": "numeric",
            "cutpoints": [50000.0],
            "bins": [
                {"label": "(-inf, 50000.0]", "woe": -0.5},
                {"label": "(50000.0, inf]", "woe": 0.5},
            ],
        },
        "age": {
            "kind": "numeric",
            "cutpoints": [30.0],
            "bins": [
                {"label": "(-inf, 30.0]", "woe": -0.3},
                {"label": "(30.0, inf]", "woe": 0.3},
            ],
        },
    }


def test_contributions_reflect_coefficient_and_woe_sign():
    df = pd.DataFrame({"income": [10000.0, 90000.0], "age": [20.0, 40.0]})
    fitted_params = {"const": -1.0, "income": -0.8, "age": -0.5}
    factor = 28.85

    contributions = compute_variable_contributions(df, _binning_variables(), fitted_params, factor)

    # low income (negative WOE) with negative coefficient -> negative points
    assert contributions.loc[0, "income"] < 0
    # high income (positive WOE) with negative coefficient -> positive points
    assert contributions.loc[1, "income"] > 0


def test_reason_codes_rank_lowest_contribution_first():
    df = pd.DataFrame({"income": [10000.0], "age": [40.0]})
    fitted_params = {"const": -1.0, "income": -0.8, "age": -0.5}
    factor = 28.85

    contributions = compute_variable_contributions(df, _binning_variables(), fitted_params, factor)
    reasons = compute_reason_codes(contributions, top_n=2)

    # income is low (bad for the applicant) -> should be reason_1
    assert reasons.loc[0, "reason_1"] == "income"
    assert reasons.loc[0, "reason_1_points"] < reasons.loc[0, "reason_2_points"]


def test_reason_codes_handles_top_n_larger_than_variable_count():
    df = pd.DataFrame({"income": [10000.0], "age": [40.0]})
    fitted_params = {"const": -1.0, "income": -0.8, "age": -0.5}
    contributions = compute_variable_contributions(df, _binning_variables(), fitted_params, 28.85)
    reasons = compute_reason_codes(contributions, top_n=5)

    assert reasons.loc[0, "reason_3"] is None
    assert reasons.loc[0, "reason_3_points"] is None
