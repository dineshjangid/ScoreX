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


def generate_ml_scoring_python(
    algorithm: str,
    variables: list[str],
    categories: dict[str, list[str]],
    mode: str,
) -> str:
    """Standalone scoring script for an ML final model (XGBoost/Random
    Forest/LightGBM/CatBoost). Unlike the logistic scorecard's points
    formula, this can't be inlined as arithmetic — it needs the actual
    fitted model object, downloaded separately as final_model.joblib and
    expected alongside this script. What IS generated here is the exact
    feature-encoding this project's final model was trained on (so new
    data is encoded identically) plus the call to score it.
    """
    lines = [
        "import joblib",
        "import pandas as pd",
        "",
        f"# Fitted {algorithm} model, downloaded from this project's Reporting step",
        '# ("Download model file") and placed next to this script.',
        'MODEL_PATH = "final_model.joblib"',
        "",
        f"VARIABLES = {variables!r}",
        "",
        "# Categories seen at training time for each non-numeric variable —",
        "# needed to encode new data exactly the way the model was trained,",
        "# including mapping any category unseen at training time to \"missing\".",
        f"CATEGORIES = {categories!r}",
        "",
        f'FEATURE_MODE = {mode!r}  # "category" | "raw_str" | "ordinal"',
        "",
        "",
        "def _encode(df: pd.DataFrame) -> pd.DataFrame:",
        "    X = df[VARIABLES].copy()",
        "    for col, cats in CATEGORIES.items():",
        "        col_str = X[col].astype(str)",
        "        if FEATURE_MODE == \"raw_str\":",
        "            X[col] = col_str",
        "        else:",
        "            # Map anything unseen at training time to NaN before",
        "            # categorizing, rather than passing an out-of-vocabulary",
        "            # value straight to pd.Categorical.",
        "            known = col_str.where(col_str.isin(cats))",
        "            cat = pd.Categorical(known, categories=cats)",
        "            X[col] = cat if FEATURE_MODE == \"category\" else cat.codes",
        "    return X",
        "",
        "",
        "def score_applications(df: pd.DataFrame) -> pd.Series:",
        '    """Returns a 0-1000 safety score per row (higher = safer), the',
        "    same convention as this tool's points scorecards.",
        '    """',
        "    model = joblib.load(MODEL_PATH)",
        "    p_bad = model.predict_proba(_encode(df))[:, 1]",
        "    score = pd.Series((1 - p_bad) * 1000, index=df.index)",
        "    return score.round().astype(int)",
    ]
    return "\n".join(lines)
