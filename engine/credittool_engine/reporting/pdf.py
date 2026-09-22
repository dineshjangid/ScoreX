"""A scorecard development report as PDF: methodology summary, target/
sampling, variable list with IV, model coefficients, and validation
metrics — the audit trail a model risk / validation team would expect.
"""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_TABLE_STYLE = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f3ec")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e4e7")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]
)


def _table(headers: list[str], rows: list[list]) -> Table:
    table = Table([headers] + rows, repeatRows=1)
    table.setStyle(_TABLE_STYLE)
    return table


def build_pdf_report(data: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"Scorecard Development Report — {data['project_name']}", styles["Title"]))
    story.append(Paragraph(f"Scorecard type: {data['scorecard_type']}", styles["Normal"]))
    story.append(Spacer(1, 12))

    target = data.get("target_definition", {}).get("summary", {})
    if target:
        story.append(Paragraph("Target Definition", styles["Heading2"]))
        story.append(
            _table(
                ["Total", "Good", "Bad", "Excluded", "Bad rate %"],
                [[target.get("n_total"), target.get("n_good"), target.get("n_bad"), target.get("n_excluded"), target.get("bad_rate_pct")]],
            )
        )
        story.append(Spacer(1, 12))

    sampling = data.get("sampling", {}).get("summary", {})
    if sampling:
        story.append(Paragraph("Sampling", styles["Heading2"]))
        rows = [[label, s.get("n_total"), s.get("bad_rate_pct")] for label, s in sampling.items()]
        story.append(_table(["Sample", "N", "Bad rate %"], rows))
        story.append(Spacer(1, 12))

    binning_vars = data.get("binning", {}).get("variables", {})
    if binning_vars:
        story.append(Paragraph("Variable Information Value", styles["Heading2"]))
        rows = sorted(
            ([var, b["kind"], b["iv"], len(b["bins"])] for var, b in binning_vars.items()),
            key=lambda r: r[2],
            reverse=True,
        )
        story.append(_table(["Variable", "Kind", "IV", "N bins"], rows))
        story.append(Spacer(1, 12))

    model = data.get("modeling", {})
    if model:
        story.append(Paragraph("Logistic Regression Model", styles["Heading2"]))
        rows = [["(intercept)", model.get("intercept"), "", "", ""]]
        rows += [
            [c["variable"], c["coefficient"], c["std_error"], c["z_value"], c["p_value"]]
            for c in model.get("coefficients", [])
        ]
        story.append(_table(["Variable", "Coefficient", "Std error", "z", "p-value"], rows))
        story.append(Paragraph(f"Pseudo R²: {model.get('pseudo_r2')} — N obs: {model.get('n_obs')}", styles["Normal"]))
        story.append(Spacer(1, 12))

    scaling = data.get("scaling", {})
    if scaling:
        story.append(Paragraph("Points Scorecard", styles["Heading2"]))
        story.append(
            Paragraph(
                f"Base points: {scaling.get('base_points')} — Score range: {scaling.get('min_score')}–{scaling.get('max_score')}",
                styles["Normal"],
            )
        )
        rows = []
        for v in scaling.get("variables", []):
            for b in v["bins"]:
                rows.append([v["variable"], b["label"], b["woe"], b["points"]])
        story.append(_table(["Variable", "Bin", "WOE", "Points"], rows))
        story.append(Spacer(1, 12))

    validation = data.get("validation")
    if validation:
        story.append(Paragraph("Validation", styles["Heading2"]))
        rows = []
        for label in ("train", "test", "oot"):
            m = validation.get(label)
            if m:
                rows.append([label, m["n_total"], m["bad_rate_pct"], m["ks"], m["auc"], m["gini"]])
        story.append(_table(["Sample", "N", "Bad rate %", "KS", "AUC", "Gini"], rows))
        psi = validation.get("psi_test_vs_train")
        if psi:
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"PSI (test vs train): {psi['index']}", styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()
