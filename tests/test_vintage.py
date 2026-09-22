import numpy as np
import pandas as pd

from credittool_engine.target import vintage_analysis


def test_vintage_bad_rate_per_monthly_cohort():
    dates = pd.to_datetime(["2024-01-15"] * 50 + ["2024-02-15"] * 50 + ["2024-03-15"] * 50)
    bad = pd.Series([1] * 10 + [0] * 40 + [1] * 20 + [0] * 30 + [1] * 5 + [0] * 45, dtype=float)
    df = pd.DataFrame({"origination_date": dates})

    rows = vintage_analysis(df, "origination_date", bad, freq="M")

    assert [r["cohort"] for r in rows] == ["2024-01", "2024-02", "2024-03"]
    assert rows[0]["n_total"] == 50
    assert rows[0]["n_bad"] == 10
    assert rows[0]["bad_rate_pct"] == 20.0
    assert rows[1]["bad_rate_pct"] == 40.0
    assert rows[2]["bad_rate_pct"] == 10.0


def test_vintage_excludes_rows_with_no_target_or_no_date():
    dates = pd.to_datetime(["2024-01-01", "2024-01-02", None, "2024-01-04"])
    bad = pd.Series([1.0, np.nan, 0.0, 0.0])
    df = pd.DataFrame({"date": dates})

    rows = vintage_analysis(df, "date", bad, freq="M")

    assert len(rows) == 1
    assert rows[0]["n_total"] == 2  # row 0 (bad=1) and row 3 (bad=0); rows 1 and 2 excluded


def test_vintage_returns_empty_list_when_no_valid_rows():
    df = pd.DataFrame({"date": [None, None]})
    bad = pd.Series([np.nan, np.nan])
    assert vintage_analysis(df, "date", bad) == []
