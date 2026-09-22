import pandas as pd

from credittool_engine.target import TargetDefinition, apply_target_definition, target_summary


def test_values_mode_binary_column():
    df = pd.DataFrame({"delinquent_90dpd": [0, 1, 0, 1, 0]})
    target_def = TargetDefinition(target_column="delinquent_90dpd", mode="values", bad_values=["1"])

    bad_flag = apply_target_definition(df, target_def)

    assert list(bad_flag) == [0, 1, 0, 1, 0]
    summary = target_summary(bad_flag)
    assert summary == {"n_total": 5, "n_good": 3, "n_bad": 2, "n_excluded": 0, "bad_rate_pct": 40.0}


def test_threshold_mode_treats_non_numeric_as_excluded():
    df = pd.DataFrame({"dpd": [0, 45, 90, 120, None]})
    target_def = TargetDefinition(target_column="dpd", mode="threshold", threshold=90)

    bad_flag = apply_target_definition(df, target_def)
    summary = target_summary(bad_flag)

    assert summary["n_bad"] == 2  # 90 and 120
    assert summary["n_good"] == 2  # 0 and 45
    assert summary["n_excluded"] == 1  # the NaN dpd row is not a valid numeric value


def test_exclude_values_removes_rows_from_good_and_bad():
    df = pd.DataFrame({"outcome": ["good", "bad", "reject", "good", "bad"]})
    target_def = TargetDefinition(target_column="outcome", mode="values", bad_values=["bad"], exclude_values=["reject"])

    bad_flag = apply_target_definition(df, target_def)
    summary = target_summary(bad_flag)

    assert summary == {"n_total": 5, "n_good": 2, "n_bad": 2, "n_excluded": 1, "bad_rate_pct": 50.0}


def test_exclude_column_separate_from_target_column():
    df = pd.DataFrame(
        {
            "dpd": [0, 90, 0, 90, 0],
            "decision": ["approved", "approved", "declined", "approved", "declined"],
        }
    )
    target_def = TargetDefinition(
        target_column="dpd",
        mode="threshold",
        threshold=90,
        exclude_values=["declined"],
        exclude_column="decision",
    )

    bad_flag = apply_target_definition(df, target_def)
    summary = target_summary(bad_flag)

    # rows 2 and 4 (declined) excluded regardless of their dpd value;
    # remaining: row 0 good, rows 1 and 3 bad
    assert summary == {"n_total": 5, "n_good": 1, "n_bad": 2, "n_excluded": 2, "bad_rate_pct": 66.67}
