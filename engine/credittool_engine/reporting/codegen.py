"""Generate standalone scoring code (Python function / SQL expression)
from a finished scorecard — no dependency on this package, so it can be
dropped into an external system for deployment.
"""
from __future__ import annotations


def generate_scoring_python(scorecard: dict, binning_variables: dict) -> str:
    lines = [
        "def score_application(record: dict) -> int:",
        '    """Auto-generated credit scorecard scoring function."""',
        f"    total = {scorecard['base_points']}",
    ]

    for var_points in scorecard["variables"]:
        var = var_points["variable"]
        binning = binning_variables[var]
        points_by_label = {b["label"]: b["points"] for b in var_points["bins"]}
        missing_points = points_by_label.get("Missing", 0)

        lines.append("")
        lines.append(f"    # --- {var} ---")
        lines.append(f"    value = record.get({var!r})")
        lines.append("    if value is None:")
        lines.append(f"        total += {missing_points}")
        lines.append("    else:")

        if binning["kind"] == "numeric":
            cutpoints = binning.get("cutpoints") or []
            numeric_bins = [b for b in var_points["bins"] if b["label"] != "Missing"]
            if cutpoints:
                for i, cutpoint in enumerate(cutpoints):
                    keyword = "if" if i == 0 else "elif"
                    lines.append(f"        {keyword} value <= {cutpoint}:")
                    lines.append(f"            total += {numeric_bins[i]['points']}")
                lines.append("        else:")
                lines.append(f"            total += {numeric_bins[-1]['points']}")
            else:
                lines.append(f"        total += {numeric_bins[-1]['points']}")
        else:
            categories_map = binning.get("categories_map") or {}
            other_points = points_by_label.get("Other", 0)
            points_by_raw = {raw: points_by_label.get(label, 0) for raw, label in categories_map.items()}
            lines.append(f"        _points_by_category = {points_by_raw!r}")
            lines.append(f"        total += _points_by_category.get(str(value), {other_points})")

    lines.append("")
    lines.append("    return total")
    return "\n".join(lines)


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def generate_scoring_sql(scorecard: dict, binning_variables: dict, table: str = "applicants") -> str:
    parts = [str(scorecard["base_points"])]

    for var_points in scorecard["variables"]:
        var = var_points["variable"]
        binning = binning_variables[var]
        points_by_label = {b["label"]: b["points"] for b in var_points["bins"]}
        missing_points = points_by_label.get("Missing", 0)

        case_lines = ["CASE", f"  WHEN {var} IS NULL THEN {missing_points}"]

        if binning["kind"] == "numeric":
            cutpoints = binning.get("cutpoints") or []
            numeric_bins = [b for b in var_points["bins"] if b["label"] != "Missing"]
            for i, cutpoint in enumerate(cutpoints):
                case_lines.append(f"  WHEN {var} <= {cutpoint} THEN {numeric_bins[i]['points']}")
            case_lines.append(f"  ELSE {numeric_bins[-1]['points']}")
        else:
            categories_map = binning.get("categories_map") or {}
            other_points = points_by_label.get("Other", 0)
            by_points: dict[int, list[str]] = {}
            for raw, label in categories_map.items():
                by_points.setdefault(points_by_label.get(label, 0), []).append(raw)
            for points, raws in by_points.items():
                quoted = ", ".join(_sql_quote(r) for r in raws)
                case_lines.append(f"  WHEN {var} IN ({quoted}) THEN {points}")
            case_lines.append(f"  ELSE {other_points}")

        case_lines.append("END")
        parts.append("(\n  " + "\n  ".join(case_lines) + "\n)")

    expr = " +\n  ".join(parts)
    return f"SELECT *,\n  {expr} AS credit_score\nFROM {table};"
