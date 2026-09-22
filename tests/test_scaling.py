import numpy as np
import pandas as pd

from credittool_engine.scaling import ScalingConfig, build_scorecard
from credittool_engine.scoring import compute_scores


def _simple_binning_variables():
    return {
        "income": {
            "kind": "numeric",
            "cutpoints": [50000.0],
            "bins": [
                {"label": "(-inf, 50000.0]", "woe": -0.5, "n_total": 50, "n_good": 20, "n_bad": 30, "bad_rate_pct": 60.0, "pct_of_total": 50.0},
                {"label": "(50000.0, inf]", "woe": 0.5, "n_total": 50, "n_good": 40, "n_bad": 10, "bad_rate_pct": 20.0, "pct_of_total": 50.0},
            ],
        },
    }


def test_offset_and_factor_match_standard_formula():
    config = ScalingConfig(pdo=20.0, base_score=600.0, base_odds=50.0)
    fitted_params = {"const": -1.0, "income": -0.8}
    scorecard = build_scorecard(fitted_params, _simple_binning_variables(), config)

    expected_factor = 20.0 / np.log(2)
    expected_offset = 600.0 - expected_factor * np.log(50.0)
    assert np.isclose(scorecard.factor, expected_factor)
    assert np.isclose(scorecard.offset, expected_offset)


def test_bin_points_use_negative_coefficient_convention():
    config = ScalingConfig(pdo=20.0, base_score=600.0, base_odds=50.0)
    fitted_params = {"const": -1.0, "income": -0.8}
    scorecard = build_scorecard(fitted_params, _simple_binning_variables(), config)

    income_points = next(v for v in scorecard.variables if v.variable == "income")
    low_bin = next(b for b in income_points.bins if b.label == "(-inf, 50000.0]")
    high_bin = next(b for b in income_points.bins if b.label == "(50000.0, inf]")

    # higher WOE (safer) with a negative coefficient -> more points
    assert high_bin.points > low_bin.points


def test_min_max_score_bounds_are_consistent():
    config = ScalingConfig(pdo=20.0, base_score=600.0, base_odds=50.0)
    fitted_params = {"const": -1.0, "income": -0.8}
    scorecard = build_scorecard(fitted_params, _simple_binning_variables(), config)
    assert scorecard.min_score <= scorecard.max_score


def test_compute_scores_matches_scorecard_bin_points():
    config = ScalingConfig(pdo=20.0, base_score=600.0, base_odds=50.0)
    fitted_params = {"const": -1.0, "income": -0.8}
    binning_variables = _simple_binning_variables()
    scorecard = build_scorecard(fitted_params, binning_variables, config)

    df = pd.DataFrame({"income": [10000.0, 90000.0]})
    scores = compute_scores(df, binning_variables, fitted_params, scorecard.factor, scorecard.offset)

    income_points = next(v for v in scorecard.variables if v.variable == "income")
    low_bin_points = next(b.points for b in income_points.bins if b.label == "(-inf, 50000.0]")
    high_bin_points = next(b.points for b in income_points.bins if b.label == "(50000.0, inf]")

    assert scores.iloc[0] == scorecard.base_points + low_bin_points
    assert scores.iloc[1] == scorecard.base_points + high_bin_points


def test_higher_pdo_widens_score_spread():
    fitted_params = {"const": -1.0, "income": -0.8}
    binning_variables = _simple_binning_variables()

    narrow = build_scorecard(fitted_params, binning_variables, ScalingConfig(pdo=10.0, base_score=600.0, base_odds=50.0))
    wide = build_scorecard(fitted_params, binning_variables, ScalingConfig(pdo=40.0, base_score=600.0, base_odds=50.0))

    assert (wide.max_score - wide.min_score) > (narrow.max_score - narrow.min_score)
