"""Scorecard validation: discrimination (KS, AUC/Gini, ROC), calibration
(a decile table), and stability (PSI on score, CSI on each characteristic).

Convention: `score` is "higher = safer" (as produced by scoring.compute_
scores), matching how the rest of this engine treats WOE and points.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve

_EPS = 1e-4


def compute_ks(bad_flag: pd.Series, score: pd.Series) -> float:
    """KS statistic (%) between the cumulative good and bad distributions
    of score."""
    order = score.sort_values().index
    bad_sorted = bad_flag.loc[order]
    total_good = int((bad_sorted == 0).sum())
    total_bad = int((bad_sorted == 1).sum())
    if total_good == 0 or total_bad == 0:
        return 0.0
    cum_good = (bad_sorted == 0).cumsum() / total_good
    cum_bad = (bad_sorted == 1).cumsum() / total_bad
    return round(float((cum_good - cum_bad).abs().max()) * 100, 2)


def compute_auc_gini(bad_flag: pd.Series, score: pd.Series) -> tuple[float, float]:
    """AUC/Gini for predicting "bad" — since higher score means safer,
    -score is used as the risk-ranking signal for the positive (bad) class."""
    if bad_flag.nunique() < 2:
        return 0.5, 0.0
    auc = roc_auc_score(bad_flag, -score)
    gini = 2 * auc - 1
    return round(float(auc), 4), round(float(gini), 4)


def roc_curve_points(bad_flag: pd.Series, score: pd.Series, max_points: int = 50) -> list[dict[str, float]]:
    if bad_flag.nunique() < 2:
        return []
    fpr, tpr, _ = roc_curve(bad_flag, -score)
    idx = np.linspace(0, len(fpr) - 1, min(max_points, len(fpr))).astype(int)
    return [{"fpr": round(float(fpr[i]), 4), "tpr": round(float(tpr[i]), 4)} for i in idx]


def decile_table(bad_flag: pd.Series, score: pd.Series, n_bins: int = 10) -> list[dict[str, Any]]:
    """One row per score decile, ordered riskiest (lowest score) first —
    the standard lift-chart / calibration table."""
    frame = pd.DataFrame({"score": score, "bad": bad_flag})
    try:
        frame["decile"] = pd.qcut(frame["score"], q=n_bins, duplicates="drop")
    except ValueError:
        frame["decile"] = pd.Categorical([str(frame["score"].iloc[0])] * len(frame))

    total_bad = int((frame["bad"] == 1).sum())
    rows = []
    for interval, sub in frame.groupby("decile", observed=True, sort=True):
        n_total = len(sub)
        n_bad = int((sub["bad"] == 1).sum())
        rows.append(
            {
                "score_range": str(interval),
                "n_total": int(n_total),
                "n_bad": n_bad,
                "bad_rate_pct": round(n_bad / n_total * 100, 2) if n_total else 0.0,
                "pct_of_total_bad": round(n_bad / total_bad * 100, 2) if total_bad else 0.0,
            }
        )
    return rows


def stability_index(reference_labels: pd.Series, comparison_labels: pd.Series) -> dict[str, Any]:
    """Generic PSI/CSI computation between two label distributions."""
    ref_pct = reference_labels.value_counts(normalize=True)
    comp_pct = comparison_labels.value_counts(normalize=True)
    labels = sorted(set(ref_pct.index) | set(comp_pct.index), key=str)

    index_value = 0.0
    buckets = []
    for label in labels:
        r = float(ref_pct.get(label, 0.0))
        c = float(comp_pct.get(label, 0.0))
        contribution = (c - r) * np.log((c + _EPS) / (r + _EPS))
        index_value += contribution
        buckets.append(
            {
                "bucket": str(label),
                "reference_pct": round(r * 100, 2),
                "comparison_pct": round(c * 100, 2),
                "contribution": round(float(contribution), 4),
            }
        )
    return {"index": round(float(index_value), 4), "buckets": buckets}


def population_stability_index(reference_score: pd.Series, comparison_score: pd.Series, n_bins: int = 10) -> dict[str, Any]:
    """PSI on the total score, bucketed by reference-sample quantiles."""
    try:
        _, edges = pd.qcut(reference_score, q=n_bins, retbins=True, duplicates="drop")
    except ValueError:
        edges = np.array([reference_score.min(), reference_score.max()])
    edges = np.unique(edges.astype(float))
    if len(edges) < 2:
        edges = np.array([reference_score.min(), reference_score.max()])
    edges[0], edges[-1] = -np.inf, np.inf

    ref_labels = pd.cut(reference_score, bins=edges, include_lowest=True).astype(str)
    comp_labels = pd.cut(comparison_score, bins=edges, include_lowest=True).astype(str)
    return stability_index(ref_labels, comp_labels)
