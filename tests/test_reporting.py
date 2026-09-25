import io

from openpyxl import load_workbook
from pypdf import PdfReader

from credittool_engine.reporting import build_excel_report, build_pdf_report


def _sample_report_data():
    return {
        "project_name": "Test Scorecard",
        "scorecard_type": "application",
        "target_definition": {"summary": {"n_total": 200, "n_good": 168, "n_bad": 32, "n_excluded": 0, "bad_rate_pct": 16.0}},
        "sampling": {"summary": {"train": {"n_total": 140, "bad_rate_pct": 15.7}, "test": {"n_total": 60, "bad_rate_pct": 16.6}}},
        "binning": {
            "variables": {
                "age": {"kind": "numeric", "iv": 0.12, "bins": [{"label": "(-inf, 44.0]", "woe": 0.2, "points": -12}]},
                "segment": {"kind": "categorical", "iv": 0.21, "bins": [{"label": "A", "woe": 0.4, "points": 11}]},
            }
        },
        "modeling": {
            "intercept": -1.68,
            "n_obs": 140,
            "pseudo_r2": 0.05,
            "coefficients": [{"variable": "age", "coefficient": -0.86, "std_error": 0.8, "z_value": -1.07, "p_value": 0.28}],
        },
        "scaling": {
            "base_points": 536,
            "min_score": 490,
            "max_score": 568,
            "variables": [{"variable": "age", "bins": [{"label": "(-inf, 44.0]", "woe": 0.2, "points": -12}]}],
        },
        "validation": {
            "train": {"n_total": 140, "bad_rate_pct": 15.7, "ks": 32.0, "auc": 0.64, "gini": 0.29},
            "test": {"n_total": 60, "bad_rate_pct": 16.6, "ks": 26.0, "auc": 0.41, "gini": -0.17},
            "oot": None,
            "psi_test_vs_train": {"index": 0.29, "buckets": []},
        },
    }


def test_excel_report_has_expected_sheets_and_content():
    report_bytes = build_excel_report(_sample_report_data())
    wb = load_workbook(io.BytesIO(report_bytes))

    assert wb.sheetnames == ["Summary", "Binning & IV", "Model", "Scorecard"]

    binning_ws = wb["Binning & IV"]
    values = [row[0].value for row in binning_ws.iter_rows(min_row=2, max_col=1)]
    assert "age" in values
    assert "segment" in values

    scorecard_ws = wb["Scorecard"]
    assert scorecard_ws["A1"].value == "Base points"
    assert scorecard_ws["B1"].value == 536


def test_pdf_report_builds_and_contains_project_name():
    report_bytes = build_pdf_report(_sample_report_data())
    assert report_bytes[:4] == b"%PDF"

    reader = PdfReader(io.BytesIO(report_bytes))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Test Scorecard" in text
    assert "Validation" in text


def test_pdf_report_handles_missing_optional_sections():
    data = _sample_report_data()
    data["validation"] = None
    report_bytes = build_pdf_report(data)
    assert report_bytes[:4] == b"%PDF"


def _penalised_report_data():
    data = _sample_report_data()
    data["modeling"].update(
        penalty="l1",
        alpha=0.02,
        dropped_variables=["segment"],
        coefficients=[{"variable": "age", "coefficient": -0.5, "std_error": None, "z_value": None, "p_value": None}],
    )
    return data


def test_excel_report_marks_penalised_fit():
    wb = load_workbook(io.BytesIO(build_excel_report(_penalised_report_data())))
    rows = [[c.value for c in row] for row in wb["Model"].iter_rows()]
    assert ["age", -0.5, "n/a", "n/a", "n/a"] in rows
    assert ["Penalty", "L1", "alpha", 0.02] in [r[:4] for r in rows]
    assert ["Dropped by penalty", "segment"] in [r[:2] for r in rows]


def test_pdf_report_marks_penalised_fit():
    reader = PdfReader(io.BytesIO(build_pdf_report(_penalised_report_data())))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "None" not in text
    assert "n/a" in text
    assert "L1 penalty" in text and "segment" in text
