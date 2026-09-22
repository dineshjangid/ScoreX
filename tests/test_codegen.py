import numpy as np
import pandas as pd

from credittool_engine.reporting.codegen import generate_scoring_python, generate_scoring_sql
from credittool_engine.scaling import ScalingConfig, build_scorecard
from credittool_engine.scoring import compute_scores


def _fixture():
    binning_variables = {
        "income": {
            "kind": "numeric",
            "cutpoints": [50000.0],
            "bins": [
                {"label": "(-inf, 50000.0]", "woe": -0.5},
                {"label": "(50000.0, inf]", "woe": 0.5},
                {"label": "Missing", "woe": -0.8},
            ],
        },
        "segment": {
            "kind": "categorical",
            "categories_map": {"A": "A", "B": "B", "C": "Other"},
            "bins": [
                {"label": "A", "woe": 0.4},
                {"label": "B", "woe": 0.2},
                {"label": "Other", "woe": -0.6},
            ],
        },
    }
    fitted_params = {"const": -1.0, "income": -0.8, "segment": -0.6}
    config = ScalingConfig(pdo=20.0, base_score=600.0, base_odds=50.0)
    scorecard = build_scorecard(fitted_params, binning_variables, config).to_dict()
    return binning_variables, fitted_params, scorecard


def test_generated_python_matches_compute_scores():
    binning_variables, fitted_params, scorecard = _fixture()
    code = generate_scoring_python(scorecard, binning_variables)

    namespace: dict = {}
    exec(code, namespace)
    score_application = namespace["score_application"]

    df = pd.DataFrame(
        {
            "income": [10000.0, 90000.0, np.nan, 50000.0],
            "segment": ["A", "B", "C", "unseen_category"],
        }
    )
    expected = compute_scores(df, binning_variables, fitted_params, scorecard["factor"], scorecard["offset"])

    for i, row in df.iterrows():
        record = row.to_dict()
        # pandas NaN -> None, matching what a real caller would pass in
        record = {k: (None if pd.isna(v) else v) for k, v in record.items()}
        assert score_application(record) == expected.iloc[i]


def test_generated_sql_contains_all_variables_and_case_structure():
    binning_variables, _, scorecard = _fixture()
    sql = generate_scoring_sql(scorecard, binning_variables, table="loans")

    assert "income" in sql
    assert "segment" in sql
    assert sql.count("CASE") == 2
    assert sql.count("END") == 2
    assert "FROM loans" in sql
    assert str(scorecard["base_points"]) in sql


def test_generated_sql_escapes_quotes_in_category_values():
    binning_variables, _, scorecard = _fixture()
    binning_variables["segment"]["categories_map"]["A"] = "A"
    binning_variables["segment"]["categories_map"]["O'Brien"] = "Other"
    sql = generate_scoring_sql(scorecard, binning_variables)
    assert "O''Brien" in sql
