"""Written sections of the model development document that the data can't
supply on its own (purpose, data sources, judgements, limitations...).

Each field gets a draft built from the project's own numbers, for the
analyst to edit on the Documentation step. Saved text always wins over the
draft; the draft is only a starting point.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NarrativeField:
    key: str
    title: str
    guidance: str


NARRATIVE_FIELDS: list[NarrativeField] = [
    NarrativeField("purpose_scope", "Purpose and scope", "What decision the model supports, which products/segments it covers, and what it replaces."),
    NarrativeField("data_sources", "Data sources", "Where the development data came from, the extraction date, and the observation period."),
    NarrativeField("exclusions", "Exclusions", "Which records were excluded from development and why."),
    NarrativeField("target_rationale", "Target definition rationale", "Why this bad definition and performance window suit the model's purpose."),
    NarrativeField("key_judgements", "Key modelling judgements", "Choices that shaped the model: variables forced in or out, binning overrides, penalty, final model choice."),
    NarrativeField("limitations", "Limitations", "Known weaknesses, populations the model shouldn't be used for, and compensating controls."),
    NarrativeField("monitoring_plan", "Ongoing monitoring", "Metrics, thresholds and frequency for monitoring the model in production."),
]

FIELD_KEYS = [f.key for f in NARRATIVE_FIELDS]

_TYPE_PURPOSE = {
    "application": "rank new applicants by their likelihood of becoming bad, to support approve/decline and pricing decisions at origination",
    "behavioural": "rank existing customers by their likelihood of becoming bad, to support account management decisions such as limit changes and collections prioritisation",
    "decision_tree": "segment the population into policy groups with distinct risk",
}


def _final_model_name(data: dict[str, Any]) -> str:
    final = data.get("final_model") or {}
    if final.get("source") == "ml_benchmark":
        return {"xgboost": "XGBoost", "random_forest": "Random Forest", "lightgbm": "LightGBM", "catboost": "CatBoost"}.get(
            final.get("algorithm"), str(final.get("algorithm"))
        )
    return "logistic regression scorecard"


def _n(value: Any) -> str:
    return f"{value:,}" if isinstance(value, int) else str(value)


def draft_narrative(data: dict[str, Any]) -> dict[str, str]:
    """A draft for every narrative field, from whatever project data exists."""
    profile = data.get("data_profile") or {}
    target = data.get("target_definition") or {}
    definition = target.get("definition") or {}
    target_summary = target.get("summary") or {}
    sampling = data.get("sampling") or {}
    sampling_config = sampling.get("config") or {}
    sampling_summary = sampling.get("summary") or {}
    selection = data.get("variable_selection") or {}
    model = data.get("modeling") or {}
    validation = data.get("validation") or {}
    model_name = _final_model_name(data)

    purpose = (
        f"This {data.get('scorecard_type', 'credit')} model is developed to "
        f"{_TYPE_PURPOSE.get(data.get('scorecard_type', ''), 'rank accounts by risk')}. "
        f"The final model is a {model_name}. "
        "[State the products, channels and segments in scope, and any model this replaces.]"
    )

    data_sources = (
        f"The development dataset ({profile.get('original_filename', 'uploaded file')}) contains "
        f"{_n(profile.get('n_rows', 'N'))} records and {_n(profile.get('n_columns', 'N'))} columns. "
        "[State the source systems, extraction date and the observation period the records cover.]"
    )

    excluded_target = target_summary.get("n_excluded", 0) or 0
    excluded_sampling = (sampling_summary.get("excluded") or {}).get("n_total", 0) or 0
    exclusion_parts = []
    if definition.get("exclude_values"):
        exclusion_parts.append(
            f"{_n(excluded_target)} records were excluded at target definition because "
            f"{definition.get('exclude_column') or definition.get('target_column')} took the value(s) "
            f"{', '.join(map(str, definition['exclude_values']))}"
        )
    elif excluded_target:
        exclusion_parts.append(f"{_n(excluded_target)} records were excluded at target definition")
    if excluded_sampling:
        exclusion_parts.append(f"{_n(excluded_sampling)} records were excluded at sampling")
    exclusions = (
        (". ".join(exclusion_parts) + ". " if exclusion_parts else "No records were excluded by the tool. ")
        + "[List any exclusions applied before the data was loaded, e.g. fraud, deceased, policy declines, and why.]"
    )

    if not definition.get("target_column"):
        bad_rule = "[the bad definition]"
    elif definition.get("mode") == "threshold":
        bad_rule = f"{definition.get('target_column')} at or above {definition.get('threshold')}"
    else:
        bad_rule = f"{definition.get('target_column')} in {', '.join(map(str, definition.get('bad_values') or []))}"
    window = definition.get("performance_window_months")
    target_rationale = (
        f"An account is classed as bad when {bad_rule}"
        + (f", observed over a {window}-month performance window" if window else "")
        + f". This gives a development bad rate of {target_summary.get('bad_rate_pct', 'N')}% "
        f"({_n(target_summary.get('n_bad', 'N'))} bads). "
        "[Explain why this definition and window match the model's purpose, e.g. roll-rate or vintage analysis.]"
    )

    judgements = []
    config = selection.get("config") or {}
    if config:
        judgements.append(
            f"Variables were screened on IV ≥ {config.get('min_iv')}, pairwise correlation ≤ {config.get('max_corr')} "
            f"and VIF ≤ {config.get('max_vif')}, leaving {len(selection.get('selected') or [])} candidates."
        )
    if model:
        penalty = model.get("penalty", "none")
        judgements.append(
            f"The logistic model uses {len(model.get('variables') or [])} variables"
            + (f" with an {penalty.upper()} penalty (α = {model.get('alpha')})" if penalty != "none" else " without a penalty")
            + "."
        )
    if (data.get("final_model") or {}).get("source") == "ml_benchmark":
        judgements.append(f"A {model_name} was chosen as the final model over the logistic scorecard.")
    candidates = data.get("candidates") or []
    if candidates:
        judgements.append(f"{len(candidates)} model candidates were fitted and compared on train, test and OOT discrimination.")
    key_judgements = " ".join(judgements) + " [Add the reasoning behind each choice.]"

    limitation_parts = []
    train = validation.get("train") or {}
    for sample, label in (("test", "test"), ("oot", "out-of-time")):
        m = validation.get(sample) or {}
        if train.get("gini") and m.get("gini") is not None and train["gini"] > 0:
            drop = (train["gini"] - m["gini"]) / train["gini"]
            if drop > 0.1:
                limitation_parts.append(f"Discrimination falls by {drop * 100:.0f}% on the {label} sample (Gini {m['gini']} vs {train['gini']} on train).")
    psi_oot = (validation.get("psi_oot_vs_train") or {}).get("index")
    if psi_oot is not None and psi_oot >= 0.1:
        limitation_parts.append(f"The out-of-time population has shifted (PSI {psi_oot}).")
    if not sampling_config.get("oot_size"):
        limitation_parts.append("No out-of-time sample was held out, so stability over time is untested.")
    limitations = (" ".join(limitation_parts) + " " if limitation_parts else "") + (
        "[Describe populations the model shouldn't be used for and any compensating controls.]"
    )

    monitoring_plan = (
        "Monitor monthly: population stability (PSI on the score; alert at 0.1, act at 0.25), "
        "characteristic stability (CSI on each model variable), and — once outcomes mature — "
        f"Gini and KS against the development values (test Gini {(validation.get('test') or {}).get('gini', 'N')}). "
        "[Confirm thresholds, owners and escalation.]"
    )

    return {
        "purpose_scope": purpose,
        "data_sources": data_sources,
        "exclusions": exclusions,
        "target_rationale": target_rationale,
        "key_judgements": key_judgements,
        "limitations": limitations,
        "monitoring_plan": monitoring_plan,
    }


def resolve_narrative(data: dict[str, Any]) -> dict[str, str]:
    """Saved text where the analyst has written some, the draft otherwise."""
    saved = data.get("narrative") or {}
    drafts = draft_narrative(data)
    return {key: (saved.get(key) or "").strip() or drafts[key] for key in FIELD_KEYS}
