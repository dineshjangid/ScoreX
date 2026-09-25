"""The model development document as a renderer-neutral structure.

build_document() turns the project's report data into numbered sections of
simple blocks (headings, paragraphs, tables, figures...). The Word and PDF
renderers both walk the same structure, so the two formats never drift.
Sections without data (e.g. no OOT sample, no saved versions) are left out
rather than printed empty.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Union

from . import charts
from .narrative import NARRATIVE_FIELDS, resolve_narrative

# A test/OOT Gini more than this fraction below train is flagged (matches the app).
GINI_DROP_WARNING = 0.1

ALGORITHM_LABELS = {
    "logistic": "Logistic regression scorecard",
    "xgboost": "XGBoost",
    "random_forest": "Random Forest",
    "lightgbm": "LightGBM",
    "catboost": "CatBoost",
}
SAMPLE_LABELS = {"train": "Train", "test": "Test", "oot": "OOT"}


@dataclass
class Heading:
    text: str
    level: int  # 1 = section, 2 = subsection


@dataclass
class Paragraph:
    text: str
    style: str = "body"  # "body" | "note" | "narrative"


@dataclass
class Bullets:
    items: list[str]


@dataclass
class KeyValues:
    items: list[tuple[str, str]]


@dataclass
class Table:
    headers: list[str]
    rows: list[list[Any]]
    caption: str | None = None
    # Column indexes to right-align (numbers).
    numeric: list[int] = field(default_factory=list)


@dataclass
class Figure:
    png: bytes
    caption: str
    width_in: float = 6.2


@dataclass
class PageBreak:
    pass


Block = Union[Heading, Paragraph, Bullets, KeyValues, Table, Figure, PageBreak]


@dataclass
class Document:
    title: str
    subtitle: str
    meta: list[tuple[str, str]]
    blocks: list[Block]


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}".rstrip("0").rstrip(".") if abs(value) < 1e6 else f"{value:,.0f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _pct(value: Any) -> str:
    return "—" if value is None else f"{value}%"


def _iv_strength(iv: float) -> str:
    if iv < 0.02:
        return "Not predictive"
    if iv < 0.1:
        return "Weak"
    if iv < 0.3:
        return "Medium"
    if iv < 0.5:
        return "Strong"
    return "Suspicious (check for leakage)"


def _stability(index: float) -> str:
    if index < 0.1:
        return "Stable"
    if index < 0.25:
        return "Moderate shift"
    return "Significant shift"


def _gini_drop(train: dict | None, other: dict | None) -> float | None:
    if not train or not other or not train.get("gini") or train["gini"] <= 0:
        return None
    return (train["gini"] - other["gini"]) / train["gini"]


class _Builder:
    def __init__(self) -> None:
        self.blocks: list[Block] = []
        self.section = 0
        self.subsection = 0

    def h1(self, text: str) -> None:
        self.section += 1
        self.subsection = 0
        self.blocks.append(Heading(f"{self.section}  {text}", 1))

    def h2(self, text: str) -> None:
        self.subsection += 1
        self.blocks.append(Heading(f"{self.section}.{self.subsection}  {text}", 2))

    def appendix(self, letter: str, text: str) -> None:
        self.blocks.append(Heading(f"Appendix {letter}  {text}", 1))

    def add(self, *blocks: Block) -> None:
        self.blocks.extend(blocks)


def build_document(data: dict[str, Any]) -> Document:
    narrative = resolve_narrative(data)
    b = _Builder()

    final = data.get("final_model") or {}
    is_ml = final.get("source") == "ml_benchmark"
    final_name = ALGORITHM_LABELS.get(final.get("algorithm") or "logistic", str(final.get("algorithm")))
    validation = data.get("validation") or {}
    model = data.get("modeling") or {}
    binning_vars = (data.get("binning") or {}).get("variables") or {}
    selection = data.get("variable_selection") or {}
    model_vars = final.get("variables") or model.get("variables") or []

    _executive_summary(b, data, final_name, is_ml, validation, model)
    b.h1("Purpose and scope")
    b.add(Paragraph(narrative["purpose_scope"], "narrative"))
    _data_section(b, data, narrative)
    _target_section(b, data, narrative)
    _sampling_section(b, data)
    _characteristics_section(b, binning_vars, selection, model_vars)
    _selection_section(b, selection)
    _model_section(b, data, narrative, is_ml, final_name, model)
    if not is_ml:
        _scorecard_section(b, data.get("scaling") or {})
    _validation_section(b, validation)
    _reason_codes_section(b, data.get("reason_codes"), is_ml)
    _versions_section(b, data.get("versions") or [])
    b.h1("Limitations")
    b.add(Paragraph(narrative["limitations"], "narrative"))
    b.h1("Ongoing monitoring")
    b.add(Paragraph(narrative["monitoring_plan"], "narrative"))
    _appendices(b, data)

    generated_at = data.get("generated_at") or datetime.now().isoformat()
    meta = [
        ("Project", data.get("project_name", "")),
        ("Model type", str(data.get("scorecard_type", "")).replace("_", " ").title()),
        ("Final model", final_name),
        ("Generated", f"{generated_at[:16].replace('T', ' ')} by {data.get('generated_by', '—')}"),
    ]
    if data.get("project_created_at"):
        meta.append(("Project created", data["project_created_at"][:10]))
    return Document(
        title="Model Development Document",
        subtitle=data.get("project_name", ""),
        meta=meta,
        blocks=b.blocks,
    )


def _findings(data: dict, validation: dict, model: dict, is_ml: bool) -> list[str]:
    findings = []
    train = validation.get("train")
    for key, label in (("test", "Test"), ("oot", "OOT")):
        drop = _gini_drop(train, validation.get(key))
        if drop is not None and drop > GINI_DROP_WARNING:
            findings.append(
                f"{label} Gini is {drop * 100:.1f}% below train ({validation[key]['gini']} vs {train['gini']})"
                + (" — possible overfitting." if key == "test" else " — possible overfitting or population drift.")
            )
    for key, label in (("psi_test_vs_train", "test"), ("psi_oot_vs_train", "OOT")):
        psi = (validation.get(key) or {}).get("index")
        if psi is not None and psi >= 0.1:
            findings.append(f"Score PSI on the {label} sample is {psi} ({_stability(psi).lower()}).")
    for key, label in (("csi_test_vs_train", "test"), ("csi_oot_vs_train", "OOT")):
        shifted = [v for v, r in (validation.get(key) or {}).items() if r.get("index", 0) >= 0.1]
        if shifted:
            findings.append(f"CSI ≥ 0.1 on the {label} sample for: {', '.join(shifted)}.")
    if not is_ml and model:
        wrong = [c["variable"] for c in model.get("coefficients", []) if c["coefficient"] > 0]
        if wrong:
            findings.append(f"Coefficient sign contradicts the WOE direction for: {', '.join(wrong)}.")
        insignificant = [c["variable"] for c in model.get("coefficients", []) if c.get("p_value") is not None and c["p_value"] >= 0.05]
        if insignificant:
            findings.append(f"Not significant at 5%: {', '.join(insignificant)}.")
    if not validation.get("oot"):
        findings.append("No out-of-time sample was validated.")
    return findings


def _executive_summary(b: _Builder, data: dict, final_name: str, is_ml: bool, validation: dict, model: dict) -> None:
    b.h1("Executive summary")
    target = (data.get("target_definition") or {}).get("summary") or {}
    n_vars = len((data.get("final_model") or {}).get("variables") or (data.get("modeling") or {}).get("variables") or [])
    scaling = data.get("scaling") or {}
    model_type = str(data.get("scorecard_type", "")).replace("_", " ")
    article = "an" if model_type[:1].lower() in "aeiou" else "a"
    final_phrase = final_name[0].lower() + final_name[1:] if final_name.startswith("Logistic") else final_name
    summary = (
        f"This document describes the development of {data.get('project_name')}, {article} "
        f"{model_type} model. The final model is a {final_phrase} "
        f"using {n_vars} characteristics, developed on {_fmt(target.get('n_total'))} records with a bad rate of "
        f"{_pct(target.get('bad_rate_pct'))}."
    )
    if not is_ml and scaling.get("min_score") is not None:
        summary += f" Scores range from {scaling['min_score']} to {scaling['max_score']}."
    b.add(Paragraph(summary))

    rows = []
    for key in ("train", "test", "oot"):
        m = validation.get(key)
        if m:
            rows.append([SAMPLE_LABELS[key], _fmt(m["n_total"]), _pct(m["bad_rate_pct"]), _fmt(m["ks"]), _fmt(m["auc"]), _fmt(m["gini"])])
    if rows:
        b.add(Table(["Sample", "N", "Bad rate", "KS", "AUC", "Gini"], rows, "Headline performance", numeric=[1, 2, 3, 4, 5]))
    else:
        b.add(Paragraph("Validation has not been run; performance figures are unavailable.", "note"))

    findings = _findings(data, validation, model, is_ml)
    b.add(Paragraph("Findings for review:" if findings else "No issues were flagged by the automated checks."))
    if findings:
        b.add(Bullets(findings))


def _data_section(b: _Builder, data: dict, narrative: dict) -> None:
    profile = data.get("data_profile") or {}
    b.h1("Data")
    b.h2("Sources")
    b.add(Paragraph(narrative["data_sources"], "narrative"))
    if profile:
        b.h2("Development dataset")
        b.add(
            KeyValues(
                [
                    ("File", str(profile.get("original_filename", "—"))),
                    ("Records", _fmt(profile.get("n_rows"))),
                    ("Columns", _fmt(profile.get("n_columns"))),
                ]
            )
        )
        rows = [
            [c["name"], c["kind"], f"{c.get('missing_pct', 0)}%", _fmt(c.get("n_unique"))]
            for c in profile.get("columns", [])
        ]
        if rows:
            b.add(Table(["Column", "Type", "Missing", "Distinct values"], rows, "Column profile", numeric=[2, 3]))
    b.h2("Exclusions")
    b.add(Paragraph(narrative["exclusions"], "narrative"))


def _target_section(b: _Builder, data: dict, narrative: dict) -> None:
    target = data.get("target_definition") or {}
    definition = target.get("definition") or {}
    summary = target.get("summary") or {}
    b.h1("Target definition")
    if definition:
        items = [("Target column", str(definition.get("target_column")))]
        if definition.get("mode") == "threshold":
            items.append(("Bad when", f"≥ {definition.get('threshold')}"))
        else:
            items.append(("Bad values", ", ".join(map(str, definition.get("bad_values") or [])) or "—"))
        if definition.get("exclude_values"):
            items.append(("Excluded values", f"{', '.join(map(str, definition['exclude_values']))} (in {definition.get('exclude_column') or definition.get('target_column')})"))
        if definition.get("performance_window_months"):
            items.append(("Performance window", f"{definition['performance_window_months']} months from {definition.get('observation_date_column')}"))
        b.add(KeyValues(items))
    if summary:
        b.add(
            Table(
                ["Total", "Good", "Bad", "Excluded", "Bad rate"],
                [[_fmt(summary.get("n_total")), _fmt(summary.get("n_good")), _fmt(summary.get("n_bad")), _fmt(summary.get("n_excluded")), _pct(summary.get("bad_rate_pct"))]],
                "Outcome counts",
                numeric=[0, 1, 2, 3, 4],
            )
        )
    b.h2("Rationale")
    b.add(Paragraph(narrative["target_rationale"], "narrative"))


def _sampling_section(b: _Builder, data: dict) -> None:
    sampling = data.get("sampling") or {}
    config = sampling.get("config") or {}
    summary = sampling.get("summary") or {}
    if not sampling:
        return
    b.h1("Sampling")
    if config.get("test_size") is not None:
        test_pct = int(round(config["test_size"] * 100))
        method = f"Records were split at random into train and test ({100 - test_pct}/{test_pct}"
        method += f", seed {config['random_state']})" if config.get("random_state") is not None else ")"
        if config.get("oot_size"):
            how = (
                f"the most recent {config['oot_size'] * 100:.0f}% by {config['date_column']}"
                if config.get("date_column")
                else f"a random {config['oot_size'] * 100:.0f}%"
            )
            method += f", after first holding out {how} as an out-of-time (OOT) sample"
        b.add(Paragraph(method + "."))
    rows = [
        [SAMPLE_LABELS.get(k, k.title()), _fmt(s.get("n_total")), _fmt(s.get("n_good")), _fmt(s.get("n_bad")), _pct(s.get("bad_rate_pct"))]
        for k, s in summary.items()
        if s and s.get("n_total")
    ]
    if rows:
        b.add(Table(["Sample", "N", "Good", "Bad", "Bad rate"], rows, "Sample composition", numeric=[1, 2, 3, 4]))


def _characteristics_section(b: _Builder, binning_vars: dict, selection: dict, model_vars: list[str]) -> None:
    if not binning_vars:
        return
    selected = set(selection.get("selected") or [])
    b.h1("Characteristic analysis")
    b.add(
        Paragraph(
            "Each candidate characteristic was binned and converted to weight of evidence, WOE = ln(%good / %bad); "
            "information value (IV) summarises its univariate predictive power."
        )
    )
    min_iv = (selection.get("config") or {}).get("min_iv")
    b.add(Figure(charts.iv_chart([(v, info["iv"], v in selected) for v, info in binning_vars.items()], min_iv), "Information value by characteristic (selected in blue)"))
    rows = [
        [v, info["kind"], _fmt(info["iv"]), _iv_strength(info["iv"]), len(info["bins"]), "Yes" if v in selected else "No"]
        for v, info in sorted(binning_vars.items(), key=lambda kv: kv[1]["iv"], reverse=True)
    ]
    b.add(Table(["Characteristic", "Type", "IV", "Strength", "Bins", "Selected"], rows, "Information value", numeric=[2, 4]))

    for var in model_vars:
        info = binning_vars.get(var)
        if not info:
            continue
        b.h2(f"Binning: {var}")
        b.add(
            Table(
                ["Bin", "N", "% of total", "Bad", "Bad rate", "WOE"],
                [[r["label"], _fmt(r["n_total"]), _pct(r.get("pct_of_total")), _fmt(r["n_bad"]), _pct(r["bad_rate_pct"]), _fmt(r["woe"])] for r in info["bins"]],
                f"{var} — IV {_fmt(info['iv'])}",
                numeric=[1, 2, 3, 4, 5],
            ),
            Figure(charts.bad_rate_by_bin_chart(info["bins"]), f"Bad rate by bin — {var}", 5.4),
        )


def _selection_section(b: _Builder, selection: dict) -> None:
    if not selection:
        return
    config = selection.get("config") or {}
    b.h1("Variable selection")
    b.add(
        Paragraph(
            f"Characteristics were screened on IV ≥ {config.get('min_iv')}, then for multicollinearity: pairwise correlation ≤ "
            f"{config.get('max_corr')} and variance inflation factor (VIF) ≤ {config.get('max_vif')}. "
            f"{len(selection.get('selected') or [])} characteristics passed."
        )
    )
    vif = selection.get("vif") or {}
    rows = [[v, _fmt(vif.get(v), 2)] for v in selection.get("selected") or []]
    if rows:
        b.add(Table(["Selected characteristic", "VIF"], rows, "Selected characteristics", numeric=[1]))
    dropped = selection.get("dropped") or []
    if dropped:
        b.add(Table(["Dropped characteristic", "Reason"], [[d["variable"], d["reason"]] for d in dropped], "Characteristics dropped at selection"))


def _model_section(b: _Builder, data: dict, narrative: dict, is_ml: bool, final_name: str, model: dict) -> None:
    b.h1("Model development")
    b.h2("Methodology")
    method = (
        "A logistic regression predicting the probability of bad was fitted on the WOE-transformed characteristics of the "
        "training sample, so each coefficient scales its characteristic's WOE."
    )
    if model.get("penalty", "none") != "none":
        method += (
            f" The fit used an {model['penalty'].upper()} penalty (α = {model.get('alpha')}) to limit overfitting; penalised "
            "estimates have no standard errors, so p-values are not reported."
        )
        if model.get("dropped_variables"):
            method += f" The penalty removed: {', '.join(model['dropped_variables'])}."
    if is_ml:
        method += (
            f" A {final_name} model fitted on the raw characteristics was benchmarked against it and chosen as the final model; "
            "it is scored directly from its predicted probability, without a points scorecard."
        )
    b.add(Paragraph(method))

    if model:
        b.h2("Logistic model estimates")
        rows = [["(intercept)", _fmt(model.get("intercept")), "", "", "", ""]]
        for c in model.get("coefficients", []):
            sign = "Wrong sign" if c["coefficient"] > 0 else ("Not significant" if c.get("p_value") is not None and c["p_value"] >= 0.05 else "OK")
            rows.append([c["variable"], _fmt(c["coefficient"]), _fmt(c.get("std_error")) if c.get("std_error") is not None else "n/a", _fmt(c.get("z_value")) if c.get("z_value") is not None else "n/a", _fmt(c.get("p_value")) if c.get("p_value") is not None else "n/a", sign])
        b.add(Table(["Characteristic", "Coefficient", "Std error", "z", "p-value", "Check"], rows, "Coefficients (negative = safer as WOE rises)", numeric=[1, 2, 3, 4]))
        b.add(KeyValues([("Observations", _fmt(model.get("n_obs"))), ("Log-likelihood", _fmt(model.get("log_likelihood"))), ("Pseudo R²", _fmt(model.get("pseudo_r2"))), ("AIC", _fmt(model.get("aic")))]))

    if is_ml:
        ml = data.get("ml_benchmark_result") or {}
        b.h2(f"{final_name} final model")
        params = ml.get("hyperparams") or {}
        if params:
            b.add(KeyValues([(k.replace("_", " ").capitalize(), "library default" if v is None else _fmt(v)) for k, v in params.items()]))
        importance = [[f["variable"], _fmt(f["mean_abs_shap"])] for f in ml.get("feature_importance", [])]
        if importance:
            b.add(Table(["Characteristic", "Mean |SHAP|"], importance, "Feature importance", numeric=[1]))

    candidates = data.get("candidates") or []
    if candidates:
        b.h2("Alternatives considered")
        b.add(Paragraph(f"{len(candidates)} candidate models were fitted during development. Active candidates are those carried forward to final model selection."))
        rows = []
        for c in candidates:
            m = c.get("sample_metrics") or {}
            rows.append(
                [
                    ALGORITHM_LABELS.get(c["kind"], c["kind"]).replace(" regression scorecard", ""),
                    _candidate_settings(c),
                    len(c.get("variables") or []),
                    _fmt((m.get("train") or {}).get("gini")),
                    _fmt((m.get("test") or {}).get("gini")),
                    _fmt((m.get("oot") or {}).get("gini")),
                    "Yes" if c.get("is_active") else "",
                ]
            )
        b.add(Table(["Model", "Settings", "Vars", "Train Gini", "Test Gini", "OOT Gini", "Active"], rows, "Candidate models (newest first)", numeric=[2, 3, 4, 5]))

    b.h2("Key modelling judgements")
    b.add(Paragraph(narrative["key_judgements"], "narrative"))


def _candidate_settings(c: dict) -> str:
    s = c.get("settings") or {}
    if c["kind"] == "logistic":
        return f"{s.get('penalty', 'none').upper()} α={s.get('alpha')}" if s.get("penalty", "none") != "none" else "No penalty"
    parts = [f"{s.get('n_estimators')} trees", f"depth {s.get('max_depth')}"]
    for key, label in (("learning_rate", "lr"), ("subsample", "subsample"), ("min_samples_leaf", "min leaf"), ("l2_reg", "L2")):
        if s.get(key) is not None:
            parts.append(f"{label} {s[key]}")
    return ", ".join(parts)


def _scorecard_section(b: _Builder, scaling: dict) -> None:
    if not scaling or scaling.get("not_applicable"):
        return
    config = scaling.get("config") or {}
    b.h1("Scorecard")
    if config:
        b.add(
            Paragraph(
            f"Log-odds were scaled so that {_fmt(config.get('base_score'))} points correspond to good:bad odds of {_fmt(config.get('base_odds'))}:1 "
            f"and every {_fmt(config.get('pdo'))} points double the odds (score = offset − factor × ln(odds of bad))."
            ),
            KeyValues(
                [
                    ("PDO", _fmt(config.get("pdo"))),
                    ("Base score / odds", f"{_fmt(config.get('base_score'))} at {_fmt(config.get('base_odds'))}:1"),
                    ("Factor", _fmt(scaling.get("factor"))),
                    ("Offset", _fmt(scaling.get("offset"))),
                ]
            ),
        )
    b.add(KeyValues([("Base points", _fmt(scaling.get("base_points"))), ("Score range", f"{scaling.get('min_score')} – {scaling.get('max_score')}")]))
    rows = [[v["variable"], bin_["label"], _fmt(bin_["woe"]), bin_["points"]] for v in scaling.get("variables", []) for bin_ in v["bins"]]
    if rows:
        b.add(Table(["Characteristic", "Attribute", "WOE", "Points"], rows, "Points table", numeric=[2, 3]))


def _validation_section(b: _Builder, validation: dict) -> None:
    b.h1("Validation")
    if not validation:
        b.add(Paragraph("Validation has not been run.", "note"))
        return
    b.h2("Discrimination")
    train = validation.get("train")
    rows = []
    for key in ("train", "test", "oot"):
        m = validation.get(key)
        if not m:
            continue
        drop = _gini_drop(train, m) if key != "train" else None
        if drop is None:
            flag = "—"
        elif drop > GINI_DROP_WARNING:
            flag = f"{drop * 100:.1f}% lower ⚠"
        else:
            flag = f"{drop * 100:.1f}% lower" if drop >= 0 else f"{-drop * 100:.1f}% higher"
        rows.append([SAMPLE_LABELS[key], _fmt(m["n_total"]), _pct(m["bad_rate_pct"]), _fmt(m["ks"]), _fmt(m["auc"]), _fmt(m["gini"]), flag])
    b.add(Table(["Sample", "N", "Bad rate", "KS", "AUC", "Gini", "Gini vs train"], rows, "Discrimination by sample", numeric=[1, 2, 3, 4, 5]))

    samples = validation.get("samples") or {"train": {"roc": validation.get("roc_train") or [], "decile_table": validation.get("decile_table_train") or [], "score_histogram": validation.get("score_histogram_train") or []}}
    if any(s["roc"] for s in samples.values()):
        b.add(Figure(charts.roc_chart({k: s["roc"] for k, s in samples.items()}), "ROC curve by sample", 3.4))

    b.h2("Calibration and rank ordering")
    labels = [r["score_range"] for r in samples["train"]["decile_table"]]
    if labels:
        b.add(
            Paragraph("Score buckets are train-sample deciles, riskiest first; test and OOT are bucketed on the same cut points."),
            Figure(
                charts.bucket_lines_chart(labels, {k: [r["bad_rate_pct"] if r["n_total"] else None for r in s["decile_table"]] for k, s in samples.items()}, "Bad rate %"),
                "Bad rate by score bucket",
            ),
        )
    for key, s in samples.items():
        if not s["decile_table"]:
            continue
        b.add(
            Table(
                ["Score range", "N", "Bad", "Bad rate", "% of bads"],
                [[r["score_range"], _fmt(r["n_total"]), _fmt(r["n_bad"]), _pct(r["bad_rate_pct"]) if r["n_total"] else "—", _pct(r["pct_of_total_bad"])] for r in s["decile_table"]],
                f"Decile table — {SAMPLE_LABELS[key]}",
                numeric=[1, 2, 3, 4],
            )
        )

    b.h2("Stability")
    hist_labels = [str(bin_["bin_start"]) for bin_ in samples["train"]["score_histogram"]]
    if hist_labels:
        b.add(
            Figure(
                charts.bucket_lines_chart(
                    hist_labels,
                    {k: [bin_.get("pct") if bin_.get("pct") is not None else None for bin_ in s["score_histogram"]] for k, s in samples.items()},
                    "% of sample",
                ),
                "Score distribution by sample",
            )
        )
    for key, label in (("psi_test_vs_train", "Test"), ("psi_oot_vs_train", "OOT")):
        psi = validation.get(key)
        if not psi:
            continue
        b.add(
            Paragraph(f"Population stability index, {label} vs train: {psi['index']} — {_stability(psi['index']).lower()} (below 0.1 stable, 0.1–0.25 moderate, above 0.25 significant)."),
            Table(
                ["Score bucket", "Train %", f"{label} %", "Contribution"],
                [[r["bucket"], _pct(r["reference_pct"]), _pct(r["comparison_pct"]), _fmt(r["contribution"])] for r in psi["buckets"]],
                f"PSI — {label} vs train",
                numeric=[1, 2, 3],
            ),
        )
    csi_test = validation.get("csi_test_vs_train") or {}
    csi_oot = validation.get("csi_oot_vs_train") or {}
    if csi_test:
        rows = []
        for var, r in csi_test.items():
            oot = csi_oot.get(var)
            worst = max(r["index"], oot["index"] if oot else 0)
            rows.append([var, _fmt(r["index"]), _fmt(oot["index"]) if oot else "—", _stability(worst)])
        if csi_oot:
            b.add(Table(["Characteristic", "CSI test", "CSI OOT", "Assessment"], rows, "Characteristic stability index", numeric=[1, 2]))
        else:
            b.add(Table(["Characteristic", "CSI test", "Assessment"], [[r[0], r[1], r[3]] for r in rows], "Characteristic stability index", numeric=[1]))


def _reason_codes_section(b: _Builder, reason_codes: dict | None, is_ml: bool) -> None:
    if not reason_codes:
        return
    b.h1("Adverse action reason codes")
    method = (
        "For each applicant, reasons are the characteristics contributing most to a high predicted risk, ranked by SHAP value."
        if is_ml
        else "For each applicant, reasons are the characteristics contributing the fewest (most negative) points to the score, from the points table's WOE-based points."
    )
    b.add(Paragraph(f"{method} The top {reason_codes.get('top_n')} reasons are returned for each of {_fmt(reason_codes.get('n_scored'))} scored records."))
    freq = reason_codes.get("reason_1_frequency")
    if freq:
        b.add(Table(["Characteristic", "Records where it is reason 1", "Share"], [[r["variable"], _fmt(r["count"]), _pct(r["pct"])] for r in freq], "Most frequent primary reason", numeric=[1, 2]))


def _versions_section(b: _Builder, versions: list[dict]) -> None:
    if not versions:
        return
    b.h1("Champion and challenger versions")
    rows = [
        [f"v{v['version_number']}", v.get("label") or "", "Champion" if v.get("is_champion") else "", str(v.get("created_at", ""))[:10], v.get("n_variables"), _fmt(v.get("train_ks")), _fmt(v.get("train_gini")), v.get("score_range") or "—"]
        for v in versions
    ]
    b.add(Table(["Version", "Label", "Status", "Saved", "Vars", "Train KS", "Train Gini", "Score range"], rows, "Saved model versions", numeric=[4, 5, 6]))


def _appendices(b: _Builder, data: dict) -> None:
    audit = data.get("audit") or []
    if audit:
        b.add(PageBreak())
        b.appendix("A", "Development audit trail")
        b.add(
            Table(
                ["When", "Who", "Role", "Action", "Detail"],
                [[str(e.get("created_at", ""))[:16].replace("T", " "), e.get("username", ""), e.get("role", ""), e.get("action", ""), e.get("detail") or ""] for e in audit],
                "Actions recorded on this project, oldest first",
            )
        )
    b.appendix("B" if audit else "A", "Sign-off")
    b.add(
        Table(
            ["Role", "Name", "Signature", "Date"],
            [["Model developer (analyst)", data.get("generated_by", ""), "", ""], ["Independent validator", "", "", ""], ["Approver", "", "", ""]],
        )
    )


__all__ = ["Document", "build_document", "NARRATIVE_FIELDS"]
