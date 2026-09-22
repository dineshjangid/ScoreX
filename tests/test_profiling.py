import pandas as pd

from credittool_engine.data import profile_dataframe


def test_profile_numeric_and_categorical_columns():
    df = pd.DataFrame(
        {
            "age": [25, 30, 35, None, 40],
            "segment": ["A", "A", "B", "B", "B"],
        }
    )

    profile = profile_dataframe(df)

    assert profile["n_rows"] == 5
    assert profile["n_columns"] == 2

    age_profile = next(c for c in profile["columns"] if c["name"] == "age")
    assert age_profile["kind"] == "numeric"
    assert age_profile["missing_count"] == 1
    assert age_profile["stats"]["min"] == 25
    assert age_profile["stats"]["max"] == 40

    segment_profile = next(c for c in profile["columns"] if c["name"] == "segment")
    assert segment_profile["kind"] == "categorical"
    assert segment_profile["n_unique"] == 2
    top_values = {v["value"]: v["count"] for v in segment_profile["top_values"]}
    assert top_values == {"A": 2, "B": 3}


def test_profile_handles_all_missing_column():
    df = pd.DataFrame({"empty": [None, None, None]})
    profile = profile_dataframe(df)
    col = profile["columns"][0]
    assert col["missing_count"] == 3
    assert col["missing_pct"] == 100.0
    assert "stats" not in col
    assert "top_values" not in col
